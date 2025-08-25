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
            
            # Extract detection results with minimal overhead
            detections = inference_results["results"]["detections"]
            
            # Optimized detection filtering
            threshold_as_decimal = self.camera.ai_threshold / 100.0
            confidence_above_threshold = False
            
            # Filter detections based on threshold
            filtered_detections = []
            for detection in detections:
                confidence = detection["confidence"]
                if confidence >= threshold_as_decimal:
                    filtered_detections.append(detection)
                    confidence_above_threshold = True
                    logger.debug(f"[Thread-{thread_id}] Detection above threshold: class={detection['class_name']}, confidence={confidence:.3f}")
            
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
                class_id = detection["class_id"]
                confidence = detection["confidence"]
                bbox = detection["bbox"]  # [x, y, width, height]
                
                # Calculate length as the maximum of width and height, divided by 100
                length = max(bbox[2], bbox[3]) / 100
                max_length = max(max_length, length)
                
                # Map class_id to error type and name
                error_type_mapping = {
                    0: ('discoloration', '変色'),
                    1: ('hole', '穴'),
                    2: ('knot', '節'),
                    3: ('dead_knot', '死に節'),
                    4: ('live_knot', '流れ節_生'),
                    5: ('tight_knot', '生き節')
                }
                
                if class_id in error_type_mapping:
                    flag_name, error_type_name = error_type_mapping[class_id]
                    result_flags[flag_name] = True
                    
                    # Create inspection detail object
                    detail = InspectionDetails(
                        inspection_id=shared_inspection_id,
                        error_type=class_id,
                        error_type_name=error_type_name,
                        x_position=float(bbox[0]),
                        y_position=float(bbox[1]),
                        width=float(bbox[2]),
                        height=float(bbox[3]),
                        length=float(length),
                        confidence=float(confidence),
                        image_path=image_path,
                        image_no=image_no
                    )
                    inspection_details.append(detail)
            
            # Determine inspection result based on flags and length
            inspection_result = self._determine_inspection_result(result_flags, max_length)
            
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
                        "x_position": detail.x_position,
                        "y_position": detail.y_position,
                        "width": detail.width,
                        "height": detail.height,
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
    
    def _determine_inspection_result(self, result_flags: Dict[str, bool], max_length: float) -> str:
        """
        Determine inspection result based on flags and length.
        
        Args:
            result_flags: Dictionary of detection flags
            max_length: Maximum length of detected defects
            
        Returns:
            str: Inspection result string
        """
        if not any(result_flags.values()):
            return "無欠点"
        elif result_flags['knot'] or result_flags['dead_knot'] or result_flags['live_knot'] or result_flags['tight_knot']:
            if max_length > 1.5:
                return "こぶし"
            else:
                return "節あり"
        else:
            return "節あり"
    
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
                if result:
                    # Update existing result
                    for flag_name, flag_value in result_flags.items():
                        if flag_value:  # Only update if flag is True
                            setattr(result, flag_name, flag_value)
                    if max_length > 0:
                        result.length = int(max_length * 100)  # Convert to mm
                else:
                    # Create new result
                    result = InspectionResult(
                        inspection_id=inspection_id,
                        length=int(max_length * 100) if max_length > 0 else None,
                        **result_flags
                    )
                    session.add(result)
                
                # Update inspection record
                inspection = session.query(Inspection).filter_by(inspection_id=inspection_id).first()
                if inspection:
                    inspection.results = inspection_result
                
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
