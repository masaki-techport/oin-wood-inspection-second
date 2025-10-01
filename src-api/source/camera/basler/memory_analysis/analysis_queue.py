"""
Memory analysis queue system with priority-based processing.
"""

import queue
import threading
import time
import uuid
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from collections import deque
import numpy as np

logger = logging.getLogger('MemoryAnalysisQueue')

@dataclass
class AnalysisTask:
    """Represents a single image analysis task."""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    image_data: np.ndarray = None
    image_timestamp: float = 0.0
    image_index: int = 0
    priority: int = 0
    retry_count: int = 0
    max_retries: int = 3
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    status: str = "pending"  # pending, processing, completed, failed, retrying
    result: Optional['AnalysisResult'] = None
    error: Optional[str] = None
    processing_time: float = 0.0
    image_hash: Optional[str] = None
    
    def __post_init__(self):
        if self.image_data is not None:
            self.image_hash = self._calculate_image_hash()
    
    def _calculate_image_hash(self) -> str:
        """Calculate hash for image data."""
        import hashlib
        return hashlib.md5(self.image_data.tobytes()).hexdigest()
    
    def start_processing(self) -> None:
        """Mark task as started processing."""
        self.status = "processing"
        self.started_at = time.time()
    
    def complete_processing(self, result: 'AnalysisResult') -> None:
        """Mark task as completed with result."""
        self.status = "completed"
        self.completed_at = time.time()
        self.result = result
        if self.started_at:
            self.processing_time = self.completed_at - self.started_at
    
    def fail_processing(self, error: str) -> None:
        """Mark task as failed with error."""
        self.status = "failed"
        self.completed_at = time.time()
        self.error = error
        if self.started_at:
            self.processing_time = self.completed_at - self.started_at
    
    def can_retry(self) -> bool:
        """Check if task can be retried."""
        return self.retry_count < self.max_retries and self.status == "failed"
    
    def retry(self) -> None:
        """Mark task for retry."""
        if self.can_retry():
            self.retry_count += 1
            self.status = "retrying"
            self.started_at = None
            self.completed_at = None
            self.error = None

@dataclass
class AnalysisResult:
    """Represents the result of image analysis."""
    task_id: str
    image_timestamp: float
    image_index: int
    image_hash: str
    image_path: str = ""  # Path to the analyzed image
    detections: List[Dict[str, Any]] = field(default_factory=list)
    confidence_above_threshold: bool = False
    max_length: float = 0.0
    inspection_result: str = "無欠点"
    ai_threshold: int = 50
    processing_time: float = 0.0
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    is_discarded: bool = False  # Flag for pattern-based cleanup
    
    def mark_discarded(self) -> None:
        """Mark result as discarded for pattern-based cleanup."""
        self.is_discarded = True
    
    def update_access_time(self) -> None:
        """Update last accessed time."""
        self.last_accessed = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'task_id': self.task_id,
            'image_timestamp': self.image_timestamp,
            'image_index': self.image_index,
            'image_hash': self.image_hash,
            'detections': self.detections,
            'confidence_above_threshold': self.confidence_above_threshold,
            'max_length': self.max_length,
            'inspection_result': self.inspection_result,
            'ai_threshold': self.ai_threshold,
            'processing_time': self.processing_time,
            'created_at': self.created_at,
            'last_accessed': self.last_accessed,
            'is_discarded': self.is_discarded
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AnalysisResult':
        """Create from dictionary."""
        return cls(**data)

class QueueStatistics:
    """Statistics tracking for analysis queue."""
    
    def __init__(self):
        self.total_tasks_processed = 0
        self.successful_tasks = 0
        self.failed_tasks = 0
        self.average_processing_time = 0.0
        self.processing_times = deque(maxlen=1000)  # Keep last 1000 times
        self.queue_size = 0
        self.processing_count = 0
        self.memory_usage_mb = 0.0
        self.last_cleanup = 0.0
    
    def update_average_processing_time(self, processing_time: float) -> None:
        """Update average processing time."""
        self.processing_times.append(processing_time)
        if self.processing_times:
            self.average_processing_time = sum(self.processing_times) / len(self.processing_times)
    
    def get_success_rate(self) -> float:
        """Get success rate percentage."""
        if self.total_tasks_processed == 0:
            return 0.0
        return (self.successful_tasks / self.total_tasks_processed) * 100.0
    
    def update_memory_usage(self, usage_mb: float) -> None:
        """Update memory usage."""
        self.memory_usage_mb = usage_mb

class MemoryAnalysisQueue:
    """Thread-safe priority queue for analysis tasks."""
    
    def __init__(self, max_size: int = 100, priority_mode: bool = True):
        self.max_size = max_size
        self.priority_mode = priority_mode
        self.queue = queue.PriorityQueue(maxsize=max_size)
        self.task_registry = {}  # task_id -> AnalysisTask
        self.completed_tasks = {}  # task_id -> AnalysisResult
        self.failed_tasks = {}  # task_id -> AnalysisTask
        self.processing_tasks = {}  # task_id -> AnalysisTask
        self.lock = threading.RLock()
        self.stats = QueueStatistics()
        self.cleanup_interval = 60  # seconds
        self.last_cleanup = time.time()
    
    def reset(self) -> None:
        """Clear all queued, processing, completed, and failed tasks.
        Safe to call at start of a new inspection to avoid stale temp results.
        """
        with self.lock:
            try:
                # Drain queue non-blockingly
                while not self.queue.empty():
                    try:
                        if self.priority_mode:
                            self.queue.get_nowait()
                        else:
                            self.queue.get_nowait()
                    except queue.Empty:
                        break
                self.task_registry.clear()
                self.completed_tasks.clear()
                self.failed_tasks.clear()
                self.processing_tasks.clear()
                self.stats.queue_size = 0
                self.stats.processing_count = 0
                self.last_cleanup = time.time()
                logger.info("MemoryAnalysisQueue reset for new inspection session")
            except Exception as e:
                logger.warning(f"Failed to reset MemoryAnalysisQueue: {e}")

    def enqueue_task(self, image_data: np.ndarray, image_timestamp: float, 
                    image_index: int, priority: int = 0) -> str:
        """Add new analysis task to queue."""
        with self.lock:
            # Check if queue is full
            if self.queue.full():
                self._handle_queue_overflow()
            
            # Create task
            task = AnalysisTask(
                image_data=image_data,
                image_timestamp=image_timestamp,
                image_index=image_index,
                priority=priority
            )
            
            # Add to queue
            if self.priority_mode:
                # Use negative priority for max-heap behavior
                self.queue.put((-priority, task.created_at, task.task_id, task))
            else:
                self.queue.put((task.created_at, task.task_id, task))
            
            # Register task
            self.task_registry[task.task_id] = task
            self.stats.total_tasks_processed += 1
            
            logger.debug(f"Enqueued task {task.task_id} for image {image_index}")
            return task.task_id
    
    def dequeue_task(self) -> Optional[AnalysisTask]:
        """Get next task for processing."""
        try:
            with self.lock:
                if self.priority_mode:
                    _, _, task_id, task = self.queue.get_nowait()
                else:
                    _, task_id, task = self.queue.get_nowait()
                
                # Move to processing
                task.start_processing()
                self.processing_tasks[task_id] = task
                
                logger.debug(f"Dequeued task {task_id} for processing")
                return task
                
        except queue.Empty:
            return None
    
    def complete_task(self, task_id: str, result: AnalysisResult) -> None:
        """Mark task as completed with results."""
        with self.lock:
            if task_id in self.processing_tasks:
                task = self.processing_tasks.pop(task_id)
                task.complete_processing(result)
                self.completed_tasks[task_id] = result
                self.stats.successful_tasks += 1
                
                # Update average processing time
                if task.processing_time > 0:
                    self.stats.update_average_processing_time(task.processing_time)
                
                logger.debug(f"Completed task {task_id} in {task.processing_time:.3f}s")
            else:
                logger.warning(f"Task {task_id} not found in processing tasks")
    
    def fail_task(self, task_id: str, error: str) -> None:
        """Mark task as failed with error."""
        with self.lock:
            if task_id in self.processing_tasks:
                task = self.processing_tasks.pop(task_id)
                task.fail_processing(error)
                self.failed_tasks[task_id] = task
                self.stats.failed_tasks += 1
                
                logger.warning(f"Failed task {task_id}: {error}")
            else:
                logger.warning(f"Task {task_id} not found in processing tasks")
    
    def retry_task(self, task_id: str) -> bool:
        """Retry a failed task."""
        with self.lock:
            if task_id in self.failed_tasks:
                task = self.failed_tasks.pop(task_id)
                if task.can_retry():
                    task.retry()
                    # Re-queue task
                    if self.priority_mode:
                        self.queue.put((-task.priority, task.created_at, task.task_id, task))
                    else:
                        self.queue.put((task.created_at, task.task_id, task))
                    
                    logger.info(f"Retrying task {task_id} (attempt {task.retry_count})")
                    return True
                else:
                    logger.warning(f"Task {task_id} exceeded max retries")
            return False
    
    def get_task_status(self, task_id: str) -> Optional[str]:
        """Get current status of a task."""
        with self.lock:
            if task_id in self.task_registry:
                return self.task_registry[task_id].status
            return None
    
    def get_completed_result(self, task_id: str) -> Optional[AnalysisResult]:
        """Get completed result for a task."""
        with self.lock:
            return self.completed_tasks.get(task_id)
    
    def get_result_by_image_index(self, image_index: int) -> Optional[AnalysisResult]:
        """Get result by image index."""
        with self.lock:
            for result in self.completed_tasks.values():
                if result.image_index == image_index:
                    return result
            return None
    
    def get_results_for_range(self, start_timestamp: float, end_timestamp: float) -> List[AnalysisResult]:
        """Get results for time range in FIFO order (oldest first)."""
        with self.lock:
            results = []
            for result in self.completed_tasks.values():
                if start_timestamp <= result.image_timestamp <= end_timestamp:
                    results.append(result)
            return sorted(results, key=lambda r: r.image_timestamp)
    
    def get_all_completed_results_fifo(self, limit: Optional[int] = None) -> List[AnalysisResult]:
        """Get all completed results in FIFO order (oldest first)."""
        with self.lock:
            results = list(self.completed_tasks.values())
            # Sort by image_timestamp for FIFO order (oldest first)
            sorted_results = sorted(results, key=lambda r: r.image_timestamp)
            
            # Apply limit if specified
            if limit is not None and limit > 0:
                return sorted_results[:limit]
            
            return sorted_results
    
    def cleanup_old_tasks(self, max_age_seconds: int = 3600) -> int:
        """Remove old completed/failed tasks."""
        current_time = time.time()
        cleaned_count = 0
        
        with self.lock:
            # Clean up completed tasks
            expired_completed = []
            for task_id, result in self.completed_tasks.items():
                if (current_time - result.created_at) > max_age_seconds:
                    expired_completed.append(task_id)
            
            for task_id in expired_completed:
                del self.completed_tasks[task_id]
                if task_id in self.task_registry:
                    del self.task_registry[task_id]
                cleaned_count += 1
            
            # Clean up failed tasks
            expired_failed = []
            for task_id, task in self.failed_tasks.items():
                if (current_time - task.created_at) > max_age_seconds:
                    expired_failed.append(task_id)
            
            for task_id in expired_failed:
                del self.failed_tasks[task_id]
                if task_id in self.task_registry:
                    del self.task_registry[task_id]
                cleaned_count += 1
            
            self.last_cleanup = current_time
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} old tasks")
            
            return cleaned_count
    
    def _handle_queue_overflow(self) -> None:
        """Handle queue overflow by removing oldest pending tasks."""
        logger.warning("Queue overflow detected, removing oldest pending tasks")
        
        # Remove oldest pending tasks
        removed_count = 0
        temp_tasks = []
        
        # Get all pending tasks
        while not self.queue.empty():
            try:
                if self.priority_mode:
                    _, _, task_id, task = self.queue.get_nowait()
                else:
                    _, task_id, task = self.queue.get_nowait()
                
                if task.status == "pending":
                    temp_tasks.append((task.created_at, task_id, task))
                else:
                    # Re-queue non-pending tasks
                    if self.priority_mode:
                        self.queue.put((-task.priority, task.created_at, task_id, task))
                    else:
                        self.queue.put((task.created_at, task_id, task))
            except queue.Empty:
                break
        
        # Sort by creation time and keep newest
        temp_tasks.sort(key=lambda x: x[0], reverse=True)
        keep_count = min(len(temp_tasks), self.max_size // 2)
        
        for i, (created_at, task_id, task) in enumerate(temp_tasks):
            if i < keep_count:
                # Re-queue task
                if self.priority_mode:
                    self.queue.put((-task.priority, task.created_at, task_id, task))
                else:
                    self.queue.put((task.created_at, task_id, task))
            else:
                # Remove task
                if task_id in self.task_registry:
                    del self.task_registry[task_id]
                removed_count += 1
        
        logger.info(f"Removed {removed_count} oldest pending tasks due to overflow")
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics and status."""
        with self.lock:
            self.stats.queue_size = self.queue.qsize()
            self.stats.processing_count = len(self.processing_tasks)
            
            return {
                'queue_size': self.stats.queue_size,
                'processing_count': self.stats.processing_count,
                'completed_count': len(self.completed_tasks),
                'failed_count': len(self.failed_tasks),
                'total_tasks': self.stats.total_tasks_processed,
                'success_rate': self.stats.get_success_rate(),
                'average_processing_time': self.stats.average_processing_time,
                'memory_usage_mb': self.stats.memory_usage_mb,
                'last_cleanup': self.last_cleanup
            }
