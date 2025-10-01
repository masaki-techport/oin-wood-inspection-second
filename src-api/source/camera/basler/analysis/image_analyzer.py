"""
Image analysis functionality for BaslerCamera.
"""

import os
import time
import logging
import re
from datetime import datetime
from typing import Dict, Any, List, Optional

from db import Inspection, InspectionResult
from db.inspection_details import InspectionDetails
from db.engine import SessionLocal

# Import the new LengthCalculator class
from .length_calculator import LengthCalculator

logger = logging.getLogger('BaslerCamera.ImageAnalyzer')

# Configure performance metrics
PERFORMANCE_METRICS = {
    'inference_time': [],
    'db_operation_time': [],
}

class ImageAnalyzer:
    """Handles image analysis and database operations for inference results"""
    
    def __init__(self, camera_instance):
        """Initialize with a reference to the parent camera object"""
        self.camera = camera_instance
        self.length_calculator = LengthCalculator()
        
    def analyze_image(self, image_path: str, shared_inspection_id: int = None) -> Dict[str, Any]:
        """
        Analyze an image using the inference service and save results to database
        with optimized performance
        
        Args:
            image_path: Path to the image file
            shared_inspection_id: Optional inspection ID to use for all images in a batch
            
        Returns:
            Dict[str, Any]: Analysis results with database IDs
        """
        start_time = time.time()
        logger.info(f"🔍 Starting image analysis for: {image_path}")
        
        # Start timing measurement for image analysis
        timing_collector = getattr(self.camera, 'timing_collector', None)
        analysis_measurement_id = None
        if timing_collector:
            analysis_measurement_id = timing_collector.start_measurement(
                "image_analysis", 
                {"image_path": image_path, "shared_inspection_id": shared_inspection_id}
            )
        
        try:
            # Run inference on the image with performance tracking
            inference_start = time.time()
            logger.info(f"🔍 Running inference on image: {image_path}")
            
            # Start timing measurement for inference
            inference_measurement_id = None
            if timing_collector:
                inference_measurement_id = timing_collector.start_measurement(
                    "inference", 
                    {"image_path": image_path}
                )
            
            inference_results = self.camera.inference_service.predict_image(image_path)
            inference_time = time.time() - inference_start
            PERFORMANCE_METRICS['inference_time'].append(inference_time)
            logger.info(f"🔍 Inference completed in {inference_time:.3f}s")
            
            # End timing measurement for inference
            if timing_collector and inference_measurement_id:
                timing_collector.end_measurement("inference", inference_measurement_id)
            
            if not inference_results.get("success", False):
                logger.warning(f"Inference failed: {inference_results.get('error', 'Unknown error')}")
                return None
                
            # Extract detection results with minimal overhead
            detections = inference_results["results"]["detections"]
            
            # Optimized detection filtering
            threshold_as_decimal = self.camera.ai_threshold / 100.0
            confidence_above_threshold = False
            
            # Filter detections based on threshold - using list comprehension for better performance
            filtered_detections = []
            for detection in detections:
                confidence = detection["confidence"]
                if confidence >= threshold_as_decimal:
                    filtered_detections.append(detection)
                    confidence_above_threshold = True
                    logger.debug(f"Detection above threshold: class={detection['class_name']}, confidence={confidence:.3f}")
            
            # If no detections above threshold, minimal logging
            if not confidence_above_threshold:
                logger.info(f"No detections with confidence above threshold ({self.camera.ai_threshold}%)")
            
            # Japanese class names mapping
            japanese_class_names = {
                0: '変色',      # discoloration  
                1: '穴',        # hole
                2: '死に節',     # knot_dead
                3: '流れ節(死)', # flow_dead
                4: '流れ節(生)', # flow_live
                5: '生き節',     # knot_live
            }
            
            # Extract image number from filename
            image_no = None
            try:
                basename = os.path.basename(image_path)
                match = re.search(r'No_(\d{4})\.(bmp|jpg|png)', basename)
                if match:
                    image_no = int(match.group(1))
                    logger.debug(f"Extracted image number: {image_no} from filename: {basename}")
                else:
                    logger.debug(f"Could not extract image number from filename: {basename}")
            except Exception as e:
                logger.warning(f"Error extracting image number from {image_path}: {e}")
            
            # Prepare data structures for batch database operations
            db_operation_start = time.time()
            
            # Start timing measurement for database operations
            db_measurement_id = None
            if timing_collector:
                db_measurement_id = timing_collector.start_measurement(
                    "database_operations", 
                    {"image_path": image_path, "detection_count": len(filtered_detections)}
                )
            
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
                class_id = detection["class_id"]
                confidence = detection["confidence"]
                bbox = detection["bbox"]  # [x1, y1, x2, y2] format after xywh2xyxy conversion
                
                # Validate bbox format before processing
                if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
                    logger.error(f"Skipping detection with invalid bbox format: {bbox}")
                    continue
                
                # Calculate length using the new LengthCalculator class
                length = self.length_calculator.calculate_defect_length(bbox, image_path)
                
                if length is not None:
                    # Keep track of the maximum length across all detections
                    max_length = max(max_length, length)
                    
                    # Debug logging for length calculation
                    logger.debug(f"Detection class_id={class_id}, bbox={bbox}, calculated_length={length}, max_length_so_far={max_length}")
                else:
                    logger.warning(f"Failed to calculate length for detection class_id={class_id}, bbox={bbox}")
                    continue
                
                # Update result flags
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
                
                # Extract coordinates from bbox [x1, y1, x2, y2]
                x1, y1, x2, y2 = bbox
                
                # Calculate actual width and height from coordinates
                actual_width = x2 - x1
                actual_height = y2 - y1
                
                # Prepare detail record for batch insertion with all coordinates
                inspection_details.append({
                    'error_type': class_id,
                    'error_type_name': japanese_class_names.get(class_id, f"Unknown class {class_id}"),
                    'x_position': x1,
                    'y_position': y1,
                    'x2_position': x2,
                    'y2_position': y2,
                    'width': actual_width,
                    'height': actual_height,
                    'length': length,
                    'confidence': confidence,
                    'image_path': image_path,
                    'image_no': image_no  # Use the extracted image number
                })
            
            # Determine the inspection result using the LengthCalculator
            has_knots = result_flags['dead_knot'] or result_flags['knot'] or result_flags['tight_knot'] or result_flags['live_knot']
            inspection_result = self.length_calculator.determine_inspection_result(has_knots, max_length)
            logger.debug(f"Inspection result determined: {inspection_result}, has_knots={has_knots}, max_length={max_length}")
                
            inspection_data = {
                'ai_threshold': self.camera.ai_threshold,
                'folder_path': os.path.dirname(image_path),
                'status': True,  # Set status to True when inspection is completed (regardless of defects found)
                'results': inspection_result,
                'details': []
            }
            
            # Use optimized database operations
            inspection_id = None
            inspection_details_db = []
            
            # Database operations with retries for better resilience
            max_retries = 3
            for retry in range(max_retries):
                try:
                    with SessionLocal() as session:
                        # Transaction start
                        session.begin()
                        
                        # Handle existing or new inspection
                        if shared_inspection_id:
                            # Get the existing inspection
                            inspection = session.query(Inspection).get(shared_inspection_id)
                            if inspection:
                                logger.debug(f"Using shared inspection ID: {shared_inspection_id}")
                                inspection_id = shared_inspection_id
                                
                                # Update inspection status to True when inspection is completed (regardless of defects found)
                                inspection.status = True
                                
                                # Update results if we found defects that are more severe than current result
                                current_result = inspection.results or '無欠点'
                                new_result = inspection_data['results']
                                
                                # Priority: 節あり > こぶし > 無欠点
                                should_update_result = False
                                if current_result == '無欠点' and new_result in ['こぶし', '節あり']:
                                    should_update_result = True
                                elif current_result == 'こぶし' and new_result == '節あり':
                                    should_update_result = True
                                
                                if should_update_result:
                                    inspection.results = new_result
                                    logger.debug(f"Updated inspection results from '{current_result}' to '{new_result}'")
                            else:
                                # Create new inspection with prepared data
                                inspection = Inspection(
                                    ai_threshold=self.camera.ai_threshold,
                                    inspection_dt=datetime.now(),
                                    folder_path=os.path.dirname(image_path),
                                    status=True,  # Set status to True when inspection is completed
                                    results=inspection_data['results']
                                )
                                session.add(inspection)
                                session.flush()
                                inspection_id = inspection.inspection_id
                        else:
                            # Create new inspection with prepared data
                            inspection = Inspection(
                                ai_threshold=self.camera.ai_threshold,
                                inspection_dt=datetime.now(),
                                folder_path=os.path.dirname(image_path),
                                status=True,  # Set status to True when inspection is completed
                                results=inspection_data['results']
                            )
                            session.add(inspection)
                            session.flush()
                            inspection_id = inspection.inspection_id
                        
                        # Manage inspection result - get or create
                        inspection_result = session.query(InspectionResult).filter(
                            InspectionResult.inspection_id == inspection_id
                        ).first()
                        
                        # Query the maximum length from inspection_details for this inspection
                        try:
                            from sqlalchemy import func
                            max_details_length = session.query(
                                func.max(InspectionDetails.length)
                            ).filter(
                                InspectionDetails.inspection_id == inspection_id,
                                InspectionDetails.length.isnot(None)  # Exclude NULL values
                            ).scalar()
                            
                            if max_details_length is not None and max_details_length > 0:
                                logger.debug(f"Found maximum length {max_details_length} mm from inspection_details")
                                # Use this value if it's greater than our current max_length
                                if max_details_length > max_length:
                                    max_length = max_details_length
                                    logger.info(f"Updated max_length to {max_length} mm from inspection_details")
                        except Exception as e:
                            logger.warning(f"Error querying max length from inspection_details: {e}")
                        
                        if not inspection_result:
                            # Create new with all flags set properly
                            inspection_result = InspectionResult(
                                inspection_id=inspection_id,
                                length=max_length if filtered_detections else 0.0,  # Always use 0.0 instead of None to avoid NULL values
                                **result_flags
                            )
                            logger.debug(f"Created new InspectionResult with length={max_length if filtered_detections else 0.0} mm")
                            session.add(inspection_result)
                        else:
                            # Update existing flags (OR operation to keep existing true values)
                            for flag, value in result_flags.items():
                                if value:
                                    setattr(inspection_result, flag, True)
                            
                                                        # ENHANCED: Always ensure length is not NULL
                            if inspection_result.length is None:
                                # First priority: fix NULL values regardless of other conditions
                                inspection_result.length = max_length if filtered_detections and max_length > 0 else 0.0
                                logger.info(f"Fixed NULL length value for inspection {inspection_id}, set to {inspection_result.length} mm")
                            elif filtered_detections and max_length > 0 and max_length > inspection_result.length:
                                # Update only if we have a larger value
                                inspection_result.length = max_length
                                logger.debug(f"Updated inspection_result.length to {max_length} mm")
                            elif inspection_result.length == 0 and filtered_detections and max_length > 0:
                                # Special case: existing value is 0 but we have valid detections with length
                                inspection_result.length = max_length
                                logger.debug(f"Updated inspection_result.length from 0 to {max_length} mm")
                        
                        # True batch insert for all inspection details using bulk_save_objects
                        if inspection_details:
                            logger.debug(f"Batch inserting {len(inspection_details)} inspection details")
                            detail_objects = [
                                InspectionDetails(
                                    inspection_id=inspection_id,
                                    **detail_data
                                ) for detail_data in inspection_details
                            ]
                            session.bulk_save_objects(detail_objects)
                        
                        # Commit all changes in a single transaction
                        session.commit()
                        
                        # Only query details if needed
                        if len(filtered_detections) > 0:
                            # Use optimized query with projection for better performance
                            inspection_details_db = session.query(InspectionDetails).filter(
                                InspectionDetails.inspection_id == inspection_id
                            ).all()
                        
                        # Success - break retry loop
                        break
                        
                except Exception as db_error:
                    logger.error(f"Database error (attempt {retry+1}/{max_retries}): {db_error}")
                    if retry == max_retries - 1:
                        raise  # Re-raise on last attempt
                    time.sleep(0.2)  # Brief delay before retry
            
            # Track database operation time
            db_time = time.time() - db_operation_start
            PERFORMANCE_METRICS['db_operation_time'].append(db_time)
            
            # End timing measurement for database operations
            if timing_collector and db_measurement_id:
                timing_collector.end_measurement("database_operations", db_measurement_id)
            
            # Prepare optimized return data
            result_data = {
                "inspection_id": inspection_id,
                "detections": filtered_detections,
                "confidence_above_threshold": confidence_above_threshold,
                "ai_threshold": self.camera.ai_threshold,
                "results": inspection_data['results'],  # Include the results field
                "inspection_details": [
                    {
                        "id": detail.error_id,
                        "error_type": detail.error_type,
                        "error_type_name": detail.error_type_name,
                        "x_position": detail.x_position,
                        "y_position": detail.y_position,
                        "width": detail.width,
                        "height": detail.height,
                        "length": detail.length,
                        "confidence": detail.confidence,
                        "image_path": detail.image_path,
                        "image_no": detail.image_no,
                    }
                    for detail in inspection_details_db
                ]
            }
            
            # Log total time for analysis
            total_time = time.time() - start_time
            logger.info(f"🔍 Analysis completed in {total_time:.3f}s (inference: {inference_time:.3f}s, db: {db_time:.3f}s)")
            logger.info(f"🔍 Analysis result - inspection_id: {result_data.get('inspection_id')}, confidence_above_threshold: {result_data.get('confidence_above_threshold')}, results: {result_data.get('results')}")

            # Update timing session metadata with inspection_id (sequential path)
            try:
                if timing_collector and inspection_id:
                    timing_collector.set_session_metadata(inspection_id=inspection_id)
            except Exception:
                pass
            
            # End timing measurement for image analysis
            if timing_collector and analysis_measurement_id:
                timing_collector.end_measurement("image_analysis", analysis_measurement_id)
            
            return result_data
                
        except Exception as e:
            logger.error(f"Error analyzing image: {e}")
            # Track full failure time
            total_time = time.time() - start_time
            logger.error(f"Analysis failed after {total_time:.3f}s")
            return None
    
    def cleanup(self):
        """Clean up resources when the analyzer is being destroyed."""
        try:
            if hasattr(self, 'length_calculator'):
                self.length_calculator.cleanup()
                logger.debug("ImageAnalyzer cleanup completed")
        except Exception as e:
            logger.error(f"Error during ImageAnalyzer cleanup: {e}")
    
    def __del__(self):
        """Destructor to ensure proper cleanup of resources."""
        try:
            self.cleanup()
        except Exception:
            pass  # Ignore errors during destruction