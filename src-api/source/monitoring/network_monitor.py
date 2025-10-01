"""
Network connectivity monitoring and error recovery system.
"""

import asyncio
import logging
import time
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import aiohttp
from network_config import network_config

logger = logging.getLogger(__name__)

class NetworkStatus(Enum):
    """Network connectivity status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    UNKNOWN = "unknown"

@dataclass
class NetworkMetrics:
    """Network performance metrics."""
    timestamp: float
    response_time: Optional[float] = None
    success_rate: float = 0.0
    error_count: int = 0
    total_requests: int = 0
    status: NetworkStatus = NetworkStatus.UNKNOWN
    last_error: Optional[str] = None

@dataclass
class MonitoringTarget:
    """Network monitoring target configuration."""
    name: str
    url: str
    interval: int = 30  # seconds
    timeout: int = 5    # seconds
    retry_count: int = 3
    enabled: bool = True
    metrics: List[NetworkMetrics] = field(default_factory=list)

class NetworkMonitor:
    """Network connectivity monitoring system."""
    
    def __init__(self, max_metrics_history: int = 100):
        self.targets: Dict[str, MonitoringTarget] = {}
        self.max_metrics_history = max_metrics_history
        self.monitoring_tasks: Dict[str, asyncio.Task] = {}
        self.is_running = False
        self.callbacks: List[Callable[[str, NetworkMetrics], None]] = []
        
    def add_target(self, target: MonitoringTarget):
        """Add a monitoring target."""
        self.targets[target.name] = target
        logger.info(f"Added monitoring target: {target.name} -> {target.url}")
        
        # Start monitoring if system is running
        if self.is_running:
            self._start_target_monitoring(target.name)
    
    def remove_target(self, name: str):
        """Remove a monitoring target."""
        if name in self.targets:
            # Stop monitoring task
            if name in self.monitoring_tasks:
                self.monitoring_tasks[name].cancel()
                del self.monitoring_tasks[name]
            
            del self.targets[name]
            logger.info(f"Removed monitoring target: {name}")
    
    def add_callback(self, callback: Callable[[str, NetworkMetrics], None]):
        """Add a callback for monitoring events."""
        self.callbacks.append(callback)
    
    async def start_monitoring(self):
        """Start network monitoring for all targets."""
        if self.is_running:
            logger.warning("Network monitoring is already running")
            return
        
        self.is_running = True
        logger.info("Starting network monitoring system")
        
        # Start monitoring tasks for all enabled targets
        for name in self.targets:
            if self.targets[name].enabled:
                self._start_target_monitoring(name)
        
        # Add default monitoring targets if none exist
        if not self.targets:
            self._add_default_targets()
    
    async def stop_monitoring(self):
        """Stop network monitoring."""
        if not self.is_running:
            return
        
        self.is_running = False
        logger.info("Stopping network monitoring system")
        
        # Cancel all monitoring tasks
        for task in self.monitoring_tasks.values():
            task.cancel()
        
        # Wait for tasks to complete
        if self.monitoring_tasks:
            await asyncio.gather(*self.monitoring_tasks.values(), return_exceptions=True)
        
        self.monitoring_tasks.clear()
    
    def _start_target_monitoring(self, name: str):
        """Start monitoring for a specific target."""
        if name not in self.targets:
            return
        
        target = self.targets[name]
        task = asyncio.create_task(self._monitor_target(target))
        self.monitoring_tasks[name] = task
        logger.info(f"Started monitoring for target: {name}")
    
    async def _monitor_target(self, target: MonitoringTarget):
        """Monitor a specific target continuously."""
        logger.info(f"Monitoring target {target.name} every {target.interval} seconds")
        
        while self.is_running and target.enabled:
            try:
                metrics = await self._check_target(target)
                self._record_metrics(target, metrics)
                
                # Notify callbacks
                for callback in self.callbacks:
                    try:
                        callback(target.name, metrics)
                    except Exception as e:
                        logger.error(f"Error in monitoring callback: {e}")
                
                # Wait for next check
                await asyncio.sleep(target.interval)
                
            except asyncio.CancelledError:
                logger.info(f"Monitoring cancelled for target: {target.name}")
                break
            except Exception as e:
                logger.error(f"Error monitoring target {target.name}: {e}")
                await asyncio.sleep(target.interval)
    
    async def _check_target(self, target: MonitoringTarget) -> NetworkMetrics:
        """Check connectivity to a specific target."""
        start_time = time.time()
        metrics = NetworkMetrics(timestamp=start_time)
        
        for attempt in range(target.retry_count):
            try:
                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=target.timeout)
                ) as session:
                    async with session.get(target.url) as response:
                        end_time = time.time()
                        response_time = (end_time - start_time) * 1000  # Convert to ms
                        
                        metrics.response_time = response_time
                        metrics.total_requests = 1
                        
                        if response.status == 200:
                            metrics.success_rate = 1.0
                            metrics.status = NetworkStatus.HEALTHY
                            return metrics
                        else:
                            metrics.last_error = f"HTTP {response.status}"
                            
            except asyncio.TimeoutError:
                metrics.last_error = "Timeout"
            except aiohttp.ClientError as e:
                metrics.last_error = f"Client error: {str(e)}"
            except Exception as e:
                metrics.last_error = f"Unexpected error: {str(e)}"
            
            # Wait before retry (except on last attempt)
            if attempt < target.retry_count - 1:
                await asyncio.sleep(1)
        
        # All attempts failed
        metrics.error_count = 1
        metrics.total_requests = 1
        metrics.success_rate = 0.0
        metrics.status = NetworkStatus.FAILED
        
        return metrics
    
    def _record_metrics(self, target: MonitoringTarget, metrics: NetworkMetrics):
        """Record metrics for a target."""
        target.metrics.append(metrics)
        
        # Limit metrics history
        if len(target.metrics) > self.max_metrics_history:
            target.metrics = target.metrics[-self.max_metrics_history:]
        
        # Log significant events
        if metrics.status == NetworkStatus.FAILED:
            logger.warning(f"Target {target.name} failed: {metrics.last_error}")
        elif metrics.status == NetworkStatus.HEALTHY and metrics.response_time:
            logger.debug(f"Target {target.name} healthy: {metrics.response_time:.1f}ms")
    
    def _add_default_targets(self):
        """Add default monitoring targets."""
        # Monitor local health endpoint
        host_ip = network_config.get_host_ip()
        
        default_targets = [
            MonitoringTarget(
                name="local_health",
                url=f"http://127.0.0.1:8000/health",
                interval=30
            ),
            MonitoringTarget(
                name="network_health",
                url=f"http://{host_ip}:8000/health",
                interval=60
            ),
            MonitoringTarget(
                name="external_connectivity",
                url="http://8.8.8.8:53",  # Google DNS
                interval=120,
                timeout=10
            )
        ]
        
        for target in default_targets:
            self.add_target(target)
    
    def get_status_summary(self) -> Dict[str, Any]:
        """Get overall network status summary."""
        summary = {
            "overall_status": NetworkStatus.UNKNOWN,
            "targets": {},
            "timestamp": time.time()
        }
        
        if not self.targets:
            return summary
        
        healthy_count = 0
        failed_count = 0
        
        for name, target in self.targets.items():
            if not target.metrics:
                target_status = NetworkStatus.UNKNOWN
                latest_metrics = None
            else:
                latest_metrics = target.metrics[-1]
                target_status = latest_metrics.status
            
            summary["targets"][name] = {
                "status": target_status.value,
                "url": target.url,
                "last_check": latest_metrics.timestamp if latest_metrics else None,
                "response_time": latest_metrics.response_time if latest_metrics else None,
                "last_error": latest_metrics.last_error if latest_metrics else None
            }
            
            if target_status == NetworkStatus.HEALTHY:
                healthy_count += 1
            elif target_status == NetworkStatus.FAILED:
                failed_count += 1
        
        # Determine overall status
        total_targets = len(self.targets)
        if healthy_count == total_targets:
            summary["overall_status"] = NetworkStatus.HEALTHY
        elif failed_count == total_targets:
            summary["overall_status"] = NetworkStatus.FAILED
        else:
            summary["overall_status"] = NetworkStatus.DEGRADED
        
        return summary
    
    def get_target_metrics(self, name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent metrics for a specific target."""
        if name not in self.targets:
            return []
        
        target = self.targets[name]
        recent_metrics = target.metrics[-limit:] if target.metrics else []
        
        return [
            {
                "timestamp": m.timestamp,
                "response_time": m.response_time,
                "success_rate": m.success_rate,
                "status": m.status.value,
                "error": m.last_error
            }
            for m in recent_metrics
        ]

# Global network monitor instance
network_monitor = NetworkMonitor()
