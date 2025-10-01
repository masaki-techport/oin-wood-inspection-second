"""
Settings Service
Manages real-time settings updates and integration with the camera and analysis systems
"""

import threading
import logging
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime

from services.config_settings_service import get_config_settings_service

# Configure logging
logger = logging.getLogger('SettingsService')

class ParameterSubscriber:
    """Interface for components that need to be notified of parameter changes"""
    
    def on_parameter_updated(self, parameter_name: str, old_value: Any, new_value: Any) -> bool:
        """
        Handle parameter update notification
        
        Args:
            parameter_name: Name of the parameter that changed
            old_value: Previous value
            new_value: New value
            
        Returns:
            True if update was successful, False otherwise
        """
        raise NotImplementedError

class SettingsService:
    """
    Centralized settings management service with real-time updates
    """
    
    def __init__(self):
        self._config_service = get_config_settings_service()
        self._subscribers: List[ParameterSubscriber] = []
        self._lock = threading.RLock()  # Reentrant lock for nested calls
        self._cached_length_threshold = 10.0
        self._cached_ai_threshold = 50
        self._cached_temp_section_size = 5
        self._cached_temp_section_max_visible = -1
        self._last_update = None
        self._cache_ttl = 300  # 5 minutes cache TTL
        
        # Subscribe to config changes
        self._config_service.subscribe_to_changes(self._on_config_changed)
        
        logger.info("SettingsService initialized")
    
    def _on_config_changed(self, section: str, key: str, value: Any) -> None:
        """Handle configuration changes from the config service"""
        with self._lock:
            if section == "INSPECTION":
                if key == "length_threshold":
                    old_value = self._cached_length_threshold
                    self._cached_length_threshold = float(value)
                    self._last_update = datetime.now()
                    self._notify_subscribers('length_threshold', old_value, self._cached_length_threshold)
                elif key == "ai_threshold":
                    old_value = self._cached_ai_threshold
                    self._cached_ai_threshold = int(value)
                    self._last_update = datetime.now()
                    self._notify_subscribers('ai_threshold', old_value, self._cached_ai_threshold)
                elif key == "temp_section_size":
                    old_value = self._cached_temp_section_size
                    self._cached_temp_section_size = int(value)
                    self._last_update = datetime.now()
                    self._notify_subscribers('temp_section_size', old_value, self._cached_temp_section_size)
                elif key == "temp_section_max_visible":
                    old_value = self._cached_temp_section_max_visible
                    self._cached_temp_section_max_visible = int(value)
                    self._last_update = datetime.now()
                    self._notify_subscribers('temp_section_max_visible', old_value, self._cached_temp_section_max_visible)
    
    def subscribe(self, subscriber: ParameterSubscriber) -> None:
        """
        Subscribe to parameter update notifications
        
        Args:
            subscriber: Object that implements ParameterSubscriber interface
        """
        with self._lock:
            if subscriber not in self._subscribers:
                self._subscribers.append(subscriber)
                logger.info(f"Added subscriber: {type(subscriber).__name__}")
    
    def unsubscribe(self, subscriber: ParameterSubscriber) -> None:
        """
        Unsubscribe from parameter update notifications
        
        Args:
            subscriber: Subscriber to remove
        """
        with self._lock:
            if subscriber in self._subscribers:
                self._subscribers.remove(subscriber)
                logger.info(f"Removed subscriber: {type(subscriber).__name__}")
    
    def _notify_subscribers(self, parameter_name: str, old_value: Any, new_value: Any) -> None:
        """
        Notify all subscribers of parameter changes
        
        Args:
            parameter_name: Name of changed parameter
            old_value: Previous value
            new_value: New value
        """
        failed_subscribers = []
        
        with self._lock:
            for subscriber in self._subscribers:
                try:
                    success = subscriber.on_parameter_updated(parameter_name, old_value, new_value)
                    if not success:
                        logger.warning(f"Subscriber {type(subscriber).__name__} failed to update {parameter_name}")
                except Exception as e:
                    logger.error(f"Error notifying subscriber {type(subscriber).__name__}: {e}")
                    failed_subscribers.append(subscriber)
        
        # Remove failed subscribers to prevent future errors
        for subscriber in failed_subscribers:
            self.unsubscribe(subscriber)
    
    def _is_cache_valid(self) -> bool:
        """Check if cached settings are still valid"""
        if self._last_update is None:
            return False
        return (datetime.now() - self._last_update).total_seconds() < self._cache_ttl
    
    
    def get_current_settings(self, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """
        Get current settings with caching
        
        Args:
            force_refresh: Force refresh from configuration
            
        Returns:
            Current settings dictionary or None if error
        """
        with self._lock:
            # Return cached if valid and not forcing refresh
            if not force_refresh and self._is_cache_valid():
                return {
                    'camera_exposure': self._config_service.get_camera_exposure(),
                    'lighting_intensity': self._config_service.get_lighting_intensity(),
                    'ai_threshold': self._cached_ai_threshold,
                    'length_threshold': self._cached_length_threshold,
                    'temp_section_size': self._cached_temp_section_size,
                    'temp_section_max_visible': self._cached_temp_section_max_visible
                }
            
            try:
                # Get settings from config service
                settings = {
                    'camera_exposure': self._config_service.get_camera_exposure(),
                    'lighting_intensity': self._config_service.get_lighting_intensity(),
                    'ai_threshold': self._config_service.get_ai_threshold(),
                    'length_threshold': self._config_service.get_length_threshold(),
                    'temp_section_size': self._config_service.get_temp_section_size(),
                    'temp_section_max_visible': self._config_service.get_temp_section_max_visible()
                }
                
                # Update cache
                self._cached_length_threshold = settings['length_threshold']
                self._cached_ai_threshold = settings['ai_threshold']
                self._cached_temp_section_size = settings['temp_section_size']
                self._cached_temp_section_max_visible = settings['temp_section_max_visible']
                self._last_update = datetime.now()
                
                logger.debug(f"Loaded settings from configuration: {settings}")
                return settings
                    
            except Exception as e:
                logger.error(f"Unexpected error getting settings: {e}")
                return None
    
    def update_settings(self, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Update settings and notify subscribers
        
        Args:
            **kwargs: Setting fields to update
            
        Returns:
            Updated settings dictionary or None if error
        """
        try:
            # Update settings in configuration file
            for key, value in kwargs.items():
                if key == 'camera_exposure':
                    self._config_service.update_settings(camera_exposure=value)
                elif key == 'lighting_intensity':
                    self._config_service.update_settings(lighting_intensity=value)
                elif key == 'ai_threshold':
                    self._config_service.update_ai_threshold(value)
                elif key == 'length_threshold':
                    self._config_service.update_length_threshold(value)
            
            # Get updated settings
            updated_settings = self.get_current_settings(force_refresh=True)
            
            logger.info(f"Settings updated: {kwargs}")
            return updated_settings
                
        except Exception as e:
            logger.error(f"Unexpected error updating settings: {e}")
            return None
    
    def get_length_threshold(self) -> float:
        """
        Get current length threshold (cached for performance)
        
        Returns:
            Current length threshold value
        """
        with self._lock:
            if self._is_cache_valid():
                return self._cached_length_threshold
            
            # Refresh cache
            settings = self.get_current_settings(force_refresh=True)
            if settings:
                return settings['length_threshold']
            
            # Fallback to default
            logger.warning("Using default length threshold due to cache miss")
            return 10.0
    
    def get_ai_threshold(self) -> int:
        """
        Get current AI threshold (cached for performance)
        
        Returns:
            Current AI threshold value
        """
        with self._lock:
            if self._is_cache_valid():
                return self._cached_ai_threshold
            
            # Refresh cache
            settings = self.get_current_settings(force_refresh=True)
            if settings:
                return settings['ai_threshold']
            
            # Fallback to default
            logger.warning("Using default AI threshold due to cache miss")
            return 50
    
    def get_temp_section_size(self) -> int:
        """
        Get current temp section size (cached for performance)
        
        Returns:
            Current temp section size value
        """
        with self._lock:
            if self._is_cache_valid():
                return self._cached_temp_section_size
            
            # Refresh cache
            settings = self.get_current_settings(force_refresh=True)
            if settings:
                return settings['temp_section_size']
            
            # Fallback to default
            logger.warning("Using default temp section size due to cache miss")
            return 5
    
    def get_temp_section_max_visible(self) -> int:
        """
        Get current temp section max visible (cached for performance)
        
        Returns:
            Current temp section max visible value (-1 for infinite)
        """
        with self._lock:
            if self._is_cache_valid():
                return self._cached_temp_section_max_visible
            
            # Refresh cache
            settings = self.get_current_settings(force_refresh=True)
            if settings:
                return settings['temp_section_max_visible']
            
            # Fallback to default
            logger.warning("Using default temp section max visible due to cache miss")
            return -1
    
    def update_length_threshold(self, new_threshold: float) -> bool:
        """
        Update length threshold only
        
        Args:
            new_threshold: New length threshold value
            
        Returns:
            True if successful, False otherwise
        """
        if not 1.0 <= new_threshold <= 50.0:
            logger.error(f"Invalid length threshold: {new_threshold}")
            return False
        
        result = self.update_settings(length_threshold=new_threshold)
        return result is not None
    
    def update_ai_threshold(self, new_threshold: int) -> bool:
        """
        Update AI threshold only
        
        Args:
            new_threshold: New AI threshold value
            
        Returns:
            True if successful, False otherwise
        """
        if not 10 <= new_threshold <= 100:
            logger.error(f"Invalid AI threshold: {new_threshold}")
            return False
        
        result = self.update_settings(ai_threshold=new_threshold)
        return result is not None
    
    def create_default_settings(self) -> Optional[Dict[str, Any]]:
        """
        Create default settings
        
        Returns:
            Default settings dictionary or None if error
        """
        return self.update_settings(
            camera_exposure=1000,
            lighting_intensity=50,
            ai_threshold=50,
            length_threshold=10.0
        )
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics for monitoring
        
        Returns:
            Dictionary with cache statistics
        """
        with self._lock:
            return {
                'cached_length_threshold': self._cached_length_threshold,
                'cached_ai_threshold': self._cached_ai_threshold,
                'cached_temp_section_size': self._cached_temp_section_size,
                'cached_temp_section_max_visible': self._cached_temp_section_max_visible,
                'last_update': self._last_update.isoformat() if self._last_update else None,
                'cache_valid': self._is_cache_valid(),
                'subscriber_count': len(self._subscribers),
                'cache_ttl_seconds': self._cache_ttl
            }

# Global settings service instance
_settings_service: Optional[SettingsService] = None

def get_settings_service() -> SettingsService:
    """
    Get global settings service instance (singleton pattern)
    
    Returns:
        Global SettingsService instance
    """
    global _settings_service
    if _settings_service is None:
        _settings_service = SettingsService()
    return _settings_service

# Convenience functions for quick access
def get_current_length_threshold() -> float:
    """Get current length threshold"""
    return get_settings_service().get_length_threshold()

def get_current_ai_threshold() -> int:
    """Get current AI threshold"""
    return get_settings_service().get_ai_threshold()

def update_length_threshold(threshold: float) -> bool:
    """Update length threshold"""
    return get_settings_service().update_length_threshold(threshold)

def update_ai_threshold(threshold: int) -> bool:
    """Update AI threshold"""
    return get_settings_service().update_ai_threshold(threshold)