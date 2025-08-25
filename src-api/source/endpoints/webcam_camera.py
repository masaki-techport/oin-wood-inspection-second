# source/endpoints/webcam_camera.py
from fastapi import APIRouter
from fastapi.responses import JSONResponse
import base64
import cv2
from camera.webcam_camera import WebcamCamera

router = APIRouter()
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
    """Get a snapshot from webcam"""
    try:
        if not webcam.is_connected():
            print("[WEBCAM] Webcam not connected, attempting to reconnect")
            # Try to reconnect once
            if webcam.connect():
                print("[WEBCAM] Reconnection successful")
            else:
                print("[WEBCAM] Reconnection failed, returning empty image")
                # Return empty image instead of error
                return {"image": "", "error": "Webcam not connected", "status": "disconnected"}

        frame = webcam.get_frame()
        if not frame:
            print("[WEBCAM] Failed to grab image from webcam, returning empty image")
            # Return empty image instead of error
            return {"image": "", "error": "Failed to grab image", "status": "no_frame"}

        img = frame["image"]  # Use 'image' key instead of 'img'
        # Convert RGB back to BGR for cv2.imencode (cv2 expects BGR format)
        img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        _, buffer = cv2.imencode(".jpg", img_bgr)
        base64_img = base64.b64encode(buffer).decode("utf-8")
        return {"image": base64_img, "status": "ok"}
    except Exception as e:
        print(f"[WEBCAM] Error in get_webcam_snapshot: {e}")
        import traceback
        traceback.print_exc()
        # Return empty image instead of error
        return {"image": "", "error": str(e), "status": "error"}

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