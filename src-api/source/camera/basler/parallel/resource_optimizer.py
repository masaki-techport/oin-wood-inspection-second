"""
Resource Optimizer for parallel image processing.

This module provides dynamic resource optimization including thread count
adjustment, memory usage monitoring, and intelligent queue management
to prevent system overload and optimize performance.
"""

import time
import threading
import psutil
import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from collections import deque

logger = logging.getLogger('BaslerCamera.ResourceOptimizer')

@dataclass
class SystemResourceState:
    """Current system resource state."""
    cpu_percent: float
    memory_percent: float
    memory_available_gb: float
    disk_io_rate: float
    load_average: float
    timestamp: float

@dataclass
class OptimizationConfig:
    """Configuration for resource optimization."""
    # CPU thresholds
    cpu_high_threshold: float = 85.0
    cpu_low_threshold: float = 50.0
    
    # Memory thresholds
    memory_high_threshold: float = 80.0
    memory_critical_threshold: float = 90.0
    
    # Thread management
    min_threads: int = 5
    max_threads: int = 15
    thread_adjustment_step: int = 2
    
    # Queue management
    max_queue_size: int = 100
    queue_throttle_threshold: int = 80
    
    # Monitoring intervals
    monitoring_interval: float = 5.0
    optimization_interval: float = 30.0

class ResourceOptimizer:
    """
    Dynamic resource optimizer for parallel processing.
    
    Features:
    - Dynamic thread count adjustment based on system load
    - Memory usage monitoring and throttling
    - Intelligent queue management to prevent thread starvation
    - Configuration optimization based on system capabilities
    """
    
    def __init__(self, config: OptimizationConfig = None):
        """
        Initialize the resource optimizer.
        
        Args:
            config: Optimization configuration
        """
        self.config = config or OptimizationConfig()
        self._lock = threading.Lock()
        self.enabled = True
        
        # System monitoring
        self.resource_history = deque(maxlen=100)
        self.current_state: Optional[SystemResourceState] = None
        
        # Optimization state
        self.current_thread_count = self._detect_initial_thread_count()
        self.optimization_history = deque(maxlen=50)
        self.last_optimization_time = 0
        
        # Queue management
        self.queue_sizes = {}
        self.throttled_queues = set()
        
        # Performance tracking
        self.performance_metrics = {
            'optimizations_applied': 0,
            'thread_adjustments': 0,
            'memory_throttles': 0,
            'queue_throttles': 0
        }
        
        # Start monitoring
        self._start_monitoring()
        
        logger.info(f"ResourceOptimizer initialized with {self.current_thread_count} threads")
    
    def _detect_initial_thread_count(self) -> int:
        """Detect optimal initial thread count based on system capabilities."""
        try:
            cpu_cores = psutil.cpu_count(logical=False) or psutil.cpu_count()
            memory_gb = psutil.virtual_memory().total / (1024**3)
            
            # Base calculation: 1.5x physical cores
            base_threads = int(cpu_cores * 1.5)
            
            # Adjust based on memory
            if memory_gb < 8:
                base_threads = min(base_threads, 6)
            elif memory_gb > 16:
                base_threads = min(base_threads + 2, self.config.max_threads)
            
            # Constrain to configured limits
            optimal_threads = max(self.config.min_threads, 
                                min(self.config.max_threads, base_threads))
            
            logger.info(f"Detected optimal thread count: {optimal_threads} "
                       f"(CPU cores: {cpu_cores}, Memory: {memory_gb:.1f}GB)")
            
            return optimal_threads
            
        except Exception as e:
            logger.warning(f"Error detecting optimal threads: {e}, using default")
            return 8
    
    def _start_monitoring(self):
        """Start background resource monitoring."""
        def monitor_resources():
            while self.enabled:
                try:
                    self._collect_system_metrics()
                    
                    # Check if optimization is needed
                    if (time.time() - self.last_optimization_time > 
                        self.config.optimization_interval):
                        self._optimize_resources()
                        self.last_optimization_time = time.time()
                    
                except Exception as e:
                    logger.warning(f"Resource monitoring error: {e}")
                
                time.sleep(self.config.monitoring_interval)
        
        monitor_thread = threading.Thread(target=monitor_resources, daemon=True)
        monitor_thread.start()
        logger.info("Started resource monitoring")
    
    def _collect_system_metrics(self):
        """Collect current system resource metrics."""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            
            # Get disk I/O rate (simplified)
            disk_io = psutil.disk_io_counters()
            disk_io_rate = 0
            if disk_io and hasattr(self, '_last_disk_io'):
                time_diff = time.time() - self._last_disk_time
                if time_diff > 0:
                    bytes_diff = (disk_io.read_bytes + disk_io.write_bytes) - self._last_disk_io
                    disk_io_rate = bytes_diff / time_diff / (1024 * 1024)  # MB/s
            
            if disk_io:
                self._last_disk_io = disk_io.read_bytes + disk_io.write_bytes
                self._last_disk_time = time.time()
            
            # Get load average (Unix-like systems)
            load_average = 0
            try:
                load_average = psutil.getloadavg()[0] if hasattr(psutil, 'getloadavg') else cpu_percent / 100
            except:
                load_average = cpu_percent / 100
            
            state = SystemResourceState(
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_available_gb=memory.available / (1024**3),
                disk_io_rate=disk_io_rate,
                load_average=load_average,
                timestamp=time.time()
            )
            
            with self._lock:
                self.current_state = state
                self.resource_history.append(state)
            
        except Exception as e:
            logger.warning(f"Error collecting system metrics: {e}")
    
    def _optimize_resources(self):
        """Perform resource optimization based on current system state."""
        if not self.current_state:
            return
        
        with self._lock:
            state = self.current_state
            optimizations_applied = []
            
            # Check if thread count adjustment is needed
            new_thread_count = self._calculate_optimal_thread_count(state)
            if new_thread_count != self.current_thread_count:
                old_count = self.current_thread_count
                self.current_thread_count = new_thread_count
                self.performance_metrics['thread_adjustments'] += 1
                optimizations_applied.append(f"threads: {old_count} -> {new_thread_count}")
            
            # Check memory throttling
            if state.memory_percent > self.config.memory_high_threshold:
                self._apply_memory_throttling(state)
                optimizations_applied.append("memory throttling")
            
            # Check queue management
            self._optimize_queue_management(state)
            
            # Record optimization
            if optimizations_applied:
                self.performance_metrics['optimizations_applied'] += 1
                optimization_record = {
                    'timestamp': time.time(),
                    'system_state': state,
                    'optimizations': optimizations_applied,
                    'new_thread_count': self.current_thread_count
                }
                self.optimization_history.append(optimization_record)
                
                logger.info(f"Applied optimizations: {', '.join(optimizations_applied)}")
    
    def _calculate_optimal_thread_count(self, state: SystemResourceState) -> int:
        """Calculate optimal thread count based on current system state."""
        current_threads = self.current_thread_count
        
        # High CPU usage - reduce threads
        if state.cpu_percent > self.config.cpu_high_threshold:
            new_threads = max(self.config.min_threads, 
                            current_threads - self.config.thread_adjustment_step)
            return new_threads
        
        # Low CPU usage and available memory - increase threads
        elif (state.cpu_percent < self.config.cpu_low_threshold and 
              state.memory_percent < self.config.memory_high_threshold):
            new_threads = min(self.config.max_threads, 
                            current_threads + self.config.thread_adjustment_step)
            return new_threads
        
        # Memory pressure - reduce threads
        elif state.memory_percent > self.config.memory_high_threshold:
            new_threads = max(self.config.min_threads, 
                            current_threads - self.config.thread_adjustment_step)
            return new_threads
        
        return current_threads
    
    def _apply_memory_throttling(self, state: SystemResourceState):
        """Apply memory throttling measures."""
        if state.memory_percent > self.config.memory_critical_threshold:
            # Critical memory usage - aggressive throttling
            self.performance_metrics['memory_throttles'] += 1
            logger.warning(f"Critical memory usage: {state.memory_percent:.1f}% - applying aggressive throttling")
        elif state.memory_percent > self.config.memory_high_threshold:
            # High memory usage - moderate throttling
            self.performance_metrics['memory_throttles'] += 1
            logger.info(f"High memory usage: {state.memory_percent:.1f}% - applying memory throttling")
    
    def _optimize_queue_management(self, state: SystemResourceState):
        """Optimize queue management to prevent thread starvation."""
        for queue_name, queue_size in self.queue_sizes.items():
            if queue_size > self.config.queue_throttle_threshold:
                if queue_name not in self.throttled_queues:
                    self.throttled_queues.add(queue_name)
                    self.performance_metrics['queue_throttles'] += 1
                    logger.info(f"Throttling queue {queue_name} (size: {queue_size})")
            elif queue_size < self.config.queue_throttle_threshold * 0.5:
                if queue_name in self.throttled_queues:
                    self.throttled_queues.remove(queue_name)
                    logger.info(f"Removing throttle from queue {queue_name}")
    
    def get_optimal_thread_count(self) -> int:
        """Get current optimal thread count."""
        with self._lock:
            return self.current_thread_count
    
    def should_throttle_queue(self, queue_name: str) -> bool:
        """Check if a queue should be throttled."""
        with self._lock:
            return queue_name in self.throttled_queues
    
    def update_queue_size(self, queue_name: str, size: int):
        """Update queue size for monitoring."""
        with self._lock:
            self.queue_sizes[queue_name] = size
    
    def should_throttle_memory_operations(self) -> bool:
        """Check if memory operations should be throttled."""
        if not self.current_state:
            return False
        
        return self.current_state.memory_percent > self.config.memory_high_threshold
    
    def get_memory_pressure_level(self) -> str:
        """Get current memory pressure level."""
        if not self.current_state:
            return "unknown"
        
        memory_percent = self.current_state.memory_percent
        
        if memory_percent > self.config.memory_critical_threshold:
            return "critical"
        elif memory_percent > self.config.memory_high_threshold:
            return "high"
        elif memory_percent > 60:
            return "moderate"
        else:
            return "low"
    
    def get_system_load_level(self) -> str:
        """Get current system load level."""
        if not self.current_state:
            return "unknown"
        
        cpu_percent = self.current_state.cpu_percent
        
        if cpu_percent > self.config.cpu_high_threshold:
            return "high"
        elif cpu_percent > 70:
            return "moderate"
        else:
            return "low"
    
    def get_optimization_summary(self) -> Dict[str, Any]:
        """Get optimization summary and statistics."""
        with self._lock:
            recent_history = list(self.resource_history)[-10:]
            
            summary = {
                'enabled': self.enabled,
                'current_thread_count': self.current_thread_count,
                'current_system_state': {
                    'cpu_percent': self.current_state.cpu_percent if self.current_state else 0,
                    'memory_percent': self.current_state.memory_percent if self.current_state else 0,
                    'memory_available_gb': self.current_state.memory_available_gb if self.current_state else 0,
                    'load_level': self.get_system_load_level(),
                    'memory_pressure': self.get_memory_pressure_level()
                },
                'performance_metrics': self.performance_metrics.copy(),
                'throttled_queues': list(self.throttled_queues),
                'recent_optimizations': list(self.optimization_history)[-5:],
                'config': {
                    'min_threads': self.config.min_threads,
                    'max_threads': self.config.max_threads,
                    'cpu_high_threshold': self.config.cpu_high_threshold,
                    'memory_high_threshold': self.config.memory_high_threshold
                }
            }
            
            if recent_history:
                avg_cpu = sum(s.cpu_percent for s in recent_history) / len(recent_history)
                avg_memory = sum(s.memory_percent for s in recent_history) / len(recent_history)
                summary['recent_averages'] = {
                    'cpu_percent': avg_cpu,
                    'memory_percent': avg_memory
                }
        
        return summary
    
    def update_config(self, new_config: Dict[str, Any]):
        """Update optimization configuration."""
        with self._lock:
            for key, value in new_config.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
                    logger.info(f"Updated config {key} = {value}")
    
    def enable_optimization(self):
        """Enable resource optimization."""
        self.enabled = True
        logger.info("Resource optimization enabled")
    
    def disable_optimization(self):
        """Disable resource optimization."""
        self.enabled = False
        logger.info("Resource optimization disabled")
    
    def shutdown(self):
        """Shutdown the resource optimizer."""
        self.enabled = False
        logger.info("ResourceOptimizer shutdown")
