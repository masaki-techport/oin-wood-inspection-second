"""
Performance Monitor for parallel image processing.

This module provides comprehensive performance monitoring and metrics collection
for parallel processing components, including timing measurements, thread
utilization tracking, and performance comparison reports.
"""

import time
import threading
import psutil
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque

logger = logging.getLogger('BaslerCamera.PerformanceMonitor')

@dataclass
class ProcessingStageMetrics:
    """Metrics for a specific processing stage."""
    stage_name: str
    total_time: float = 0.0
    count: int = 0
    min_time: float = float('inf')
    max_time: float = 0.0
    times: deque = field(default_factory=lambda: deque(maxlen=1000))
    
    def add_measurement(self, duration: float):
        """Add a timing measurement."""
        self.total_time += duration
        self.count += 1
        self.min_time = min(self.min_time, duration)
        self.max_time = max(self.max_time, duration)
        self.times.append(duration)
    
    @property
    def average_time(self) -> float:
        """Get average processing time."""
        return self.total_time / self.count if self.count > 0 else 0.0
    
    @property
    def recent_average(self) -> float:
        """Get average of recent measurements (last 100)."""
        recent = list(self.times)[-100:]
        return sum(recent) / len(recent) if recent else 0.0

@dataclass
class ThreadUtilizationMetrics:
    """Metrics for thread utilization."""
    thread_pool_name: str
    max_threads: int
    active_threads: int = 0
    peak_active_threads: int = 0
    total_tasks_submitted: int = 0
    total_tasks_completed: int = 0
    idle_time: float = 0.0
    busy_time: float = 0.0
    
    @property
    def utilization_percentage(self) -> float:
        """Get thread utilization percentage."""
        total_time = self.idle_time + self.busy_time
        return (self.busy_time / total_time * 100) if total_time > 0 else 0.0
    
    @property
    def peak_utilization_percentage(self) -> float:
        """Get peak utilization percentage."""
        return (self.peak_active_threads / self.max_threads * 100) if self.max_threads > 0 else 0.0

class PerformanceMonitor:
    """
    Comprehensive performance monitoring for parallel processing.
    
    Tracks:
    - Processing stage timings (save, analyze, presentation)
    - Thread utilization and resource usage
    - Memory usage and system load
    - Performance comparisons between sequential and parallel processing
    """
    
    def __init__(self):
        """Initialize the performance monitor."""
        self._lock = threading.Lock()
        self.start_time = time.time()
        
        # Stage metrics
        self.stage_metrics: Dict[str, ProcessingStageMetrics] = {}
        
        # Thread utilization metrics
        self.thread_metrics: Dict[str, ThreadUtilizationMetrics] = {}
        
        # System resource metrics
        self.system_metrics = {
            'cpu_usage': deque(maxlen=1000),
            'memory_usage': deque(maxlen=1000),
            'disk_io': deque(maxlen=1000),
            'network_io': deque(maxlen=1000)
        }
        
        # Processing session metrics
        self.session_metrics = {
            'sequential_sessions': [],
            'parallel_sessions': [],
            'current_session': None
        }
        
        # Performance comparison data
        self.comparison_data = {
            'sequential_avg_time': 0.0,
            'parallel_avg_time': 0.0,
            'efficiency_ratio': 0.0,
            'throughput_improvement': 0.0
        }
        
        # Start system monitoring
        self._start_system_monitoring()
    
    def start_processing_session(self, session_type: str, image_count: int, 
                                processing_groups: int = 1) -> str:
        """
        Start a new processing session for monitoring.
        
        Args:
            session_type: 'sequential' or 'parallel'
            image_count: Number of images to process
            processing_groups: Number of processing groups (for parallel)
            
        Returns:
            str: Session ID
        """
        session_id = f"{session_type}_{int(time.time())}"
        
        with self._lock:
            self.session_metrics['current_session'] = {
                'session_id': session_id,
                'session_type': session_type,
                'start_time': time.time(),
                'image_count': image_count,
                'processing_groups': processing_groups,
                'completed_images': 0,
                'stage_timings': defaultdict(list),
                'thread_usage': defaultdict(list),
                'system_snapshots': []
            }
        
        logger.info(f"Started {session_type} processing session: {session_id}")
        return session_id
    
    def end_processing_session(self, session_id: str) -> Dict[str, Any]:
        """
        End a processing session and calculate final metrics.
        
        Args:
            session_id: Session ID to end
            
        Returns:
            Dict[str, Any]: Session performance summary
        """
        with self._lock:
            current = self.session_metrics['current_session']
            if not current or current['session_id'] != session_id:
                logger.warning(f"Session {session_id} not found or not current")
                return {}
            
            # Calculate session metrics
            end_time = time.time()
            total_time = end_time - current['start_time']
            
            session_summary = {
                'session_id': session_id,
                'session_type': current['session_type'],
                'total_time': total_time,
                'image_count': current['image_count'],
                'completed_images': current['completed_images'],
                'processing_groups': current['processing_groups'],
                'images_per_second': current['completed_images'] / total_time if total_time > 0 else 0,
                'avg_time_per_image': total_time / current['completed_images'] if current['completed_images'] > 0 else 0,
                'stage_timings': dict(current['stage_timings']),
                'thread_usage_summary': self._calculate_thread_usage_summary(current['thread_usage']),
                'system_resource_summary': self._calculate_system_summary(current['system_snapshots'])
            }
            
            # Store session data
            if current['session_type'] == 'sequential':
                self.session_metrics['sequential_sessions'].append(session_summary)
            else:
                self.session_metrics['parallel_sessions'].append(session_summary)
            
            # Update comparison data
            self._update_comparison_data()
            
            # Clear current session
            self.session_metrics['current_session'] = None
            
        logger.info(f"Ended processing session: {session_id} ({total_time:.3f}s, {session_summary['images_per_second']:.2f} img/s)")
        return session_summary
    
    def record_stage_timing(self, stage_name: str, duration: float, 
                          image_path: str = None, group_name: str = None):
        """
        Record timing for a processing stage.
        
        Args:
            stage_name: Name of the processing stage (save, analyze, presentation)
            duration: Duration in seconds
            image_path: Optional image path for detailed tracking
            group_name: Optional group name for parallel processing
        """
        with self._lock:
            # Update global stage metrics
            if stage_name not in self.stage_metrics:
                self.stage_metrics[stage_name] = ProcessingStageMetrics(stage_name)
            
            self.stage_metrics[stage_name].add_measurement(duration)
            
            # Update current session metrics
            if self.session_metrics['current_session']:
                session = self.session_metrics['current_session']
                session['stage_timings'][stage_name].append({
                    'duration': duration,
                    'timestamp': time.time(),
                    'image_path': image_path,
                    'group_name': group_name
                })
        
        logger.debug(f"Recorded {stage_name} timing: {duration:.3f}s (group: {group_name})")
    
    def record_thread_utilization(self, thread_pool_name: str, active_threads: int, 
                                max_threads: int, task_submitted: bool = False, 
                                task_completed: bool = False):
        """
        Record thread utilization metrics.
        
        Args:
            thread_pool_name: Name of the thread pool
            active_threads: Current number of active threads
            max_threads: Maximum number of threads in pool
            task_submitted: Whether a task was just submitted
            task_completed: Whether a task was just completed
        """
        with self._lock:
            if thread_pool_name not in self.thread_metrics:
                self.thread_metrics[thread_pool_name] = ThreadUtilizationMetrics(
                    thread_pool_name, max_threads
                )
            
            metrics = self.thread_metrics[thread_pool_name]
            metrics.active_threads = active_threads
            metrics.peak_active_threads = max(metrics.peak_active_threads, active_threads)
            
            if task_submitted:
                metrics.total_tasks_submitted += 1
            if task_completed:
                metrics.total_tasks_completed += 1
            
            # Update current session
            if self.session_metrics['current_session']:
                session = self.session_metrics['current_session']
                session['thread_usage'][thread_pool_name].append({
                    'timestamp': time.time(),
                    'active_threads': active_threads,
                    'utilization': (active_threads / max_threads * 100) if max_threads > 0 else 0
                })
    
    def record_image_completion(self, image_path: str, group_name: str = None):
        """
        Record completion of an image processing.
        
        Args:
            image_path: Path of the completed image
            group_name: Processing group name
        """
        with self._lock:
            if self.session_metrics['current_session']:
                self.session_metrics['current_session']['completed_images'] += 1
    
    def _start_system_monitoring(self):
        """Start background system resource monitoring."""
        def monitor_system():
            while True:
                try:
                    # Collect system metrics
                    cpu_percent = psutil.cpu_percent(interval=1)
                    memory = psutil.virtual_memory()
                    disk_io = psutil.disk_io_counters()
                    network_io = psutil.net_io_counters()
                    
                    timestamp = time.time()
                    
                    with self._lock:
                        self.system_metrics['cpu_usage'].append((timestamp, cpu_percent))
                        self.system_metrics['memory_usage'].append((timestamp, memory.percent))
                        
                        if disk_io:
                            self.system_metrics['disk_io'].append((timestamp, disk_io.read_bytes + disk_io.write_bytes))
                        
                        if network_io:
                            self.system_metrics['network_io'].append((timestamp, network_io.bytes_sent + network_io.bytes_recv))
                        
                        # Add to current session
                        if self.session_metrics['current_session']:
                            self.session_metrics['current_session']['system_snapshots'].append({
                                'timestamp': timestamp,
                                'cpu_percent': cpu_percent,
                                'memory_percent': memory.percent,
                                'memory_used_gb': memory.used / (1024**3),
                                'disk_io_bytes': disk_io.read_bytes + disk_io.write_bytes if disk_io else 0,
                                'network_io_bytes': network_io.bytes_sent + network_io.bytes_recv if network_io else 0
                            })
                
                except Exception as e:
                    logger.warning(f"System monitoring error: {e}")
                
                time.sleep(5)  # Monitor every 5 seconds
        
        monitor_thread = threading.Thread(target=monitor_system, daemon=True)
        monitor_thread.start()
        logger.info("Started system resource monitoring")
    
    def _calculate_thread_usage_summary(self, thread_usage: Dict) -> Dict[str, Any]:
        """Calculate thread usage summary for a session."""
        summary = {}
        for pool_name, usage_data in thread_usage.items():
            if usage_data:
                utilizations = [data['utilization'] for data in usage_data]
                summary[pool_name] = {
                    'avg_utilization': sum(utilizations) / len(utilizations),
                    'max_utilization': max(utilizations),
                    'min_utilization': min(utilizations),
                    'samples': len(utilizations)
                }
        return summary
    
    def _calculate_system_summary(self, snapshots: List[Dict]) -> Dict[str, Any]:
        """Calculate system resource summary for a session."""
        if not snapshots:
            return {}
        
        cpu_values = [s['cpu_percent'] for s in snapshots]
        memory_values = [s['memory_percent'] for s in snapshots]
        
        return {
            'avg_cpu_percent': sum(cpu_values) / len(cpu_values),
            'max_cpu_percent': max(cpu_values),
            'avg_memory_percent': sum(memory_values) / len(memory_values),
            'max_memory_percent': max(memory_values),
            'peak_memory_gb': max(s['memory_used_gb'] for s in snapshots),
            'samples': len(snapshots)
        }
    
    def _update_comparison_data(self):
        """Update performance comparison data."""
        seq_sessions = self.session_metrics['sequential_sessions']
        par_sessions = self.session_metrics['parallel_sessions']
        
        if seq_sessions:
            self.comparison_data['sequential_avg_time'] = sum(s['avg_time_per_image'] for s in seq_sessions) / len(seq_sessions)
        
        if par_sessions:
            self.comparison_data['parallel_avg_time'] = sum(s['avg_time_per_image'] for s in par_sessions) / len(par_sessions)
        
        # Calculate efficiency ratio
        if self.comparison_data['sequential_avg_time'] > 0 and self.comparison_data['parallel_avg_time'] > 0:
            self.comparison_data['efficiency_ratio'] = self.comparison_data['sequential_avg_time'] / self.comparison_data['parallel_avg_time']
            self.comparison_data['throughput_improvement'] = (self.comparison_data['efficiency_ratio'] - 1) * 100
    
    def generate_performance_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive performance report.
        
        Returns:
            Dict[str, Any]: Performance report with all metrics
        """
        with self._lock:
            report = {
                'report_timestamp': datetime.now().isoformat(),
                'monitoring_duration': time.time() - self.start_time,
                'stage_metrics': {
                    name: {
                        'total_time': metrics.total_time,
                        'count': metrics.count,
                        'average_time': metrics.average_time,
                        'recent_average': metrics.recent_average,
                        'min_time': metrics.min_time if metrics.min_time != float('inf') else 0,
                        'max_time': metrics.max_time
                    }
                    for name, metrics in self.stage_metrics.items()
                },
                'thread_metrics': {
                    name: {
                        'max_threads': metrics.max_threads,
                        'peak_active_threads': metrics.peak_active_threads,
                        'total_tasks_submitted': metrics.total_tasks_submitted,
                        'total_tasks_completed': metrics.total_tasks_completed,
                        'peak_utilization_percentage': metrics.peak_utilization_percentage
                    }
                    for name, metrics in self.thread_metrics.items()
                },
                'session_summary': {
                    'sequential_sessions': len(self.session_metrics['sequential_sessions']),
                    'parallel_sessions': len(self.session_metrics['parallel_sessions']),
                    'recent_sequential': self.session_metrics['sequential_sessions'][-5:],
                    'recent_parallel': self.session_metrics['parallel_sessions'][-5:]
                },
                'performance_comparison': self.comparison_data.copy(),
                'system_resource_summary': self._get_recent_system_summary()
            }
        
        return report
    
    def _get_recent_system_summary(self) -> Dict[str, Any]:
        """Get summary of recent system resource usage."""
        recent_cpu = list(self.system_metrics['cpu_usage'])[-100:]
        recent_memory = list(self.system_metrics['memory_usage'])[-100:]
        
        if not recent_cpu or not recent_memory:
            return {}
        
        cpu_values = [value for _, value in recent_cpu]
        memory_values = [value for _, value in recent_memory]
        
        return {
            'avg_cpu_percent': sum(cpu_values) / len(cpu_values),
            'max_cpu_percent': max(cpu_values),
            'avg_memory_percent': sum(memory_values) / len(memory_values),
            'max_memory_percent': max(memory_values),
            'sample_period_minutes': (recent_cpu[-1][0] - recent_cpu[0][0]) / 60 if len(recent_cpu) > 1 else 0
        }
