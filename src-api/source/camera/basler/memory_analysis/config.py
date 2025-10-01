"""
Configuration management for memory analysis system.
"""

import json
import os
import logging
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional

logger = logging.getLogger('MemoryAnalysisConfig')

@dataclass
class MemoryAnalysisConfig:
    """Configuration for memory analysis system."""
    
    # Core settings
    enabled: bool = True
    queue_size: int = 100
    worker_count: int = 4
    max_results: int = 1000
    cache_size: int = 100
    
    # Performance settings
    analysis_timeout: float = 30.0
    retry_attempts: int = 3
    retry_delay: float = 1.0
    cleanup_interval: int = 60
    memory_limit_mb: int = 512
    
    # Queue settings
    priority_mode: bool = True
    overflow_strategy: str = "drop_oldest"  # drop_oldest, pause_capture, error
    
    # Cache settings
    cache_ttl_seconds: int = 3600
    enable_compression: bool = True
    
    # Monitoring settings
    performance_monitoring: bool = True
    detailed_logging: bool = False
    
    # Fallback settings
    fallback_enabled: bool = True
    fallback_threshold: float = 0.3  # 30% failure rate
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MemoryAnalysisConfig':
        """Create from dictionary."""
        return cls(**data)

class MemoryAnalysisConfigManager:
    """Configuration manager for memory analysis."""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "memory_analysis_config.json"
        self.config = MemoryAnalysisConfig()
        self.load_config()
    
    def load_config(self) -> None:
        """Load configuration from file."""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    file_config = json.load(f)
                    self.config = MemoryAnalysisConfig.from_dict(file_config)
                logger.info(f"Loaded memory analysis config from {self.config_path}")
        except Exception as e:
            logger.warning(f"Failed to load config: {e}, using defaults")
    
    def save_config(self) -> None:
        """Save configuration to file."""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config.to_dict(), f, indent=2)
            logger.info(f"Saved memory analysis config to {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
    
    def get_config(self) -> MemoryAnalysisConfig:
        """Get current configuration."""
        return self.config
    
    def update_config(self, updates: Dict[str, Any]) -> None:
        """Update configuration."""
        config_dict = self.config.to_dict()
        config_dict.update(updates)
        self.config = MemoryAnalysisConfig.from_dict(config_dict)
        self.save_config()
    
    def reset_to_defaults(self) -> None:
        """Reset to default configuration."""
        self.config = MemoryAnalysisConfig()
        self.save_config()
        logger.info("Reset to default configuration")
