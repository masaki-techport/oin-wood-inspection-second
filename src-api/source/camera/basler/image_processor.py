"""
Image processing utilities for Basler camera module.
"""

import cv2
import numpy as np
import logging
import os
from typing import Optional

logger = logging.getLogger('BaslerCamera.ImageProcessor')

class ImageProcessor:
    """Optimized image processing operations"""
    
    @staticmethod
    def enhance_image(image: np.ndarray, alpha: float = 1.1, beta: int = 5) -> np.ndarray:
        """Enhance image with optimized processing"""
        return cv2.convertScaleAbs(image, alpha=alpha, beta=beta)
    
    @staticmethod
    def rgb_to_bgr(image: np.ndarray) -> np.ndarray:
        """Convert RGB to BGR with memory optimization"""
        # This avoids a copy if possible
        return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    
    @staticmethod
    def save_image(image: np.ndarray, filepath: str, quality: int = 95) -> bool:
        """Save image with optimized settings"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            # Check if file extension is .bmp and save accordingly
            if filepath.lower().endswith('.bmp'):
                return cv2.imwrite(filepath, image)
            else:
                return cv2.imwrite(filepath, image, [cv2.IMWRITE_JPEG_QUALITY, quality])
        except Exception as e:
            logger.error(f"Error saving image: {e}")
            return False