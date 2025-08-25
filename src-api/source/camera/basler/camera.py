import __init__
"""
Main BaslerCamera implementation module - using modular structure.
"""

import os
import time
import threading
import logging
import queue
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
import cv2
import traceback
from collections import deque
import numpy as np

# Try to import pypylon for Basler cameras
try:
    from pypylon import pylon
    PYLON_AVAILABLE = True
except ImportError:
    PYLON_AVAILABLE = False
    print("[WARNING] pypylon is not available, Basler camera support will be limited")

from camera.base import AbstractCamera
from inference.inference_service import WoodKnotInferenceService

# Import database models
from db import Inspection, InspectionResult
from db.inspection_details import InspectionDetails
from db.inspection_presentation import InspectionPresentation
from sqlalchemy.orm import Session
from db.engine import SessionLocal

# Import database handler
from .db_handler import DatabaseHandler

# Import module components
from .buffer_handling.buffer_manager import BufferManager
from .buffer_handling.frame_extractor import FrameExtractor
from .frame_handling.frame_grabber import FrameGrabber
from .frame_handling.grab_loop import grab_loop
from .event_processor import EventProcessor
from .image_processor import ImageProcessor
from .hardware.camera_controller import CameraController
from .analysis.image_analyzer import ImageAnalyzer
from .analysis.presentation_processor import PresentationProcessor

# Configure logging
logger = logging.getLogger('BaslerCamera')

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
        
        # Buffer for recording - using deque like the original file
        self.buffer_fps = buffer_fps
        self.max_buffer_seconds = max_buffer_seconds
        self.buffer_size = int(max_buffer_seconds * buffer_fps)
        self.buffer = deque(maxlen=self.buffer_size) # Original implementation uses deque
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
        
        # Save directory (matches the original implementation)
        self.save_directory = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                '..',
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
        
        # Flag to indicate a new inspection has just started
        self.inspection_just_started = False
        
        # Initialize database handler
        self.db_handler = DatabaseHandler()
        
        # Initialize component modules
        self.buffer_manager = BufferManager(self)
        self.frame_extractor = FrameExtractor(self)
        self.frame_grabber = FrameGrabber(self)
        self.event_processor = EventProcessor(self)
        self.image_processor = ImageProcessor()
        self.camera_controller = CameraController(self)
        self.image_analyzer = ImageAnalyzer(self)
        self.presentation_processor = PresentationProcessor(self)

        # Initialize parallel processing manager
        try:
            from .parallel.parallel_processing_manager import ParallelProcessingManager
            self.parallel_processor = ParallelProcessingManager(self)
            logger.info("Parallel processing manager initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize parallel processing manager: {e}")
            self.parallel_processor = None

        logger.info("BaslerCamera initialized successfully")
        
    def test_camera_detection(self) -> Dict[str, Any]:
        """
        Test camera detection without connecting
        
        Returns:
            Dict[str, Any]: Detection results and diagnostics
        """
        return self.camera_controller.test_camera_detection()

    def connect(self) -> bool:
        """
        Connect to the first available Basler camera
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        if not PYLON_AVAILABLE:
            logger.error("Error: pypylon not available")
            return False
            
        try:
            # Test detection first
            detection_result = self.test_camera_detection()
            if not detection_result["success"]:
                logger.error(f"Camera detection failed: {detection_result.get('error', 'Unknown error')}")
                return False
                
            if detection_result["camera_count"] == 0:
                logger.error("No cameras detected during pre-connection test")
                return False
                
            logger.info(f"Pre-connection test passed: {detection_result['camera_count']} camera(s) detected")
            
            # Use the camera controller to establish connection
            result = self.camera_controller.connect()
            
            if result:
                # Start in snapshot mode by default
                self.set_mode("snapshot")
                
                # Start the event processing thread
                self.event_processor.start_event_processing()
                
            return result
            
        except Exception as e:
            logger.error(f"Error connecting to camera: {e}")
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
            self.event_processor.stop_event_processing()

            # Stop recording if active
            if self.is_recording:
                self.buffer_manager.stop_recording()

            # Stop grabbing if active
            if self.is_grabbing:
                self.stop_grabbing()

            # Shutdown parallel processing manager
            if hasattr(self, 'parallel_processor') and self.parallel_processor:
                self.parallel_processor.shutdown()

            # Use camera controller to release hardware resources
            self.camera_controller.release_camera_resources()

        except Exception as e:
            logger.error(f"Error releasing camera resources: {e}")
            
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
            logger.error(f"Error disconnecting from camera: {e}")
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
            self.buffer_manager.stop_recording()
            
        self.mode = mode
        logger.info(f"Set mode to {mode}")
        
        # Start new mode
        if mode == "continuous" or mode == "recording":
            self.start_grabbing()
            
        if mode == "recording":
            self.buffer_manager.start_recording()
            
    def get_frame(self) -> Dict[str, Any]:
        """Get the latest frame from the camera"""
        # Safety checks
        if not self.is_connected_flag or self.camera is None:
            self._last_error = "Not connected to camera"
            # Create a fallback image
            return self._create_fallback_image()
            
        # For continuous or recording mode, use cached frame for better performance
        if (self.mode == "continuous" or self.mode == "recording") and self.latest_frame is not None:
            with self.lock:
                if self.latest_frame is not None:
                    # Return a copy of the latest frame
                    return {
                        "image": self.latest_frame.copy(), 
                        "timestamp": self.latest_frame_timestamp or time.time()
                    }
        
        # For snapshot mode or as fallback, use the frame grabber
        try:
            frame_data = self.frame_grabber.optimized_frame_grab(self.converter)
            if frame_data:
                return frame_data
            else:
                return self._create_fallback_image()
                
        except Exception as e:
            self._error_count += 1
            self._last_error = str(e)
            logger.error(f"Exception in get_frame: {e}")
            return self._create_fallback_image()
    
    def _create_fallback_image(self) -> Dict[str, Any]:
        """Create a fallback image when camera capture fails"""
        # Create a small black image with text
        height, width = 480, 640
        fallback_image = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Add text with system status
        if self.camera is None:
            status_text = "Camera Not Initialized"
        elif not self.is_connected_flag:
            status_text = "Camera Disconnected"
        else:
            status_text = "No Camera Signal"
            
        cv2.putText(fallback_image, status_text, (width//2 - 120, height//2 - 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        if self._last_error:
            cv2.putText(fallback_image, f"Error: {self._last_error}", (width//2 - 200, height//2 + 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 50, 50), 1)
                       
        cv2.putText(fallback_image, f"Mode: {self.mode}", (width//2 - 200, height//2 + 50),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
            
        logger.warning(f"Created fallback image due to camera issues: {self._last_error}")
        
        return {
            "image": fallback_image,
            "timestamp": int(time.time() * 1000000),
            "is_fallback": True,
            "error": self._last_error
        }
    
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
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S%f")[:-3]
            file_name = f"{timestamp}.bmp"
            path = save_path or self.save_directory
            os.makedirs(path, exist_ok=True)
            full_path = os.path.join(path, file_name)
            
            # Save image using the image processor
            img_bgr = self.image_processor.rgb_to_bgr(frame["image"])
            if self.image_processor.save_image(img_bgr, full_path):
                self.save_path = full_path
                self.save_message = "保存しました"  # "Saved" in Japanese
                return full_path
            else:
                return "Failed to save image"
                
        except Exception as e:
            error_msg = f"Error saving frame: {str(e)}"
            logger.error(error_msg)
            return error_msg
            
    def set_ai_threshold(self, threshold: int) -> None:
        """
        Set the AI threshold for detection confidence
        
        Args:
            threshold: Threshold value (10-100)
        """
        # Validate threshold range
        if threshold < 10 or threshold > 100:
            logger.warning(f"Invalid AI threshold: {threshold}. Must be between 10 and 100. Using 50 as default.")
            threshold = 50
            
        self.ai_threshold = threshold
        logger.info(f"Set AI threshold to {self.ai_threshold}%")
        
        # Convert from percentage to float (0.0-1.0) for the inference service
        inference_threshold = threshold / 100.0
        self.inference_service.update_threshold(inference_threshold)
        logger.info(f"Updated inference service threshold to {inference_threshold}")

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
                # Let the camera controller handle the hardware settings
                self.camera_controller.set_exposure_time(self.exposure_time_us)
                
            # Frame rate settings
            if "fps" in params:
                fps = float(params["fps"])
                if self.camera is not None and self.is_connected_flag:
                    # Let the camera controller handle frame rate settings
                    self.camera_controller.set_frame_rate(fps)
                
                # Update buffer fps
                self.buffer_fps = fps
                self.buffer_size = int(self.max_buffer_seconds * self.buffer_fps)
                self.buffer = deque(maxlen=self.buffer_size)
                logger.info(f"Set buffer fps to {self.buffer_fps}")
                
            # Buffer settings
            if "MaxSeconds" in params:
                self.max_buffer_seconds = int(params["MaxSeconds"])
                self.buffer_size = int(self.max_buffer_seconds * self.buffer_fps)
                self.buffer = deque(maxlen=self.buffer_size)
                logger.info(f"Set buffer size to {self.buffer_size} frames ({self.max_buffer_seconds} seconds)")
                
            # Save directory
            if "SaveDirectory" in params:
                self.save_directory = params["SaveDirectory"]
                os.makedirs(self.save_directory, exist_ok=True)
                logger.info(f"Set save directory to {self.save_directory}")
                
        except Exception as e:
            logger.error(f"Error setting parameters: {e}")
            
    def start_grabbing(self) -> bool:
        """
        Start continuously grabbing frames from the camera
        
        Returns:
            bool: True if grabbing started successfully, False otherwise
        """
        if not self.is_connected_flag or self.camera is None:
            logger.error("Error: Not connected to camera")
            return False
            
        if self.is_grabbing:
            logger.info("Already grabbing frames")
            return True
            
        try:
            # Check if camera is already grabbing
            if self.camera.IsGrabbing():
                logger.info("Camera is already grabbing, no need to start again")
                self.is_grabbing = True
                self.stop_event.clear()
                
                # Start grab thread if not already running
                if self.grab_thread is None or not self.grab_thread.is_alive():
                    self.grab_thread = threading.Thread(
                        target=grab_loop, 
                        args=(self, self.stop_event, self.grab_lock, self.lock, self.frame_grabber, self.image_processor),
                        daemon=True
                    )
                    self.grab_thread.start()
                
                logger.info("Started monitoring existing grab")
                return True
            
            # Start grabbing
            self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
            self.is_grabbing = True
            self.stop_event.clear()
            
            # Start grab thread
            self.grab_thread = threading.Thread(
                target=grab_loop, 
                args=(self, self.stop_event, self.grab_lock, self.lock, self.frame_grabber, self.image_processor),
                daemon=True
            )
            self.grab_thread.start()
            
            logger.info("Started grabbing frames")
            return True
            
        except Exception as e:
            logger.error(f"Error starting grabbing: {e}")
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
            logger.info("Stopped grabbing frames")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping grabbing: {e}")
            return False
            
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
        return self.buffer_manager.save_buffer_images(output_dir, prefix, filter_start_time, filter_end_time)
        
    def discard_buffer_images(self) -> None:
        """
        Discard buffered images without saving
        """
        self.buffer_manager.discard_buffer_images()
        
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
            "ai_threshold": self.ai_threshold,  # Always include AI threshold
            # Add capture-compatible status fields
            "last_save_message": self.save_message,
            "processing_active": False,  # BaslerCamera doesn't track this separately
            "sensors_active": False,     # BaslerCamera doesn't track this separately
            "inspection_just_started": self.inspection_just_started  # Include flag for frontend to know we just started
        }
        
        # Include last inspection results if available
        if self.last_inspection_results:
            inspection_data = {
                "inspection_id": self.last_inspection_results.get("inspection_id"),
                "inspection_details": self.last_inspection_results.get("inspection_details", []),
                "confidence_above_threshold": self.last_inspection_results.get("confidence_above_threshold", False),
                "ai_threshold": self.last_inspection_results.get("ai_threshold", self.ai_threshold),
                "results": self.last_inspection_results.get("results")
            }
            
            # Include presentation images if available
            if "presentation_images" in self.last_inspection_results:
                inspection_data["presentation_images"] = self.last_inspection_results["presentation_images"]
                inspection_data["presentation_ready"] = self.last_inspection_results.get("presentation_ready", False)
            
            # Include inspection date if available
            if "inspection_dt" in self.last_inspection_results:
                inspection_data["inspection_dt"] = self.last_inspection_results["inspection_dt"]
            
            status_dict["inspection_data"] = inspection_data
            logger.info(f"Included inspection_id {self.last_inspection_results.get('inspection_id')} in status data with presentation_ready={inspection_data.get('presentation_ready', False)}")
        
        return status_dict
        
    def _analyze_image(self, image_path: str, shared_inspection_id: int = None) -> Dict[str, Any]:
        """
        Analyze an image using the inference service and save results to database
        This is a proxy method that forwards to the image analyzer
        
        Args:
            image_path: Path to the image file
            shared_inspection_id: Optional inspection ID to use for all images in a batch
            
        Returns:
            Dict[str, Any]: Analysis results with database IDs
        """
        return self.image_analyzer.analyze_image(image_path, shared_inspection_id)
        
    def _process_presentation_images_background(self, inspection_id: int, image_paths: List[str]) -> None:
        """
        Process presentation images in a background thread
        This is a proxy method that forwards to the presentation processor
        
        Args:
            inspection_id: Inspection ID to associate images with
            image_paths: List of image paths to process
        """
        self.presentation_processor.save_presentation_images(inspection_id, image_paths)