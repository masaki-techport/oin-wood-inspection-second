"""
Performance monitoring and statistics for memory analysis system.
"""

import time
import threading
import logging
import psutil
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

logger = logging.getLogger('MemoryMonitor')

@dataclass
class PerformanceMetrics:
    """Performance metrics for memory analysis system."""
    # Queue metrics
    queue_size: int = 0
    processing_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    
    # Timing metrics
    average_processing_time: float = 0.0
    total_processing_time: float = 0.0
    queue_wait_time: float = 0.0
    
    # Memory metrics
    memory_usage_mb: float = 0.0
    cache_hit_rate: float = 0.0
    cache_size: int = 0
    
    # Error metrics
    error_rate: float = 0.0
    retry_count: int = 0
    timeout_count: int = 0
    
    # Cleanup metrics
    cleanup_count: int = 0
    cleaned_count: int = 0
    
    def get_success_rate(self) -> float:
        """Get success rate percentage."""
        total = self.completed_count + self.failed_count
        if total == 0:
            return 0.0
        return (self.completed_count / total) * 100.0
    
    def get_throughput(self) -> float:
        """Get throughput (tasks per second)."""
        if self.total_processing_time > 0:
            return (self.completed_count + self.failed_count) / self.total_processing_time
        return 0.0

class MemoryMonitor:
    """Performance monitoring for memory analysis system."""
    
    def __init__(self, update_interval: float = 1.0):
        self.update_interval = update_interval
        self.metrics = PerformanceMetrics()
        self.history = deque(maxlen=1000)  # Keep last 1000 measurements
        self.lock = threading.Lock()
        self.running = False
        self.monitor_thread = None
        self.start_time = time.time()
        
        # Component references
        self.analysis_queue = None
        self.analysis_processor = None
        self.results_storage = None
        self.result_cache = None
    
    def set_components(self, analysis_queue=None, analysis_processor=None, 
                      results_storage=None, result_cache=None):
        """Set component references for monitoring."""
        self.analysis_queue = analysis_queue
        self.analysis_processor = analysis_processor
        self.results_storage = results_storage
        self.result_cache = result_cache
    
    def start_monitoring(self) -> None:
        """Start performance monitoring."""
        if self.running:
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True,
            name="MemoryMonitor"
        )
        self.monitor_thread.start()
        logger.info("Memory monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop performance monitoring."""
        self.running = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2.0)
        logger.info("Memory monitoring stopped")
    
    def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self.running:
            try:
                self._update_metrics()
                time.sleep(self.update_interval)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(1.0)
    
    def _update_metrics(self) -> None:
        """Update performance metrics."""
        with self.lock:
            # Update queue metrics
            if self.analysis_queue:
                queue_stats = self.analysis_queue.get_queue_stats()
                self.metrics.queue_size = queue_stats.get('queue_size', 0)
                self.metrics.processing_count = queue_stats.get('processing_count', 0)
                self.metrics.completed_count = queue_stats.get('completed_count', 0)
                self.metrics.failed_count = queue_stats.get('failed_count', 0)
                self.metrics.average_processing_time = queue_stats.get('average_processing_time', 0.0)
            
            # Update processor metrics
            if self.analysis_processor:
                processor_stats = self.analysis_processor.get_performance_stats()
                self.metrics.total_processing_time = processor_stats.get('total_processing_time', 0.0)
                self.metrics.retry_count = processor_stats.get('retry_count', 0)
                self.metrics.timeout_count = processor_stats.get('timeout_count', 0)
            
            # Update storage metrics
            if self.results_storage:
                storage_stats = self.results_storage.get_storage_stats()
                self.metrics.cleanup_count = storage_stats.get('cleanup_count', 0)
                self.metrics.cleaned_count = storage_stats.get('cleaned_count', 0)
            
            # Update cache metrics
            if self.result_cache:
                cache_stats = self.result_cache.get_cache_stats()
                self.metrics.cache_hit_rate = cache_stats.get('hit_rate', 0.0)
                self.metrics.cache_size = cache_stats.get('cache_size', 0)
            
            # Update memory usage
            self.metrics.memory_usage_mb = self._get_memory_usage()
            
            # Calculate error rate
            total_tasks = self.metrics.completed_count + self.metrics.failed_count
            if total_tasks > 0:
                self.metrics.error_rate = (self.metrics.failed_count / total_tasks) * 100.0
            
            # Record in history
            self.history.append({
                'timestamp': time.time(),
                'metrics': self.metrics.__dict__.copy()
            })
    
    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            return memory_info.rss / (1024 * 1024)  # Convert to MB
        except Exception as e:
            logger.warning(f"Failed to get memory usage: {e}")
            return 0.0
    
    def record_task_completion(self, processing_time: float, success: bool) -> None:
        """Record task completion metrics."""
        with self.lock:
            if success:
                self.metrics.completed_count += 1
            else:
                self.metrics.failed_count += 1
            
            # Update average processing time
            if processing_time > 0:
                total_tasks = self.metrics.completed_count + self.metrics.failed_count
                if total_tasks > 0:
                    self.metrics.average_processing_time = (
                        (self.metrics.average_processing_time * (total_tasks - 1) + processing_time) / total_tasks
                    )
    
    def record_cleanup(self, cleaned_count: int) -> None:
        """Record cleanup operation."""
        with self.lock:
            self.metrics.cleanup_count += 1
            self.metrics.cleaned_count += cleaned_count
    
    def get_current_metrics(self) -> PerformanceMetrics:
        """Get current performance metrics."""
        with self.lock:
            return PerformanceMetrics(**self.metrics.__dict__)
    
    def get_historical_metrics(self, duration_seconds: int = 300) -> List[Dict[str, Any]]:
        """Get historical metrics for specified duration."""
        cutoff_time = time.time() - duration_seconds
        
        with self.lock:
            return [entry for entry in self.history if entry['timestamp'] >= cutoff_time]
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Get comprehensive performance report."""
        with self.lock:
            uptime = time.time() - self.start_time
            
            return {
                'uptime_seconds': uptime,
                'uptime_hours': uptime / 3600,
                'current_metrics': self.metrics.__dict__.copy(),
                'success_rate': self.metrics.get_success_rate(),
                'throughput': self.metrics.get_throughput(),
                'memory_usage_mb': self.metrics.memory_usage_mb,
                'cache_hit_rate': self.metrics.cache_hit_rate,
                'error_rate': self.metrics.error_rate,
                'recent_activity': list(self.history)[-10:] if self.history else []
            }
    
    def get_memory_usage_breakdown(self) -> Dict[str, Any]:
        """Get detailed memory usage breakdown."""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            
            return {
                'rss_mb': memory_info.rss / (1024 * 1024),
                'vms_mb': memory_info.vms / (1024 * 1024),
                'percent': process.memory_percent(),
                'available_mb': psutil.virtual_memory().available / (1024 * 1024),
                'total_mb': psutil.virtual_memory().total / (1024 * 1024)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory breakdown: {e}")
            return {}
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get system health status."""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_available_mb': memory.available / (1024 * 1024),
                'disk_percent': disk.percent,
                'disk_free_gb': disk.free / (1024 * 1024 * 1024),
                'load_average': psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
            }
        except Exception as e:
            logger.warning(f"Failed to get system health: {e}")
            return {}
    
    def reset_metrics(self) -> None:
        """Reset all metrics to zero."""
        with self.lock:
            self.metrics = PerformanceMetrics()
            self.history.clear()
            self.start_time = time.time()
            logger.info("Performance metrics reset")
    
    def export_metrics(self, filepath: str) -> None:
        """Export metrics to file."""
        try:
            import json
            
            with self.lock:
                data = {
                    'export_time': time.time(),
                    'uptime_seconds': time.time() - self.start_time,
                    'current_metrics': self.metrics.__dict__.copy(),
                    'historical_data': list(self.history)
                }
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Metrics exported to {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to export metrics: {e}")
    
    def get_alerts(self) -> List[Dict[str, Any]]:
        """Get performance alerts."""
        alerts = []
        
        with self.lock:
            # Memory usage alert
            if self.metrics.memory_usage_mb > 1000:  # 1GB threshold
                alerts.append({
                    'type': 'memory_usage',
                    'level': 'warning',
                    'message': f"High memory usage: {self.metrics.memory_usage_mb:.1f}MB",
                    'timestamp': time.time()
                })
            
            # Error rate alert
            if self.metrics.error_rate > 10:  # 10% error rate threshold
                alerts.append({
                    'type': 'error_rate',
                    'level': 'warning',
                    'message': f"High error rate: {self.metrics.error_rate:.1f}%",
                    'timestamp': time.time()
                })
            
            # Queue size alert
            if self.metrics.queue_size > 80:  # 80% of max queue size
                alerts.append({
                    'type': 'queue_size',
                    'level': 'warning',
                    'message': f"High queue size: {self.metrics.queue_size}",
                    'timestamp': time.time()
                })
            
            # Cache hit rate alert
            if self.metrics.cache_hit_rate < 50:  # 50% hit rate threshold
                alerts.append({
                    'type': 'cache_hit_rate',
                    'level': 'info',
                    'message': f"Low cache hit rate: {self.metrics.cache_hit_rate:.1f}%",
                    'timestamp': time.time()
                })
        
        return alerts
