"""
Camera streaming service for real-time video feeds
"""
import asyncio
import cv2
import time
from typing import AsyncGenerator, Optional
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from .base import BaseStreamingService
from .error_handling import StreamErrorHandler
from camera_manager import camera_manager


class CameraStreamManager(BaseStreamingService):
    """Manager for camera video streaming with comprehensive recovery"""
    
    def __init__(self):
        super().__init__()
        self.error_handler = StreamErrorHandler()
        self.active_camera_streams = {}
        
        # Mark camera streams as critical
        self._recovery_manager.mark_as_critical("CameraStreamManager")
        
        # Register custom recovery strategies
        self._register_camera_recovery_strategies()
    
    async def generate_frames(self, camera_id: str, camera_type: str = "basler") -> AsyncGenerator[bytes, None]:
        """Generate continuous frame stream for camera"""
        stream_id = self.generate_stream_id()
        status = self.register_stream(stream_id, f"camera_{camera_type}")
        
        try:
            # Get camera from manager
            camera = camera_manager.get_camera(camera_type, f"stream_{stream_id}")
            
            if not camera or not camera.is_connected():
                # Generate fallback frames
                async for frame in self._generate_fallback_frames(stream_id):
                    yield frame
                return
            
            self.logger.info(f"Starting camera stream {stream_id} for {camera_type} camera")
            
            frame_interval = 1.0 / self.config.camera.frame_rate
            last_frame_time = 0
            
            while status.is_active:
                current_time = time.time()
                
                # Control frame rate
                if current_time - last_frame_time < frame_interval:
                    await asyncio.sleep(0.01)  # Small sleep to prevent busy waiting
                    continue
                
                try:
                    # Get frame from camera
                    frame_data = camera.get_frame()
                    
                    if not frame_data or "image" not in frame_data:
                        # Generate error frame
                        frame_bytes = self._generate_error_frame("No frame data available")
                    else:
                        # Convert frame to JPEG
                        img = frame_data["image"]
                        img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                        
                        # Encode with configured quality
                        encode_params = [cv2.IMWRITE_JPEG_QUALITY, self.config.camera.quality]
                        success, buffer = cv2.imencode('.jpg', img_bgr, encode_params)
                        
                        if not success:
                            frame_bytes = self._generate_error_frame("Failed to encode frame")
                        else:
                            frame_bytes = buffer.tobytes()
                    
                    # Format as multipart stream
                    multipart_frame = (
                        b'--frame\r\n'
                        b'Content-Type: image/jpeg\r\n'
                        b'Content-Length: ' + str(len(frame_bytes)).encode() + b'\r\n\r\n' +
                        frame_bytes + b'\r\n'
                    )
                    
                    yield multipart_frame
                    
                    # Update metrics
                    self.update_stream_activity(stream_id, len(multipart_frame))
                    last_frame_time = current_time
                    
                except Exception as e:
                    # Use comprehensive error handling
                    should_continue = await self.handle_stream_error(e, stream_id, "frame_generation")
                    
                    if should_continue:
                        # Generate error frame and continue
                        error_frame = self._generate_error_frame(f"Camera error: {str(e)}")
                        multipart_frame = (
                            b'--frame\r\n'
                            b'Content-Type: image/jpeg\r\n'
                            b'Content-Length: ' + str(len(error_frame)).encode() + b'\r\n\r\n' +
                            error_frame + b'\r\n'
                        )
                        yield multipart_frame
                        continue
                    else:
                        # Switch to fallback mode
                        self.logger.warning(f"Switching to fallback mode for stream {stream_id}")
                        async for fallback_frame in self._generate_fallback_frames(stream_id):
                            yield fallback_frame
                        break
        
        except Exception as e:
            self.logger.error(f"Fatal error in camera stream {stream_id}: {e}")
            # Generate final error frame
            error_frame = self._generate_error_frame("Stream terminated due to error")
            yield (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n'
                b'Content-Length: ' + str(len(error_frame)).encode() + b'\r\n\r\n' +
                error_frame + b'\r\n'
            )
        
        finally:
            # Cleanup
            try:
                camera_manager.release_camera(f"stream_{stream_id}")
            except Exception as e:
                self.logger.warning(f"Error releasing camera for stream {stream_id}: {e}")
            
            await self.cleanup_stream(stream_id)
    
    def _register_camera_recovery_strategies(self):
        """Register camera-specific recovery strategies"""
        from .error_handling import RestartPolicy, get_auto_restart_manager
        
        async def camera_recovery(context):
            """Camera-specific recovery strategy"""
            stream_id = context.stream_id
            if stream_id and stream_id in self.active_streams:
                try:
                    # Try to reconnect camera
                    camera_manager.reconnect_camera("basler")
                    self.logger.info(f"Successfully reconnected camera for stream {stream_id}")
                except Exception as e:
                    self.logger.error(f"Camera reconnection failed: {e}")
                    raise
        
        async def camera_fallback(context):
            """Camera fallback to simulation mode"""
            self.logger.info("Activating camera fallback - switching to simulation mode")
            # The fallback is handled in the frame generation loop
            
        async def camera_restart(context):
            """Restart camera stream"""
            stream_id = context.stream_id
            if stream_id:
                # Clean up existing stream
                await self.cleanup_stream(stream_id)
                
                # Restart camera manager
                try:
                    camera_manager.restart_camera_system()
                    self.logger.info(f"Camera system restarted for stream {stream_id}")
                except Exception as e:
                    self.logger.error(f"Camera system restart failed: {e}")
                    raise
        
        # Register strategies
        self._recovery_manager.register_recovery_strategy("CameraStreamManager", camera_recovery)
        self._recovery_manager.register_fallback_handler("CameraStreamManager", camera_fallback)
        self._recovery_manager.register_restart_handler("CameraStreamManager", camera_restart)
        
        # Custom restart policy for cameras
        camera_restart_policy = RestartPolicy(
            max_attempts=5,  # More attempts for critical camera streams
            base_delay=10.0,  # Longer delay for hardware recovery
            max_delay=120.0,
            exponential_backoff=True,
            restart_on_errors=[ConnectionError, TimeoutError, OSError, RuntimeError]
        )
        
        auto_restart_manager = get_auto_restart_manager()
        auto_restart_manager.register_restart_policy("CameraStreamManager", camera_restart_policy)
    
    async def restart_stream_implementation(self, context):
        """Implementation for restarting camera streams"""
        stream_id = context.stream_id
        
        try:
            # Clean up existing resources
            if stream_id in self.active_camera_streams:
                del self.active_camera_streams[stream_id]
                
            # Release camera resources
            camera_manager.release_camera(f"stream_{stream_id}")
            
            # Wait for hardware to stabilize
            await asyncio.sleep(2.0)
            
            # Reinitialize camera
            camera = camera_manager.get_camera("basler", f"stream_{stream_id}")
            if camera and camera.is_connected():
                self.logger.info(f"Successfully restarted camera stream {stream_id}")
            else:
                raise RuntimeError("Failed to reinitialize camera after restart")
                
        except Exception as e:
            self.logger.error(f"Camera stream restart failed: {e}")
            raise
    
    async def _generate_fallback_frames(self, stream_id: str) -> AsyncGenerator[bytes, None]:
        """Generate fallback frames when camera is not available"""
        self.logger.warning(f"Generating fallback frames for stream {stream_id}")
        
        fallback_frame = self._generate_error_frame("Camera not available - running in simulation mode")
        
        frame_interval = 1.0 / self.config.camera.frame_rate
        
        while stream_id in self.active_streams:
            multipart_frame = (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n'
                b'Content-Length: ' + str(len(fallback_frame)).encode() + b'\r\n\r\n' +
                fallback_frame + b'\r\n'
            )
            
            yield multipart_frame
            self.update_stream_activity(stream_id, len(multipart_frame))
            
            await asyncio.sleep(frame_interval)
    
    def _generate_error_frame(self, message: str) -> bytes:
        """Generate an error frame with message"""
        import numpy as np
        
        # Create a simple error image
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        img.fill(50)  # Dark gray background
        
        # Add text (if OpenCV text functions are available)
        try:
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.7
            color = (255, 255, 255)  # White text
            thickness = 2
            
            # Calculate text size and position
            text_size = cv2.getTextSize(message, font, font_scale, thickness)[0]
            text_x = (img.shape[1] - text_size[0]) // 2
            text_y = (img.shape[0] + text_size[1]) // 2
            
            cv2.putText(img, message, (text_x, text_y), font, font_scale, color, thickness)
        except Exception:
            pass  # If text rendering fails, just return the gray image
        
        # Encode as JPEG
        success, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 70])
        
        if success:
            return buffer.tobytes()
        else:
            # Return minimal JPEG if encoding fails
            return b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x11\x08\x01\xe0\x02\x80\x01\x01\x11\x00\x02\x11\x01\x03\x11\x01\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x08\xff\xc4\x00\x14\x10\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00\x3f\x00\xaa\xff\xd9'
    
    async def cleanup_stream(self, stream_id: str):
        """Clean up resources for a specific stream"""
        if stream_id in self.active_streams:
            self.active_streams[stream_id].is_active = False
        
        self.unregister_stream(stream_id)
        self.logger.info(f"Cleaned up camera stream {stream_id}")
    
    def configure_stream(self, frame_rate: int = None, quality: int = None):
        """Configure stream parameters"""
        from .config import update_streaming_config
        
        updates = {}
        if frame_rate is not None:
            updates["frame_rate"] = max(1, min(60, frame_rate))
        
        if quality is not None:
            updates["quality"] = max(10, min(100, quality))
        
        if updates:
            success = update_streaming_config({"camera": updates})
            if success:
                self.logger.info(f"Updated camera stream config: {updates}")
            else:
                self.logger.error("Failed to update camera stream configuration")


# Global camera stream manager instance
camera_stream_manager = CameraStreamManager()


def create_camera_stream_response(camera_id: str, camera_type: str = "basler") -> StreamingResponse:
    """Create a StreamingResponse for camera feed"""
    
    def generate_stream():
        """Synchronous wrapper for async generator"""
        import asyncio
        
        async def async_wrapper():
            async for frame in camera_stream_manager.generate_frames(camera_id, camera_type):
                yield frame
        
        # Run the async generator in the current event loop
        loop = asyncio.get_event_loop()
        gen = async_wrapper()
        
        try:
            while True:
                try:
                    frame = loop.run_until_complete(gen.__anext__())
                    yield frame
                except StopAsyncIteration:
                    break
        except Exception as e:
            camera_stream_manager.logger.error(f"Error in stream wrapper: {e}")
    
    return StreamingResponse(
        generate_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "Connection": "keep-alive"
        }
    )