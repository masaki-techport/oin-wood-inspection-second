"""
Event processing functionality for Basler camera module.
"""

import os
import time
import logging
import threading
import queue
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import numpy as np
import cv2

from .image_processor import ImageProcessor
from db.inspection_images import InspectionImage
from db.engine import SessionLocal

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
        
        logger.info(f"Processing save event with {len(buffer_snapshot)} frames")
        
        if not buffer_snapshot:
            logger.warning("No frames to save")
            self.camera.save_message = "保存失敗 (0枚)"  # "Save failed" in Japanese
            return
            
        # Create timing reports
        self._create_timing_reports(output_dir, buffer_snapshot)
        
        # Save the images
        saved_images = self._save_buffer_images(buffer_snapshot, output_dir)
        
        # Update camera status
        self.camera.save_message = f"保存完了 ({len(saved_images)}枚)"  # "Save completed" in Japanese
        
        # Run inference on the saved images
        if saved_images:
            self._analyze_saved_images(saved_images)
            
    def _create_timing_reports(self, output_dir: str, buffer_snapshot: List[np.ndarray]) -> None:
        """Create timing report files"""
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
            
    def _save_buffer_images(self, buffer_snapshot: List[np.ndarray], output_dir: str) -> List[str]:
        """Save buffer images to disk and record in database"""
        saved_paths = []
        
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
                    
            logger.info(f"Saved {len(saved_paths)} images to {output_dir}")
            
        except Exception as e:
            logger.error(f"Error saving buffer images: {e}")
            
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
                        image_no = i  # Fallback to using the sequence index
                    
                    # Create image record
                    image_record = InspectionImage(
                        inspection_id=inspection_id,
                        image_no=image_no,
                        image_path=image_path,
                        image_type='raw',
                        capture_timestamp=datetime.now(),
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
        """Analyze saved images using parallel or sequential processing"""
        if not image_paths:
            logger.warning("No images to analyze")
            return

        logger.info(f"Starting analysis of {len(image_paths)} images")

        # Try parallel processing first, fallback to sequential if needed
        if hasattr(self.camera, 'parallel_processor') and self.camera.parallel_processor.enabled:
            logger.info("Using parallel processing for image analysis")
            try:
                result = self.camera.parallel_processor.process_images_parallel(image_paths)
                if result:
                    logger.info(f"🔍 Parallel processing completed successfully")
                    return
                else:
                    logger.warning("Parallel processing returned no result, falling back to sequential")
            except Exception as e:
                logger.error(f"Parallel processing failed: {e}, falling back to sequential")
        else:
            logger.info("Parallel processing not available, using sequential processing")

        # Fallback to sequential processing
        self._analyze_saved_images_sequential(image_paths)

    def _analyze_saved_images_sequential(self, image_paths: List[str]) -> None:
        """Sequential image analysis (original implementation)"""
        if not image_paths:
            logger.warning("No images to analyze")
            return

        logger.info(f"Starting sequential analysis of {len(image_paths)} images")

        # Create a shared inspection ID for all images
        shared_inspection_id = None

        # Analyze first image to get inspection ID
        if image_paths:
            logger.info(f"🔍 Starting analysis of first image: {image_paths[0]}")
            first_result = self.camera._analyze_image(image_paths[0])
            if first_result and 'inspection_id' in first_result:
                shared_inspection_id = first_result['inspection_id']
                logger.info(f"🔍 Created shared inspection ID: {shared_inspection_id}")
                logger.info(f"🔍 First analysis result: {first_result}")

                # Save this result to camera for API access
                self.camera.last_inspection_results = first_result
                logger.info(f"🔍 Stored inspection results in camera.last_inspection_results")

                # Save images to database
                self._save_images_to_db(shared_inspection_id, image_paths)
            else:
                logger.warning(f"🔍 Analysis of first image failed or returned no inspection_id: {first_result}")

        # Analyze remaining images with shared ID
        latest_result = first_result
        if len(image_paths) > 1 and shared_inspection_id:
            for path in image_paths[1:]:
                result = self.camera._analyze_image(path, shared_inspection_id)
                if result:  # Update with latest successful result
                    latest_result = result

        # Update camera with the final/latest inspection results
        if latest_result:
            # Clear the 'just started' flag since we now have real results
            self.camera.inspection_just_started = False

            self.camera.last_inspection_results = latest_result
            logger.info(f"🔍 Updated camera with final inspection results for ID: {shared_inspection_id}")
            logger.info(f"🔍 Final inspection result summary: ID={latest_result.get('inspection_id')}, confidence_above_threshold={latest_result.get('confidence_above_threshold')}, AI_threshold={latest_result.get('ai_threshold')}")
            logger.info(f"🔍 Cleared inspection_just_started flag")

            # Update save message to include analysis results
            if latest_result.get('confidence_above_threshold'):
                self.camera.save_message = f"検査完了: 欠点検出 (ID: {shared_inspection_id})"
            else:
                self.camera.save_message = f"検査完了: 欠点なし (ID: {shared_inspection_id})"

        # Start background thread to process presentation images
        if shared_inspection_id:
            # Create a separate thread for presentation processing
            presentation_thread = threading.Thread(
                target=self.camera._process_presentation_images_background,
                args=(shared_inspection_id, image_paths),
                daemon=True
            )
            presentation_thread.start()
            logger.info(f"Started background thread for presentation images")