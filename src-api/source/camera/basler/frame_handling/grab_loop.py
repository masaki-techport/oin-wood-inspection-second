"""
Continuous frame grabbing loop implementation for BaslerCamera.
"""

import os
import time
import logging
import numpy as np
from pypylon import pylon

logger = logging.getLogger('BaslerCamera.GrabLoop')

# Performance metrics
PERFORMANCE_METRICS = {
    'frame_grab_time': [],
}

def grab_loop(camera_instance, stop_event, grab_lock, lock, frame_grabber, image_processor):
    """Optimized background thread for continuously grabbing frames"""
    logger.info("Optimized grab loop started")
    last_buffer_report_time = time.time()
    frames_captured = 0
    consecutive_errors = 0
    max_consecutive_errors = 5
    recovery_attempts = 0
    max_recovery_attempts = 3
    
    # Pre-allocate buffers for better memory efficiency
    image_cache = None
    
    # Get interval time from params.yaml for proper timing
    try:
        import yaml
        config_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'config', 'params.yaml')
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            interval_time_ms = config.get('IntervalTime', 1000)  # Default 1000ms
            frame_interval = interval_time_ms / 1000.0  # Convert to seconds
            logger.info(f"Using interval time from params.yaml: {interval_time_ms}ms ({frame_interval:.3f}s)")
    except Exception as e:
        logger.warning(f"Could not read IntervalTime from params.yaml: {e}, using default 1.0s")
        frame_interval = 1.0  # Default 1 second
    
    next_frame_time = time.time()
    
    # Main loop - runs until stop_event is set
    while not stop_event.is_set():
        try:
            current_time = time.time()
            
            # Implement precise timing for consistent frame rate
            if current_time < next_frame_time and camera_instance.mode != "snapshot":
                # Sleep only if we're ahead of schedule
                sleep_time = next_frame_time - current_time
                if sleep_time > 0.001:  # Only sleep for meaningful durations
                    time.sleep(sleep_time)
                continue
            
            # Schedule next frame
            next_frame_time = current_time + frame_interval
            
            # Check if buffer manager is ready for new image (rate limiting with tolerance)
            if hasattr(camera_instance, 'buffer_manager') and hasattr(camera_instance.buffer_manager, '_last_analysis_time'):
                time_since_last = current_time - camera_instance.buffer_manager._last_analysis_time
                interval_seconds = camera_instance.buffer_manager.interval_time_ms / 1000.0
                
                if time_since_last < (interval_seconds - 0.05):  # 50ms tolerance
                    # Skip this frame due to rate limiting
                    logger.debug(f"Grab loop: skipping frame due to rate limiting ({time_since_last:.3f}s < {interval_seconds-0.05:.3f}s)")
                    continue
            
            # Check if camera is grabbing
            if not camera_instance.camera.IsGrabbing():
                logger.info("Camera not grabbing, restarting...")
                try:
                    with grab_lock:
                        camera_instance.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
                    time.sleep(0.1)  # Reduced sleep time
                except Exception as e:
                    logger.error(f"Error starting grabbing: {e}")
                    time.sleep(0.5)  # Reduced sleep time
                    continue
            
            # Try to grab a frame with optimized error handling
            try:
                grab_timeout = 250  # Reduced timeout for better responsiveness (ms)
                start_time = time.time()
                
                # Start timing measurement for frame grab
                timing_collector = getattr(camera_instance, 'timing_collector', None)
                grab_measurement_id = None
                if timing_collector:
                    grab_measurement_id = timing_collector.start_measurement(
                        "frame_grab", 
                        {"timeout_ms": grab_timeout, "frame_index": frames_captured}
                    )
                
                # Use the grab_lock with minimal lock duration
                grab_result = None
                with grab_lock:
                    grab_result = camera_instance.camera.RetrieveResult(grab_timeout, pylon.TimeoutHandling_Return)
                
                # Process outside the lock to minimize lock time
                if grab_result and grab_result.GrabSucceeded():
                    # Reset error counters on success
                    consecutive_errors = 0
                    recovery_attempts = 0
                    
                    # Get timestamp with minimal overhead
                    timestamp = int(time.time() * 1000000)  # Default to system time
                    try:
                        if camera_instance.camera.ChunkModeActive.GetValue():
                            timestamp = grab_result.ChunkTimestamp.GetValue()
                    except:
                        pass  # Keep default timestamp
                    
                    # Convert to RGB image with minimal copying
                    image_rgb = camera_instance.converter.Convert(grab_result).GetArray()
                    
                    # Apply image enhancements only when necessary
                    # This is a performance optimization - we only enhance when needed
                    if camera_instance.mode == "recording":
                        # Apply image enhancements with pre-allocated buffer if possible
                        if image_cache is None or image_cache.shape != image_rgb.shape:
                            image_cache = np.empty_like(image_rgb)
                        
                        # Use optimized image processor
                        image_enhanced = image_processor.enhance_image(image_rgb, alpha=1.1, beta=5)
                    else:
                        # Skip enhancement for better performance in non-recording modes
                        image_enhanced = image_rgb
                    
                    # Store the frame with minimal locking
                    with lock:
                        camera_instance.latest_frame = image_enhanced  # Use direct reference
                        camera_instance.latest_frame_timestamp = timestamp
                    
                    # Add to buffer if in recording mode - optimized buffer operations
                    if camera_instance.is_recording:
                        try:
                            buffer_size_before = len(camera_instance.buffer)
                            current_time = time.time()
                            
                            # Start timing measurement for buffer add
                            buffer_measurement_id = None
                            if timing_collector:
                                buffer_measurement_id = timing_collector.start_measurement(
                                    "buffer_add", 
                                    {"buffer_size_before": buffer_size_before, "frame_index": frames_captured}
                                )
                            
                            # Add to buffer with sequential index for memory analysis
                            buffer_index = len(camera_instance.buffer)
                            buffer_entry = {
                                "image": image_enhanced,  # Direct reference for better performance
                                "timestamp": current_time,
                                "index": buffer_index  # Sequential index for memory analysis
                            }
                            camera_instance.buffer.append(buffer_entry)
                            
                            # Trigger memory analysis if available
                            if hasattr(camera_instance, 'buffer_manager') and hasattr(camera_instance.buffer_manager, '_on_buffer_image_added'):
                                try:
                                    camera_instance.buffer_manager._on_buffer_image_added(
                                        image_enhanced, current_time, buffer_index
                                    )
                                except Exception as analysis_error:
                                    logger.debug(f"Memory analysis not available: {analysis_error}")
                            
                            frames_captured += 1
                            
                            # End timing measurement for buffer add
                            if timing_collector and buffer_measurement_id:
                                timing_collector.end_measurement("buffer_add", buffer_measurement_id)
                            
                            # Reduced logging frequency for better performance
                            now = time.time()
                            if now - last_buffer_report_time >= 10.0 or buffer_size_before == 0:
                                logger.info(f"Buffer: {len(camera_instance.buffer)}/{camera_instance.buffer_size} frames, FPS: {frames_captured/(now-last_buffer_report_time):.1f}")
                                frames_captured = 0
                                last_buffer_report_time = now
                                
                        except Exception as buffer_error:
                            logger.error(f"Error adding to buffer: {buffer_error}")
                    
                    # Release grab result to free resources quickly
                    grab_result.Release()
                    
                    # Track performance metrics
                    grab_time = time.time() - start_time
                    PERFORMANCE_METRICS['frame_grab_time'].append(grab_time)
                    
                    # End timing measurement for frame grab
                    if timing_collector and grab_measurement_id:
                        timing_collector.end_measurement("frame_grab", grab_measurement_id)
                    
                else:
                    # Handle grab failure with minimal overhead
                    error_msg = "Unknown grab error"
                    if grab_result:
                        error_msg = f"Grab failed: {grab_result.GetErrorDescription()}"
                        grab_result.Release()
                    
                    consecutive_errors += 1
                    
                    # Only log every few errors to reduce overhead
                    if consecutive_errors % 5 == 1:
                        logger.warning(f"{error_msg} (errors: {consecutive_errors}/{max_consecutive_errors})")
                    
                    # Adaptive sleep based on error type
                    time.sleep(0.05)
                
            except pylon.TimeoutException:
                # Just a timeout, not an error - very minimal processing
                pass
                
            except Exception as grab_error:
                consecutive_errors += 1
                logger.error(f"Error in grab: {grab_error}")
                time.sleep(0.05)  # Reduced sleep
            
            # Check if we need recovery - optimized recovery logic
            if consecutive_errors >= max_consecutive_errors:
                frame_grabber.handle_grab_recovery(
                    camera_instance.camera, 
                    camera_instance.exposure_time_us,
                    consecutive_errors, 
                    recovery_attempts, 
                    max_recovery_attempts
                )
                consecutive_errors = 0
                recovery_attempts += 1
                if recovery_attempts > max_recovery_attempts:
                    recovery_attempts = 0  # Reset for next time
        
        except Exception as loop_error:
            logger.error(f"Error in grab loop: {loop_error}")
            time.sleep(0.2)  # Reduced sleep time
    
    logger.info("Grab loop stopped")