"""
Processing Group for parallel image analysis.

This module implements individual processing groups (A-E) that handle
parallel analysis of assigned images using dedicated thread pools
with error isolation and status tracking.
"""

import time
import logging
import threading
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum

from .parallel_image_analyzer import ParallelImageAnalyzer
from .database_connection_pool import DatabaseConnectionPool

logger = logging.getLogger('BaslerCamera.ProcessingGroup')

class GroupStatus(Enum):
    """Enumeration for processing group status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"

class ProcessingGroup:
    """
    Individual processing group for parallel image analysis.
    
    Each group (A-E) has:
    - Dedicated thread pool with 2-3 threads per group
    - Group status tracking (pending, processing, completed, error)
    - Error isolation so group failures don't affect other groups
    - Performance metrics collection
    """
    
    def __init__(self, group_name: str, image_paths: List[str], thread_pool_size: int = 2):
        """
        Initialize a processing group.
        
        Args:
            group_name: Group identifier (A, B, C, D, or E)
            image_paths: List of image paths assigned to this group
            thread_pool_size: Number of threads for this group's pool (2-3)
        """
        self.group_name = group_name
        self.image_paths = image_paths
        self.thread_pool_size = min(3, max(2, thread_pool_size))  # Constrain to 2-3 threads
        
        # Status tracking
        self.status = GroupStatus.PENDING
        self.start_time = None
        self.end_time = None
        self.error_message = None
        
        # Results tracking
        self.processed_images = 0
        self.successful_images = 0
        self.failed_images = 0
        self.results = []
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Performance metrics
        self.performance_metrics = {
            'processing_time': 0,
            'avg_time_per_image': 0,
            'throughput': 0,  # images per second
            'thread_utilization': 0
        }
        
        logger.info(f"ProcessingGroup {group_name} initialized with {len(image_paths)} images and {self.thread_pool_size} threads")
    
    def process_group(self, shared_inspection_id: int, db_pool: DatabaseConnectionPool, 
                     results_manager) -> Dict[str, Any]:
        """
        Process all images in this group using parallel threads.
        
        Args:
            shared_inspection_id: Inspection ID for all images in this group
            db_pool: Database connection pool for thread-safe operations
            results_manager: Real-time results manager for status updates
            
        Returns:
            Dict[str, Any]: Group processing results
        """
        self.start_time = time.time()
        
        with self._lock:
            self.status = GroupStatus.PROCESSING
        
        logger.info(f"Group {self.group_name} starting processing of {len(self.image_paths)} images")
        
        try:
            # Create parallel image analyzer for this group
            analyzer = ParallelImageAnalyzer(
                camera_instance=results_manager.camera,  # Get camera from results manager
                db_pool=db_pool
            )
            
            # Process images in parallel using ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=self.thread_pool_size, 
                                  thread_name_prefix=f"Group-{self.group_name}") as executor:
                
                # Submit all image processing tasks
                future_to_image = {
                    executor.submit(
                        analyzer.analyze_image_parallel,
                        image_path,
                        shared_inspection_id,
                        self.group_name
                    ): image_path for image_path in self.image_paths
                }
                
                # Collect results as they complete
                for future in as_completed(future_to_image):
                    image_path = future_to_image[future]
                    
                    try:
                        result = future.result()
                        
                        with self._lock:
                            self.processed_images += 1
                            
                            if result:
                                self.successful_images += 1
                                self.results.append(result)
                                logger.debug(f"Group {self.group_name} successfully processed: {image_path}")
                            else:
                                self.failed_images += 1
                                logger.warning(f"Group {self.group_name} failed to process: {image_path}")
                        
                        # Update real-time results
                        if results_manager:
                            results_manager.update_group_progress(
                                self.group_name, 
                                self.processed_images, 
                                len(self.image_paths),
                                result
                            )
                            
                    except Exception as e:
                        with self._lock:
                            self.processed_images += 1
                            self.failed_images += 1
                        
                        logger.error(f"Group {self.group_name} error processing {image_path}: {e}")
                        
                        # Update real-time results with error
                        if results_manager:
                            results_manager.update_group_progress(
                                self.group_name, 
                                self.processed_images, 
                                len(self.image_paths),
                                None
                            )
            
            # Calculate final status
            self.end_time = time.time()
            
            with self._lock:
                if self.failed_images == 0:
                    self.status = GroupStatus.COMPLETED
                elif self.successful_images > 0:
                    self.status = GroupStatus.COMPLETED  # Partial success still counts as completed
                    logger.warning(f"Group {self.group_name} completed with {self.failed_images} failures")
                else:
                    self.status = GroupStatus.ERROR
                    self.error_message = f"All {self.failed_images} images failed to process"
            
            # Calculate performance metrics
            self._calculate_performance_metrics()
            
            # Prepare group result
            group_result = self._prepare_group_result(shared_inspection_id, analyzer)
            
            logger.info(f"Group {self.group_name} completed: {self.successful_images}/{len(self.image_paths)} successful")
            
            return group_result
            
        except Exception as e:
            self.end_time = time.time()
            
            with self._lock:
                self.status = GroupStatus.ERROR
                self.error_message = str(e)
            
            logger.error(f"Group {self.group_name} processing failed: {e}")
            
            return {
                'group_name': self.group_name,
                'status': self.status.value,
                'error': str(e),
                'processed_images': self.processed_images,
                'total_images': len(self.image_paths)
            }
    
    def _calculate_performance_metrics(self):
        """Calculate performance metrics for this group."""
        if self.start_time and self.end_time:
            processing_time = self.end_time - self.start_time
            
            with self._lock:
                self.performance_metrics['processing_time'] = processing_time
                
                if self.processed_images > 0:
                    self.performance_metrics['avg_time_per_image'] = processing_time / self.processed_images
                    self.performance_metrics['throughput'] = self.processed_images / processing_time
                
                # Thread utilization (simplified metric)
                if len(self.image_paths) > 0:
                    ideal_time = processing_time / self.thread_pool_size
                    actual_time = processing_time
                    self.performance_metrics['thread_utilization'] = min(1.0, ideal_time / actual_time)
    
    def _prepare_group_result(self, shared_inspection_id: int, analyzer: ParallelImageAnalyzer) -> Dict[str, Any]:
        """
        Prepare the final result for this group.
        
        Args:
            shared_inspection_id: Inspection ID
            analyzer: The analyzer used for processing
            
        Returns:
            Dict[str, Any]: Group result data
        """
        with self._lock:
            # Consolidate detection results
            all_detections = []
            confidence_above_threshold = False
            
            for result in self.results:
                if result and result.get('detections'):
                    all_detections.extend(result['detections'])
                if result and result.get('confidence_above_threshold'):
                    confidence_above_threshold = True
            
            group_result = {
                'group_name': self.group_name,
                'inspection_id': shared_inspection_id,
                'status': self.status.value,
                'processed_images': self.processed_images,
                'successful_images': self.successful_images,
                'failed_images': self.failed_images,
                'total_images': len(self.image_paths),
                'detections': all_detections,
                'confidence_above_threshold': confidence_above_threshold,
                'performance_metrics': self.performance_metrics.copy(),
                'processing_time': self.performance_metrics['processing_time'],
                'error_message': self.error_message
            }
            
            return group_result
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current status of this processing group.
        
        Returns:
            Dict[str, Any]: Current group status
        """
        with self._lock:
            return {
                'group_name': self.group_name,
                'status': self.status.value,
                'processed_images': self.processed_images,
                'successful_images': self.successful_images,
                'failed_images': self.failed_images,
                'total_images': len(self.image_paths),
                'progress_percentage': (self.processed_images / len(self.image_paths) * 100) if self.image_paths else 0,
                'error_message': self.error_message,
                'performance_metrics': self.performance_metrics.copy()
            }
    
    def is_completed(self) -> bool:
        """
        Check if this group has completed processing.
        
        Returns:
            bool: True if completed (success or error), False if still processing
        """
        with self._lock:
            return self.status in [GroupStatus.COMPLETED, GroupStatus.ERROR]
    
    def is_successful(self) -> bool:
        """
        Check if this group completed successfully.
        
        Returns:
            bool: True if completed successfully, False otherwise
        """
        with self._lock:
            return self.status == GroupStatus.COMPLETED and self.successful_images > 0
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get performance summary for this group.
        
        Returns:
            Dict[str, Any]: Performance summary
        """
        with self._lock:
            return {
                'group_name': self.group_name,
                'thread_pool_size': self.thread_pool_size,
                'images_assigned': len(self.image_paths),
                'images_processed': self.processed_images,
                'success_rate': (self.successful_images / self.processed_images * 100) if self.processed_images > 0 else 0,
                'performance_metrics': self.performance_metrics.copy()
            }
