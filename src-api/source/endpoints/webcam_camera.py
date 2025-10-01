# source/endpoints/webcam_camera.py
from fastapi import APIRouter
from fastapi.responses import JSONResponse
import base64
import cv2
from camera.webcam_camera import WebcamCamera
import logging

router = APIRouter()
logger = logging.getLogger(__name__)
webcam = WebcamCamera()

@router.post("/webcam/connect")
def connect_webcam():
    """Connect to webcam"""
    success = webcam.connect()
    return {
        "connected": success,
        "message": "Webcam connected successfully" if success else "No webcam detected"
    }

@router.post("/webcam/disconnect")
def disconnect_webcam():
    """Disconnect from webcam"""
    success = webcam.disconnect()
    return {"disconnected": success}

@router.get("/webcam/is_connected")
def check_webcam_connection():
    """Check if webcam is connected"""
    return {"connected": webcam.is_connected()}

@router.post("/webcam/start")
def start_webcam():
    """Start webcam (set to continuous mode)"""
    if not webcam.is_connected():
        return JSONResponse(
            status_code=400,
            content={"error": "Webcam not connected"}
        )
    webcam.set_mode('continuous')
    return {"status": "started"}

@router.post("/webcam/stop")
def stop_webcam():
    """Stop webcam (set to snapshot mode)"""
    if not webcam.is_connected():
        return JSONResponse(
            status_code=200,
            content={"status": "already stopped"}
        )
    webcam.set_mode('snapshot')
    return {"status": "stopped"}

@router.get("/webcam/snapshot")
def get_webcam_snapshot():
    """Get a snapshot from webcam with timeout monitoring"""
    import time
    start_time = time.time()
    
    try:
        logger.info(f"Webcam snapshot request received at {start_time}")
        
        if not webcam.is_connected():
            logger.warning("Webcam not connected, attempting to reconnect")
            # Try to reconnect once with timeout monitoring
            reconnect_start = time.time()
            if webcam.connect():
                reconnect_time = int((time.time() - reconnect_start) * 1000)
                logger.info(f"Webcam reconnection successful in {reconnect_time}ms")
            else:
                total_time = int((time.time() - start_time) * 1000)
                logger.error(f"Webcam reconnection failed, returning empty image (took {total_time}ms)")
                return {
                    "image": "", 
                    "error": "Webcam not connected", 
                    "status": "disconnected",
                    "response_time_ms": total_time
                }

        # Capture frame with timeout monitoring
        frame_start = time.time()
        frame = webcam.get_frame()
        frame_time = int((time.time() - frame_start) * 1000)
        
        if not frame:
            total_time = int((time.time() - start_time) * 1000)
            logger.error(f"Failed to grab image from webcam, frame capture took {frame_time}ms, total {total_time}ms")
            return {
                "image": "", 
                "error": "Failed to grab image", 
                "status": "no_frame",
                "frame_capture_time_ms": frame_time,
                "response_time_ms": total_time
            }

        # Process image
        img = frame["image"]  # Use 'image' key instead of 'img'
        # Convert RGB back to BGR for cv2.imencode (cv2 expects BGR format)
        img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        _, buffer = cv2.imencode(".jpg", img_bgr)
        base64_img = base64.b64encode(buffer).decode("utf-8")
        
        total_time = int((time.time() - start_time) * 1000)
        return {
            "image": base64_img, 
            "status": "ok",
            "frame_capture_time_ms": frame_time,
            "response_time_ms": total_time
        }
    except Exception as e:
        total_time = int((time.time() - start_time) * 1000)
        logger.exception(f"Error in get_webcam_snapshot: {e} (total time: {total_time}ms)")
        # Return empty image instead of error
        return {
            "image": "", 
            "error": str(e), 
            "status": "error",
            "response_time_ms": total_time
        }

@router.post("/webcam/save")
def save_webcam_image():
    """Save current webcam frame"""
    if not webcam.is_connected():
        return JSONResponse(
            status_code=400,
            content={"error": "Webcam not connected"}
        )
    path = webcam.write_frame()
    if path:
        return {"path": path}
    return JSONResponse(
        status_code=500,
        content={"error": "Failed to save webcam image"}
    )

@router.get("/webcam/list_cameras")
def list_available_cameras():
    """List all available camera indices"""
    cameras = webcam.list_available_cameras()
    return {"available_cameras": cameras}

@router.post("/webcam/set_camera_index")
def set_camera_index(camera_index: int):
    """Switch to a different camera index"""
    # Disconnect current camera
    webcam.disconnect()
    
    # Update camera index
    webcam.camera_index = camera_index
    
    # Reconnect with new index
    success = webcam.connect()
    return {
        "success": success,
        "camera_index": camera_index,
        "message": f"Switched to camera {camera_index}" if success else f"Failed to connect to camera {camera_index}"
    } 