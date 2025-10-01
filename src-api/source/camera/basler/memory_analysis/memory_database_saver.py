"""
Memory Database Saver for memory analysis system.

This module provides database saving capabilities for the memory analysis system,
similar to the parallel system's database operations but optimized for memory-based
analysis results.
"""

import logging
import threading
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

from db.engine import SessionLocal
from db import Inspection, InspectionResult
from db.inspection_details import InspectionDetails

logger = logging.getLogger('BaslerCamera.MemoryDatabaseSaver')

class MemoryDatabaseSaver:
    """
    Database saver for memory analysis results.
    
    Handles saving of inspection details and results from memory analysis
    to the database using the same patterns as the parallel system.
    """
    
    def __init__(self, camera_instance):
        """
        Initialize the memory database saver.
        
        Args:
            camera_instance: Reference to the parent BaslerCamera object
        """
        self.camera = camera_instance
        self._lock = threading.Lock()
        
        logger.info("MemoryDatabaseSaver initialized")
    
    def save_analysis_results(self, inspection_id: int, analysis_results: List[Any]) -> bool:
        """
        Save analysis results from memory analysis to database.
        
        Args:
            inspection_id: Inspection ID to associate results with
            analysis_results: List of AnalysisResult objects from memory analysis
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info(f"Saving {len(analysis_results)} analysis results to database for inspection {inspection_id}")
            
            # Convert analysis results to inspection details
            inspection_details = []
            result_flags = {
                'discoloration': False,
                'hole': False,
                'knot': False,
                'dead_knot': False,
                'live_knot': False,
                'tight_knot': False
            }
            max_length = 0.0
            
            for result in analysis_results:
                if not hasattr(result, 'detections') or not result.detections:
                    continue
                
                # Process each detection in the result
                for detection in result.detections:
                    try:
                        # Extract detection data
                        class_id = detection.get('class_id', -1)
                        confidence = detection.get('confidence', 0.0)
                        bbox = detection.get('bbox', [0, 0, 0, 0])
                        length = detection.get('length', 0.0)
                        image_path = getattr(result, 'image_path', '')
                        image_no = getattr(result, 'image_index', 0)
                        
                        # Validate bbox format
                        if not self._validate_bbox(bbox):
                            logger.warning(f"Invalid bbox format: {bbox}")
                            continue
                        
                        # Calculate dimensions
                        pixel_width = bbox[2] - bbox[0]   # x2 - x1
                        pixel_height = bbox[3] - bbox[1]  # y2 - y1
                        
                        # Map class_id to error type and name (same as parallel system)
                        error_type_mapping = {
                            0: ('discoloration', '変色'),      # discoloration
                            1: ('hole', '穴'),                # hole
                            2: ('dead_knot', '死に節'),        # knot_dead -> dead_knot flag
                            3: ('dead_knot', '流れ節(死)'),     # flow_dead -> dead_knot flag
                            4: ('live_knot', '流れ節(生)'),     # flow_live -> live_knot flag
                            5: ('tight_knot', '生き節')        # knot_live -> tight_knot flag
                        }
                        
                        if class_id in error_type_mapping:
                            flag_name, error_type_name = error_type_mapping[class_id]
                            
                            # Update result flags (same logic as parallel system)
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
                            
                            # Only use length for knot-related defects (class_id 2,3,4,5) for max_length
                            if length is not None and class_id in [2, 3, 4, 5]:
                                max_length = max(max_length, length)
                            
                            # Create inspection detail object (same structure as parallel system)
                            detail = InspectionDetails(
                                inspection_id=inspection_id,
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
                            
                    except Exception as detection_error:
                        logger.error(f"Error processing detection {detection}: {detection_error}")
                        continue
            
            # Determine inspection result using LengthCalculator (same as parallel system)
            has_knots = result_flags.get('knot', False) or result_flags.get('dead_knot', False) or result_flags.get('live_knot', False) or result_flags.get('tight_knot', False)
            
            # Use LengthCalculator to determine result
            if hasattr(self.camera, 'length_calculator'):
                inspection_result = self.camera.length_calculator.determine_inspection_result(has_knots, max_length)
            else:
                # Fallback logic (same as parallel system)
                if has_knots:
                    if max_length >= 10.0:
                        inspection_result = "節あり"
                    else:
                        inspection_result = "こぶし"
                else:
                    inspection_result = "無欠点"
            
            logger.info(f"Determined inspection result: {inspection_result}, flags: {result_flags}, max_length: {max_length}")
            
            # Save to database
            success = self._save_to_database(inspection_id, inspection_details, result_flags, max_length, inspection_result)
            
            if success:
                logger.info(f"Successfully saved {len(inspection_details)} inspection details and result to database")
            else:
                logger.error("Failed to save analysis results to database")
            
            return success
            
        except Exception as e:
            logger.error(f"Error saving analysis results: {e}")
            return False
    
    def _save_to_database(self, inspection_id: int, inspection_details: List[InspectionDetails],
                         result_flags: Dict[str, bool], max_length: float, 
                         inspection_result: str) -> bool:
        """
        Save inspection details and results to database.
        
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
            with SessionLocal() as session:
                try:
                    # Save inspection details using bulk operations
                    if inspection_details:
                        session.bulk_save_objects(inspection_details)
                        logger.debug(f"Bulk saved {len(inspection_details)} inspection details")
                    
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
                    
                    # Update inspection record with final result and status
                    inspection = session.query(Inspection).filter_by(inspection_id=inspection_id).first()
                    if inspection:
                        inspection.results = inspection_result
                        # Set status to True when inspection is completed (regardless of defects found)
                        inspection.status = True
                        logger.info(f"Updated inspection result to '{inspection_result}' and status to {inspection.status} for inspection {inspection_id}")
                    
                    session.commit()
                    return True
                    
                except Exception as e:
                    session.rollback()
                    logger.error(f"Database error saving analysis results: {e}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error in _save_to_database: {e}")
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
