"""
Monitoring and metrics collection for streaming services
"""
import time
from typing import Dict, Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class StreamMetrics:
    """Metrics for a streaming service"""
    stream_id: str
    stream_type: str
    bytes_sent: int = 0
    messages_sent: int = 0
    errors: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)


class MetricsCollector:
    """Collects and manages streaming metrics"""
    
    def __init__(self):
        self.stream_metrics: Dict[str, StreamMetrics] = {}
        self.global_metrics = {
            "total_streams": 0,
            "total_bytes_sent": 0,
            "total_messages_sent": 0,
            "total_errors": 0
        }
    
    def register_stream(self, stream_id: str, stream_type: str):
        """Register a new stream for monitoring"""
        self.stream_metrics[stream_id] = StreamMetrics(
            stream_id=stream_id,
            stream_type=stream_type
        )
        self.global_metrics["total_streams"] += 1
    
    def unregister_stream(self, stream_id: str):
        """Unregister a stream from monitoring"""
        if stream_id in self.stream_metrics:
            del self.stream_metrics[stream_id]
    
    def update_stream_activity(self, stream_id: str, bytes_sent: int, messages_sent: int):
        """Update stream activity metrics"""
        if stream_id in self.stream_metrics:
            metrics = self.stream_metrics[stream_id]
            metrics.bytes_sent += bytes_sent
            metrics.messages_sent += messages_sent
            metrics.last_activity = datetime.now()
            
            # Update global metrics
            self.global_metrics["total_bytes_sent"] += bytes_sent
            self.global_metrics["total_messages_sent"] += messages_sent
    
    def increment_stream_error(self, stream_id: str):
        """Increment error count for a stream"""
        if stream_id in self.stream_metrics:
            self.stream_metrics[stream_id].errors += 1
            self.global_metrics["total_errors"] += 1
    
    def get_stream_metrics(self, stream_id: str) -> Dict[str, Any]:
        """Get metrics for a specific stream"""
        if stream_id not in self.stream_metrics:
            return {}
        
        metrics = self.stream_metrics[stream_id]
        return {
            "stream_id": metrics.stream_id,
            "stream_type": metrics.stream_type,
            "bytes_sent": metrics.bytes_sent,
            "messages_sent": metrics.messages_sent,
            "errors": metrics.errors,
            "start_time": metrics.start_time.isoformat(),
            "last_activity": metrics.last_activity.isoformat(),
            "uptime_seconds": (datetime.now() - metrics.start_time).total_seconds()
        }
    
    def get_global_metrics(self) -> Dict[str, Any]:
        """Get global streaming metrics"""
        return self.global_metrics.copy()
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all metrics"""
        return {
            "global": self.get_global_metrics(),
            "streams": {
                stream_id: self.get_stream_metrics(stream_id)
                for stream_id in self.stream_metrics
            }
        }


# Global metrics collector instance
_metrics_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance"""
    return _metrics_collector


async def start_monitoring():
    """Start monitoring services (health checks and metrics collection)"""
    try:
        from .error_handling import get_health_checker
        health_checker = get_health_checker()
        await health_checker.start_monitoring()
    except Exception as e:
        # Log error but don't fail completely
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to start health monitoring: {e}")


async def stop_monitoring():
    """Stop monitoring services"""
    try:
        from .error_handling import get_health_checker
        health_checker = get_health_checker()
        health_checker.stop_monitoring()
    except Exception as e:
        # Log error but don't fail completely
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to stop health monitoring: {e}")