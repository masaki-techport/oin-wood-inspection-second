"""
Parallel Image Analyzer for thread-safe image analysis.

This module provides thread-safe image analysis capabilities that extend
the existing ImageAnalyzer logic with connection pool integration and
optimized database operations for parallel processing.
"""

import os
import time
import logging
import re
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional

from db import Inspection, InspectionResult
from db.inspection_details import InspectionDetails
from .database_connection_pool import DatabaseConnectionPool

# Import the new LengthCalculator class
from ..analysis.length_calculator import LengthCalculator

logger = logging.getLogger('BaslerCamera.ParallelImageAnalyzer')

# Thread-local storage for performance metrics
thread_local = threading.local()

class ParallelImageAnalyzer:
    """
    Thread-safe image analyzer for parallel processing.
    
    Extends the existing ImageAnalyzer.analyze_image() logic with:
    - Connection pool integration for database operations
    - Bulk database operations for better performance
    - Thread-safe operation with minimal locking
    - Optimized AI inference calls that don't block database operations
    """
    
    def __init__(self, camera_instance, db_pool: DatabaseConnectionPool):
        """
        Initialize the parallel image analyzer.
        
        Args:
            camera_instance: Reference to the parent BaslerCamera object
            db_pool: Database connection pool for thread-safe operations
        """
        self.camera = camera_instance
        self.db_pool = db_pool
        self._lock = threading.Lock()
        self.length_calculator = LengthCalculator()
        
        # Performance tracking (thread-safe)
        self.performance_metrics = {
            'inference_times': [],
            'db_operation_times': [],
            'total_analysis_times': [],
            'images_processed': 0
        }
        

        
    def analyze_image_parallel(self, image_path: str, shared_inspection_id: int, 
                             group_name: str = None) -> Dict[str, Any]:
        """
        Analyze an image in a thread-safe manner with connection pool integration.
        
        This method is based on the existing ImageAnalyzer.analyze_image() logic
        but optimized for parallel processing.
        
        Args:
            image_path: Path to the image file
            shared_inspection_id: Inspection ID to use for this image
            group_name: Processing group name (A-E) for tracking
            
        Returns:
            Dict[str, Any]: Analysis results with database IDs
        """
        start_time = time.time()
        thread_id = threading.get_ident()
        logger.info(f"🔍 [Thread-{thread_id}] [Group-{group_name}] Starting analysis: {os.path.basename(image_path)}")
        
        try:
            # Run inference on the image with performance tracking
            inference_start = time.time()
            logger.debug(f"🔍 [Thread-{thread_id}] Running inference on: {image_path}")
            inference_results = self.camera.inference_service.predict_image(image_path)
            inference_time = time.time() - inference_start
            
            # Store in thread-local storage to avoid locking
            if not hasattr(thread_local, 'inference_times'):
                thread_local.inference_times = []
            thread_local.inference_times.append(inference_time)
            
            logger.debug(f"🔍 [Thread-{thread_id}] Inference completed in {inference_time:.3f}s")
            
            if not inference_results.get("success", False):
                logger.warning(f"[Thread-{thread_id}] Inference failed: {inference_results.get('error', 'Unknown error')}")
                return None
            
            # Extract detection results with error handling
            try:
                detections = inference_results.get("results", {}).get("detections", [])
                if not isinstance(detections, list):
                    logger.error(f"[Thread-{thread_id}] Invalid detections format: expected list, got {type(detections)}")
                    return None
                logger.info(f"[Thread-{thread_id}] Received {len(detections)} detections from inference")
            except Exception as e:
                logger.error(f"[Thread-{thread_id}] Error extracting detections from inference results: {e}")
                return None
            
            # Optimized detection filtering with error handling
            try:
                threshold_as_decimal = self.camera.ai_threshold / 100.0
                if not 0 <= threshold_as_decimal <= 1:
                    logger.warning(f"[Thread-{thread_id}] Invalid AI threshold: {self.camera.ai_threshold}, using 0.5")
                    threshold_as_decimal = 0.5
                logger.info(f"[Thread-{thread_id}] Using AI threshold: {self.camera.ai_threshold}% ({threshold_as_decimal})")
            except Exception as e:
                logger.error(f"[Thread-{thread_id}] Error calculating threshold, using default 0.5: {e}")
                threshold_as_decimal = 0.5
            
            confidence_above_threshold = False
            
            # Filter detections based on threshold
            filtered_detections = []
            for detection in detections:
                try:
                    if not isinstance(detection, dict):
                        logger.warning(f"[Thread-{thread_id}] Skipping non-dict detection: {detection}")
                        continue
                    
                    confidence = detection.get("confidence")
                    if confidence is None or not isinstance(confidence, (int, float)):
                        logger.warning(f"[Thread-{thread_id}] Skipping detection with invalid confidence: {confidence}")
                        continue
                    
                    if confidence >= threshold_as_decimal:
                        filtered_detections.append(detection)
                        confidence_above_threshold = True
                        class_name = detection.get('class_name', 'unknown')
                        logger.info(f"[Thread-{thread_id}] Detection above threshold: class={class_name}, confidence={confidence:.3f}")
                    else:
                        class_name = detection.get('class_name', 'unknown')
                        logger.info(f"[Thread-{thread_id}] Detection below threshold: class={class_name}, confidence={confidence:.3f} < {threshold_as_decimal}")
                        
                except Exception as filter_error:
                    logger.error(f"[Thread-{thread_id}] Error filtering detection {detection}: {filter_error}")
                    continue
            
            # Log filtering results
            logger.info(f"[Thread-{thread_id}] Filtered {len(filtered_detections)} detections from {len(detections)} total detections")
            
            # Extract image number from filename
            image_no = self._extract_image_number(image_path)
            
            # Prepare data structures for batch database operations
            db_operation_start = time.time()
            
            # Prepare all inspection details for batch insertion
            inspection_details = []
            result_flags = {
                'discoloration': False,
                'hole': False,
                'knot': False,
                'dead_knot': False,
                'live_knot': False,
                'tight_knot': False
            }
            
            # Process all detections in a single pass
            max_length = 0
            for detection in filtered_detections:
                try:
                    # Validate detection data structure first
                    if not self._validate_detection_data(detection):
                        logger.error(f"Skipping detection with invalid data structure: {detection}")
                        continue
                    
                    class_id = detection["class_id"]
                    confidence = detection["confidence"]
                    bbox = detection["bbox"]  # [x1, y1, x2, y2] format after xywh2xyxy conversion
                    
                    # Validate bbox format before processing
                    if not self._validate_bbox(bbox):
                        logger.error(f"Skipping detection with invalid bbox: {bbox}")
                        continue
                    
                    # Correct bbox calculation: width = x2 - x1, height = y2 - y1
                    pixel_width = bbox[2] - bbox[0]   # x2 - x1 (①節の横方向のピクセル数)
                    pixel_height = bbox[3] - bbox[1]  # y2 - y1 (②節の縦方向のピクセル数)
                    
                    # Additional validation for calculated dimensions
                    if pixel_width <= 0 or pixel_height <= 0:
                        logger.error(f"Skipping detection with invalid calculated dimensions: width={pixel_width}, height={pixel_height}")
                        continue
                    
                    # Calculate length using the LengthCalculator class
                    length = self.length_calculator.calculate_defect_length(bbox, image_path)
                    
                    # Only use length for knot-related defects (class_id 2,3,4,5) for max_length calculation
                    # Discoloration (0) and holes (1) should not contribute to max_length
                    if length is not None and class_id in [2, 3, 4, 5]:  # Only knot types
                        max_length = max(max_length, length)
                        logger.debug(f"Updated max_length to {max_length}mm for knot type {class_id}")
                    elif length is not None:
                        logger.debug(f"Length calculated for non-knot type {class_id}: {length}mm (not used for max_length)")
                    else:
                        logger.warning(f"Failed to calculate length for detection, skipping")
                        continue
                    
                    # Map class_id to error type and name - FIXED TO MATCH ANALYSIS FOLDER
                    error_type_mapping = {
                        0: ('discoloration', '変色'),      # discoloration
                        1: ('hole', '穴'),                # hole
                        2: ('dead_knot', '死に節'),        # knot_dead -> dead_knot flag, correct Japanese name
                        3: ('dead_knot', '流れ節(死)'),     # flow_dead -> dead_knot flag, correct Japanese name
                        4: ('live_knot', '流れ節(生)'),     # flow_live -> live_knot flag, correct Japanese name
                        5: ('tight_knot', '生き節')        # knot_live -> tight_knot flag, correct Japanese name
                    }
                    
                    if class_id in error_type_mapping:
                        flag_name, error_type_name = error_type_mapping[class_id]
                        
                        # Update result flags - FIXED TO MATCH ANALYSIS FOLDER LOGIC
                        if class_id == 0:  # discoloration
                            result_flags['discoloration'] = True
                        elif class_id == 1:  # hole
                            result_flags['hole'] = True
                        elif class_id == 2:  # knot_dead
                            result_flags['dead_knot'] = True
                            result_flags['knot'] = True
                        elif class_id == 3:  # flow_dead
                            result_flags['dead_knot'] = True
                            result_flags['knot'] = True
                        elif class_id == 4:  # flow_live
                            result_flags['live_knot'] = True
                            result_flags['knot'] = True
                        elif class_id == 5:  # knot_live
                            result_flags['tight_knot'] = True
                            result_flags['knot'] = True
                        
                        try:
                            # Create inspection detail object with validation
                            # Store all four coordinates and calculated dimensions
                            detail = InspectionDetails(
                                inspection_id=shared_inspection_id,
                                error_type=class_id,
                                error_type_name=error_type_name,
                                x_position=float(bbox[0]),  # x1 (left-top)
                                y_position=float(bbox[1]),  # y1 (left-top)
                                x2_position=float(bbox[2]), # x2 (right-bottom)
                                y2_position=float(bbox[3]), # y2 (right-bottom)
                                width=float(pixel_width),   # Calculated: x2 - x1
                                height=float(pixel_height), # Calculated: y2 - y1
                                length=float(length),
                                confidence=float(confidence),
                                image_path=image_path,
                                image_no=image_no
                            )
                            inspection_details.append(detail)
                            
                        except Exception as detail_error:
                            logger.error(f"Error creating inspection detail for detection {detection}: {detail_error}")
                            # Continue processing - don't let one bad detail stop the whole analysis
                            continue
                    else:
                        logger.warning(f"Unknown class_id {class_id} in detection, skipping")
                        
                except Exception as detection_error:
                    logger.error(f"Error processing detection {detection}: {detection_error}")
                    # Continue processing other detections instead of failing completely
                    continue
            
            # Determine inspection result using the LengthCalculator
            has_knots = result_flags.get('knot', False) or result_flags.get('dead_knot', False) or result_flags.get('live_knot', False) or result_flags.get('tight_knot', False)
            inspection_result = self.length_calculator.determine_inspection_result(has_knots, max_length)
            logger.info(f"[Thread-{thread_id}] Inspection result: {inspection_result}, flags: {result_flags}, max_length: {max_length}")
            
            # Perform database operations using connection pool
            success = self._save_analysis_results_parallel(
                shared_inspection_id, 
                inspection_details, 
                result_flags, 
                max_length, 
                inspection_result
            )
            
            db_time = time.time() - db_operation_start
            
            if not success:
                logger.error(f"[Thread-{thread_id}] Database operations failed")
                return None
            
            # Prepare optimized return data
            result_data = {
                "inspection_id": shared_inspection_id,
                "detections": filtered_detections,
                "confidence_above_threshold": confidence_above_threshold,
                "ai_threshold": self.camera.ai_threshold,
                "results": inspection_result,
                "inspection_details": [
                    {
                        "error_type": detail.error_type,
                        "error_type_name": detail.error_type_name,
                        "x_position": detail.x_position,  # x1 (left-top)
                        "y_position": detail.y_position,  # y1 (left-top)
                        "x2_position": detail.x2_position, # x2 (right-bottom)
                        "y2_position": detail.y2_position, # y2 (right-bottom)
                        "width": detail.width,      # Calculated: x2 - x1
                        "height": detail.height,    # Calculated: y2 - y1
                        "length": detail.length,
                        "confidence": detail.confidence,
                        "image_path": detail.image_path,
                        "image_no": detail.image_no,
                    }
                    for detail in inspection_details
                ],
                "group_name": group_name,
                "thread_id": thread_id
            }
            
            # Log total time for analysis
            total_time = time.time() - start_time
            logger.info(f"🔍 [Thread-{thread_id}] [Group-{group_name}] Analysis completed in {total_time:.3f}s (inference: {inference_time:.3f}s, db: {db_time:.3f}s)")
            
            # Update performance metrics (thread-safe)
            with self._lock:
                self.performance_metrics['inference_times'].append(inference_time)
                self.performance_metrics['db_operation_times'].append(db_time)
                self.performance_metrics['total_analysis_times'].append(total_time)
                self.performance_metrics['images_processed'] += 1
            
            return result_data
            
        except Exception as e:
            total_time = time.time() - start_time
            logger.error(f"[Thread-{thread_id}] Error analyzing image: {e}")
            logger.error(f"[Thread-{thread_id}] Analysis failed after {total_time:.3f}s")
            return None
    
    def _extract_image_number(self, image_path: str) -> Optional[int]:
        """
        Extract image number from filename.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Optional[int]: Image number or None if not found
        """
        try:
            basename = os.path.basename(image_path)
            match = re.search(r'No_(\d{4})\.(bmp|jpg|png)', basename)
            if match:
                return int(match.group(1))
        except Exception as e:
            logger.warning(f"Error extracting image number from {image_path}: {e}")
        return None
    

    
    def _save_analysis_results_parallel(self, inspection_id: int, inspection_details: List[InspectionDetails],
                                      result_flags: Dict[str, bool], max_length: float, 
                                      inspection_result: str) -> bool:
        """
        Save analysis results using the connection pool for thread-safe operations.
        
        Args:
            inspection_id: Inspection ID
            inspection_details: List of inspection details to save
            result_flags: Result flags for inspection result
            max_length: Maximum length for inspection result
            inspection_result: Inspection result string
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Use bulk operations for better performance
            if inspection_details:
                success = self.db_pool.bulk_save_inspection_details(inspection_details)
                if not success:
                    logger.error("Failed to bulk save inspection details")
                    return False
            
            # Update inspection result using connection pool
            def update_inspection_result(session, inspection_id, result_flags, max_length, inspection_result):
                # Update or create inspection result
                result = session.query(InspectionResult).filter_by(inspection_id=inspection_id).first()
                
                # Query the maximum length from inspection_details for this inspection
                # Only consider knot-related defects (error_type 2,3,4,5) for max_length
                try:
                    from sqlalchemy import func
                    max_details_length = session.query(
                        func.max(InspectionDetails.length)
                    ).filter(
                        InspectionDetails.inspection_id == inspection_id,
                        InspectionDetails.length.isnot(None),  # Exclude NULL values
                        InspectionDetails.error_type.in_([2, 3, 4, 5])  # Only knot types
                    ).scalar()
                    
                    if max_details_length is not None and max_details_length > 0:
                        logger.debug(f"Found maximum knot length {max_details_length} mm from inspection_details")
                        # Use this value if it's greater than our current max_length
                        if max_details_length > max_length:
                            max_length = max_details_length
                            logger.info(f"Updated max_length to {max_length} mm from inspection_details (knot types only)")
                except Exception as e:
                    logger.warning(f"Error querying max knot length from inspection_details: {e}")
                if result:
                    # Update existing result flags and length
                    for flag_name, flag_value in result_flags.items():
                        if flag_value:  # Only update if flag is True
                            setattr(result, flag_name, flag_value)
                    
                    # ENHANCED: First priority is to fix NULL values
                    if result.length is None:
                        # Always fix NULL values first
                        result.length = max_length if max_length > 0 else 0.0
                        logger.info(f"Fixed NULL length value for inspection {inspection_id}, set to {result.length} mm")
                    elif max_length > 0 and (result.length == 0 or max_length > result.length):
                        # Update if we have a valid max_length that's greater than current
                        result.length = max_length
                        logger.debug(f"Updated length for inspection {inspection_id} to {max_length} mm")
                    else:
                        # Double-check that length is not NULL before continuing
                        if result.length is None:
                            result.length = 0.0
                            logger.warning(f"Found unexpected NULL length for inspection {inspection_id}, fixed to 0.0 mm")
                        else:
                            logger.debug(f"Keeping existing length {result.length} for inspection {inspection_id} (new max_length: {max_length})")
                else:
                    # Create new result with proper length value - always set a value to avoid NULL
                    result = InspectionResult(
                        inspection_id=inspection_id,
                        length=max_length,  # Always set a length value, even if it's 0
                        **result_flags
                    )
                    session.add(result)
                    logger.debug(f"Created new InspectionResult for inspection {inspection_id} with length {max_length} mm")

                # DO NOT update inspection.results here - it will be updated during consolidation
                # This prevents race conditions where different threads set different results

                session.commit()
                return True
            
            return self.db_pool.execute_with_retry(
                update_inspection_result, 
                inspection_id, 
                result_flags, 
                max_length, 
                inspection_result
            )
            
        except Exception as e:
            logger.error(f"Error saving analysis results: {e}")
            return False
    
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
    

    

    

    

    

    

    
    def cleanup(self):
        """Clean up resources when the analyzer is being destroyed."""
        try:
            if hasattr(self, 'length_calculator'):
                self.length_calculator.cleanup()
            logger.debug("ParallelImageAnalyzer cleanup completed")
        except Exception as e:
            logger.error(f"Error during ParallelImageAnalyzer cleanup: {e}")
    
    def __del__(self):
        """
        Destructor to ensure proper cleanup of cache resources.
        """
        try:
            self.cleanup()
        except Exception:
            pass  # Ignore errors during destruction
    

    
    def _validate_detection_data(self, detection: dict) -> bool:
        """
        Validate detection data structure to ensure all required fields are present.
        
        Args:
            detection: Detection dictionary from inference results
            
        Returns:
            bool: True if detection is valid, False otherwise
        """
        try:
            required_fields = ['class_id', 'confidence', 'bbox']
            
            # Check if all required fields are present
            for field in required_fields:
                if field not in detection:
                    logger.error(f"Missing required field '{field}' in detection: {detection}")
                    return False
            
            # Validate field types and values
            class_id = detection['class_id']
            if not isinstance(class_id, int) or class_id < 0:
                logger.error(f"Invalid class_id: expected non-negative integer, got {class_id}")
                return False
            
            confidence = detection['confidence']
            if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
                logger.error(f"Invalid confidence: expected float between 0-1, got {confidence}")
                return False
            
            # Bbox validation is handled separately by _validate_bbox
            return True
            
        except Exception as e:
            logger.error(f"Error validating detection data: {e}")
            return False
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics for this analyzer.
        
        Returns:
            Dict[str, Any]: Performance metrics
        """
        with self._lock:
            if not self.performance_metrics['total_analysis_times']:
                return {}
            
            return {
                'images_processed': self.performance_metrics['images_processed'],
                'avg_inference_time': sum(self.performance_metrics['inference_times']) / len(self.performance_metrics['inference_times']),
                'avg_db_time': sum(self.performance_metrics['db_operation_times']) / len(self.performance_metrics['db_operation_times']),
                'avg_total_time': sum(self.performance_metrics['total_analysis_times']) / len(self.performance_metrics['total_analysis_times']),
                'total_inference_time': sum(self.performance_metrics['inference_times']),
                'total_db_time': sum(self.performance_metrics['db_operation_times']),
                'total_analysis_time': sum(self.performance_metrics['total_analysis_times'])
            }
    

