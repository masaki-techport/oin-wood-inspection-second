"""
Real-Time Results Manager for parallel processing.

This module manages real-time updates and results consolidation from
multiple processing groups, providing immediate frontend notifications
and maintaining camera.last_inspection_results.
"""

import time
import logging
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger('BaslerCamera.RealTimeResultsManager')

class RealTimeResultsManager:
    """
    Manages real-time results and status updates for parallel processing.
    
    Provides:
    - Group status tracking and real-time updates
    - Results consolidation from multiple groups into final inspection result
    - Immediate frontend notification when each group completes processing
    - Updates to camera.last_inspection_results for API access
    """
    
    def __init__(self, camera_instance):
        """
        Initialize the real-time results manager.
        
        Args:
            camera_instance: Reference to the parent BaslerCamera object
        """
        self.camera = camera_instance
        self._lock = threading.Lock()
        
        # Processing state
        self.inspection_id = None
        self.processing_groups = {}  # group_name -> group_info
        self.group_results = {}      # group_name -> result_data
        self.processing_start_time = None
        self.processing_complete = False
        
        # Real-time status for API
        self.real_time_status = {
            'inspection_id': None,
            'total_groups': 0,
            'completed_groups': 0,
            'processing_groups': {},
            'overall_progress': 0,
            'estimated_completion': None,
            'status': 'idle'  # idle, processing, completed, error
        }
        
        # Consolidated results
        self.consolidated_result = None
        
    def initialize_processing(self, inspection_id: int, processing_groups: List):
        """
        Initialize processing tracking for a new inspection.
        
        Args:
            inspection_id: Inspection ID for this processing session
            processing_groups: List of ProcessingGroup instances
        """
        with self._lock:
            self.inspection_id = inspection_id
            self.processing_start_time = time.time()
            self.processing_complete = False
            self.consolidated_result = None
            
            # Initialize group tracking
            self.processing_groups = {}
            self.group_results = {}
            
            for group in processing_groups:
                self.processing_groups[group.group_name] = {
                    'total_images': len(group.image_paths),
                    'processed_images': 0,
                    'status': 'pending',
                    'start_time': None,
                    'completion_time': None
                }
            
            # Update real-time status
            self.real_time_status = {
                'inspection_id': inspection_id,
                'total_groups': len(processing_groups),
                'completed_groups': 0,
                'processing_groups': self.processing_groups.copy(),
                'overall_progress': 0,
                'estimated_completion': None,
                'status': 'processing'
            }
            
            # Update camera status immediately
            self.camera.last_inspection_results = {
                'inspection_id': inspection_id,
                'status': 'processing',
                'groups': self.processing_groups.copy(),
                'overall_progress': 0
            }
        
        logger.info(f"Initialized processing tracking for inspection {inspection_id} with {len(processing_groups)} groups")
    
    def update_group_progress(self, group_name: str, processed_images: int, 
                            total_images: int, latest_result: Optional[Dict[str, Any]]):
        """
        Update progress for a specific processing group.
        
        Args:
            group_name: Name of the processing group (A-E)
            processed_images: Number of images processed so far
            total_images: Total number of images in the group
            latest_result: Latest analysis result from the group
        """
        with self._lock:
            if group_name not in self.processing_groups:
                logger.warning(f"Unknown group {group_name} in progress update")
                return
            
            # Update group progress
            group_info = self.processing_groups[group_name]
            group_info['processed_images'] = processed_images
            
            # Update status
            if processed_images == 0:
                group_info['status'] = 'pending'
            elif processed_images < total_images:
                group_info['status'] = 'processing'
                if group_info['start_time'] is None:
                    group_info['start_time'] = time.time()
            else:
                group_info['status'] = 'completed'
                group_info['completion_time'] = time.time()
            
            # Store latest result
            if latest_result:
                self.group_results[group_name] = latest_result
            
            # Update overall progress
            total_processed = sum(info['processed_images'] for info in self.processing_groups.values())
            total_images_all = sum(info['total_images'] for info in self.processing_groups.values())
            overall_progress = (total_processed / total_images_all * 100) if total_images_all > 0 else 0
            
            completed_groups = sum(1 for info in self.processing_groups.values() if info['status'] == 'completed')
            
            # Update real-time status
            self.real_time_status.update({
                'completed_groups': completed_groups,
                'processing_groups': self.processing_groups.copy(),
                'overall_progress': overall_progress,
                'estimated_completion': self._estimate_completion_time()
            })
            
            # Update camera status for API access
            self.camera.last_inspection_results = {
                'inspection_id': self.inspection_id,
                'status': 'processing',
                'groups': self.processing_groups.copy(),
                'overall_progress': overall_progress,
                'completed_groups': completed_groups,
                'total_groups': self.real_time_status['total_groups']
            }
        
        logger.debug(f"Group {group_name} progress: {processed_images}/{total_images} ({overall_progress:.1f}% overall)")
    
    def consolidate_results(self, group_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Consolidate results from all processing groups into final inspection result.
        
        Args:
            group_results: List of results from all processing groups
            
        Returns:
            Dict[str, Any]: Consolidated final result
        """
        with self._lock:
            self.processing_complete = True
            processing_time = time.time() - self.processing_start_time if self.processing_start_time else 0
            
            # Consolidate all detections
            all_detections = []
            confidence_above_threshold = False
            successful_groups = 0
            total_processed_images = 0
            total_successful_images = 0
            
            for result in group_results:
                if result and result.get('status') == 'completed':
                    successful_groups += 1
                    
                    if result.get('detections'):
                        all_detections.extend(result['detections'])
                    
                    if result.get('confidence_above_threshold'):
                        confidence_above_threshold = True
                    
                    total_processed_images += result.get('processed_images', 0)
                    total_successful_images += result.get('successful_images', 0)
            
            # Determine overall inspection result and consolidated length
            max_length = 0.0  # Initialize with 0.0 instead of None to avoid NULL values
            if all_detections:
                # Check for specific defect types and lengths
                has_knots = any(d.get('class_name', '').lower() in ['knot', '節', 'dead_knot', 'live_knot', 'tight_knot']
                              for d in all_detections)
                
                # Get the maximum length from all detections that have a calculated length
                # Only consider knot-related defects (class_id 2,3,4,5) for max_length
                max_length = 0
                for d in all_detections:
                    if ('length' in d and isinstance(d['length'], (int, float)) and 
                        d.get('class_id') in [2, 3, 4, 5] and d['length'] > max_length):
                        max_length = d['length']
                        logger.debug(f"Updated max_length to {max_length}mm from knot detection class_id {d.get('class_id')}")
                    
                # If no length found in detections, check if any group results have a max_length
                if max_length == 0:
                    for result in group_results:
                        if result and isinstance(result.get('max_length'), (int, float)) and result['max_length'] > max_length:
                            max_length = result['max_length']
                            logger.debug(f"Updated max_length to {max_length}mm from group result")
                            
                logger.debug(f"Consolidated max_length: {max_length} mm")

                # Get the configurable length threshold from settings
                try:
                    from services.settings_service import get_current_length_threshold
                    length_threshold = get_current_length_threshold()
                    if not isinstance(length_threshold, (int, float)) or length_threshold <= 0:
                        logger.warning(f"Invalid length threshold from settings: {length_threshold}, using default 10.0")
                        length_threshold = 10.0
                except Exception as e:
                    logger.warning(f"Error getting length threshold from settings: {e}, using default 10.0")
                    length_threshold = 10.0
                
                # Improved classification logic based on defect types and length
                if has_knots:
                    # For knots, use length-based classification with configurable threshold
                    if max_length > length_threshold:
                        overall_result = "節あり"
                        logger.info(f"Classification: 節あり (knots with length {max_length}mm > threshold {length_threshold}mm)")
                    else:
                        overall_result = "こぶし"
                        logger.info(f"Classification: こぶし (knots with length {max_length}mm <= threshold {length_threshold}mm)")
                elif confidence_above_threshold:
                    # If confidence is above threshold but no knots (e.g., holes, discoloration)
                    # These are not classified by length, but still indicate defects
                    overall_result = "無欠点"
                    logger.info(f"Classification: 無欠点 (defects detected but no knots)")
                else:
                    # No defects detected
                    overall_result = "無欠点"
                    logger.info(f"Classification: 無欠点 (no defects detected)")
            else:
                overall_result = "無欠点"
            
            # Create consolidated result
            self.consolidated_result = {
                'inspection_id': self.inspection_id,
                'detections': all_detections,
                'confidence_above_threshold': confidence_above_threshold,
                'results': overall_result,
                'max_length': max_length,  # Add consolidated maximum length
                'processing_summary': {
                    'total_groups': len(group_results),
                    'successful_groups': successful_groups,
                    'total_processed_images': total_processed_images,
                    'total_successful_images': total_successful_images,
                    'processing_time': processing_time,
                    'parallel_efficiency': self._calculate_parallel_efficiency(group_results)
                },
                'group_results': group_results,
                'timestamp': datetime.now().isoformat()
            }
            
            # Update real-time status to completed
            self.real_time_status.update({
                'status': 'completed',
                'overall_progress': 100,
                'completion_time': time.time()
            })
            
            # Update camera with final results
            self.camera.last_inspection_results = self.consolidated_result.copy()
            
        logger.info(f"Consolidated results for inspection {self.inspection_id}: {overall_result} "
                   f"({successful_groups}/{len(group_results)} groups successful, "
                   f"{total_successful_images}/{total_processed_images} images processed)")
        
        return self.consolidated_result
    
    def _estimate_completion_time(self) -> Optional[float]:
        """
        Estimate completion time based on current progress.
        
        Returns:
            Optional[float]: Estimated completion timestamp or None
        """
        if not self.processing_start_time:
            return None
        
        current_time = time.time()
        elapsed_time = current_time - self.processing_start_time
        
        # Calculate progress
        total_processed = sum(info['processed_images'] for info in self.processing_groups.values())
        total_images = sum(info['total_images'] for info in self.processing_groups.values())
        
        if total_processed == 0 or total_images == 0:
            return None
        
        progress_ratio = total_processed / total_images
        if progress_ratio == 0:
            return None
        
        estimated_total_time = elapsed_time / progress_ratio
        estimated_completion = self.processing_start_time + estimated_total_time
        
        return estimated_completion
    
    def _calculate_parallel_efficiency(self, group_results: List[Dict[str, Any]]) -> float:
        """
        Calculate parallel processing efficiency.
        
        Args:
            group_results: Results from all processing groups
            
        Returns:
            float: Efficiency ratio (0.0 to 1.0)
        """
        if not group_results:
            return 0.0
        
        # Calculate total processing time if done sequentially
        total_images = sum(result.get('total_images', 0) for result in group_results)
        avg_time_per_image = 0
        
        valid_groups = [r for r in group_results if r.get('performance_metrics', {}).get('avg_time_per_image', 0) > 0]
        if valid_groups:
            avg_time_per_image = sum(r['performance_metrics']['avg_time_per_image'] for r in valid_groups) / len(valid_groups)
        
        if avg_time_per_image == 0 or total_images == 0:
            return 0.0
        
        estimated_sequential_time = total_images * avg_time_per_image
        actual_parallel_time = max((result.get('processing_time', 0) for result in group_results), default=0)
        
        if actual_parallel_time == 0:
            return 0.0
        
        efficiency = min(1.0, estimated_sequential_time / actual_parallel_time)
        return efficiency
    
    def get_real_time_status(self) -> Dict[str, Any]:
        """
        Get current real-time status for API access.
        
        Returns:
            Dict[str, Any]: Current real-time status
        """
        with self._lock:
            return self.real_time_status.copy()
    
    def get_group_status(self, group_name: str) -> Optional[Dict[str, Any]]:
        """
        Get status for a specific group.
        
        Args:
            group_name: Name of the group (A-E)
            
        Returns:
            Optional[Dict[str, Any]]: Group status or None if not found
        """
        with self._lock:
            if group_name in self.processing_groups:
                return self.processing_groups[group_name].copy()
            return None
    
    def is_processing_complete(self) -> bool:
        """
        Check if all processing is complete.
        
        Returns:
            bool: True if processing is complete, False otherwise
        """
        with self._lock:
            return self.processing_complete
    
    def reset(self):
        """Reset the results manager for a new processing session."""
        with self._lock:
            self.inspection_id = None
            self.processing_groups = {}
            self.group_results = {}
            self.processing_start_time = None
            self.processing_complete = False
            self.consolidated_result = None
            
            self.real_time_status = {
                'inspection_id': None,
                'total_groups': 0,
                'completed_groups': 0,
                'processing_groups': {},
                'overall_progress': 0,
                'estimated_completion': None,
                'status': 'idle'
            }
        
        logger.info("RealTimeResultsManager reset for new processing session")
