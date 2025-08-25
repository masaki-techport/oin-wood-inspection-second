"""
Application Configuration Manager
Handles loading and managing configuration from settings.ini
"""

import os
import configparser
from typing import Dict, Any
from __init__ import SOURCE_DIR, CONFIG_DIR, CONFIG_FILE_NAME, ROOT_DIR

class AppConfig:
    """
    Application configuration manager
    """
    
    def __init__(self, config_file: str = CONFIG_FILE_NAME):
        """
        Initialize configuration manager
        
        Args:
            config_file: Path to the configuration file
        """
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self.load_config()
        
    def load_config(self):
        """
        Load configuration from file, create with defaults if not exists
        """
        self.config_file_path = CONFIG_DIR + "/" + self.config_file
        if os.path.exists(self.config_file_path):
            try:
                self.config.read(self.config_file_path)
                # Use print here since logging isn't initialized yet during config loading
                print(f"[CONFIG] Loaded configuration from {self.config_file}")
            except Exception as e:
                print(f"[CONFIG] Error loading config file: {e}")
                self.create_default_config()
        else:
            print(f"[CONFIG] Configuration file {self.config_file} not found, creating default")
            self.create_default_config()
            
    def create_default_config(self):
        """
        Create default configuration file
        """
        # Debug settings
        self.config.add_section('DEBUG')
        self.config.set('DEBUG', 'debug_mode', '0')
        self.config.set('DEBUG', 'show_debug_windows', '0')
        self.config.set('DEBUG', 'verbose_logging', '0')
        self.config.set('DEBUG', 'debug_capture_time', '0')
        
        # Camera settings
        self.config.add_section('CAMERA')
        self.config.set('CAMERA', 'default_camera_type', 'webcam')
        self.config.set('CAMERA', 'auto_reconnect', '1')
        self.config.set('CAMERA', 'connection_timeout', '5')
        
        # Sensor settings
        self.config.add_section('SENSOR')
        self.config.set('SENSOR', 'simulation_mode', '1')
        self.config.set('SENSOR', 'buffer_duration', '30')
        self.config.set('SENSOR', 'buffer_fps', '5')
        
        # UI settings
        self.config.add_section('UI')
        self.config.set('UI', 'polling_interval', '200')
        self.config.set('UI', 'notification_timeout', '5000')
        
        # Logging settings
        self.config.add_section('LOGGING')
        self.config.set('LOGGING', 'log_directory', './log')
        self.config.set('LOGGING', 'log_level', 'INFO')
        self.config.set('LOGGING', 'rotation_time', '00:00')
        self.config.set('LOGGING', 'retention_days', '7')
        self.config.set('LOGGING', 'max_file_size_mb', '10')
        self.config.set('LOGGING', 'console_logging', '1')
        
        self.save_config()
        
    def save_config(self):
        """
        Save configuration to file
        """
        try:
            with open(CONFIG_DIR + "/" + self.config_file, 'w') as f:
                self.config.write(f)
            # Use print here since logging isn't initialized yet during config loading
            print(f"[CONFIG] Configuration saved to {self.config_file}")
        except Exception as e:
            print(f"[CONFIG] Error saving config file: {e}")
            
    def get(self, section: str, key: str, fallback: Any = None) -> Any:
        """
        Get configuration value
        
        Args:
            section: Configuration section
            key: Configuration key
            fallback: Default value if key not found
            
        Returns:
            Configuration value
        """
        try:
            return self.config.get(section, key, fallback=fallback)
        except:
            return fallback
            
    def getint(self, section: str, key: str, fallback: int = 0) -> int:
        """
        Get integer configuration value
        
        Args:
            section: Configuration section
            key: Configuration key
            fallback: Default value if key not found
            
        Returns:
            Integer configuration value
        """
        try:
            return self.config.getint(section, key, fallback=fallback)
        except:
            return fallback
            
    def getboolean(self, section: str, key: str, fallback: bool = False) -> bool:
        """
        Get boolean configuration value
        
        Args:
            section: Configuration section
            key: Configuration key
            fallback: Default value if key not found
            
        Returns:
            Boolean configuration value
        """
        try:
            return self.config.getboolean(section, key, fallback=fallback)
        except:
            return fallback
            
    def set(self, section: str, key: str, value: str):
        """
        Set configuration value
        
        Args:
            section: Configuration section
            key: Configuration key
            value: Configuration value
        """
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, key, str(value))
        
    def is_debug_mode(self) -> bool:
        """
        Check if debug mode is enabled
        
        Returns:
            True if debug mode is enabled
        """
        return self.getboolean('DEBUG', 'debug_mode', False)
        
    def show_debug_windows(self) -> bool:
        """
        Check if debug windows should be shown
        
        Returns:
            True if debug windows should be shown
        """
        return self.getboolean('DEBUG', 'show_debug_windows', False)
        
    def debug_capture_time(self) -> bool:
        """
        Check if capture time debugging is enabled
        
        Returns:
            True if capture time debugging is enabled
        """
        return self.getboolean('DEBUG', 'debug_capture_time', False)
        
    def get_default_camera_type(self) -> str:
        """
        Get default camera type
        
        Returns:
            Default camera type
        """
        return self.get('CAMERA', 'default_camera_type', 'webcam')
    
    # Logging configuration methods
    def get_log_directory(self) -> str:
        """
        Get log directory path
        
        Returns:
            Log directory path
        """
        return self.get('LOGGING', 'log_directory', './log')
    
    def get_log_level(self) -> str:
        """
        Get logging level
        
        Returns:
            Log level string
        """
        return self.get('LOGGING', 'log_level', 'INFO')
    
    def get_log_retention_days(self) -> int:
        """
        Get log retention period in days
        
        Returns:
            Number of days to retain logs
        """
        return self.getint('LOGGING', 'retention_days', 7)
    
    def get_log_rotation_time(self) -> str:
        """
        Get log rotation time
        
        Returns:
            Log rotation time in HH:MM format
        """
        return self.get('LOGGING', 'rotation_time', '00:00')
    
    def is_console_logging_enabled(self) -> bool:
        """
        Check if console logging is enabled
        
        Returns:
            True if console logging is enabled
        """
        return self.getboolean('LOGGING', 'console_logging', True)

# Global configuration instance
app_config = AppConfig()

server_port = 8000
base_url = f"http://0.0.0.0:{server_port}"

APP_CONFIG = {
    "upload_folder_inspection": os.path.join(ROOT_DIR, "data", "images", "inspection"),
}

DB = {
    "driver": f"sqlite:///{os.path.join(ROOT_DIR, 'data', 'sqlite.db')}",
    "echo": False
}

