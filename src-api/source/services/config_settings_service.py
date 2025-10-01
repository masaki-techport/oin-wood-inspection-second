"""
Configuration-based Settings Service

This service manages application settings using INI configuration files
instead of database storage, providing a simpler and more maintainable approach.
"""

import os
import configparser
import threading
import logging
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime

logger = logging.getLogger('ConfigSettingsService')

class ConfigSettingsService:
    """
    Configuration file-based settings service.
    
    Manages settings using INI files with real-time updates and observer pattern
    for notifying components when settings change.
    """
    
    def __init__(self, config_path: str = None):
        """
        Initialize the configuration settings service.
        
        Args:
            config_path: Path to the settings.ini file. If None, uses default path.
        """
        if config_path is None:
            # Default to config/settings.ini relative to the project root
            self.config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                'config', 
                'settings.ini'
            )
        else:
            self.config_path = config_path
            
        self.config = configparser.ConfigParser()
        self._lock = threading.RLock()
        self._subscribers: List[Callable[[str, Any], None]] = []
        
        # Load configuration on initialization
        self._load_config()
        
        logger.info(f"ConfigSettingsService initialized with config: {self.config_path}")
    
    def _load_config(self) -> bool:
        """
        Load configuration from INI file.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not os.path.exists(self.config_path):
                logger.warning(f"Config file not found: {self.config_path}")
                self._create_default_config()
            
            self.config.read(self.config_path, encoding='utf-8')
            logger.info(f"Configuration loaded from: {self.config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            return False
    
    def _create_default_config(self):
        """Create default configuration file if it doesn't exist."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            
            # Create default configuration
            default_config = configparser.ConfigParser()
            
            # Add INSPECTION section with default values
            default_config.add_section('INSPECTION')
            default_config.set('INSPECTION', 'camera_exposure', '1000')
            default_config.set('INSPECTION', 'lighting_intensity', '50')
            default_config.set('INSPECTION', 'ai_threshold', '50')
            default_config.set('INSPECTION', 'length_threshold', '10.0')

            
            # Add CALCULATED_RESOLUTION section with default mm per pixel values
            default_config.add_section('CALCULATED_RESOLUTION')
            default_config.set('CALCULATED_RESOLUTION', 'horizontal_mm_per_pixel', '0.245833')
            default_config.set('CALCULATED_RESOLUTION', 'vertical_mm_per_pixel', '0.288889')
            
            # Write to file
            with open(self.config_path, 'w', encoding='utf-8') as f:
                default_config.write(f)
                
            logger.info(f"Created default configuration: {self.config_path}")
            
        except Exception as e:
            logger.error(f"Error creating default configuration: {e}")
    
    def _save_config(self) -> bool:
        """
        Save configuration to INI file.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with self._lock:
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    self.config.write(f)
                logger.debug(f"Configuration saved to: {self.config_path}")
                return True
                
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            return False
    
    def get_length_threshold(self) -> float:
        """
        Get the current length threshold value.
        
        Returns:
            float: Length threshold value (default: 10.0)
        """
        try:
            with self._lock:
                if self.config.has_option('INSPECTION', 'length_threshold'):
                    return self.config.getfloat('INSPECTION', 'length_threshold')
                else:
                    logger.warning("Length threshold not found in config, using default: 10.0")
                    return 10.0
        except Exception as e:
            logger.error(f"Error getting length threshold: {e}")
            return 10.0
    
    def get_ai_threshold(self) -> int:
        """
        Get the current AI threshold value.
        
        Returns:
            int: AI threshold value (default: 50)
        """
        try:
            with self._lock:
                if self.config.has_option('INSPECTION', 'ai_threshold'):
                    return self.config.getint('INSPECTION', 'ai_threshold')
                else:
                    logger.warning("AI threshold not found in config, using default: 50")
                    return 50
        except Exception as e:
            logger.error(f"Error getting AI threshold: {e}")
            return 50
    
    def get_temp_section_size(self) -> int:
        """
        Get the current temp section size value.
        
        Returns:
            int: Temp section size value (default: 5)
        """
        try:
            with self._lock:
                if self.config.has_option('INSPECTION', 'temp_section_size'):
                    return self.config.getint('INSPECTION', 'temp_section_size')
                else:
                    logger.warning("Temp section size not found in config, using default: 5")
                    return 5
        except Exception as e:
            logger.error(f"Error getting temp section size: {e}")
            return 5
    
    def get_temp_section_max_visible(self) -> int:
        """
        Get the current temp section max visible value.
        
        Returns:
            int: Temp section max visible value (default: -1 for infinite)
        """
        try:
            with self._lock:
                if self.config.has_option('INSPECTION', 'temp_section_max_visible'):
                    return self.config.getint('INSPECTION', 'temp_section_max_visible')
                else:
                    logger.warning("Temp section max visible not found in config, using default: -1")
                    return -1
        except Exception as e:
            logger.error(f"Error getting temp section max visible: {e}")
            return -1
    
    def get_camera_exposure(self) -> int:
        """
        Get the current camera exposure value.
        
        Returns:
            int: Camera exposure value (default: 1000)
        """
        try:
            with self._lock:
                if self.config.has_option('INSPECTION', 'camera_exposure'):
                    return self.config.getint('INSPECTION', 'camera_exposure')
                else:
                    logger.warning("Camera exposure not found in config, using default: 1000")
                    return 1000
        except Exception as e:
            logger.error(f"Error getting camera exposure: {e}")
            return 1000
    
    def get_lighting_intensity(self) -> int:
        """
        Get the current lighting intensity value.
        
        Returns:
            int: Lighting intensity value (default: 50)
        """
        try:
            with self._lock:
                if self.config.has_option('INSPECTION', 'lighting_intensity'):
                    return self.config.getint('INSPECTION', 'lighting_intensity')
                else:
                    logger.warning("Lighting intensity not found in config, using default: 50")
                    return 50
        except Exception as e:
            logger.error(f"Error getting lighting intensity: {e}")
            return 50
    

    
    def get_horizontal_mm_per_pixel(self) -> float:
        """
        Get the current horizontal mm per pixel value (分解能_横).
        
        Returns:
            float: Horizontal mm per pixel value (default: 0.245833)
        """
        try:
            with self._lock:
                if self.config.has_option('CALCULATED_RESOLUTION', 'horizontal_mm_per_pixel'):
                    return self.config.getfloat('CALCULATED_RESOLUTION', 'horizontal_mm_per_pixel')
                else:
                    logger.warning("Horizontal mm per pixel not found in config, using default: 0.245833")
                    return 0.245833
        except Exception as e:
            logger.error(f"Error getting horizontal mm per pixel: {e}")
            return 0.245833
    
    def get_vertical_mm_per_pixel(self) -> float:
        """
        Get the current vertical mm per pixel value (分解能_縦).
        
        Returns:
            float: Vertical mm per pixel value (default: 0.288889)
        """
        try:
            with self._lock:
                if self.config.has_option('CALCULATED_RESOLUTION', 'vertical_mm_per_pixel'):
                    return self.config.getfloat('CALCULATED_RESOLUTION', 'vertical_mm_per_pixel')
                else:
                    logger.warning("Vertical mm per pixel not found in config, using default: 0.288889")
                    return 0.288889
        except Exception as e:
            logger.error(f"Error getting vertical mm per pixel: {e}")
            return 0.288889
    
    def get_all_settings(self) -> Dict[str, Any]:
        """
        Get all inspection settings.
        
        Returns:
            Dict[str, Any]: All settings values
        """
        try:
            with self._lock:
                return {
                    'camera_exposure': self.get_camera_exposure(),
                    'lighting_intensity': self.get_lighting_intensity(),
                    'ai_threshold': self.get_ai_threshold(),
                    'length_threshold': self.get_length_threshold(),
                    'horizontal_mm_per_pixel': self.get_horizontal_mm_per_pixel(),
                    'vertical_mm_per_pixel': self.get_vertical_mm_per_pixel()
                }
        except Exception as e:
            logger.error(f"Error getting all settings: {e}")
            return {
                'camera_exposure': 1000,
                'lighting_intensity': 50,
                'ai_threshold': 50,
                'length_threshold': 10.0,
                'horizontal_mm_per_pixel': 0.245833,
                'vertical_mm_per_pixel': 0.288889
            }
    
    def update_settings(self, **kwargs) -> bool:
        """
        Update multiple settings at once.
        
        Args:
            **kwargs: Settings to update (camera_exposure, lighting_intensity, ai_threshold, length_threshold)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with self._lock:
                # Ensure INSPECTION section exists
                if not self.config.has_section('INSPECTION'):
                    self.config.add_section('INSPECTION')
                
                changes = {}
                
                # Validate and update each setting
                for key, value in kwargs.items():
                    if key in ['camera_exposure', 'lighting_intensity', 'ai_threshold', 'length_threshold']:
                        # Validate values
                        if key == 'camera_exposure':
                            if not isinstance(value, int) or not 0 <= value <= 100000:
                                raise ValueError(f"Camera exposure must be integer between 0-100000, got: {value}")
                        elif key == 'lighting_intensity':
                            if not isinstance(value, int) or not 0 <= value <= 100:
                                raise ValueError(f"Lighting intensity must be integer between 0-100, got: {value}")
                        elif key == 'ai_threshold':
                            if not isinstance(value, int) or not 10 <= value <= 100:
                                raise ValueError(f"AI threshold must be integer between 10-100, got: {value}")
                        elif key == 'length_threshold':
                            # Remove range limitation - allow any positive value
                            if not isinstance(value, (int, float)) or value <= 0:
                                raise ValueError(f"Length threshold must be a positive number, got: {value}")
                        
                        # Get old value for change notification
                        old_value = self.config.get('INSPECTION', key, fallback=None)
                        
                        # Update the setting
                        self.config.set('INSPECTION', key, str(value))
                        changes[key] = {'old': old_value, 'new': value}
                        
                        logger.debug(f"Updated setting: {key} = {value}")
                    else:
                        logger.warning(f"Unknown setting key: {key}")
                
                # Save configuration
                if changes and self._save_config():
                    # Notify subscribers about changes
                    for key, change in changes.items():
                        self._notify_subscribers(key, change['new'])
                    
                    logger.info(f"Settings updated successfully: {list(changes.keys())}")
                    return True
                else:
                    return False
                    
        except Exception as e:
            logger.error(f"Error updating settings: {e}")
            return False
    
    def update_length_threshold(self, value: float) -> bool:
        """
        Update the length threshold setting (no range limitation).
        
        Args:
            value: New length threshold value (any positive value)
            
        Returns:
            bool: True if successful, False otherwise
        """
        return self.update_settings(length_threshold=value)
    
    def update_ai_threshold(self, value: int) -> bool:
        """
        Update the AI threshold setting.
        
        Args:
            value: New AI threshold value
            
        Returns:
            bool: True if successful, False otherwise
        """
        return self.update_settings(ai_threshold=value)
    

    
    def update_resolution_mm_per_pixel(self, horizontal_mm_per_pixel: float, vertical_mm_per_pixel: float) -> bool:
        """
        Update the calculated resolution settings (mm per pixel values).
        
        Args:
            horizontal_mm_per_pixel: Horizontal mm per pixel (分解能_横)
            vertical_mm_per_pixel: Vertical mm per pixel (分解能_縦)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with self._lock:
                # Validate values
                if not isinstance(horizontal_mm_per_pixel, (int, float)) or horizontal_mm_per_pixel <= 0:
                    raise ValueError(f"Horizontal mm per pixel must be a positive number, got: {horizontal_mm_per_pixel}")
                if not isinstance(vertical_mm_per_pixel, (int, float)) or vertical_mm_per_pixel <= 0:
                    raise ValueError(f"Vertical mm per pixel must be a positive number, got: {vertical_mm_per_pixel}")
                
                # Ensure CALCULATED_RESOLUTION section exists
                if not self.config.has_section('CALCULATED_RESOLUTION'):
                    self.config.add_section('CALCULATED_RESOLUTION')
                
                # Get old values for change notification
                old_horizontal = self.config.get('CALCULATED_RESOLUTION', 'horizontal_mm_per_pixel', fallback=None)
                old_vertical = self.config.get('CALCULATED_RESOLUTION', 'vertical_mm_per_pixel', fallback=None)
                
                # Update the settings
                self.config.set('CALCULATED_RESOLUTION', 'horizontal_mm_per_pixel', str(horizontal_mm_per_pixel))
                self.config.set('CALCULATED_RESOLUTION', 'vertical_mm_per_pixel', str(vertical_mm_per_pixel))
                
                # Save configuration
                if self._save_config():
                    # Notify subscribers about changes
                    if old_horizontal != str(horizontal_mm_per_pixel):
                        self._notify_subscribers('horizontal_mm_per_pixel', horizontal_mm_per_pixel)
                    if old_vertical != str(vertical_mm_per_pixel):
                        self._notify_subscribers('vertical_mm_per_pixel', vertical_mm_per_pixel)
                    
                    logger.info(f"Resolution mm per pixel updated: h={horizontal_mm_per_pixel}, v={vertical_mm_per_pixel}")
                    return True
                else:
                    return False
                    
        except Exception as e:
            logger.error(f"Error updating resolution mm per pixel: {e}")
            return False
    
    def subscribe_to_changes(self, callback: Callable[[str, Any], None]):
        """
        Subscribe to setting change notifications.
        
        Args:
            callback: Function to call when settings change (setting_name, new_value)
        """
        with self._lock:
            if callback not in self._subscribers:
                self._subscribers.append(callback)
                logger.debug(f"Added settings change subscriber: {callback.__name__}")
    
    def unsubscribe_from_changes(self, callback: Callable[[str, Any], None]):
        """
        Unsubscribe from setting change notifications.
        
        Args:
            callback: Function to remove from subscribers
        """
        with self._lock:
            if callback in self._subscribers:
                self._subscribers.remove(callback)
                logger.debug(f"Removed settings change subscriber: {callback.__name__}")
    
    def _notify_subscribers(self, setting_name: str, new_value: Any):
        """
        Notify all subscribers about a setting change.
        
        Args:
            setting_name: Name of the changed setting
            new_value: New value of the setting
        """
        try:
            for callback in self._subscribers[:]:  # Copy list to avoid concurrent modification
                try:
                    callback(setting_name, new_value)
                except Exception as e:
                    logger.error(f"Error notifying subscriber {callback.__name__}: {e}")
        except Exception as e:
            logger.error(f"Error in _notify_subscribers: {e}")
    
    def reload_config(self) -> bool:
        """
        Reload configuration from file.
        
        Returns:
            bool: True if successful, False otherwise
        """
        with self._lock:
            return self._load_config()


# Global instance for easy access
_config_settings_service = None

def get_config_settings_service() -> ConfigSettingsService:
    """
    Get the global configuration settings service instance.
    
    Returns:
        ConfigSettingsService: Global instance
    """
    global _config_settings_service
    if _config_settings_service is None:
        _config_settings_service = ConfigSettingsService()
    return _config_settings_service

def get_current_length_threshold() -> float:
    """
    Get the current length threshold from configuration.
    
    Returns:
        float: Current length threshold value
    """
    try:
        service = get_config_settings_service()
        return service.get_length_threshold()
    except Exception as e:
        logger.error(f"Error getting current length threshold: {e}")
        return 10.0  # Default fallback

def get_current_ai_threshold() -> int:
    """
    Get the current AI threshold from configuration.
    
    Returns:
        int: Current AI threshold value
    """
    try:
        service = get_config_settings_service()
        return service.get_ai_threshold()
    except Exception as e:
        logger.error(f"Error getting current AI threshold: {e}")
        return 50  # Default fallback

def get_current_resolution_settings() -> tuple[float, float]:
    """
    Get the current resolution settings (mm per pixel) from configuration.
    
    Returns:
        tuple[float, float]: (horizontal_mm_per_pixel, vertical_mm_per_pixel)
    """
    try:
        service = get_config_settings_service()
        horizontal = service.get_horizontal_mm_per_pixel()
        vertical = service.get_vertical_mm_per_pixel()
        return (horizontal, vertical)
    except Exception as e:
        logger.error(f"Error getting current resolution settings: {e}")
        return (0.245833, 0.288889)  # Default fallback

def get_current_temp_section_size() -> int:
    """
    Get the current temp section size from configuration.
    
    Returns:
        int: Temp section size value
    """
    try:
        service = get_config_settings_service()
        return service.get_temp_section_size()
    except Exception as e:
        logger.error(f"Error getting current temp section size: {e}")
        return 5  # Default fallback

def get_current_temp_section_max_visible() -> int:
    """
    Get the current temp section max visible from configuration.
    
    Returns:
        int: Temp section max visible value (-1 for infinite)
    """
    try:
        service = get_config_settings_service()
        return service.get_temp_section_max_visible()
    except Exception as e:
        logger.error(f"Error getting current temp section max visible: {e}")
        return -1  # Default fallback