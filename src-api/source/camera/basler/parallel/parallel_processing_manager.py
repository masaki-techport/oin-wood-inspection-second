"""
Parallel Processing Manager for Basler camera image analysis.

This module orchestrates parallel processing of images by coordinating
image distribution, thread management, and results consolidation.
"""

import os
import time
import logging
import threading
import multiprocessing
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from .image_distribution_manager import ImageDistributionManager
from .database_connection_pool import DatabaseConnectionPool
from .real_time_results_manager import RealTimeResultsManager
from .performance_monitor import PerformanceMonitor
from .resource_optimizer import ResourceOptimizer, OptimizationConfig

logger = logging.getLogger('BaslerCamera.ParallelProcessingManager')

class ParallelProcessingManager:
    """
    Main orchestrator for parallel image processing.
    
    Manages the entire parallel processing workflow including:
    - CPU core detection and thread optimization
    - Image distribution across processing groups
    - Database connection pooling
    - Real-time results management
    - Graceful fallback to sequential processing
    """
    
    def __init__(self, camera_instance):
        """
        Initialize the parallel processing manager.
        
        Args:
            camera_instance: Reference to the parent BaslerCamera object
        """
        self.camera = camera_instance
        self.enabled = True
        self.thread_count = self._detect_optimal_threads()
        
        # Initialize core components
        self.image_distributor = ImageDistributionManager()
        self.db_pool = DatabaseConnectionPool(pool_size=min(10, self.thread_count))
        self.results_manager = RealTimeResultsManager(camera_instance)

        # Initialize performance monitoring and resource optimization
        self.performance_monitor = PerformanceMonitor()
        self.resource_optimizer = ResourceOptimizer()

        # Performance tracking (legacy - kept for compatibility)
        self.performance_metrics = {
            'total_processing_time': [],
            'group_processing_times': {},
            'images_processed': 0,
            'parallel_efficiency': []
        }
        
        logger.info(f"ParallelProcessingManager initialized with {self.thread_count} threads")
        
    def _detect_optimal_threads(self) -> int:
        """
        Detect CPU cores and determine optimal thread count.

        Returns:
            int: Optimal thread count (5-15 threads)
        """
        try:
            # Use resource optimizer for more sophisticated detection
            if hasattr(self, 'resource_optimizer') and self.resource_optimizer:
                return self.resource_optimizer.get_optimal_thread_count()

            # Fallback to basic detection
            cpu_cores = multiprocessing.cpu_count()
            logger.info(f"Detected {cpu_cores} CPU cores")

            # Calculate optimal thread count
            # Use 1.5-2x CPU cores but constrain to 5-15 range
            optimal_threads = min(15, max(5, int(cpu_cores * 1.5)))

            # Adjust based on system memory (basic heuristic)
            try:
                import psutil
                memory_gb = psutil.virtual_memory().total / (1024**3)
                if memory_gb < 8:
                    optimal_threads = min(optimal_threads, 8)
                elif memory_gb > 16:
                    optimal_threads = min(15, optimal_threads + 2)
            except ImportError:
                logger.warning("psutil not available, using basic thread calculation")

            logger.info(f"Calculated optimal thread count: {optimal_threads}")
            return optimal_threads

        except Exception as e:
            logger.warning(f"Error detecting optimal threads: {e}, using default of 8")
            return 8
    
    def process_images_parallel(self, image_paths: List[str], shared_inspection_id: int = None) -> Dict[str, Any]:
        """
        Process images in parallel using multiple thread groups.
        
        This is the main entry point that replaces EventProcessor._analyze_saved_images()
        
        Args:
            image_paths: List of image file paths to process
            shared_inspection_id: Optional inspection ID to use for all images
            
        Returns:
            Dict[str, Any]: Consolidated processing results
        """
        if not self.enabled or not image_paths:
            logger.warning("Parallel processing disabled or no images to process")
            return self._fallback_to_sequential(image_paths, shared_inspection_id)
        
        start_time = time.time()
        logger.info(f"Starting parallel processing of {len(image_paths)} images")

        # Start performance monitoring session
        session_id = self.performance_monitor.start_processing_session(
            'parallel', len(image_paths), 5  # 5 groups A-E
        )

        try:
            # Create shared inspection ID if not provided
            if shared_inspection_id is None:
                # Analyze first image to get inspection ID (same as original logic)
                if image_paths:
                    logger.info(f"🔍 Creating shared inspection ID from first image: {image_paths[0]}")
                    first_result = self.camera._analyze_image(image_paths[0])
                    if first_result and 'inspection_id' in first_result:
                        shared_inspection_id = first_result['inspection_id']
                        logger.info(f"🔍 Created shared inspection ID: {shared_inspection_id}")
                        
                        # Save this result to camera for API access
                        self.camera.last_inspection_results = first_result
                        
                        # Save images to database
                        self.camera.event_processor._save_images_to_db(shared_inspection_id, image_paths)
                    else:
                        logger.warning(f"🔍 Failed to create inspection ID from first image")
                        return self._fallback_to_sequential(image_paths, shared_inspection_id)
            
            # Distribute images across processing groups
            distributed_images = self.image_distributor.distribute_images(image_paths)
            logger.info(f"Distributed {len(image_paths)} images across {len(distributed_images)} groups")
            
            # Create processing groups
            processing_groups = self.image_distributor.create_processing_groups(
                distributed_images, 
                threads_per_group=max(2, self.thread_count // 5)
            )
            
            # Initialize results tracking
            self.results_manager.initialize_processing(shared_inspection_id, processing_groups)
            
            # Process groups in parallel
            results = self._process_groups_parallel(processing_groups, shared_inspection_id)
            
            # Consolidate results
            final_result = self.results_manager.consolidate_results(results)
            
            # Update performance metrics
            total_time = time.time() - start_time
            self.performance_metrics['total_processing_time'].append(total_time)
            self.performance_metrics['images_processed'] += len(image_paths)

            # End performance monitoring session
            session_summary = self.performance_monitor.end_processing_session(session_id)

            logger.info(f"Parallel processing completed in {total_time:.3f}s for {len(image_paths)} images")
            logger.info(f"Performance: {session_summary.get('images_per_second', 0):.2f} images/sec")
            
            # Update camera status
            if final_result.get('confidence_above_threshold'):
                self.camera.save_message = f"検査完了: 欠点検出 (ID: {shared_inspection_id})"
            else:
                self.camera.save_message = f"検査完了: 欠点なし (ID: {shared_inspection_id})"
            
            # Start background thread for presentation processing
            if shared_inspection_id:
                presentation_thread = threading.Thread(
                    target=self.camera._process_presentation_images_background,
                    args=(shared_inspection_id, image_paths),
                    daemon=True
                )
                presentation_thread.start()
                logger.info(f"Started background thread for presentation images")
            
            return final_result
            
        except Exception as e:
            logger.error(f"Error in parallel processing: {e}")
            return self._fallback_to_sequential(image_paths, shared_inspection_id)
    
    def _process_groups_parallel(self, processing_groups: List, shared_inspection_id: int) -> List[Dict[str, Any]]:
        """
        Process multiple groups in parallel using ThreadPoolExecutor.
        
        Args:
            processing_groups: List of ProcessingGroup instances
            shared_inspection_id: Inspection ID for all images
            
        Returns:
            List[Dict[str, Any]]: Results from all groups
        """
        results = []
        
        with ThreadPoolExecutor(max_workers=len(processing_groups)) as executor:
            # Submit all group processing tasks
            future_to_group = {
                executor.submit(
                    group.process_group, 
                    shared_inspection_id, 
                    self.db_pool, 
                    self.results_manager
                ): group for group in processing_groups
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_group):
                group = future_to_group[future]
                try:
                    result = future.result()
                    results.append(result)
                    logger.info(f"Group {group.group_name} completed processing")
                except Exception as e:
                    logger.error(f"Group {group.group_name} failed: {e}")
                    # Continue processing other groups
        
        return results
    
    def _fallback_to_sequential(self, image_paths: List[str], shared_inspection_id: int = None) -> Dict[str, Any]:
        """
        Fallback to sequential processing when parallel processing fails.
        
        Args:
            image_paths: List of image paths to process
            shared_inspection_id: Optional inspection ID
            
        Returns:
            Dict[str, Any]: Processing results
        """
        logger.warning("Falling back to sequential processing")
        
        # Use the original sequential logic from EventProcessor
        self.camera.event_processor._analyze_saved_images_sequential(image_paths)
        return self.camera.last_inspection_results
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics for monitoring and optimization.

        Returns:
            Dict[str, Any]: Performance metrics
        """
        # Get comprehensive performance report
        performance_report = self.performance_monitor.generate_performance_report()
        optimization_summary = self.resource_optimizer.get_optimization_summary()

        # Legacy metrics for compatibility
        legacy_metrics = {}
        if self.performance_metrics['total_processing_time']:
            avg_time = sum(self.performance_metrics['total_processing_time']) / len(self.performance_metrics['total_processing_time'])
            legacy_metrics = {
                'enabled': self.enabled,
                'thread_count': self.thread_count,
                'average_processing_time': avg_time,
                'total_images_processed': self.performance_metrics['images_processed'],
                'group_performance': self.performance_metrics['group_processing_times']
            }

        # Combine all metrics
        return {
            'legacy_metrics': legacy_metrics,
            'performance_report': performance_report,
            'optimization_summary': optimization_summary,
            'current_thread_count': self.resource_optimizer.get_optimal_thread_count(),
            'memory_pressure': self.resource_optimizer.get_memory_pressure_level(),
            'system_load': self.resource_optimizer.get_system_load_level()
        }
    
    def enable_parallel_processing(self):
        """Enable parallel processing."""
        self.enabled = True
        logger.info("Parallel processing enabled")
    
    def disable_parallel_processing(self):
        """Disable parallel processing (fallback to sequential)."""
        self.enabled = False
        logger.info("Parallel processing disabled")
    
    def shutdown(self):
        """Shutdown the parallel processing manager and cleanup resources."""
        logger.info("Shutting down ParallelProcessingManager")

        if hasattr(self, 'db_pool'):
            self.db_pool.close_all_connections()

        if hasattr(self, 'resource_optimizer'):
            self.resource_optimizer.shutdown()

        logger.info("ParallelProcessingManager shutdown complete")
