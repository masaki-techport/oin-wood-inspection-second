"""
Base streaming service classes and utilities
"""
import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Set, Optional, AsyncGenerator, Callable
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class StreamStatus:
    """Status information for an active stream"""
    stream_id: str
    stream_type: str
    client_count: int = 0
    bytes_sent: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    is_active: bool = True
    error_count: int = 0


class BaseStreamingService(ABC):
    """Base class for all streaming services"""
    
    def __init__(self):
        from .config import get_streaming_config, register_config_change_callback
        from .error_handling import get_error_handler, get_recovery_manager
        
        self.config = get_streaming_config()
        self.active_streams: Dict[str, StreamStatus] = {}
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Error handling integration
        self._error_handler = get_error_handler()
        self._recovery_manager = get_recovery_manager()
        
        # Register for configuration changes
        register_config_change_callback(self._on_config_change)
        
        # Initialize monitoring integration
        self._metrics_collector = None
        self._init_monitoring()
        
        # Register recovery strategies
        self._register_recovery_strategies()
    
    def _init_monitoring(self):
        """Initialize monitoring integration"""
        try:
            from .monitoring import get_metrics_collector
            self._metrics_collector = get_metrics_collector()
        except ImportError:
            self.logger.warning("Monitoring system not available")
    
    def _on_config_change(self, new_config):
        """Handle configuration changes"""
        self.config = new_config
        self.logger.info(f"Configuration updated for {self.__class__.__name__}")
        # Subclasses can override this method to handle specific config changes
    
    def generate_stream_id(self) -> str:
        """Generate unique stream ID"""
        return f"{self.__class__.__name__}_{int(time.time() * 1000)}"
    
    def register_stream(self, stream_id: str, stream_type: str) -> StreamStatus:
        """Register a new active stream"""
        status = StreamStatus(
            stream_id=stream_id,
            stream_type=stream_type
        )
        self.active_streams[stream_id] = status
        self.logger.info(f"Registered stream {stream_id} of type {stream_type}")
        
        # Register with monitoring system
        if self._metrics_collector:
            self._metrics_collector.register_stream(stream_id, stream_type)
        
        return status
    
    def unregister_stream(self, stream_id: str):
        """Unregister an active stream"""
        if stream_id in self.active_streams:
            del self.active_streams[stream_id]
            self.logger.info(f"Unregistered stream {stream_id}")
            
            # Unregister from monitoring system
            if self._metrics_collector:
                self._metrics_collector.unregister_stream(stream_id)
    
    def update_stream_activity(self, stream_id: str, bytes_sent: int = 0):
        """Update stream activity metrics"""
        if stream_id in self.active_streams:
            status = self.active_streams[stream_id]
            status.last_activity = datetime.now()
            status.bytes_sent += bytes_sent
            
            # Update monitoring metrics
            if self._metrics_collector:
                self._metrics_collector.update_stream_activity(stream_id, bytes_sent, 1)
    
    def increment_error_count(self, stream_id: str):
        """Increment error count for a stream"""
        if stream_id in self.active_streams:
            self.active_streams[stream_id].error_count += 1
            
            # Update monitoring metrics
            if self._metrics_collector:
                self._metrics_collector.increment_stream_error(stream_id)
    
    def get_stream_stats(self) -> Dict[str, Any]:
        """Get statistics for all active streams"""
        return {
            "active_streams": len(self.active_streams),
            "total_bytes_sent": sum(s.bytes_sent for s in self.active_streams.values()),
            "streams": [
                {
                    "id": status.stream_id,
                    "type": status.stream_type,
                    "client_count": status.client_count,
                    "bytes_sent": status.bytes_sent,
                    "start_time": status.start_time.isoformat(),
                    "last_activity": status.last_activity.isoformat(),
                    "is_active": status.is_active,
                    "error_count": status.error_count
                }
                for status in self.active_streams.values()
            ]
        }
    
    def _register_recovery_strategies(self):
        """Register recovery strategies for this service"""
        from .error_handling import (
            get_disconnection_handler, 
            get_auto_restart_manager,
            RestartPolicy
        )
        
        service_name = self.__class__.__name__
        disconnection_handler = get_disconnection_handler()
        auto_restart_manager = get_auto_restart_manager()
        
        async def default_recovery(context):
            """Default recovery strategy"""
            if context.stream_id and context.stream_id in self.active_streams:
                await self.cleanup_stream(context.stream_id)
                self.logger.info(f"Cleaned up failed stream {context.stream_id}")
        
        async def default_fallback(context):
            """Default fallback handler"""
            self.logger.warning(f"Fallback activated for {service_name}")
            # Subclasses can override this behavior
            
        async def disconnection_cleanup(stream_id: str, context):
            """Handle client disconnection cleanup"""
            if stream_id in self.active_streams:
                await self.cleanup_stream(stream_id)
                self.unregister_stream(stream_id)
                self.logger.info(f"Cleaned up disconnected stream {stream_id}")
        
        async def restart_stream(context):
            """Restart failed stream"""
            if hasattr(self, 'restart_stream_implementation'):
                await self.restart_stream_implementation(context)
            else:
                self.logger.warning(f"No restart implementation for {service_name}")
            
        # Register strategies
        self._recovery_manager.register_recovery_strategy(service_name, default_recovery)
        self._recovery_manager.register_fallback_handler(service_name, default_fallback)
        self._recovery_manager.register_restart_handler(service_name, restart_stream)
        disconnection_handler.register_cleanup_callback(service_name, disconnection_cleanup)
        
        # Register default restart policy
        restart_policy = RestartPolicy(
            max_attempts=3,
            base_delay=5.0,
            exponential_backoff=True
        )
        auto_restart_manager.register_restart_policy(service_name, restart_policy)
    
    async def handle_stream_error(self, error: Exception, stream_id: str, operation: str = None) -> bool:
        """Handle stream error using comprehensive error handling"""
        from .error_handling import ErrorContext, get_auto_restart_manager
        
        context = ErrorContext(
            stream_type=self.__class__.__name__,
            stream_id=stream_id,
            operation=operation,
            additional_data={"service": self.__class__.__name__, "error": error}
        )
        
        # Increment error count for monitoring
        self.increment_error_count(stream_id)
        
        # Use comprehensive error handler
        should_retry = await self._error_handler.handle_error(error, context)
        
        if not should_retry:
            # Use comprehensive recovery manager
            await self._recovery_manager.handle_stream_failure(self.__class__.__name__, context)
            
            # Schedule auto-restart if configured
            auto_restart_manager = get_auto_restart_manager()
            restart_scheduled = await auto_restart_manager.schedule_restart(
                self.__class__.__name__,
                context,
                self._create_restart_callback(stream_id)
            )
            
            if restart_scheduled:
                self.logger.info(f"Auto-restart scheduled for stream {stream_id}")
                
        return should_retry
    
    def _create_restart_callback(self, stream_id: str) -> Callable:
        """Create restart callback for auto-restart manager"""
        async def restart_callback(context):
            """Callback to restart specific stream"""
            if hasattr(self, 'restart_stream_implementation'):
                await self.restart_stream_implementation(context)
            else:
                # Default restart behavior
                if stream_id in self.active_streams:
                    await self.cleanup_stream(stream_id)
                    self.unregister_stream(stream_id)
                    
                # Subclasses should override restart_stream_implementation
                # for more sophisticated restart logic
                self.logger.warning(f"Default restart for {stream_id} - cleanup only")
                
        return restart_callback
    
    async def detect_disconnected_clients(self):
        """Detect and handle disconnected clients"""
        from .error_handling import get_disconnection_handler
        
        disconnection_handler = get_disconnection_handler()
        await disconnection_handler.detect_client_disconnections(self.active_streams)
    
    async def graceful_shutdown(self):
        """Gracefully shutdown all streams"""
        from .error_handling import get_disconnection_handler
        
        self.logger.info(f"Initiating graceful shutdown for {self.__class__.__name__}")
        
        disconnection_handler = get_disconnection_handler()
        await disconnection_handler.graceful_shutdown_all(self.active_streams)
        
        # Clear active streams
        self.active_streams.clear()
        
        self.logger.info(f"Graceful shutdown completed for {self.__class__.__name__}")
    
    @abstractmethod
    async def cleanup_stream(self, stream_id: str):
        """Clean up resources for a specific stream"""
        pass


class LegacyStreamErrorHandler:
    """Legacy error handler - use error_handling.StreamErrorHandler instead"""
    
    def __init__(self):
        from .config import get_streaming_config, register_config_change_callback
        from .error_handling import get_error_handler
        
        self.config = get_streaming_config()
        self.logger = logging.getLogger(self.__class__.__name__)
        self._error_handler = get_error_handler()
        
        # Register for configuration changes
        register_config_change_callback(self._on_config_change)
    
    def _on_config_change(self, new_config):
        """Handle configuration changes"""
        self.config = new_config
    
    async def handle_stream_error(self, error: Exception, stream_type: str, stream_id: str = None) -> bool:
        """
        Handle streaming errors with retry logic
        Returns True if the error was handled and stream should continue
        """
        from .error_handling import ErrorContext
        
        context = ErrorContext(
            stream_type=stream_type,
            stream_id=stream_id,
            operation="stream_operation"
        )
        
        return await self._error_handler.handle_error(error, context)
    
    def _is_recoverable_error(self, error: Exception) -> bool:
        """Determine if an error is recoverable"""
        recoverable_errors = (
            ConnectionError,
            TimeoutError,
            asyncio.TimeoutError,
            OSError
        )
        return isinstance(error, recoverable_errors)
    
    def log_stream_error(self, error: Exception, context: Dict[str, Any]):
        """Log streaming errors with context"""
        self.logger.error(
            f"Streaming error: {context['error_type']} - {context['error_message']}",
            extra=context
        )


class SSEConnectionManager:
    """Manager for Server-Sent Events connections with disconnection handling"""
    
    def __init__(self):
        self.connections: Dict[str, asyncio.Queue] = {}
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Integration with disconnection handler
        from .error_handling import get_disconnection_handler
        self._disconnection_handler = get_disconnection_handler()
        self._register_cleanup_callbacks()
        
        # Health monitoring
        self._last_activity: Dict[str, datetime] = {}
        self._connection_timeout = 300  # 5 minutes
        
    def _register_cleanup_callbacks(self):
        """Register cleanup callbacks with disconnection handler"""
        async def sse_cleanup(stream_id: str, context):
            """Cleanup callback for SSE connections"""
            if stream_id in self.connections:
                await self.remove_client_by_id(stream_id)
                
        self._disconnection_handler.register_cleanup_callback("SSE", sse_cleanup)
    
    async def add_client(self, client_id: Optional[str] = None) -> tuple[str, asyncio.Queue]:
        """Add new SSE client with unique ID"""
        if client_id is None:
            client_id = f"sse_client_{int(time.time() * 1000)}"
            
        client_queue = asyncio.Queue()
        self.connections[client_id] = client_queue
        self.connection_metadata[client_id] = {
            "connected_at": datetime.now(),
            "message_count": 0,
            "last_activity": datetime.now()
        }
        self._last_activity[client_id] = datetime.now()
        
        self.logger.info(f"Added SSE client {client_id}. Total connections: {len(self.connections)}")
        return client_id, client_queue
    
    async def remove_client(self, client_queue: asyncio.Queue):
        """Remove SSE client by queue reference"""
        client_id = None
        for cid, queue in self.connections.items():
            if queue is client_queue:
                client_id = cid
                break
                
        if client_id:
            await self.remove_client_by_id(client_id)
    
    async def remove_client_by_id(self, client_id: str):
        """Remove SSE client by ID"""
        if client_id in self.connections:
            # Clean up queue
            queue = self.connections[client_id]
            try:
                # Clear any remaining messages
                while not queue.empty():
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
            except Exception as e:
                self.logger.warning(f"Error clearing queue for client {client_id}: {e}")
                
            del self.connections[client_id]
            
        if client_id in self.connection_metadata:
            del self.connection_metadata[client_id]
            
        if client_id in self._last_activity:
            del self._last_activity[client_id]
            
        self.logger.info(f"Removed SSE client {client_id}. Total connections: {len(self.connections)}")
    
    async def broadcast(self, message: str):
        """Broadcast message to all connected clients with disconnection detection"""
        if not self.connections:
            return
        
        disconnected_clients = set()
        successful_sends = 0
        
        for client_id, client_queue in self.connections.copy().items():
            try:
                # Use timeout to detect slow/disconnected clients
                await asyncio.wait_for(client_queue.put(message), timeout=5.0)
                
                # Update activity tracking
                self._last_activity[client_id] = datetime.now()
                if client_id in self.connection_metadata:
                    self.connection_metadata[client_id]["message_count"] += 1
                    self.connection_metadata[client_id]["last_activity"] = datetime.now()
                    
                successful_sends += 1
                
            except asyncio.TimeoutError:
                self.logger.warning(f"Timeout sending to client {client_id}")
                disconnected_clients.add(client_id)
            except Exception as e:
                self.logger.warning(f"Failed to send message to client {client_id}: {e}")
                disconnected_clients.add(client_id)
        
        # Remove disconnected clients
        for client_id in disconnected_clients:
            await self.remove_client_by_id(client_id)
            
        if disconnected_clients:
            self.logger.info(f"Removed {len(disconnected_clients)} disconnected clients")
            
    async def cleanup_stale_connections(self):
        """Clean up connections that haven't been active"""
        now = datetime.now()
        stale_clients = []
        
        for client_id, last_activity in self._last_activity.items():
            if (now - last_activity).total_seconds() > self._connection_timeout:
                stale_clients.append(client_id)
                
        for client_id in stale_clients:
            self.logger.info(f"Cleaning up stale connection {client_id}")
            await self.remove_client_by_id(client_id)
            
    async def send_to_client(self, client_id: str, message: str) -> bool:
        """Send message to specific client"""
        if client_id not in self.connections:
            return False
            
        try:
            await asyncio.wait_for(
                self.connections[client_id].put(message), 
                timeout=5.0
            )
            
            # Update activity
            self._last_activity[client_id] = datetime.now()
            if client_id in self.connection_metadata:
                self.connection_metadata[client_id]["message_count"] += 1
                self.connection_metadata[client_id]["last_activity"] = datetime.now()
                
            return True
            
        except (asyncio.TimeoutError, Exception) as e:
            self.logger.warning(f"Failed to send to client {client_id}: {e}")
            await self.remove_client_by_id(client_id)
            return False
    
    def get_connection_count(self) -> int:
        """Get number of active connections"""
        return len(self.connections)
        
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get detailed connection statistics"""
        now = datetime.now()
        
        return {
            "total_connections": len(self.connections),
            "connections": [
                {
                    "client_id": client_id,
                    "connected_duration": (now - metadata["connected_at"]).total_seconds(),
                    "message_count": metadata["message_count"],
                    "last_activity": metadata["last_activity"].isoformat(),
                    "is_active": (now - self._last_activity.get(client_id, now)).total_seconds() < 60
                }
                for client_id, metadata in self.connection_metadata.items()
            ]
        }
    
    async def graceful_shutdown(self):
        """Gracefully shutdown all connections"""
        self.logger.info("Initiating graceful shutdown of SSE connections")
        
        # Send shutdown message to all clients
        shutdown_message = format_sse_message("shutdown", {"message": "Server shutting down"})
        await self.broadcast(shutdown_message)
        
        # Wait a moment for messages to be sent
        await asyncio.sleep(1.0)
        
        # Clean up all connections
        client_ids = list(self.connections.keys())
        for client_id in client_ids:
            await self.remove_client_by_id(client_id)
            
        self.logger.info("SSE graceful shutdown completed")


def format_sse_message(event: str, data: Any, event_id: str = None, retry: int = None) -> str:
    """Format Server-Sent Events message"""
    import json
    
    message_parts = []
    
    if event_id:
        message_parts.append(f"id: {event_id}")
    
    if retry:
        message_parts.append(f"retry: {retry}")
    
    message_parts.append(f"event: {event}")
    
    if isinstance(data, (dict, list)):
        data = json.dumps(data)
    
    message_parts.append(f"data: {data}")
    message_parts.append("")  # Empty line to end message
    
    return "\n".join(message_parts)