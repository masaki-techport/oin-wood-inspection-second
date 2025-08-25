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
from sqlalchemy.orm import Session

# Fix imports for sensor modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from __init__ import CONFIG_DIR
from sensor_monitor import SensorMonitor
from sensor_state_machine import SensorStateMachine
from camera_buffer import SensorTriggeredCapture
from camera.webcam_camera import WebcamCamera
from camera.basler import BaslerCamera
from camera.base import AbstractCamera
from app_config import app_config
from camera_manager import camera_manager
from dependencies import get_session
from db.inspection_result import InspectionResult

# Import streaming services
from streaming.sensor_sse import sensor_broadcaster, broadcast_sensor_status, broadcast_sensor_event

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

# Print debug messages only if debug mode is enabled
def debug_print(message: str):
    """Print debug message only if debug mode is enabled"""
    if DEBUG_MODE:
        print(f"[DEBUG] {message}")

def info_print(message: str):
    """Print info message (always shown)"""
    print(f"[SENSOR_INSPECTION] {message}")

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
            sensor_monitor.start_monitoring(sensor_capture.handle_sensor_decision)
            debug_print("Started sensor monitor successfully")
            sensor_capture.start_monitoring()  # Set to inspection mode
            debug_print("Started sensor capture monitoring")
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


@router.get("/sensor-inspection/status")
async def get_sensor_inspection_status():
    """Get current sensor inspection status with real-time state machine updates"""
    global sensor_monitor, sensor_capture
    
    try:
        if not sensor_monitor or not sensor_capture:
            info_print("[STATUS] Sensor inspection not active - no monitor or capture")
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
        info_print(f"[STATUS] Active - Camera: {current_camera_type}, Sensors: A={sensor_status['sensor_a']}, B={sensor_status['sensor_b']}, " 
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
                
        # Use camera status inspection data if available, otherwise try direct camera access
        if not inspection_data and current_camera and hasattr(current_camera, 'last_inspection_results'):
            inspection_data = current_camera.last_inspection_results
            
        # Fetch fresh inspection results from database if we have an inspection_id
        inspection_results = None
        if inspection_data and inspection_data.get('inspection_id'):
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
                debug_print(f"[STATUS] Error fetching fresh inspection results: {e}")
            
        # Debug logging for inspection data
        if inspection_data:
            info_print(f"[STATUS] Including inspection data in response: inspection_id={inspection_data.get('inspection_id')}")
            # Ensure inspection_details is always preserved in the response
            if 'inspection_details' not in inspection_data and hasattr(current_camera, 'last_inspection_results') and current_camera.last_inspection_results:
                if 'inspection_details' in current_camera.last_inspection_results:
                    inspection_data['inspection_details'] = current_camera.last_inspection_results['inspection_details']
                    info_print(f"[STATUS] Preserved inspection_details from previous data")
        else:
            debug_print(f"[STATUS] No inspection data available from camera")
            
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
                "update_age_ms": last_update_diff
            },
            "inspection_data": inspection_data,
            "inspection_results": inspection_results,  # Include fresh inspection results from database
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
        info_print(f"[STATUS] Error getting status: {e}")
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
        config = {
            "dio": {
                "device_name": "DIO001",
                "simulation_mode": SENSOR_SIMULATION_MODE,
                "bit_a": 0,
                "bit_b": 1
            },
            "buffer": {
                "duration_seconds": BUFFER_DURATION_SECONDS,
                "fps": BUFFER_FPS
            },
            "save": {
                "base_directory": "data/images/inspection",
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