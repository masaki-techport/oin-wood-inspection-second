"""
Camera Manager Module
Provides centralized access to camera resources to prevent conflicts
"""

import threading
import time
from typing import Optional, Dict, Any, Type
from camera.base import AbstractCamera
from camera.webcam_camera import WebcamCamera
import logging

# Optional import for Basler camera
try:
    from camera.basler import BaslerCamera, PYLON_AVAILABLE
except ImportError:
    logging.getLogger(__name__).warning("Basler camera not available in camera_manager - pypylon not installed")
    BaslerCamera = None
    PYLON_AVAILABLE = False

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
        self.development_mode = True  # Enable development mode by default
        self.preferred_camera_type = "basler"  # Default to webcam for development
        self.logger = logging.getLogger(__name__)
    
    def get_camera(self, camera_type: str, user_id: str) -> AbstractCamera:
        """
        Get a camera instance of the specified type

        Args:
            camera_type: Type of camera to get ('basler', 'webcam', etc.)
            user_id: ID of the component requesting the camera

        Returns:
            Camera instance

        Raises:
            ValueError: If camera type is unsupported
            RuntimeError: If camera cannot be created or connected
        """
        with self.camera_lock:
            # If a different camera type is already active, disconnect it
            if self.active_camera and self.camera_type != camera_type:
                self.logger.info(f"Switching camera type from {self.camera_type} to {camera_type}")
                self.logger.info(f"Disconnecting current {self.camera_type} camera...")
                self._disconnect_camera()
                self.logger.info("Previous camera disconnected successfully")

            # Create camera if needed
            if not self.active_camera:
                try:
                    self.logger.info(f"Initializing new {camera_type} camera...")
                    self.active_camera = self._create_camera(camera_type)
                    self.camera_type = camera_type
                    self.logger.info(f"Camera {camera_type} initialized and ready")
                except (ValueError, RuntimeError) as e:
                    # Re-raise the exception to let the caller handle it
                    self.logger.error(f"Failed to create {camera_type} camera: {e}")
                    self.logger.warning("Camera creation failed, check camera availability and connections")
                    raise

            # Register user
            self.users[user_id] = time.time()
            self.logger.debug(f"User '{user_id}' registered for {camera_type} camera")
            self.logger.debug(f"Active users: {list(self.users.keys())}")

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
                self.logger.debug(f"User '{user_id}' released camera")
                self.logger.debug(f"Remaining users: {list(self.users.keys())}")
                
            # If no more users, disconnect the camera
            if not self.users and self.active_camera:
                self.logger.info(f"No active users, disconnecting {self.camera_type} camera...")
                self._disconnect_camera()
                self.logger.info("Camera disconnected and resources released")
    
    def _create_camera(self, camera_type: str) -> AbstractCamera:
        """
        Create a camera instance of the specified type

        Args:
            camera_type: Type of camera to create

        Returns:
            Camera instance

        Raises:
            ValueError: If camera type is unsupported
            RuntimeError: If camera cannot be created or connected
        """
        camera = None

        if camera_type == "basler":
            # Check if Basler camera is available
            if not PYLON_AVAILABLE or BaslerCamera is None:
                raise RuntimeError(f"Basler camera not available: pypylon not installed or BaslerCamera not imported")

            try:
                self.logger.info("Creating Basler camera instance...")
                camera = BaslerCamera()
                self.logger.info("Successfully created BaslerCamera instance")
                self.logger.debug(f"Camera type: {camera.__class__.__name__}")
            except Exception as e:
                self.logger.exception(f"Failed to create BaslerCamera: {e}")
                raise RuntimeError(f"Failed to create BaslerCamera: {e}")

        elif camera_type == "webcam":
            try:
                self.logger.info("Creating Webcam camera instance...")
                camera = WebcamCamera()
                self.logger.info("Successfully created WebcamCamera instance")
                self.logger.debug(f"Camera type: {camera.__class__.__name__}")
            except Exception as e:
                self.logger.exception(f"Failed to create WebcamCamera: {e}")
                raise RuntimeError(f"Failed to create WebcamCamera: {e}")
        else:
            raise ValueError(f"Unsupported camera type: {camera_type}")

        # Try to connect to the camera
        try:
            self.logger.info(f"Attempting to connect to {camera_type} camera...")
            if not camera.connect():
                self.logger.error("Connection failed: Camera.connect() returned False")
                raise RuntimeError(f"Failed to connect to {camera_type} camera: Connection returned False")

            self.logger.debug("Verifying camera connection status...")
            if not camera.is_connected():
                self.logger.error("Connection verification failed: Camera.is_connected() returned False")
                raise RuntimeError(f"Failed to connect to {camera_type} camera: Camera reports not connected")

            self.logger.info(f"Successfully connected to {camera_type} camera")
            self.logger.info("Camera status: Connected and ready")

        except Exception as e:
            # Clean up the camera instance if connection failed
            try:
                if hasattr(camera, 'disconnect'):
                    camera.disconnect()
            except:
                pass
            raise RuntimeError(f"Failed to connect to {camera_type} camera: {e}")

        return camera
    
    def _disconnect_camera(self) -> None:
        """Disconnect the active camera"""
        if self.active_camera:
            try:
                self.logger.info(f"Disconnecting {self.camera_type} camera...")
                self.active_camera.disconnect()
                self.logger.info("Camera disconnection successful")
            except Exception as e:
                self.logger.exception(f"Error disconnecting camera: {e}")
            
            self.active_camera = None
            self.camera_type = None
            self.logger.debug("Camera references cleared")
    
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
                "user_count": len(self.users),
                "development_mode": self.development_mode,
                "preferred_camera_type": self.preferred_camera_type,
                "actual_camera_class": self.active_camera.__class__.__name__ if self.active_camera else None
            }

    def set_development_mode(self, enabled: bool) -> None:
        """
        Enable or disable development mode

        Args:
            enabled: True to enable development mode, False to disable
        """
        with self.camera_lock:
            self.development_mode = enabled
            self.logger.info(f"Development mode {'enabled' if enabled else 'disabled'}")

    def set_preferred_camera_type(self, camera_type: str) -> None:
        """
        Set the preferred camera type for development mode

        Args:
            camera_type: Preferred camera type ('basler' or 'webcam')
        """
        if camera_type not in ["basler", "webcam"]:
            raise ValueError("Camera type must be 'basler' or 'webcam'")

        with self.camera_lock:
            self.preferred_camera_type = camera_type
            self.logger.info(f"Preferred camera type set to: {camera_type}")

            # If we have an active camera and it's different from the preferred type,
            # we might want to switch (but only if no users are active)
            if not self.users and self.active_camera:
                self.logger.info("No active users, considering camera switch...")
                self._disconnect_camera()

    def force_camera_type(self, camera_type: str, user_id: str) -> AbstractCamera:
        """
        Force the use of a specific camera type, disconnecting current camera if needed

        Args:
            camera_type: Type of camera to force ('basler' or 'webcam')
            user_id: ID of the component requesting the camera

        Returns:
            Camera instance

        Raises:
            ValueError: If camera type is unsupported
            RuntimeError: If camera cannot be created or connected
        """
        with self.camera_lock:
            # Disconnect current camera regardless of type
            if self.active_camera:
                self.logger.warning(f"Forcing camera switch to {camera_type}")
                self._disconnect_camera()
                self.users.clear()  # Clear all users since we're forcing a switch

            # Create new camera of the specified type
            try:
                self.active_camera = self._create_camera(camera_type)
                self.camera_type = camera_type
            except (ValueError, RuntimeError) as e:
                # Re-raise the exception to let the caller handle it
                self.logger.error(f"Failed to force switch to {camera_type} camera: {e}")
                raise

            # Register user
            self.users[user_id] = time.time()

            return self.active_camera

# Create a singleton instance
camera_manager = CameraManager() 