# source/endpoints/sensor_inspection.py
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
import sys
import os
import time
import yaml
import base64
import cv2
import traceback
import gc
from typing import Optional, Dict, Any
from pydantic import BaseModel
import logging
from sqlalchemy.orm import Session

# Fix imports for sensor modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from __init__ import CONFIG_DIR
from sensor_monitor import SensorMonitor
from sensor_state_machine import SensorStateMachine
from camera_buffer import SensorTriggeredCapture
from camera.webcam_camera import WebcamCamera
from camera.base import AbstractCamera

# Optional import for Basler camera
try:
    from camera.basler import BaslerCamera
    BASLER_AVAILABLE = True
except ImportError:
    print("[WARNING] Basler camera not available in sensor_inspection - pypylon not installed")
    BaslerCamera = None
    BASLER_AVAILABLE = False
from app_config import app_config
from camera_manager import camera_manager
from dependencies import get_session
from db.inspection_result import InspectionResult

# Import streaming services
from streaming.sensor_sse import sensor_broadcaster, broadcast_sensor_status, broadcast_sensor_event
from services import memory_image_cache

router = APIRouter()

# Pydantic models for request bodies
class StartInspectionRequest(BaseModel):
    camera_type: str = "webcam"
    ai_threshold: int = 50  # Default threshold at 50%

# Global instances
sensor_monitor: SensorMonitor = None
sensor_capture: SensorTriggeredCapture = None
current_camera = None
current_camera_type = None  # Track the current camera type

# Configuration from settings.ini
DEBUG_MODE = app_config.is_debug_mode()
SHOW_DEBUG_WINDOWS = app_config.show_debug_windows()
SENSOR_SIMULATION_MODE = app_config.getboolean('SENSOR', 'simulation_mode', False)
BUFFER_DURATION_SECONDS = app_config.getint('SENSOR', 'buffer_duration', 30)
BUFFER_FPS = app_config.getint('SENSOR', 'buffer_fps', 5)

# Status mapping for frontend display
STATUS_MAPPING = {
    "MONITORING": "待機中",
    "RECORDING": "検査中",
    "SAVING": "処理中",
    "STOPPED": "停止"
}

logger = logging.getLogger(__name__)

# Logging helpers honoring DEBUG_MODE
def debug_print(message: str):
    if DEBUG_MODE:
        logger.debug(message)

def info_print(message: str):
    logger.info(message)

def error_print(message: str):
    logger.error(message)

# Try to load configuration from file
CONFIG_FILE = os.path.join(CONFIG_DIR, 'sensor_config.yaml')
try:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = yaml.safe_load(f)
            if config:
                if 'dio' in config and 'simulation_mode' in config['dio']:
                    SENSOR_SIMULATION_MODE = config['dio']['simulation_mode']
                if 'buffer' in config:
                    if 'duration_seconds' in config['buffer']:
                        BUFFER_DURATION_SECONDS = config['buffer']['duration_seconds']
                    if 'fps' in config['buffer']:
                        BUFFER_FPS = config['buffer']['fps']
                info_print(f"Loaded configuration from {CONFIG_FILE}")
except Exception as e:
    info_print(f"Error loading config: {e}")


def _dispatch_frontend_clear_event():
    """Dispatch frontend clear event to trigger UI clearing"""
    try:
        # Import SSE broadcaster to send clear event to frontend
        from streaming.sensor_sse import broadcast_sensor_event
        import asyncio
        
        # Create clear event data
        clear_event_data = {
            "event_type": "inspection_clear",
            "message": "Inspection results cleared for new cycle",
            "timestamp": time.time(),
            "clear_requested": True
        }
        
        # Dispatch the event asynchronously (non-blocking)
        def dispatch_async():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(broadcast_sensor_event("inspection-clear", clear_event_data))
                loop.close()
            except Exception as e:
                debug_print(f"Error dispatching frontend clear event: {e}")
        
        import threading
        clear_thread = threading.Thread(target=dispatch_async, daemon=True)
        clear_thread.start()
        
        info_print("🔵 Dispatched frontend clear event for UI clearing")
        
    except Exception as e:
        debug_print(f"Error dispatching frontend clear event: {e}")


def _clear_ui_immediately():
    """Clear UI components immediately for instant visual feedback - PHASE 1"""
    try:
        start_time = time.time()
        info_print("⚡ IMMEDIATE UI clearing - Phase 1")
        
        # Dispatch frontend clear event first
        _dispatch_frontend_clear_event()
        
        # Clear only the most critical UI components that affect visual display
        cleared_components = []
        
        # 1. Clear camera inspection results (affects UI display)
        if current_camera and hasattr(current_camera, 'last_inspection_results'):
            current_camera.last_inspection_results = None
            cleared_components.append("camera_results")
            
            # Also clear any cached inspection_id references
            if hasattr(current_camera, 'inspection_id'):
                current_camera.inspection_id = None
                cleared_components.append("camera_inspection_id")
        
        # 2. Clear temp sections (affects image display A-E)
        if current_camera and hasattr(current_camera, 'buffer_manager') and current_camera.buffer_manager:
            if hasattr(current_camera.buffer_manager, 'temp_section_assembler') and current_camera.buffer_manager.temp_section_assembler:
                current_camera.buffer_manager.temp_section_assembler.reset()
                cleared_components.append("temp_sections")
                info_print("✅ Cleared temp sections (inspection results from A-E frames)")
        
        # 3. Clear sensor capture data (affects UI state)
        if sensor_capture and hasattr(sensor_capture, 'clear_inspection_results'):
            sensor_capture.clear_inspection_results()
            cleared_components.append("sensor_capture")
        
        # 4. Clear clear_requested flag
        if sensor_monitor and hasattr(sensor_monitor, 'status_tracker'):
            sensor_monitor.status_tracker.clear_requested_flag()
            cleared_components.append("clear_flag")
        
        elapsed_time = (time.time() - start_time) * 1000
        info_print(f"⚡ IMMEDIATE clear completed in {elapsed_time:.1f}ms: {', '.join(cleared_components)}")
        
        return elapsed_time
        
    except Exception as e:
        error_print(f"Error in immediate UI clearing: {e}")
        return 0


def _clear_background_data():
    """Clear background data and caches - PHASE 2 (non-blocking)"""
    try:
        info_print("🔄 Background data clearing - Phase 2")
        start_time = time.time()
        
        # Use threading to clear heavy components in background
        import threading
        import concurrent.futures
        
        def clear_buffer_manager_data():
            """Clear buffer manager data"""
            cleared = []
            if current_camera and hasattr(current_camera, 'buffer_manager') and current_camera.buffer_manager:
                buffer_manager = current_camera.buffer_manager
                
                # Clear results storage
                if hasattr(buffer_manager, 'results_storage') and buffer_manager.results_storage:
                    if hasattr(buffer_manager.results_storage, 'clear_all'):
                        buffer_manager.results_storage.clear_all()
                        cleared.append("results_storage")
                
                # Clear analysis queue
                if hasattr(buffer_manager, 'analysis_queue') and buffer_manager.analysis_queue:
                    if hasattr(buffer_manager.analysis_queue, 'reset'):
                        buffer_manager.analysis_queue.reset()
                        cleared.append("analysis_queue")
                
                # Clear result cache
                if hasattr(buffer_manager, 'result_cache') and buffer_manager.result_cache:
                    if hasattr(buffer_manager.result_cache, 'clear'):
                        buffer_manager.result_cache.clear()
                        cleared.append("result_cache")
                
                # Clear buffer manager inspection results
                if hasattr(buffer_manager, 'last_inspection_results'):
                    buffer_manager.last_inspection_results = None
                    cleared.append("buffer_manager_inspection_results")
            
            return cleared
        
        def clear_memory_cache():
            """Clear memory image cache"""
            try:
                memory_image_cache.clear_all()
                return "memory_image_cache"
            except Exception as cache_err:
                debug_print(f"Failed to clear memory image cache: {cache_err}")
                return None
        
        def clear_camera_cached_data():
            """Clear camera cached data"""
            cleared = []
            if current_camera:
                # Clear cached inspection data
                if hasattr(current_camera, 'cached_inspection_results'):
                    current_camera.cached_inspection_results = None
                if hasattr(current_camera, 'inspection_data'):
                    current_camera.inspection_data = None
                    cleared.append("camera_cached_data")
            return cleared
        
        # Execute background clearing operations in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            # Submit background clearing tasks
            futures = [
                executor.submit(clear_buffer_manager_data),
                executor.submit(clear_memory_cache),
                executor.submit(clear_camera_cached_data)
            ]
            
            # Collect results
            cleared_components = []
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        if isinstance(result, list):
                            cleared_components.extend(result)
                        else:
                            cleared_components.append(result)
                except Exception as e:
                    debug_print(f"Error in background clear operation: {e}")
        
        elapsed_time = (time.time() - start_time) * 1000
        info_print(f"🔄 Background clear completed in {elapsed_time:.1f}ms: {', '.join(cleared_components)}")
        
    except Exception as e:
        error_print(f"Error in background clearing: {e}")


def _clear_all_ui_components():
    """Clear all UI components - IMMEDIATE + BACKGROUND approach"""
    try:
        info_print("🧹 Clearing all UI components for new inspection cycle")
        
        # PHASE 1: Immediate UI clearing (blocking, fast)
        immediate_time = _clear_ui_immediately()
        
        # PHASE 2: Background data clearing (non-blocking)
        import threading
        background_thread = threading.Thread(
            target=_clear_background_data,
            daemon=True
        )
        background_thread.start()
        
        info_print(f"🎉 UI clearing initiated - immediate: {immediate_time:.1f}ms, background: async")
        
    except Exception as e:
        error_print(f"Error clearing UI components: {e}")
        import traceback
        traceback.print_exc()


def cleanup_resources():
    """Clean up all camera and sensor resources"""
    global sensor_monitor, sensor_capture, current_camera, current_camera_type
    
    info_print("Cleaning up all resources...")
    
    # Stop sensor monitoring first
    if sensor_monitor:
        try:
            debug_print("Stopping sensor monitor")
            sensor_monitor.stop_monitoring()
        except Exception as e:
            info_print(f"Error stopping sensor monitor: {e}")
        sensor_monitor = None
    
    # Then stop capture system
    if sensor_capture:
        try:
            debug_print("Cleaning up sensor capture")
            sensor_capture.cleanup()
        except Exception as e:
            info_print(f"Error cleaning up sensor capture: {e}")
        sensor_capture = None
    
    # Release camera from camera manager
    try:
        if current_camera:
            info_print(f"Releasing {current_camera_type} camera")
            camera_manager.release_camera("sensor_inspection")
    except Exception as e:
        info_print(f"Error releasing camera: {e}")
    
    current_camera = None
    # Don't reset current_camera_type here to preserve user selection
    
    # Force garbage collection
    gc.collect()
    time.sleep(1.0)  # Give time for resources to be released
    
    info_print("All resources cleaned up")


@router.post("/sensor-inspection/start")
async def start_sensor_inspection(request: StartInspectionRequest):
    """
    Start sensor-based inspection system
    This replaces the manual 開始 button with automatic sensor triggering
    """
    global sensor_monitor, sensor_capture, current_camera, current_camera_type
    
    # Extract parameters from request
    camera_type = request.camera_type
    ai_threshold = request.ai_threshold
    
    try:
        info_print(f"Starting sensor inspection with camera type: {camera_type}, AI threshold: {ai_threshold}%")
        debug_print(f"Request received with camera_type: {camera_type}")
        
        # Preserve the camera type selection
        current_camera_type = camera_type
        debug_print(f"Set current_camera_type to: {current_camera_type}")
        
        # Clean up all existing resources (except camera type preference)
        cleanup_resources()

        # Clear in-memory presentation previews when starting a new inspection
        try:
            memory_image_cache.clear_all()
            info_print("Cleared in-memory image preview cache for new inspection")
        except Exception as cache_err:
            debug_print(f"Failed to clear memory preview cache: {cache_err}")
            
        # Use the camera manager to get a camera instance
        debug_print(f"Getting camera of type {camera_type} from camera manager")
        try:
            current_camera = camera_manager.get_camera(camera_type, "sensor_inspection")
            camera_created = True
            camera_connected = current_camera.is_connected()
            camera_in_use = False
            
            if camera_connected:
                info_print(f"{camera_type} camera connected successfully via camera manager")
            else:
                debug_print(f"{camera_type} camera connection failed via camera manager")
                
        except Exception as e:
            error_msg = str(e)
            info_print(f"Error getting {camera_type} camera from camera manager: {e}")
            
            # Check for "exclusively opened" error which indicates camera is in use
            if "exclusively opened by another client" in error_msg:
                camera_in_use = True
                info_print("CAMERA IN USE ERROR: The camera is currently being used by another application")
                info_print("Please close any other applications that might be using the camera (like Pylon Viewer)")
            
            if DEBUG_MODE:
                traceback.print_exc()
                
            # Create a dummy camera as fallback
            debug_print("Creating dummy camera as fallback")
            current_camera = AbstractCamera()
            camera_created = False
            camera_connected = False
                
        if not camera_connected:
            info_print(f"Warning: {camera_type} camera connection failed, continuing in simulation-only mode")
        
        # Reset temporary sections for a clean start of new inspection
        try:
            if hasattr(current_camera, 'buffer_manager') and current_camera.buffer_manager and \
               getattr(current_camera.buffer_manager, 'temp_section_assembler', None):
                current_camera.buffer_manager.temp_section_assembler.reset()
                info_print("TempSectionAssembler reset for new inspection start")
        except Exception as reset_err:
            debug_print(f"TempSectionAssembler reset failed: {reset_err}")

        # Initialize sensor-triggered capture system - this should work even with a non-connected camera
        try:
            debug_print(f"Initializing SensorTriggeredCapture with {camera_type} camera")
            
            # For BaslerCamera, configure it directly for sensor-triggered recording
            if camera_type == "basler" and camera_connected:
                # Configure camera for buffer recording
                debug_print("Configuring BaslerCamera for sensor-triggered recording")
                try:
                    # Clear any previous inspection results when starting new session
                    current_camera.last_inspection_results = None
                    debug_print("Cleared previous inspection results from camera")
                    
                    # Also add a flag to mark that we've just started a new inspection
                    current_camera.inspection_just_started = True
                    
                    # Set buffer parameters directly on camera
                    current_camera.max_buffer_seconds = BUFFER_DURATION_SECONDS
                    current_camera.buffer_fps = BUFFER_FPS
                    current_camera.buffer_size = int(BUFFER_DURATION_SECONDS * BUFFER_FPS)
                    
                    # Set AI threshold
                    debug_print(f"Setting AI threshold to {ai_threshold}%")
                    current_camera.set_ai_threshold(ai_threshold)
                    info_print(f"Successfully configured BaslerCamera with AI threshold {ai_threshold}%")
                except Exception as config_error:
                    debug_print(f"Error configuring BaslerCamera: {config_error}")
            elif camera_type == "basler" and not camera_connected:
                # Even if not connected, set the AI threshold for when it does connect
                try:
                    # Clear any previous inspection results when starting new session
                    current_camera.last_inspection_results = None
                    debug_print("Cleared previous inspection results from disconnected camera")
                    
                    debug_print(f"Setting AI threshold to {ai_threshold}% on disconnected BaslerCamera")
                    current_camera.set_ai_threshold(ai_threshold)
                except Exception as config_error:
                    debug_print(f"Error setting AI threshold on disconnected BaslerCamera: {config_error}")
            
            # For other camera types, set AI threshold if method exists
            if camera_type != "basler" and hasattr(current_camera, 'set_ai_threshold'):
                try:
                    # Clear any previous inspection results when starting new session
                    if hasattr(current_camera, 'last_inspection_results'):
                        current_camera.last_inspection_results = None
                        debug_print("Cleared previous inspection results from non-basler camera")
                    
                    debug_print(f"Setting AI threshold to {ai_threshold}% on {camera_type} camera")
                    current_camera.set_ai_threshold(ai_threshold)
                except Exception as config_error:
                    debug_print(f"Error setting AI threshold on {camera_type} camera: {config_error}")
            
            # Create sensor capture system
            debug_print(f"Creating SensorTriggeredCapture with camera_interface: {current_camera is not None}")
            sensor_capture = SensorTriggeredCapture(
                camera_interface=current_camera,
                max_seconds=BUFFER_DURATION_SECONDS,
                fps=BUFFER_FPS
            )
            debug_print("SensorTriggeredCapture created successfully")
            
        except Exception as capture_error:
            info_print(f"Error initializing SensorTriggeredCapture: {capture_error}")
            if DEBUG_MODE:
                traceback.print_exc()
            # Create a minimal capture system that won't crash
            debug_print("Creating minimal capture system")
            sensor_capture = SensorTriggeredCapture(
                camera_interface=None,  # No camera
                max_seconds=5,  # Minimal buffer
                fps=1  # Minimal frame rate
            )
        
        # Initialize sensor monitor - this should always work
        try:
            debug_print(f"Initializing SensorMonitor (simulation_mode={SENSOR_SIMULATION_MODE})")
            # Force simulation mode if camera is not connected
            effective_simulation_mode = SENSOR_SIMULATION_MODE or not camera_connected
            if not camera_connected and not SENSOR_SIMULATION_MODE:
                debug_print("Forcing simulation mode because camera is not connected")
            
            sensor_monitor = SensorMonitor(simulation_mode=effective_simulation_mode)
        except Exception as monitor_error:
            info_print(f"Error initializing SensorMonitor: {monitor_error}")
            if DEBUG_MODE:
                traceback.print_exc()
            # Create a basic monitor in simulation mode
            debug_print("Creating basic monitor in simulation mode")
            sensor_monitor = SensorMonitor(simulation_mode=True)
        
        # Start sensor monitoring with capture callback
        try:
            debug_print(f"Starting sensor monitoring. sensor_capture: {sensor_capture is not None}")
            if sensor_capture is None:
                raise ValueError("sensor_capture is None. Cannot start monitoring.")
            debug_print(f"sensor_capture attributes: {dir(sensor_capture)}")
            
            # Create a combined callback that handles both sensor decisions and camera triggering
            def combined_sensor_callback(result: Optional[str], state: str):
                """Combined callback for sensor decisions and camera triggering"""
                try:
                    # Handle clear results signal for new inspection cycle
                    if result == "CLEAR_RESULTS":
                        # IMMEDIATE UI clearing for instant visual feedback
                        info_print(f"🔵 CLEAR_RESULTS with state={state} - IMMEDIATE UI clearing")
                        immediate_time = _clear_ui_immediately()
                        
                        # Start background clearing in separate thread (non-blocking)
                        import threading
                        background_thread = threading.Thread(
                            target=_clear_background_data,
                            daemon=True
                        )
                        background_thread.start()
                        
                        info_print(f"🔵 CLEAR_RESULTS completed in {immediate_time:.1f}ms - UI cleared immediately")
                        
                        # CRITICAL: Start capture and analysis immediately after UI clearing
                        # Call handle_sensor_decision with None result to trigger recording start
                        info_print(f"🔵 Starting capture and analysis for state={state}")
                        sensor_capture.handle_sensor_decision(None, state)
                        
                        info_print(f"🔵 CLEAR_RESULTS with state={state} - capture and analysis started")
                    else:
                        # Handle normal sensor decision (original logic)
                        info_print(f"🔵 SENSOR CALLBACK: result={result}, state={state}")
                        sensor_capture.handle_sensor_decision(result, state)
                    
                    # If sensor detects PASS_L_TO_R, start camera capturing
                    if result == "pass_L_to_R":
                        info_print("Sensor detected PASS_L_TO_R - starting camera capture")
                        if hasattr(sensor_capture, 'start_sensor_triggered_capture'):
                            sensor_capture.start_sensor_triggered_capture()
                        else:
                            info_print("Warning: sensor_capture does not have start_sensor_triggered_capture method")
                            
                except Exception as e:
                    info_print(f"Error in combined sensor callback: {e}")
                    if DEBUG_MODE:
                        traceback.print_exc()
            
            sensor_monitor.start_monitoring(combined_sensor_callback)
            debug_print("Started sensor monitor successfully")
            sensor_capture.start_monitoring()  # Prepare system but don't start capturing
            debug_print("Prepared sensor capture system - waiting for sensor triggers")
        except Exception as start_error:
            info_print(f"Error starting monitoring: {start_error}")
            if DEBUG_MODE:
                traceback.print_exc()
            # Don't fail here, return partial success
        
        # Determine final status message based on what worked
        status_message = f"Sensor-based inspection started with {camera_type} camera."
        if not camera_connected:
            if camera_in_use:
                status_message += " Camera is in use by another application, running in simulation mode."
            else:
                status_message += " Camera not connected, running in simulation mode only."
        status_message += " Waiting for sensor triggers..."
        
        info_print(status_message)
        
        start_response = {
            "status": "started",
            "camera_type": camera_type,
            "camera_connected": camera_connected,
            "camera_in_use": camera_in_use,
            "simulation_mode": sensor_monitor.simulation_mode if sensor_monitor else True,
            "buffer_duration": BUFFER_DURATION_SECONDS,
            "buffer_fps": BUFFER_FPS,
            "ai_threshold": ai_threshold,
            "message": status_message
        }
        
        # Broadcast start event via SSE (non-blocking)
        try:
            event_data = {
                "event_type": "inspection_started",
                "camera_type": camera_type,
                "camera_connected": camera_connected,
                "simulation_mode": sensor_monitor.simulation_mode if sensor_monitor else True,
                "message": status_message,
                "timestamp": time.time()
            }
            await broadcast_sensor_event("inspection-started", event_data)
        except Exception as sse_error:
            debug_print(f"SSE event broadcast failed: {sse_error}")
        
        return start_response
        
    except Exception as e:
        info_print(f"Failed to start sensor inspection: {e}")
        if DEBUG_MODE:
            traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to start sensor inspection: {str(e)}"}
        )


@router.post("/sensor-inspection/stop")
async def stop_sensor_inspection():
    """Stop sensor-based inspection system"""
    try:
        info_print("Stopping sensor inspection system...")
        cleanup_resources()
        info_print("Sensor inspection system stopped successfully")
        
        stop_response = {
            "status": "stopped",
            "message": "Sensor-based inspection stopped"
        }
        
        # Broadcast stop event via SSE (non-blocking)
        try:
            event_data = {
                "event_type": "inspection_stopped",
                "message": "Sensor-based inspection stopped",
                "timestamp": time.time()
            }
            await broadcast_sensor_event("inspection-stopped", event_data)
        except Exception as sse_error:
            debug_print(f"SSE event broadcast failed: {sse_error}")
        
        return stop_response
        
    except Exception as e:
        info_print(f"Error stopping sensor inspection: {e}")
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to stop sensor inspection: {str(e)}"}
        )


@router.post("/sensor-inspection/clear-flag")
async def clear_sensor_flag():
    """Clear the clear_requested flag after processing"""
    global sensor_monitor
    
    try:
        if sensor_monitor and hasattr(sensor_monitor, 'status_tracker'):
            sensor_monitor.status_tracker.clear_requested_flag()
            return {"status": "success", "message": "Flag cleared"}
        else:
            return {"status": "error", "message": "Sensor monitor not available"}
    except Exception as e:
        debug_print(f"Error clearing flag: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/sensor-inspection/clear-all-ui")
async def clear_all_ui_components():
    """Clear all UI components - IMMEDIATE + BACKGROUND approach"""
    try:
        info_print("🧹 API: Clearing all UI components with immediate + background approach")
        
        # Use the new immediate + background clearing approach
        _clear_all_ui_components()
        
        return {
            "status": "success", 
            "message": "All UI components cleared successfully (immediate + background)",
            "timestamp": time.time()
        }
        
    except Exception as e:
        error_print(f"Error clearing all UI components: {e}")
        return {
            "status": "error", 
            "message": f"Failed to clear UI components: {str(e)}",
            "timestamp": time.time()
        }


@router.post("/sensor-inspection/clear-ui-fast")
async def clear_ui_fast():
    """Fast UI clearing - only clears essential UI data for immediate response"""
    try:
        info_print("⚡ Fast UI clearing - using immediate clearing approach")
        
        # Dispatch frontend clear event first
        _dispatch_frontend_clear_event()
        
        # Use the immediate clearing function for fastest response
        immediate_time = _clear_ui_immediately()
        
        return {
            "status": "success",
            "message": f"Fast UI clearing completed in {immediate_time:.1f}ms",
            "cleared_components": ["camera_results", "temp_sections", "sensor_capture", "clear_flag"],
            "timestamp": time.time()
        }
        
    except Exception as e:
        error_print(f"Error in fast UI clearing: {e}")
        return {
            "status": "error",
            "message": f"Fast UI clearing failed: {str(e)}",
            "timestamp": time.time()
        }


@router.get("/sensor-inspection/status")
async def get_sensor_inspection_status():
    """Get current sensor inspection status with real-time state machine updates"""
    global sensor_monitor, sensor_capture
    
    try:
        if not sensor_monitor or not sensor_capture:
            debug_print("[STATUS] Sensor inspection not active - no monitor or capture")
            inactive_status = {
                "active": False,
                "message": "Sensor inspection not active",
                "timestamp": time.time()
            }
            
            # Broadcast inactive status via SSE (non-blocking)
            try:
                await broadcast_sensor_status(inactive_status)
            except Exception as sse_error:
                debug_print(f"SSE broadcast failed: {sse_error}")
            
            return inactive_status
            
        # Get detailed status including real-time state machine updates
        sensor_status = sensor_monitor.get_detailed_status()
        
        # Get capture status
        capture_status = sensor_capture.get_status()
        
        # Map internal status to UI display status
        ui_status = STATUS_MAPPING.get(capture_status["status"], "待機中")
        
        # Change status based on sensor state
        if sensor_status["sensor_a"] or sensor_status["sensor_b"]:
            # When any sensor is ON, show "処理中" (processing)
            ui_status = "処理中"
        elif sensor_status["current_state"] == "B_ACTIVE":
            # If in B_ACTIVE state but sensors are off, show "検査中"
            ui_status = "検査中"
        
        # Add timestamps for monitoring response times
        current_time = time.time()
        last_update_diff = round((current_time - sensor_status["last_update_time"]) * 1000, 2) if "last_update_time" in sensor_status else None
        debug_print(f"[STATUS] Active - Camera: {current_camera_type}, Sensors: A={sensor_status['sensor_a']}, B={sensor_status['sensor_b']}, " 
              f"State={sensor_status['current_state']}, LastResult={sensor_status['last_result']}, "
              f"Update: {last_update_diff}ms ago")
        
        # Count total saves and discards
        total_saves = getattr(sensor_capture, 'total_saves', 0)
        total_discards = getattr(sensor_capture, 'total_discards', 0)
        
        # Get AI threshold and camera status if available
        ai_threshold = 50  # Default
        camera_status = {}
        inspection_data = None
        
        if current_camera and hasattr(current_camera, 'ai_threshold'):
            ai_threshold = current_camera.ai_threshold
            
        # Get comprehensive camera status if available
        if current_camera and hasattr(current_camera, 'get_status'):
            try:
                camera_status = current_camera.get_status()
                # Extract inspection data if available in camera status
                if 'inspection_data' in camera_status:
                    inspection_data = camera_status['inspection_data']
                # Update AI threshold from camera status if available
                if 'ai_threshold' in camera_status:
                    ai_threshold = camera_status['ai_threshold']
            except Exception as e:
                debug_print(f"Error getting camera status: {e}")
                
        # Check if clearing is requested first
        clear_requested = sensor_status.get("clear_requested", False)
        
        # Use camera status inspection data if available, otherwise try direct camera access
        # BUT only if clearing is not requested
        if not clear_requested:
            if not inspection_data and current_camera and hasattr(current_camera, 'last_inspection_results'):
                inspection_data = current_camera.last_inspection_results
        else:
            # When clearing is requested, ensure inspection_data is None
            inspection_data = None
            debug_print("[STATUS] Clear requested - setting inspection_data to None")
        
        # Fetch fresh inspection results from database ONLY for forward pass results
        # Guard: skip hydration for reverse/returns/timeouts/errors
        inspection_results = None
        last_result = sensor_status.get('last_result')
        is_forward_pass = last_result == 'pass_L_to_R'
        if not clear_requested and is_forward_pass and inspection_data and inspection_data.get('inspection_id'):
            try:
                from db.engine import SessionLocal
                from db.inspection_result import InspectionResult
                
                with SessionLocal() as db_session:
                    inspection_result = db_session.query(InspectionResult).filter(
                        InspectionResult.inspection_id == inspection_data['inspection_id']
                    ).first()
                    
                    if inspection_result:
                        inspection_results = {
                            "inspection_id": inspection_result.inspection_id,
                            "discoloration": inspection_result.discoloration,
                            "hole": inspection_result.hole,
                            "knot": inspection_result.knot,
                            "dead_knot": inspection_result.dead_knot,
                            "live_knot": inspection_result.live_knot,
                            "tight_knot": inspection_result.tight_knot,
                            "length": inspection_result.length
                        }
                        debug_print(f"[STATUS] Fetched fresh inspection results from database for ID {inspection_data['inspection_id']}")
                    else:
                        debug_print(f"[STATUS] No inspection results found in database for ID {inspection_data['inspection_id']}")
            except Exception as e:
                error_print(f"[STATUS] Error fetching fresh inspection results: {e}")
        elif clear_requested:
            debug_print("[STATUS] Clear requested - skipping database fetch for inspection results")
        elif not is_forward_pass:
            debug_print(f"[STATUS] Non-forward result '{last_result}' - skipping database fetch for inspection results")
            
        # Debug logging for inspection data
        if inspection_data:
            debug_print(f"[STATUS] Including inspection data in response: inspection_id={inspection_data.get('inspection_id')}")
            # Do NOT preserve previous inspection_details when a clear has been requested
            if not sensor_status.get("clear_requested", False):
                if 'inspection_details' not in inspection_data and hasattr(current_camera, 'last_inspection_results') and current_camera.last_inspection_results:
                    if 'inspection_details' in current_camera.last_inspection_results:
                        inspection_data['inspection_details'] = current_camera.last_inspection_results['inspection_details']
                        debug_print(f"[STATUS] Preserved inspection_details from previous data")
        else:
            debug_print(f"[STATUS] No inspection data available from camera")
            
        # Check if clearing is requested - if so, don't include inspection data
        clear_requested = sensor_status.get("clear_requested", False)
        
        # When clearing or non-forward result, ensure data is null to keep UI clear
        if clear_requested or not is_forward_pass:
            inspection_data = None
            inspection_results = None
            if clear_requested:
                debug_print("[STATUS] Clear requested - setting all inspection data to null")
            else:
                debug_print(f"[STATUS] Non-forward result '{last_result}' - clearing inspection data/results for UI")
        
        status_response = {
            "active": True,
            "camera_type": current_camera_type,  # Add camera type to status response
            "ai_threshold": ai_threshold,  # Include AI threshold in status
            "sensors": {
                "sensor_a": sensor_status["sensor_a"],
                "sensor_b": sensor_status["sensor_b"],
                "current_state": sensor_status["current_state"],
                "last_result": sensor_status["last_result"],
                "last_update_time": sensor_status["last_update_time"],
                "update_age_ms": last_update_diff,
                "clear_requested": clear_requested
            },
            "inspection_data": inspection_data,  # Will be None if clear_requested
            "inspection_results": inspection_results,  # Will be None if clear_requested
            "camera_status": camera_status,  # Include full camera status for debugging
            "capture": {
                "status": ui_status,  # Use mapped status for UI
                "last_save_message": capture_status["last_save_message"],
                "processing_active": capture_status.get("processing_active", False),
                "sensors_active": capture_status.get("sensors_active", False),
                "sensor_a": sensor_status["sensor_a"],  # Add sensor states directly to capture status
                "sensor_b": sensor_status["sensor_b"],  # for easier frontend access
                "total_saves": total_saves,
                "total_discards": total_discards,
                "buffer_status": {
                    "is_recording": camera_status.get("recording", False),
                    "buffer_size": camera_status.get("buffer_size", 0),
                    "max_buffer_size": camera_status.get("max_buffer_size", BUFFER_DURATION_SECONDS * BUFFER_FPS)
                }
            },
            "simulation_mode": sensor_status["simulation_mode"],
            "timestamp": current_time
        }
        
        # Broadcast status update via SSE (non-blocking)
        try:
            await broadcast_sensor_status(status_response)
        except Exception as sse_error:
            # Don't fail the main request if SSE broadcast fails
            debug_print(f"SSE broadcast failed: {sse_error}")
        
        return status_response
        
    except Exception as e:
        error_print(f"[STATUS] Error getting status: {e}")
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to get status: {str(e)}"}
        )


@router.post("/sensor-inspection/trigger-test")
async def trigger_test_sequence():
    """
    Trigger a test sensor sequence (simulation mode only)
    This simulates a left-to-right object pass that should trigger image capture
    """
    global sensor_monitor
    
    if not sensor_monitor:
        return JSONResponse(
            status_code=400,
            content={"error": "Sensor inspection not active"}
        )
        
    if not sensor_monitor.simulation_mode:
        return JSONResponse(
            status_code=400,
            content={"error": "Test sequences only available in simulation mode"}
        )
        
    try:
        sensor_monitor.trigger_test_sequence()
        
        test_response = {
            "status": "triggered",
            "message": "Test sequence triggered - simulating left-to-right object pass"
        }
        
        # Broadcast test event via SSE (non-blocking)
        try:
            event_data = {
                "event_type": "test_triggered",
                "message": "Test sequence triggered - simulating left-to-right object pass",
                "timestamp": time.time()
            }
            await broadcast_sensor_event("test-triggered", event_data)
        except Exception as sse_error:
            debug_print(f"SSE event broadcast failed: {sse_error}")
        
        return test_response
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to trigger test: {str(e)}"}
        )


@router.post("/sensor-inspection/toggle-sensor-a")
def toggle_sensor_a():
    """Toggle sensor A state manually (simulation mode only)"""
    global sensor_monitor
    
    if not sensor_monitor:
        info_print("[TOGGLE_A] Sensor inspection not active")
        return JSONResponse(
            status_code=400,
            content={"error": "Sensor inspection not active"}
        )
        
    if not sensor_monitor.simulation_mode:
        info_print("[TOGGLE_A] Not in simulation mode")
        return JSONResponse(
            status_code=400,
            content={"error": "Manual control only available in simulation mode"}
        )
        
    try:
        info_print("[TOGGLE_A] Toggling sensor A...")
        new_state = sensor_monitor.toggle_sensor_a()
        info_print(f"[TOGGLE_A] Sensor A toggled to: {new_state}")
        
        return {
            "status": "toggled",
            "sensor_a": new_state,
            "message": f"Sensor A toggled to {'ON' if new_state else 'OFF'}"
        }
        
    except Exception as e:
        info_print(f"[TOGGLE_A] Error: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to toggle sensor A: {str(e)}"}
        )


@router.post("/sensor-inspection/toggle-sensor-b")
def toggle_sensor_b():
    """Toggle sensor B state manually (simulation mode only)"""
    global sensor_monitor
    
    if not sensor_monitor:
        info_print("[TOGGLE_B] Sensor inspection not active")
        return JSONResponse(
            status_code=400,
            content={"error": "Sensor inspection not active"}
        )
        
    if not sensor_monitor.simulation_mode:
        info_print("[TOGGLE_B] Not in simulation mode")
        return JSONResponse(
            status_code=400,
            content={"error": "Manual control only available in simulation mode"}
        )
        
    try:
        info_print("[TOGGLE_B] Toggling sensor B...")
        new_state = sensor_monitor.toggle_sensor_b()
        info_print(f"[TOGGLE_B] Sensor B toggled to: {new_state}")
        
        return {
            "status": "toggled",
            "sensor_b": new_state,
            "message": f"Sensor B toggled to {'ON' if new_state else 'OFF'}"
        }
        
    except Exception as e:
        info_print(f"[TOGGLE_B] Error: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to toggle sensor B: {str(e)}"}
        )


@router.get("/sensor-inspection/configuration")
def get_sensor_configuration():
    """Get current sensor configuration"""
    return {
        "simulation_mode": SENSOR_SIMULATION_MODE,
        "buffer_duration": BUFFER_DURATION_SECONDS,
        "buffer_fps": BUFFER_FPS,
        "debug_mode": DEBUG_MODE,
        "show_debug_windows": SHOW_DEBUG_WINDOWS
    }


@router.post("/sensor-inspection/configuration")
def update_sensor_configuration(
    simulation_mode: bool = None,
    buffer_duration: int = None,
    buffer_fps: int = None
):
    """Update sensor configuration"""
    global SENSOR_SIMULATION_MODE, BUFFER_DURATION_SECONDS, BUFFER_FPS
    
    if simulation_mode is not None:
        SENSOR_SIMULATION_MODE = simulation_mode
        
    if buffer_duration is not None:
        BUFFER_DURATION_SECONDS = max(5, min(300, buffer_duration))  # Limit between 5s and 5min
        
    if buffer_fps is not None:
        BUFFER_FPS = max(1, min(30, buffer_fps))  # Limit between 1 and 30 fps
        
    # Save configuration to file
    try:
        # Resolve base directory to absolute path under src-api/data/images/inspection
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        abs_inspection_dir = os.path.join(root_dir, "data", "images", "inspection")
        config = {
            "dio": {
                "device_name": "DIO000",
                "simulation_mode": SENSOR_SIMULATION_MODE,
                "bit_a": 0,
                "bit_b": 1
            },
            "buffer": {
                "duration_seconds": BUFFER_DURATION_SECONDS,
                "fps": BUFFER_FPS
            },
            "save": {
                "base_directory": abs_inspection_dir,
                "format": "jpg",
                "quality": 95
            }
        }
        
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
            
        info_print(f"Configuration saved to {CONFIG_FILE}")
    except Exception as e:
        info_print(f"Error saving configuration: {e}")
    
    return {
        "simulation_mode": SENSOR_SIMULATION_MODE,
        "buffer_duration": BUFFER_DURATION_SECONDS,
        "buffer_fps": BUFFER_FPS,
        "message": "Configuration updated"
    }


@router.post("/sensor-inspection/set-ai-threshold")
def set_ai_threshold(ai_threshold: int):
    """
    Update the AI threshold for the current camera
    
    Args:
        ai_threshold: New AI threshold (10-100)
    """
    global current_camera
    
    if not current_camera:
        return JSONResponse(
            status_code=400,
            content={"error": "No active camera"}
        )
    
    # Validate threshold range
    if ai_threshold < 10 or ai_threshold > 100:
        return JSONResponse(
            status_code=400,
            content={"error": "AI threshold must be between 10 and 100"}
        )
    
    try:
        # Update camera AI threshold
        if hasattr(current_camera, 'set_ai_threshold'):
            current_camera.set_ai_threshold(ai_threshold)
            info_print(f"Updated AI threshold to {ai_threshold}%")
            
            return {
                "status": "success",
                "ai_threshold": ai_threshold,
                "message": f"AI threshold updated to {ai_threshold}%"
            }
        else:
            return JSONResponse(
                status_code=400,
                content={"error": "Camera does not support AI threshold setting"}
            )
            
    except Exception as e:
        info_print(f"Error setting AI threshold: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to set AI threshold: {str(e)}"}
        )


@router.get("/sensor-inspection/inspection-result/{inspection_id}")
def get_inspection_result(inspection_id: int, session: Session = Depends(get_session)):
    """
    Fetch detailed inspection results for a specific inspection ID
    Returns defect classification data from t_inspection_result table
    """
    try:
        info_print(f"[INSPECTION_RESULT] Fetching results for inspection_id: {inspection_id}")
        
        # Query the inspection result from database
        inspection_result = session.query(InspectionResult).filter(
            InspectionResult.inspection_id == inspection_id
        ).first()
        
        if not inspection_result:
            info_print(f"[INSPECTION_RESULT] No results found for inspection_id: {inspection_id}")
            return JSONResponse(
                status_code=404,
                content={
                    "status": "error",
                    "error": f"Inspection result not found for ID: {inspection_id}",
                    "code": "INSPECTION_RESULT_NOT_FOUND"
                }
            )
        
        # Build response data
        result_data = {
            "inspection_id": inspection_result.inspection_id,
            "discoloration": inspection_result.discoloration,
            "hole": inspection_result.hole,
            "knot": inspection_result.knot,
            "dead_knot": inspection_result.dead_knot,
            "live_knot": inspection_result.live_knot,
            "tight_knot": inspection_result.tight_knot,
            "length": inspection_result.length
        }
        
        info_print(f"[INSPECTION_RESULT] Successfully retrieved results for inspection_id: {inspection_id}")
        debug_print(f"[INSPECTION_RESULT] Result data: {result_data}")
        
        return {
            "status": "success",
            "data": result_data
        }
        
    except Exception as e:
        error_msg = f"Failed to fetch inspection result for ID {inspection_id}: {str(e)}"
        info_print(f"[INSPECTION_RESULT] Error: {error_msg}")
        if DEBUG_MODE:
            traceback.print_exc()
        
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": error_msg,
                "code": "DATABASE_ERROR"
            }
        )


@router.get("/sensor-inspection/debug-camera-status")
def debug_camera_status():
    """Debug endpoint to check camera inspection results"""
    global current_camera
    
    if not current_camera:
        return {"error": "No active camera"}
    
    debug_info = {
        "camera_type": current_camera.__class__.__name__,
        "has_last_inspection_results": hasattr(current_camera, 'last_inspection_results'),
        "last_inspection_results": getattr(current_camera, 'last_inspection_results', None),
        "has_get_status": hasattr(current_camera, 'get_status'),
        "camera_status": None
    }
    
    # Try to get camera status
    try:
        if hasattr(current_camera, 'get_status'):
            debug_info["camera_status"] = current_camera.get_status()
    except Exception as e:
        debug_info["camera_status_error"] = str(e)
    
    return debug_info


@router.get("/sensor-inspection/debug-presentation-images/{inspection_id}")
def debug_presentation_images(inspection_id: int):
    """Debug endpoint to check presentation images for a specific inspection"""
    try:
        from db.inspection_presentation import InspectionPresentation
        from db.engine import SessionLocal
        
        debug_info = {
            "inspection_id": inspection_id,
            "presentation_images": [],
            "total_count": 0,
            "file_existence": {}
        }
        
        # Query presentation images
        with SessionLocal() as session:
            presentations = session.query(InspectionPresentation).filter(
                InspectionPresentation.inspection_id == inspection_id
            ).order_by(InspectionPresentation.group_name).all()
            
            debug_info["total_count"] = len(presentations)
            
            for p in presentations:
                image_info = {
                    "group_name": p.group_name,
                    "image_path": p.image_path,
                    "file_exists": os.path.exists(p.image_path) if p.image_path else False
                }
                debug_info["presentation_images"].append(image_info)
                debug_info["file_existence"][p.group_name] = image_info["file_exists"]
        
        return debug_info
        
    except Exception as e:
        return {"error": f"Failed to debug presentation images: {str(e)}"}


@router.post("/sensor-inspection/trigger-fake-inspection")
def trigger_fake_inspection():
    """Debug endpoint to create a fake inspection with presentation images"""
    global current_camera
    
    if not current_camera:
        return {"error": "No active camera"}
    
    try:
        # Create some fake presentation data
        fake_inspection_data = {
            "inspection_id": 999,
            "confidence_above_threshold": True,
            "ai_threshold": 50,
            "inspection_details": [
                {
                    "id": 1,
                    "error_type": 1,  # hole
                    "error_type_name": "穴",
                    "x_position": 100,
                    "y_position": 200,
                    "width": 50,
                    "height": 30,
                    "length": 5.0,
                    "confidence": 0.85,
                    "image_path": "fake_image.jpg"
                }
            ]
        }
        
        # Update camera with fake data
        current_camera.last_inspection_results = fake_inspection_data
        
        info_print(f"Created fake inspection data: {fake_inspection_data}")
        
        return {
            "status": "success",
            "message": "Fake inspection data created",
            "inspection_data": fake_inspection_data
        }
        
    except Exception as e:
        return {"error": f"Failed to create fake inspection: {str(e)}"}


@router.get("/sensor-inspection/latest-frame")
def get_latest_frame():
    """Get the latest frame from the buffer (for preview)"""
    global sensor_capture, current_camera_type
    
    if not sensor_capture:
        return {
            "image": "",
            "timestamp": time.time(),
            "status": "no_capture_system"
        }
        
    try:
        frame = sensor_capture.get_latest_frame()
        if frame is None:
            return {
                "image": "",
                "timestamp": time.time(),
                "status": "no_frame"
            }
            
        # Note: We no longer need to convert BGR to RGB here since the camera classes
        # now handle this internally and always return RGB format
        
        # Convert RGB to BGR for OpenCV JPEG encoding (cv2.imencode expects BGR)
        if current_camera_type == "basler" or current_camera_type == "basler_legacy":
            # Basler cameras now return RGB, so convert to BGR for JPEG encoding
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            _, buffer = cv2.imencode('.jpg', frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 80])
        else:
            # Webcam cameras return RGB, so convert to BGR for JPEG encoding
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            _, buffer = cv2.imencode('.jpg', frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 80])
        
        jpg_as_text = base64.b64encode(buffer).decode('utf-8')
        
        return {
            "image": f"data:image/jpeg;base64,{jpg_as_text}",
            "timestamp": time.time(),
            "status": "ok",
            "camera_type": current_camera_type  # Include camera type for debugging
        }
        
    except Exception as e:
        info_print(f"[SENSOR_INSPECTION] Failed to get latest frame: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "image": "",
            "timestamp": time.time(),
            "status": "error",
            "error": str(e)
        } 