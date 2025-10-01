"""
Memory results storage with pattern-based cleanup.
"""

import threading
import time
import logging
from collections import OrderedDict
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from .analysis_queue import AnalysisResult
from .exceptions import StorageError

logger = logging.getLogger('MemoryResultsStorage')

@dataclass
class StorageStatistics:
    """Statistics for results storage."""
    total_stored: int = 0
    removed_count: int = 0
    current_size: int = 0
    hit_count: int = 0
    miss_count: int = 0
    cleanup_count: int = 0
    cleaned_count: int = 0
    buffer_discard_cleanups: int = 0
    buffer_clear_cleanups: int = 0
    buffer_overflow_cleanups: int = 0
    
    def get_hit_rate(self) -> float:
        """Get cache hit rate percentage."""
        total_requests = self.hit_count + self.miss_count
        if total_requests == 0:
            return 0.0
        return (self.hit_count / total_requests) * 100.0

class PatternCleanupManager:
    """Manages pattern-based cleanup for analysis results."""
    
    def __init__(self, storage: 'MemoryResultsStorage'):
        self.storage = storage
        self.buffer_discard_callback = None
        self.cleanup_patterns = {
            'buffer_discard': self._handle_buffer_discard,
            'buffer_clear': self._handle_buffer_clear,
            'buffer_overflow': self._handle_buffer_overflow
        }
    
    def set_buffer_discard_callback(self, callback) -> None:
        """Set callback for buffer discard events."""
        self.buffer_discard_callback = callback
    
    def _handle_buffer_discard(self, discarded_image_indices: List[int]) -> None:
        """Handle buffer discard pattern."""
        logger.info(f"Handling buffer discard pattern for {len(discarded_image_indices)} images")
        self.storage.on_buffer_discard(discarded_image_indices)
    
    def _handle_buffer_clear(self, start_timestamp: float, end_timestamp: float) -> None:
        """Handle buffer clear pattern."""
        logger.info(f"Handling buffer clear pattern for timestamp range {start_timestamp} - {end_timestamp}")
        self.storage.on_buffer_clear(start_timestamp, end_timestamp)
    
    def _handle_buffer_overflow(self, overflowed_image_indices: List[int]) -> None:
        """Handle buffer overflow pattern."""
        logger.info(f"Handling buffer overflow pattern for {len(overflowed_image_indices)} images")
        self.storage.on_buffer_discard(overflowed_image_indices)
    
    def handle_cleanup_pattern(self, pattern_type: str, **kwargs) -> None:
        """Handle cleanup pattern based on type."""
        if pattern_type in self.cleanup_patterns:
            self.cleanup_patterns[pattern_type](**kwargs)
        else:
            logger.warning(f"Unknown cleanup pattern: {pattern_type}")

class MemoryResultsStorage:
    """Thread-safe memory storage for analysis results with pattern-based cleanup."""
    
    def __init__(self, max_results: int = 1000, enable_compression: bool = True):
        self.max_results = max_results
        self.enable_compression = enable_compression
        
        # Storage structures
        self.results = {}  # task_id -> AnalysisResult
        self.image_index_map = {}  # image_index -> task_id
        self.timestamp_map = OrderedDict()  # timestamp -> task_id (for time-based queries)
        self.image_hash_map = {}  # image_hash -> task_id (for deduplication)
        
        # Thread safety
        self.lock = threading.RLock()
        
        # Statistics
        self.stats = StorageStatistics()
        
        # Pattern-based cleanup management
        self.pattern_cleanup_manager = PatternCleanupManager(self)
        self.buffer_discard_callback = None
    
    def set_buffer_discard_callback(self, callback) -> None:
        """Set callback for buffer discard events."""
        self.buffer_discard_callback = callback
        self.pattern_cleanup_manager.set_buffer_discard_callback(callback)
    
    def store_result(self, result: AnalysisResult) -> None:
        """Store analysis result with indexing."""
        with self.lock:
            # Check if we need to make space
            if len(self.results) >= self.max_results:
                self._evict_oldest_result()
            
            # Store result
            self.results[result.task_id] = result
            
            # Update indexes
            self.image_index_map[result.image_index] = result.task_id
            self.timestamp_map[result.image_timestamp] = result.task_id
            self.image_hash_map[result.image_hash] = result.task_id
            
            # Update statistics
            self.stats.total_stored += 1
            self.stats.current_size = len(self.results)
            
            logger.debug(f"Stored result for task {result.task_id}, image {result.image_index}")
    
    def get_result_by_task_id(self, task_id: str) -> Optional[AnalysisResult]:
        """Get result by task ID."""
        with self.lock:
            result = self.results.get(task_id)
            if result:
                result.update_access_time()
                self.stats.hit_count += 1
            else:
                self.stats.miss_count += 1
            return result
    
    def get_result_by_image_index(self, image_index: int) -> Optional[AnalysisResult]:
        """Get result by image index."""
        with self.lock:
            task_id = self.image_index_map.get(image_index)
            if task_id:
                result = self.results.get(task_id)
                if result:
                    result.update_access_time()
                    self.stats.hit_count += 1
                else:
                    self.stats.miss_count += 1
                return result
            else:
                self.stats.miss_count += 1
                return None
    
    def get_result_by_timestamp(self, timestamp: float) -> Optional[AnalysisResult]:
        """Get result by timestamp."""
        with self.lock:
            task_id = self.timestamp_map.get(timestamp)
            if task_id:
                result = self.results.get(task_id)
                if result:
                    result.update_access_time()
                    self.stats.hit_count += 1
                else:
                    self.stats.miss_count += 1
                return result
            else:
                self.stats.miss_count += 1
                return None
    
    def get_results_for_range(self, start_timestamp: float, end_timestamp: float) -> List[AnalysisResult]:
        """Get results for time range in FIFO order (oldest first)."""
        with self.lock:
            results = []
            for timestamp, task_id in self.timestamp_map.items():
                if start_timestamp <= timestamp <= end_timestamp:
                    result = self.results.get(task_id)
                    if result and not result.is_discarded:
                        result.update_access_time()
                        results.append(result)
                        self.stats.hit_count += 1
                    else:
                        self.stats.miss_count += 1
            
            # Sort by image_timestamp for FIFO order (oldest first)
            return sorted(results, key=lambda r: r.image_timestamp)
    
    def get_all_results_fifo(self, limit: Optional[int] = None) -> List[AnalysisResult]:
        """Get all results in FIFO order (oldest first)."""
        with self.lock:
            results = []
            for timestamp, task_id in self.timestamp_map.items():
                result = self.results.get(task_id)
                if result and not result.is_discarded:
                    result.update_access_time()
                    results.append(result)
                    self.stats.hit_count += 1
                else:
                    self.stats.miss_count += 1
            
            # Sort by image_timestamp for FIFO order (oldest first)
            sorted_results = sorted(results, key=lambda r: r.image_timestamp)
            
            # Apply limit if specified
            if limit is not None and limit > 0:
                return sorted_results[:limit]
            
            return sorted_results
    
    def remove_result(self, task_id: str) -> bool:
        """Remove result by task ID."""
        with self.lock:
            if task_id not in self.results:
                return False
            
            result = self.results[task_id]
            
            # Remove from indexes
            if result.image_index in self.image_index_map:
                del self.image_index_map[result.image_index]
            if result.image_timestamp in self.timestamp_map:
                del self.timestamp_map[result.image_timestamp]
            if result.image_hash in self.image_hash_map:
                del self.image_hash_map[result.image_hash]
            
            # Remove from storage
            del self.results[task_id]
            
            # Update statistics
            self.stats.removed_count += 1
            self.stats.current_size = len(self.results)
            
            logger.debug(f"Removed result for task {task_id}")
            return True
    
    def cleanup_results_for_discarded_images(self, discarded_image_indices: List[int]) -> int:
        """Remove results for discarded images based on sensor pattern."""
        cleaned_count = 0
        
        with self.lock:
            for image_index in discarded_image_indices:
                task_id = self.image_index_map.get(image_index)
                if task_id and self.remove_result(task_id):
                    cleaned_count += 1
                    logger.debug(f"Cleaned up result for discarded image {image_index}")
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} results for discarded images")
            self.stats.buffer_discard_cleanups += 1
        
        return cleaned_count
    
    def cleanup_results_for_timestamp_range(self, start_timestamp: float, end_timestamp: float) -> int:
        """Remove results for specific timestamp range (when buffer is cleared)."""
        cleaned_count = 0
        
        with self.lock:
            timestamps_to_remove = []
            
            # Create a copy of items to avoid mutation during iteration
            timestamp_items = list(self.timestamp_map.items())
            
            for timestamp, task_id in timestamp_items:
                if start_timestamp <= timestamp <= end_timestamp:
                    if self.remove_result(task_id):
                        cleaned_count += 1
                        timestamps_to_remove.append(timestamp)
            
            # Clean up timestamp map
            for timestamp in timestamps_to_remove:
                self.timestamp_map.pop(timestamp, None)
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} results for timestamp range")
            self.stats.buffer_clear_cleanups += 1
        
        return cleaned_count
    
    def on_buffer_discard(self, discarded_image_indices: List[int]) -> None:
        """Handle buffer discard event - clean up corresponding analysis results."""
        cleaned_count = self.cleanup_results_for_discarded_images(discarded_image_indices)
        
        # Update statistics
        self.stats.cleanup_count += 1
        self.stats.cleaned_count += cleaned_count
        
        logger.info(f"Buffer discard cleanup: removed {cleaned_count} analysis results")
    
    def on_buffer_clear(self, start_timestamp: float, end_timestamp: float) -> None:
        """Handle buffer clear event - clean up all results in timestamp range."""
        cleaned_count = self.cleanup_results_for_timestamp_range(start_timestamp, end_timestamp)
        
        # Update statistics
        self.stats.cleanup_count += 1
        self.stats.cleaned_count += cleaned_count
        
        logger.info(f"Buffer clear cleanup: removed {cleaned_count} analysis results")
    
    def _evict_oldest_result(self) -> None:
        """Evict oldest result to make space."""
        with self.lock:
            if not self.results:
                return
            
            # Find oldest result by creation time
            oldest_task_id = min(
                self.results.keys(),
                key=lambda tid: self.results[tid].created_at
            )
            
            logger.debug(f"Evicting oldest result {oldest_task_id}")
            self.remove_result(oldest_task_id)
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        with self.lock:
            self.stats.current_size = len(self.results)
            
            return {
                'total_stored': self.stats.total_stored,
                'removed_count': self.stats.removed_count,
                'current_size': self.stats.current_size,
                'hit_count': self.stats.hit_count,
                'miss_count': self.stats.miss_count,
                'hit_rate': self.stats.get_hit_rate(),
                'cleanup_count': self.stats.cleanup_count,
                'cleaned_count': self.stats.cleaned_count,
                'buffer_discard_cleanups': self.stats.buffer_discard_cleanups,
                'buffer_clear_cleanups': self.stats.buffer_clear_cleanups,
                'buffer_overflow_cleanups': self.stats.buffer_overflow_cleanups
            }
    
    def clear_all(self) -> None:
        """Clear all stored results."""
        with self.lock:
            self.results.clear()
            self.image_index_map.clear()
            self.timestamp_map.clear()
            self.image_hash_map.clear()
            self.stats.current_size = 0
            
            logger.info("Cleared all stored results")
    
    def get_cleanup_pattern_stats(self) -> Dict[str, Any]:
        """Get cleanup pattern statistics."""
        return {
            'buffer_discard_cleanups': self.stats.buffer_discard_cleanups,
            'buffer_clear_cleanups': self.stats.buffer_clear_cleanups,
            'buffer_overflow_cleanups': self.stats.buffer_overflow_cleanups,
            'total_cleanups': self.stats.cleanup_count,
            'total_cleaned': self.stats.cleaned_count
        }
