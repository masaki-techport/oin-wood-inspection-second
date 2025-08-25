"""
Thread-safe image buffer implementation for Basler camera module.
"""

import threading
from collections import deque
from typing import Dict, Any, List

import logging
logger = logging.getLogger('BaslerCamera.Buffer')

class ImageBuffer:
    """Thread-safe image buffer implementation with memory optimization"""
    
    def __init__(self, max_size: int = 300):
        """Initialize buffer with maximum size"""
        self.buffer = deque(maxlen=max_size)
        self.lock = threading.RLock()
        self.max_size = max_size
        
    def append(self, item: Dict[str, Any]) -> None:
        """Add item to buffer in thread-safe manner"""
        with self.lock:
            self.buffer.append(item)
            
    def clear(self) -> None:
        """Clear buffer in thread-safe manner"""
        with self.lock:
            self.buffer.clear()
            
    def get_snapshot(self) -> List[Dict[str, Any]]:
        """Get a snapshot of the current buffer"""
        with self.lock:
            return list(self.buffer)
            
    def __len__(self) -> int:
        """Get buffer length in thread-safe manner"""
        with self.lock:
            return len(self.buffer)