import __init__
# source/lib/camera/basler_camera.py
from camera.base import AbstractCamera
from pypylon import pylon
from PIL import Image
import cv2
import traceback
import os
from datetime import datetime
import yaml
import time
import threading
import numpy as np
from collections import deque
from typing import Optional, Dict, Any, List
import json # Added for JSON timing reports
import queue  # For the event queue system
import re  # Added for regular expression matching

# Import inference services
from inference.inference_service import WoodKnotInferenceService
from db import Inspection, InspectionResult
from db.inspection_details import InspectionDetails
from db.inspection_presentation import InspectionPresentation
from sqlalchemy.orm import Session
from db.engine import SessionLocal

# Try to import pypylon for Basler cameras
try:
    PYLON_AVAILABLE = True
except ImportError:
    PYLON_AVAILABLE = False
    print("[BASLER_CAMERA] Warning: pypylon not available, Basler cameras will not work")

class BaslerCamera(AbstractCamera):
    """
    Unified Basler camera implementation with buffer recording capability
    """
    
    def __init__(self, exposure_time_us: int = 20000, max_buffer_seconds: int = 30, buffer_fps: int = 10):
        """
        Initialize Basler camera
        
        Args:
            exposure_time_us: Exposure time in microseconds
            max_buffer_seconds: Maximum seconds to keep in buffer for recording
            buffer_fps: Frames per second for buffer recording (10 fps = 0.1 second interval)
        """
        # Camera hardware settings
        self.camera = None
        self.is_connected_flag = False
        self.is_grabbing = False
        self.exposure_time_us = exposure_time_us
        
        # Thread safety
        self.lock = threading.Lock()
        self.grab_lock = threading.Lock()  # Dedicated lock for camera grab operations
        self.grab_thread = None
        self.stop_event = threading.Event()
        
        # Frame handling
        self.latest_frame = None
        self.latest_frame_timestamp = 0
        self.mode = "snapshot"  # Default mode: "snapshot", "continuous", or "recording"
        
        # Buffer for recording
        self.buffer_fps = buffer_fps
        self.max_buffer_seconds = max_buffer_seconds
        self.buffer_size = int(max_buffer_seconds * buffer_fps)
        self.buffer = deque(maxlen=self.buffer_size)
        self.is_recording = False
        self.record_thread = None
        
        # Status tracking
        self.status = "待機中"  # Status in Japanese: "Standby"
        self.save_message = ""
        self.save_path = ""
        self._last_error = None
        self._error_count = 0
        self._max_errors = 3
        
        # Background threads
        self.background_threads = []
        
        # Image converter for Bayer pattern
        self.converter = pylon.ImageFormatConverter() if PYLON_AVAILABLE else None
        if self.converter:
            # Use RGB8packed for proper color representation
            self.converter.OutputPixelFormat = pylon.PixelType_RGB8packed
            self.converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned
        
        # Configuration
        self.config_path = os.path.join(__init__.CONFIG_DIR, 'params.yaml')
        self.save_directory = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                '..',
                'data',
                'images',
                'inspection'
            )
        )
        os.makedirs(self.save_directory, exist_ok=True)
        
        # Initialize inference service
        self.inference_service = WoodKnotInferenceService()
        
        # AI threshold (percentage, 10-100)
        self.ai_threshold = 50
        
        # Store last inspection results for API retrieval
        self.last_inspection_results = None
        
        # Event queue system for handling multiple sensor events
        self.event_queue = queue.Queue()
        self.event_processing_thread = None
        self.event_processing_active = False
        
    def connect(self) -> bool:
        """
        Connect to the first available Basler camera
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        if not PYLON_AVAILABLE:
            print("[BASLER_CAMERA] Error: pypylon not available")
            return False
            
        try:
            # Release any existing camera resources
            self._release_camera_resources()
            
            # Check if any Basler cameras are available
            devices = pylon.TlFactory.GetInstance().EnumerateDevices()
            if not devices:
                print("[BASLER_CAMERA] Error: No Basler cameras found")
                return False
                
            print(f"[BASLER_CAMERA] Found {len(devices)} Basler camera(s)")
            for i, device in enumerate(devices):
                print(f"[BASLER_CAMERA] Device {i}: {device.GetFriendlyName()}")
            
            # Try to create device with retries for exclusive access issues
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    print(f"[BASLER_CAMERA] Creating camera instance (attempt {attempt+1}/{max_retries})")
                    
                    # Force device release at the transport layer before creating a new instance
                    if attempt > 0:
                        print("[BASLER_CAMERA] Attempting to release device at transport layer")
                        try:
                            # Get the transport layer factory
                            tl_factory = pylon.TlFactory.GetInstance()
                            
                            # Try to release all devices
                            for device_info in devices:
                                try:
                                    print(f"[BASLER_CAMERA] Releasing device: {device_info.GetFriendlyName()}")
                                    tl_factory.DestroyDevice(device_info)
                                except Exception as release_error:
                                    print(f"[BASLER_CAMERA] Could not release device: {release_error}")
                            
                            # Wait for resources to be freed
                            time.sleep(2.0)
                        except Exception as tl_error:
                            print(f"[BASLER_CAMERA] Transport layer operation failed: {tl_error}")
                    
                    # Connect to the first camera
                    self.camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
                    self.camera.Open()
                    break
                except Exception as create_error:
                    if attempt < max_retries - 1:
                        print(f"[BASLER_CAMERA] Failed to create camera instance (attempt {attempt+1}): {create_error}")
                        time.sleep(2.0)  # Wait before retry
                    else:
                        print(f"[BASLER_CAMERA] Failed to create camera after {max_retries} attempts: {create_error}")
                        self.is_connected_flag = False
                        return False
            
            # Optimize GigE settings to prevent "incomplete grab" errors
            try:
                # Check if this is a GigE camera
                if hasattr(self.camera.GetDeviceInfo(), "GetDeviceClass") and self.camera.GetDeviceInfo().GetDeviceClass() == "BaslerGigE":
                    print("[BASLER_CAMERA] GigE camera detected - applying optimized network settings")
                    
                    # Increase the number of buffers for grabbing to prevent buffer underruns
                    if hasattr(self.camera, "MaxNumBuffer"):
                        self.camera.MaxNumBuffer.SetValue(32)  # Use more buffers (default is often 10)
                        print(f"[BASLER_CAMERA] Set MaxNumBuffer to {self.camera.MaxNumBuffer.GetValue()}")
                        
                    # Set packet size to a good value for most networks
                    try:
                        if hasattr(self.camera, "GevSCPSPacketSize"):
                            self.camera.GevSCPSPacketSize.SetValue(8192)  # 8KB packets
                            print(f"[BASLER_CAMERA] Set GevSCPSPacketSize to {self.camera.GevSCPSPacketSize.GetValue()}")
                    except Exception as packet_error:
                        print(f"[BASLER_CAMERA] Could not set packet size: {packet_error}")
                        
                    # Increase the packet resend timeout
                    try:
                        if hasattr(self.camera, "GevSCPD"):
                            self.camera.GevSCPD.SetValue(5000)  # 5000 ticks
                            print(f"[BASLER_CAMERA] Set GevSCPD (packet delay) to {self.camera.GevSCPD.GetValue()}")
                    except Exception as delay_error:
                        print(f"[BASLER_CAMERA] Could not set packet delay: {delay_error}")
                        
                    # Increase frame timeout
                    try:
                        if hasattr(self.camera, "GrabTimeout"):
                            self.camera.GrabTimeout.SetValue(5000)  # 5000ms timeout
                            print(f"[BASLER_CAMERA] Set GrabTimeout to {self.camera.GrabTimeout.GetValue()}ms")
                    except Exception as timeout_error:
                        print(f"[BASLER_CAMERA] Could not set grab timeout: {timeout_error}")
                        
                    # Enable frame retention if available (keeps incomplete frames)
                    try:
                        if hasattr(self.camera, "GevSCFTD"):
                            self.camera.GevSCFTD.SetValue(True)
                            print("[BASLER_CAMERA] Enabled frame retention")
                    except Exception as retention_error:
                        print(f"[BASLER_CAMERA] Could not set frame retention: {retention_error}")
            except Exception as gige_error:
                print(f"[BASLER_CAMERA] Could not apply GigE optimizations: {gige_error}")
            
            # Configure camera settings
            try:
                self.camera.PixelFormat.SetValue("BayerRG8")  # Color image format
            except Exception as e:
                print(f"[BASLER_CAMERA] Warning: Could not set PixelFormat: {e}")
                
            # Set exposure time
            try:
                # Try different parameter names for exposure time that might exist
                if hasattr(self.camera, "ExposureTime"):
                    self.camera.ExposureTime.SetValue(self.exposure_time_us)
                    print(f"[BASLER_CAMERA] Set exposure time to {self.exposure_time_us} μs using ExposureTime")
                elif hasattr(self.camera, "ExposureTimeAbs"):
                    self.camera.ExposureTimeAbs.SetValue(self.exposure_time_us)
                    print(f"[BASLER_CAMERA] Set exposure time to {self.exposure_time_us} μs using ExposureTimeAbs")
                elif hasattr(self.camera, "ExposureTimeRaw"):
                    self.camera.ExposureTimeRaw.SetValue(self.exposure_time_us)
                    print(f"[BASLER_CAMERA] Set exposure time to {self.exposure_time_us} μs using ExposureTimeRaw")
                else:
                    print(f"[BASLER_CAMERA] Warning: Could not set exposure time - no compatible parameter found")
            except Exception as e:
                print(f"[BASLER_CAMERA] Warning: Could not set exposure time: {e}")
                # Continue connecting despite exposure setting failure
            
            # Configure chunks for timestamps
            try:
                self.camera.ChunkModeActive = True
                self.camera.ChunkSelector = "Timestamp"
                self.camera.ChunkEnable = True
            except Exception as chunk_error:
                print(f"[BASLER_CAMERA] Chunk mode configuration failed, timestamps may not be available: {chunk_error}")
            
            # Get camera info
            device_info = self.camera.GetDeviceInfo()
            print(f"[BASLER_CAMERA] Connected to: {device_info.GetFriendlyName()}")
            print(f"[BASLER_CAMERA] Model: {device_info.GetModelName()}")
            print(f"[BASLER_CAMERA] Serial: {device_info.GetSerialNumber()}")
            
            self.is_connected_flag = True
            
            # Start in snapshot mode by default
            self.set_mode("snapshot")
            
            # Start the event processing thread
            self.start_event_processing()
            
            return True
            
        except Exception as e:
            print(f"[BASLER_CAMERA] Error connecting to camera: {e}")
            traceback.print_exc()
            if self.camera is not None:
                try:
                    self.camera.Close()
                except:
                    pass
                self.camera = None
            self.is_connected_flag = False
            return False

    def _release_camera_resources(self):
        """Safely release all camera resources"""
        try:
            # Stop event processing
            self.stop_event_processing()
            
            # Stop recording if active
            if self.is_recording:
                self.stop_recording()
            
            # Stop grabbing if active
            if self.is_grabbing:
                self.stop_grabbing()
            
            if self.camera:
                try:
                    if self.camera.IsGrabbing():
                        print("[BASLER_CAMERA] Stopping camera grabbing")
                        self.camera.StopGrabbing()
                except Exception as grab_error:
                    print(f"[BASLER_CAMERA] Error stopping grabbing: {grab_error}")
                
                try:
                    if self.camera.IsOpen():
                        print("[BASLER_CAMERA] Closing camera")
                    self.camera.Close()
                except Exception as close_error:
                    print(f"[BASLER_CAMERA] Error closing camera: {close_error}")
                
                # Set to None to ensure garbage collection
                self.camera = None
                
                # Give the system time to release resources
                time.sleep(1.0)
                
                # Force garbage collection
                import gc
                gc.collect()
                
                print("[BASLER_CAMERA] Camera resources released")
        except Exception as e:
            print(f"[BASLER_CAMERA] Error releasing camera resources: {e}")
            
    def disconnect(self) -> bool:
        """
        Disconnect from the camera
        
        Returns:
            bool: True if disconnection successful, False otherwise
        """
        try:
            self._release_camera_resources()
            self.is_connected_flag = False
            return True
        except Exception as e:
            print(f"[BASLER_CAMERA] Error disconnecting from camera: {e}")
            traceback.print_exc()
            return False

    def is_connected(self) -> bool:
        """
        Check if camera is connected
        
        Returns:
            bool: True if connected, False otherwise
        """
        try:
            return self.camera is not None and self.camera.IsOpen()
        except Exception:
            return False

    def set_mode(self, mode: str) -> None:
        """
        Set camera mode
        
        Args:
            mode: Camera mode ("snapshot", "continuous", or "recording")
        """
        if mode not in ["snapshot", "continuous", "recording"]:
            raise ValueError("Mode must be 'snapshot', 'continuous', or 'recording'")
            
        # If we're already in this mode, do nothing
        if self.mode == mode:
            return
            
        # Stop current mode
        if self.is_grabbing:
            self.stop_grabbing()
        if self.is_recording:
            self.stop_recording()
            
        self.mode = mode
        print(f"[BASLER_CAMERA] Set mode to {mode}")
        
        # Start new mode
        if mode == "continuous" or mode == "recording":
            self.start_grabbing()
            
        if mode == "recording":
            self.start_recording()
            
    def get_frame(self) -> Dict[str, Any]:
        """Get the latest frame from the camera"""
        # First do a safety check
        if not self._check_camera_safety():
            print(f"[BASLER_CAMERA] Camera safety check failed: {self._last_error}")
            return None
        
        # For continuous or recording mode, always return the latest frame from buffer
        if (self.mode == "continuous" or self.mode == "recording") and self.latest_frame is not None:
            with self.lock:
                if self.latest_frame is not None:
                    return {
                        "image": self.latest_frame.copy(),
                        "timestamp": self.latest_frame_timestamp or time.time()
                    }
        
        # For snapshot mode or as fallback, grab a new frame
        # Use grab_lock to ensure only one thread grabs at a time
        try:
            # Start grabbing if needed
            if not self.camera.IsGrabbing():
                print("[BASLER_CAMERA] Auto-starting camera grabbing...")
                self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly if 
                                        (self.mode == "continuous" or self.mode == "recording") 
                                        else 1)
                time.sleep(0.1)  # Give camera time to start
            
            # Try up to 3 times to grab a frame
            for attempt in range(3):
                try:
                    # Grab with timeout - THIS IS THE CRITICAL SECTION CAUSING THREAD CONFLICTS
                    # Use the lock to ensure only one thread can grab at a time
                    grab_result = None
                    with self.grab_lock:  # Critical section lock
                        grab_timeout = 2000  # ms
                        grab_result = self.camera.RetrieveResult(grab_timeout, pylon.TimeoutHandling_Return)
                    
                    # Process result outside of lock
                    if grab_result and grab_result.GrabSucceeded():
                        # Reset error count
                        self._error_count = 0
                        
                        # Get image
                        image_rgb = self.converter.Convert(grab_result).GetArray()
                        
                        # Get timestamp if available
                        timestamp = int(time.time() * 1000000)  # Default to system time
                        try:
                            if self.camera.ChunkModeActive.GetValue():
                                timestamp = grab_result.ChunkTimestamp.GetValue()
                        except:
                            pass  # Use default timestamp
                        
                        # Release grab result
                        grab_result.Release()
                        
                        # Store frame for background thread to use
                        with self.lock:
                            self.latest_frame = image_rgb.copy()
                            self.latest_frame_timestamp = timestamp
                        
                        return {
                            "image": image_rgb,
                            "timestamp": timestamp
                        }
                    else:
                        # Handle grab failure
                        if grab_result:
                            error_msg = f"Grab failed: {grab_result.GetErrorDescription()}"
                            grab_result.Release()
                            self._last_error = error_msg
                        else:
                            self._last_error = "Grab result is None"
                        
                        self._error_count += 1
                        print(f"[BASLER_CAMERA] {self._last_error}")
                        
                        # Check for incomplete grab error
                        if "incompletely grabbed" in self._last_error:
                            time.sleep(0.5)  # Wait longer before retry
                        else:
                            time.sleep(0.1)
                            
                except Exception as e:
                    self._error_count += 1
                    self._last_error = str(e)
                    print(f"[BASLER_CAMERA] Exception during grab attempt {attempt+1}: {e}")
                    time.sleep(0.2)
            
            # All attempts failed, try to use latest frame as fallback
            with self.lock:
                if self.latest_frame is not None:
                    print("[BASLER_CAMERA] Using latest frame as fallback")
                    return {
                        "image": self.latest_frame.copy(),
                        "timestamp": self.latest_frame_timestamp or time.time()
                    }
            
            print("[BASLER_CAMERA] Failed to grab image, returning None")
            return None
            
        except Exception as e:
            self._error_count += 1
            print(f"[BASLER_CAMERA] Exception in get_frame: {e}")
            traceback.print_exc()
            self._last_error = str(e)
            return None

    def _check_camera_safety(self) -> bool:
        """Verify camera is connected and in a safe state to use"""
        if not self.camera:
            self._last_error = "Camera not initialized"
            return False
            
        if not self.camera.IsOpen():
            self._last_error = "Camera is not open"
            return False
            
        if self._error_count >= self._max_errors:
            # Too many consecutive errors, try to recover
            print("[BASLER_CAMERA] Too many camera errors, attempting recovery...")
            self._error_count = 0
            try:
                if self.camera.IsGrabbing():
                    self.camera.StopGrabbing()
                self.camera.Close()
                time.sleep(0.5)
                self.camera.Open()
                if self.mode == 'continuous' or self.mode == 'recording':
                    self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
                else:
                    self.camera.StartGrabbing(1)
                print("[BASLER_CAMERA] Camera recovery successful")
                return True
            except Exception as e:
                print(f"[BASLER_CAMERA] Camera recovery failed: {e}")
                self._last_error = f"Recovery failed: {str(e)}"
                return False
                
        return True
            
    def write_frame(self, save_path: str = None) -> str:
        """
        Write the current frame to disk
        
        Args:
            save_path: Path to save the frame
            
        Returns:
            str: Path to the saved file or error message
        """
        frame = self.get_frame()
        if not frame or frame["image"] is None:
            return "No frame available"
            
        try:
            # Use provided path or default
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S%f")[:-3]
            file_name = f"{timestamp}.jpg"
            path = save_path or self.save_directory
            os.makedirs(path, exist_ok=True)
            full_path = os.path.join(path, file_name)
            
            # Save image (convert from RGB to BGR for OpenCV)
            img_bgr = cv2.cvtColor(frame["image"], cv2.COLOR_RGB2BGR)
            cv2.imwrite(full_path, img_bgr)
            
            self.save_path = full_path
            self.save_message = "保存しました"  # "Saved" in Japanese
            
            return full_path
        except Exception as e:
            error_msg = f"Error saving frame: {str(e)}"
            print(f"[BASLER_CAMERA] {error_msg}")
            return error_msg
            
    def set_ai_threshold(self, threshold: int) -> None:
        """
        Set the AI threshold for detection confidence
        
        Args:
            threshold: Threshold value (10-100)
        """
        # Validate threshold range
        if threshold < 10 or threshold > 100:
            print(f"[BASLER_CAMERA] Invalid AI threshold: {threshold}. Must be between 10 and 100. Using 50 as default.")
            threshold = 50
            
        self.ai_threshold = threshold
        print(f"[BASLER_CAMERA] Set AI threshold to {self.ai_threshold}%")
        
        # Convert from percentage to float (0.0-1.0) for the inference service
        inference_threshold = threshold / 100.0
        self.inference_service.update_threshold(inference_threshold)
        print(f"[BASLER_CAMERA] Updated inference service threshold to {inference_threshold}")

    def set_params(self, params: dict) -> None:
        """
        Set camera parameters
        
        Args:
            params: Dictionary of parameters
        """
        try:
            # AI threshold setting
            if "AIThreshold" in params:
                self.set_ai_threshold(int(params["AIThreshold"]))
                
            # Camera hardware settings
            if "ExposureTime" in params and self.camera is not None and self.is_connected_flag:
                self.exposure_time_us = int(params["ExposureTime"])
                try:
                    # Try different parameter names for exposure time
                    if hasattr(self.camera, "ExposureTime"):
                        self.camera.ExposureTime.SetValue(self.exposure_time_us)
                    elif hasattr(self.camera, "ExposureTimeAbs"):
                        self.camera.ExposureTimeAbs.SetValue(self.exposure_time_us)
                    elif hasattr(self.camera, "ExposureTimeRaw"):
                        self.camera.ExposureTimeRaw.SetValue(self.exposure_time_us)
                    else:
                        print(f"[BASLER_CAMERA] Warning: Could not set exposure time - no compatible parameter found")
                    print(f"[BASLER_CAMERA] Set exposure time to {self.exposure_time_us} μs")
                except Exception as e:
                    print(f"[BASLER_CAMERA] Warning: Could not set exposure time: {e}")
                
            # Frame rate settings
            if "fps" in params:
                fps = float(params["fps"])
                if self.camera is not None and self.is_connected_flag:
                    try:
                        self.camera.AcquisitionFrameRateEnable.SetValue(True)
                        self.camera.AcquisitionFrameRate.SetValue(fps)
                        print(f"[BASLER_CAMERA] Set acquisition frame rate to {fps} fps")
                    except Exception as e:
                        print(f"[BASLER_CAMERA] Error setting frame rate: {e}")
                
                # Update buffer fps
                self.buffer_fps = fps
                self.buffer_size = int(self.max_buffer_seconds * self.buffer_fps)
                self.buffer = deque(maxlen=self.buffer_size)
                print(f"[BASLER_CAMERA] Set buffer fps to {self.buffer_fps}")
                
            # Buffer settings
            if "MaxSeconds" in params:
                self.max_buffer_seconds = int(params["MaxSeconds"])
                self.buffer_size = int(self.max_buffer_seconds * self.buffer_fps)
                self.buffer = deque(maxlen=self.buffer_size)
                print(f"[BASLER_CAMERA] Set buffer size to {self.buffer_size} frames ({self.max_buffer_seconds} seconds)")
                
            # Save directory
            if "SaveDirectory" in params:
                self.save_directory = params["SaveDirectory"]
                os.makedirs(self.save_directory, exist_ok=True)
                print(f"[BASLER_CAMERA] Set save directory to {self.save_directory}")
                
        except Exception as e:
            print(f"[BASLER_CAMERA] Error setting parameters: {e}")
            
    def start_grabbing(self) -> bool:
        """
        Start continuously grabbing frames from the camera
        
        Returns:
            bool: True if grabbing started successfully, False otherwise
        """
        if not self.is_connected_flag or self.camera is None:
            print("[BASLER_CAMERA] Error: Not connected to camera")
            return False
            
        if self.is_grabbing:
            print("[BASLER_CAMERA] Already grabbing frames")
            return True
            
        try:
            # Check if camera is already grabbing
            if self.camera.IsGrabbing():
                print("[BASLER_CAMERA] Camera is already grabbing, no need to start again")
                self.is_grabbing = True
                self.stop_event.clear()
                
                # Start grab thread if not already running
                if self.grab_thread is None or not self.grab_thread.is_alive():
                    self.grab_thread = threading.Thread(target=self._grab_loop, daemon=True)
                    self.grab_thread.start()
                
                print("[BASLER_CAMERA] Started monitoring existing grab")
                return True
            
            # Start grabbing
            self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
            self.is_grabbing = True
            self.stop_event.clear()
            
            # Start grab thread
            self.grab_thread = threading.Thread(target=self._grab_loop, daemon=True)
            self.grab_thread.start()
            
            print("[BASLER_CAMERA] Started grabbing frames")
            return True
            
        except Exception as e:
            print(f"[BASLER_CAMERA] Error starting grabbing: {e}")
            return False
            
    def stop_grabbing(self) -> bool:
        """
        Stop grabbing frames from the camera
        
        Returns:
            bool: True if grabbing stopped successfully, False otherwise
        """
        if not self.is_grabbing:
            return True
            
        try:
            # Signal thread to stop
            self.stop_event.set()
            
            # Wait for thread to stop
            if self.grab_thread is not None and self.grab_thread.is_alive():
                self.grab_thread.join(timeout=2.0)
                
            # Stop grabbing
            if self.camera is not None and self.camera.IsGrabbing():
                self.camera.StopGrabbing()
                
            self.is_grabbing = False
            print("[BASLER_CAMERA] Stopped grabbing frames")
            return True
            
        except Exception as e:
            print(f"[BASLER_CAMERA] Error stopping grabbing: {e}")
            return False
            
    def start_recording(self) -> bool:
        """
        Start recording images to buffer
        
        Args:
            bool: True if recording started successfully, False otherwise
        """
        if not self.is_connected_flag:
            print("[BASLER_CAMERA] Cannot start recording - camera not connected")
            return False
            
        # Make sure grabbing is active
        if not self.is_grabbing:
            print("[BASLER_CAMERA] Starting grabbing for recording")
            if not self.start_grabbing():
                print("[BASLER_CAMERA] Failed to start grabbing, recording will not work properly")
                # Continue anyway to avoid breaking the workflow
        else:
            print("[BASLER_CAMERA] Grabbing already active, using existing grab session")
        
        # If already recording, just return success
        if self.is_recording:
            print("[BASLER_CAMERA] Already recording, no need to start again")
            return True
        
        # Set camera frame rate to ensure exact capture rate (10fps)
        try:
            # Set acquisition frame rate to 10fps
            if self.camera:
                self.camera.AcquisitionFrameRateEnable.SetValue(True)
                self.camera.AcquisitionFrameRate.SetValue(self.buffer_fps)
                print(f"[BASLER_CAMERA] Set camera acquisition frame rate to {self.buffer_fps} fps")
        except Exception as e:
            print(f"[BASLER_CAMERA] Warning: Could not set camera frame rate: {e}")
        
        # Reset the buffer before starting recording    
        print(f"[BASLER_CAMERA] Initializing buffer with capacity: {self.buffer_size} frames")
        self.buffer = deque(maxlen=self.buffer_size)
        self.buffer.clear()  # Clear any existing items (shouldn't be needed, but just to be safe)
        print(f"[BASLER_CAMERA] Buffer initialized and cleared - capacity: {self.buffer.maxlen} frames")
        print(f"[BASLER_CAMERA] 🔴 Fresh recording started - buffer completely cleared for new capture sequence")
        
        # Set recording flag - this is critical for the _grab_loop to start adding frames
        self.is_recording = True
        self.status = "録画中"  # "Recording" in Japanese
        self.save_message = ""
        
        # Grab an initial frame to add to the buffer - important for the 撮影する condition
        print("[BASLER_CAMERA] 撮影する condition detected - Capturing initial frame for buffer")
        try:
            # Capture multiple initial frames to ensure we have something in the buffer
            for i in range(3):  # Try to get 3 initial frames
                frame = self.get_frame()
                if frame and 'image' in frame:
                    current_time = time.time()
                    self.buffer.append({
                        "image": frame['image'].copy(),
                        "timestamp": current_time
                    })
                    print(f"[BASLER_CAMERA] Added initial frame {i+1} to buffer, buffer size now: {len(self.buffer)}")
                else:
                    print(f"[BASLER_CAMERA] Could not capture initial frame {i+1}")
                time.sleep(0.1)  # Small delay between captures
                
            # Check if we captured any frames
            if len(self.buffer) == 0:
                print("[BASLER_CAMERA] WARNING: Could not capture any initial frames, buffer remains empty")
        except Exception as e:
            print(f"[BASLER_CAMERA] Error capturing initial frames: {e}")
        
        print("[BASLER_CAMERA] Started recording to buffer")
        return True
        
    def stop_recording(self) -> bool:
        """
        Stop recording images to buffer
        
        Returns:
            bool: True if recording stopped successfully, False otherwise
        """
        if not self.is_recording:
            return True
            
        self.is_recording = False
        self.status = "待機中"  # "Standby" in Japanese
        
        print("[BASLER_CAMERA] Stopped recording to buffer")
        return True
        
    def _analyze_image(self, image_path: str, shared_inspection_id: int = None) -> Dict[str, Any]:
        """
        Analyze an image using the inference service and save results to database
        
        Args:
            image_path: Path to the image file
            shared_inspection_id: Optional inspection ID to use for all images in a batch
            
        Returns:
            Dict[str, Any]: Analysis results with database IDs
        """
        try:
            # Run inference on the image
            inference_results = self.inference_service.predict_image(image_path)
            
            if not inference_results.get("success", False):
                print(f"[BASLER_CAMERA] Inference failed: {inference_results.get('error', 'Unknown error')}")
                return None
                
            # Extract detection results
            detections = inference_results["results"]["detections"]
            
            # Check if any detection has confidence above threshold (percentage converted to decimal)
            threshold_as_decimal = self.ai_threshold / 100.0
            confidence_above_threshold = False
            filtered_detections = []
            
            # Filter detections based on threshold
            for detection in detections:
                confidence = detection["confidence"]
                if confidence >= threshold_as_decimal:
                    filtered_detections.append(detection)
                    confidence_above_threshold = True
                    print(f"[BASLER_CAMERA] Detection above threshold: class={detection['class_name']}, confidence={confidence:.3f}, threshold={threshold_as_decimal:.3f}")
                else:
                    print(f"[BASLER_CAMERA] Detection below threshold: class={detection['class_name']}, confidence={confidence:.3f}, threshold={threshold_as_decimal:.3f}")
            
            # If no detections above threshold, log and return
            if not confidence_above_threshold:
                print(f"[BASLER_CAMERA] No detections with confidence above threshold ({self.ai_threshold}%), skipping database save")
                # Could return early here, but we'll still create database entries but mark status as False
            
            # Create a database session
            with SessionLocal() as session:
                # If shared_inspection_id is provided, use it instead of creating a new inspection
                if shared_inspection_id:
                    # Get the existing inspection from the database
                    inspection = session.query(Inspection).get(shared_inspection_id)
                    if inspection:
                        print(f"[BASLER_CAMERA] Using shared inspection ID: {shared_inspection_id}")
                        
                        # Update inspection status if this image has confidence above threshold
                        if confidence_above_threshold and not inspection.status:
                            inspection.status = True
                            print(f"[BASLER_CAMERA] Updated inspection {inspection.inspection_id} status to {inspection.status}")
                            session.flush()
                    else:
                        print(f"[BASLER_CAMERA] Warning: Shared inspection ID {shared_inspection_id} not found, creating new inspection")
                        # Create a new inspection since shared one doesn't exist
                        inspection = Inspection(
                            ai_threshold=self.ai_threshold,
                            inspection_dt=datetime.now(),
                            file_path=os.path.dirname(image_path),
                            status=confidence_above_threshold,
                            results='無欠点'  # Default to no defects
                        )
                        session.add(inspection)
                        session.flush()  # Get the inspection_id
                else:
                    # Create a new inspection record
                    inspection = Inspection(
                        ai_threshold=self.ai_threshold,  # Use the stored AI threshold value
                        inspection_dt=datetime.now(),
                        file_path=os.path.dirname(image_path),  # Use parent folder path instead of image path
                        status=confidence_above_threshold,  # Only mark as active if confidence above threshold
                        results='無欠点'  # Default to no defects
                    )
                    
                    # Add inspection to database
                    session.add(inspection)
                    session.flush()  # Get the inspection_id
                
                # Check if we need to create inspection result
                # Only create if this is a new inspection or we're adding a new one
                if not shared_inspection_id or not session.query(InspectionResult).filter(InspectionResult.inspection_id == inspection.inspection_id).first():
                    # Create inspection result record
                    inspection_result = InspectionResult(
                        inspection_id=inspection.inspection_id,
                        discoloration=False,
                        hole=False,
                        knot=False,
                        dead_knot=False,
                        live_knot=False,
                        tight_knot=False
                    )
                    
                    # Japanese class names mapping
                    japanese_class_names = {
                        0: '変色',      # discoloration  
                        1: '穴',        # hole
                        2: '死に節',     # knot_dead
                        3: '流れ節(死)', # flow_dead
                        4: '流れ節(生)', # flow_live
                        5: '生き節',     # knot_live
                    }
                    
                    # Add inspection result to database
                    session.add(inspection_result)
                else:
                    # Get existing inspection result
                    inspection_result = session.query(InspectionResult).filter(InspectionResult.inspection_id == inspection.inspection_id).first()
                
                # Update flags based on detections for this image
                if len(filtered_detections) > 0:
                    # Japanese class names mapping
                    japanese_class_names = {
                        0: '変色',      # discoloration  
                        1: '穴',        # hole
                        2: '死に節',     # knot_dead
                        3: '流れ節(死)', # flow_dead
                        4: '流れ節(生)', # flow_live
                        5: '生き節',     # knot_live
                    }
                    
                    # Update inspection result based on detection class
                    for detection in filtered_detections:
                        class_id = detection["class_id"]
                        if class_id == 0:  # discoloration
                            inspection_result.discoloration = True
                        elif class_id == 1:  # hole
                            inspection_result.hole = True
                        elif class_id == 2:  # knot_dead
                            inspection_result.dead_knot = True
                        elif class_id == 3:  # flow_dead
                            inspection_result.dead_knot = True
                        elif class_id == 4:  # flow_live
                            inspection_result.live_knot = True
                        elif class_id == 5:  # knot_live
                            inspection_result.tight_knot = True
                            
                    # Set generic knot flag if any knot type is detected
                    if (inspection_result.dead_knot or inspection_result.live_knot or
                            inspection_result.tight_knot):
                        inspection_result.knot = True
                
                # Add inspection result to database
                session.add(inspection_result)
                
                # Save detailed inspection details for each detection
                all_detail_lengths = []
                for detection in filtered_detections:
                    class_id = detection["class_id"]
                    confidence = detection["confidence"]
                    bbox = detection["bbox"]  # [x, y, width, height]
                    
                    # Calculate length as the maximum of width and height, divided by 100 to match condition
                    length = max(bbox[2], bbox[3]) / 100
                    all_detail_lengths.append(length)
                    
                    # Extract image number from filename
                    image_no = None
                    try:
                        basename = os.path.basename(image_path)
                        match = re.search(r'No_(\d{4})\.(bmp|jpg|png)', basename)
                        if match:
                            image_no = int(match.group(1))
                    except Exception as e:
                        print(f"[BASLER_CAMERA] Error extracting image number from {image_path}: {e}")

                    # Create inspection detail record
                    inspection_detail = InspectionDetails(
                        inspection_id=inspection.inspection_id,
                        error_type=class_id,
                        error_type_name=japanese_class_names.get(class_id, f"Unknown class {class_id}"),
                        x_position=bbox[0],
                        y_position=bbox[1],
                        width=bbox[2],
                        height=bbox[3],
                        length=length,  # Add the length field
                        confidence=confidence,
                        image_path=image_path,  # Store the path to the error image
                        image_no=image_no  # Store the image number
                    )
                    
                    # Add inspection detail to database
                    session.add(inspection_detail)
                
                # Update the inspection_result length field based on the length of all details
                if all_detail_lengths and inspection_result:
                    # Calculate the total length from all details
                    total_length = sum(all_detail_lengths)
                    # Update the inspection_result length
                    inspection_result.length = int(total_length * 100)  # Convert back to the original scale (mm)
                    session.add(inspection_result)
                    print(f"[BASLER_CAMERA] Updated inspection_result length to {inspection_result.length} mm based on {len(all_detail_lengths)} details")
                
                # Commit transaction
                session.commit()
                
                if confidence_above_threshold:
                    print(f"[BASLER_CAMERA] Image analyzed and results saved to database: {inspection.inspection_id}")
                    print(f"[BASLER_CAMERA] Saved {len(filtered_detections)} inspection details with positions and types")
                else:
                    print(f"[BASLER_CAMERA] Image analyzed but no detections above threshold ({self.ai_threshold}%)")
                    print(f"[BASLER_CAMERA] Created inspection record {inspection.inspection_id} with status=False")
                
                # Return analysis results with database IDs for reference
                return {
                    "inspection_id": inspection.inspection_id,
                    "inference_results": inference_results,
                    "detections": filtered_detections,
                    "confidence_above_threshold": confidence_above_threshold,
                    "ai_threshold": self.ai_threshold,
                    # Include detailed inspection data for frontend to use
                    "inspection_details": [
                        {
                            "id": detail.error_id,
                            "error_type": detail.error_type,
                            "error_type_name": detail.error_type_name,
                            "x_position": detail.x_position,
                            "y_position": detail.y_position,
                            "width": detail.width,
                            "height": detail.height,
                            "length": detail.length,
                            "confidence": detail.confidence,
                            "image_path": detail.image_path,
                            "image_no": detail.image_no
                        }
                        for detail in session.query(InspectionDetails).filter(InspectionDetails.inspection_id == inspection.inspection_id).all()
                    ]
                }
                
        except Exception as e:
            print(f"[BASLER_CAMERA] Error analyzing image: {e}")
            traceback.print_exc()
            return None

    def _grab_loop(self):
        """Background thread for continuously grabbing frames"""
        print("[BASLER_CAMERA] Grab loop started")
        last_buffer_report_time = time.time()
        frames_captured = 0
        consecutive_errors = 0
        max_consecutive_errors = 5
        recovery_attempts = 0
        max_recovery_attempts = 3
        
        # Main loop - runs until stop_event is set
        while not self.stop_event.is_set():
            try:
                # Check if camera is grabbing
                if not self.camera.IsGrabbing():
                    print("[BASLER_CAMERA] Camera not grabbing, restarting...")
                    try:
                        with self.grab_lock:
                            self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
                        time.sleep(0.2)
                    except Exception as e:
                        print(f"[BASLER_CAMERA] Error starting grabbing: {e}")
                        time.sleep(1.0)
                        continue
                
                # Try to grab a frame
                try:
                    grab_timeout = 500  # ms
                    # Use the grab_lock to prevent thread conflicts
                    with self.grab_lock:
                            grab_result = self.camera.RetrieveResult(grab_timeout, pylon.TimeoutHandling_Return)
                    
                    # Process outside the lock to minimize lock time
                    if grab_result and grab_result.GrabSucceeded():
                        # Reset error counters on success
                            consecutive_errors = 0
                            recovery_attempts = 0 
                            # Get timestamp
                            timestamp = int(time.time() * 1000000)  # Default to system time
                            try:
                                if self.camera.ChunkModeActive.GetValue():
                                    timestamp = grab_result.ChunkTimestamp.GetValue()
                            except:
                                pass  # Keep default timestamp
                            
                            # Convert to RGB image
                            image_rgb = self.converter.Convert(grab_result).GetArray()
                            
                            # Apply image enhancements
                            alpha = 1.1  # Contrast
                            beta = 5     # Brightness
                            image_enhanced = cv2.convertScaleAbs(image_rgb, alpha=alpha, beta=beta)
                            
                            # Store the frame
                            with self.lock:
                                self.latest_frame = image_enhanced
                                self.latest_frame_timestamp = timestamp
                            
                            # Add to buffer if in recording mode
                            if self.is_recording:
                                try:
                                    buffer_size_before = len(self.buffer)
                                    self.buffer.append({
                                        "image": image_enhanced.copy(),
                                        "timestamp": time.time()
                                    })
                                    
                                    buffer_size_after = len(self.buffer)
                                    frames_captured += 1
                                    
                                    # Periodically report buffer status
                                    now = time.time()
                                    if now - last_buffer_report_time >= 5.0 or buffer_size_before == 0:
                                        print(f"[BASLER_CAMERA] Buffer: {buffer_size_after}/{self.buffer_size} frames")
                                        last_buffer_report_time = now
                                    
                                    # Log first frame added
                                    if buffer_size_before == 0 and buffer_size_after > 0:
                                        print(f"[BASLER_CAMERA] First frame added to buffer")
                                        
                                except Exception as buffer_error:
                                    print(f"[BASLER_CAMERA] Error adding to buffer: {buffer_error}")
                            
                            # Release the grab result
                            grab_result.Release()
                            
                    else:
                            # Handle grab failure
                            error_msg = "Unknown grab error"
                            if grab_result:
                                error_msg = f"Grab failed: {grab_result.GetErrorDescription()}"
                                grab_result.Release()
                            
                            consecutive_errors += 1
                            print(f"[BASLER_CAMERA] {error_msg} (errors: {consecutive_errors}/{max_consecutive_errors})")
                            
                            # Short sleep to avoid busy waiting
                            time.sleep(0.1)
                            
                except pylon.TimeoutException:
                    # Just a timeout, not an error
                    pass
                    
                except Exception as grab_error:
                    consecutive_errors += 1
                    print(f"[BASLER_CAMERA] Error in grab: {grab_error}")
                    time.sleep(0.1)
                
                # Check if we need recovery due to errors
                if consecutive_errors >= max_consecutive_errors:
                    if recovery_attempts < max_recovery_attempts:
                        print(f"[BASLER_CAMERA] Too many errors, attempting recovery {recovery_attempts+1}/{max_recovery_attempts}")
                        recovery_attempts += 1
                        consecutive_errors = 0
                        
                        try:
                            # Try to recover the camera
                            with self.grab_lock:
                                if self.camera.IsGrabbing():
                                    self.camera.StopGrabbing()
                                time.sleep(0.5)
                                
                                if not self.camera.IsOpen():
                                    print("[BASLER_CAMERA] Camera disconnected, reopening...")
                                    self.camera.Open()
                                    time.sleep(1.0)
                                
                                # Restart grabbing
                                print("[BASLER_CAMERA] Restarting camera grabbing")
                                self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
                                time.sleep(0.5)
                            
                            print("[BASLER_CAMERA] Camera recovery completed")
                        
                        except Exception as recovery_error:
                            print(f"[BASLER_CAMERA] Error during recovery: {recovery_error}")
                    
                    else:
                        print(f"[BASLER_CAMERA] Maximum recovery attempts ({max_recovery_attempts}) reached")
                        # Reset counters to prevent constant recovery attempts
                        consecutive_errors = 0
                        recovery_attempts = 0
            
            except Exception as loop_error:
                print(f"[BASLER_CAMERA] Error in grab loop: {loop_error}")
                traceback.print_exc()
                time.sleep(0.5)
        
        print("[BASLER_CAMERA] Grab loop stopped")

    def save_buffer_images(self, output_dir=None, prefix="frame", filter_start_time=None, filter_end_time=None) -> List[str]:
        """
        Save all buffered images to directory and analyze them with inference
        
        Args:
            output_dir: Directory to save images to
            prefix: Prefix for image filenames
            filter_start_time: If provided, only save images captured after this timestamp
            filter_end_time: If provided, only save images captured before this timestamp
            
        Returns:
            List[str]: List of saved file paths
        """
        print(f"[BASLER_CAMERA] 保存する condition detected - save_buffer_images called with output_dir={output_dir}, buffer size={len(self.buffer)}")
        print(f"[BASLER_CAMERA] Filter start time: {filter_start_time}, Filter end time: {filter_end_time}")
        
        # Create output directory if needed
        if not output_dir:
            output_dir = self._make_timestamp_dir(self.save_directory)
            print(f"[BASLER_CAMERA] Created directory: {output_dir}")
            
        # First set save path so frontend can show it
        self.save_path = os.path.abspath(output_dir)
        self.save_message = "処理中..." # "Processing..." in Japanese
        
        # Check if buffer is empty
        if len(self.buffer) == 0:
            print("[BASLER_CAMERA] Buffer is empty, attempting to capture current frame")
            try:
                # Try to capture at least one frame
                frame = self.get_frame()
                if frame and 'image' in frame:
                    # Add to buffer
                    current_time = time.time()
                    self.buffer.append({
                        "image": frame['image'].copy(),
                        "timestamp": current_time
                    })
                    print(f"[BASLER_CAMERA] Added current frame to buffer with timestamp {current_time}")
                    
                    # Try to get a few more frames if possible
                    for i in range(5):  # Increased from 2 to 5 frames
                        time.sleep(0.1)  # Small delay between captures
                        try:
                            frame = self.get_frame()
                            if frame and 'image' in frame:
                                current_time = time.time()
                                self.buffer.append({
                                    "image": frame['image'].copy(),
                                    "timestamp": current_time
                                })
                                print(f"[BASLER_CAMERA] Added additional frame {i+1} to buffer with timestamp {current_time}")
                        except Exception as e:
                            print(f"[BASLER_CAMERA] Error capturing additional frame: {e}")
                else:
                    print("[BASLER_CAMERA] Failed to capture current frame")
            except Exception as e:
                print(f"[BASLER_CAMERA] Error capturing frame: {e}")
                traceback.print_exc()
                
            # Check buffer again after capture attempt
            if len(self.buffer) == 0:
                print("[BASLER_CAMERA] Buffer is still empty after capture attempt, nothing to save")
                self.save_message = "保存失敗 (0枚)"  # "Save failed" in Japanese
                return []
        
        # Extract frames from buffer based on filter criteria
        buffer_snapshot = self._extract_frames_from_buffer(filter_start_time, filter_end_time)
        
        # Check if we got any frames
        if len(buffer_snapshot) == 0:
            print("[BASLER_CAMERA] No frames extracted from buffer")
            self.save_message = "保存失敗 (0枚)"  # "Save failed" in Japanese
            return []
            
        # Start event processing thread if not already started
        if not self.event_processing_active:
            self.start_event_processing()
            
        # Create event data for the queue
        event_data = {
            'event_type': 'save',
            'output_dir': output_dir,
            'buffer_snapshot': buffer_snapshot.copy(),  # Make a copy to avoid thread issues
            'filter_start_time': filter_start_time,
            'filter_end_time': filter_end_time,
            'timestamp': time.time()
        }
        
        # Add to queue for background processing
        self.event_queue.put(event_data)
        print(f"[BASLER_CAMERA] Added save event to queue with {len(buffer_snapshot)} frames")
        
        # Update UI status - actual processing happens in background
        self.save_message = f"処理中... ({len(buffer_snapshot)}枚)"  # "Processing..." in Japanese
        
        # Return the output directory so the caller knows where to look for files
        return [output_dir]
        
    def _extract_frames_from_buffer(self, filter_start_time=None, filter_end_time=None):
        """Extract frames from buffer based on filter criteria"""
        buffer_snapshot = []
        has_timestamps = False
        
        # First determine if we have frames with timestamps
        for item in self.buffer:
            if isinstance(item, dict) and "timestamp" in item:
                has_timestamps = True
                break
        
        # Time-based filtering - only save images from the specific detection sequence
        if has_timestamps:
            filtered_frames = []
            
            if filter_start_time and filter_end_time:
                print(f"[BASLER_CAMERA] 🔍 Filtering buffer for images between {filter_start_time} and {filter_end_time}")
                # Filter frames within the time window of the specific pass_L_to_R event
                for item in self.buffer:
                    if (isinstance(item, dict) and "timestamp" in item and 
                        item["timestamp"] >= filter_start_time and 
                        item["timestamp"] <= filter_end_time):
                        filtered_frames.append(item)
                print(f"[BASLER_CAMERA] 🔍 Filtered buffer from {len(self.buffer)} to {len(filtered_frames)} frames")
                print(f"[BASLER_CAMERA] 🔍 Sequence duration: {filter_end_time - filter_start_time:.2f}s")
            elif filter_start_time:
                print(f"[BASLER_CAMERA] 🔍 Filtering buffer for images after {filter_start_time}")
                # Just filter by start time if no end time provided
                for item in self.buffer:
                    if isinstance(item, dict) and "timestamp" in item and item["timestamp"] >= filter_start_time:
                        filtered_frames.append(item)
                print(f"[BASLER_CAMERA] 🔍 Filtered buffer from {len(self.buffer)} to {len(filtered_frames)} frames")
            else:
                # No filtering needed
                print(f"[BASLER_CAMERA] 🔍 No time filtering requested")
                for item in self.buffer:
                    if isinstance(item, dict) and "timestamp" in item:
                        filtered_frames.append(item)
            
            # Step 2: Resample frames to ensure exactly 0.1s intervals
            if len(filtered_frames) > 0:
                # Sort frames by timestamp to ensure proper order
                filtered_frames.sort(key=lambda x: x["timestamp"])
                
                # Calculate start and end time
                actual_start_time = filtered_frames[0]["timestamp"]
                actual_end_time = filtered_frames[-1]["timestamp"]
                duration = actual_end_time - actual_start_time
                
                # Calculate ideal number of frames at 10fps
                target_interval = 1.0 / self.buffer_fps  # 0.1s at 10fps
                ideal_frame_count = int(duration / target_interval) + 1
                
                print(f"[BASLER_CAMERA] 🔍 Sequence duration: {duration:.3f}s")
                print(f"[BASLER_CAMERA] 🔍 Target interval: {target_interval:.3f}s")
                print(f"[BASLER_CAMERA] 🔍 Ideal frame count at {self.buffer_fps}fps: {ideal_frame_count}")
                
                # If we have more frames than needed, perform resampling
                if len(filtered_frames) > ideal_frame_count and ideal_frame_count > 0:
                    print(f"[BASLER_CAMERA] 🔍 Resampling frames to ensure exact {target_interval:.3f}s intervals")
                    
                    # Select frames at exact intervals
                    for i in range(ideal_frame_count):
                        # Calculate target timestamp for this frame
                        target_time = actual_start_time + (i * target_interval)
                        
                        # Find closest frame to this timestamp
                        closest_frame = min(filtered_frames, key=lambda x: abs(x["timestamp"] - target_time))
                        buffer_snapshot.append(closest_frame["image"])
                        
                    print(f"[BASLER_CAMERA] 🔍 Resampled to {len(buffer_snapshot)} frames at {target_interval:.3f}s intervals")
                else:
                    # Just extract images from filtered frames
                    buffer_snapshot = [item["image"] for item in filtered_frames]
                    print(f"[BASLER_CAMERA] 🔍 Using all {len(buffer_snapshot)} filtered frames")
            else:
                print(f"[BASLER_CAMERA] ⚠️ No frames found in filter time range")
        else:
            # Old format buffer without timestamps - estimate filtering
            print(f"[BASLER_CAMERA] ⚠️ Buffer contains old format frames without timestamps, using estimation")
            buffer_items = list(self.buffer)
            if len(buffer_items) > 0 and isinstance(buffer_items[0], np.ndarray):  # Old format - direct images
                # Estimate how many frames to keep based on time since filter_start_time
                if filter_start_time:
                    duration = time.time() - filter_start_time
                    buffer_frames = int(duration * self.buffer_fps)
                    
                    if buffer_frames > 0 and buffer_frames < len(buffer_items):
                        # Take exact number of frames to match 10fps
                        buffer_snapshot = buffer_items[-buffer_frames:]
                        print(f"[BASLER_CAMERA] Estimated {buffer_frames} frames since {filter_start_time}, resampling")
                    else:
                        buffer_snapshot = buffer_items
                        print(f"[BASLER_CAMERA] Using all frames as estimate exceeds buffer size")
                else:
                    buffer_snapshot = buffer_items
                    print(f"[BASLER_CAMERA] No time filter provided, using all frames")
            else:
                print(f"[BASLER_CAMERA] ⚠️ Unknown buffer format, using all frames")
                # Try to extract images from any format
                for item in buffer_items:
                    if isinstance(item, np.ndarray):
                        buffer_snapshot.append(item)
                    elif isinstance(item, dict) and "image" in item and isinstance(item["image"], np.ndarray):
                        buffer_snapshot.append(item["image"])
                
                print(f"[BASLER_CAMERA] Extracted {len(buffer_snapshot)} images from buffer")
                
        # EMERGENCY: If no frames were found in the filtered buffer but we have frames in the original buffer,
        # use all original buffer frames
        if len(buffer_snapshot) == 0 and len(self.buffer) > 0:
            print("[BASLER_CAMERA] ⚠️ EMERGENCY: No frames in filtered buffer but original buffer has frames")
            buffer_items = list(self.buffer)
            # Try to extract images from any format
            for item in buffer_items:
                if isinstance(item, np.ndarray):
                    buffer_snapshot.append(item)
                elif isinstance(item, dict) and "image" in item and isinstance(item["image"], np.ndarray):
                    buffer_snapshot.append(item["image"])
            print(f"[BASLER_CAMERA] Emergency buffer extraction: {len(buffer_snapshot)} frames")
            
        return buffer_snapshot

    def _create_timing_report_summary(self, output_dir, filter_start_time=None, filter_end_time=None, frame_count=0) -> str:
        """Create a timing report summary text file"""
        try:
            report_path = os.path.join(output_dir, "capture_timing_summary.txt")
            with open(report_path, "w") as f:
                now = datetime.now()
                f.write("CAPTURE TIMING REPORT\n")
                f.write("===================\n\n")
                f.write(f"Generated: {now.isoformat()}\n")
                f.write(f"Camera: BaslerCamera\n")
                f.write(f"FPS Setting: {self.buffer_fps} (interval: {1.0/self.buffer_fps:.3f}s)\n")
                f.write(f"Buffer Size: {self.buffer_size} frames ({self.max_buffer_seconds}s)\n\n")
                
                # Sensor events are unknown in this function, so set a placeholder
                # This will be updated when images are actually saved
                f.write("RECORD #1\n")
                f.write(f"  Start: {datetime.now().isoformat()}\n")
                f.write(f"  End: {datetime.now().isoformat()}\n")
                f.write(f"  Duration: 0.000s\n")
                f.write(f"  Result: unknown\n")
                f.write(f"  Frames Captured: {frame_count}\n")
                f.write(f"  Actual FPS: 0.000\n")
                f.write(f"  FPS Accuracy: 0.0%\n")
                f.write("  Sensor Events: N/A\n")
                f.write("  Sensor Intervals: N/A\n")
                
            return report_path
        except Exception as e:
            print(f"[BASLER_CAMERA] Error creating timing report summary: {e}")
            return None

    def _create_timing_report_json(self, output_dir, filter_start_time=None, filter_end_time=None, frames=None) -> str:
        """Create a detailed timing report JSON file"""
        try:
            report_path = os.path.join(output_dir, "capture_timing_report.json")
            report_data = {
                "generated": datetime.now().isoformat(),
                "camera": "BaslerCamera",
                "settings": {
                    "fps": self.buffer_fps,
                    "interval": 1.0/self.buffer_fps,
                    "buffer_size": self.buffer_size,
                    "max_seconds": self.max_buffer_seconds,
                },
                "records": [
                    {
                        "start_time": datetime.now().isoformat(),
                        "end_time": datetime.now().isoformat(),
                        "duration": 0.0,
                        "result": "unknown",
                        "frames_captured": len(frames) if frames else 0,
                        "actual_fps": 0.0,
                        "fps_accuracy": 0.0,
                        "sensor_events": []
                    }
                ]
            }
            
            with open(report_path, "w") as f:
                json.dump(report_data, f, indent=2)
                
            return report_path
        except Exception as e:
            print(f"[BASLER_CAMERA] Error creating timing report JSON: {e}")
            return None
            
    def _update_timing_report(self, output_dir, frames_captured=0):
        """Update timing reports with actual frame count"""
        try:
            # Update summary file
            summary_path = os.path.join(output_dir, "capture_timing_summary.txt")
            if os.path.exists(summary_path):
                with open(summary_path, "r") as f:
                    lines = f.readlines()
                
                # Find and update the frames captured line
                for i, line in enumerate(lines):
                    if "Frames Captured:" in line:
                        lines[i] = f"  Frames Captured: {frames_captured}\n"
                        
                        # Also update FPS information if we have frame count
                        if frames_captured > 0 and i+1 < len(lines) and "Actual FPS:" in lines[i+1]:
                            actual_fps = frames_captured / self.max_buffer_seconds
                            fps_accuracy = (actual_fps / self.buffer_fps) * 100
                            lines[i+1] = f"  Actual FPS: {actual_fps:.3f}\n"
                            lines[i+2] = f"  FPS Accuracy: {fps_accuracy:.1f}%\n"
                
                with open(summary_path, "w") as f:
                    f.writelines(lines)
            
            # Update JSON file
            json_path = os.path.join(output_dir, "capture_timing_report.json")
            if os.path.exists(json_path):
                with open(json_path, "r") as f:
                    data = json.load(f)
                
                if "records" in data and len(data["records"]) > 0:
                    data["records"][0]["frames_captured"] = frames_captured
                    if frames_captured > 0:
                        actual_fps = frames_captured / self.max_buffer_seconds
                        fps_accuracy = (actual_fps / self.buffer_fps) * 100
                        data["records"][0]["actual_fps"] = actual_fps
                        data["records"][0]["fps_accuracy"] = fps_accuracy
                
                with open(json_path, "w") as f:
                    json.dump(data, f, indent=2)
            
            return True
        except Exception as e:
            print(f"[BASLER_CAMERA] Error updating timing reports: {e}")
            return False

    def _process_presentation_images_background(self, inspection_id: int, image_paths: List[str]) -> None:
        """
        Process presentation images in a background thread
        
        Args:
            inspection_id: Inspection ID to associate images with
            image_paths: List of image paths to process
        """
        try:
            print(f"[BASLER_CAMERA] Background thread: Processing presentation images for inspection {inspection_id}")
            self.save_presentation_images(inspection_id, image_paths)
            print(f"[BASLER_CAMERA] Background thread: Completed processing presentation images")
        except Exception as e:
            print(f"[BASLER_CAMERA] Background thread: Error processing presentation images: {e}")
            traceback.print_exc()

    def save_presentation_images(self, inspection_id: int, image_paths: List[str]) -> None:
        """
        Save representative images for presentation groups A-E
        
        Args:
            inspection_id: The inspection ID to associate with the presentation images
            image_paths: List of paths to the saved images
        """
        if not image_paths:
            print("[BASLER_CAMERA] No images to select for presentation")
            return
            
        # Log timing information for performance analysis
        start_time = time.time()
        print(f"[BASLER_CAMERA] Selecting presentation images from {len(image_paths)} images for inspection {inspection_id}")
        
        # Clear any existing presentation data for this inspection to avoid conflicts
        try:
            with SessionLocal() as session:
                session.query(InspectionPresentation).filter(
                    InspectionPresentation.inspection_id == inspection_id
                ).delete()
                session.commit()
                print(f"[BASLER_CAMERA] Cleared existing presentation images for inspection {inspection_id}")
        except Exception as e:
            print(f"[BASLER_CAMERA] Error clearing existing presentation images: {e}")
            # Continue with the process even if clearing fails
        
        try:
            # Group images based on total count
            total_images = len(image_paths)
            group_count = min(5, total_images)  # Maximum of 5 groups (A-E)
            
            # Calculate images per group and prepare selection
            group_images = {}
            
            if group_count == 1:
                # If only one image, use it for group A
                group_images['A'] = image_paths[0]
            elif group_count <= 5:
                # Divide images evenly among groups
                images_per_group = total_images // group_count
                remainder = total_images % group_count
                
                # Assign group names based on count (A, B, C, D, E)
                group_names = [chr(65 + i) for i in range(group_count)]  # ASCII 65 = 'A'
                
                start_idx = 0
                for i, group_name in enumerate(group_names):
                    # Calculate end index for this group, distributing remainder
                    extra = 1 if i < remainder else 0
                    end_idx = start_idx + images_per_group + extra
                    
                    # Select middle image from this group
                    group_images_slice = image_paths[start_idx:end_idx]
                    middle_idx = len(group_images_slice) // 2
                    group_images[group_name] = group_images_slice[middle_idx]
                    
                    # Move to next group's start
                    start_idx = end_idx
            else:
                # With more than 5 images, select evenly distributed images
                indices = [int(i * total_images / 5) for i in range(5)]
                group_names = ['A', 'B', 'C', 'D', 'E']
                
                for i, group_name in enumerate(group_names):
                    group_images[group_name] = image_paths[indices[i]]
            
            print(f"[BASLER_CAMERA] Selected {len(group_images)} presentation images")
            
            # Normalize image paths - use forward slashes for web URLs
            normalized_group_images = {}
            for group, path in group_images.items():
                # Convert to absolute path if not already
                if not os.path.isabs(path):
                    abs_path = os.path.abspath(path)
                else:
                    abs_path = path
                
                # Verify the file exists
                if not os.path.isfile(abs_path):
                    print(f"[BASLER_CAMERA] Warning: Presentation image does not exist: {abs_path}")
                    # Skip this image if it doesn't exist
                    continue
                
                # Store the normalized path (use forward slashes)
                normalized_path = abs_path.replace('\\', '/')
                
                # For database storage, make sure we're preserving the full absolute path
                # This ensures we can find the file later
                normalized_group_images[group] = normalized_path
                
                print(f"[BASLER_CAMERA] Group {group} image path: {normalized_path}")
            
            try:
                # Save selected images to the database - use a new session to avoid conflicts
                with SessionLocal() as session:
                    try:
                        # Delete any existing presentation images for this inspection
                        session.query(InspectionPresentation).filter(
                            InspectionPresentation.inspection_id == inspection_id
                        ).delete()
                        
                        # Insert new presentation images
                        for group_name, image_path in normalized_group_images.items():
                            presentation = InspectionPresentation(
                                inspection_id=inspection_id,
                                group_name=group_name,
                                image_path=image_path
                            )
                            session.add(presentation)
                        
                        # Commit the transaction
                        # Ensure changes are committed immediately
                        session.commit()
                        end_time = time.time()
                        print(f"[BASLER_CAMERA] Saved {len(normalized_group_images)} presentation images to database for inspection {inspection_id} in {end_time - start_time:.3f}s")
                        
                        # Log the saved paths for debugging (only in debug mode to reduce log verbosity)
                        for group_name, image_path in normalized_group_images.items():
                            print(f"[BASLER_CAMERA] Saved group {group_name} image path: {image_path}")
                            
                            # Check if API would be able to find this file
                            inspection_match = re.search(r'inspection[/\\](.*)', image_path, re.IGNORECASE)
                            if inspection_match:
                                relative_path = inspection_match.group(1).replace('\\', '/')
                                print(f"[BASLER_CAMERA] API relative path would be: src-api/data/images/inspection/{relative_path}")
                                
                        # Force the session to flush and commit changes
                        session.flush()
                        session.commit()
                    except Exception as db_error:
                        session.rollback()
                        print(f"[BASLER_CAMERA] Database error saving presentation images: {db_error}")
                        traceback.print_exc()
            except Exception as session_error:
                print(f"[BASLER_CAMERA] Session error saving presentation images: {session_error}")
                traceback.print_exc()
            
        except Exception as e:
            print(f"[BASLER_CAMERA] Error saving presentation images: {e}")
            traceback.print_exc()
        
        # Update last_inspection_results to indicate presentation images are ready
        try:
            # Initialize last_inspection_results if not already set
            if self.last_inspection_results is None:
                self.last_inspection_results = {}
            
            # Get presentation images from database to ensure we're using latest data
            with SessionLocal() as session:
                presentation_images = session.query(InspectionPresentation).filter(
                    InspectionPresentation.inspection_id == inspection_id
                ).all()
                
                # If we have presentation images, get inspection date
                inspection_dt = None
                if len(presentation_images) > 0:
                    inspection = session.query(Inspection).get(inspection_id)
                    if inspection:
                        inspection_dt = inspection.inspection_dt.isoformat()
                
                # Convert to dict for frontend use
                presentation_images_data = [
                    {
                        "id": img.id,
                        "inspection_id": img.inspection_id,
                        "group_name": img.group_name,
                        "image_path": img.image_path
                    }
                    for img in presentation_images
                ]
                
                # Store presentation data for API retrieval
                self.last_inspection_results["inspection_id"] = inspection_id
                self.last_inspection_results["presentation_images"] = presentation_images_data
                self.last_inspection_results["inspection_dt"] = inspection_dt
                self.last_inspection_results["presentation_ready"] = True
                
                print(f"[BASLER_CAMERA] Updated last_inspection_results with {len(presentation_images_data)} presentation images for inspection {inspection_id}")
        except Exception as update_error:
            print(f"[BASLER_CAMERA] Error updating last_inspection_results: {update_error}")
            traceback.print_exc()
        
    def discard_buffer_images(self) -> None:
        """
        Discard buffered images without saving
        """
        print(f"[BASLER_CAMERA] Discarding buffer with {len(self.buffer)} frames")
        self.buffer.clear()
        self.save_message = "破棄しました"  # "Discarded" in Japanese
        self.save_path = ""
        print("[BASLER_CAMERA] Discarded buffer images")
        
    def get_latest_image(self):
        """
        Get the most recent image from buffer
        
        Returns:
            numpy.ndarray: Latest image
        """
        with self.lock:
            return self.latest_frame.copy() if self.latest_frame is not None else None
            
    def get_status(self) -> Dict[str, Any]:
        """
        Get current camera status
        
        Returns:
            Dict[str, Any]: Status information
        """
        status_dict = {
            "type": "basler",
            "connected": self.is_connected_flag,
            "grabbing": self.is_grabbing,
            "recording": self.is_recording,
            "mode": self.mode,
            "status": self.status,
            "save_message": self.save_message,
            "save_path": self.save_path,
            "buffer_size": len(self.buffer),
            "max_buffer_size": self.buffer_size,
            "exposure_time_us": self.exposure_time_us,
            "ai_threshold": self.ai_threshold  # Always include AI threshold
        }
        
        # Include last inspection results if available
        if self.last_inspection_results:
            status_dict["inspection_data"] = {
                "inspection_id": self.last_inspection_results.get("inspection_id"),
                "inspection_details": self.last_inspection_results.get("inspection_details", []),
                "confidence_above_threshold": self.last_inspection_results.get("confidence_above_threshold", False),
                "ai_threshold": self.last_inspection_results.get("ai_threshold", self.ai_threshold)
            }
            print(f"[BASLER_CAMERA] Included inspection_id {self.last_inspection_results.get('inspection_id')} in status data")
        
        return status_dict
        
    def _make_timestamp_dir(self, root_dir="output_dir") -> str:
        """
        Create timestamped directory for saving images
        
        Args:
            root_dir: Root directory
            
        Returns:
            str: Path to created directory
        """
        try:
            # First check if root directory exists, if not try to create it
            if not os.path.exists(root_dir):
                print(f"[BASLER_CAMERA] Root directory doesn't exist: {root_dir}, creating it")
                os.makedirs(root_dir, exist_ok=True)
            
            # Check write permissions
            test_file = os.path.join(root_dir, "_test_write.tmp")
            try:
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
                print(f"[BASLER_CAMERA] Root directory is writable: {root_dir}")
            except Exception as e:
                print(f"[BASLER_CAMERA] WARNING: Root directory is not writable: {root_dir}, error: {e}")
                # Try to use a fallback directory
                root_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'images', 'inspection')
                os.makedirs(root_dir, exist_ok=True)
                print(f"[BASLER_CAMERA] Using fallback directory: {root_dir}")
            
            now = datetime.now()
            # dirname = now.strftime("%Y%m%d_%H%M%S")
            dirname = now.strftime("%Y%m%d_%H%M")
            path = os.path.join(root_dir, dirname)
            os.makedirs(path, exist_ok=True)
            print(f"[BASLER_CAMERA] Created timestamped directory: {path}")
            return path
        except Exception as e:
            print(f"[BASLER_CAMERA] Error creating directory: {e}")
            # Use a fallback directory in the current directory
            fallback_dir = os.path.join(".", "images", now.strftime("%Y%m%d_%H%M"))
            os.makedirs(fallback_dir, exist_ok=True)
            print(f"[BASLER_CAMERA] Using emergency fallback directory: {fallback_dir}")
            return fallback_dir
        
    def save_images(self, output_dir=None, prefix="frame") -> List[str]:
        """
        Save all buffered images to directory (alias for save_buffer_images)
        
        Args:
            output_dir: Directory to save images to
            prefix: Prefix for image filenames
            
        Returns:
            List[str]: List of saved file paths
        """
        return self.save_buffer_images(output_dir, prefix)
        
    def discard_images(self) -> None:
        """
        Discard buffered images without saving (alias for discard_buffer_images)
        """
        self.discard_buffer_images()

    @staticmethod
    def is_camera_available() -> bool:
        """
        Check if any Basler cameras are available
        
        Returns:
            bool: True if at least one camera is available, False otherwise
        """
        if not PYLON_AVAILABLE:
            return False
            
        try:
            devices = pylon.TlFactory.GetInstance().EnumerateDevices()
            return len(devices) > 0
        except:
            return False

    def start_event_processing(self):
        """Start the background thread that processes sensor events in the queue"""
        if self.event_processing_active:
            print("[BASLER_CAMERA] Event processing already active")
            return
            
        self.event_processing_active = True
        self.event_processing_thread = threading.Thread(target=self._process_event_queue, daemon=True)
        self.event_processing_thread.start()
        print("[BASLER_CAMERA] Event queue processing started")
        
    def stop_event_processing(self):
        """Stop the event processing thread"""
        if not self.event_processing_active:
            print("[BASLER_CAMERA] Event processing already stopped")
            return
            
        self.event_processing_active = False
        if self.event_processing_thread and self.event_processing_thread.is_alive():
            # Wait for thread to complete current processing
            self.event_processing_thread.join(timeout=5.0)
            print("[BASLER_CAMERA] Event queue processing stopped")
        
    def _process_event_queue(self):
        """Process sensor events from the queue in the background"""
        while self.event_processing_active:
            try:
                # Get next event from queue with timeout to allow for graceful shutdown
                try:
                    event_data = self.event_queue.get(timeout=1.0)
                except queue.Empty:
                    # No events in queue, continue loop
                    continue
                    
                # Process the event
                print(f"[BASLER_CAMERA] Processing event from queue: {event_data.get('event_type', 'unknown')}")
                
                # Extract event data
                event_type = event_data.get('event_type')
                output_dir = event_data.get('output_dir')
                buffer_snapshot = event_data.get('buffer_snapshot')
                filter_start_time = event_data.get('filter_start_time')
                filter_end_time = event_data.get('filter_end_time')
                
                # Create output directory if needed
                if output_dir is None:
                    output_dir = self._make_timestamp_dir(self.save_directory)
                    print(f"[BASLER_CAMERA] Created output directory for queued event: {output_dir}")
                
                # Save buffer snapshot if it's a save event
                if event_type == 'save' and buffer_snapshot:
                    self._process_buffer_snapshot(buffer_snapshot, output_dir, filter_start_time, filter_end_time)
                    
                # Mark task as complete
                self.event_queue.task_done()
                    
            except Exception as e:
                print(f"[BASLER_CAMERA] Error processing event queue: {e}")
                traceback.print_exc()
                
        print("[BASLER_CAMERA] Event queue processor stopped")
        
    def _process_buffer_snapshot(self, buffer_snapshot, output_dir, filter_start_time=None, filter_end_time=None):
        """Process a buffer snapshot and save images"""
        print(f"[BASLER_CAMERA] Processing buffer snapshot with {len(buffer_snapshot)} frames to {output_dir}")
        saved_files = []
        
        try:
            # Ensure the directory exists
            os.makedirs(output_dir, exist_ok=True)
            
            # First create timing reports
            timing_report_summary = self._create_timing_report_summary(output_dir, filter_start_time, filter_end_time, len(buffer_snapshot))
            timing_report_json = self._create_timing_report_json(output_dir, filter_start_time, filter_end_time, buffer_snapshot)
            
            # Save each image from the snapshot
            for idx, img in enumerate(buffer_snapshot):
                try:
                    # Skip if image is None
                    if img is None:
                        print(f"[BASLER_CAMERA] Warning: Image {idx} in snapshot is None, skipping")
                        continue
                        
                    now = datetime.now()
                    timestamp = now.strftime("%Y%m%d_%H%M%S_%f")[:-3]
                    # Use configured filename format with clear interval marking
                    interval = 1.0 / self.buffer_fps
                    frame_time = idx * interval
                    # format_file_name = f"{output_dir}/frame_{idx:04d}_time_{frame_time:.1f}s_{timestamp}"
                    format_file_name = f"{output_dir}/No_{idx:04d}"
                    # First try BMP format (original format)
                    filename = format_file_name + ".bmp"
                    
                    # Debug image properties before saving
                    print(f"[BASLER_CAMERA] Image {idx} shape: {img.shape}, type: {img.dtype}, min: {np.min(img)}, max: {np.max(img)}")
                    
                    # Convert from RGB to BGR for OpenCV
                    img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                    
                    # Try saving in BMP format first
                    success = cv2.imwrite(filename, img_bgr)
                    
                    # If BMP fails, try JPG
                    if not success:
                        print(f"[BASLER_CAMERA] Failed with BMP, trying JPG format")
                        filename = format_file_name +".jpg"
                        success = cv2.imwrite(filename, img_bgr)
                        
                        # If JPG fails, try PNG
                        if not success:
                            print(f"[BASLER_CAMERA] Failed with JPG, trying PNG format")
                            filename = format_file_name + ".png"
                            success = cv2.imwrite(filename, img_bgr)
                    
                    if success:
                        saved_files.append(filename)
                        if idx % 10 == 0 or idx == len(buffer_snapshot) - 1:
                            print(f"[BASLER_CAMERA] Saved {idx+1}/{len(buffer_snapshot)} images")
                    else:
                        # Ultimate fallback - try saving as raw data
                        print(f"[BASLER_CAMERA] Failed to write image {idx} in all formats, trying raw data")
                        raw_filename = f"{output_dir}/frame_{idx:04d}_raw_{timestamp}.npy"
                        np.save(raw_filename, img)
                        saved_files.append(raw_filename)
                        print(f"[BASLER_CAMERA] Saved image {idx} as raw data")
                        
                except Exception as e:
                    print(f"[BASLER_CAMERA] Error saving snapshot image {idx}: {e}")
                    traceback.print_exc()
                    
            # Update the timing reports with actual frame count
            if len(saved_files) > 0:
                self._update_timing_report(output_dir, len(saved_files))
                print(f"[BASLER_CAMERA] Updated timing report for snapshot with {len(saved_files)} frames captured")
                
                # Run inference on saved images
                self._analyze_saved_files(saved_files, output_dir)
                
        except Exception as e:
            print(f"[BASLER_CAMERA] Error processing buffer snapshot: {e}")
            traceback.print_exc()
            
        print(f"[BASLER_CAMERA] Finished processing buffer snapshot, saved {len(saved_files)} files")
        return saved_files
        
    def _analyze_saved_files(self, saved_files, output_dir):
        """Analyze saved files with inference in the background"""
        if len(saved_files) == 0:
            print("[BASLER_CAMERA] No files to analyze")
            return
            
        # Start a background thread for analysis
        analysis_thread = threading.Thread(
            target=self._analyze_files_thread,
            args=(saved_files, output_dir),
            daemon=True
        )
        analysis_thread.start()
        self.background_threads.append(analysis_thread)
        print(f"[BASLER_CAMERA] Started background analysis thread for {len(saved_files)} files")
        
    def _analyze_files_thread(self, saved_files, output_dir):
        """Background thread to analyze saved files"""
        print(f"[BASLER_CAMERA] Starting analysis of {len(saved_files)} files in background")
        try:
            # Run inference on all saved images with a shared inspection_id
            all_inspection_results = []
            shared_inspection_id = None
            
            for img_idx, image_path in enumerate(saved_files):
                # Skip raw numpy files for analysis
                if image_path.endswith('.npy'):
                    print(f"[BASLER_CAMERA] Skipping raw numpy file: {image_path}")
                    continue
                    
                try:
                    # Analyze each image with the shared inspection ID to accumulate all errors
                    # For the first image, we create a new inspection ID
                    if img_idx == 0:
                        analysis_results = self._analyze_image(image_path)
                        if analysis_results and "inspection_id" in analysis_results:
                            shared_inspection_id = analysis_results["inspection_id"]
                            print(f"[BASLER_CAMERA] Created shared inspection_id: {shared_inspection_id} for image batch")
                    else:
                        # Use the shared inspection_id for all subsequent images so all errors accumulate
                        analysis_results = self._analyze_image(image_path, shared_inspection_id)
                    
                    if analysis_results:
                        confidence_above_threshold = analysis_results.get("confidence_above_threshold", False)
                        print(f"[BASLER_CAMERA] Analysis results for image {img_idx+1}: Inspection ID {analysis_results['inspection_id']}, "
                              f"Detections: {len(analysis_results['detections'])}, "
                              f"Above AI threshold ({self.ai_threshold}%): {confidence_above_threshold}")
                        
                        # Add to results list
                        all_inspection_results.append(analysis_results)
                        
                        # Store the latest results for API retrieval
                        self.last_inspection_results = analysis_results
                        
                        if not confidence_above_threshold:
                            print(f"[BASLER_CAMERA] Image {img_idx+1} does not meet AI threshold ({self.ai_threshold}%)")
                    else:
                        print(f"[BASLER_CAMERA] Analysis failed or returned no results for image {img_idx+1}")
                except Exception as analysis_error:
                    print(f"[BASLER_CAMERA] Error analyzing image {image_path}: {analysis_error}")
                    traceback.print_exc()
                    continue
            
            # Start a background thread to process presentation images
            if shared_inspection_id and len(saved_files) > 0:
                # Create a copy of saved_files to prevent reference issues
                saved_files_copy = saved_files.copy()
                print(f"[BASLER_CAMERA] Starting presentation image processing for inspection_id: {shared_inspection_id}")
                # Process presentation images directly in this thread to ensure they're ready
                # Process the presentation images right away to minimize delay
                self.save_presentation_images(shared_inspection_id, saved_files_copy)
                print(f"[BASLER_CAMERA] Completed presentation image processing for inspection_id: {shared_inspection_id}")
                
                # Create a frontend notification about presentation images being ready
                try:
                    # Get the presentation images we just saved - use a separate session to avoid potential locks
                    with SessionLocal() as session:
                        # Add a small delay to ensure database writes are complete
                        time.sleep(0.1)
                        
                        # Use a direct SQL query for better performance
                        presentation_images = session.query(InspectionPresentation).filter(
                            InspectionPresentation.inspection_id == shared_inspection_id
                        ).all()
                        
                        # If we have presentation images, add the inspection_dt to the notification
                        inspection_dt = None
                        if len(presentation_images) > 0:
                            inspection = session.query(Inspection).get(shared_inspection_id)
                            if inspection:
                                inspection_dt = inspection.inspection_dt.isoformat()
                        
                        # Convert to dict for frontend use
                        presentation_images_data = [
                            {
                                "id": img.id,
                                "inspection_id": img.inspection_id,
                                "group_name": img.group_name,
                                "image_path": img.image_path
                            }
                            for img in presentation_images
                        ]
                        
                        print(f"[BASLER_CAMERA] Prepared notification with {len(presentation_images_data)} presentation images for frontend")
                        
                        # Store the presentation images in the last_inspection_results for API retrieval
                        if self.last_inspection_results:
                            self.last_inspection_results["presentation_images"] = presentation_images_data
                            self.last_inspection_results["inspection_dt"] = inspection_dt
                            self.last_inspection_results["presentation_ready"] = True  # Add a flag to indicate presentation images are ready
                            print(f"[BASLER_CAMERA] Added presentation_images to last_inspection_results for frontend retrieval")
                except Exception as notification_error:
                    print(f"[BASLER_CAMERA] Error creating presentation image notification: {notification_error}")
                    traceback.print_exc()
                
                # Ensure the inspection_id is included in the status data for the frontend
                if self.last_inspection_results and "inspection_id" not in self.last_inspection_results:
                    self.last_inspection_results["inspection_id"] = shared_inspection_id
                
        except Exception as e:
            print(f"[BASLER_CAMERA] Error in analysis thread: {e}")
            traceback.print_exc()
            
        print(f"[BASLER_CAMERA] Background analysis completed for {len(saved_files)} files")


# Simple test function
def test_basler_camera():
    """Test the Basler camera implementation"""
    camera = BaslerCamera()
    
    print("Testing Basler camera...")
    
    # Check if camera is available
    if not BaslerCamera.is_camera_available():
        print("No Basler cameras available")
        return
        
    # Connect to camera
    if not camera.connect():
        print("Failed to connect to camera")
        return
        
    # Grab a few frames
    print("Grabbing frames for 5 seconds...")
    for i in range(5):
        frame = camera.get_frame()
        if frame and "image" in frame:
            print(f"Frame {i+1}: Shape={frame['image'].shape}, Type={frame['image'].dtype}")
        else:
            print(f"Frame {i+1}: None")
        time.sleep(1)
        
    # Test recording mode
    print("Testing recording mode...")
    camera.set_mode("recording")
    time.sleep(3)  # Record for 3 seconds
    
    # Save buffer
    print("Saving buffer...")
    saved_files = camera.save_buffer_images()
    print(f"Saved {len(saved_files)} files")
    
    # Disconnect
    camera.disconnect()
    
    print("Test complete")


if __name__ == "__main__":
    test_basler_camera()
