"""
Buffer management functionality for BaslerCamera.
"""

import __init__
import os
import time
import logging
import yaml
from datetime import datetime

logger = logging.getLogger('BaslerCamera.BufferManager')

class BufferManager:
    """Manages buffer operations for BaslerCamera"""
    
    def __init__(self, camera_instance):
        """Initialize with a reference to the parent camera object"""
        self.camera = camera_instance
        self.config_path = os.path.join(__init__.CONFIG_DIR, 'params.yaml')
        self.interval_time_ms = self._read_interval_time()
        
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
        logger.info(f"Buffer initialized and cleared - capacity: {self.camera.buffer_size} frames")
        logger.info(f"Fresh recording started - buffer completely cleared for new capture sequence")
        
        # Set recording flag - this is critical for the _grab_loop to start adding frames
        self.camera.is_recording = True
        self.camera.status = "録画中"  # "Recording" in Japanese
        self.camera.save_message = ""
        
        # Grab an initial frame to add to the buffer
        logger.info("Capturing initial frame for buffer")
        try:
            # Capture multiple initial frames to ensure we have something in the buffer
            for i in range(3):  # Try to get 3 initial frames
                frame = self.camera.get_frame()
                if frame and 'image' in frame:
                    current_time = time.time()
                    self.camera.buffer.append({
                        "image": frame['image'].copy(),
                        "timestamp": current_time
                    })
                    logger.info(f"Added initial frame {i+1} to buffer, buffer size now: {len(self.camera.buffer)}")
                else:
                    logger.warning(f"Could not capture initial frame {i+1}")
                time.sleep(0.1)  # Small delay between captures
                
            # Check if we captured any frames
            if len(self.camera.buffer) == 0:
                logger.warning("WARNING: Could not capture any initial frames, buffer remains empty")
        except Exception as e:
            logger.error(f"Error capturing initial frames: {e}")
        
        logger.info("Started recording to buffer")
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
        self.camera.buffer.clear()
        self.camera.save_message = "破棄しました"  # "Discarded" in Japanese
        self.camera.save_path = ""
        logger.info("Discarded buffer images")
        
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