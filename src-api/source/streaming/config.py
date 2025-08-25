"""
Streaming Configuration Management System
Provides centralized configuration for all streaming services with runtime updates
"""

import os
import json
import logging
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from threading import Lock
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class CameraStreamConfig:
    """Configuration for camera streaming"""
    frame_rate: int = 10
    quality: int = 85
    max_concurrent_streams: int = 5
    buffer_size: int = 10
    timeout_seconds: int = 30
    enable_compression: bool = True
    
    def validate(self) -> List[str]:
        """Validate camera stream configuration"""
        errors = []
        if not 1 <= self.frame_rate <= 60:
            errors.append("frame_rate must be between 1 and 60")
        if not 10 <= self.quality <= 100:
            errors.append("quality must be between 10 and 100")
        if not 1 <= self.max_concurrent_streams <= 50:
            errors.append("max_concurrent_streams must be between 1 and 50")
        if not 1 <= self.buffer_size <= 100:
            errors.append("buffer_size must be between 1 and 100")
        if not 5 <= self.timeout_seconds <= 300:
            errors.append("timeout_seconds must be between 5 and 300")
        return errors


@dataclass
class SSEConfig:
    """Configuration for Server-Sent Events"""
    update_interval: float = 0.5
    max_connections: int = 100
    heartbeat_interval: float = 30.0
    connection_timeout: int = 60
    retry_delay: int = 3000
    enable_compression: bool = False
    
    def validate(self) -> List[str]:
        """Validate SSE configuration"""
        errors = []
        if not 0.1 <= self.update_interval <= 10.0:
            errors.append("update_interval must be between 0.1 and 10.0 seconds")
        if not 1 <= self.max_connections <= 1000:
            errors.append("max_connections must be between 1 and 1000")
        if not 5.0 <= self.heartbeat_interval <= 300.0:
            errors.append("heartbeat_interval must be between 5.0 and 300.0 seconds")
        if not 10 <= self.connection_timeout <= 600:
            errors.append("connection_timeout must be between 10 and 600 seconds")
        if not 1000 <= self.retry_delay <= 30000:
            errors.append("retry_delay must be between 1000 and 30000 milliseconds")
        return errors


@dataclass
class FileStreamConfig:
    """Configuration for file streaming"""
    chunk_size: int = 8192
    max_concurrent_streams: int = 20
    enable_compression: bool = True
    cache_headers: bool = True
    max_file_size_mb: int = 500
    timeout_seconds: int = 60
    
    def validate(self) -> List[str]:
        """Validate file stream configuration"""
        errors = []
        if not 1024 <= self.chunk_size <= 1048576:  # 1KB to 1MB
            errors.append("chunk_size must be between 1024 and 1048576 bytes")
        if not 1 <= self.max_concurrent_streams <= 100:
            errors.append("max_concurrent_streams must be between 1 and 100")
        if not 1 <= self.max_file_size_mb <= 2048:  # Up to 2GB
            errors.append("max_file_size_mb must be between 1 and 2048")
        if not 10 <= self.timeout_seconds <= 600:
            errors.append("timeout_seconds must be between 10 and 600")
        return errors


@dataclass
class DataStreamConfig:
    """Configuration for data streaming (JSON, inspection data)"""
    batch_size: int = 100
    max_concurrent_streams: int = 10
    enable_compression: bool = True
    timeout_seconds: int = 120
    max_memory_mb: int = 100
    
    def validate(self) -> List[str]:
        """Validate data stream configuration"""
        errors = []
        if not 10 <= self.batch_size <= 10000:
            errors.append("batch_size must be between 10 and 10000")
        if not 1 <= self.max_concurrent_streams <= 50:
            errors.append("max_concurrent_streams must be between 1 and 50")
        if not 30 <= self.timeout_seconds <= 600:
            errors.append("timeout_seconds must be between 30 and 600")
        if not 10 <= self.max_memory_mb <= 1000:
            errors.append("max_memory_mb must be between 10 and 1000")
        return errors


@dataclass
class ErrorHandlingConfig:
    """Configuration for error handling and recovery"""
    retry_attempts: int = 3
    retry_delay: float = 1.0
    exponential_backoff: bool = True
    max_retry_delay: float = 30.0
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 60
    
    def validate(self) -> List[str]:
        """Validate error handling configuration"""
        errors = []
        if not 0 <= self.retry_attempts <= 10:
            errors.append("retry_attempts must be between 0 and 10")
        if not 0.1 <= self.retry_delay <= 60.0:
            errors.append("retry_delay must be between 0.1 and 60.0 seconds")
        if not 1.0 <= self.max_retry_delay <= 300.0:
            errors.append("max_retry_delay must be between 1.0 and 300.0 seconds")
        if not 1 <= self.circuit_breaker_threshold <= 50:
            errors.append("circuit_breaker_threshold must be between 1 and 50")
        if not 10 <= self.circuit_breaker_timeout <= 600:
            errors.append("circuit_breaker_timeout must be between 10 and 600 seconds")
        return errors


@dataclass
class MonitoringConfig:
    """Configuration for monitoring and metrics"""
    enable_metrics: bool = True
    metrics_interval: float = 5.0
    enable_health_checks: bool = True
    health_check_interval: float = 30.0
    log_level: str = "INFO"
    max_log_size_mb: int = 100
    
    def validate(self) -> List[str]:
        """Validate monitoring configuration"""
        errors = []
        if not 1.0 <= self.metrics_interval <= 300.0:
            errors.append("metrics_interval must be between 1.0 and 300.0 seconds")
        if not 5.0 <= self.health_check_interval <= 600.0:
            errors.append("health_check_interval must be between 5.0 and 600.0 seconds")
        if self.log_level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            errors.append("log_level must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL")
        if not 1 <= self.max_log_size_mb <= 1000:
            errors.append("max_log_size_mb must be between 1 and 1000")
        return errors


@dataclass
class StreamingConfig:
    """Complete streaming configuration"""
    camera: CameraStreamConfig = field(default_factory=CameraStreamConfig)
    sse: SSEConfig = field(default_factory=SSEConfig)
    file: FileStreamConfig = field(default_factory=FileStreamConfig)
    data: DataStreamConfig = field(default_factory=DataStreamConfig)
    error_handling: ErrorHandlingConfig = field(default_factory=ErrorHandlingConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    
    def validate(self) -> Dict[str, List[str]]:
        """Validate all configuration sections"""
        validation_errors = {}
        
        camera_errors = self.camera.validate()
        if camera_errors:
            validation_errors["camera"] = camera_errors
            
        sse_errors = self.sse.validate()
        if sse_errors:
            validation_errors["sse"] = sse_errors
            
        file_errors = self.file.validate()
        if file_errors:
            validation_errors["file"] = file_errors
            
        data_errors = self.data.validate()
        if data_errors:
            validation_errors["data"] = data_errors
            
        error_errors = self.error_handling.validate()
        if error_errors:
            validation_errors["error_handling"] = error_errors
            
        monitoring_errors = self.monitoring.validate()
        if monitoring_errors:
            validation_errors["monitoring"] = monitoring_errors
            
        return validation_errors
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StreamingConfig':
        """Create configuration from dictionary"""
        return cls(
            camera=CameraStreamConfig(**data.get("camera", {})),
            sse=SSEConfig(**data.get("sse", {})),
            file=FileStreamConfig(**data.get("file", {})),
            data=DataStreamConfig(**data.get("data", {})),
            error_handling=ErrorHandlingConfig(**data.get("error_handling", {})),
            monitoring=MonitoringConfig(**data.get("monitoring", {}))
        )


class StreamingConfigManager:
    """
    Manages streaming configuration with runtime updates and persistence
    """
    
    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize configuration manager
        
        Args:
            config_file: Path to configuration file (optional)
        """
        self.config_file = config_file or self._get_default_config_path()
        self.config = StreamingConfig()
        self._lock = Lock()
        self._change_callbacks: List[Callable[[StreamingConfig], None]] = []
        self._last_modified: Optional[datetime] = None
        
        # Load configuration from file if it exists
        self.load_config()
        
        logger.info(f"StreamingConfigManager initialized with config file: {self.config_file}")
    
    def _get_default_config_path(self) -> str:
        """Get default configuration file path"""
        from __init__ import ROOT_DIR
        config_dir = Path(ROOT_DIR) / "config"
        config_dir.mkdir(exist_ok=True)
        return str(config_dir / "streaming_config.json")
    
    def load_config(self) -> bool:
        """
        Load configuration from file
        
        Returns:
            True if configuration was loaded successfully
        """
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                
                with self._lock:
                    self.config = StreamingConfig.from_dict(data)
                    self._last_modified = datetime.now()
                
                # Validate loaded configuration
                validation_errors = self.config.validate()
                if validation_errors:
                    logger.warning(f"Configuration validation errors: {validation_errors}")
                    return False
                
                logger.info(f"Configuration loaded from {self.config_file}")
                self._notify_change_callbacks()
                return True
            else:
                # Create default configuration file
                self.save_config()
                logger.info(f"Created default configuration at {self.config_file}")
                return True
                
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            return False
    
    def save_config(self) -> bool:
        """
        Save configuration to file
        
        Returns:
            True if configuration was saved successfully
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            
            with self._lock:
                data = self.config.to_dict()
                # Add metadata
                data["_metadata"] = {
                    "version": "1.0",
                    "last_updated": datetime.now().isoformat(),
                    "description": "Streaming services configuration"
                }
            
            with open(self.config_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            self._last_modified = datetime.now()
            logger.info(f"Configuration saved to {self.config_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            return False
    
    def get_config(self) -> StreamingConfig:
        """
        Get current configuration
        
        Returns:
            Current streaming configuration
        """
        with self._lock:
            return self.config
    
    def update_config(self, updates: Dict[str, Any], validate: bool = True) -> bool:
        """
        Update configuration with new values
        
        Args:
            updates: Dictionary of configuration updates
            validate: Whether to validate the updated configuration
            
        Returns:
            True if configuration was updated successfully
        """
        try:
            with self._lock:
                # Create updated configuration
                current_dict = self.config.to_dict()
                
                # Apply updates recursively
                self._deep_update(current_dict, updates)
                
                # Create new configuration object
                new_config = StreamingConfig.from_dict(current_dict)
                
                # Validate if requested
                if validate:
                    validation_errors = new_config.validate()
                    if validation_errors:
                        logger.error(f"Configuration validation failed: {validation_errors}")
                        return False
                
                # Apply the new configuration
                self.config = new_config
                self._last_modified = datetime.now()
            
            # Save to file
            if self.save_config():
                self._notify_change_callbacks()
                logger.info(f"Configuration updated successfully")
                return True
            else:
                logger.error("Failed to save updated configuration")
                return False
                
        except Exception as e:
            logger.error(f"Error updating configuration: {e}")
            return False
    
    def _deep_update(self, base_dict: Dict[str, Any], updates: Dict[str, Any]):
        """Recursively update nested dictionary"""
        for key, value in updates.items():
            if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                self._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value
    
    def register_change_callback(self, callback: Callable[[StreamingConfig], None]):
        """
        Register callback to be called when configuration changes
        
        Args:
            callback: Function to call when configuration changes
        """
        self._change_callbacks.append(callback)
        logger.debug(f"Registered configuration change callback: {callback.__name__}")
    
    def unregister_change_callback(self, callback: Callable[[StreamingConfig], None]):
        """
        Unregister configuration change callback
        
        Args:
            callback: Function to unregister
        """
        if callback in self._change_callbacks:
            self._change_callbacks.remove(callback)
            logger.debug(f"Unregistered configuration change callback: {callback.__name__}")
    
    def _notify_change_callbacks(self):
        """Notify all registered callbacks of configuration changes"""
        for callback in self._change_callbacks:
            try:
                callback(self.config)
            except Exception as e:
                logger.error(f"Error in configuration change callback {callback.__name__}: {e}")
    
    def reload_if_changed(self) -> bool:
        """
        Reload configuration if file has been modified
        
        Returns:
            True if configuration was reloaded
        """
        try:
            if os.path.exists(self.config_file):
                file_mtime = datetime.fromtimestamp(os.path.getmtime(self.config_file))
                if self._last_modified is None or file_mtime > self._last_modified:
                    return self.load_config()
            return False
        except Exception as e:
            logger.error(f"Error checking configuration file modification: {e}")
            return False
    
    def get_section_config(self, section: str) -> Any:
        """
        Get configuration for a specific section
        
        Args:
            section: Configuration section name
            
        Returns:
            Configuration object for the section
        """
        with self._lock:
            return getattr(self.config, section, None)
    
    def update_section_config(self, section: str, updates: Dict[str, Any]) -> bool:
        """
        Update configuration for a specific section
        
        Args:
            section: Configuration section name
            updates: Dictionary of updates for the section
            
        Returns:
            True if section was updated successfully
        """
        return self.update_config({section: updates})


# Global configuration manager instance
config_manager = StreamingConfigManager()


def get_streaming_config() -> StreamingConfig:
    """Get current streaming configuration"""
    return config_manager.get_config()


def update_streaming_config(updates: Dict[str, Any]) -> bool:
    """Update streaming configuration"""
    return config_manager.update_config(updates)


def register_config_change_callback(callback: Callable[[StreamingConfig], None]):
    """Register callback for configuration changes"""
    config_manager.register_change_callback(callback)


def get_camera_config() -> CameraStreamConfig:
    """Get camera streaming configuration"""
    return config_manager.get_section_config("camera")


def get_sse_config() -> SSEConfig:
    """Get SSE configuration"""
    return config_manager.get_section_config("sse")


def get_file_config() -> FileStreamConfig:
    """Get file streaming configuration"""
    return config_manager.get_section_config("file")


def get_data_config() -> DataStreamConfig:
    """Get data streaming configuration"""
    return config_manager.get_section_config("data")


def get_error_handling_config() -> ErrorHandlingConfig:
    """Get error handling configuration"""
    return config_manager.get_section_config("error_handling")


def get_monitoring_config() -> MonitoringConfig:
    """Get monitoring configuration"""
    return config_manager.get_section_config("monitoring")