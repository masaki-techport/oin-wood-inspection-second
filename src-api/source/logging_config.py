"""
Centralized Logging Configuration Module
Handles setup and management of application logging with rotation and retention
"""

import os
import logging
import logging.handlers
from datetime import datetime
from typing import Optional
from app_config import app_config

class LoggingConfig:
    """
    Centralized logging configuration and setup
    """
    
    def __init__(self):
        self.logger_initialized = False
        
    def setup_logging(self) -> None:
        """
        Setup centralized logging configuration with rotation and retention
        """
        if self.logger_initialized:
            return
            
        # Get configuration values
        log_dir = app_config.get('LOGGING', 'log_directory', './log')
        log_level = app_config.get('LOGGING', 'log_level', 'INFO')
        rotation_time = app_config.get('LOGGING', 'rotation_time', '00:00')
        retention_days = app_config.getint('LOGGING', 'retention_days', 7)
        max_file_size = app_config.getint('LOGGING', 'max_file_size_mb', 10)
        console_logging = app_config.getboolean('LOGGING', 'console_logging', True)
        
        # Create log directory if it doesn't exist
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
            
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        
        # Clear existing handlers to avoid duplicates
        root_logger.handlers.clear()
        
        # Setup file handler with daily rotation
        log_file_path = os.path.join(log_dir, 'application.log')
        
        # Create daily rotating file handler
        file_handler = logging.handlers.TimedRotatingFileHandler(
            filename=log_file_path,
            when='midnight',
            interval=1,
            backupCount=retention_days,
            encoding='utf-8'
        )
        
        # Set rotation time (default: midnight)
        if rotation_time != '00:00':
            # Parse custom rotation time if needed
            try:
                hour, minute = map(int, rotation_time.split(':'))
                file_handler.atTime = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0).time()
            except ValueError:
                # Fall back to midnight if invalid format
                pass
        
        # Create formatter
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        
        # Setup console handler if enabled
        if console_logging:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)
            
        self.logger_initialized = True
        
        # Log initialization message
        logger = logging.getLogger(__name__)
        logger.info(f"Logging system initialized - Level: {log_level}, Directory: {log_dir}, Retention: {retention_days} days")
        
    def get_logger(self, name: str) -> logging.Logger:
        """
        Get a logger instance with the specified name
        
        Args:
            name: Logger name (typically __name__)
            
        Returns:
            Logger instance
        """
        if not self.logger_initialized:
            self.setup_logging()
        return logging.getLogger(name)
        
    def log_exception(self, logger: logging.Logger, message: str, exc_info: bool = True) -> None:
        """
        Log an exception with full traceback
        
        Args:
            logger: Logger instance to use
            message: Exception message
            exc_info: Whether to include exception info
        """
        logger.error(message, exc_info=exc_info)
        
    def log_startup(self, component_name: str, logger: Optional[logging.Logger] = None) -> None:
        """
        Log a component startup message
        
        Args:
            component_name: Name of the component starting up
            logger: Optional logger instance (creates one if not provided)
        """
        if logger is None:
            logger = self.get_logger(__name__)
        logger.info(f"{component_name} started successfully")
        
    def log_shutdown(self, component_name: str, logger: Optional[logging.Logger] = None) -> None:
        """
        Log a component shutdown message
        
        Args:
            component_name: Name of the component shutting down
            logger: Optional logger instance (creates one if not provided)
        """
        if logger is None:
            logger = self.get_logger(__name__)
        logger.info(f"{component_name} shutdown completed")

# Global logging configuration instance
logging_config = LoggingConfig()

# Convenience function for getting loggers
def get_logger(name: str) -> logging.Logger:
    """
    Convenience function to get a logger instance
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Logger instance
    """
    return logging_config.get_logger(name)