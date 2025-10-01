"""
Real-time analysis processor with worker threads.
"""

import threading
import time
import logging
import tempfile
import os
from typing import Optional, Dict, Any, List
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np

from .analysis_queue import AnalysisTask, AnalysisResult, MemoryAnalysisQueue
from .exceptions import AnalysisTaskError, WorkerError
from .memory_database_saver import MemoryDatabaseSaver
from ..analysis.length_calculator import LengthCalculator

logger = logging.getLogger('MemoryAnalysisProcessor')

class AnalysisWorker:
    """Individual analysis worker thread."""
    
    def __init__(self, worker_id: int, processor: 'MemoryAnalysisProcessor'):
        self.worker_id = worker_id
        self.processor = processor
        self.thread = None
        self.running = False
        
    def start(self) -> None:
        """Start worker thread."""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(
            target=self.run,
            daemon=True,
            name=f"AnalysisWorker-{self.worker_id}"
        )
        self.thread.start()
    
    def stop(self) -> None:
        """Stop worker thread."""
        self.running = False
    
    def run(self) -> None:
        """Main worker execution loop."""
        logger.info(f"Analysis worker {self.worker_id} started")
        
        while self.running and not self.processor.stop_event.is_set():
            try:
                # Get next task
                task = self.processor.queue.dequeue_task()
                
                if task is None:
                    # No tasks available, wait briefly
                    time.sleep(0.1)
                    continue
                
                # Process task
                try:
                    result = self.processor._process_single_task(task)
                    self.processor.queue.complete_task(task.task_id, result)
                    
                    logger.debug(f"Worker {self.worker_id} completed task {task.task_id} for image {task.image_index}")
                    
                except Exception as e:
                    # Handle analysis error
                    self.processor.error_handler.handle_analysis_failure(task, e)
                    
                    if task.can_retry():
                        # Retry task
                        self.processor.queue.retry_task(task.task_id)
                        logger.info(f"Worker {self.worker_id} retrying task {task.task_id}")
                    else:
                        # Mark as failed
                        self.processor.queue.fail_task(task.task_id, str(e))
                        logger.error(f"Worker {self.worker_id} failed task {task.task_id}: {e}")
                
            except Exception as e:
                logger.error(f"Error in worker {self.worker_id}: {e}")
                time.sleep(1)  # Brief delay before retry
        
        logger.info(f"Analysis worker {self.worker_id} stopped")

class ErrorHandler:
    """Error handling and recovery for analysis system."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.error_counts = {}
        self.last_error_time = {}
        
    def handle_analysis_failure(self, task: AnalysisTask, error: Exception) -> None:
        """Handle analysis failure with retry logic."""
        error_key = type(error).__name__
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        self.last_error_time[error_key] = time.time()
        
        logger.warning(f"Analysis failure for task {task.task_id}: {error}")
        
        # Check if we should retry
        if task.can_retry():
            # Calculate retry delay with exponential backoff
            delay = self.config.get('retry_delay', 1.0) * (2 ** task.retry_count)
            logger.info(f"Retrying task {task.task_id} in {delay:.1f}s")
        else:
            logger.error(f"Task {task.task_id} exceeded max retries")
    
    def handle_queue_overflow(self, queue: MemoryAnalysisQueue) -> None:
        """Handle queue overflow."""
        strategy = self.config.get('overflow_strategy', 'drop_oldest')
        
        if strategy == 'drop_oldest':
            queue._handle_queue_overflow()
        elif strategy == 'pause_capture':
            # Pause image capture temporarily
            logger.warning("Pausing image capture due to queue overflow")
            # Implementation would pause camera capture
        else:
            raise AnalysisTaskError("Queue overflow")
    
    def handle_memory_pressure(self, usage_mb: float) -> None:
        """Handle memory pressure."""
        limit_mb = self.config.get('memory_limit_mb', 512)
        
        if usage_mb > limit_mb:
            logger.warning(f"Memory pressure detected: {usage_mb:.1f}MB > {limit_mb}MB")
            # Trigger aggressive cleanup
            # Implementation would clean up old results

class PerformanceMonitor:
    """Performance monitoring for analysis system."""
    
    def __init__(self):
        self.metrics = {
            'total_tasks_processed': 0,
            'successful_tasks': 0,
            'failed_tasks': 0,
            'average_processing_time': 0.0,
            'processing_times': [],
            'cleanup_count': 0,
            'cleaned_tasks': 0,
            'memory_usage_mb': 0.0
        }
        self.history = []
        self.lock = threading.Lock()
    
    def record_task_completion(self, processing_time: float, success: bool) -> None:
        """Record task completion metrics."""
        with self.lock:
            self.metrics['total_tasks_processed'] += 1
            if success:
                self.metrics['successful_tasks'] += 1
            else:
                self.metrics['failed_tasks'] += 1
            
            # Update average processing time
            if processing_time > 0:
                self.metrics['processing_times'].append(processing_time)
                if len(self.metrics['processing_times']) > 1000:  # Keep last 1000
                    self.metrics['processing_times'].pop(0)
                
                if self.metrics['processing_times']:
                    self.metrics['average_processing_time'] = sum(self.metrics['processing_times']) / len(self.metrics['processing_times'])
            
            # Record in history
            self.history.append({
                'timestamp': time.time(),
                'processing_time': processing_time,
                'success': success
            })
            
            # Keep only last 1000 entries
            if len(self.history) > 1000:
                self.history.pop(0)
    
    def record_cleanup(self, cleaned_count: int) -> None:
        """Record cleanup operation."""
        with self.lock:
            self.metrics['cleanup_count'] += 1
            self.metrics['cleaned_tasks'] += cleaned_count
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics."""
        with self.lock:
            return self.metrics.copy()
    
    def get_historical_metrics(self, duration_seconds: int = 300) -> list:
        """Get historical metrics for specified duration."""
        cutoff_time = time.time() - duration_seconds
        
        with self.lock:
            return [entry for entry in self.history if entry['timestamp'] >= cutoff_time]

class MemoryAnalysisProcessor:
    """Real-time analysis processor for buffer images."""
    
    def __init__(self, camera_instance, queue: MemoryAnalysisQueue, 
                 worker_count: int = 4, config: Optional[Dict[str, Any]] = None):
        self.camera = camera_instance
        self.queue = queue
        # Derive worker count from settings temp_section_size
        try:
            from services.settings_service import get_settings_service
            self.worker_count = get_settings_service().get_temp_section_size()
        except Exception:
            self.worker_count = worker_count
        self.config = config or {}
        self.workers = []
        self.running = False
        self.stop_event = threading.Event()
        self.performance_monitor = PerformanceMonitor()
        self.error_handler = ErrorHandler(self.config)
        
        # Initialize database saver for saving analysis results
        self.database_saver = MemoryDatabaseSaver(camera_instance)
        
        # Ensure a resolution-aware LengthCalculator is available
        try:
            if hasattr(self.camera, 'length_calculator') and self.camera.length_calculator:
                self.length_calculator = self.camera.length_calculator
            else:
                self.length_calculator = LengthCalculator()
        except Exception:
            self.length_calculator = LengthCalculator()
        
        # Rate limiting based on IntervalTime from params.yaml
        self.interval_time_ms = self._get_interval_time()
        self.last_analysis_time = 0
    
    @property
    def is_running(self) -> bool:
        """Check if processor is running."""
        return self.running
    
    def _get_interval_time(self) -> float:
        """Get interval time from params.yaml in seconds."""
        try:
            import yaml
            import os
            import sys
            # Add source directory to path to import __init__
            source_dir = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..')
            if source_dir not in sys.path:
                sys.path.append(source_dir)
            from __init__ import PARAMS_CONFIG_FILE
            
            with open(PARAMS_CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                interval_ms = config.get('IntervalTime', 100)  # Default 100ms
                return interval_ms / 1000.0  # Convert to seconds
        except Exception as e:
            logger.warning(f"Could not read IntervalTime from params.yaml: {e}")
            return 0.1  # Default 100ms
        
        # Analysis settings
        self.analysis_timeout = self.config.get('analysis_timeout', 30.0)
        self.retry_attempts = self.config.get('retry_attempts', 3)
        self.retry_delay = self.config.get('retry_delay', 1.0)
        
    def start_processing(self) -> None:
        """Start analysis workers."""
        if self.running:
            logger.warning("Analysis processor already running")
            return
        
        self.running = True
        self.stop_event.clear()
        
        # Start worker threads
        for i in range(self.worker_count):
            worker = AnalysisWorker(i, self)
            worker.start()
            self.workers.append(worker)
        
        # Start cleanup thread
        self.cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True,
            name="AnalysisCleanup"
        )
        self.cleanup_thread.start()
        
        logger.info(f"Started analysis processor with {self.worker_count} workers")
    
    def stop_processing(self) -> None:
        """Stop analysis workers."""
        if not self.running:
            return
        
        self.running = False
        self.stop_event.set()
        
        # Stop all workers
        for worker in self.workers:
            worker.stop()
        
        # Wait for workers to finish
        for worker in self.workers:
            if worker.thread and worker.thread.is_alive():
                worker.thread.join(timeout=5.0)
        
        self.workers.clear()
        logger.info("Stopped analysis processor")
    
    def _cleanup_loop(self) -> None:
        """Background cleanup loop."""
        while self.running and not self.stop_event.is_set():
            try:
                # Cleanup old tasks
                cleaned_count = self.queue.cleanup_old_tasks()
                
                # Update performance metrics
                self.performance_monitor.record_cleanup(cleaned_count)
                
                # Sleep for cleanup interval
                time.sleep(self.config.get('cleanup_interval', 60))
                
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                time.sleep(10)  # Brief delay before retry
    
    def _analyze_image_memory_only(self, image_path: str) -> Dict[str, Any]:
        """Analyze image without saving to database (memory-only)."""
        try:
            # Run inference using the camera's inference service
            if hasattr(self.camera, 'inference_service') and self.camera.inference_service:
                # Get inference results
                inference_result = self.camera.inference_service.predict_image(image_path)
                if inference_result.get('success', False):
                    # FIX 1: Get detections from correct nested structure
                    raw_detections = inference_result.get('results', {}).get('detections', [])
                    logger.debug(f"Raw detections from inference: {len(raw_detections)} items")
                    
                    # FIX 2: Convert inference detections to analysis format
                    detections = self._convert_inference_detections(raw_detections)
                    logger.debug(f"Converted detections: {len(detections)} items")
                else:
                    logger.warning(f"Inference failed: {inference_result.get('error', 'Unknown error')}")
                    detections = []
                
                # Process detections
                confidence_above_threshold = False
                max_length = 0.0
                ai_threshold = getattr(self.camera, 'ai_threshold', 50)
                threshold_as_decimal = ai_threshold / 100.0  # Convert percentage to decimal
                
                if detections:
                    # Check if any detection has confidence above threshold
                    for detection in detections:
                        confidence = detection.get('confidence', 0)
                        if confidence >= threshold_as_decimal:  # Compare with decimal threshold
                            confidence_above_threshold = True
                            logger.debug(f"Detection above threshold: confidence={confidence:.3f} >= {threshold_as_decimal:.3f}")
                            break
                    
                    # Calculate max length using length calculator (same as parallel system)
                    try:
                        max_length = (
                            self.camera.length_calculator.calculate_max_length(detections)
                            if hasattr(self.camera, 'length_calculator') and self.camera.length_calculator
                            else self.length_calculator.calculate_max_length(detections)
                        )
                    except Exception:
                        # Final fallback: scan any precomputed 'length' values
                        max_length = max((d.get('length', 0.0) for d in detections), default=0.0)
                
                # Determine result using the same logic as LengthCalculator
                if confidence_above_threshold:
                    # Check if any detections are knots (class_id 2,3,4,5)
                    has_knots = False
                    for detection in detections:
                        class_id = detection.get('class_id', -1)
                        if class_id in [2, 3, 4, 5]:  # knot_dead, flow_dead, flow_live, knot_live
                            has_knots = True
                            break
                    
                    if has_knots:
                        # Use length threshold to determine 節あり vs こぶし
                        try:
                            from services.settings_service import get_current_length_threshold
                            length_threshold = get_current_length_threshold()
                            if max_length > length_threshold:
                                results = "節あり"
                            else:
                                results = "こぶし"
                        except Exception as e:
                            logger.warning(f"Error getting length threshold: {e}, defaulting to こぶし")
                            results = "こぶし"
                    else:
                        # Non-knot defects (discoloration, hole)
                        results = "こぶし"
                else:
                    results = "無欠点"  # No defect
                
                logger.debug(f"Analysis result: {results}, confidence_above: {confidence_above_threshold}, max_length: {max_length}")
                
                return {
                    'detections': detections,
                    'confidence_above_threshold': confidence_above_threshold,
                    'max_length': max_length,
                    'results': results,
                    'ai_threshold': ai_threshold
                }
            else:
                logger.warning("No inference service available")
                return {
                    'detections': [],
                    'confidence_above_threshold': False,
                    'max_length': 0.0,
                    'results': '無欠点',
                    'ai_threshold': 50
                }
                
        except Exception as e:
            logger.error(f"Error in memory-only analysis: {e}")
            return {
                'detections': [],
                'confidence_above_threshold': False,
                'max_length': 0.0,
                'results': '無欠点',
                'ai_threshold': 50
            }
    
    def _convert_inference_detections(self, raw_detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert inference service detections to analysis format."""
        converted_detections = []
        
        for detection in raw_detections:
                try:
                    # FIX 2: Map class_id to error_type
                    class_id = detection.get('class_id', 0)
                    error_type = self._map_class_id_to_error_type(class_id)
                    
                        # FIX 3: Convert confidence from 0.0-1.0 to 0-100
                    confidence = detection.get('confidence', 0.0) * 100
                
                    # FIX 4: Calculate length from bbox using centralized calculator (mm)
                    bbox = detection.get('bbox', [0, 0, 0, 0])
                    try:
                        if hasattr(self.camera, 'length_calculator') and self.camera.length_calculator:
                            length = self.camera.length_calculator.calculate_defect_length(bbox)
                        else:
                            length = self.length_calculator.calculate_defect_length(bbox)
                    except Exception:
                        length = None
                
                    converted_detection = {
                        'error_type': error_type,
                        'confidence': confidence,
                        'length': length,
                        'bbox': bbox,
                        'class_id': class_id,
                        'class_name': detection.get('class_name', 'Unknown')
                    }
                    
                    converted_detections.append(converted_detection)
                    logger.debug(f"Converted detection: class_id={class_id} → error_type={error_type}, "
                            f"confidence={confidence:.1f}%, length={length:.1f}mm")
                
                except Exception as e:
                    logger.error(f"Error converting detection: {e}")
                    continue
        
        return converted_detections
    
    def _map_class_id_to_error_type(self, class_id: int) -> int:
        """Map inference class_id to analysis error_type."""
        # Mapping from inference service class_id to analysis error_type
        class_to_error_mapping = {
            0: 5,  # discoloration (変色) → error_type 5
            1: 4,  # hole (穴) → error_type 4  
            2: 2,  # knot_dead (死に節) → error_type 2
            3: 3,  # flow_dead (流れ節(死)) → error_type 3
            4: 3,  # flow_live (流れ節(生)) → error_type 3
            5: 2,  # knot_live (生き節) → error_type 2
        }
        return class_to_error_mapping.get(class_id, 0)
    
    def _calculate_length_from_bbox(self, bbox: List[float]) -> float:
        """Calculate physical length from bbox using LengthCalculator (mm)."""
        try:
            if hasattr(self.camera, 'length_calculator') and self.camera.length_calculator:
                length = self.camera.length_calculator.calculate_defect_length(bbox)
            else:
                length = self.length_calculator.calculate_defect_length(bbox)
            return float(length) if length is not None else 0.0
        except Exception:
            return 0.0
    
    def _process_single_task(self, task: AnalysisTask) -> AnalysisResult:
        """Process a single analysis task."""
        start_time = time.time()
        
        # Start timing measurement for memory analysis
        timing_collector = getattr(self.camera, 'timing_collector', None)
        memory_analysis_measurement_id = None
        if timing_collector:
            memory_analysis_measurement_id = timing_collector.start_measurement(
                "memory_analysis", 
                {"image_index": task.image_index, "task_id": task.task_id}
            )
        
        # Rate limiting is now handled at buffer level
        
        try:
            # Run analysis using memory-only method directly on ndarray (no temp files)
            try:
                # Start timing measurement for memory inference
                memory_inference_measurement_id = None
                if timing_collector:
                    memory_inference_measurement_id = timing_collector.start_measurement(
                        "memory_inference", 
                        {"image_index": task.image_index}
                    )
                
                if hasattr(self.camera, 'inference_service') and self.camera.inference_service:
                    # Pass RGB directly. Inference now expects RGB to avoid double conversions.
                    inference_result = self.camera.inference_service.predict_array(task.image_data)
                else:
                    inference_result = {"success": False, "results": {"detections": []}}
                
                # End timing measurement for memory inference and attribute to memory_analysis
                if timing_collector and memory_inference_measurement_id:
                    inference_duration = timing_collector.end_measurement("memory_inference", memory_inference_measurement_id)
                    try:
                        # Attach inference duration as breakdown to the last memory_analysis measurement
                        if self.camera and hasattr(self.camera, 'timing_collector') and self.camera.timing_collector.current_session:
                            ms = self.camera.timing_collector.current_session.measurements
                            if ms and ms[-1].operation_name == "memory_analysis":
                                ms[-1].metadata = ms[-1].metadata or {}
                                ms[-1].metadata["inference_duration"] = inference_duration
                    except Exception:
                        pass
                    
            except Exception as e:
                logger.warning(f"Inference call failed: {e}")
                inference_result = {"success": False, "results": {"detections": []}}
                
                # End timing measurement for memory inference on error
                if timing_collector and memory_inference_measurement_id:
                    timing_collector.end_measurement("memory_inference", memory_inference_measurement_id)

            # Adapt existing analyzer to accept results
            def _analyze_from_inference(inf_res):
                try:
                    raw_detections = inf_res.get('results', {}).get('detections', []) if inf_res.get('success') else []
                    detections = self._convert_inference_detections(raw_detections)
                    confidence_above_threshold = any(d.get('confidence', 0) > getattr(self.camera, 'ai_threshold', 50) for d in detections)
                    try:
                        max_length = (
                            self.camera.length_calculator.calculate_max_length(detections)
                            if hasattr(self.camera, 'length_calculator') and self.camera.length_calculator
                            else self.length_calculator.calculate_max_length(detections)
                        )
                    except Exception:
                        max_length = max((d.get('length', 0.0) for d in detections), default=0.0)
                    return {
                        'detections': detections,
                        'confidence_above_threshold': confidence_above_threshold,
                        'max_length': max_length,
                        'results': '欠点あり' if confidence_above_threshold else '無欠点',
                        'ai_threshold': getattr(self.camera, 'ai_threshold', 50)
                    }
                except Exception as e:
                    logger.warning(f"Analyze from inference failed: {e}")
                    return {
                        'detections': [],
                        'confidence_above_threshold': False,
                        'max_length': 0.0,
                        'results': '無欠点',
                        'ai_threshold': getattr(self.camera, 'ai_threshold', 50)
                    }

            analysis_result = _analyze_from_inference(inference_result)

            # Put JPEG preview to in-memory cache only (no disk)
            saved_preview_rel_path = None
            try:
                import cv2  # type: ignore
                from services import memory_image_cache
                # Encode preview directly from RGB; OpenCV expects BGR, but for preview
                # color fidelity is not critical. Convert cheaply.
                img_bgr_for_jpg = cv2.cvtColor(task.image_data, cv2.COLOR_RGB2BGR)
                ok, buf = cv2.imencode('.jpg', img_bgr_for_jpg, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                if ok:
                    memory_image_cache.put_preview(task.image_index, buf.tobytes())
                # Expose virtual path for frontend fallback (served by /api/stream/memory-preview/{index})
                saved_preview_rel_path = f"memory-preview/{task.image_index}"
            except Exception as preview_err:
                logger.debug(f"Failed to create in-memory preview for image {task.image_index}: {preview_err}")
            
            if not analysis_result:
                raise AnalysisTaskError("Analysis returned no result")
            
            # Convert to AnalysisResult
            result = AnalysisResult(
                task_id=task.task_id,
                image_timestamp=task.image_timestamp,
                image_index=task.image_index,
                image_hash=task.image_hash,
                # Point to in-memory preview virtual path first; fallback to presentation naming
                image_path=saved_preview_rel_path or f"memory-preview/{task.image_index}",
                detections=analysis_result.get('detections', []),
                confidence_above_threshold=analysis_result.get('confidence_above_threshold', False),
                max_length=analysis_result.get('max_length', 0.0),
                inspection_result=analysis_result.get('results', '無欠点'),
                ai_threshold=analysis_result.get('ai_threshold', 50),
                processing_time=time.time() - start_time
            )
            
            # Store result in memory only (no database saving until PASS_L_TO_R)
            if hasattr(self.camera, 'buffer_manager'):
                try:
                    # Store in results storage (memory only)
                    if hasattr(self.camera.buffer_manager, 'results_storage'):
                        self.camera.buffer_manager.results_storage.store_result(result)
                    
                    # Cache for quick access
                    if hasattr(self.camera.buffer_manager, 'result_cache'):
                        self.camera.buffer_manager.result_cache.put(f"image_{task.image_index}", result)
                    
                    logger.debug(f"Stored analysis result in memory for image {task.image_index} (no database save until PASS_L_TO_R)")
                        
                except Exception as storage_error:
                    logger.warning(f"Error storing analysis result: {storage_error}")
            
            # Record performance metrics
            self.performance_monitor.record_task_completion(
                result.processing_time, True
            )
            
            # End timing measurement for memory analysis
            if timing_collector and memory_analysis_measurement_id:
                timing_collector.end_measurement("memory_analysis", memory_analysis_measurement_id)
            
            return result
            
        except Exception as e:
            # Record error metrics
            self.performance_monitor.record_task_completion(
                time.time() - start_time, False
            )
            raise AnalysisTaskError(f"Analysis failed: {str(e)}")
    
    def _save_temp_image(self, task: AnalysisTask) -> str:
        """Save image data to temporary file for analysis."""
        import cv2
        
        # Create temp file
        temp_dir = tempfile.gettempdir()
        temp_filename = f"analysis_{task.task_id}.bmp"
        temp_path = os.path.join(temp_dir, temp_filename)
        
        # Convert RGB to BGR for OpenCV
        img_bgr = cv2.cvtColor(task.image_data, cv2.COLOR_RGB2BGR)
        cv2.imwrite(temp_path, img_bgr)
        
        return temp_path
    
    def _cleanup_temp_image(self, temp_path: str) -> None:
        """Clean up temporary image file."""
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception as e:
            logger.warning(f"Failed to cleanup temp image {temp_path}: {e}")
    
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        return self.performance_monitor.get_current_metrics()
    
    def get_worker_status(self) -> list:
        """Get worker status information."""
        return [
            {
                'worker_id': worker.worker_id,
                'running': worker.running,
                'thread_alive': worker.thread.is_alive() if worker.thread else False
            }
            for worker in self.workers
        ]
    
    def save_analysis_results_to_database(self, inspection_id: int, analysis_results: List[AnalysisResult]) -> bool:
        """
        Save analysis results from memory to database.
        
        Args:
            inspection_id: Inspection ID to associate results with
            analysis_results: List of AnalysisResult objects from memory analysis
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info(f"Saving {len(analysis_results)} analysis results to database for inspection {inspection_id}")
            return self.database_saver.save_analysis_results(inspection_id, analysis_results)
        except Exception as e:
            logger.error(f"Error saving analysis results to database: {e}")
            return False
