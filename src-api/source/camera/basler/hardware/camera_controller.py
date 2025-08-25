"""
Camera hardware control functionality for BaslerCamera.
"""

import os
import gc
import time
import logging
import traceback
from pypylon import pylon
from camera.basler.camera import PYLON_AVAILABLE
logger = logging.getLogger('BaslerCamera.Hardware')

class CameraController:
    """Handles direct camera hardware control for BaslerCamera"""
    
    def __init__(self, camera_instance):
        """Initialize with a reference to the parent camera object"""
        self.camera = camera_instance
        
    def connect(self):
        """
        Connect to the first available Basler camera
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        if not PYLON_AVAILABLE:
            logger.error("Error: pypylon not available")
            return False
            
        try:
            # Release any existing camera resources
            self.release_camera_resources()
            
            # Check if any Basler cameras are available
            tl_factory = pylon.TlFactory.GetInstance()
            devices = tl_factory.EnumerateDevices()
            
            if not devices:
                logger.error("Error: No Basler cameras found")
                logger.info("Please check:")
                logger.info("1. Camera is connected via USB/GigE")
                logger.info("2. Camera drivers are installed")
                logger.info("3. Camera is powered on")
                return False
                
            logger.info(f"Found {len(devices)} Basler camera(s)")
            for i, device in enumerate(devices):
                logger.info(f"Device {i}: {device.GetFriendlyName()} (Serial: {device.GetSerialNumber()})")
            
            # Try to create device with retries for exclusive access issues
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    logger.info(f"Attempting to connect to camera (attempt {attempt+1}/{max_retries})")
                    
                    # Force cleanup between attempts
                    if attempt > 0:
                        logger.info("Performing cleanup before retry...")
                        try:
                            # Force garbage collection
                            import gc
                            gc.collect()
                            
                            # Wait longer for resources to be freed
                            time.sleep(3.0)
                            
                            # Re-enumerate devices to refresh the list
                            devices = tl_factory.EnumerateDevices()
                            if not devices:
                                logger.error("No cameras found after cleanup")
                                return False
                                
                        except Exception as cleanup_error:
                            logger.warning(f"Cleanup operation failed: {cleanup_error}")
                    
                    # Try to connect to the first available camera
                    logger.info(f"Connecting to: {devices[0].GetFriendlyName()}")
                    self.camera.camera = pylon.InstantCamera(tl_factory.CreateFirstDevice())
                    
                    # Set a connection timeout
                    self.camera.camera.RegisterConfiguration(pylon.ConfigurationEventHandler(), pylon.RegistrationMode_ReplaceAll, pylon.Cleanup_Delete)
                    
                    # Open the camera
                    self.camera.camera.Open()
                    
                    # Verify the connection
                    if not self.camera.camera.IsOpen():
                        raise Exception("Camera failed to open properly")
                        
                    logger.info("Camera opened successfully")
                    break
                    
                except Exception as create_error:
                    error_msg = str(create_error).lower()
                    
                    if "access denied" in error_msg or "exclusive" in error_msg or "busy" in error_msg:
                        logger.error(f"Camera is being used by another application (attempt {attempt+1})")
                        logger.error("Please close Pylon Viewer, other camera software, or restart the application")
                    else:
                        logger.error(f"Failed to connect to camera (attempt {attempt+1}): {create_error}")
                    
                    # Clean up failed attempt
                    if hasattr(self, 'camera') and self.camera.camera is not None:
                        try:
                            self.camera.camera.Close()
                        except:
                            pass
                        self.camera.camera = None
                    
                    if attempt < max_retries - 1:
                        wait_time = 2.0 + (attempt * 1.0)  # Increasing wait time
                        logger.info(f"Waiting {wait_time} seconds before retry...")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"Failed to connect to camera after {max_retries} attempts")
                        logger.error("Common solutions:")
                        logger.error("1. Close Pylon Viewer or other camera applications")
                        logger.error("2. Unplug and reconnect the camera")
                        logger.error("3. Restart this application")
                        logger.error("4. Check camera drivers and permissions")
                        self.camera.is_connected_flag = False
                        return False
            
            # # Apply optimizations based on camera type
            # self.optimize_camera_settings()
            
            # # Configure camera settings
            # self.configure_camera_settings()
            
            # Get camera info
            device_info = self.camera.camera.GetDeviceInfo()
            logger.info(f"Connected to: {device_info.GetFriendlyName()}")
            logger.info(f"Model: {device_info.GetModelName()}")
            logger.info(f"Serial: {device_info.GetSerialNumber()}")
            
            self.camera.is_connected_flag = True
            
            # Start in snapshot mode by default
            self.camera.set_mode("snapshot")
            
            # Start the event processing thread
            self.camera.event_processor.start_event_processing()
            
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to camera: {e}")
            traceback.print_exc()
            if self.camera.camera is not None:
                try:
                    self.camera.camera.Close()
                except:
                    pass
                self.camera.camera = None
            self.camera.is_connected_flag = False
            return False
            
    def optimize_camera_settings(self):
        """Apply optimized settings based on camera type"""
        try:
            # Check if this is a GigE camera
            if (hasattr(self.camera.camera.GetDeviceInfo(), "GetDeviceClass") and 
                self.camera.camera.GetDeviceInfo().GetDeviceClass() == "BaslerGigE"):
                logger.info("GigE camera detected - applying optimized network settings for reliable image transfer")
                
                # ===== Buffer Settings =====
                # Increase the number of buffers dramatically to prevent buffer underruns
                if hasattr(self.camera.camera, "MaxNumBuffer"):
                    self.camera.camera.MaxNumBuffer.SetValue(100)  # Use many more buffers (default is often 10)
                    logger.info(f"Set MaxNumBuffer to {self.camera.camera.MaxNumBuffer.GetValue()}")
                
                # ===== Network Packet Settings =====
                # Set optimal packet size - try jumbo frames first, then fall back to standard
                try:
                    if hasattr(self.camera.camera, "GevSCPSPacketSize"):
                        # First try to get the network recommended value
                        try:
                            if hasattr(self.camera.camera, "GevSCPSPacketSizeMax"):
                                max_size = self.camera.camera.GevSCPSPacketSizeMax.GetValue()
                                logger.info(f"Network reports max packet size: {max_size}")
                                # Use slightly smaller than max for stability
                                packet_size = max(1500, max_size - 36)
                            else:
                                # Try standard jumbo frame size if max not available
                                packet_size = 8192  # 8KB packets (jumbo frames)
                                
                            self.camera.camera.GevSCPSPacketSize.SetValue(packet_size)
                            logger.info(f"Set GevSCPSPacketSize to {self.camera.camera.GevSCPSPacketSize.GetValue()}")
                        except Exception:
                            # Fall back to standard frame size if jumbo frames fail
                            try:
                                packet_size = 1500  # Standard Ethernet frame size
                                self.camera.camera.GevSCPSPacketSize.SetValue(packet_size)
                                logger.info(f"Fallback: Set GevSCPSPacketSize to {self.camera.camera.GevSCPSPacketSize.GetValue()}")
                            except Exception as fallback_error:
                                logger.error(f"Could not set fallback packet size: {fallback_error}")
                except Exception as packet_error:
                    logger.error(f"Could not set packet size: {packet_error}")
                
                # ===== Transmission Reliability Settings =====
                # Increase the inter-packet delay to prevent network congestion
                try:
                    if hasattr(self.camera.camera, "GevSCPD"):
                        self.camera.camera.GevSCPD.SetValue(10000)  # 10000 ticks
                        logger.info(f"Set GevSCPD (inter-packet delay) to {self.camera.camera.GevSCPD.GetValue()}")
                except Exception as delay_error:
                    logger.error(f"Could not set packet delay: {delay_error}")
                
                # Increase the number of resends for lost packets
                try:
                    if hasattr(self.camera.camera, "GevSCFTD"):
                        self.camera.camera.GevSCFTD.SetValue(True)
                        logger.info("Enabled frame transfer delay (GevSCFTD)")
                except Exception:
                    pass
                    
                # Set frame transmission timeout
                try:
                    if hasattr(self.camera.camera, "GevSCBWT"):
                        self.camera.camera.GevSCBWT.SetValue(10000)  # 10000 ticks
                        logger.info(f"Set bandwidth timeout (GevSCBWT) to {self.camera.camera.GevSCBWT.GetValue()}")
                except Exception:
                    pass
                
                # Enable frame retention to prevent frame loss
                try:
                    if hasattr(self.camera.camera, "GevStreamChannelSelector") and hasattr(self.camera.camera, "GevStreamFrameRetentionEnable"):
                        # Select the stream channel
                        self.camera.camera.GevStreamChannelSelector.SetValue(0)  # Usually channel 0
                        # Enable frame retention
                        self.camera.camera.GevStreamFrameRetentionEnable.SetValue(True)
                        logger.info("Enabled GevStreamFrameRetentionEnable")
                except Exception as retention_error:
                    logger.warning(f"Could not enable frame retention: {retention_error}")
                    
                # ===== Timeout Settings =====
                # Increase frame timeout
                try:
                    if hasattr(self.camera.camera, "GrabTimeout"):
                        self.camera.camera.GrabTimeout.SetValue(10000)  # 10000ms timeout (10 seconds)
                        logger.info(f"Set GrabTimeout to {self.camera.camera.GrabTimeout.GetValue()}ms")
                except Exception as timeout_error:
                    logger.error(f"Could not set grab timeout: {timeout_error}")
                    
                logger.info("Completed GigE camera optimization for reliable image transfer")
        except Exception as gige_error:
            logger.error(f"Could not apply GigE optimizations: {gige_error}")
    
    def configure_camera_settings(self):
        """Configure basic camera settings"""
        try:
            # Set color format
            try:
                self.camera.camera.PixelFormat.SetValue("BayerRG8")  # Color image format
            except Exception as e:
                logger.warning(f"Could not set PixelFormat: {e}")
                
            # Set exposure time
            try:
                # Try different parameter names for exposure time that might exist
                if hasattr(self.camera.camera, "ExposureTime"):
                    self.camera.camera.ExposureTime.SetValue(self.camera.exposure_time_us)
                    logger.info(f"Set exposure time to {self.camera.exposure_time_us} μs using ExposureTime")
                elif hasattr(self.camera.camera, "ExposureTimeAbs"):
                    self.camera.camera.ExposureTimeAbs.SetValue(self.camera.exposure_time_us)
                    logger.info(f"Set exposure time to {self.camera.exposure_time_us} μs using ExposureTimeAbs")
                elif hasattr(self.camera.camera, "ExposureTimeRaw"):
                    self.camera.camera.ExposureTimeRaw.SetValue(self.camera.exposure_time_us)
                    logger.info(f"Set exposure time to {self.camera.exposure_time_us} μs using ExposureTimeRaw")
                else:
                    logger.warning(f"Could not set exposure time - no compatible parameter found")
            except Exception as e:
                logger.warning(f"Could not set exposure time: {e}")
                # Continue connecting despite exposure setting failure
            
            # Configure chunks for timestamps
            try:
                self.camera.camera.ChunkModeActive = True
                self.camera.camera.ChunkSelector = "Timestamp"
                self.camera.camera.ChunkEnable = True
            except Exception as chunk_error:
                logger.warning(f"Chunk mode configuration failed, timestamps may not be available: {chunk_error}")
                
        except Exception as e:
            logger.error(f"Error configuring camera: {e}")
    
    def release_camera_resources(self):
        """Safely release all camera resources"""
        try:
            # Stop event processing
            self.camera.event_processor.stop_event_processing()
            
            # Stop recording if active
            if self.camera.is_recording:
                self.camera.stop_recording()
            
            # Stop grabbing if active
            if self.camera.is_grabbing:
                self.camera.stop_grabbing()
            
            if self.camera.camera:
                try:
                    if self.camera.camera.IsGrabbing():
                        logger.info("Stopping camera grabbing")
                        self.camera.camera.StopGrabbing()
                except Exception as grab_error:
                    logger.error(f"Error stopping grabbing: {grab_error}")
                
                try:
                    if self.camera.camera.IsOpen():
                        logger.info("Closing camera")
                    self.camera.camera.Close()
                except Exception as close_error:
                    logger.error(f"Error closing camera: {close_error}")
                
                # Set to None to ensure garbage collection
                self.camera.camera = None
                
                # Give the system time to release resources
                time.sleep(1.0)
                
                # Force garbage collection
                gc.collect()
                
                logger.info("Camera resources released")
        except Exception as e:
            logger.error(f"Error releasing camera resources: {e}")
            
    def disconnect(self):
        """
        Disconnect from the camera
        
        Returns:
            bool: True if disconnection successful, False otherwise
        """
        try:
            self.release_camera_resources()
            self.camera.is_connected_flag = False
            return True
        except Exception as e:
            logger.error(f"Error disconnecting from camera: {e}")
            traceback.print_exc()
            return False
    
    def is_connected(self):
        """
        Check if camera is connected
        
        Returns:
            bool: True if connected, False otherwise
        """
        try:
            return self.camera.camera is not None and self.camera.camera.IsOpen()
        except Exception:
            return False
    def test_camera_detection(self):
        """
        Test camera detection without connecting
        
        Returns:
            dict: Detection results and diagnostics
        """
        if not PYLON_AVAILABLE:
            return {
                "success": False,
                "error": "pypylon not available",
                "cameras": []
            }
            
        try:
            tl_factory = pylon.TlFactory.GetInstance()
            devices = tl_factory.EnumerateDevices()
            
            camera_list = []
            for i, device in enumerate(devices):
                camera_info = {
                    "index": i,
                    "friendly_name": device.GetFriendlyName(),
                    "model_name": device.GetModelName(),
                    "serial_number": device.GetSerialNumber(),
                    "device_class": device.GetDeviceClass() if hasattr(device, "GetDeviceClass") else "Unknown"
                }
                camera_list.append(camera_info)
                
            return {
                "success": True,
                "camera_count": len(devices),
                "cameras": camera_list,
                "pylon_available": True
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "cameras": [],
                "pylon_available": PYLON_AVAILABLE
            }
            
    def check_camera_safety(self):
        """Verify camera is connected and in a safe state to use"""
        if not self.camera.camera:
            self.camera._last_error = "Camera not initialized"
            return False
            
        if not self.camera.camera.IsOpen():
            self.camera._last_error = "Camera is not open"
            return False
            
        if self.camera._error_count >= self.camera._max_errors:
            # Too many consecutive errors, try to recover
            logger.warning("Too many camera errors, attempting recovery...")
            self.camera._error_count = 0
            try:
                if self.camera.camera.IsGrabbing():
                    self.camera.camera.StopGrabbing()
                self.camera.camera.Close()
                time.sleep(0.5)
                self.camera.camera.Open()
                if self.camera.mode == 'continuous' or self.camera.mode == 'recording':
                    self.camera.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
                else:
                    self.camera.camera.StartGrabbing(1)
                logger.info("Camera recovery successful")
                return True
            except Exception as e:
                logger.error(f"Camera recovery failed: {e}")
                self.camera._last_error = f"Recovery failed: {str(e)}"
                return False
                
        return True