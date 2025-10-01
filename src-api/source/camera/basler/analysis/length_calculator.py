"""
Length Calculator for defect dimensions.

This module provides a centralized service for calculating physical dimensions
of detected defects using configurable resolution settings.
"""

import logging
import threading
from typing import Optional, Tuple, List, Dict, Any
import time # Added missing import for time.time()

# Import settings service for configurable thresholds and resolution values
try:
    from services.settings_service import get_current_length_threshold
    from services.config_settings_service import get_config_settings_service
except ImportError:
    # Fallback if settings service not available
    def get_current_length_threshold():
        return 10.0
    
    def get_config_settings_service():
        return None

logger = logging.getLogger('BaslerCamera.LengthCalculator')

class LengthCalculator:
    """
    Centralized service for calculating physical dimensions of detected defects.
    
    This class provides:
    - Pixel-to-millimeter conversion using configurable resolution settings
    - Thread-safe caching of resolution values
    - Validation of calculated dimensions
    - Consistent length calculation across different analyzers
    """
    
    def __init__(self):
        """Initialize the length calculator with thread-safe caching."""
        self._lock = threading.RLock()
        
        # Thread-safe resolution settings cache
        self._resolution_cache = {
            'horizontal_mm_per_pixel': None,
            'vertical_mm_per_pixel': None,
            'last_update': None,
            'cache_ttl': 60.0,  # 60 seconds cache TTL
            'refresh_in_progress': False,
            'subscribers_registered': False
        }
        
        # Initialize cache invalidation subscription
        self._setup_cache_invalidation()
    
    def calculate_defect_length(self, bbox: list, image_path: str = None) -> Optional[float]:
        """
        Calculate the physical length of a defect from its bounding box.
        
        Args:
            bbox: Bounding box in [x1, y1, x2, y2] format
            image_path: Optional image path for logging context
            
        Returns:
            Optional[float]: Physical length in millimeters, or None if calculation fails
        """
        try:
            # Validate bbox format
            if not self._validate_bbox(bbox):
                logger.error(f"Invalid bbox format for length calculation: {bbox}")
                return None
            
            # Extract coordinates and calculate pixel dimensions
            x1, y1, x2, y2 = bbox
            pixel_width = x2 - x1   # ①節の横方向のピクセル数
            pixel_height = y2 - y1  # ②節の縦方向のピクセル数
            
            # Validate calculated pixel dimensions
            if pixel_width <= 0 or pixel_height <= 0:
                logger.error(f"Invalid calculated pixel dimensions: width={pixel_width}, height={pixel_height}")
                return None
            
            # Convert to millimeters using resolution settings
            horizontal_length_mm, vertical_length_mm = self._calculate_physical_dimensions(
                pixel_width, pixel_height
            )
            
            if horizontal_length_mm is None or vertical_length_mm is None:
                return None
            
            # Use maximum dimension as length (as per requirements)
            length = max(horizontal_length_mm, vertical_length_mm)
            
            logger.debug(f"Length calculation: bbox={bbox}, pixels=({pixel_width}, {pixel_height}), "
                        f"mm=({horizontal_length_mm:.3f}, {vertical_length_mm:.3f}), final_length={length:.3f}")
            
            return length
            
        except Exception as e:
            logger.error(f"Error calculating defect length for bbox {bbox}: {e}")
            return None
    
    def calculate_max_length(self, detections: List[Dict[str, Any]]) -> float:
        """
        Calculate the maximum length from a list of detections.
        
        This method processes a list of detection dictionaries and returns the maximum
        length found among all detections. This is used by the parallel system and
        memory analysis system for consistent length calculation.
        
        Args:
            detections: List of detection dictionaries, each containing bbox and other data
            
        Returns:
            float: Maximum length in millimeters, or 0.0 if no valid detections
        """
        try:
            if not detections:
                logger.debug("No detections provided for max length calculation")
                return 0.0
            
            max_length = 0.0
            valid_detections = 0
            
            for detection in detections:
                try:
                    # Extract bbox from detection
                    bbox = detection.get('bbox', [])
                    if not bbox or len(bbox) != 4:
                        logger.debug(f"Skipping detection with invalid bbox: {bbox}")
                        continue
                    
                    # Calculate length for this detection
                    length = self.calculate_defect_length(bbox)
                    if length is not None and length > 0:
                        max_length = max(max_length, length)
                        valid_detections += 1
                        logger.debug(f"Detection length: {length:.3f}mm, current max: {max_length:.3f}mm")
                    else:
                        logger.debug(f"Invalid length calculated for detection: {length}")
                        
                except Exception as e:
                    logger.warning(f"Error processing detection for max length: {e}")
                    continue
            
            logger.debug(f"Max length calculation: {valid_detections} valid detections, max_length: {max_length:.3f}mm")
            return max_length
            
        except Exception as e:
            logger.error(f"Error calculating max length from detections: {e}")
            return 0.0
    
    def determine_inspection_result(self, has_knots: bool, max_length: float) -> str:
        """
        Determine inspection result based on knot detection and configurable length threshold.
        
        Args:
            has_knots: Whether any knots were detected
            max_length: Maximum length of detected defects in millimeters
            
        Returns:
            str: Inspection result string
        """
        try:
            # If no knots detected, return no defects
            if not has_knots:
                logger.info(f"No knots detected, result: 無欠点")
                return "無欠点"
            
            # Validate max_length to prevent null or invalid values
            if max_length is None or not isinstance(max_length, (int, float)) or max_length < 0:
                logger.warning(f"Invalid max_length: {max_length}, defaulting to 0")
                max_length = 0
            
            # Use configurable length threshold with comprehensive error handling
            try:
                length_threshold = get_current_length_threshold()
                
                # Validate the retrieved threshold
                if not isinstance(length_threshold, (int, float)) or length_threshold <= 0:
                    raise ValueError(f"Invalid length threshold from settings: {length_threshold}")
                
                logger.info(f"Classification: knots detected with length {max_length}mm, threshold: {length_threshold}mm")
                if max_length > length_threshold:
                    logger.info(f"Result: 節あり (length {max_length}mm > threshold {length_threshold}mm)")
                    return "節あり"
                else:
                    logger.info(f"Result: こぶし (length {max_length}mm <= threshold {length_threshold}mm)")
                    return "こぶし"
                
            except Exception as e:
                logger.warning(f"Error getting length threshold, using default 10.0: {e}")
                
                # Fallback to safe default threshold
                default_threshold = 10.0
                logger.info(f"Classification: knots detected with length {max_length}mm, default threshold: {default_threshold}mm")
                if max_length > default_threshold:
                    logger.info(f"Result: 節あり (length {max_length}mm > default threshold {default_threshold}mm)")
                    return "節あり"
                else:
                    logger.info(f"Result: こぶし (length {max_length}mm <= default threshold {default_threshold}mm)")
                    return "こぶし"
                
        except Exception as e:
            logger.error(f"Error determining inspection result: {e}")
            # Return safe default result - changed to こぶし as it's less severe than 節あり
            logger.info(f"Error in classification, defaulting to こぶし")
            return "こぶし"
    
    def _validate_bbox(self, bbox: list) -> bool:
        """
        Validate bbox format to ensure 4 elements and valid coordinates.
        
        Args:
            bbox: Bounding box in [x1, y1, x2, y2] format
            
        Returns:
            bool: True if bbox is valid, False otherwise
        """
        try:
            # Check if bbox has exactly 4 elements
            if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
                logger.error(f"Invalid bbox format: expected 4 elements, got {len(bbox) if isinstance(bbox, (list, tuple)) else 'non-list'}")
                return False
            
            # Extract coordinates
            x1, y1, x2, y2 = bbox
            
            # Check if all coordinates are numeric
            if not all(isinstance(coord, (int, float)) for coord in bbox):
                logger.error(f"Invalid bbox coordinates: all values must be numeric, got {bbox}")
                return False
            
            # Check if coordinates are valid (x2 > x1, y2 > y1)
            if x2 <= x1:
                logger.error(f"Invalid bbox: x2 ({x2}) must be greater than x1 ({x1})")
                return False
            
            if y2 <= y1:
                logger.error(f"Invalid bbox: y2 ({y2}) must be greater than y1 ({y1})")
                return False
            
            # Check if coordinates are non-negative
            if any(coord < 0 for coord in bbox):
                logger.error(f"Invalid bbox: coordinates must be non-negative, got {bbox}")
                return False
            
            logger.debug(f"Bbox validation passed: {bbox}")
            return True
            
        except Exception as e:
            logger.error(f"Error validating bbox {bbox}: {e}")
            return False
    
    def _validate_resolution_values(self, horizontal_mm_per_pixel: float, vertical_mm_per_pixel: float) -> bool:
        """
        Validate resolution values to ensure they are positive numbers.
        
        Args:
            horizontal_mm_per_pixel: Horizontal resolution value
            vertical_mm_per_pixel: Vertical resolution value
            
        Returns:
            bool: True if values are valid, False otherwise
        """
        try:
            # Check if values are numeric
            if not isinstance(horizontal_mm_per_pixel, (int, float)) or not isinstance(vertical_mm_per_pixel, (int, float)):
                logger.error(f"Invalid resolution values: must be numeric, got h={type(horizontal_mm_per_pixel)}, v={type(vertical_mm_per_pixel)}")
                return False
            
            # Check if values are positive
            if horizontal_mm_per_pixel <= 0:
                logger.error(f"Invalid horizontal resolution: must be positive, got {horizontal_mm_per_pixel}")
                return False
            
            if vertical_mm_per_pixel <= 0:
                logger.error(f"Invalid vertical resolution: must be positive, got {vertical_mm_per_pixel}")
                return False
            
            # Check for reasonable bounds (prevent extremely small or large values)
            if horizontal_mm_per_pixel < 0.001 or horizontal_mm_per_pixel > 100.0:
                logger.warning(f"Horizontal resolution value seems unreasonable: {horizontal_mm_per_pixel} mm/pixel")
            
            if vertical_mm_per_pixel < 0.001 or vertical_mm_per_pixel > 100.0:
                logger.warning(f"Vertical resolution value seems unreasonable: {vertical_mm_per_pixel} mm/pixel")
            
            logger.debug(f"Resolution validation passed: h={horizontal_mm_per_pixel}, v={vertical_mm_per_pixel}")
            return True
            
        except Exception as e:
            logger.error(f"Error validating resolution values h={horizontal_mm_per_pixel}, v={vertical_mm_per_pixel}: {e}")
            return False
    
    def _setup_cache_invalidation(self):
        """
        Set up cache invalidation mechanism by subscribing to settings changes.
        """
        try:
            if not self._resolution_cache['subscribers_registered']:
                config_service = get_config_settings_service()
                if config_service:
                    # Subscribe to resolution setting changes for cache invalidation
                    config_service.subscribe_to_changes(self._on_resolution_settings_changed)
                    self._resolution_cache['subscribers_registered'] = True
                    logger.debug("Subscribed to resolution settings changes for cache invalidation")
        except Exception as e:
            logger.warning(f"Failed to setup cache invalidation subscription: {e}")
    
    def _on_resolution_settings_changed(self, setting_name: str, new_value: any):
        """
        Callback for when resolution settings change - invalidates cache.
        
        Args:
            setting_name: Name of the changed setting
            new_value: New value of the setting
        """
        try:
            # Only invalidate cache for resolution-related settings
            if setting_name in ['horizontal_mm_per_pixel', 'vertical_mm_per_pixel']:
                with self._lock:
                    logger.info(f"Resolution setting changed: {setting_name}={new_value}, invalidating cache")
                    self._invalidate_resolution_cache()
        except Exception as e:
            logger.error(f"Error handling resolution settings change: {e}")
    
    def _invalidate_resolution_cache(self):
        """
        Invalidate the resolution settings cache (must be called with lock held).
        """
        self._resolution_cache['horizontal_mm_per_pixel'] = None
        self._resolution_cache['vertical_mm_per_pixel'] = None
        self._resolution_cache['last_update'] = None
        logger.debug("Resolution cache invalidated")
    
    def _refresh_resolution_cache_internal(self):
        """
        Internal method to refresh resolution cache (must be called with lock held).
        """
        try:
            # Prevent concurrent refreshes
            if self._resolution_cache['refresh_in_progress']:
                logger.debug("Cache refresh already in progress, skipping")
                return
            
            self._resolution_cache['refresh_in_progress'] = True
            
            config_service = get_config_settings_service()
            if config_service is None:
                raise Exception("Config service is not available")
            
            # Get fresh settings
            horizontal_mm_per_pixel = config_service.get_horizontal_mm_per_pixel()
            vertical_mm_per_pixel = config_service.get_vertical_mm_per_pixel()
            
            # Validate the retrieved values
            if not self._validate_resolution_values(horizontal_mm_per_pixel, vertical_mm_per_pixel):
                raise ValueError(f"Invalid resolution values from settings: h={horizontal_mm_per_pixel}, v={vertical_mm_per_pixel}")
            
            # Update cache
            self._resolution_cache['horizontal_mm_per_pixel'] = horizontal_mm_per_pixel
            self._resolution_cache['vertical_mm_per_pixel'] = vertical_mm_per_pixel
            self._resolution_cache['last_update'] = time.time()
            
            logger.debug(f"Resolution cache refreshed: h={horizontal_mm_per_pixel}, v={vertical_mm_per_pixel}")
            
        except Exception as e:
            logger.warning(f"Failed to refresh resolution cache: {e}")
        finally:
            self._resolution_cache['refresh_in_progress'] = False
    
    def _get_resolution_settings(self) -> Tuple[float, float]:
        """
        Get current resolution settings with thread-safe caching.
        Includes comprehensive error handling, validation, and fallback values.
        
        Returns:
            Tuple[float, float]: (horizontal_mm_per_pixel, vertical_mm_per_pixel)
        """
        with self._lock:
            current_time = time.time()
            
            # Check if cache is valid
            if (self._resolution_cache['last_update'] is not None and 
                current_time - self._resolution_cache['last_update'] < self._resolution_cache['cache_ttl'] and
                self._resolution_cache['horizontal_mm_per_pixel'] is not None and
                self._resolution_cache['vertical_mm_per_pixel'] is not None):
                
                logger.debug("Using cached resolution settings")
                return (
                    self._resolution_cache['horizontal_mm_per_pixel'],
                    self._resolution_cache['vertical_mm_per_pixel']
                )
            
            # Cache miss or expired - refresh from settings service
            try:
                logger.debug("Cache miss or expired, refreshing resolution settings")
                self._refresh_resolution_cache_internal()
                
                # Return cached values if refresh was successful
                if (self._resolution_cache['horizontal_mm_per_pixel'] is not None and
                    self._resolution_cache['vertical_mm_per_pixel'] is not None):
                    return (
                        self._resolution_cache['horizontal_mm_per_pixel'],
                        self._resolution_cache['vertical_mm_per_pixel']
                    )
                else:
                    raise Exception("Cache refresh failed, no valid values available")
                    
            except Exception as e:
                logger.error(f"Error refreshing resolution cache: {e}")
                
                # Fallback to direct service call
                try:
                    config_service = get_config_settings_service()
                    if config_service:
                        horizontal_mm_per_pixel = config_service.get_horizontal_mm_per_pixel()
                        vertical_mm_per_pixel = config_service.get_vertical_mm_per_pixel()
                        
                        if self._validate_resolution_values(horizontal_mm_per_pixel, vertical_mm_per_pixel):
                            logger.warning("Using direct service call as fallback")
                            return (horizontal_mm_per_pixel, vertical_mm_per_pixel)
                    
                    raise Exception("Direct service call also failed")
                    
                except Exception as fallback_error:
                    logger.error(f"Fallback service call failed: {fallback_error}")
                    
                    # Final fallback to safe default values
                    logger.warning("Using safe default resolution values as final fallback")
                    return (0.245833, 0.288889)  # Safe defaults
    
    def _calculate_physical_dimensions(self, pixel_width: float, pixel_height: float) -> Tuple[float, float]:
        """
        Convert pixel dimensions to physical dimensions using resolution settings.
        Includes comprehensive error handling and validation.
        
        Args:
            pixel_width: Width in pixels (①節の横方向のピクセル数)
            pixel_height: Height in pixels (②節の縦方向のピクセル数)
            
        Returns:
            Tuple[float, float]: (horizontal_length_mm, vertical_length_mm)
        """
        try:
            # Validate input pixel dimensions
            if not isinstance(pixel_width, (int, float)) or not isinstance(pixel_height, (int, float)):
                raise ValueError(f"Pixel dimensions must be numeric: width={type(pixel_width)}, height={type(pixel_height)}")
            
            if pixel_width < 0 or pixel_height < 0:
                raise ValueError(f"Pixel dimensions must be non-negative: width={pixel_width}, height={pixel_height}")
            
            if pixel_width == 0 and pixel_height == 0:
                logger.warning("Both pixel dimensions are zero, returning zero physical dimensions")
                return (0.0, 0.0)
            
            # Get current resolution settings (includes error handling and validation)
            horizontal_mm_per_pixel, vertical_mm_per_pixel = self._get_resolution_settings()
            
            # Double-check resolution values (defensive programming)
            if not self._validate_resolution_values(horizontal_mm_per_pixel, vertical_mm_per_pixel):
                raise ValueError(f"Invalid resolution values: h={horizontal_mm_per_pixel}, v={vertical_mm_per_pixel}")
            
            # Calculate physical dimensions using the formulas from requirements:
            # 節の横の長さ(mm) = ①×分解能_横
            # 節の縦の長さ(mm) = ②×分解能_縦
            horizontal_length_mm = pixel_width * horizontal_mm_per_pixel
            vertical_length_mm = pixel_height * vertical_mm_per_pixel
            
            # Validate calculated results
            if horizontal_length_mm < 0 or vertical_length_mm < 0:
                raise ValueError(f"Calculated dimensions are negative: h={horizontal_length_mm}, v={vertical_length_mm}")
            
            # No limit on maximum dimensions - allow any positive value
            logger.debug(f"Calculated dimensions: h={horizontal_length_mm}mm, v={vertical_length_mm}mm")
            
            logger.debug(f"Physical dimensions calculated: {pixel_width}px × {horizontal_mm_per_pixel} = {horizontal_length_mm}mm, "
                        f"{pixel_height}px × {vertical_mm_per_pixel} = {vertical_length_mm}mm")
            
            return (horizontal_length_mm, vertical_length_mm)
            
        except Exception as e:
            logger.error(f"Error calculating physical dimensions for pixels w={pixel_width}, h={pixel_height}: {e}")
            return (None, None)
    
    def cleanup(self):
        """
        Clean up resources (subscriptions).
        Should be called when the calculator is being destroyed.
        """
        try:
            with self._lock:
                # Unsubscribe from settings changes
                if self._resolution_cache['subscribers_registered']:
                    try:
                        config_service = get_config_settings_service()
                        if config_service:
                            config_service.unsubscribe_from_changes(self._on_resolution_settings_changed)
                        self._resolution_cache['subscribers_registered'] = False
                        logger.debug("Unsubscribed from resolution settings changes")
                    except Exception as e:
                        logger.warning(f"Error unsubscribing from settings changes: {e}")
                
                # Clear cache
                self._invalidate_resolution_cache()
                logger.debug("Length calculator cleanup completed")
                
        except Exception as e:
            logger.error(f"Error during length calculator cleanup: {e}")
    
    def __del__(self):
        """
        Destructor to ensure proper cleanup of resources.
        """
        try:
            self.cleanup()
        except Exception:
            pass  # Ignore errors during destruction
