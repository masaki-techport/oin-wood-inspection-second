"""
Basler camera module for wood inspection system.
Provides functionality for Basler industrial cameras with image buffering and AI inspection.
"""

from .camera import BaslerCamera, PYLON_AVAILABLE

__all__ = ['BaslerCamera', 'PYLON_AVAILABLE']