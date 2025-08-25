"""
Camera Buffer System
Based on OiN_Direction_Acquisition_Shooting's image buffer system

This module provides a continuous image buffering system that:
- Captures images from any camera interface
- Stores them in a circular buffer for a configurable duration
- Saves images when triggered by sensor events
"""

import threading
import time
import datetime
import os
from collections import deque
import cv2
import numpy as np
import json

# Import app config for debug settings
try:
    from app_config import app_config
    DEBUG_MODE = app_config.is_debug_mode()
    DEBUG_CAPTURE_TIME = app_config.debug_capture_time()
except ImportError:
    DEBUG_MODE = False
    DEBUG_CAPTURE_TIME = False

def debug_print(message: str):
    """Print debug message only if debug mode is enabled"""
    if DEBUG_MODE:
        print(f"[DEBUG] {message}")

def info_print(message: str):
    """Print info message (always shown)"""
    print(f"[BUFFER] {message}")


class SensorTriggeredCapture:
    """
    Main camera buffer system that captures images continuously and saves them
    based on sensor triggers
    """
    
    def __init__(self, camera_interface, max_seconds=30, fps=10):
        """
        Initialize the buffer system
        
        Args:
            camera_interface: Camera interface object with get_frame() method
            max_seconds: Maximum seconds to buffer
            fps: Frames per second to capture (default: 10 fps = 0.1 second interval)
        """
        # Debug capture timing records
        self.capture_timing_records = []
        self.current_capture_timing = None
        self.camera = camera_interface
        self.max_seconds = max_seconds
        self.fps = fps
        self.buffer_size = int(max_seconds * fps)
        self.buffer = deque(maxlen=self.buffer_size)
        
        # Threading and state control
        self.is_recording = False
        self.thread = None
        self.lock = threading.Lock()
        
        # Status tracking for frontend
        self.status = "STOPPED"  # STOPPED, MONITORING, RECORDING, SAVING
        self.last_save_message = None
        self.last_save_path = None
        self.processing_active = False
        self.sensors_active = False
        self.processing_start_time = None
        
        # Counters for UI
        self.total_saves = 0
        self.total_discards = 0
        
        # Camera status check
        self.camera_connected = False
        self.camera_type = "unknown"
        
        if self.camera:
            try:
                # Get camera type for better logging
                self.camera_type = self.camera.__class__.__name__
                
                if hasattr(self.camera, 'is_connected') and callable(self.camera.is_connected):
                    self.camera_connected = self.camera.is_connected()
                    if self.camera_connected:
                        info_print(f"{self.camera_type} camera is connected")
                    else:
                        info_print(f"{self.camera_type} camera is not connected")
                else:
                    debug_print(f"{self.camera_type} camera does not have is_connected method")
                    self.camera_connected = False
            except Exception as e:
                info_print(f"Warning: Error checking camera connection: {e}")
                self.camera_connected = False
        else:
            debug_print("No camera interface provided")
            self.camera_connected = False
        
        info_print(f"Initialized with {max_seconds}s buffer at {fps} FPS (buffer size: {self.buffer_size} frames), camera connected: {self.camera_connected}")
        
    def start_monitoring(self):
        """Start monitoring mode - buffer is active but not saving"""
        with self.lock:
            if self.thread is not None and self.thread.is_alive():
                debug_print("Already running")
                return
            
            # Check if camera is valid
            if self.camera is None:
                debug_print("Warning: No camera interface provided, monitoring will start but no frames will be captured")
                self.camera_connected = False
            else:
                # Check camera connection
                try:
                    if hasattr(self.camera, 'is_connected') and callable(self.camera.is_connected):
                        self.camera_connected = self.camera.is_connected()
                        if not self.camera_connected:
                            info_print(f"Warning: {self.camera_type} camera is not connected, monitoring will start but no frames will be captured until camera connects")
                    else:
                        debug_print(f"Warning: {self.camera_type} camera does not have is_connected method")
                        self.camera_connected = False
                except Exception as e:
                    info_print(f"Warning: Error checking camera connection: {e}")
                    self.camera_connected = False
                
                # If it's a BaslerCamera, use its built-in recording mode
                if self.camera_type == "BaslerCamera":
                    debug_print("Using BaslerCamera's built-in recording mode")
                    try:
                        # Configure buffer settings
                        self.camera.max_buffer_seconds = self.max_seconds
                        self.camera.buffer_fps = self.fps
                        self.camera.buffer_size = self.buffer_size
                        
                        # First stop any existing recording
                        if hasattr(self.camera, 'stop_recording'):
                            self.camera.buffer_manager.stop_recording()
                        if hasattr(self.camera, 'stop_grabbing'):
                            self.camera.stop_grabbing()
                            
                        # Start recording mode
                        if hasattr(self.camera, 'set_mode'):
                            self.camera.set_mode("recording")
                        else:
                            # Fallback if set_mode doesn't exist
                            if hasattr(self.camera, 'start_grabbing'):
                                self.camera.start_grabbing()
                            if hasattr(self.camera, 'start_recording'):
                                self.camera.buffer_manager.start_recording()
                        
                        # Verify recording has started by checking the is_recording flag
                        if hasattr(self.camera, 'is_recording'):
                            if not self.camera.is_recording:
                                info_print("Warning: BaslerCamera recording flag is False after start attempt")
                                # Try direct method calls as fallback
                                if hasattr(self.camera, 'start_recording'):
                                    self.camera.buffer_manager.start_recording()
                        
                        # We don't need our own buffer thread for BaslerCamera
                        self.is_recording = True
                        self.status = "MONITORING"
                        info_print("Started monitoring mode using BaslerCamera's built-in recording")
                        return
                    except Exception as e:
                        info_print(f"Failed to use BaslerCamera's built-in recording: {e}, falling back to standard buffer")
            
            # Standard buffer for other camera types
            self.is_recording = True
            self.status = "MONITORING"
            self.thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.thread.start()
            info_print("Started monitoring mode")
            
    def stop_monitoring(self):
        """Stop all monitoring and recording"""
        with self.lock:
            self.is_recording = False
            self.status = "STOPPED"
            
            # If it's a BaslerCamera, stop its recording mode
            if self.camera and self.camera_type == "BaslerCamera":
                try:
                    self.camera.buffer_manager.stop_recording()
                    self.camera.set_mode("snapshot")
                    info_print("Stopped BaslerCamera's built-in recording")
                except Exception as e:
                    debug_print(f"Error stopping BaslerCamera recording: {e}")
            
        if self.thread is not None:
            self.thread.join(timeout=2.0)
            if self.thread.is_alive():
                info_print("Warning: Buffer thread did not terminate cleanly")
            self.thread = None
            
        self.buffer.clear()
        info_print("Stopped monitoring and cleared buffer")
            
    def handle_sensor_decision(self, result, state):
        """
        Handle sensor state machine decisions
        
        Args:
            result: Result from state machine (SAVE, DISCARD, None)
            state: Current state name
        """
        print(f"[CAMERA_BUFFER] 🔍 handle_sensor_decision called: result={result}, state={state}")
        debug_print(f"Sensor decision: result={result}, state={state}")
        
        # Update capture timing debug information if enabled
        if DEBUG_CAPTURE_TIME:
            self._update_capture_timing(result, state)
        
        # Check for processing timeout to auto-reset stuck state
        if (self.processing_active and self.processing_start_time and 
            time.time() - self.processing_start_time > 30.0):
            info_print("[CAMERA_BUFFER] Processing timeout detected, auto-resetting processing state")
            self.processing_active = False
            self.status = "MONITORING"
            self.processing_start_time = None
        
        # Check if we're using BaslerCamera's built-in recording
        using_basler_recording = (self.camera and self.camera_type == "BaslerCamera")
        
        # === RECORDING START CONDITIONS (撮影する) ===
        # According to CSV: When B_ACTIVE state is entered (IDLE->B_ACTIVE) 
        # or when B_THEN_A state is entered (B_ACTIVE->B_THEN_A)
        if state == "B_ACTIVE":
            # Object approaching from left, start recording (撮影する)
            info_print("🔵 RECORDING START: B_ACTIVE state detected, starting camera recording")
            self.sensors_active = True
            self.status = "RECORDING"
            
            # Start fresh BaslerCamera recording for new detection
            if using_basler_recording and hasattr(self.camera, 'is_recording'):
                try:
                    # Stop any existing recording to ensure fresh start
                    if self.camera.is_recording:
                        info_print("🔴 Stopping existing BaslerCamera recording for fresh start")
                        self.camera.buffer_manager.stop_recording()
                    
                    # Start fresh recording
                    info_print("🔴 Starting fresh BaslerCamera recording")
                    self.camera.buffer_manager.start_recording()
                except Exception as e:
                    debug_print(f"Error managing BaslerCamera recording: {e}")
            
        elif state == "B_THEN_A":
            # Object between both sensors, ensure recording is active
            debug_print("B_THEN_A: Object between both sensors, ensuring recording is active")
            self.sensors_active = True
            self.status = "RECORDING"
            
            # Ensure recording is active for BaslerCamera
            if using_basler_recording and hasattr(self.camera, 'is_recording'):
                if not self.camera.is_recording:
                    info_print("Starting BaslerCamera recording (B_THEN_A state)")
                    try:
                        self.camera.buffer_manager.start_recording()
                    except Exception as e:
                        debug_print(f"Error starting BaslerCamera recording: {e}")
        
        # === IMAGE SAVING CONDITIONS (保存する) ===
        # According to CSV: When pass_L_to_R is detected (パターンB)
        elif result == "pass_L_to_R":
            # Check if already processing to prevent overlapping saves
            if self.processing_active:
                info_print(f"[CAMERA_BUFFER] ⚠️ Save already in progress, ignoring pass_L_to_R trigger")
                return
                
            # Save the buffer (保存する)
            info_print(f"[CAMERA_BUFFER] 🔴 SAVE CONDITION TRIGGERED: pass_L_to_R detected!")
            info_print(f"[CAMERA_BUFFER] 🔴 Camera type: {self.camera_type}, Using basler recording: {using_basler_recording}")
            info_print("🔴 SAVE CONDITION: pass_L_to_R detected, saving images")
            self.status = "SAVING"
            self.processing_active = True
            self.processing_start_time = time.time()
            
            # Filter the buffer to only contain frames from the current detection sequence
            # This prevents saving frames from previous discarded sequences
            sequence_start_time = None
            sequence_end_time = None
            if DEBUG_CAPTURE_TIME and self.current_capture_timing:
                sequence_start_time = self.current_capture_timing["start_time"]
                sequence_end_time = time.time()  # Current time is the end of sequence
                info_print(f"[CAMERA_BUFFER] 🔍 Filtering buffer to only include frames from current sequence")
                info_print(f"[CAMERA_BUFFER] 🔍 Sequence start: {sequence_start_time}, end: {sequence_end_time}")
                info_print(f"[CAMERA_BUFFER] 🔍 Sequence duration: {sequence_end_time - sequence_start_time:.2f}s")
            
            if using_basler_recording:
                # Check if buffer has frames before saving
                has_frames = False
                if hasattr(self.camera, 'buffer'):
                    buffer_size = len(self.camera.buffer)
                    info_print(f"BaslerCamera buffer size before saving: {buffer_size}")
                    has_frames = buffer_size > 0
                
                if not has_frames:
                    info_print("WARNING: BaslerCamera buffer is empty, attempting to capture a frame first")
                    try:
                        # Try to get a current frame and add it to buffer
                        frame = self.camera.get_frame()
                        if frame and 'image' in frame:
                            if hasattr(self.camera, 'buffer'):
                                current_time = time.time()
                                self.camera.buffer.append({
                                    "image": frame['image'].copy(),
                                    "timestamp": current_time
                                })
                                info_print("Added current frame to buffer")
                    except Exception as e:
                        debug_print(f"Error capturing frame: {e}")
                
                # Use BaslerCamera's built-in save method
                debug_print("Using BaslerCamera's built-in save_buffer_images method")
                try:
                    # Create timestamp-based directory
                    save_dir = self._create_timestamp_dir()
                    
                    # Get filter start time if available from capture timing
                    filter_start_time = sequence_start_time
                    filter_end_time = sequence_end_time
                    
                    if filter_start_time:
                        info_print(f"[CAMERA_BUFFER] 🔍 Will filter BaslerCamera buffer to images between {filter_start_time} and {filter_end_time}")
                    
                    # Save in a separate thread to avoid blocking
                    info_print(f"[CAMERA_BUFFER] 🔴 Starting save thread for BaslerCamera buffer")
                    save_thread = threading.Thread(
                        target=self._save_basler_buffer,
                        args=(save_dir, filter_start_time, filter_end_time),
                        daemon=True
                    )
                    save_thread.start()
                    info_print(f"[CAMERA_BUFFER] 🔴 Save thread started successfully")
                except Exception as e:
                    info_print(f"Error saving BaslerCamera buffer: {e}")
                    # Reset processing state on error
                    self.processing_active = False
                    self.processing_start_time = None
                    self.status = "MONITORING"
                    # Fall back to standard save
                    self._save_standard_buffer()
            else:
                # Use standard buffer save
                self._save_standard_buffer()
            
            # Increment save counter
            self.total_saves += 1
            
        # === DISCARD CONDITIONS ===
        # According to CSV: When return_from_L, return_from_R, error, timeout_or_manual_reset
        elif result in ["return_from_L", "return_from_R", "error", "timeout_or_manual_reset"]:
            # Discard the buffer
            debug_print(f"DISCARD: Discarding buffer ({result})")
            self.status = "MONITORING"
            self.last_save_message = "画像を破棄しました"
            self.sensors_active = False
            
            if using_basler_recording:
                # Use BaslerCamera's built-in discard method
                try:
                    self.camera.discard_buffer_images()
                except Exception as e:
                    debug_print(f"Error discarding BaslerCamera buffer: {e}")
            
            # Increment discard counter
            self.total_discards += 1
            
        elif state == "IDLE":
            # Return to idle state - stop recording to prevent old images
            self.status = "MONITORING"
            self.sensors_active = False
            
            # Stop BaslerCamera recording when returning to IDLE to prevent buffer accumulation
            if using_basler_recording and hasattr(self.camera, 'is_recording'):
                if self.camera.is_recording:
                    info_print("[CAMERA_BUFFER] 🔴 IDLE state detected - stopping camera recording to prevent old image accumulation")
                    try:
                        self.camera.buffer_manager.stop_recording()
                        info_print("[CAMERA_BUFFER] 🔴 Camera recording stopped successfully")
                    except Exception as e:
                        info_print(f"[CAMERA_BUFFER] Error stopping camera recording: {e}")
            
    def _save_basler_buffer(self, save_dir, filter_start_time=None, filter_end_time=None):
        """
        Save buffer using BaslerCamera's built-in save method
        
        Args:
            save_dir: Directory to save images to
            filter_start_time: Optional timestamp to filter images by (start of sequence)
            filter_end_time: Optional timestamp to filter images by (end of sequence)
        """
        try:
            # Start time for performance measurement
            start_time = time.time()
            
            # Add debug logging
            info_print(f"[CAMERA_BUFFER] Starting to save BaslerCamera buffer to {save_dir}")
            info_print(f"[CAMERA_BUFFER] Camera type: {self.camera_type}, Has buffer attribute: {hasattr(self.camera, 'buffer')}")
            
            # Record buffer size before saving
            basler_buffer_size = 0
            if hasattr(self.camera, 'buffer'):
                basler_buffer_size = len(self.camera.buffer)
                print(f"[CAMERA_BUFFER] Buffer size: {basler_buffer_size}")
                
                # If buffer is empty but we can get a frame, add it to buffer
                if basler_buffer_size == 0:
                    info_print("[CAMERA_BUFFER] Buffer is empty, attempting to capture a frame")
                    frame = self.camera.get_frame()
                    if frame and 'image' in frame:
                        current_time = time.time()
                        self.camera.buffer.append({
                            "image": frame['image'].copy(),
                            "timestamp": current_time
                        })
                        info_print("[CAMERA_BUFFER] Added current frame to buffer")
                        basler_buffer_size = 1
            
            info_print(f"[CAMERA_BUFFER] 🔴 Calling camera.save_buffer_images with output_dir={save_dir}")
            saved_files = self.camera.save_buffer_images(output_dir=save_dir, filter_start_time=filter_start_time, filter_end_time=filter_end_time)
            save_duration = time.time() - start_time
            info_print(f"[CAMERA_BUFFER] 🔴 save_buffer_images returned {len(saved_files)} files")
            self.last_save_path = save_dir
            self.last_save_message = f"保存しました ({len(saved_files)}枚)"
            info_print(f"[CAMERA_BUFFER] Successfully saved {len(saved_files)} images to {save_dir}")
            
            # Add capture timing information if enabled
            if DEBUG_CAPTURE_TIME:
                # Save a summary report for BaslerCamera
                report_file = os.path.join(save_dir, "capture_timing.txt")
                with open(report_file, "w") as f:
                    f.write(f"BASLER CAMERA CAPTURE REPORT\n")
                    f.write(f"=========================\n\n")
                    f.write(f"Timestamp: {datetime.datetime.now().isoformat()}\n")
                    f.write(f"Camera: {self.camera_type}\n")
                    f.write(f"FPS Setting: {self.fps} (interval: {1.0/self.fps:.3f}s)\n")
                    f.write(f"Buffer Size Setting: {self.buffer_size} frames ({self.max_seconds}s)\n")
                    f.write(f"Actual Buffer Size: {basler_buffer_size} frames\n")
                    f.write(f"Saved Files: {len(saved_files)}\n")
                    f.write(f"Save Duration: {save_duration:.3f}s\n")
                    
                    # Calculate effective FPS
                    if len(saved_files) > 0:
                        effective_fps = len(saved_files) / self.max_seconds
                        expected_fps = self.fps
                        effective_interval = 1.0 / effective_fps if effective_fps > 0 else 0
                        expected_interval = 1.0 / expected_fps
                        
                        f.write(f"Expected Frames: {int(self.max_seconds * expected_fps)}\n")
                        f.write(f"Actual Frames: {len(saved_files)}\n")
                        f.write(f"Expected FPS: {expected_fps:.2f} fps\n")
                        f.write(f"Effective FPS: {effective_fps:.2f} fps\n")
                        f.write(f"Expected Interval: {expected_interval:.3f}s\n")
                        f.write(f"Effective Interval: {effective_interval:.3f}s\n")
                        
                        if self.current_capture_timing:
                            # Add interval details from capture timing
                            duration = self.current_capture_timing.get("total_duration_sec", 0)
                            if duration > 0:
                                ideal_frames = int(duration * expected_fps)
                                f.write(f"\nSequence Duration: {duration:.3f}s\n")
                                f.write(f"Ideal Frame Count: {ideal_frames}\n")
                                f.write(f"Resampled to 0.1s intervals: Yes\n")
                                
                                # Add sequence info
                                if filter_start_time and filter_end_time:
                                    f.write(f"Sequence Filter: Only images from current pass_L_to_R sequence\n")
                                    f.write(f"Sequence Start Time: {filter_start_time}\n")
                                    f.write(f"Sequence End Time: {filter_end_time}\n")
                                    f.write(f"Sequence Duration: {filter_end_time - filter_start_time:.2f}s\n")
                    else:
                        f.write(f"Frames Per Second: 0.00 fps\n")
                        f.write(f"Actual Interval: N/A\n")
                        f.write(f"Expected Interval: {1.0/self.fps:.3f}s\n")
                
                info_print(f"[DEBUG_TIMING] Saved BaslerCamera timing report to {report_file}")
                
                # Create a timestamp-based filename report
                frame_timing_file = os.path.join(save_dir, "frame_timing.txt")
                with open(frame_timing_file, "w") as f:
                    f.write(f"FRAME TIMING DETAILS\n")
                    f.write(f"===================\n\n")
                    f.write(f"Frame format: 'frame_NNNN_time_T.Ts_TIMESTAMP.bmp'\n")
                    f.write(f"Where NNNN is the frame number and T.T is time in seconds from start\n\n")
                    
                    f.write(f"{'Frame':>5} | {'Time (s)':>8} | {'Interval (s)':>12}\n")
                    f.write(f"{'-'*5}-+-{'-'*8}-+-{'-'*12}\n")
                    
                    for i in range(len(saved_files)):
                        interval = 1.0 / self.fps
                        frame_time = i * interval
                        prev_time = (i-1) * interval if i > 0 else 0
                        frame_interval = frame_time - prev_time if i > 0 else 0
                        f.write(f"{i:5d} | {frame_time:8.2f} | {frame_interval:12.3f}\n")
                    
                info_print(f"[DEBUG_TIMING] Saved frame timing details to {frame_timing_file}")
            
            self.processing_active = False
            self.processing_start_time = None
            self.status = "MONITORING"
        except Exception as e:
            info_print(f"[CAMERA_BUFFER] Error saving BaslerCamera buffer: {e}")
            import traceback
            traceback.print_exc()
            self.last_save_message = "保存エラー"
            self.processing_active = False
            self.processing_start_time = None
            self.status = "MONITORING"
            
    def _save_standard_buffer(self):
        """Save buffer using standard method"""
        # Create timestamp-based directory
        save_dir = self._create_timestamp_dir()
        
        # Save images in a separate thread to avoid blocking
        save_thread = threading.Thread(
            target=self._save_buffer_images,
            args=(save_dir,),
            daemon=True
        )
        save_thread.start()
        
    def get_status(self):
        """Get current status information for frontend"""
        with self.lock:
            # Check if we're using BaslerCamera's built-in recording
            using_basler_recording = (self.camera and self.camera_type == "BaslerCamera" and 
                                     hasattr(self.camera, 'is_recording'))
            
            # If using BaslerCamera, get buffer size from camera
            buffer_count = 0
            if using_basler_recording and hasattr(self.camera, 'buffer'):
                buffer_count = len(self.camera.buffer)
            else:
                buffer_count = len(self.buffer)
                
            return {
                "status": self.status,
                "camera_connected": self.camera_connected,
                "camera_type": self.camera_type,
                "is_recording": self.is_recording,
                "buffer_count": buffer_count,
                "buffer_size": self.buffer_size,
                "last_save_path": self.last_save_path,
                "last_save_message": self.last_save_message,
                "sensors_active": self.sensors_active,
                "processing_active": self.processing_active,
                "total_saves": self.total_saves,
                "total_discards": self.total_discards
            }
            
    def get_latest_frame(self):
        """Get the latest frame for display"""
        # If using BaslerCamera, use its get_latest_image method
        if self.camera and self.camera_type == "BaslerCamera" and hasattr(self.camera, 'get_latest_image'):
            try:
                latest_image = self.camera.get_latest_image()
                if latest_image is not None:
                    # Convert to base64 for frontend
                    _, buffer = cv2.imencode('.jpg', cv2.cvtColor(latest_image, cv2.COLOR_RGB2BGR))
                    jpg_as_text = "data:image/jpeg;base64," + str(np.base64.b64encode(buffer))[2:-1]
                    return jpg_as_text
            except Exception as e:
                debug_print(f"Error getting latest image from BaslerCamera: {e}")
        
        # Standard method for other camera types
        if not self.buffer:
            return None
            
        try:
            latest_frame = self.buffer[-1]
            # Convert to base64 for frontend
            _, buffer = cv2.imencode('.jpg', latest_frame)
            jpg_as_text = "data:image/jpeg;base64," + str(np.base64.b64encode(buffer))[2:-1]
            return jpg_as_text
        except Exception as e:
            debug_print(f"Error getting latest frame: {e}")
            return None
            
    def cleanup(self):
        """Clean up resources"""
        self.stop_monitoring()
        
    def _capture_loop(self):
        """Background thread that captures frames to buffer"""
        interval = 1.0 / self.fps  # 0.1 seconds at 10 fps
        last_frame_time = 0
        
        debug_print(f"Capture loop started with interval {interval:.3f}s")
        
        while self.is_recording:
            # Throttle capture to match desired FPS
            now = time.time()
            if now - last_frame_time < interval:
                time.sleep(0.01)  # Short sleep to avoid busy waiting
                continue
                
            last_frame_time = now
            
            # Skip if no camera or not connected
            if not self.camera:
                time.sleep(interval)
                continue
                
            # Check connection status periodically
            try:
                if hasattr(self.camera, 'is_connected') and callable(self.camera.is_connected):
                    self.camera_connected = self.camera.is_connected()
            except:
                self.camera_connected = False
                
            if not self.camera_connected:
                time.sleep(interval)
                continue
                
            # Capture frame
            try:
                frame_data = self.camera.get_frame()
                if not frame_data:
                    debug_print("No frame data received")
                    time.sleep(interval)
                    continue
                    
                # Extract image from frame data (support both 'image' and 'img' keys)
                if "image" in frame_data:
                    img = frame_data["image"]
                elif "img" in frame_data:
                    img = frame_data["img"]
                else:
                    debug_print("Frame data doesn't contain image")
                    time.sleep(interval)
                    continue
                    
                # Add to buffer
                self.buffer.append(img)
                
                # If using BaslerCamera, also add to its buffer manually if it exists
                # This is a failsafe in case the built-in recording isn't working
                if self.camera_type == "BaslerCamera" and hasattr(self.camera, 'buffer'):
                    try:
                        if self.sensors_active:  # Only populate buffer when sensors are active
                            self.camera.buffer.append(img.copy())
                    except Exception as e:
                        debug_print(f"Error adding to BaslerCamera buffer: {e}")
                
            except Exception as e:
                debug_print(f"Error capturing frame: {e}")
                time.sleep(interval)
                
        debug_print("Capture loop stopped")
        
    def _create_timestamp_dir(self, base_dir="data/images/inspection"):
        """Create a timestamped directory for saving images"""
        # Use src-api/data/images/inspection as the default path
        default_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "images", "inspection")
        
        # Use app_config save path if available, otherwise use the default src-api path
        try:
            from app_config import app_config
            base_dir = app_config.get('PATHS', 'inspection_images_dir', default_path)
        except:
            base_dir = default_path
        
        print(f"[CAMERA_BUFFER] Using save directory: {base_dir}")
        # Ensure base directory exists
        os.makedirs(base_dir, exist_ok=True)
        
        # Create timestamped subdirectory
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        save_dir = os.path.join(base_dir, timestamp)
        os.makedirs(save_dir, exist_ok=True)
        
        return save_dir
        
    def _save_buffer_images(self, output_dir):
        """Save all buffered images to the specified directory"""
        try:
            buffer_copy = list(self.buffer)  # Make a copy to avoid thread issues
            total_images = len(buffer_copy)
            
            if total_images == 0:
                info_print("No images in buffer to save")
                self.last_save_message = "バッファが空です"
                self.processing_active = False
                self.status = "MONITORING"
                return
                
            info_print(f"Saving {total_images} images to {output_dir}")
            
            # Save each image
            saved_count = 0
            for idx, img in enumerate(buffer_copy):
                try:
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                    filename = f"{output_dir}/frame_{timestamp}_{idx:04d}.jpg"
                    cv2.imwrite(filename, img)
                    saved_count += 1
                except Exception as e:
                    debug_print(f"Error saving image {idx}: {e}")
                    
            self.last_save_path = output_dir
            self.last_save_message = f"保存しました ({saved_count}枚)"
            info_print(f"Saved {saved_count} of {total_images} images to {output_dir}")
            
        except Exception as e:
            info_print(f"Error saving buffer images: {e}")
            self.last_save_message = "保存エラー"
            
        finally:
            self.processing_active = False
            self.status = "MONITORING" 

    def _update_capture_timing(self, result, state):
        """
        Update debug capture timing information based on sensor states
        
        Args:
            result: Result from state machine
            state: Current state name
        """
        # Initialize new capture timing record when B_ACTIVE state is entered (start of recording)
        if state == "B_ACTIVE" and not self.current_capture_timing:
            self.current_capture_timing = {
                "start_time": time.time(),
                "start_timestamp": datetime.datetime.now().isoformat(),
                "sensor_events": [{"time": time.time(), "state": state, "result": result}],
                "buffer_size_start": len(self.buffer),
                "fps_setting": self.fps,
                "interval_setting": 1.0 / self.fps,
            }
            info_print(f"[DEBUG_TIMING] Started capture timing record at {self.current_capture_timing['start_timestamp']}")
        
        # Record sensor state changes
        if self.current_capture_timing:
            # Add sensor event
            self.current_capture_timing["sensor_events"].append({
                "time": time.time(), 
                "state": state, 
                "result": result
            })
            
            # Complete the record when we have a result (save or discard)
            if result in ["pass_L_to_R", "return_from_L", "return_from_R", "error", "timeout_or_manual_reset"]:
                self._complete_capture_timing(result)
                
    def _complete_capture_timing(self, result):
        """
        Complete the current capture timing record and save report if needed
        
        Args:
            result: Final result from state machine
        """
        if not self.current_capture_timing:
            return
            
        # Record final information
        end_time = time.time()
        self.current_capture_timing["end_time"] = end_time
        self.current_capture_timing["end_timestamp"] = datetime.datetime.now().isoformat()
        self.current_capture_timing["total_duration_sec"] = end_time - self.current_capture_timing["start_time"]
        self.current_capture_timing["buffer_size_end"] = len(self.buffer)
        self.current_capture_timing["final_result"] = result
        
        # Calculate time intervals between sensor events
        events = self.current_capture_timing["sensor_events"]
        intervals = []
        for i in range(1, len(events)):
            interval = events[i]["time"] - events[i-1]["time"]
            intervals.append({
                "from_state": events[i-1]["state"],
                "to_state": events[i]["state"],
                "interval_sec": interval,
                "frames_expected": round(interval * self.fps)
            })
        self.current_capture_timing["sensor_intervals"] = intervals
        
        # Calculate frames captured per second
        duration = self.current_capture_timing["total_duration_sec"]
        if duration > 0:
            frames_captured = self.current_capture_timing["buffer_size_end"] - self.current_capture_timing["buffer_size_start"]
            actual_fps = frames_captured / duration
            self.current_capture_timing["frames_captured"] = frames_captured
            self.current_capture_timing["actual_fps"] = actual_fps
            self.current_capture_timing["expected_fps"] = self.fps
            self.current_capture_timing["fps_accuracy"] = (actual_fps / self.fps) * 100 if self.fps > 0 else 0
        
        # Add to records list
        self.capture_timing_records.append(self.current_capture_timing)
        
        # Save report for save events
        if result == "pass_L_to_R":
            self._save_capture_timing_report()
            
        # Reset current record
        self.current_capture_timing = None
        
    def _save_capture_timing_report(self):
        """
        Save capture timing debug report to a file
        """
        if not self.capture_timing_records:
            return
            
        try:
            # Create a report directory
            report_dir = self._create_timestamp_dir("reports")
            report_file = os.path.join(report_dir, "capture_timing_report.json")
            
            # Generate report
            report = {
                "timestamp": datetime.datetime.now().isoformat(),
                "fps_setting": self.fps,
                "interval_setting": 1.0 / self.fps,
                "buffer_size": self.buffer_size,
                "max_seconds": self.max_seconds,
                "camera_type": self.camera_type,
                "records": self.capture_timing_records
            }
            
            # Save report as JSON
            with open(report_file, "w") as f:
                json.dump(report, f, indent=2)
                
            # Also save a summary text file
            summary_file = os.path.join(report_dir, "capture_timing_summary.txt")
            with open(summary_file, "w") as f:
                f.write(f"CAPTURE TIMING REPORT\n")
                f.write(f"===================\n\n")
                f.write(f"Generated: {datetime.datetime.now().isoformat()}\n")
                f.write(f"Camera: {self.camera_type}\n")
                f.write(f"FPS Setting: {self.fps} (interval: {1.0/self.fps:.3f}s)\n")
                f.write(f"Buffer Size: {self.buffer_size} frames ({self.max_seconds}s)\n\n")
                
                for i, record in enumerate(self.capture_timing_records):
                    f.write(f"RECORD #{i+1}\n")
                    f.write(f"  Start: {record.get('start_timestamp', 'N/A')}\n")
                    f.write(f"  End: {record.get('end_timestamp', 'N/A')}\n")
                    f.write(f"  Duration: {record.get('total_duration_sec', 0):.3f}s\n")
                    f.write(f"  Result: {record.get('final_result', 'N/A')}\n")
                    f.write(f"  Frames Captured: {record.get('frames_captured', 0)}\n")
                    f.write(f"  Actual FPS: {record.get('actual_fps', 0):.3f}\n")
                    f.write(f"  FPS Accuracy: {record.get('fps_accuracy', 0):.1f}%\n")
                    
                    f.write(f"  Sensor Events:\n")
                    for event in record.get("sensor_events", []):
                        f.write(f"    - {event.get('state', 'N/A')}: {event.get('result', 'None')}\n")
                    
                    f.write(f"  Sensor Intervals:\n")
                    for interval in record.get("sensor_intervals", []):
                        f.write(f"    - {interval.get('from_state', 'N/A')} → {interval.get('to_state', 'N/A')}: "
                                f"{interval.get('interval_sec', 0):.3f}s "
                                f"(~{interval.get('frames_expected', 0)} frames)\n")
                    f.write("\n")
            
            info_print(f"[DEBUG_TIMING] Saved capture timing report to {report_file}")
            info_print(f"[DEBUG_TIMING] Saved capture timing summary to {summary_file}")
            
        except Exception as e:
            info_print(f"[DEBUG_TIMING] Error saving capture timing report: {e}") 