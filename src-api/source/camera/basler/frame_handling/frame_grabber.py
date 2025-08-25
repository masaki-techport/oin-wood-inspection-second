"""
Frame grabbing functionality for BaslerCamera.
"""

import time
import logging
import threading
import numpy as np
import cv2
from pypylon import pylon

logger = logging.getLogger('BaslerCamera.FrameGrabber')

# Configure performance metrics
PERFORMANCE_METRICS = {
    'frame_grab_time': [],
}

class FrameGrabber:
    """Handles frame grabbing operations for BaslerCamera"""
    
    def __init__(self, camera_instance):
        """Initialize with a reference to the parent camera object"""
        self.camera = camera_instance
        self.grab_lock = threading.RLock()
        self.error_count = 0
        self.last_error = None
        
    def optimized_frame_grab(self, converter, max_attempts=5, grab_timeout=1000):
        """Optimized frame grabbing implementation for better performance"""
        
        for attempt in range(max_attempts):
            try:
                # Use optimized locking strategy - shorter lock duration
                grab_result = None
                
                # Critical section with minimal lock time
                with self.grab_lock:
                    # Make sure to access the camera hardware instance
                    if self.camera.camera is None:
                        logger.warning("Camera hardware not initialized")
                        return None
                    
                    # Check if camera is still grabbing, if not start it
                    if not self.camera.camera.IsGrabbing():
                        logger.info("Camera not grabbing, starting grab operation...")
                        try:
                            self.camera.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
                            # Give the camera a moment to start grabbing
                            time.sleep(0.2)
                        except Exception as start_error:
                            logger.error(f"Failed to start grabbing: {start_error}")
                    
                    # Use a longer timeout for the first attempt
                    current_timeout = grab_timeout * 2 if attempt == 0 else grab_timeout
                    grab_result = self.camera.camera.RetrieveResult(current_timeout, pylon.TimeoutHandling_Return)
                
                # Process result outside lock for better concurrency
                if grab_result and grab_result.GrabSucceeded():
                    # Reset error count on success
                    self.error_count = 0
                    
                    # Get image with minimal conversion
                    start_conversion = time.time()
                    image_rgb = converter.Convert(grab_result).GetArray()
                    conversion_time = time.time() - start_conversion
                    
                    # Get timestamp if available
                    timestamp = int(time.time() * 1000000)  # Default to system time
                    try:
                        if hasattr(self.camera.camera, "ChunkModeActive") and self.camera.camera.ChunkModeActive.GetValue():
                            timestamp = grab_result.ChunkTimestamp.GetValue()
                    except Exception as ts_error:
                        logger.debug(f"Could not get chunk timestamp: {ts_error}")
                        pass  # Use default timestamp
                    
                    # Release grab result immediately to free resources
                    grab_result.Release()
                    
                    # Log performance metrics
                    PERFORMANCE_METRICS['frame_grab_time'].append(conversion_time)
                    logger.info(f"Successfully grabbed frame on attempt {attempt+1}")
                    
                    return {
                        "image": image_rgb,  # Return direct reference for better performance
                        "timestamp": timestamp
                    }
                else:
                    # Handle grab failure with minimal overhead
                    if grab_result:
                        error_msg = f"Grab failed: {grab_result.GetErrorDescription()}"
                        grab_result.Release()
                        self.last_error = error_msg
                    else:
                        self.last_error = "Grab result is None"
                    
                    self.error_count += 1
                    logger.debug(f"Attempt {attempt+1}: {self.last_error}")
                    
                    # Try recovery steps based on the type of error
                    if attempt < max_attempts - 1:  # Don't perform recovery on last attempt
                        if "incompletely grabbed" in self.last_error:
                            # This is typically a network issue with GigE cameras
                            logger.warning("Incomplete frame detected (network issue), adjusting settings before retry")
                            time.sleep(0.5)  # Wait longer for network to stabilize
                            
                            # First try to adjust GigE camera settings that affect network reliability
                            try:
                                if (hasattr(self.camera.camera.GetDeviceInfo(), "GetDeviceClass") and 
                                    self.camera.camera.GetDeviceInfo().GetDeviceClass() == "BaslerGigE"):
                                    
                                    # Increase inter-packet delay (helps with network congestion)
                                    if hasattr(self.camera.camera, "GevSCPD"):
                                        current = self.camera.camera.GevSCPD.GetValue()
                                        # Start with modest increases and build up if needed
                                        new_value = min(50000, current + 500) 
                                        self.camera.camera.GevSCPD.SetValue(new_value)
                                        logger.info(f"Adjusted GevSCPD from {current} to {new_value}")
                                    
                                    # Enable frame retention if available
                                    try:
                                        if hasattr(self.camera.camera, "GevStreamChannelSelector") and \
                                           hasattr(self.camera.camera, "GevStreamFrameRetentionEnable"):
                                            self.camera.camera.GevStreamChannelSelector.SetValue(0)
                                            self.camera.camera.GevStreamFrameRetentionEnable.SetValue(True)
                                            logger.info("Enabled frame retention for reliability")
                                    except Exception as retention_error:
                                        logger.debug(f"Frame retention adjustment failed: {retention_error}")
                            except Exception as gige_error:
                                logger.debug(f"GigE settings adjustment failed: {gige_error}")
                            
                            # Try to stop and restart grabbing (more aggressive recovery for network issues)
                            if attempt > 0:  # Do this on all but the first attempt for incomplete frames
                                try:
                                    with self.grab_lock:
                                        if self.camera.camera.IsGrabbing():
                                            logger.info("Restarting grab session to recover from network issue")
                                            self.camera.camera.StopGrabbing()
                                            time.sleep(0.5)  # Longer wait for network cameras
                                            self.camera.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
                                            time.sleep(0.3)
                                except Exception as restart_error:
                                    logger.error(f"Error during grab restart: {restart_error}")
                        else:
                            # For other errors, use a shorter delay
                            time.sleep(0.15)
                    
            except Exception as e:
                self.error_count += 1
                self.last_error = str(e)
                logger.debug(f"Exception during grab attempt {attempt+1}: {e}")
                time.sleep(0.15)  # Slightly longer sleep time for error recovery
                
                # If we get a critical exception, try to reset the camera connection
                if ("Device not accessible" in str(e) or "Access denied" in str(e) or 
                    "incompletely grabbed" in str(e) or "Buffer was incompletely grabbed" in str(e)):
                    logger.warning(f"Critical camera error detected: {str(e)}, attempting connection reset")
                    try:
                        # For incomplete grab errors specifically, try to fix network settings
                        if "incompletely grabbed" in str(e) or "Buffer was incompletely grabbed" in str(e):
                            logger.warning("Incomplete grab error detected - likely a network issue")
                            # Try to optimize GigE settings if this is a network camera
                            try:
                                if (hasattr(self.camera.camera.GetDeviceInfo(), "GetDeviceClass") and 
                                    self.camera.camera.GetDeviceInfo().GetDeviceClass() == "BaslerGigE"):
                                    # Increase the inter-packet delay which often helps with incomplete frames
                                    if hasattr(self.camera.camera, "GevSCPD"):
                                        current = self.camera.camera.GevSCPD.GetValue()
                                        # Increase by 50% each time, up to a reasonable maximum
                                        new_value = min(100000, int(current * 1.5))
                                        self.camera.camera.GevSCPD.SetValue(new_value)
                                        logger.info(f"Increased GevSCPD from {current} to {new_value} to fix incomplete grabs")
                                        
                                    # Also try to enable frame retention if not already enabled
                                    try:
                                        if hasattr(self.camera.camera, "GevStreamChannelSelector") and \
                                           hasattr(self.camera.camera, "GevStreamFrameRetentionEnable"):
                                            self.camera.camera.GevStreamChannelSelector.SetValue(0)
                                            self.camera.camera.GevStreamFrameRetentionEnable.SetValue(True)
                                            logger.info("Enabled frame retention to fix incomplete grabs")
                                    except Exception:
                                        pass
                            except Exception as gige_error:
                                logger.error(f"Failed to adjust GigE settings: {gige_error}")
                        
                        # Perform general recovery
                        self.handle_grab_recovery(self.camera.camera, self.camera.exposure_time_us, 
                                                 self.error_count, 0, 1)
                    except Exception as recovery_error:
                        logger.error(f"Recovery attempt failed: {recovery_error}")
        
        # All attempts failed - create a default empty image as fallback
        logger.warning("Failed to grab image after multiple attempts")
        
        # Create a small black image with "No Camera Signal" text as fallback
        height, width = 480, 640
        fallback_image = np.zeros((height, width, 3), dtype=np.uint8)
        cv2.putText(fallback_image, "No Camera Signal", (width//2 - 100, height//2),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        return {
            "image": fallback_image,
            "timestamp": int(time.time() * 1000000),
            "is_fallback": True
        }
    
    def handle_grab_recovery(self, camera, exposure_time_us, consecutive_errors, recovery_attempts, max_recovery_attempts):
        """Handle camera recovery after errors - extracted for better maintainability"""
        if recovery_attempts < max_recovery_attempts:
            logger.warning(f"Too many errors, attempting recovery {recovery_attempts+1}/{max_recovery_attempts}")
            
            try:
                # Determine if this is a GigE camera for special handling
                is_gige_camera = False
                try:
                    if hasattr(camera.GetDeviceInfo(), "GetDeviceClass"):
                        is_gige_camera = (camera.GetDeviceInfo().GetDeviceClass() == "BaslerGigE")
                        if is_gige_camera:
                            logger.info("GigE camera detected - applying network-specific recovery")
                except Exception:
                    pass
                    
                # Optimized recovery sequence
                with self.grab_lock:
                    # Stop grabbing first
                    if camera.IsGrabbing():
                        logger.info("Stopping current grab session")
                        camera.StopGrabbing()
                        time.sleep(0.5)  # Wait for resources to be released
                    
                    # Check camera connection
                    if not camera.IsOpen():
                        logger.info("Camera disconnected, reopening...")
                        camera.Open()
                        time.sleep(1.0)  # Longer wait time for connection to stabilize
                    else:
                        # Reset camera parameters
                        try:
                            # For GigE cameras with network issues, apply more aggressive recovery
                            if is_gige_camera and self.last_error and ("incompletely grabbed" in self.last_error):
                                logger.info("Applying GigE-specific recovery for incomplete frame errors")
                                
                                # Try to reset the stream channel
                                try:
                                    if hasattr(camera, "GevStreamChannelSelector"):
                                        camera.GevStreamChannelSelector.SetValue(0)
                                        
                                        # Increase packet size if under 8KB
                                        if hasattr(camera, "GevSCPSPacketSize"):
                                            current_size = camera.GevSCPSPacketSize.GetValue()
                                            if current_size < 8192:
                                                # Try standard size first, as very small packets can cause issues
                                                new_size = min(8192, current_size * 2)
                                                logger.info(f"Adjusting packet size from {current_size} to {new_size}")
                                                camera.GevSCPSPacketSize.SetValue(new_size)
                                            
                                        # Increase inter-packet delay significantly
                                        if hasattr(camera, "GevSCPD"):
                                            current_delay = camera.GevSCPD.GetValue()
                                            # More aggressive increase for recovery
                                            new_delay = current_delay * 2 
                                            logger.info(f"Increasing inter-packet delay from {current_delay} to {new_delay}")
                                            camera.GevSCPD.SetValue(new_delay)
                                            
                                        # Enable frame retention
                                        if hasattr(camera, "GevStreamFrameRetentionEnable"):
                                            camera.GevStreamFrameRetentionEnable.SetValue(True)
                                            logger.info("Enabled frame retention for better reliability")
                                except Exception as gige_error:
                                    logger.error(f"GigE-specific recovery failed: {gige_error}")
                            
                            # Standard parameter reset
                            if hasattr(camera, "ExposureTime"):
                                camera.ExposureTime.SetValue(exposure_time_us)
                                logger.info(f"Reset exposure time to {exposure_time_us}")
                                
                        except Exception as param_error:
                            logger.error(f"Parameter reset failed: {param_error}")
                    
                    # Additional pause before restarting grabbing
                    time.sleep(0.5)
                    
                    # Restart grabbing with appropriate strategy
                    logger.info("Restarting camera grabbing after recovery")
                    grab_strategy = pylon.GrabStrategy_LatestImageOnly
                    camera.StartGrabbing(grab_strategy)
                    
                    # Wait for grabbing to stabilize
                    time.sleep(0.5)
                
                logger.info("Camera recovery completed successfully")
                return True
            
            except Exception as recovery_error:
                logger.error(f"Error during recovery: {recovery_error}")
                return False
        else:
            logger.warning(f"Maximum recovery attempts ({max_recovery_attempts}) reached")
            return False