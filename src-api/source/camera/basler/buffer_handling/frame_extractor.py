"""
Frame extraction functionality for BaslerCamera buffer.
"""

import time
import logging
import numpy as np

logger = logging.getLogger('BaslerCamera.FrameExtractor')

class FrameExtractor:
    """Handles frame extraction from buffer based on various criteria"""
    
    def __init__(self, camera_instance):
        """Initialize with a reference to the parent camera object"""
        self.camera = camera_instance
    
    def extract_frames_from_buffer(self, filter_start_time=None, filter_end_time=None):
        """Extract frames from buffer based on filter criteria"""
        buffer_snapshot = []
        has_timestamps = False
        
        # First determine if we have frames with timestamps
        for item in list(self.camera.buffer):
            if isinstance(item, dict) and "timestamp" in item:
                has_timestamps = True
                break
        
        # Time-based filtering - only save images from the specific detection sequence
        if has_timestamps:
            filtered_frames = []
            buffer_items = list(self.camera.buffer)
            
            if filter_start_time and filter_end_time:
                logger.info(f"Filtering buffer for images between {filter_start_time} and {filter_end_time}")
                # Filter frames within the time window of the specific pass_L_to_R event
                for item in buffer_items:
                    if (isinstance(item, dict) and "timestamp" in item and 
                        item["timestamp"] >= filter_start_time and 
                        item["timestamp"] <= filter_end_time):
                        filtered_frames.append(item)
                logger.info(f"Filtered buffer from {len(buffer_items)} to {len(filtered_frames)} frames")
                logger.info(f"Sequence duration: {filter_end_time - filter_start_time:.2f}s")
            elif filter_start_time:
                logger.info(f"Filtering buffer for images after {filter_start_time}")
                # Just filter by start time if no end time provided
                for item in buffer_items:
                    if isinstance(item, dict) and "timestamp" in item and item["timestamp"] >= filter_start_time:
                        filtered_frames.append(item)
                logger.info(f"Filtered buffer from {len(buffer_items)} to {len(filtered_frames)} frames")
            else:
                # No filtering needed
                logger.info(f"No time filtering requested")
                for item in buffer_items:
                    if isinstance(item, dict) and "timestamp" in item:
                        filtered_frames.append(item)
            
            # Step 2: Resample frames to ensure exactly 0.1s intervals
            if len(filtered_frames) > 0:
                # Sort frames by timestamp to ensure proper order
                filtered_frames.sort(key=lambda x: x["timestamp"])
                
                # Calculate start and end time
                actual_start_time = filtered_frames[0]["timestamp"]
                actual_end_time = filtered_frames[-1]["timestamp"]
                duration = actual_end_time - actual_start_time
                
                # Calculate ideal number of frames at specified fps
                target_interval = 1.0 / self.camera.buffer_fps
                ideal_frame_count = int(duration / target_interval) + 1
                
                logger.info(f"Sequence duration: {duration:.3f}s")
                logger.info(f"Target interval: {target_interval:.3f}s")
                logger.info(f"Ideal frame count at {self.camera.buffer_fps}fps: {ideal_frame_count}")
                
                # If we have more frames than needed, perform resampling
                if len(filtered_frames) > ideal_frame_count and ideal_frame_count > 0:
                    logger.info(f"Resampling frames to ensure exact {target_interval:.3f}s intervals")
                    
                    # Select frames at exact intervals
                    for i in range(ideal_frame_count):
                        # Calculate target timestamp for this frame
                        target_time = actual_start_time + (i * target_interval)
                        
                        # Find closest frame to this timestamp
                        closest_frame = min(filtered_frames, key=lambda x: abs(x["timestamp"] - target_time))
                        buffer_snapshot.append(closest_frame["image"])
                        
                    logger.info(f"Resampled to {len(buffer_snapshot)} frames at {target_interval:.3f}s intervals")
                else:
                    # Just extract images from filtered frames
                    buffer_snapshot = [item["image"] for item in filtered_frames]
                    logger.info(f"Using all {len(buffer_snapshot)} filtered frames")
            else:
                logger.warning(f"No frames found in filter time range")
        else:
            # Old format buffer without timestamps - estimate filtering
            logger.info(f"Buffer contains old format frames without timestamps, using estimation")
            buffer_items = list(self.camera.buffer)
            if len(buffer_items) > 0 and isinstance(buffer_items[0], np.ndarray):  # Old format - direct images
                # Estimate how many frames to keep based on time since filter_start_time
                if filter_start_time:
                    duration = time.time() - filter_start_time
                    buffer_frames = int(duration * self.camera.buffer_fps)
                    
                    if buffer_frames > 0 and buffer_frames < len(buffer_items):
                        # Take exact number of frames to match specified fps
                        buffer_snapshot = buffer_items[-buffer_frames:]
                        logger.info(f"Estimated {buffer_frames} frames since {filter_start_time}, resampling")
                    else:
                        buffer_snapshot = buffer_items
                        logger.info(f"Using all frames as estimate exceeds buffer size")
                else:
                    buffer_snapshot = buffer_items
                    logger.info(f"No time filter provided, using all frames")
            else:
                logger.info(f"Unknown buffer format, using all frames")
                # Try to extract images from any format
                for item in buffer_items:
                    if isinstance(item, np.ndarray):
                        buffer_snapshot.append(item)
                    elif isinstance(item, dict) and "image" in item and isinstance(item["image"], np.ndarray):
                        buffer_snapshot.append(item["image"])
                
                logger.info(f"Extracted {len(buffer_snapshot)} images from buffer")
                
        # EMERGENCY: If no frames were found in the filtered buffer but we have frames in the original buffer,
        # use all original buffer frames
        if len(buffer_snapshot) == 0 and len(self.camera.buffer) > 0:
            logger.warning("EMERGENCY: No frames in filtered buffer but original buffer has frames")
            buffer_items = list(self.camera.buffer)
            # Try to extract images from any format
            for item in buffer_items:
                if isinstance(item, np.ndarray):
                    buffer_snapshot.append(item)
                elif isinstance(item, dict) and "image" in item and isinstance(item["image"], np.ndarray):
                    buffer_snapshot.append(item["image"])
            logger.info(f"Emergency buffer extraction: {len(buffer_snapshot)} frames")
            
        return buffer_snapshot