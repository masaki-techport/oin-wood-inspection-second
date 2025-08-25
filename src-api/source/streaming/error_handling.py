"""
Comprehensive error handling framework for streaming services
Provides centralized error handling, retry logic, exponential backoff, and recovery mechanisms
"""

import asyncio
import logging
import time
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, Optional, Callable, List, Type, Union
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for classification"""
    NETWORK = "network"
    HARDWARE = "hardware"
    DATABASE = "database"
    FILESYSTEM = "filesystem"
    AUTHENTICATION = "authentication"
    VALIDATION = "validation"
    RESOURCE = "resource"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


@dataclass
class ErrorContext:
    """Context information for an error"""
    stream_id: Optional[str] = None
    stream_type: Optional[str] = None
    client_id: Optional[str] = None
    operation: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    additional_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ErrorRecord:
    """Record of an error occurrence"""
    error: Exception
    context: ErrorContext
    severity: ErrorSeverity
    category: ErrorCategory
    timestamp: datetime = field(default_factory=datetime.now)
    retry_count: int = 0
    resolved: bool = False


@dataclass
class RetryConfig:
    """Configuration for retry logic"""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True


class StreamErrorHandler:
    """Centralized error handling framework for all streaming services"""
    
    def __init__(self):
        self.error_history: List[ErrorRecord] = []
        self.retry_config = RetryConfig()
        self.error_callbacks: Dict[ErrorCategory, List[Callable]] = {}
        self.logger = logging.getLogger(__name__)
        
        # Circuit breaker state
        self.circuit_breakers: Dict[str, 'CircuitBreaker'] = {}
        
        # Error rate tracking
        self.error_rates: Dict[str, List[datetime]] = {}
        
    def register_error_callback(self, category: ErrorCategory, callback: Callable):
        """Register callback for specific error category"""
        if category not in self.error_callbacks:
            self.error_callbacks[category] = []
        self.error_callbacks[category].append(callback)
        
    def classify_error(self, error: Exception) -> tuple[ErrorSeverity, ErrorCategory]:
        """Classify error by severity and category"""
        error_type = type(error).__name__
        error_message = str(error).lower()
        
        # Network errors
        if isinstance(error, (ConnectionError, TimeoutError, asyncio.TimeoutError)):
            return ErrorSeverity.MEDIUM, ErrorCategory.NETWORK
            
        # Database errors
        if 'database' in error_message or 'sql' in error_message:
            return ErrorSeverity.HIGH, ErrorCategory.DATABASE
            
        # File system errors
        if isinstance(error, (FileNotFoundError, PermissionError, OSError)):
            return ErrorSeverity.MEDIUM, ErrorCategory.FILESYSTEM
            
        # Authentication errors
        if 'auth' in error_message or 'permission' in error_message:
            return ErrorSeverity.HIGH, ErrorCategory.AUTHENTICATION
            
        # Resource errors
        if isinstance(error, (MemoryError, ResourceWarning)):
            return ErrorSeverity.CRITICAL, ErrorCategory.RESOURCE
            
        # Validation errors
        if isinstance(error, (ValueError, TypeError)):
            return ErrorSeverity.LOW, ErrorCategory.VALIDATION
            
        return ErrorSeverity.MEDIUM, ErrorCategory.UNKNOWN
    
    async def handle_error(self, 
                          error: Exception, 
                          context: ErrorContext,
                          retry_callback: Optional[Callable] = None) -> bool:
        """
        Handle error with comprehensive error handling logic
        Returns True if operation should be retried
        """
        severity, category = self.classify_error(error)
        
        # Create error record
        error_record = ErrorRecord(
            error=error,
            context=context,
            severity=severity,
            category=category
        )
        
        self.error_history.append(error_record)
        
        # Log error with context
        self._log_error(error_record)
        
        # Track error rate
        self._track_error_rate(context.stream_type or "unknown")
        
        # Check circuit breaker
        if context.stream_type and self._should_circuit_break(context.stream_type):
            self.logger.warning(f"Circuit breaker open for {context.stream_type}")
            return False
            
        # Execute error callbacks
        await self._execute_error_callbacks(category, error_record)
        
        # Determine if retry should be attempted
        if self._should_retry(error_record):
            delay = self._calculate_retry_delay(error_record.retry_count)
            self.logger.info(f"Retrying after {delay}s (attempt {error_record.retry_count + 1})")
            
            await asyncio.sleep(delay)
            error_record.retry_count += 1
            
            if retry_callback:
                try:
                    await retry_callback()
                except Exception as retry_error:
                    self.logger.error(f"Retry callback failed: {retry_error}")
                    
            return True
            
        return False
    
    def _should_retry(self, error_record: ErrorRecord) -> bool:
        """Determine if error should be retried"""
        if error_record.retry_count >= self.retry_config.max_attempts:
            return False
            
        # Don't retry critical errors
        if error_record.severity == ErrorSeverity.CRITICAL:
            return False
            
        # Don't retry validation errors
        if error_record.category == ErrorCategory.VALIDATION:
            return False
            
        # Don't retry authentication errors
        if error_record.category == ErrorCategory.AUTHENTICATION:
            return False
            
        return True
    
    def _calculate_retry_delay(self, retry_count: int) -> float:
        """Calculate delay for retry with exponential backoff"""
        delay = self.retry_config.base_delay * (
            self.retry_config.exponential_base ** retry_count
        )
        
        delay = min(delay, self.retry_config.max_delay)
        
        if self.retry_config.jitter:
            import random
            delay *= (0.5 + random.random() * 0.5)  # Add 0-50% jitter
            
        return delay
    
    def _track_error_rate(self, stream_type: str):
        """Track error rate for circuit breaker logic"""
        now = datetime.now()
        
        if stream_type not in self.error_rates:
            self.error_rates[stream_type] = []
            
        self.error_rates[stream_type].append(now)
        
        # Clean old entries (keep last 5 minutes)
        cutoff = now - timedelta(minutes=5)
        self.error_rates[stream_type] = [
            ts for ts in self.error_rates[stream_type] if ts > cutoff
        ]
    
    def _should_circuit_break(self, stream_type: str) -> bool:
        """Check if circuit breaker should be triggered"""
        if stream_type not in self.error_rates:
            return False
            
        # If more than 10 errors in 5 minutes, circuit break
        return len(self.error_rates[stream_type]) > 10
    
    async def _execute_error_callbacks(self, category: ErrorCategory, error_record: ErrorRecord):
        """Execute registered callbacks for error category"""
        if category in self.error_callbacks:
            for callback in self.error_callbacks[category]:
                try:
                    await callback(error_record)
                except Exception as e:
                    self.logger.error(f"Error callback failed: {e}")
    
    def _log_error(self, error_record: ErrorRecord):
        """Log error with comprehensive context"""
        context_str = f"Stream: {error_record.context.stream_type or 'unknown'}"
        if error_record.context.stream_id:
            context_str += f" ({error_record.context.stream_id})"
        if error_record.context.operation:
            context_str += f", Operation: {error_record.context.operation}"
            
        self.logger.error(
            f"[{error_record.severity.value.upper()}] {context_str} - "
            f"{type(error_record.error).__name__}: {error_record.error}",
            extra={
                "stream_type": error_record.context.stream_type,
                "stream_id": error_record.context.stream_id,
                "error_category": error_record.category.value,
                "error_severity": error_record.severity.value,
                "retry_count": error_record.retry_count,
                **error_record.context.additional_data
            }
        )
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics"""
        now = datetime.now()
        recent_errors = [
            e for e in self.error_history 
            if (now - e.timestamp).total_seconds() < 3600  # Last hour
        ]
        
        return {
            "total_errors": len(self.error_history),
            "recent_errors": len(recent_errors),
            "error_by_category": {
                category.value: len([e for e in recent_errors if e.category == category])
                for category in ErrorCategory
            },
            "error_by_severity": {
                severity.value: len([e for e in recent_errors if e.severity == severity])
                for severity in ErrorSeverity
            },
            "circuit_breaker_status": {
                stream_type: self._should_circuit_break(stream_type)
                for stream_type in self.error_rates.keys()
            }
        }


class CircuitBreaker:
    """Enhanced circuit breaker implementation for stream error handling"""
    
    def __init__(self, 
                 failure_threshold: int = 5, 
                 recovery_timeout: int = 60,
                 success_threshold: int = 2):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold  # Successes needed to close from half-open
        
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_success_time = None
        self.state = "closed"  # closed, open, half-open
        
        # Statistics
        self.total_calls = 0
        self.total_failures = 0
        self.total_successes = 0
        self.state_changes = []
        
        self.logger = logging.getLogger(__name__)
        
    def call(self, func: Callable) -> Callable:
        """Decorator to wrap function with circuit breaker"""
        async def wrapper(*args, **kwargs):
            return await self._execute_with_circuit_breaker(func, *args, **kwargs)
        return wrapper
    
    async def _execute_with_circuit_breaker(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        self.total_calls += 1
        
        if self.state == "open":
            if self._should_attempt_reset():
                self._change_state("half-open")
            else:
                raise CircuitBreakerOpenException(f"Circuit breaker is open")
                
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt reset"""
        if self.last_failure_time is None:
            return True
            
        return (datetime.now() - self.last_failure_time).total_seconds() > self.recovery_timeout
    
    def _on_success(self):
        """Handle successful operation"""
        self.total_successes += 1
        self.last_success_time = datetime.now()
        
        if self.state == "half-open":
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self._change_state("closed")
                self.failure_count = 0
                self.success_count = 0
        elif self.state == "closed":
            # Reset failure count on success in closed state
            self.failure_count = 0
        
    def _on_failure(self):
        """Handle failed operation"""
        self.total_failures += 1
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.state == "half-open":
            # Failure in half-open state immediately opens circuit
            self._change_state("open")
            self.success_count = 0
        elif self.state == "closed" and self.failure_count >= self.failure_threshold:
            self._change_state("open")
    
    def _change_state(self, new_state: str):
        """Change circuit breaker state with logging"""
        old_state = self.state
        self.state = new_state
        
        self.state_changes.append({
            "from": old_state,
            "to": new_state,
            "timestamp": datetime.now(),
            "failure_count": self.failure_count,
            "success_count": self.success_count
        })
        
        self.logger.info(f"Circuit breaker state changed: {old_state} -> {new_state}")
    
    def force_open(self):
        """Manually force circuit breaker open"""
        self._change_state("open")
        self.logger.warning("Circuit breaker manually forced open")
    
    def force_close(self):
        """Manually force circuit breaker closed"""
        self._change_state("closed")
        self.failure_count = 0
        self.success_count = 0
        self.logger.info("Circuit breaker manually forced closed")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics"""
        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "total_calls": self.total_calls,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "failure_rate": self.total_failures / max(self.total_calls, 1),
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "last_success": self.last_success_time.isoformat() if self.last_success_time else None,
            "state_changes": [
                {
                    **change,
                    "timestamp": change["timestamp"].isoformat()
                }
                for change in self.state_changes[-10:]  # Last 10 state changes
            ]
        }


class CircuitBreakerOpenException(Exception):
    """Exception raised when circuit breaker is open"""
    pass


class AutoRestartManager:
    """Manager for automatic stream restart functionality"""
    
    def __init__(self):
        self.restart_policies: Dict[str, 'RestartPolicy'] = {}
        self.active_restarts: Dict[str, asyncio.Task] = {}
        self.logger = logging.getLogger(__name__)
        
    def register_restart_policy(self, stream_type: str, policy: 'RestartPolicy'):
        """Register restart policy for stream type"""
        self.restart_policies[stream_type] = policy
        
    async def schedule_restart(self, 
                              stream_type: str, 
                              context: ErrorContext,
                              restart_callback: Callable) -> bool:
        """Schedule automatic restart for failed stream"""
        if stream_type not in self.restart_policies:
            return False
            
        policy = self.restart_policies[stream_type]
        
        if not policy.should_restart(context):
            return False
            
        # Cancel existing restart if running
        if stream_type in self.active_restarts:
            self.active_restarts[stream_type].cancel()
            
        # Schedule new restart
        restart_task = asyncio.create_task(
            self._execute_restart(stream_type, context, restart_callback, policy)
        )
        self.active_restarts[stream_type] = restart_task
        
        return True
    
    async def _execute_restart(self, 
                              stream_type: str, 
                              context: ErrorContext,
                              restart_callback: Callable,
                              policy: 'RestartPolicy'):
        """Execute restart with policy-defined delay and retry logic"""
        try:
            delay = policy.get_restart_delay()
            self.logger.info(f"Scheduling restart for {stream_type} in {delay}s")
            
            await asyncio.sleep(delay)
            
            # Execute restart callback
            await restart_callback(context)
            
            policy.on_restart_success()
            self.logger.info(f"Successfully restarted {stream_type}")
            
        except asyncio.CancelledError:
            self.logger.info(f"Restart cancelled for {stream_type}")
        except Exception as e:
            policy.on_restart_failure()
            self.logger.error(f"Restart failed for {stream_type}: {e}")
        finally:
            # Clean up active restart
            if stream_type in self.active_restarts:
                del self.active_restarts[stream_type]
    
    def cancel_restart(self, stream_type: str):
        """Cancel pending restart for stream type"""
        if stream_type in self.active_restarts:
            self.active_restarts[stream_type].cancel()
            del self.active_restarts[stream_type]
            self.logger.info(f"Cancelled restart for {stream_type}")


@dataclass
class RestartPolicy:
    """Policy for automatic stream restart"""
    max_attempts: int = 3
    base_delay: float = 5.0
    max_delay: float = 300.0
    exponential_backoff: bool = True
    restart_on_errors: List[Type[Exception]] = None
    
    def __post_init__(self):
        if self.restart_on_errors is None:
            self.restart_on_errors = [ConnectionError, TimeoutError, OSError]
        self.attempt_count = 0
        
    def should_restart(self, context: ErrorContext) -> bool:
        """Determine if restart should be attempted"""
        if self.attempt_count >= self.max_attempts:
            return False
            
        # Check if error type is restartable
        if hasattr(context, 'error') and context.error:
            error_type = type(context.error)
            if not any(issubclass(error_type, allowed) for allowed in self.restart_on_errors):
                return False
                
        return True
    
    def get_restart_delay(self) -> float:
        """Calculate restart delay based on attempt count"""
        if self.exponential_backoff:
            delay = self.base_delay * (2 ** self.attempt_count)
        else:
            delay = self.base_delay
            
        return min(delay, self.max_delay)
    
    def on_restart_success(self):
        """Handle successful restart"""
        self.attempt_count = 0
        
    def on_restart_failure(self):
        """Handle failed restart"""
        self.attempt_count += 1


class StreamRecoveryManager:
    """Manager for stream recovery mechanisms with automatic restart and circuit breaker"""
    
    def __init__(self):
        self.recovery_strategies: Dict[str, Callable] = {}
        self.fallback_handlers: Dict[str, Callable] = {}
        self.restart_handlers: Dict[str, Callable] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.logger = logging.getLogger(__name__)
        
        # Auto-restart configuration
        self.auto_restart_enabled: Dict[str, bool] = {}
        self.restart_attempts: Dict[str, int] = {}
        self.max_restart_attempts = 3
        self.restart_delay = 5.0  # seconds
        
        # Critical stream tracking
        self.critical_streams: Set[str] = set()
        
    def register_recovery_strategy(self, stream_type: str, strategy: Callable):
        """Register recovery strategy for stream type"""
        self.recovery_strategies[stream_type] = strategy
        
    def register_fallback_handler(self, stream_type: str, handler: Callable):
        """Register fallback handler for stream type"""
        self.fallback_handlers[stream_type] = handler
        
    def register_restart_handler(self, stream_type: str, handler: Callable):
        """Register automatic restart handler for stream type"""
        self.restart_handlers[stream_type] = handler
        self.auto_restart_enabled[stream_type] = True
        
    def mark_as_critical(self, stream_type: str):
        """Mark stream type as critical (requires fallback on failure)"""
        self.critical_streams.add(stream_type)
        
    def get_circuit_breaker(self, stream_type: str) -> CircuitBreaker:
        """Get or create circuit breaker for stream type"""
        if stream_type not in self.circuit_breakers:
            self.circuit_breakers[stream_type] = CircuitBreaker(
                failure_threshold=5,
                recovery_timeout=60
            )
        return self.circuit_breakers[stream_type]
        
    async def attempt_recovery(self, stream_type: str, context: ErrorContext) -> bool:
        """Attempt to recover failed stream with circuit breaker protection"""
        circuit_breaker = self.get_circuit_breaker(stream_type)
        
        # Check circuit breaker state
        if circuit_breaker.state == "open":
            self.logger.warning(f"Circuit breaker open for {stream_type}, skipping recovery")
            return False
            
        if stream_type in self.recovery_strategies:
            try:
                # Wrap recovery in circuit breaker
                @circuit_breaker.call
                async def protected_recovery():
                    await self.recovery_strategies[stream_type](context)
                    
                await protected_recovery()
                self.logger.info(f"Successfully recovered {stream_type} stream")
                return True
                
            except Exception as e:
                self.logger.error(f"Recovery failed for {stream_type}: {e}")
                
                # Attempt automatic restart if enabled
                if await self._attempt_auto_restart(stream_type, context):
                    return True
                    
        return False
    
    async def _attempt_auto_restart(self, stream_type: str, context: ErrorContext) -> bool:
        """Attempt automatic stream restart"""
        if not self.auto_restart_enabled.get(stream_type, False):
            return False
            
        if stream_type not in self.restart_handlers:
            return False
            
        # Check restart attempt limit
        attempts = self.restart_attempts.get(stream_type, 0)
        if attempts >= self.max_restart_attempts:
            self.logger.error(f"Max restart attempts reached for {stream_type}")
            return False
            
        try:
            self.logger.info(f"Attempting auto-restart for {stream_type} (attempt {attempts + 1})")
            
            # Wait before restart
            await asyncio.sleep(self.restart_delay)
            
            # Execute restart handler
            await self.restart_handlers[stream_type](context)
            
            # Reset restart attempts on success
            self.restart_attempts[stream_type] = 0
            self.logger.info(f"Successfully restarted {stream_type} stream")
            return True
            
        except Exception as e:
            # Increment restart attempts
            self.restart_attempts[stream_type] = attempts + 1
            self.logger.error(f"Auto-restart failed for {stream_type}: {e}")
            return False
    
    async def execute_fallback(self, stream_type: str, context: ErrorContext):
        """Execute fallback mechanism for failed stream"""
        if stream_type in self.fallback_handlers:
            try:
                await self.fallback_handlers[stream_type](context)
                self.logger.info(f"Executed fallback for {stream_type} stream")
            except Exception as e:
                self.logger.error(f"Fallback failed for {stream_type}: {e}")
        elif stream_type in self.critical_streams:
            # For critical streams without fallback, log critical error
            self.logger.critical(f"Critical stream {stream_type} failed without fallback")
            
    async def handle_stream_failure(self, stream_type: str, context: ErrorContext):
        """Comprehensive stream failure handling"""
        self.logger.warning(f"Handling stream failure for {stream_type}")
        
        # First, try recovery
        recovery_success = await self.attempt_recovery(stream_type, context)
        
        if not recovery_success:
            # If recovery failed, execute fallback
            await self.execute_fallback(stream_type, context)
            
            # For critical streams, attempt emergency restart
            if stream_type in self.critical_streams:
                await self._emergency_restart(stream_type, context)
                
    async def _emergency_restart(self, stream_type: str, context: ErrorContext):
        """Emergency restart for critical streams"""
        self.logger.critical(f"Attempting emergency restart for critical stream {stream_type}")
        
        try:
            # Bypass normal restart limits for critical streams
            if stream_type in self.restart_handlers:
                await self.restart_handlers[stream_type](context)
                self.logger.info(f"Emergency restart successful for {stream_type}")
        except Exception as e:
            self.logger.critical(f"Emergency restart failed for {stream_type}: {e}")
            
    def reset_restart_attempts(self, stream_type: str):
        """Reset restart attempt counter for stream type"""
        if stream_type in self.restart_attempts:
            self.restart_attempts[stream_type] = 0
            
    def get_recovery_stats(self) -> Dict[str, Any]:
        """Get recovery statistics"""
        return {
            "circuit_breakers": {
                stream_type: {
                    "state": cb.state,
                    "failure_count": cb.failure_count,
                    "last_failure": cb.last_failure_time.isoformat() if cb.last_failure_time else None
                }
                for stream_type, cb in self.circuit_breakers.items()
            },
            "restart_attempts": dict(self.restart_attempts),
            "auto_restart_enabled": dict(self.auto_restart_enabled),
            "critical_streams": list(self.critical_streams),
            "registered_handlers": {
                "recovery": list(self.recovery_strategies.keys()),
                "fallback": list(self.fallback_handlers.keys()),
                "restart": list(self.restart_handlers.keys())
            }
        }


# Global instances
_error_handler = None
_recovery_manager = None
_disconnection_handler = None
_health_checker = None
_auto_restart_manager = None


def get_error_handler() -> StreamErrorHandler:
    """Get global error handler instance"""
    global _error_handler
    if _error_handler is None:
        _error_handler = StreamErrorHandler()
    return _error_handler


def get_recovery_manager() -> StreamRecoveryManager:
    """Get global recovery manager instance"""
    global _recovery_manager
    if _recovery_manager is None:
        _recovery_manager = StreamRecoveryManager()
    return _recovery_manager


def get_auto_restart_manager() -> AutoRestartManager:
    """Get global auto-restart manager instance"""
    global _auto_restart_manager
    if _auto_restart_manager is None:
        _auto_restart_manager = AutoRestartManager()
    return _auto_restart_manager


class ClientDisconnectionHandler:
    """Handler for client disconnection scenarios"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.cleanup_callbacks: Dict[str, List[Callable]] = {}
        self.resource_monitors: Dict[str, 'ResourceMonitor'] = {}
        self.graceful_shutdown_timeout = 30.0  # seconds
        
    def register_cleanup_callback(self, stream_type: str, callback: Callable):
        """Register cleanup callback for stream type"""
        if stream_type not in self.cleanup_callbacks:
            self.cleanup_callbacks[stream_type] = []
        self.cleanup_callbacks[stream_type].append(callback)
        
    def register_resource_monitor(self, stream_id: str, monitor: 'ResourceMonitor'):
        """Register resource monitor for stream"""
        self.resource_monitors[stream_id] = monitor
        
    async def handle_client_disconnect(self, 
                                     stream_id: str, 
                                     stream_type: str,
                                     context: Optional[ErrorContext] = None):
        """Handle client disconnection with proper cleanup"""
        self.logger.info(f"Handling client disconnect for stream {stream_id}")
        
        try:
            # Execute cleanup callbacks
            if stream_type in self.cleanup_callbacks:
                for callback in self.cleanup_callbacks[stream_type]:
                    try:
                        await asyncio.wait_for(
                            callback(stream_id, context), 
                            timeout=self.graceful_shutdown_timeout
                        )
                    except asyncio.TimeoutError:
                        self.logger.warning(f"Cleanup callback timeout for {stream_id}")
                    except Exception as e:
                        self.logger.error(f"Cleanup callback error for {stream_id}: {e}")
            
            # Clean up resource monitor
            if stream_id in self.resource_monitors:
                await self.resource_monitors[stream_id].cleanup()
                del self.resource_monitors[stream_id]
                
            self.logger.info(f"Successfully cleaned up disconnected stream {stream_id}")
            
        except Exception as e:
            self.logger.error(f"Error during disconnect cleanup for {stream_id}: {e}")
            
    async def detect_client_disconnections(self, active_streams: Dict[str, Any]):
        """Detect and handle client disconnections"""
        disconnected_streams = []
        
        for stream_id, stream_info in active_streams.items():
            try:
                # Check if client is still connected
                if await self._is_client_disconnected(stream_info):
                    disconnected_streams.append((stream_id, stream_info))
            except Exception as e:
                self.logger.error(f"Error checking connection for {stream_id}: {e}")
                
        # Handle disconnected clients
        for stream_id, stream_info in disconnected_streams:
            await self.handle_client_disconnect(
                stream_id, 
                stream_info.get('stream_type', 'unknown')
            )
            
    async def _is_client_disconnected(self, stream_info: Any) -> bool:
        """Check if client is disconnected"""
        # This would be implemented based on specific stream type
        # For now, return False as a placeholder
        return False
        
    async def graceful_shutdown_all(self, active_streams: Dict[str, Any]):
        """Gracefully shutdown all active streams"""
        self.logger.info("Initiating graceful shutdown of all streams")
        
        shutdown_tasks = []
        for stream_id, stream_info in active_streams.items():
            task = asyncio.create_task(
                self.handle_client_disconnect(
                    stream_id, 
                    stream_info.get('stream_type', 'unknown')
                )
            )
            shutdown_tasks.append(task)
            
        # Wait for all shutdowns with timeout
        try:
            await asyncio.wait_for(
                asyncio.gather(*shutdown_tasks, return_exceptions=True),
                timeout=self.graceful_shutdown_timeout
            )
        except asyncio.TimeoutError:
            self.logger.warning("Graceful shutdown timeout exceeded")
            
        self.logger.info("Graceful shutdown completed")


class ResourceMonitor:
    """Monitor resources for a specific stream"""
    
    def __init__(self, stream_id: str):
        self.stream_id = stream_id
        self.resources: Dict[str, Any] = {}
        self.cleanup_tasks: List[Callable] = []
        self.logger = logging.getLogger(__name__)
        
    def register_resource(self, name: str, resource: Any, cleanup_func: Optional[Callable] = None):
        """Register a resource for monitoring"""
        self.resources[name] = resource
        if cleanup_func:
            self.cleanup_tasks.append(cleanup_func)
            
    async def cleanup(self):
        """Clean up all registered resources"""
        self.logger.info(f"Cleaning up resources for stream {self.stream_id}")
        
        for cleanup_func in self.cleanup_tasks:
            try:
                if asyncio.iscoroutinefunction(cleanup_func):
                    await cleanup_func()
                else:
                    cleanup_func()
            except Exception as e:
                self.logger.error(f"Resource cleanup error: {e}")
                
        self.resources.clear()
        self.cleanup_tasks.clear()
        
    def get_resource_usage(self) -> Dict[str, Any]:
        """Get current resource usage statistics"""
        import psutil
        import sys
        
        return {
            "memory_usage": sys.getsizeof(self.resources),
            "resource_count": len(self.resources),
            "cleanup_tasks": len(self.cleanup_tasks),
            "system_memory": psutil.virtual_memory().percent if 'psutil' in sys.modules else None
        }


class ConnectionHealthChecker:
    """Check health of streaming connections"""
    
    def __init__(self, check_interval: float = 30.0):
        self.check_interval = check_interval
        self.health_checks: Dict[str, Callable] = {}
        self.unhealthy_streams: Set[str] = set()
        self.logger = logging.getLogger(__name__)
        self._running = False
        
    def register_health_check(self, stream_type: str, check_func: Callable):
        """Register health check function for stream type"""
        self.health_checks[stream_type] = check_func
        
    async def start_monitoring(self):
        """Start connection health monitoring"""
        self._running = True
        self.logger.info("Starting connection health monitoring")
        
        while self._running:
            try:
                await self._perform_health_checks()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                self.logger.error(f"Health check error: {e}")
                await asyncio.sleep(self.check_interval)
                
    def stop_monitoring(self):
        """Stop connection health monitoring"""
        self._running = False
        self.logger.info("Stopping connection health monitoring")
        
    async def _perform_health_checks(self):
        """Perform health checks on all registered streams"""
        for stream_type, check_func in self.health_checks.items():
            try:
                is_healthy = await check_func()
                if not is_healthy and stream_type not in self.unhealthy_streams:
                    self.unhealthy_streams.add(stream_type)
                    self.logger.warning(f"Stream type {stream_type} is unhealthy")
                elif is_healthy and stream_type in self.unhealthy_streams:
                    self.unhealthy_streams.remove(stream_type)
                    self.logger.info(f"Stream type {stream_type} recovered")
            except Exception as e:
                self.logger.error(f"Health check failed for {stream_type}: {e}")
                
    def is_stream_healthy(self, stream_type: str) -> bool:
        """Check if stream type is healthy"""
        return stream_type not in self.unhealthy_streams


# Global instances
_disconnection_handler = None
_health_checker = None


def get_disconnection_handler() -> ClientDisconnectionHandler:
    """Get global disconnection handler instance"""
    global _disconnection_handler
    if _disconnection_handler is None:
        _disconnection_handler = ClientDisconnectionHandler()
    return _disconnection_handler


def get_health_checker() -> ConnectionHealthChecker:
    """Get global health checker instance"""
    global _health_checker
    if _health_checker is None:
        _health_checker = ConnectionHealthChecker()
    return _health_checker


@asynccontextmanager
async def error_handling_context(stream_type: str, 
                                stream_id: Optional[str] = None,
                                operation: Optional[str] = None):
    """Context manager for error handling in streaming operations"""
    error_handler = get_error_handler()
    context = ErrorContext(
        stream_type=stream_type,
        stream_id=stream_id,
        operation=operation
    )
    
    try:
        yield context
    except Exception as e:
        await error_handler.handle_error(e, context)
        raise


@asynccontextmanager
async def stream_lifecycle_context(stream_id: str, 
                                  stream_type: str,
                                  cleanup_callback: Optional[Callable] = None):
    """Context manager for complete stream lifecycle management"""
    disconnection_handler = get_disconnection_handler()
    resource_monitor = ResourceMonitor(stream_id)
    
    # Register resource monitor
    disconnection_handler.register_resource_monitor(stream_id, resource_monitor)
    
    try:
        yield resource_monitor
    except Exception as e:
        # Handle any errors during stream lifecycle
        context = ErrorContext(
            stream_type=stream_type,
            stream_id=stream_id,
            operation="stream_lifecycle"
        )
        await get_error_handler().handle_error(e, context)
        raise
    finally:
        # Always clean up on exit
        if cleanup_callback:
            try:
                await cleanup_callback()
            except Exception as e:
                logger.error(f"Cleanup callback error: {e}")
                
        await disconnection_handler.handle_client_disconnect(stream_id, stream_type)
   