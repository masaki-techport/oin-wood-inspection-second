"""
Custom exceptions for memory analysis system.
"""

class MemoryAnalysisError(Exception):
    """Base exception for memory analysis system."""
    pass

class AnalysisTaskError(MemoryAnalysisError):
    """Exception raised for analysis task errors."""
    pass

class StorageError(MemoryAnalysisError):
    """Exception raised for storage errors."""
    pass

class CacheError(MemoryAnalysisError):
    """Exception raised for cache errors."""
    pass

class QueueOverflowError(MemoryAnalysisError):
    """Exception raised when analysis queue overflows."""
    pass

class WorkerError(MemoryAnalysisError):
    """Exception raised for worker thread errors."""
    pass

class ConfigurationError(MemoryAnalysisError):
    """Exception raised for configuration errors."""
    pass
