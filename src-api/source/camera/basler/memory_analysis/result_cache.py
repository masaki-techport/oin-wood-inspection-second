"""
Analysis result cache with LRU and pattern-based cleanup.
"""

import threading
import time
import logging
from collections import OrderedDict
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from .analysis_queue import AnalysisResult
from .exceptions import CacheError

logger = logging.getLogger('AnalysisResultCache')

@dataclass
class CacheStatistics:
    """Statistics for result cache."""
    stored_count: int = 0
    hit_count: int = 0
    miss_count: int = 0
    evicted_count: int = 0
    invalidated_count: int = 0
    expired_count: int = 0
    discarded_count: int = 0
    
    def get_hit_rate(self) -> float:
        """Get cache hit rate percentage."""
        total_requests = self.hit_count + self.miss_count
        if total_requests == 0:
            return 0.0
        return (self.hit_count / total_requests) * 100.0

class AnalysisResultCache:
    """LRU cache with pattern-based cleanup for analysis results."""
    
    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self.cache = OrderedDict()  # LRU cache
        self.lock = threading.RLock()
        self.stats = CacheStatistics()
        self.pattern_cleanup_manager = None
    
    def get(self, key: str) -> Optional[AnalysisResult]:
        """Get result from cache."""
        with self.lock:
            if key in self.cache:
                result = self.cache[key]
                
                # Check if result is discarded
                if result.is_discarded:
                    del self.cache[key]
                    self.stats.expired_count += 1
                    return None
                
                # Move to end (most recently used)
                self.cache.move_to_end(key)
                result.update_access_time()
                self.stats.hit_count += 1
                return result
            else:
                self.stats.miss_count += 1
                return None
    
    def put(self, key: str, result: AnalysisResult) -> None:
        """Store result in cache."""
        with self.lock:
            # Remove if already exists
            if key in self.cache:
                del self.cache[key]
            
            # Check size limit
            if len(self.cache) >= self.max_size:
                # Remove least recently used
                self.cache.popitem(last=False)
                self.stats.evicted_count += 1
            
            # Add to cache
            self.cache[key] = result
            self.stats.stored_count += 1
    
    def invalidate(self, key: str) -> bool:
        """Remove result from cache."""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                self.stats.invalidated_count += 1
                return True
            return False
    
    def cleanup_discarded_results(self, discarded_image_indices: List[int]) -> int:
        """Remove results for discarded images based on pattern."""
        cleaned_count = 0
        
        with self.lock:
            keys_to_remove = []
            
            for key, result in self.cache.items():
                if result.image_index in discarded_image_indices:
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del self.cache[key]
                cleaned_count += 1
                self.stats.expired_count += 1
        
        if cleaned_count > 0:
            logger.info(f"Cache cleanup: removed {cleaned_count} discarded results")
            self.stats.discarded_count += cleaned_count
        
        return cleaned_count
    
    def mark_results_discarded(self, discarded_image_indices: List[int]) -> int:
        """Mark results as discarded for pattern-based cleanup."""
        marked_count = 0
        
        with self.lock:
            for key, result in self.cache.items():
                if result.image_index in discarded_image_indices:
                    result.mark_discarded()
                    marked_count += 1
        
        if marked_count > 0:
            logger.info(f"Cache: marked {marked_count} results as discarded")
        
        return marked_count
    
    def clear(self) -> None:
        """Clear all cached results."""
        with self.lock:
            self.cache.clear()
            logger.info("Cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self.lock:
            return {
                'cache_size': len(self.cache),
                'max_size': self.max_size,
                'stored_count': self.stats.stored_count,
                'hit_count': self.stats.hit_count,
                'miss_count': self.stats.miss_count,
                'hit_rate': self.stats.get_hit_rate(),
                'evicted_count': self.stats.evicted_count,
                'invalidated_count': self.stats.invalidated_count,
                'expired_count': self.stats.expired_count,
                'discarded_count': self.stats.discarded_count
            }
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """Get memory usage information."""
        with self.lock:
            total_size = 0
            result_count = 0
            
            for result in self.cache.values():
                total_size += result.estimate_size() if hasattr(result, 'estimate_size') else 0
                result_count += 1
            
            return {
                'total_size_bytes': total_size,
                'total_size_mb': total_size / (1024 * 1024),
                'result_count': result_count,
                'average_size_bytes': total_size / result_count if result_count > 0 else 0
            }
    
    def cleanup_old_results(self, max_age_seconds: int = 3600) -> int:
        """Remove old results based on age."""
        current_time = time.time()
        cleaned_count = 0
        
        with self.lock:
            keys_to_remove = []
            
            for key, result in self.cache.items():
                if (current_time - result.created_at) > max_age_seconds:
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del self.cache[key]
                cleaned_count += 1
                self.stats.expired_count += 1
        
        if cleaned_count > 0:
            logger.info(f"Cache: removed {cleaned_count} old results")
        
        return cleaned_count
    
    def get_result_by_image_index(self, image_index: int) -> Optional[AnalysisResult]:
        """Get result by image index."""
        with self.lock:
            for key, result in self.cache.items():
                if result.image_index == image_index:
                    # Move to end (most recently used)
                    self.cache.move_to_end(key)
                    result.update_access_time()
                    self.stats.hit_count += 1
                    return result
            
            self.stats.miss_count += 1
            return None
    
    def get_results_for_range(self, start_timestamp: float, end_timestamp: float) -> List[AnalysisResult]:
        """Get results for time range."""
        with self.lock:
            results = []
            for key, result in self.cache.items():
                if start_timestamp <= result.image_timestamp <= end_timestamp:
                    if not result.is_discarded:
                        results.append(result)
                        result.update_access_time()
                        self.stats.hit_count += 1
                    else:
                        self.stats.miss_count += 1
            
            return sorted(results, key=lambda r: r.image_timestamp)
    
    def resize(self, new_size: int) -> None:
        """Resize cache to new size."""
        with self.lock:
            if new_size < self.max_size:
                # Remove excess items
                while len(self.cache) > new_size:
                    self.cache.popitem(last=False)
                    self.stats.evicted_count += 1
            
            self.max_size = new_size
            logger.info(f"Cache resized to {new_size}")
    
    def get_least_recently_used(self) -> Optional[AnalysisResult]:
        """Get least recently used result without removing it."""
        with self.lock:
            if not self.cache:
                return None
            
            # Get first item (least recently used)
            key, result = next(iter(self.cache.items()))
            return result
    
    def get_most_recently_used(self) -> Optional[AnalysisResult]:
        """Get most recently used result without removing it."""
        with self.lock:
            if not self.cache:
                return None
            
            # Get last item (most recently used)
            key, result = next(reversed(self.cache.items()))
            return result
