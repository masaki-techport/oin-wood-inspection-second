"""
Buffer management functionality for BaslerCamera with memory analysis integration.
"""

import __init__
import os
import time
import logging
import yaml
from datetime import datetime
from typing import Optional, Dict, Any, List

logger = logging.getLogger('BaslerCamera.BufferManager')

class BufferManager:
    """Manages buffer operations for BaslerCamera"""
    
    def __init__(self, camera_instance):
        """Initialize with a reference to the parent camera object"""
        self.camera = camera_instance
        self.config_path = os.path.join(__init__.CONFIG_DIR, 'params.yaml')
        self.interval_time_ms = self._read_interval_time()
        
        # Initialize memory analysis components if available
        self.memory_analysis_enabled = False
        self.analysis_queue = None
        self.results_storage = None
        self.result_cache = None
        self.analysis_processor = None
        self.memory_monitor = None
        self.temp_section_assembler = None
        
        # Try to initialize memory analysis
        self._initialize_memory_analysis()
        
        # Group-aware gating for strict A→B→C processing using temp_section_size
        try:
            from services.settings_service import get_settings_service
            self._ga_group_size = get_settings_service().get_temp_section_size()
        except Exception:
            self._ga_group_size = 5
        self._ga_current_group = 0
        self._ga_base_index = None  # first image index of session
        self._ga_inflight = 0
        self._ga_buffer = []  # [(image_data, timestamp, index)] for future groups
        self._ga_seq = 0  # sequential assignment counter
        self._ga_assign = {}  # image_index -> group_idx (by sequential assignment)
        self._ga_seen = {}  # group_idx -> count accepted
        self._ga_done = {}  # group_idx -> count completed
        import threading
        self._ga_lock = threading.RLock()
        
        # Ordered emit queue to guarantee A→B→C display regardless of analysis finish order
        try:
            from .ordered_emit_queue import OrderedEmitQueue
            def _emit(idx: int) -> None:
                if self.temp_section_assembler:
                    res = self.analysis_queue.get_result_by_image_index(idx)
                    if res:
                        self.temp_section_assembler.add_analyzed_image(idx, res)
            self._emit_queue = OrderedEmitQueue(self._ga_group_size, _emit)
        except Exception:
            self._emit_queue = None

    def _ga_reset_session(self, start_index: int) -> None:
        """Reset group gating state for a new recording session."""
        self._ga_base_index = start_index
        self._ga_current_group = 0
        self._ga_inflight = 0
        self._ga_buffer = []
        self._ga_seq = 0
        self._ga_assign.clear()
        self._ga_seen.clear()
        self._ga_done.clear()

    def _ga_compute_group_index(self, image_index: int) -> int:
        """Compute group index relative to session base index."""
        base = 0 if self._ga_base_index is None else self._ga_base_index
        delta = max(0, image_index - base)
        return delta // max(1, self._ga_group_size)
    
    def _initialize_memory_analysis(self):
        """Initialize memory analysis components if available."""
        try:
            logger.info("Attempting to import memory analysis components...")
            from ..memory_analysis.analysis_queue import MemoryAnalysisQueue
            from ..memory_analysis.analysis_processor import MemoryAnalysisProcessor
            from ..memory_analysis.results_storage import MemoryResultsStorage
            from ..memory_analysis.result_cache import AnalysisResultCache
            from ..memory_analysis.memory_monitor import MemoryMonitor
            from ..memory_analysis.config import MemoryAnalysisConfigManager
            logger.info("Memory analysis components imported successfully")
            
            # Initialize memory analysis configuration
            config_manager = MemoryAnalysisConfigManager()
            config = config_manager.get_config()
            
            # Force enable memory analysis
            config.enabled = True
            
            # Initialize memory analysis system
            self.analysis_queue = MemoryAnalysisQueue(
                max_size=config.queue_size,
                priority_mode=config.priority_mode
            )
            self.analysis_processor = MemoryAnalysisProcessor(
                self.camera, 
                self.analysis_queue,
                worker_count=config.worker_count,
                config=config.__dict__
            )
            self.results_storage = MemoryResultsStorage(
                max_results=config.max_results,
                enable_compression=config.enable_compression
            )
            self.result_cache = AnalysisResultCache(
                max_size=config.cache_size
            )
            
            # Initialize performance monitoring
            self.memory_monitor = MemoryMonitor()
            self.memory_monitor.set_components(
                analysis_queue=self.analysis_queue,
                analysis_processor=self.analysis_processor,
                results_storage=self.results_storage,
                result_cache=self.result_cache
            )
            
            # Set up pattern-based cleanup
            self.results_storage.set_buffer_discard_callback(self._on_buffer_discard)
            
            # Initialize temp section assembler
            from .temp_section_assembler import TempSectionAssembler
            self.temp_section_assembler = TempSectionAssembler()
            self.result_cache.pattern_cleanup_manager = self.results_storage.pattern_cleanup_manager
            
            # Always start analysis processor
            try:
                self.analysis_processor.start_processing()
                self.memory_monitor.start_monitoring()
                self.memory_analysis_enabled = True
                logger.info("Memory analysis system initialized and started")
                logger.info(f"Analysis processor running: {self.analysis_processor.is_running}")
                logger.info(f"Worker count: {self.analysis_processor.worker_count}")
                logger.info("Real-time memory analysis is now ACTIVE")
            except Exception as e:
                logger.error(f"Error starting analysis processor: {e}")
                self.memory_analysis_enabled = False
                
        except ImportError as e:
            logger.error(f"Memory analysis components not available: {e}")
            self.memory_analysis_enabled = False
        except Exception as e:
            logger.error(f"Error initializing memory analysis: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.memory_analysis_enabled = False
        
    def _read_interval_time(self):
        """Read interval time from config file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                # Get interval time from config or use default
                interval_time_ms = config.get('IntervalTime', 100)
                logger.info(f"Read interval time from config: {interval_time_ms} ms")
                return interval_time_ms
        except Exception as e:
            logger.warning(f"Error reading interval time from config: {e}. Using default 100ms.")
            return 100
            
    def start_recording(self):
        """Start recording images to buffer"""
        if not self.camera.is_connected_flag:
            logger.warning("Cannot start recording - camera not connected")
            return False
        
        # Start timing measurement for recording start
        timing_collector = getattr(self.camera, 'timing_collector', None)
        recording_measurement_id = None
        if timing_collector:
            recording_measurement_id = timing_collector.start_measurement(
                "recording_start", 
                {"buffer_size": self.camera.buffer_size}
            )
            
        # Make sure grabbing is active
        if not self.camera.is_grabbing:
            logger.info("Starting grabbing for recording")
            if not self.camera.start_grabbing():
                logger.error("Failed to start grabbing, recording will not work properly")
                # Continue anyway to avoid breaking the workflow
        else:
            logger.info("Grabbing already active, using existing grab session")
        
        # If already recording, just return success
        if self.camera.is_recording:
            logger.info("Already recording, no need to start again")
            return True
        
        # Set camera frame rate to ensure exact capture rate based on interval time from config
        try:
            # Convert interval time from ms to fps
            interval_time_ms = self._read_interval_time()  # Refresh the interval time from config
            fps = 1000.0 / interval_time_ms
            
            # Set acquisition frame rate if available on this camera model
            if self.camera.camera:
                try:
                    # Check if the camera supports frame rate control
                    if hasattr(self.camera.camera, 'AcquisitionFrameRateEnable'):
                        self.camera.camera.AcquisitionFrameRateEnable.SetValue(True)
                        self.camera.camera.AcquisitionFrameRate.SetValue(fps)
                        logger.info(f"Set camera acquisition frame rate to {fps} fps (interval: {interval_time_ms} ms)")
                    else:
                        logger.info(f"This camera model doesn't support AcquisitionFrameRateEnable. Using default behavior.")
                        # Store the fps value in the camera object for buffer timing
                        self.camera.buffer_fps = fps
                except Exception as e:
                    logger.warning(f"Could not set camera frame rate: {e}")
                    # Store the fps value in the camera object for buffer timing
                    self.camera.buffer_fps = fps
        except Exception as e:
            logger.warning(f"Error configuring frame rate: {e}")
            # Ensure we have a reasonable default
            self.camera.buffer_fps = 10
        
        # Reset the buffer before starting recording    
        logger.info(f"Initializing buffer with capacity: {self.camera.buffer_size} frames")
        self.camera.buffer.clear()
        
        # Clear processed images set to prevent memory leaks
        if hasattr(self, '_processed_images'):
            self._processed_images.clear()
        
        logger.info(f"Buffer initialized and cleared - capacity: {self.camera.buffer_size} frames")
        logger.info(f"Fresh recording started - buffer completely cleared for new capture sequence")
        
        # Set recording flag - this is critical for the _grab_loop to start adding frames
        self.camera.is_recording = True
        self.camera.status = "録画中"  # "Recording" in Japanese
        self.camera.save_message = ""
        
        # Clear processed images set when starting new recording
        if hasattr(self, '_processed_images'):
            self._processed_images.clear()
            logger.info("Cleared processed images set for new recording")
        
        # Reset analysis timing for new recording
        self._last_analysis_time = 0
        # Reset group gating session state
        try:
            # Estimate starting index as 0; first incoming image will update base
            self._ga_reset_session(0)
            logger.info("Reset group gating session state")
            # Also reset temp section assembler so first group label is 'A'
            if self.temp_section_assembler:
                self.temp_section_assembler.reset()
                logger.info("Reset TempSectionAssembler (counter -> 0, sections cleared)")
            if self._emit_queue:
                self._emit_queue.reset(self._ga_group_size)
        except Exception:
            pass
        
        # Clear memory analysis transient state to avoid old previews/results
        try:
            if self.memory_analysis_enabled:
                # Reset in-memory queue and caches/storage
                if self.analysis_queue and hasattr(self.analysis_queue, 'reset'):
                    self.analysis_queue.reset()
                if self.results_storage and hasattr(self.results_storage, 'clear_all'):
                    self.results_storage.clear_all()
                if self.result_cache and hasattr(self.result_cache, 'clear'):
                    self.result_cache.clear()
                # Also clear presentation previews
                try:
                    from services import memory_image_cache
                    memory_image_cache.clear_all()
                except Exception:
                    pass
                logger.info("Cleared memory analysis queue, storage, cache and previews for fresh recording")
        except Exception as mem_reset_err:
            logger.warning(f"Memory analysis reset failed: {mem_reset_err}")
        
        # Let the grab loop handle all frame capture to avoid duplicate additions
        logger.info("Buffer initialized, grab loop will handle frame capture")
        
        logger.info("Started recording to buffer")
        
        # End timing measurement for recording start
        if timing_collector and recording_measurement_id:
            timing_collector.end_measurement("recording_start", recording_measurement_id)
        
        return True
        
    def stop_recording(self):
        """Stop recording images to buffer"""
        if not self.camera.is_recording:
            return True
            
        self.camera.is_recording = False
        self.camera.status = "待機中"  # "Standby" in Japanese
        
        logger.info("Stopped recording to buffer")
        return True
        
    def save_buffer_images(self, output_dir=None, prefix="frame", filter_start_time=None, filter_end_time=None):
        """
        Save all buffered images to directory and analyze them with inference
        
        Args:
            output_dir: Directory to save images to
            prefix: Prefix for image filenames
            filter_start_time: If provided, only save images captured after this timestamp
            filter_end_time: If provided, only save images captured before this timestamp
            
        Returns:
            List[str]: List of saved file paths
        """
        logger.info(f"Save buffer images called with output_dir={output_dir}, buffer size={len(self.camera.buffer)}")
        logger.info(f"Filter start time: {filter_start_time}, Filter end time: {filter_end_time}")
        
        # Create output directory if needed
        if not output_dir:
            output_dir = self.make_timestamp_dir(self.camera.save_directory)
            logger.info(f"Created directory: {output_dir}")
            
        # First set save path so frontend can show it
        self.camera.save_path = os.path.abspath(output_dir)
        self.camera.save_message = "処理中..."  # "Processing..." in Japanese
        
        # Check if buffer is empty
        if len(self.camera.buffer) == 0:
            logger.warning("Buffer is empty, attempting to capture current frame")
            try:
                # Try to capture at least one frame
                frame = self.camera.get_frame()
                if frame and 'image' in frame:
                    # Add to buffer
                    current_time = time.time()
                    self.camera.buffer.append({
                        "image": frame['image'].copy(),
                        "timestamp": current_time
                    })
                    logger.info(f"Added current frame to buffer with timestamp {current_time}")
                    
                    # Try to get a few more frames if possible
                    for i in range(5):  # Try for 5 frames
                        time.sleep(0.1)  # Small delay between captures
                        try:
                            frame = self.camera.get_frame()
                            if frame and 'image' in frame:
                                current_time = time.time()
                                self.camera.buffer.append({
                                    "image": frame['image'].copy(),
                                    "timestamp": current_time
                                })
                                logger.info(f"Added additional frame {i+1} to buffer with timestamp {current_time}")
                        except Exception as e:
                            logger.error(f"Error capturing additional frame: {e}")
                else:
                    logger.warning("Failed to capture current frame")
            except Exception as e:
                logger.error(f"Error capturing frame: {e}")
                
            # Check buffer again after capture attempt
            if len(self.camera.buffer) == 0:
                logger.warning("Buffer is still empty after capture attempt, nothing to save")
                self.camera.save_message = "保存失敗 (0枚)"  # "Save failed" in Japanese
                return []
        
        # Extract frames from buffer based on filter criteria
        frame_extractor = self.camera.frame_extractor
        buffer_snapshot = frame_extractor.extract_frames_from_buffer(filter_start_time, filter_end_time)
        
        # Check if we got any frames
        if len(buffer_snapshot) == 0:
            logger.warning("No frames extracted from buffer")
            self.camera.save_message = "保存失敗 (0枚)"  # "Save failed" in Japanese
            return []
            
        # Start event processing thread if not already started
        if not self.camera.event_processor.event_processing_active:
            self.camera.event_processor.start_event_processing()
            
        # Create event data for the queue
        event_data = {
            'event_type': 'save',
            'output_dir': output_dir,
            'buffer_snapshot': buffer_snapshot.copy(),  # Make a copy to avoid thread issues
            'filter_start_time': filter_start_time,
            'filter_end_time': filter_end_time,
            'timestamp': time.time()
        }
        
        # Add to queue for background processing
        self.camera.event_processor.event_queue.put(event_data)
        logger.info(f"Added save event to queue with {len(buffer_snapshot)} frames")
        
        # Update UI status - actual processing happens in background
        self.camera.save_message = f"処理中... ({len(buffer_snapshot)}枚)"  # "Processing..." in Japanese
        
        # Return the output directory so the caller knows where to look for files
        return [output_dir]
        
    def discard_buffer_images(self):
        """Discard buffered images without saving"""
        logger.info(f"Discarding buffer with {len(self.camera.buffer)} frames")
        
        # Get image indices before clearing for pattern-based cleanup
        discarded_indices = list(range(len(self.camera.buffer)))
        
        # Clear buffer
        self.camera.buffer.clear()
        
        # Clean up analysis results using pattern-based cleanup
        if self.memory_analysis_enabled:
            self._on_buffer_discard(discarded_indices)
        
        self.camera.save_message = "破棄しました"  # "Discarded" in Japanese
        self.camera.save_path = ""
        logger.info("Discarded buffer images and cleaned up analysis results")
    
    # --- Save-session coordination for memory analysis cleanup ---
    def begin_save_session(self) -> None:
        """Mark that a SAVE session is in progress to defer non-discard cleanups."""
        try:
            self.save_in_progress = True
            logger.info("Save session started: deferring non-discard memory cleanups")
            
            # Ensure memory analysis continues running during save session
            if self.memory_analysis_enabled and self.analysis_processor:
                if not self.analysis_processor.is_running:
                    logger.warning("Analysis processor not running at save session start, restarting...")
                    try:
                        self.analysis_processor.start_processing()
                        logger.info("Analysis processor restarted for save session")
                    except Exception as restart_error:
                        logger.error(f"Failed to restart analysis processor for save session: {restart_error}")
                else:
                    logger.info("Analysis processor continues running during save session")
        except Exception:
            self.save_in_progress = True
    
    def end_save_session(self) -> None:
        """Mark that SAVE session has finished; allow cleanups again."""
        try:
            self.save_in_progress = False
            logger.info("Save session ended: normal cleanups re-enabled")
            
            # Ensure memory analysis system continues running after save session
            if self.memory_analysis_enabled and self.analysis_processor:
                if not self.analysis_processor.is_running:
                    logger.warning("Analysis processor stopped during save session, restarting...")
                    try:
                        self.analysis_processor.start_processing()
                        logger.info("Analysis processor restarted successfully")
                    except Exception as restart_error:
                        logger.error(f"Failed to restart analysis processor: {restart_error}")
                        
                # Log analysis processor status for debugging
                if hasattr(self.analysis_processor, 'get_performance_stats'):
                    stats = self.analysis_processor.get_performance_stats()
                    logger.info(f"Analysis processor stats: {stats}")
                else:
                    logger.info("Analysis processor continues running after save session")
            else:
                logger.warning("Memory analysis system not available or disabled")
                
        except Exception as e:
            logger.error(f"Error in end_save_session: {e}")
            self.save_in_progress = False
    
    def ensure_analysis_processor_running(self) -> bool:
        """Ensure the analysis processor is running, restart if needed."""
        try:
            if not self.memory_analysis_enabled or not self.analysis_processor:
                logger.warning("Memory analysis system not available")
                return False
                
            if not self.analysis_processor.is_running:
                logger.warning("Analysis processor not running, attempting to restart...")
                try:
                    self.analysis_processor.start_processing()
                    logger.info("Analysis processor restarted successfully")
                    return True
                except Exception as restart_error:
                    logger.error(f"Failed to restart analysis processor: {restart_error}")
                    return False
            else:
                logger.debug("Analysis processor is running normally")
                return True
                
        except Exception as e:
            logger.error(f"Error checking analysis processor status: {e}")
            return False
    
    def get_analysis_completion_status(self, image_indices: List[int]) -> Dict[str, Any]:
        """
        Get analysis completion status for specific image indices.
        
        Args:
            image_indices: List of image indices to check
            
        Returns:
            Dictionary with completion status information
        """
        try:
            completed = []
            missing = []
            in_progress = []
            
            for idx in image_indices:
                # Check result cache first
                cache_key = f"image_{idx}"
                if cache_key in self.result_cache:
                    completed.append(idx)
                    continue
                
                # Check results storage
                if hasattr(self, 'results_storage') and self.results_storage:
                    if self.results_storage.has_result(idx):
                        completed.append(idx)
                        continue
                
                # Check if in analysis queue
                if hasattr(self, 'analysis_processor') and self.analysis_processor:
                    if hasattr(self.analysis_processor, 'analysis_queue'):
                        if self.analysis_processor.analysis_queue.is_image_in_queue(idx):
                            in_progress.append(idx)
                            continue
                
                # If not found anywhere, it's missing
                missing.append(idx)
            
            return {
                'completed': completed,
                'missing': missing,
                'in_progress': in_progress,
                'total_requested': len(image_indices),
                'completion_rate': len(completed) / len(image_indices) if image_indices else 0.0
            }
        except Exception as e:
            logger.error(f"Error getting analysis completion status: {e}")
            return {
                'completed': [],
                'missing': image_indices,
                'in_progress': [],
                'total_requested': len(image_indices),
                'completion_rate': 0.0
            }
        
    def make_timestamp_dir(self, root_dir="output_dir"):
        """
        Create timestamped directory for saving images
        
        Args:
            root_dir: Root directory
            
        Returns:
            str: Path to created directory
        """
        try:
            # First check if root directory exists, if not try to create it
            if not os.path.exists(root_dir):
                logger.info(f"Root directory doesn't exist: {root_dir}, creating it")
                os.makedirs(root_dir, exist_ok=True)
            
            # Create timestamped directory
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dir_path = os.path.join(root_dir, timestamp)
            os.makedirs(dir_path, exist_ok=True)
            logger.info(f"Created timestamped directory: {dir_path}")
            
            return dir_path
            
        except Exception as e:
            logger.error(f"Error creating timestamped directory: {e}")
            return root_dir
    
    def _on_buffer_image_added(self, image_data, timestamp: float, index: int):
        """Called when image is added to buffer - trigger analysis with rate limiting."""
        logger.info(f"Buffer image added: index={index}, memory_analysis_enabled={self.memory_analysis_enabled}")
        
        if not self.memory_analysis_enabled:
            logger.warning(f"Memory analysis disabled, skipping image {index}")
            return
        
        # Ensure analysis processor is running before processing new images
        if not self.ensure_analysis_processor_running():
            logger.warning(f"Analysis processor not running, skipping image {index}")
            return
        
        # Initialize processed images tracking
        if not hasattr(self, '_processed_images'):
            self._processed_images = set()
        
        # Prevent duplicate analysis of the same image
        if index in self._processed_images:
            logger.debug(f"Image {index} already processed, skipping duplicate analysis")
            return
        
        # Rate limiting - only process images at the capture interval
        current_time = time.time()
        if not hasattr(self, '_last_analysis_time'):
            self._last_analysis_time = 0
        
        time_since_last = current_time - self._last_analysis_time
        interval_seconds = self.interval_time_ms / 1000.0
        
        # Non-blocking rate limiting - skip if too soon (with small tolerance)
        if time_since_last < (interval_seconds - 0.1):  # 100ms tolerance
            logger.debug(f"Rate limiting: skipping image {index}, too soon ({time_since_last:.3f}s < {interval_seconds-0.1:.3f}s)")
            return
        
        logger.debug(f"Rate limiting passed: processing image {index} after {time_since_last:.3f}s (interval: {interval_seconds:.3f}s)")
        
        self._last_analysis_time = current_time
        
        try:
            logger.info(f"Processing buffer image {index} for memory analysis")
            # Mark as processed to prevent duplicates
            self._processed_images.add(index)
            
            # Queue for analysis with rate limiting
            self._on_new_image_captured(image_data, timestamp, index)
            
        except Exception as e:
            logger.error(f"Error processing buffer image {index}: {e}")
    
    def _on_new_image_captured(self, image_data, timestamp: float, index: int):
        """Called when new image is captured - queue for analysis."""
        logger.info(f"New image captured: index={index}, memory_analysis_enabled={self.memory_analysis_enabled}, analysis_queue={self.analysis_queue is not None}")
        
        if not self.memory_analysis_enabled or not self.analysis_queue:
            logger.warning(f"Memory analysis not available, skipping image {index}")
            return
        
        try:
            # Initialize base index on first image of session
            with self._ga_lock:
                if self._ga_base_index is None:
                    self._ga_reset_session(index)
                    logger.info(f"Group gating base index initialized to {index}")
            # Assign group by sequential acceptance, not absolute index
            with self._ga_lock:
                group_idx = self._ga_seq // max(1, self._ga_group_size)
                self._ga_assign[index] = group_idx
                self._ga_seen[group_idx] = self._ga_seen.get(group_idx, 0) + 1
                self._ga_seq += 1
            with self._ga_lock:
                if group_idx == self._ga_current_group and self._ga_inflight < self._ga_group_size:
                    # Enqueue into current group
                    task_id = self.analysis_queue.enqueue_task(
                        image_data, timestamp, index, priority=1
                    )
                    self._ga_inflight += 1
                    logger.info(f"Queued image {index} for group {self._ga_current_group} (inflight={self._ga_inflight}/{self._ga_group_size}) task={task_id}")
                    # Start background result polling only when actually enqueued
                    self._start_result_polling(index)
                else:
                    # Hold for future group
                    self._ga_buffer.append((image_data, timestamp, index))
                    logger.debug(f"Buffered image {index} for future group {group_idx}; current={self._ga_current_group}")
        except Exception as e:
            logger.error(f"Error queuing/buffering image for analysis: {e}")
    
    def _start_result_polling(self, image_index: int):
        """Start background polling for analysis result."""
        if not self.memory_analysis_enabled or not self.analysis_queue:
            return
        
        def poll_for_result():
            """Background thread to poll for analysis result."""
            max_attempts = 30  # Poll for up to 30 seconds
            attempt = 0
            
            logger.debug(f"Starting background polling for image {image_index}")
            
            while attempt < max_attempts:
                try:
                    result = self.analysis_queue.get_result_by_image_index(image_index)
                    if result:
                        logger.debug(f"Found analysis result for image {image_index} on attempt {attempt + 1}")
                        
                        # Store in results storage
                        if self.results_storage:
                            self.results_storage.store_result(result)
                        
                        # Cache for quick access
                        if self.result_cache:
                            self.result_cache.put(f"image_{image_index}", result)
                        
                        logger.info(f"✅ Stored analysis result for image {image_index}")
                        
                        # Register into ordered emit queue (strict A→B→C emission)
                        try:
                            if self._emit_queue:
                                grp = self._ga_assign.get(image_index, self._ga_compute_group_index(image_index))
                                self._emit_queue.register(grp, image_index)
                            else:
                                # Fallback: direct emit
                                if self.temp_section_assembler:
                                    self.temp_section_assembler.add_analyzed_image(image_index, result)
                        except Exception as e:
                            logger.error(f"Ordered emit error for image {image_index}: {e}")
                        
                        # Group gating: update and possibly flush next group
                        try:
                            self._on_result_stored(image_index)
                        except Exception as gate_err:
                            logger.error(f"Group gating error: {gate_err}")
                        return
                    else:
                        logger.debug(f"No result found for image {image_index} on attempt {attempt + 1}")
                    
                    # Wait before next attempt
                    time.sleep(0.5)
                    attempt += 1
                    
                except Exception as e:
                    logger.error(f"Error polling for result {image_index}: {e}")
                    break
            
            logger.warning(f"Timeout waiting for analysis result for image {image_index} after {max_attempts} attempts")
        
        # Start background polling
        import threading
        poll_thread = threading.Thread(target=poll_for_result, daemon=True)
        poll_thread.start()

    def _on_result_stored(self, image_index: int) -> None:
        """Update group gating on result and flush buffered images if the group completes.
        This function must be called only after the result for image_index is stored.
        """
        with self._ga_lock:
            grp_idx = self._ga_assign.get(image_index, self._ga_compute_group_index(image_index))
            self._ga_done[grp_idx] = self._ga_done.get(grp_idx, 0) + 1
            if grp_idx == self._ga_current_group:
                if self._ga_inflight > 0:
                    self._ga_inflight -= 1
                # Complete only when FULL group_size items have been processed for this group
                seen = self._ga_seen.get(self._ga_current_group, 0)
                done = self._ga_done.get(self._ga_current_group, 0)
                if self._ga_inflight == 0 and done >= self._ga_group_size and seen >= self._ga_group_size:
                    # Advance to next group
                    self._ga_current_group += 1
                    # Flush buffered images that belong to the new current group, up to group_size
                    to_enqueue = []
                    remain = self._ga_group_size
                    keep_buffer = []
                    for item in self._ga_buffer:
                        gidx = self._ga_assign.get(item[2], self._ga_compute_group_index(item[2]))
                        if gidx == self._ga_current_group and remain > 0:
                            to_enqueue.append(item)
                            remain -= 1
                        else:
                            keep_buffer.append(item)
                    self._ga_buffer = keep_buffer
                    for (img, ts, idx) in to_enqueue:
                        try:
                            tid = self.analysis_queue.enqueue_task(img, ts, idx, priority=1)
                            self._ga_inflight += 1
                            logger.info(f"Released buffered image {idx} for group {self._ga_current_group} (inflight={self._ga_inflight}/{self._ga_group_size}) task={tid}")
                            # Start polling for flushed items now that they are enqueued
                            self._start_result_polling(idx)
                        except Exception as eq_err:
                            logger.error(f"Failed to enqueue buffered image {idx}: {eq_err}")
    
    def _store_analysis_result_when_ready(self, image_index: int):
        """Store analysis result when it becomes available (legacy method)."""
        if not self.memory_analysis_enabled or not self.analysis_queue:
            logger.warning(f"Memory analysis not available for image {image_index}")
            return
        
        try:
            # Check if result is available
            result = self.analysis_queue.get_result_by_image_index(image_index)
            if result:
                # Store in results storage
                if self.results_storage:
                    self.results_storage.store_result(result)
                
                # Cache for quick access
                if self.result_cache:
                    self.result_cache.put(f"image_{image_index}", result)
                
                logger.info(f"✅ Stored analysis result for image {image_index}")
            else:
                logger.debug(f"No analysis result available yet for image {image_index}")
            
        except Exception as e:
            logger.error(f"Error storing analysis result for image {image_index}: {e}")
    
    def get_analysis_result(self, image_index: int) -> Optional[Any]:
        """Get analysis result for specific image."""
        if not self.memory_analysis_enabled:
            return None
        
        try:
            # Try cache first
            if self.result_cache:
                result = self.result_cache.get_result_by_image_index(image_index)
                if result:
                    return result
            
            # Try storage
            if self.results_storage:
                result = self.results_storage.get_result_by_image_index(image_index)
                if result:
                    # Cache the result
                    if self.result_cache:
                        self.result_cache.put(f"image_{image_index}", result)
                    return result
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting analysis result for image {image_index}: {e}")
            return None
    
    def get_analysis_results_for_save(self, start_time: float, end_time: float) -> List[Any]:
        """Get all analysis results for save operation in FIFO order."""
        if not self.memory_analysis_enabled or not self.results_storage:
            return []
        
        try:
            # Get results from storage in FIFO order (oldest first)
            results = self.results_storage.get_results_for_range(start_time, end_time)
            
            # Cache results for future use
            if self.result_cache:
                for result in results:
                    self.result_cache.put(f"image_{result.image_index}", result)
            
            logger.info(f"Retrieved {len(results)} analysis results for save operation in FIFO order")
            return results
            
        except Exception as e:
            logger.error(f"Error getting analysis results for save: {e}")
            return []
    
    def get_all_analysis_results_fifo(self, limit: Optional[int] = None) -> List[Any]:
        """Get all analysis results in FIFO order (oldest first)."""
        if not self.memory_analysis_enabled or not self.results_storage:
            return []
        
        try:
            # Get all results from storage in FIFO order (oldest first)
            results = self.results_storage.get_all_results_fifo(limit)
            
            # Cache results for future use
            if self.result_cache:
                for result in results:
                    self.result_cache.put(f"image_{result.image_index}", result)
            
            logger.info(f"Retrieved {len(results)} analysis results in FIFO order")
            return results
            
        except Exception as e:
            logger.error(f"Error getting all analysis results in FIFO order: {e}")
            return []
    
    def _on_buffer_discard(self, discarded_image_indices: List[int]) -> None:
        """Handle buffer discard event - clean up analysis results."""
        if not self.memory_analysis_enabled:
            return
        
        try:
            logger.info(f"Buffer discard: cleaning up analysis results for {len(discarded_image_indices)} images")
            
            # Clean up storage
            if self.results_storage:
                self.results_storage.on_buffer_discard(discarded_image_indices)
            
            # Clean up cache
            if self.result_cache:
                self.result_cache.cleanup_discarded_results(discarded_image_indices)

            # Also remove any presentation previews from in-memory cache
            try:
                from services import memory_image_cache
                for idx in discarded_image_indices:
                    memory_image_cache.remove_preview(idx)
            except Exception as cache_err:
                logger.debug(f"Memory preview cache cleanup failed: {cache_err}")
            
        except Exception as e:
            logger.error(f"Error in buffer discard cleanup: {e}")
    
    def on_buffer_clear(self, start_timestamp: float, end_timestamp: float) -> None:
        """Handle buffer clear event - clean up all results in timestamp range."""
        if not self.memory_analysis_enabled:
            return
        # Defer cleanup during active SAVE; DISCARD path will still clean immediately
        if getattr(self, 'save_in_progress', False):
            logger.info("Save in progress: skipping buffer clear cleanup to preserve pre-analyzed results")
            return
        
        try:
            logger.info(f"Buffer clear: cleaning up analysis results for timestamp range {start_timestamp} - {end_timestamp}")
            
            # Clean up storage
            if self.results_storage:
                self.results_storage.on_buffer_clear(start_timestamp, end_timestamp)
            
            # Clean up cache
            if self.result_cache:
                self.result_cache.cleanup_old_results()
            
        except Exception as e:
            logger.error(f"Error in buffer clear cleanup: {e}")
    
    def get_analysis_stats(self) -> Dict[str, Any]:
        """Get analysis system statistics."""
        if not self.memory_analysis_enabled:
            return {"enabled": False}
        
        try:
            stats = {
                "enabled": True,
                "queue_stats": self.analysis_queue.get_queue_stats() if self.analysis_queue else {},
                "storage_stats": self.results_storage.get_storage_stats() if self.results_storage else {},
                "cache_stats": self.result_cache.get_cache_stats() if self.result_cache else {},
                "processor_stats": self.analysis_processor.get_performance_stats() if self.analysis_processor else {},
                "monitor_stats": self.memory_monitor.get_current_metrics().__dict__ if self.memory_monitor else {}
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting analysis stats: {e}")
            return {"enabled": True, "error": str(e)}
    
    def enable_memory_analysis(self) -> None:
        """Enable memory analysis."""
        try:
            self.memory_analysis_enabled = True
            if self.analysis_processor:
                self.analysis_processor.start_processing()
            if self.memory_monitor:
                self.memory_monitor.start_monitoring()
            logger.info("Memory analysis enabled")
        except Exception as e:
            logger.error(f"Error enabling memory analysis: {e}")
    
    def disable_memory_analysis(self) -> None:
        """Disable memory analysis."""
        try:
            self.memory_analysis_enabled = False
            if self.analysis_processor:
                self.analysis_processor.stop_processing()
            if self.memory_monitor:
                self.memory_monitor.stop_monitoring()
            logger.info("Memory analysis disabled")
        except Exception as e:
            logger.error(f"Error disabling memory analysis: {e}")
    
    def _add_to_temp_section(self, image_index: int):
        """Add analyzed image to temp section assembler."""
        try:
            if not self.temp_section_assembler:
                logger.debug(f"No temp section assembler available for image {image_index}")
                return
            
            logger.debug(f"Waiting for analysis result for image {image_index}")
            # Wait for analysis result with timeout
            analysis_result = self._wait_for_analysis_result(image_index, timeout=5.0)
            if analysis_result:
                logger.debug(f"Found analysis result for image {image_index}, type: {type(analysis_result)}")
                completed_section = self.temp_section_assembler.add_analyzed_image(image_index, analysis_result)
                if completed_section:
                    logger.info(f"Completed temp section {completed_section.label} with {len(completed_section.image_indices)} images")
                    # Trigger cleanup if needed
                    self.temp_section_assembler.cleanup_old_sections()
            else:
                logger.warning(f"No analysis result found for image {image_index} after timeout")
                
        except Exception as e:
            logger.error(f"Error adding image {image_index} to temp section: {e}")
    
    def _wait_for_analysis_result(self, image_index: int, timeout: float = 5.0) -> Optional[Any]:
        """Wait for analysis result with timeout."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            result = self.get_analysis_result(image_index)
            if result:
                return result
            
            # Wait briefly before checking again
            time.sleep(0.1)
        
        return None
    
    def get_temp_sections(self, limit: int = -1) -> List[Dict[str, Any]]:
        """Get recent temp sections for API."""
        try:
            if not self.temp_section_assembler:
                return []
            
            sections = self.temp_section_assembler.get_recent_sections(limit)
            return [
                {
                    'id': section.id,
                    'label': section.label,
                    'status': section.status,
                    'image_indices': section.image_indices,
                    'representative_image': section.representative_image,
                    'summary_color': section.summary_color,
                    'created_at': section.created_at,
                    'completed_at': section.completed_at
                }
                for section in sections
            ]
        except Exception as e:
            logger.error(f"Error getting temp sections: {e}")
            return []
    
    def get_temp_section_stats(self) -> Dict[str, Any]:
        """Get temp section assembler statistics."""
        try:
            if not self.temp_section_assembler:
                return {}
            return self.temp_section_assembler.get_stats()
        except Exception as e:
            logger.error(f"Error getting temp section stats: {e}")
            return {}
    
    def get_analysis_completion_status(self, image_indices: List[int]) -> Dict[str, Any]:
        """
        Get analysis completion status for specific image indices.
        
        Args:
            image_indices: List of image indices to check
            
        Returns:
            Dict[str, Any]: Status information including completed, pending, and missing indices
        """
        if not self.memory_analysis_enabled:
            return {"error": "Memory analysis not enabled"}
        
        completed = []
        pending = []
        missing = []
        
        for index in image_indices:
            try:
                # Check if result exists in cache or storage
                result = self.get_analysis_result(index)
                if result and not getattr(result, 'is_discarded', False):
                    completed.append(index)
                else:
                    # Check if task is still in queue
                    if hasattr(self, 'analysis_queue') and self.analysis_queue:
                        task_status = self.analysis_queue.get_task_status(f"image_{index}")
                        if task_status in ['pending', 'processing', 'retrying']:
                            pending.append(index)
                        else:
                            missing.append(index)
                    else:
                        missing.append(index)
            except Exception as e:
                logger.debug(f"Error checking analysis status for image {index}: {e}")
                missing.append(index)
        
        return {
            "completed": completed,
            "pending": pending,
            "missing": missing,
            "total": len(image_indices),
            "completion_rate": len(completed) / len(image_indices) if image_indices else 0.0
        }