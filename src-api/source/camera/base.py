# source/lib/camera/base.py
from abc import ABC, abstractmethod
import numpy as np
import time
import os
from datetime import datetime
import cv2

class AbstractCamera(ABC):
    """
    Abstract base class for camera interfaces.
    Also provides a concrete dummy implementation for fallback use.
    """
    
    # These methods are no longer abstract since we provide concrete implementations
    def __init__(self):
        """Initialize dummy camera for fallback use"""
        self.connected = False
        self.mode = 'snapshot'
        self.save_directory = 'data/images/fallback'
        print("[DUMMY_CAMERA] Initialized dummy camera")
    
    def connect(self) -> bool:
        """Connect to dummy camera"""
        self.connected = True
        print("[DUMMY_CAMERA] Connected to dummy camera")
        return True
    
    def disconnect(self) -> bool:
        """Disconnect from dummy camera"""
        self.connected = False
        print("[DUMMY_CAMERA] Disconnected from dummy camera")
        return True
    
    def is_connected(self) -> bool:
        """Check if dummy camera is connected"""
        return self.connected
    
    def set_mode(self, mode: str) -> None:
        """Set dummy camera mode"""
        self.mode = mode
        print(f"[DUMMY_CAMERA] Set mode to {mode}")
    
    def get_frame(self) -> dict:
        """Get a dummy frame (black image)"""
        # Create a small black image as a placeholder
        height, width = 480, 640
        black_image = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Add text to indicate it's a dummy camera
        cv2.putText(
            black_image, 
            "No Camera Connected", 
            (width//2 - 150, height//2), 
            cv2.FONT_HERSHEY_SIMPLEX, 
            1, 
            (255, 255, 255), 
            2
        )
        
        return {
            "image": black_image,
            "timestamp": int(time.time() * 1000000)  # Microseconds
        }
    
    def write_frame(self, save_path: str = None) -> str:
        """Save a dummy frame"""
        frame = self.get_frame()["image"]
        
        # Create save path
        path = save_path or self.save_directory
        os.makedirs(path, exist_ok=True)
        
        # Create filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S%f")[:-3]
        filename = f"dummy_{timestamp}.jpg"
        full_path = os.path.join(path, filename)
        
        # Save image
        cv2.imwrite(full_path, frame)
        print(f"[DUMMY_CAMERA] Saved dummy frame to {full_path}")
        return full_path
    
    def set_params(self, params: dict) -> None:
        """Set dummy camera parameters"""
        if 'SaveDirectory' in params:
            self.save_directory = params['SaveDirectory']
        print(f"[DUMMY_CAMERA] Set parameters: {params}")
