# source/camera/webcam_camera.py
from .base import AbstractCamera
import cv2
import traceback
import logging
import os
from datetime import datetime
import numpy as np
from PIL import Image
import time


class WebcamCamera(AbstractCamera):
    def __init__(self, camera_index=0):
        """
        Initialize webcam camera
        Args:
            camera_index: Camera device index (0 for default camera, 1 for external, etc.)
        """
        self.camera_index = camera_index
        self.camera = None
        self.connected = False
        self.mode = 'snapshot'
        from __init__ import ROOT_DIR
        self.save_directory = os.path.join(ROOT_DIR, 'data', 'images', 'webcam')
        
        # Webcam settings
        self.frame_width = 1280
        self.frame_height = 720
        self.fps = 30

    def connect(self):
        """Connect to webcam using OpenCV"""
        try:
            logging.getLogger(__name__).info(f"Attempting to connect to webcam (index: {self.camera_index})")
            
            # Release any existing camera
            if self.camera is not None:
                self.camera.release()
                
            # Initialize camera
            self.camera = cv2.VideoCapture(self.camera_index)
            
            if not self.camera.isOpened():
                logging.getLogger(__name__).error(f"Failed to open webcam at index {self.camera_index}")
                self.connected = False
                return False
            
            # Set camera properties
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)
            self.camera.set(cv2.CAP_PROP_FPS, self.fps)
            
            # Test if camera can capture a frame
            ret, frame = self.camera.read()
            if not ret:
                print("[ERROR] Failed to capture test frame from webcam")
                self.camera.release()
                self.connected = False
                return False
            
            self.connected = True
            logging.getLogger(__name__).info("Webcam connected successfully")
            logging.getLogger(__name__).debug(f"Frame size: {frame.shape[1]}x{frame.shape[0]}")
            return True
            
        except Exception as e:
            logging.getLogger(__name__).exception(f"Webcam connection failed: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """Disconnect from webcam"""
        try:
            if self.camera is not None:
                self.camera.release()
                self.camera = None
            self.connected = False
            logging.getLogger(__name__).info("Webcam disconnected")
            return True
        except Exception as e:
            logging.getLogger(__name__).exception(f"Webcam disconnect failed: {e}")
            return False

    def is_connected(self):
        """Check if webcam is connected and working"""
        try:
            if self.camera is None:
                return False
            return self.camera.isOpened() and self.connected
        except Exception:
            return False

    def set_mode(self, mode: str):
        """Set camera mode (for compatibility with Basler interface)"""
        if mode not in ["snapshot", "continuous"]:
            raise ValueError("mode must be 'snapshot' or 'continuous'")
        self.mode = mode
        logging.getLogger(__name__).info(f"Webcam mode set to: {mode}")

    def get_frame(self):
        """Capture a frame from webcam"""
        try:
            if not self.is_connected():
                logging.getLogger(__name__).warning("Webcam not connected")
                # Try to reconnect automatically
                if self.reconnect():
                    logging.getLogger(__name__).info("Webcam reconnected successfully")
                else:
                    return None
                
            ret, frame = self.camera.read()
            if not ret:
                logging.getLogger(__name__).error("Failed to capture frame from webcam")
                # Mark as disconnected and try to reconnect next time
                self.connected = False
                return None
            
            # Convert BGR to RGB (OpenCV uses BGR by default)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Generate timestamp (in microseconds for compatibility with Basler)
            timestamp = int(datetime.now().timestamp() * 1000000)
            
            return {
                'timestamp': timestamp,
                'image': frame_rgb  # Use 'image' key for consistency with other camera interfaces
            }
            
        except Exception as e:
            logging.getLogger(__name__).error(f"get_frame failed: {e}")
            self.connected = False  # Mark as disconnected on error
            return None

    def write_frame(self, save_path: str = None):
        """Capture and save a frame"""
        frame_data = self.get_frame()
        if frame_data:
            try:
                # Convert to PIL Image
                pil_img = Image.fromarray(frame_data['image'])
                
                # Generate filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S%f")[:-3]
                file_name = f"webcam_{timestamp}.jpg"
                
                # Create save path
                path = save_path or self.save_directory
                os.makedirs(path, exist_ok=True)
                full_path = os.path.join(path, file_name)
                
                # Save image
                pil_img.save(full_path)
                logging.getLogger(__name__).info(f"Webcam frame saved to: {full_path}")
                return full_path
                
            except Exception as e:
                logging.getLogger(__name__).exception(f"Failed to save webcam frame: {e}")
                return None
        return None

    def set_resolution(self, width: int, height: int):
        """Set camera resolution"""
        self.frame_width = width
        self.frame_height = height
        if self.is_connected():
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            logging.getLogger(__name__).info(f"Webcam resolution set to: {width}x{height}")

    def set_fps(self, fps: int):
        """Set camera FPS"""
        self.fps = fps
        if self.is_connected():
            self.camera.set(cv2.CAP_PROP_FPS, fps)
            logging.getLogger(__name__).info(f"Webcam FPS set to: {fps}")

    def set_params(self, params: dict):
        """Set camera parameters (for compatibility with Basler interface)"""
        try:
            if 'SaveDirectory' in params:
                self.save_directory = params['SaveDirectory']
                
            if 'FrameWidth' in params:
                self.set_resolution(params['FrameWidth'], self.frame_height)
                
            if 'FrameHeight' in params:
                self.set_resolution(self.frame_width, params['FrameHeight'])
                
            if 'FPS' in params:
                self.set_fps(params['FPS'])
                
            logging.getLogger(__name__).info(f"Webcam parameters updated: {params}")
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to set webcam parameters: {e}")

    def list_available_cameras(self):
        """List available camera indices"""
        available_cameras = []
        for i in range(10):  # Check first 10 indices
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                available_cameras.append(i)
                cap.release()
        return available_cameras

    def reconnect(self):
        """Try to reconnect to the camera"""
        logging.getLogger(__name__).info("Attempting to reconnect webcam...")
        # Ensure camera is released before reconnecting
        if self.camera is not None:
            try:
                self.camera.release()
            except:
                pass
            self.camera = None
            
        # Wait a moment before reconnecting
        time.sleep(0.5)
        
        # Try to connect again
        return self.connect() 