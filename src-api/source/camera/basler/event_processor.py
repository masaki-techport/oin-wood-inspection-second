"""
Event processing functionality for Basler camera module.
"""

import os
import time
import logging
import threading
import queue
import json
from typing import Dict, Any, List, Optional, Set
from datetime import datetime
from datetime import timedelta
import numpy as np
import cv2

from .image_processor import ImageProcessor
from .memory_analysis.memory_presentation_processor import MemoryPresentationProcessor
from db.inspection_images import InspectionImage
from db.engine import SessionLocal
from db import Inspection, InspectionResult

# Import app config for debug settings
try:
    from app_config import app_config
    DEBUG_CAPTURE_TIME = app_config.debug_capture_time()
    DEBUG_MODE = app_config.is_debug_mode()
except ImportError:
    DEBUG_CAPTURE_TIME = False
    DEBUG_MODE = False

logger = logging.getLogger('BaslerCamera.EventProcessor')

class EventProcessor:
    """Handles event processing for the Basler camera"""
    
    def __init__(self, camera_instance):
        """Initialize with a reference to the parent camera object"""
        self.camera = camera_instance
        self.event_queue = queue.PriorityQueue()
        self.event_processing_thread = None
        self.event_processing_active = False
        self.image_processor = ImageProcessor()
        
        # Initialize memory presentation processor
        self.memory_presentation_processor = MemoryPresentationProcessor(camera_instance)
        
    def start_event_processing(self) -> None:
        """Start the event processing thread"""
        if not self.event_processing_active:
            self.event_processing_active = True
            self.event_processing_thread = threading.Thread(
                target=self._event_processing_loop, 
                daemon=True
            )
            self.event_processing_thread.start()
            logger.info("Event processing thread started")
            
    def stop_event_processing(self) -> None:
        """Stop the event processing thread"""
        self.event_processing_active = False
        if self.event_processing_thread and self.event_processing_thread.is_alive():
            # Wait for thread to finish (with timeout)
            self.event_processing_thread.join(timeout=2.0)
            logger.info("Event processing thread stopped")
            
    def _event_processing_loop(self) -> None:
        """Main event processing loop"""
        logger.info("Event processing loop started")
        
        while self.event_processing_active:
            try:
                # Get event from queue with timeout
                try:
                    event_data = self.event_queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                    
                # Process based on event type
                event_type = event_data.get('event_type')
                
                if event_type == 'save':
                    # Process save event
                    self._process_save_event(event_data)
                else:
                    logger.warning(f"Unknown event type: {event_type}")
                    
                # Mark task as done
                self.event_queue.task_done()
                
            except Exception as e:
                logger.error(f"Error in event processing loop: {e}")
                time.sleep(0.1)
                
        logger.info("Event processing loop stopped")
        
    def _process_save_event(self, event_data: Dict[str, Any]) -> None:
        """Process a save event"""
        output_dir = event_data.get('output_dir')
        buffer_snapshot = event_data.get('buffer_snapshot', [])
        filter_start_time = event_data.get('filter_start_time')
        filter_end_time = event_data.get('filter_end_time')
        
        logger.info(f"Processing save event with {len(buffer_snapshot)} frames")
        
        # Start timing measurement for save event processing
        timing_collector = getattr(self.camera, 'timing_collector', None)
        save_event_measurement_id = None
        if timing_collector:
            save_event_measurement_id = timing_collector.start_measurement(
                "save_event_processing", 
                {"output_dir": output_dir, "frame_count": len(buffer_snapshot)}
            )
        
        if not buffer_snapshot:
            logger.warning("No frames to save")
            self.camera.save_message = "保存失敗 (0枚)"  # "Save failed" in Japanese
            return
            
        # Mark SAVE session to protect memory results
        try:
            if hasattr(self.camera, 'buffer_manager') and self.camera.buffer_manager:
                self.camera.buffer_manager.begin_save_session()
        except Exception:
            pass

        # Create timing reports
        self._create_timing_reports(output_dir, buffer_snapshot)
        
            # Note: Timing report will be generated after session finalization
        
        # Mark CAPTURE phase end and SAVE phase start
        if timing_collector:
            timing_collector.mark_phase_end("capture")
            timing_collector.mark_phase_start("save")

        # Save the images
        saved_images = self._save_buffer_images(buffer_snapshot, output_dir)

        # Mark SAVE phase end and ANALYSIS phase start
        if timing_collector:
            timing_collector.mark_phase_end("save")
            timing_collector.mark_phase_start("analysis")
        
        # Update camera status
        self.camera.save_message = f"保存完了 ({len(saved_images)}枚)"  # "Save completed" in Japanese
        
        # Try to use pre-analyzed results first
        if saved_images:
            # Mark analysis phase end and presentation phase start
            timing_collector = getattr(self.camera, 'timing_collector', None)
            if timing_collector:
                timing_collector.mark_phase_end("analysis")
                timing_collector.mark_phase_start("presentation")
            
            self._analyze_saved_images_memory_aware(saved_images, buffer_snapshot, filter_start_time, filter_end_time)
            
            # Handle PASS_L_TO_R split into fixed 5 groups
            self._handle_pass_l_to_r_split(saved_images)
            
            # Mark presentation phase end and finalize session
            if timing_collector:
                timing_collector.mark_phase_end("presentation")
                
                # End timing measurement for save event processing BEFORE finalizing
                if save_event_measurement_id:
                    try:
                        timing_collector.end_measurement("save_event_processing", save_event_measurement_id)
                    except Exception:
                        pass
                
                # Set session metadata before finalizing
                timing_collector.set_session_metadata(
                    output_directory=output_dir,
                    image_count=len(buffer_snapshot),
                    inspection_id=getattr(self.camera, 'last_inspection_id', None)
                )
                
                completed_session = timing_collector.finalize_current_session()
                if completed_session:
                    logger.info(f"Finalized timing session: {completed_session.session_id}")
                    
                    # Generate comprehensive timing report after session is finalized
                    self._generate_comprehensive_timing_report_from_session(completed_session, output_dir)

        # End SAVE session regardless of outcome
        try:
            if hasattr(self.camera, 'buffer_manager') and self.camera.buffer_manager:
                self.camera.buffer_manager.end_save_session()
        except Exception:
            pass
        
        # End timing measurement for save event processing (safety, if not ended above)
        if timing_collector and save_event_measurement_id:
            try:
                timing_collector.end_measurement("save_event_processing", save_event_measurement_id)
            except Exception:
                pass
    
    def _analyze_saved_images_memory_aware(self, saved_images: List[str], buffer_snapshot: List[np.ndarray], 
                                         filter_start_time: Optional[float], filter_end_time: Optional[float]) -> None:
        """Analyze saved images using memory-aware approach."""
        
        # Check if memory analysis is available
        if not hasattr(self.camera, 'memory_analysis_enabled') or not self.camera.memory_analysis_enabled:
            logger.error("Memory analysis not available")
            self._analyze_saved_images(saved_images)
            return
        
        try:
            # Try to get pre-analyzed results
            pre_analyzed_results = self._get_pre_analyzed_results(buffer_snapshot, filter_start_time, filter_end_time)
            
            if pre_analyzed_results:
                logger.info(f"Found {len(pre_analyzed_results)} pre-analyzed results, using them")
                self._use_pre_analyzed_results(saved_images, pre_analyzed_results)
            else:
                logger.warning("No pre-analyzed results found after waiting, using memory-aware analysis")
                logger.info("This may indicate that memory analysis is still processing images")
                # Use memory-aware analysis instead of falling back to real-time analysis
                self._analyze_saved_images_memory_aware_new(saved_images)
                
        except Exception as e:
            logger.error(f"Error in memory-aware analysis: {e}")
            logger.info("Falling back to real-time analysis")
            self._analyze_saved_images(saved_images)
    
    def _get_pre_analyzed_results(self, buffer_snapshot: List[np.ndarray],
                                filter_start_time: Optional[float], 
                                filter_end_time: Optional[float]) -> List[Any]:
        """Get pre-analyzed results from memory storage."""
        
        if not hasattr(self.camera.buffer_manager, 'get_analysis_results_for_save'):
            return []
        
        try:
            # Determine time range for query
            if filter_start_time and filter_end_time:
                start_time = filter_start_time
                end_time = filter_end_time
            else:
                # Use buffer snapshot timestamps
                timestamps = []
                for frame in buffer_snapshot:
                    if isinstance(frame, dict) and 'timestamp' in frame:
                        timestamps.append(frame['timestamp'])
                    elif hasattr(frame, 'timestamp'):
                        timestamps.append(frame.timestamp)
                
                if timestamps:
                    start_time = min(timestamps)
                    end_time = max(timestamps)
                else:
                    return []
            
            # Get results for time range
            results = self.camera.buffer_manager.get_analysis_results_for_save(start_time, end_time)
            
            # Filter results that match buffer snapshot by image index
            matching_results = []
            missing_indices = []
            
            for i, frame in enumerate(buffer_snapshot):
                # Try to get result by image index first (more reliable)
                if isinstance(frame, dict) and 'index' in frame:
                    result = self.camera.buffer_manager.get_analysis_result(frame['index'])
                elif isinstance(frame, dict) and 'timestamp' in frame:
                    # Find result by timestamp
                    for result in results:
                        if abs(result.image_timestamp - frame['timestamp']) < 0.1:  # 100ms tolerance
                            matching_results.append(result)
                            break
                else:
                    result = self.camera.buffer_manager.get_analysis_result(i)
                
                if result and not getattr(result, 'is_discarded', False):
                    matching_results.append(result)
                    logger.debug(f"Found pre-analyzed result for image {i}")
                else:
                    missing_indices.append(i)
            
            # Wait for missing analysis results if any
            if missing_indices:
                logger.info(f"Waiting for analysis completion of {len(missing_indices)} images: {missing_indices}")
                missing_results = self._wait_for_analysis_completion(missing_indices, buffer_snapshot)
                matching_results.extend(missing_results)
            
            logger.info(f"Found {len(matching_results)} matching pre-analyzed results out of {len(buffer_snapshot)} images")
            return matching_results
            
        except Exception as e:
            logger.error(f"Error getting pre-analyzed results: {e}")
            return []
    
    def _wait_for_analysis_completion(self, missing_indices: List[int], buffer_snapshot: List[np.ndarray]) -> List[Any]:
        """
        Wait for analysis completion of missing images.
        
        Args:
            missing_indices: List of image indices that are missing analysis results
            buffer_snapshot: Buffer snapshot for reference
            
        Returns:
            List[Any]: Analysis results for the missing images
        """
        if not missing_indices:
            return []
        
        logger.info(f"Waiting for analysis completion of {len(missing_indices)} images")
        
        max_wait_time = 30.0  # Maximum wait time in seconds
        poll_interval = 0.5   # Poll every 500ms
        start_time = time.time()
        
        completed_results = []
        still_missing = missing_indices.copy()
        
        while still_missing and (time.time() - start_time) < max_wait_time:
            for i, missing_index in enumerate(still_missing):
                try:
                    # Try to get result by image index
                    result = self.camera.buffer_manager.get_analysis_result(missing_index)
                    
                    if result and not getattr(result, 'is_discarded', False):
                        completed_results.append(result)
                        still_missing.remove(missing_index)
                        logger.info(f"✅ Analysis completed for image {missing_index} after waiting")
                    else:
                        # Check if image is still being processed
                        if hasattr(self.camera.buffer_manager, 'analysis_queue'):
                            task_status = self.camera.buffer_manager.analysis_queue.get_task_status(f"image_{missing_index}")
                            if task_status in ['completed', 'failed']:
                                # Task is done but no result found, mark as missing
                                logger.warning(f"Analysis task for image {missing_index} completed but no result found")
                                still_missing.remove(missing_index)
                        
                except Exception as e:
                    logger.debug(f"Error checking analysis status for image {missing_index}: {e}")
            
            if still_missing:
                elapsed = time.time() - start_time
                logger.debug(f"Still waiting for {len(still_missing)} images: {still_missing} (elapsed: {elapsed:.1f}s)")
                time.sleep(poll_interval)
        
        if still_missing:
            elapsed = time.time() - start_time
            logger.warning(f"Timeout waiting for analysis completion of {len(still_missing)} images: {still_missing} (waited {elapsed:.1f}s)")
        else:
            logger.info(f"✅ All {len(missing_indices)} missing images completed analysis")
        
        return completed_results
    
    def _use_pre_analyzed_results(self, saved_images: List[str], analysis_results: List[Any], skip_paths: Optional[Set[str]] = None) -> None:
        """Use pre-analyzed results for save operation without re-analyzing files."""
        try:
            if not analysis_results:
                logger.info("No pre-analyzed results provided; skipping use_pre_analyzed_results")
                return

            # Use first result as representative for initial fields
            first_result = analysis_results[0]

            # Get the shared inspection ID from the first result (should already exist)
            shared_inspection_id = getattr(first_result, 'inspection_id', None)
            if not shared_inspection_id:
                # Only create inspection record if it doesn't exist
                shared_inspection_id = self._create_inspection_record_from_pre_result(first_result)
                if not shared_inspection_id:
                    logger.error("Failed to create inspection record from pre-analyzed result")
                    self.camera.save_message = "保存失敗: 検査記録作成エラー"
                    return
                logger.info(f"🔍 Created new DB inspection_id={shared_inspection_id} for {len(saved_images)} images (pre-analyzed)")
            else:
                logger.info(f"🔍 Using existing DB inspection_id={shared_inspection_id} for {len(saved_images)} images (pre-analyzed)")

            # Update camera status payload using first result
            result_data = {
                "inspection_id": shared_inspection_id,
                "detections": getattr(first_result, 'detections', []),
                "confidence_above_threshold": getattr(first_result, 'confidence_above_threshold', False),
                "ai_threshold": getattr(first_result, 'ai_threshold', 50),
                "results": getattr(first_result, 'inspection_result', '無欠点'),
                "inspection_details": [
                    {
                        "error_type": det.get('class_id', 0),
                        "error_type_name": det.get('class_name', 'Unknown'),
                        "x_position": det.get('bbox', [0, 0, 0, 0])[0],
                        "y_position": det.get('bbox', [0, 0, 0, 0])[1],
                        "x2_position": det.get('bbox', [0, 0, 0, 0])[2],
                        "y2_position": det.get('bbox', [0, 0, 0, 0])[3],
                        "width": det.get('bbox', [0, 0, 0, 0])[2] - det.get('bbox', [0, 0, 0, 0])[0],
                        "height": det.get('bbox', [0, 0, 0, 0])[3] - det.get('bbox', [0, 0, 0, 0])[1],
                        "length": det.get('length', 0.0),
                        "confidence": det.get('confidence', 0.0),
                        "image_no": getattr(first_result, 'image_index', 0)
                    }
                    for det in getattr(first_result, 'detections', [])
                ]
            }
            self.camera.last_inspection_results = result_data
            self.camera.inspection_just_started = False

            # Save images to DB for this inspection
            self._save_images_to_db(shared_inspection_id, saved_images)

            # Save analysis results to database using memory analysis system
            if hasattr(self.camera, 'buffer_manager') and hasattr(self.camera.buffer_manager, 'analysis_processor'):
                success = self.camera.buffer_manager.analysis_processor.save_analysis_results_to_database(
                    shared_inspection_id, analysis_results
                )
                if success:
                    logger.info(f"Successfully saved {len(analysis_results)} analysis results to database")
                else:
                    logger.warning("Failed to save analysis results to database, using alternative method")
                    # Use alternative consolidation method
                    consolidated = self._convert_analysis_results_to_dicts(analysis_results)
                    self._consolidate_and_save_results(shared_inspection_id, consolidated)
            else:
                logger.warning("Memory analysis processor not available, using alternative consolidation")
                # Use alternative consolidation method
                consolidated = self._convert_analysis_results_to_dicts(analysis_results)
                self._consolidate_and_save_results(shared_inspection_id, consolidated)

            # Record timing measurements for pre-analyzed results to keep 1:1 tracking
            try:
                timing_collector = getattr(self.camera, 'timing_collector', None)
                if timing_collector and timing_collector.current_session:
                    for r in analysis_results:
                        try:
                            # Derive start/end times from created_at and processing_time if available
                            created_at = getattr(r, 'created_at', None)
                            processing_time = getattr(r, 'processing_time', None)
                            img_index = getattr(r, 'image_index', None)
                            task_id = getattr(r, 'task_id', None)
                            img_path = getattr(r, 'image_path', None)

                            # Fallbacks if fields are missing
                            if processing_time is None:
                                processing_time = 0.0
                            if created_at is None:
                                created_at = time.time()
                            # Skip if this path was analyzed at SAVE time
                            if skip_paths and img_path in skip_paths:
                                continue
                            # Skip if a runtime memory_analysis for same image already exists in session
                            try:
                                ms = timing_collector.current_session.measurements
                                duplicate_found = False
                                for m in ms:
                                    if m.operation_name == "memory_analysis":
                                        midx = (m.metadata or {}).get('image_index')
                                        if midx is not None and img_index is not None and midx == img_index:
                                            # If existing entry is not marked pre_analyzed, we consider it runtime and skip adding another
                                            if not ((m.metadata or {}).get('pre_analyzed', False)):
                                                duplicate_found = True
                                                break
                                if duplicate_found:
                                    continue
                            except Exception:
                                pass

                            start_dt = datetime.fromtimestamp(created_at)
                            end_dt = start_dt + timedelta(seconds=processing_time)
                            start_str = start_dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                            end_str = end_dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

                            # Append synthetic measurement directly
                            from .timing.timing_report import TimingMeasurement
                            tm = TimingMeasurement(
                                operation_name="memory_analysis",
                                start_time=start_str,
                                end_time=end_str,
                                duration=processing_time,
                                metadata={
                                    "image_index": img_index,
                                    "task_id": task_id,
                                    "image_path": img_path,
                                    "pre_analyzed": True
                                }
                            )
                            timing_collector.current_session.measurements.append(tm)
                        except Exception as _tm_err:
                            logger.debug(f"Could not append pre-analyzed timing: {_tm_err}")
            except Exception as _outer_tm_err:
                logger.debug(f"Timing append for pre-analyzed results failed: {_outer_tm_err}")

            # Start 5-group presentation processing using memory analysis (synchronously)
            self._start_memory_5group_presentation_processing_sync(shared_inspection_id, saved_images)

            # Update timing session metadata with inspection_id
            try:
                timing_collector = getattr(self.camera, 'timing_collector', None)
                if timing_collector and shared_inspection_id:
                    timing_collector.set_session_metadata(inspection_id=shared_inspection_id)
            except Exception:
                pass

            # Notify completion
            self.camera.save_message = f"保存完了 (事前分析済み) ({len(saved_images)}枚)"
            logger.info(f"Successfully finalized SAVE using {len(analysis_results)} pre-analyzed results (inspection_id={shared_inspection_id})")
        except Exception as e:
            logger.error(f"Error using pre-analyzed results: {e}")
            # Use real-time analysis
            self._analyze_saved_images(saved_images)

    def _create_inspection_record_from_pre_result(self, pre_result: Any) -> Optional[int]:
        """Create an Inspection row using fields from a pre-analyzed AnalysisResult object."""
        try:
            with SessionLocal() as session:
                # Extract folder path from image path
                image_path = getattr(pre_result, 'image_path', '')
                folder_path = os.path.dirname(image_path) if image_path else ''
                
                inspection = Inspection(
                    ai_threshold=getattr(pre_result, 'ai_threshold', getattr(self.camera, 'ai_threshold', 50)),
                    inspection_dt=datetime.now(),
                    folder_path=folder_path,
                    status=True,
                    results=getattr(pre_result, 'inspection_result', '無欠点')
                )
                session.add(inspection)
                session.commit()
                session.refresh(inspection)
                return inspection.inspection_id
        except Exception as e:
            logger.error(f"Failed creating inspection from pre-result: {e}")
            return None

    def _convert_analysis_results_to_dicts(self, analysis_results: List[Any]) -> List[Dict[str, Any]]:
        """Normalize AnalysisResult objects to dictionaries expected by consolidation."""
        normalized: List[Dict[str, Any]] = []
        try:
            for r in analysis_results:
                normalized.append({
                    'detections': getattr(r, 'detections', []),
                    'confidence_above_threshold': getattr(r, 'confidence_above_threshold', False),
                    'ai_threshold': getattr(r, 'ai_threshold', 50),
                    'max_length': getattr(r, 'max_length', 0.0),
                    'inspection_result': getattr(r, 'inspection_result', '無欠点')
                })
        except Exception as e:
            logger.error(f"Error converting analysis results: {e}")
        return normalized
            
    def _create_timing_reports(self, output_dir: str, buffer_snapshot: List[np.ndarray]) -> None:
        """Create timing report files"""
        if not DEBUG_CAPTURE_TIME or not DEBUG_MODE:
            return
            
        # Create summary report
        try:
            report_path = os.path.join(output_dir, "capture_timing_summary.txt")
            with open(report_path, "w") as f:
                now = datetime.now()
                f.write("CAPTURE TIMING REPORT\n")
                f.write("===================\n\n")
                f.write(f"Generated: {now.isoformat()}\n")
                f.write(f"Camera: BaslerCamera\n")
                f.write(f"FPS Setting: {self.camera.buffer_fps} (interval: {1.0/self.camera.buffer_fps:.3f}s)\n")
                f.write(f"Buffer Size: {self.camera.buffer_size} frames ({self.camera.max_buffer_seconds}s)\n\n")
                
                # Sensor events placeholder
                f.write("RECORD #1\n")
                f.write(f"  Start: {datetime.now().isoformat()}\n")
                f.write(f"  End: {datetime.now().isoformat()}\n")
                f.write(f"  Duration: 0.000s\n")
                f.write(f"  Result: unknown\n")
                f.write(f"  Frames Captured: {len(buffer_snapshot)}\n")
                f.write(f"  Actual FPS: 0.000\n")
                f.write(f"  FPS Accuracy: 0.0%\n")
                f.write("  Sensor Events: N/A\n")
                f.write("  Sensor Intervals: N/A\n")
                
            logger.info(f"Created timing report: {report_path}")
            
        except Exception as e:
            logger.error(f"Error creating timing report: {e}")
            
        # Create JSON report
        try:
            report_path = os.path.join(output_dir, "capture_timing_report.json")
            report_data = {
                "generated": datetime.now().isoformat(),
                "camera": "BaslerCamera",
                "settings": {
                    "fps": self.camera.buffer_fps,
                    "interval": 1.0/self.camera.buffer_fps,
                    "buffer_size": self.camera.buffer_size,
                    "max_seconds": self.camera.max_buffer_seconds,
                },
                "records": [
                    {
                        "start_time": datetime.now().isoformat(),
                        "end_time": datetime.now().isoformat(),
                        "duration": 0.0,
                        "result": "unknown",
                        "frames_captured": len(buffer_snapshot),
                        "actual_fps": 0.0,
                        "fps_accuracy": 0.0,
                        "sensor_events": []
                    }
                ]
            }
            
            with open(report_path, "w") as f:
                json.dump(report_data, f, indent=2)
                
            logger.info(f"Created JSON timing report: {report_path}")
            
        except Exception as e:
            logger.error(f"Error creating JSON timing report: {e}")
    
    def _generate_comprehensive_timing_report_from_session(self, completed_session, output_dir: str) -> None:
        """Generate comprehensive timing report from a finalized session."""
        if not DEBUG_CAPTURE_TIME or not DEBUG_MODE:
            return
            
        try:
            # Generate JSON timing report
            try:
                from .timing import TimingReport
                timing_collector = getattr(self.camera, 'timing_collector', None)
                if timing_collector:
                    timing_report = TimingReport(timing_collector)
                    json_report_path = timing_report.generate_session_report(completed_session, output_dir)
                    if json_report_path:
                        logger.info(f"Generated JSON timing report: {json_report_path}")
                    else:
                        logger.warning("Failed to generate JSON timing report")
                else:
                    logger.warning("No timing collector available for JSON report")
            except ImportError as e:
                logger.warning(f"Could not import TimingReport: {e}")
            except Exception as e:
                logger.error(f"Error generating JSON timing report: {e}")
            
            # Generate text timing report
            try:
                from .timing import TextReportGenerator
                text_report_generator = TextReportGenerator()
                text_report_path = text_report_generator.generate_session_report(completed_session, output_dir)
                if text_report_path:
                    logger.info(f"Generated text timing report: {text_report_path}")
                else:
                    logger.warning("Failed to generate text timing report")
            except ImportError as e:
                logger.warning(f"Could not import TextReportGenerator: {e}")
            except Exception as e:
                logger.error(f"Error generating text timing report: {e}")
                
        except Exception as e:
            logger.error(f"Error in comprehensive timing report generation: {e}")
            
    def _save_buffer_images(self, buffer_snapshot: List[np.ndarray], output_dir: str) -> List[str]:
        """Save buffer images to disk and record in database"""
        saved_paths = []
        
        # Start timing measurement for image saving
        timing_collector = getattr(self.camera, 'timing_collector', None)
        image_save_measurement_id = None
        if timing_collector:
            image_save_measurement_id = timing_collector.start_measurement(
                "image_saving", 
                {"output_dir": output_dir, "image_count": len(buffer_snapshot)}
            )
        
        try:
            # Ensure directory exists
            os.makedirs(output_dir, exist_ok=True)
            
            # Save all images
            for i, image in enumerate(buffer_snapshot):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S%f")[:-3]
                # filename = f"frame_{i:04d}_{timestamp}.bmp"
                filename = f"No_{i:04d}.bmp"
                filepath = os.path.join(output_dir, filename)
                
                # Convert RGB to BGR for OpenCV
                img_bgr = self.image_processor.rgb_to_bgr(image)
                if cv2.imwrite(filepath, img_bgr):
                    saved_paths.append(filepath)
                    
                    # Add individual image save timing measurement
                    if timing_collector:
                        individual_save_id = timing_collector.start_measurement(
                            "individual_image_save",
                            {"image_path": filepath, "image_no": i, "filename": filename}
                        )
                        # End immediately as this is just for tracking
                        timing_collector.end_measurement("individual_image_save", individual_save_id)
                    
            logger.info(f"Saved {len(saved_paths)} images to {output_dir}")
            
        except Exception as e:
            logger.error(f"Error saving buffer images: {e}")
        
        # End timing measurement for image saving
        if timing_collector and image_save_measurement_id:
            timing_collector.end_measurement("image_saving", image_save_measurement_id)
            
        return saved_paths
        
    def _save_images_to_db(self, inspection_id: int, image_paths: List[str]) -> None:
        """Save image records to the database"""
        if not image_paths or not inspection_id:
            logger.warning("No images or inspection ID to save to database")
            return
            
        logger.info(f"Saving {len(image_paths)} image records to database for inspection ID {inspection_id}")
        
        try:
            with SessionLocal() as session:
                # Create records for all images
                for i, image_path in enumerate(image_paths):
                    # Extract image number from filename (e.g. No_0001.bmp -> 1)
                    image_no = 0
                    try:
                        filename = os.path.basename(image_path)
                        if filename.startswith('No_') and filename.endswith('.bmp'):
                            image_no = int(filename[3:7])
                    except Exception as e:
                        logger.warning(f"Could not extract image number from filename {filename}: {e}")
                        image_no = i  # Use the sequence index
                    
                    # Create image record
                    image_record = InspectionImage(
                        inspection_id=inspection_id,
                        image_no=image_no,
                        image_path=image_path,
                        image_type='raw',
                        image_metadata=json.dumps({
                            "sequence": i,
                            "camera_type": "basler",
                            "fps": self.camera.buffer_fps
                        })
                    )
                    session.add(image_record)
                
                # Commit all records at once
                session.commit()
                logger.info(f"Successfully saved {len(image_paths)} image records to database")
                
        except Exception as e:
            logger.error(f"Error saving image records to database: {e}")
            
    def _analyze_saved_images(self, image_paths: List[str]) -> None:
        """Analyze saved images using memory analysis system"""
        if not image_paths:
            logger.warning("No images to analyze")
            return

        logger.info(f"Starting memory analysis of {len(image_paths)} images")

        # Use memory analysis system instead of parallel processing
        try:
            # Check if memory analysis is available
            if not hasattr(self.camera, 'buffer_manager') or not self.camera.buffer_manager:
                logger.error("Memory analysis system not available")
                self.camera.save_message = "保存失敗: メモリ分析システムが利用できません"
                return
            
            if not getattr(self.camera.buffer_manager, 'memory_analysis_enabled', False):
                logger.error("Memory analysis not enabled")
                self.camera.save_message = "保存失敗: メモリ分析が有効になっていません"
                return
            
            # Use memory analysis system
            self._analyze_saved_images_memory_aware_new(image_paths)
            
        except Exception as e:
            logger.error(f"Error in memory analysis: {e}")
            self.camera.save_message = "保存失敗: メモリ分析エラー"

    def _analyze_saved_images_memory_aware_new(self, image_paths: List[str]) -> None:
        """
        Analyze saved images using memory analysis system.
        
        This method reuses pre-analyzed results from memory and finalizes SAVE
        without any re-analysis.
        """
        try:
            logger.info(f"Starting memory-aware analysis of {len(image_paths)} images")
            
            # Check if memory analysis system is available
            if not hasattr(self.camera, 'buffer_manager') or not self.camera.buffer_manager:
                logger.error("Memory analysis system not available")
                self.camera.save_message = "保存失敗: メモリ分析システムが利用できません"
                return
            
            # Reuse pre-analyzed result objects from memory; do not re-analyze files
            pre_result_objects: List[Any] = []
            try:
                if hasattr(self.camera.buffer_manager, 'get_analysis_result'):
                    for path in image_paths:
                        image_no = self._extract_image_no_from_path(path)
                        if image_no is None:
                            continue
                        res = self.camera.buffer_manager.get_analysis_result(image_no)
                        if res and not getattr(res, 'is_discarded', False):
                            # Update the image path to use the actual disk file path instead of memory-preview
                            res.image_path = path
                            pre_result_objects.append(res)
                logger.info(f"Reused {len(pre_result_objects)} pre-analyzed results from memory for SAVE")
            except Exception as e:
                logger.warning(f"Failed to fetch pre-analyzed results in SAVE flow: {e}")
                pre_result_objects = []
            
            # Wait for ALL missing results during SAVE to ensure complete analysis
            if len(pre_result_objects) < len(image_paths) and hasattr(self.camera, 'buffer_manager'):
                missing_count = len(image_paths) - len(pre_result_objects)
                logger.info(f"Waiting for {missing_count} missing analysis results...")
                
                import time as _t
                max_wait_time = 30.0  # 30 seconds max wait for complete analysis
                poll_interval = 0.5   # Poll every 500ms
                start_time = _t.time()
                
                while len(pre_result_objects) < len(image_paths) and (_t.time() - start_time) < max_wait_time:
                    res_objs = []
                    try:
                        for path in image_paths:
                            ino = self._extract_image_no_from_path(path)
                            if ino is None:
                                continue
                            r = self.camera.buffer_manager.get_analysis_result(ino)
                            if r and not getattr(r, 'is_discarded', False):
                                # Update the image path to use the actual disk file path
                                r.image_path = path
                                res_objs.append(r)
                        
                        if len(res_objs) == len(image_paths):
                            pre_result_objects = res_objs
                            logger.info(f"✅ Successfully found all {len(pre_result_objects)} analysis results")
                            break
                        elif len(res_objs) > len(pre_result_objects):
                            # Found some new results
                            pre_result_objects = res_objs
                            logger.info(f"Found {len(pre_result_objects)} analysis results, still waiting for {len(image_paths) - len(pre_result_objects)} more")
                    except Exception as e:
                        logger.debug(f"Error checking analysis results: {e}")
                    
                    _t.sleep(poll_interval)
                
                if len(pre_result_objects) < len(image_paths):
                    missing_count = len(image_paths) - len(pre_result_objects)
                    logger.warning(f"⚠️ Still missing {missing_count} analysis results after waiting {max_wait_time}s")
                    logger.warning("This may cause presentation groups D and E to show NO IMAGE")
                else:
                    logger.info(f"✅ All {len(pre_result_objects)} analysis results are ready for presentation processing")

            if pre_result_objects:
                # First, ensure all pre_result_objects have the shared inspection ID
                # Get the shared inspection ID from the first result or create one
                shared_inspection_id = None
                if pre_result_objects:
                    shared_inspection_id = getattr(pre_result_objects[0], 'inspection_id', None)
                
                if shared_inspection_id is None:
                    # Create shared inspection ID from first result
                    first_result = pre_result_objects[0]
                    shared_inspection_id = self._create_inspection_record_from_pre_result(first_result)
                    if shared_inspection_id:
                        logger.info(f"🔍 Created shared inspection ID {shared_inspection_id} for memory analysis")
                        # Update all pre_result_objects with the shared inspection ID
                        for r in pre_result_objects:
                            r.inspection_id = shared_inspection_id
                    else:
                        logger.error("Failed to create shared inspection ID for memory analysis")
                        return
                
                # Determine missing images (by path) and perform inline memory analysis to ensure 1:1 coverage
                try:
                    have_paths = set()
                    for r in pre_result_objects:
                        try:
                            if getattr(r, 'image_path', None):
                                have_paths.add(r.image_path)
                        except Exception:
                            pass
                    missing_pairs = []  # list of (image_no, path)
                    for path in image_paths:
                        if path in have_paths:
                            continue
                        ino = self._extract_image_no_from_path(path)
                        missing_pairs.append((ino, path))

                    if missing_pairs and hasattr(self.camera.buffer_manager, 'analysis_processor'):
                        logger.info(f"Performing inline memory analysis for {len(missing_pairs)} missing images during SAVE")
                        analyzed_paths: Set[str] = set()
                        for ino, path in missing_pairs:
                            try:
                                # Inline analysis using the memory processor (with timing)
                                # Use the shared inspection ID that was just created/ensured above
                                if shared_inspection_id is None:
                                    logger.error("No shared inspection ID available for inline analysis")
                                    continue
                                    
                                res = self._analyze_image_with_memory_processor(
                                    self.camera.buffer_manager.analysis_processor,
                                    path,
                                    ino,
                                    shared_inspection_id=shared_inspection_id
                                )
                                if res:
                                    # Create AnalysisResult-like object to unify with pre_result_objects
                                    class _TempRes:
                                        pass
                                    tr = _TempRes()
                                    tr.image_index = ino if ino is not None else -1
                                    tr.image_path = path
                                    tr.detections = res.get('detections', [])
                                    tr.confidence_above_threshold = res.get('confidence_above_threshold', False)
                                    tr.ai_threshold = res.get('ai_threshold', getattr(self.camera, 'ai_threshold', 50))
                                    tr.max_length = res.get('max_length', 0.0)
                                    tr.inspection_result = res.get('results', '無欠点')
                                    tr.inspection_id = shared_inspection_id  # Set the shared inspection ID
                                    tr.created_at = time.time()
                                    tr.processing_time = 0.0
                                    pre_result_objects.append(tr)
                                    analyzed_paths.add(path)
                            except Exception as e:
                                logger.warning(f"Inline memory analysis failed for image {ino}: {e}")

                except Exception as e:
                    logger.debug(f"Error resolving missing analyses inline: {e}")

                # Use the existing helper to finalize SAVE using (now complete) results
                self._use_pre_analyzed_results(image_paths, pre_result_objects, skip_paths=analyzed_paths if 'analyzed_paths' in locals() else None)
                return

            # No pre-analyzed results available
            logger.error("No pre-analyzed results available for memory-aware processing")
            self.camera.save_message = "保存失敗: 事前分析結果がありません"
            return

        except Exception as e:
            logger.error(f"Error in memory-aware analysis: {e}")
            self.camera.save_message = "保存失敗: メモリ分析エラー"
            return
    
    def _analyze_image_with_memory_processor(self, memory_processor, image_path: str, image_no: int, shared_inspection_id: int) -> Dict[str, Any]:
        """
        Analyze image using memory analysis processor directly.
        
        Args:
            memory_processor: MemoryAnalysisProcessor instance
            image_path: Path to the image file
            image_no: Image number extracted from filename
            shared_inspection_id: REQUIRED shared inspection ID (must not be None)
            
        Returns:
            Dict[str, Any]: Analysis results with shared inspection ID
        """
        try:
            if shared_inspection_id is None:
                logger.error(f"shared_inspection_id is required for memory analysis of image: {image_path}")
                return None
                
            logger.info(f"🔍 Using memory analysis processor for image: {image_path} with shared_inspection_id: {shared_inspection_id}")
            
            # Use the memory processor's internal analysis method
            # This bypasses the old image_analyzer.py completely
            analysis_result = memory_processor._analyze_image_memory_only(image_path)
            
            if not analysis_result:
                logger.warning(f"Memory analysis returned no result for {image_path}")
                return None
            
            # Convert memory analysis result to the expected format
            result_data = {
                "inspection_id": shared_inspection_id,  # Always use the shared inspection ID
                "detections": analysis_result.get('detections', []),
                "confidence_above_threshold": analysis_result.get('confidence_above_threshold', False),
                "ai_threshold": self.camera.ai_threshold,
                "results": analysis_result.get('results', '無欠点'),
                "max_length": analysis_result.get('max_length', 0.0),
                "inspection_result": analysis_result.get('results', '無欠点')
            }
            
            # NEVER create inspection records in memory analysis - use shared_inspection_id only
            logger.info(f"🔍 Memory analysis completed for image {image_no}: {result_data.get('results')} (shared_inspection_id: {shared_inspection_id})")
            return result_data
            
        except Exception as e:
            logger.error(f"Error in memory analysis processor: {e}")
            return None
    
    def _create_inspection_record(self, image_path: str, analysis_result: Dict[str, Any]) -> int:
        """
        Create a new inspection record in the database.
        
        Args:
            image_path: Path to the image file
            analysis_result: Analysis result from memory processor
            
        Returns:
            int: New inspection ID
        """
        try:
            from db import Inspection
            from db.engine import SessionLocal
            from datetime import datetime
            
            with SessionLocal() as session:
                inspection = Inspection(
                    ai_threshold=self.camera.ai_threshold,
                    inspection_dt=datetime.now(),
                    folder_path=os.path.dirname(image_path),
                    status=True,
                    results=analysis_result.get('results', '無欠点')
                )
                session.add(inspection)
                session.commit()
                session.refresh(inspection)
                
                logger.info(f"🔍 Created new inspection record: {inspection.inspection_id}")
                return inspection.inspection_id
                
        except Exception as e:
            logger.error(f"Error creating inspection record: {e}")
            return None

    def _store_analysis_result_in_memory(self, image_no: int, image_path: str, result: Dict[str, Any]) -> None:
        """
        Store analysis result in memory analysis system.
        
        Args:
            image_no: Image number
            image_path: Path to the image
            result: Analysis result dictionary
        """
        try:
            if not hasattr(self.camera, 'buffer_manager') or not self.camera.buffer_manager:
                return
            
            # Create AnalysisResult object for memory storage
            from .memory_analysis.analysis_queue import AnalysisResult
            
            analysis_result = AnalysisResult(
                task_id=f"task_{image_no}",
                image_timestamp=time.time(),
                image_index=image_no,
                image_hash=f"hash_{image_no}",
                image_path=image_path,
                detections=result.get('detections', []),
                confidence_above_threshold=result.get('confidence_above_threshold', False),
                max_length=result.get('max_length', 0.0),
                inspection_result=result.get('inspection_result', '無欠点'),
                ai_threshold=result.get('ai_threshold', 50),
                processing_time=result.get('processing_time', 0.1),
                created_at=time.time(),
                last_accessed=time.time(),
                is_discarded=False
            )
            
            # Store in memory analysis system
            if hasattr(self.camera.buffer_manager, 'results_storage'):
                self.camera.buffer_manager.results_storage.store_result(analysis_result)
            
            if hasattr(self.camera.buffer_manager, 'result_cache'):
                self.camera.buffer_manager.result_cache.put(f"image_{image_no}", analysis_result)
            
            logger.debug(f"Stored analysis result for image {image_no} in memory")
            
        except Exception as e:
            logger.error(f"Error storing analysis result in memory: {e}")


    def _consolidate_and_save_results(self, inspection_id: int, analysis_results: List[Dict[str, Any]]) -> None:
        """
        Consolidate analysis results and save to database.

        Args:
            inspection_id: Inspection ID
            analysis_results: List of analysis results
        """
        try:
            if not analysis_results:
                logger.warning(f"No analysis results to consolidate for inspection {inspection_id}")
                return
            
            # Calculate consolidated values
            max_length = 0.0
            has_defects = False
            inspection_result = "無欠点"
            
            for result in analysis_results:
                # Check if any defects were found
                if result.get('confidence_above_threshold', False):
                    has_defects = True
                    inspection_result = "こぶし"  # Default to こぶし if defects found
                
                # Get max length from detections
                detections = result.get('detections', [])
                for detection in detections:
                    length = detection.get('length', 0.0)
                    if length > max_length:
                        max_length = length
            
            # Determine final result
            if has_defects:
                if max_length >= 10.0:
                    inspection_result = "節あり"
                else:
                    inspection_result = "こぶし"
            else:
                inspection_result = "無欠点"
                max_length = 0.0
            
            logger.info(f"Consolidated results for inspection {inspection_id}: {inspection_result}, max_length: {max_length}mm")
            
            # Save to database
            with SessionLocal() as session:
                try:
                    # Update or create InspectionResult
                    result_record = session.query(InspectionResult).filter_by(inspection_id=inspection_id).first()
                    if result_record:
                        result_record.length = max_length
                        result_record.results = inspection_result
                        logger.info(f"Updated InspectionResult for inspection {inspection_id}")
                    else:
                        # Create new result record
                        result_record = InspectionResult(
                            inspection_id=inspection_id,
                            length=max_length,
                            results=inspection_result
                        )
                        session.add(result_record)
                        logger.info(f"Created new InspectionResult for inspection {inspection_id}")
                    
                    # Update Inspection record
                    inspection_record = session.query(Inspection).filter_by(inspection_id=inspection_id).first()
                    if inspection_record:
                        inspection_record.results = inspection_result
                        inspection_record.status = True  # Mark as completed
                        logger.info(f"Updated Inspection record for inspection {inspection_id}")
                    
                    session.commit()
                    logger.info(f"Successfully consolidated and saved results for inspection {inspection_id}")

                except Exception as e:
                    session.rollback()
                    logger.error(f"Error consolidating results: {e}")
                    raise
        except Exception as e:
            logger.error(f"Error in _consolidate_and_save_results: {e}")

    def _start_presentation_processing(self, inspection_id: int, image_paths: List[str]) -> None:
        """
        Start presentation processing using 5-group distribution logic.

        Args:
            inspection_id: Inspection ID for presentation processing
            image_paths: List of image paths to process
        """
        try:
            logger.info(f"Starting 5-group presentation processing for inspection {inspection_id} with {len(image_paths)} images")
            
            # Create 5-group distribution (A-E) instead of using parallel processor
            distributed_images = self._create_5_group_distribution(image_paths)
            
            if distributed_images:
                logger.info(f"Created 5-group distribution: {list(distributed_images.keys())}")
                # Use the new 5-group presentation processing
                self._start_presentation_processing_with_groups(inspection_id, distributed_images)
            else:
                logger.warning("No images to process for presentation")

        except Exception as e:
            logger.error(f"Error in 5-group presentation processing: {e}")
            # Try alternative processing
            try:
                if hasattr(self.camera, 'presentation_processor'):
                    self.camera.presentation_processor.save_presentation_images(inspection_id)
                    logger.info(f"Alternative presentation processing completed for inspection {inspection_id}")
            except Exception as alt_error:
                logger.error(f"Alternative presentation processing also failed: {alt_error}")

    def _create_5_group_distribution(self, image_paths: List[str]) -> Dict[str, List[str]]:
        """
        Create 5-group distribution (A-E) from image paths.
        
        Args:
            image_paths: List of image paths to distribute
            
        Returns:
            Dict[str, List[str]]: Dictionary mapping group names (A-E) to image paths
        """
        try:
            if not image_paths:
                logger.warning("No image paths provided for 5-group distribution")
                return {}
            
            # Extract image numbers and sort them
            image_data = []
            for image_path in image_paths:
                image_no = self._extract_image_no_from_path(image_path)
                if image_no is not None:
                    image_data.append((image_no, image_path))
            
            if not image_data:
                logger.warning("No valid image numbers found in paths")
                return {}
            
            # Sort by image number
            image_data.sort(key=lambda x: x[0])
            
            # Create 5-group distribution
            fixed_groups = ['A', 'B', 'C', 'D', 'E']
            total_images = len(image_data)
            images_per_group = total_images // 5
            remainder = total_images % 5
            
            logger.info(f"Distributing {total_images} images into 5 groups: {images_per_group} base + {remainder} extra")
            
            distributed_images = {}
            current_idx = 0
            
            for i, group_label in enumerate(fixed_groups):
                # Add one extra image to first 'remainder' groups
                group_size = images_per_group + (1 if i < remainder else 0)
                
                if current_idx < total_images:
                    end_idx = min(current_idx + group_size, total_images)
                    group_image_paths = [image_data[j][1] for j in range(current_idx, end_idx)]
                    
                    distributed_images[group_label] = group_image_paths
                    current_idx = end_idx
                    
                    logger.info(f"  Group {group_label}: {len(group_image_paths)} images")
            
            return distributed_images
            
        except Exception as e:
            logger.error(f"Error creating 5-group distribution: {e}")
            return {}

    def _run_parallel_presentation_processing(self, inspection_id: int,
                                            distributed_images: Dict[str, List[str]]) -> None:
        """
        Run parallel presentation processing in background thread.

        Args:
            inspection_id: Inspection ID
            distributed_images: Dictionary mapping group names to image paths
        """
        try:
            # Use memory presentation processor instead of parallel processor
            result = self.memory_presentation_processor.process_presentation_images_memory_aware(
                inspection_id, distributed_images
            )

            if result.get('success'):
                logger.info(f"Memory-aware presentation processing completed successfully for inspection {inspection_id}")
            else:
                logger.warning(f"Memory-aware presentation processing failed for inspection {inspection_id}: "
                             f"{result.get('error', 'unknown error')}")

        except Exception as e:
            logger.error(f"Error in memory-aware presentation processing thread: {e}")
            # Try alternative processing
            try:
                all_image_paths = []
                for paths in distributed_images.values():
                    all_image_paths.extend(paths)
                self.camera._process_presentation_images_background(inspection_id, all_image_paths)
            except Exception as alt_error:
                logger.error(f"Error in alternative presentation processing: {alt_error}")
    
    def _start_memory_5group_presentation_processing_sync(self, inspection_id: int, saved_images: List[str]) -> None:
        """
        Start memory-aware 5-group presentation processing synchronously.
        
        This ensures the save session doesn't end until presentation processing is complete.
        
        Args:
            inspection_id: Inspection ID
            saved_images: List of saved image paths
        """
        try:
            # Import the new memory 5-group presentation processor
            from .memory_analysis.memory_5group_presentation_processor import Memory5GroupPresentationProcessor
            
            # Initialize processor if not already available
            if not hasattr(self, 'memory_5group_processor'):
                self.memory_5group_processor = Memory5GroupPresentationProcessor(self.camera)
            
            # Run synchronously (not in background thread)
            result = self.memory_5group_processor.process_5group_presentation_memory_aware(
                inspection_id, saved_images
            )
            
            if result.get('success'):
                logger.info(f"Memory 5-group presentation processing completed successfully for inspection {inspection_id}")
                logger.info(f"Processed {result.get('processing_metrics', {}).get('total_images', 0)} images across {result.get('processing_metrics', {}).get('groups_processed', 0)} groups")
            else:
                logger.warning(f"Memory 5-group presentation processing failed for inspection {inspection_id}: "
                             f"{result.get('error', 'unknown error')}")
                # Try alternative presentation processing
                try:
                    self._start_presentation_processing(inspection_id, saved_images)
                except Exception as alt_error:
                    logger.error(f"Error in alternative presentation processing: {alt_error}")
            
        except Exception as e:
            logger.error(f"Error in synchronous memory 5-group presentation processing: {e}")
            # Try alternative presentation processing
            try:
                self._start_presentation_processing(inspection_id, saved_images)
            except Exception as alt_error:
                logger.error(f"Error in alternative presentation processing: {alt_error}")
    
    def _start_memory_5group_presentation_processing(self, inspection_id: int, saved_images: List[str]) -> None:
        """
        Start memory-aware 5-group presentation processing in background thread.
        
        Args:
            inspection_id: Inspection ID
            saved_images: List of saved image paths
        """
        try:
            # Import the new memory 5-group presentation processor
            from .memory_analysis.memory_5group_presentation_processor import Memory5GroupPresentationProcessor
            
            # Initialize processor if not already available
            if not hasattr(self, 'memory_5group_processor'):
                self.memory_5group_processor = Memory5GroupPresentationProcessor(self.camera)
            
            # Run in background thread
            def run_memory_5group_processing():
                try:
                    result = self.memory_5group_processor.process_5group_presentation_memory_aware(
                        inspection_id, saved_images
                    )
                    
                    if result.get('success'):
                        logger.info(f"Memory 5-group presentation processing completed successfully for inspection {inspection_id}")
                        logger.info(f"Processed {result.get('processing_metrics', {}).get('total_images', 0)} images across {result.get('processing_metrics', {}).get('groups_processed', 0)} groups")
                    else:
                        logger.warning(f"Memory 5-group presentation processing failed for inspection {inspection_id}: "
                                     f"{result.get('error', 'unknown error')}")
                        
                except Exception as e:
                    logger.error(f"Error in memory 5-group presentation processing: {e}")
                    # Try alternative presentation processing
                    try:
                        self._start_presentation_processing(inspection_id, saved_images)
                    except Exception as alt_error:
                        logger.error(f"Error in alternative presentation processing: {alt_error}")
            
            # Start background thread
            import threading
            thread = threading.Thread(target=run_memory_5group_processing, daemon=True)
            thread.start()
            logger.info(f"Started memory 5-group presentation processing thread for inspection {inspection_id}")
            
        except Exception as e:
            logger.error(f"Error starting memory 5-group presentation processing: {e}")
            # Try alternative presentation processing
            try:
                self._start_presentation_processing(inspection_id, saved_images)
            except Exception as alt_error:
                logger.error(f"Error in alternative presentation processing: {alt_error}")
    
    def _handle_pass_l_to_r_split(self, saved_images: List[str]) -> None:
        """
        Handle PASS_L_TO_R split into fixed 5 groups.
        
        Args:
            saved_images: List of saved image paths
        """
        try:
            if not saved_images:
                return
            
            # Get temp section assembler from buffer manager
            if not hasattr(self.camera, 'buffer_manager') or not self.camera.buffer_manager:
                logger.warning("No buffer manager available for PASS_L_TO_R split")
                return
            
            assembler = self.camera.buffer_manager.temp_section_assembler
            if not assembler:
                logger.warning("No temp section assembler available for PASS_L_TO_R split")
                return
            
            # Determine image number range from saved images
            # Extract image numbers from file paths (assuming format like image_001.jpg)
            image_numbers = []
            for image_path in saved_images:
                try:
                    # Extract number from filename
                    filename = os.path.basename(image_path)
                    # Remove extension and extract number
                    name_without_ext = os.path.splitext(filename)[0]
                    if '_' in name_without_ext:
                        number_str = name_without_ext.split('_')[-1]
                        image_numbers.append(int(number_str))
                except (ValueError, IndexError) as e:
                    logger.warning(f"Could not extract image number from {image_path}: {e}")
                    continue
            
            if not image_numbers:
                logger.warning("No valid image numbers found for PASS_L_TO_R split")
                return
            
            image_numbers.sort()
            min_image_no = min(image_numbers)
            max_image_no = max(image_numbers)
            total_images = len(image_numbers)
            
            logger.info(f"PASS_L_TO_R split: {total_images} images, range {min_image_no}-{max_image_no}")
            
            # Split into exactly 5 groups (A-E) with even distribution
            fixed_groups = ['A', 'B', 'C', 'D', 'E']
            groups = []
            
            # Calculate images per group
            images_per_group = total_images // 5
            remainder = total_images % 5
            
            logger.info(f"Distributing {total_images} images into 5 groups: {images_per_group} base + {remainder} extra")
            
            # Distribute images evenly across 5 groups
            current_idx = 0
            for i, group_label in enumerate(fixed_groups):
                # Add one extra image to first 'remainder' groups
                group_size = images_per_group + (1 if i < remainder else 0)
                
                if current_idx < total_images:
                    end_idx = min(current_idx + group_size, total_images)
                    group_images = image_numbers[current_idx:end_idx]
                    
                    groups.append({
                        'label': group_label,
                        'image_numbers': group_images,
                        'count': len(group_images)
                    })
                    
                    current_idx = end_idx
                    logger.info(f"  Group {group_label}: {len(group_images)} images (indices {current_idx - len(group_images)}-{current_idx - 1})")
            
            # Create save sections data
            save_sections = {
                'event': 'save_sections',
                'data': {
                    'groups': groups,
                    'total_images': total_images,
                    'image_range': f"{min_image_no}-{max_image_no}",
                    'timestamp': time.time()
                }
            }
            
            logger.info(f"Created PASS_L_TO_R save sections: {len(groups)} groups (A-E)")
            for group in groups:
                logger.info(f"  Group {group['label']}: {group['count']} images")
            
            # Mark all temp sections as saved
            all_sections = assembler.get_all_sections()
            for section in all_sections:
                if section.status == 'completed':
                    assembler.mark_section_saved(section.id)
            
            # Convert groups to distributed_images format for presentation processing
            distributed_images = {}
            for group in groups:
                group_label = group['label']
                group_image_numbers = group['image_numbers']
                
                # Convert image numbers back to image paths
                group_image_paths = []
                for image_no in group_image_numbers:
                    # Find the corresponding image path from saved_images
                    for saved_image in saved_images:
                        if self._extract_image_no_from_path(saved_image) == image_no:
                            group_image_paths.append(saved_image)
                            break
                
                if group_image_paths:
                    distributed_images[group_label] = group_image_paths
                    logger.info(f"Group {group_label}: {len(group_image_paths)} image paths")
            
             # Note: Presentation processing is already handled by _start_presentation_processing
             # in the memory analysis flow, so we don't need to call it again here
            
            # TODO: Send save_sections event via SSE
            # This would be implemented with a proper SSE broadcaster
            logger.info("PASS_L_TO_R split completed - save_sections event ready for SSE")
            
        except Exception as e:
            logger.error(f"Error in PASS_L_TO_R split: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    def _extract_image_no_from_path(self, image_path: str) -> Optional[int]:
        """
        Extract image_no from image path using "No_????" pattern.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Optional[int]: Extracted image number or None if not found
        """
        import re
        
        if not image_path:
            return None
        
        try:
            # Look for "No_" followed by digits in the path
            matches = re.findall(r'No_(\d+)', image_path)
            if matches:
                # Use the last match in case there are multiple "No_" patterns
                image_no_str = matches[-1]
                image_no = int(image_no_str)
                return image_no
            else:
                return None
        except Exception as e:
            logger.error(f"Error extracting image_no from path {image_path}: {e}")
            return None
    
    def _start_presentation_processing_with_groups(self, inspection_id: int, distributed_images: Dict[str, List[str]]) -> None:
        """
        Start presentation processing with the 5-group distribution.
        
        Args:
            inspection_id: Inspection ID
            distributed_images: Dictionary mapping group names (A-E) to image paths
        """
        try:
            # Use memory presentation processor instead of parallel processor
            result = self.memory_presentation_processor.process_presentation_images_memory_aware(
                inspection_id, distributed_images
            )

            if result.get('success'):
                logger.info(f"Memory-aware presentation processing completed successfully for inspection {inspection_id}")
            else:
                logger.warning(f"Memory-aware presentation processing failed for inspection {inspection_id}: "
                             f"{result.get('error', 'unknown error')}")

        except Exception as e:
            logger.error(f"Error in memory-aware presentation processing thread: {e}")
            # Try alternative processing
            try:
                all_image_paths = []
                for paths in distributed_images.values():
                    all_image_paths.extend(paths)
                
                # Try alternative presentation processing
                if hasattr(self.camera, 'presentation_processor'):
                    self.camera.presentation_processor.save_presentation_images(inspection_id)
                    logger.info(f"Alternative presentation processing completed for inspection {inspection_id}")
                else:
                    logger.error("No alternative presentation processor available")
            except Exception as alt_error:
                logger.error(f"Alternative presentation processing also failed: {alt_error}")