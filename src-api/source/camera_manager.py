"""
Camera Manager Module
Provides centralized access to camera resources to prevent conflicts
"""

import threading
import time
from typing import Optional, Dict, Any, Type
from camera.base import AbstractCamera
from camera.basler import BaslerCamera, PYLON_AVAILABLE
from camera.webcam_camera import WebcamCamera

class CameraManager:
    """
    Singleton class to manage camera access and prevent conflicts
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(CameraManager, cls).__new__(cls)
                cls._instance._initialize()
            return cls._instance
    
    def _initialize(self):
        """Initialize the camera manager"""
        self.active_camera = None
        self.camera_type = None
        self.camera_lock = threading.Lock()
        self.users = {}  # Track which components are using the camera
    
    def get_camera(self, camera_type: str, user_id: str) -> AbstractCamera:
        """
        Get a camera instance of the specified type
        
        Args:
            camera_type: Type of camera to get ('basler', 'webcam', etc.)
            user_id: ID of the component requesting the camera
            
        Returns:
            Camera instance
        """
        with self.camera_lock:
            # If a different camera type is already active, disconnect it
            if self.active_camera and self.camera_type != camera_type:
                print(f"[CAMERA_MANAGER] Switching camera type from {self.camera_type} to {camera_type}")
                self._disconnect_camera()
            
            # Create camera if needed
            if not self.active_camera:
                self.active_camera = self._create_camera(camera_type)
                self.camera_type = camera_type
            
            # Register user
            self.users[user_id] = time.time()
            
            return self.active_camera
    
    def release_camera(self, user_id: str) -> None:
        """
        Release a camera instance
        
        Args:
            user_id: ID of the component releasing the camera
        """
        with self.camera_lock:
            if user_id in self.users:
                del self.users[user_id]
                
            # If no more users, disconnect the camera
            if not self.users and self.active_camera:
                self._disconnect_camera()
    
    def _create_camera(self, camera_type: str) -> AbstractCamera:
        """
        Create a camera instance of the specified type
        
        Args:
            camera_type: Type of camera to create
            
        Returns:
            Camera instance
        """
        if camera_type == "basler":
            if not PYLON_AVAILABLE or BaslerCamera is None:
                print(f"[CAMERA_MANAGER] Cannot connect to basler camera: pypylon not available or BaslerCamera not imported")
                camera = WebcamCamera()  # Fallback to webcam camera
            else:
                try:
                    camera = BaslerCamera()
                    print(f"[CAMERA_MANAGER] Successfully created BaslerCamera instance")
                except Exception as e:
                    print(f"[CAMERA_MANAGER] Error creating BaslerCamera: {e}")
                    camera = WebcamCamera()  # Fallback to webcam camera
        elif camera_type == "webcam":
            camera = WebcamCamera()
        else:
            raise ValueError(f"Unsupported camera type: {camera_type}")
        
        # Try to connect
        try:
            camera.connect()
        except Exception as e:
            print(f"[CAMERA_MANAGER] Error connecting to {camera_type} camera: {e}")
        
        return camera
    
    def _disconnect_camera(self) -> None:
        """Disconnect the active camera"""
        if self.active_camera:
            try:
                self.active_camera.disconnect()
            except Exception as e:
                print(f"[CAMERA_MANAGER] Error disconnecting camera: {e}")
            
            self.active_camera = None
            self.camera_type = None
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the camera manager
        
        Returns:
            Status dictionary
        """
        with self.camera_lock:
            return {
                "active_camera_type": self.camera_type,
                "is_connected": self.active_camera.is_connected() if self.active_camera else False,
                "active_users": list(self.users.keys()),
                "user_count": len(self.users)
            }

# Create a singleton instance
camera_manager = CameraManager() 