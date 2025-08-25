"""
Server-Sent Events streaming for real-time sensor status updates
"""
import asyncio
import json
import time
from typing import AsyncGenerator, Dict, Any
from fastapi.responses import StreamingResponse

from .base import BaseStreamingService, SSEConnectionManager, format_sse_message


class SensorStatusBroadcaster(BaseStreamingService):
    """Broadcaster for real-time sensor status updates via SSE"""
    
    def __init__(self):
        super().__init__()
        self.connection_manager = SSEConnectionManager()
        self.last_status = None
        self.monitoring_task = None
        self.is_monitoring = False
    
    async def add_client(self) -> asyncio.Queue:
        """Add new SSE client"""
        client_queue = await self.connection_manager.add_client()
        
        # Send initial status if available
        if self.last_status:
            try:
                initial_message = format_sse_message("sensor-status", self.last_status)
                await client_queue.put(initial_message)
            except Exception as e:
                self.logger.warning(f"Failed to send initial status to new client: {e}")
        
        return client_queue
    
    async def remove_client(self, client_queue: asyncio.Queue):
        """Remove SSE client"""
        await self.connection_manager.remove_client(client_queue)
    
    async def broadcast_status(self, status: Dict[str, Any]):
        """Broadcast status to all connected clients"""
        self.last_status = status
        
        try:
            message = format_sse_message("sensor-status", status, event_id=str(int(time.time() * 1000)))
            await self.connection_manager.broadcast(message)
            
            # Update metrics for all active streams
            for stream_id in self.active_streams:
                self.update_stream_activity(stream_id, len(message.encode()))
                
        except Exception as e:
            self.logger.error(f"Failed to broadcast sensor status: {e}")
    
    async def broadcast_event(self, event_type: str, data: Dict[str, Any]):
        """Broadcast custom event to all connected clients"""
        try:
            message = format_sse_message(event_type, data, event_id=str(int(time.time() * 1000)))
            await self.connection_manager.broadcast(message)
        except Exception as e:
            self.logger.error(f"Failed to broadcast event {event_type}: {e}")
    
    async def start_monitoring(self):
        """Start continuous status monitoring"""
        if self.is_monitoring:
            return
        
        self.is_monitoring = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        self.logger.info("Started sensor status monitoring")
    
    async def stop_monitoring(self):
        """Stop continuous status monitoring"""
        self.is_monitoring = False
        
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Stopped sensor status monitoring")
    
    async def _monitoring_loop(self):
        """Main monitoring loop that fetches and broadcasts status updates"""
        from endpoints.sensor_inspection import get_sensor_inspection_status
        
        while self.is_monitoring:
            try:
                # Only fetch status if we have connected clients
                if self.connection_manager.get_connection_count() > 0:
                    # Get current sensor status
                    status_response = get_sensor_inspection_status()
                    
                    # Check if status has changed significantly
                    if self._should_broadcast_status(status_response):
                        await self.broadcast_status(status_response)
                
                await asyncio.sleep(self.config.sse.update_interval)
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(1.0)  # Longer sleep on error
    
    def _should_broadcast_status(self, new_status: Dict[str, Any]) -> bool:
        """Determine if status should be broadcast (has changed significantly)"""
        if not self.last_status:
            return True
        
        # Check for significant changes
        significant_keys = [
            'active', 'sensors', 'capture', 'inspection_data', 'ai_threshold'
        ]
        
        for key in significant_keys:
            if key in new_status and key in self.last_status:
                if new_status[key] != self.last_status[key]:
                    return True
        
        return False
    
    async def generate_sse_stream(self, client_queue: asyncio.Queue) -> AsyncGenerator[str, None]:
        """Generate SSE stream for a specific client"""
        stream_id = self.generate_stream_id()
        status = self.register_stream(stream_id, "sensor_sse")
        
        try:
            # Send initial connection message
            welcome_message = format_sse_message(
                "connected", 
                {"message": "Connected to sensor status stream", "timestamp": time.time()}
            )
            yield welcome_message
            
            while status.is_active:
                try:
                    # Wait for message with timeout
                    message = await asyncio.wait_for(client_queue.get(), timeout=30.0)
                    yield message
                    self.update_stream_activity(stream_id, len(message.encode()))
                    
                except asyncio.TimeoutError:
                    # Send keepalive message
                    keepalive = format_sse_message("keepalive", {"timestamp": time.time()})
                    yield keepalive
                    
                except Exception as e:
                    self.logger.error(f"Error in SSE stream {stream_id}: {e}")
                    self.increment_error_count(stream_id)
                    break
        
        except Exception as e:
            self.logger.error(f"Fatal error in SSE stream {stream_id}: {e}")
        
        finally:
            await self.cleanup_stream(stream_id)
    
    async def cleanup_stream(self, stream_id: str):
        """Clean up resources for a specific stream"""
        if stream_id in self.active_streams:
            self.active_streams[stream_id].is_active = False
        
        self.unregister_stream(stream_id)
        self.logger.info(f"Cleaned up SSE stream {stream_id}")
    
    def get_connection_count(self) -> int:
        """Get number of active SSE connections"""
        return self.connection_manager.get_connection_count()


# Global sensor status broadcaster instance
sensor_broadcaster = SensorStatusBroadcaster()


async def create_sensor_sse_response() -> StreamingResponse:
    """Create a StreamingResponse for sensor status SSE"""
    
    # Add client to broadcaster
    client_queue = await sensor_broadcaster.add_client()
    
    # Start monitoring if not already started
    await sensor_broadcaster.start_monitoring()
    
    async def generate_sse():
        """Generate SSE stream"""
        try:
            async for message in sensor_broadcaster.generate_sse_stream(client_queue):
                yield message
        except Exception as e:
            sensor_broadcaster.logger.error(f"Error in SSE generation: {e}")
        finally:
            # Clean up client connection
            await sensor_broadcaster.remove_client(client_queue)
    
    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )


async def broadcast_sensor_event(event_type: str, data: Dict[str, Any]):
    """Utility function to broadcast sensor events"""
    await sensor_broadcaster.broadcast_event(event_type, data)


async def broadcast_sensor_status(status: Dict[str, Any]):
    """Utility function to broadcast sensor status"""
    await sensor_broadcaster.broadcast_status(status)