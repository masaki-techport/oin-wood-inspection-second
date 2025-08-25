# source/endpoints/camera.py
from fastapi import APIRouter
from fastapi.responses import JSONResponse
import base64
import cv2
from camera.basler import BaslerCamera
from camera_manager import camera_manager

router = APIRouter()
# Use camera manager instead of direct instantiation
camera_id = "camera_endpoint"

@router.post("/camera/connect")
def connect_camera():
    # Get camera from manager
    camera = camera_manager.get_camera("basler", camera_id)
    success = camera.is_connected()
    return {
        "connected": success,
        "message": "Camera connected successfully" if success else "No camera detected - running in development mode"
    }

@router.post("/camera/disconnect")
def disconnect_camera():
    # Release camera from manager
    camera_manager.release_camera(camera_id)
    return {"disconnected": True}

@router.get("/camera/is_connected")
def check_camera_connection():
    status = camera_manager.get_status()
    is_connected = status["is_connected"] and status["active_camera_type"] == "basler"
    return {"connected": is_connected}

@router.post("/camera/start")
def start_camera():
    status = camera_manager.get_status()
    if not status["is_connected"] or status["active_camera_type"] != "basler":
        # Try to get a camera
        camera = camera_manager.get_camera("basler", camera_id)
        if camera:
            if not camera.is_connected():
                return JSONResponse(
                    status_code=400,
                    content={"error": "Camera not connected"}
                )
                # Get camera and set mode
            camera = camera_manager.get_camera("basler", camera_id)
            camera.set_mode('continuous')
            return {"status": "started"}
        else:
            return JSONResponse(
                status_code=400,
                content={"error": "Camera not found"}
            )  

@router.post("/camera/stop")
def stop_camera():
    status = camera_manager.get_status()
    if not status["is_connected"] or status["active_camera_type"] != "basler":
        return JSONResponse(
            status_code=200,
            content={"status": "already stopped"}
        )
    
    # Get camera and set mode
    camera = camera_manager.get_camera("basler", camera_id)
    camera.set_mode('snapshot')
    return {"status": "stopped"}

@router.get("/camera/snapshot")
def get_snapshot():
    try:
        #Get camera from manager
        camera = camera_manager.get_camera("basler", camera_id)
            
        if not camera.is_connected():
                print("[BASLER] Camera not connected, returning empty image")
                # Return empty image instead of error
                return {"image": "", "error": "Camera not connected", "status": "disconnected"}

        frame = camera.get_frame()
        if not frame:
                print("[BASLER] Failed to grab image, returning empty image")
                # Return empty image instead of error
                return {"image": "", "error": "Failed to grab image", "status": "no_frame"}
                
        # Check if this is a fallback image
        if "is_fallback" in frame and frame["is_fallback"]:
                print("[BASLER] Using fallback image due to camera issues")
                # We still have an image to display, so continue processing

        # Get image from frame data (should always be "image" key in consolidated implementation)
        if "image" in frame:
            img = frame["image"]
        else:
            print("[BASLER] Frame data doesn't contain image data")
            return {"image": "", "error": "Invalid frame format", "status": "invalid_format"}
            
        # Convert RGB to BGR for OpenCV JPEG encoding (cv2.imencode expects BGR)
        img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        _, buffer = cv2.imencode(".jpg", img_bgr)
        base64_img = base64.b64encode(buffer).decode("utf-8")
        return {"image": base64_img, "status": "ok"}
    except Exception as e:
        print(f"[BASLER] Error in get_snapshot: {e}")
        import traceback
        traceback.print_exc()
        # Return empty image instead of error
        return {"image": "", "error": str(e), "status": "error"}

@router.post("/camera/save")
def save_image():
    # Get camera from manager
    camera = camera_manager.get_camera("basler", camera_id)

    if not camera.is_connected():
        return JSONResponse(
            status_code=400,
            content={"error": "Camera not connected"}
        )
    path = camera.write_frame()
    if path:
        return {"path": path}
    return JSONResponse(
        status_code=500,
        content={"error": "Failed to save image"}
    )

@router.get("/camera/parallel_status")
def get_parallel_processing_status():
    """Get real-time parallel processing status."""
    try:
        camera = camera_manager.get_camera("basler", camera_id)

        if not camera or not hasattr(camera, 'parallel_processor'):
            return {
                "parallel_processing_available": False,
                "message": "Parallel processing not available"
            }

        parallel_processor = camera.parallel_processor
        if not parallel_processor:
            return {
                "parallel_processing_available": False,
                "message": "Parallel processor not initialized"
            }

        # Get comprehensive status
        performance_metrics = parallel_processor.get_performance_metrics()

        # Get real-time results if available
        real_time_status = {}
        if hasattr(parallel_processor, 'results_manager'):
            real_time_status = parallel_processor.results_manager.get_real_time_status()

        return {
            "parallel_processing_available": True,
            "enabled": parallel_processor.enabled,
            "thread_count": parallel_processor.thread_count,
            "real_time_status": real_time_status,
            "performance_metrics": performance_metrics,
            "last_inspection_results": camera.last_inspection_results
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to get parallel processing status: {str(e)}"}
        )

@router.get("/camera/group_status/{group_name}")
def get_group_processing_status(group_name: str):
    """Get processing status for a specific group (A-E)."""
    try:
        camera = camera_manager.get_camera("basler", camera_id)

        if not camera or not hasattr(camera, 'parallel_processor'):
            return JSONResponse(
                status_code=404,
                content={"error": "Parallel processing not available"}
            )

        parallel_processor = camera.parallel_processor
        if not parallel_processor or not hasattr(parallel_processor, 'results_manager'):
            return JSONResponse(
                status_code=404,
                content={"error": "Results manager not available"}
            )

        group_status = parallel_processor.results_manager.get_group_status(group_name)

        if group_status is None:
            return JSONResponse(
                status_code=404,
                content={"error": f"Group {group_name} not found"}
            )

        return {
            "group_name": group_name,
            "status": group_status
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to get group status: {str(e)}"}
        )

@router.get("/camera/performance_report")
def get_performance_report():
    """Get comprehensive performance report for parallel processing."""
    try:
        camera = camera_manager.get_camera("basler", camera_id)

        if not camera or not hasattr(camera, 'parallel_processor'):
            return JSONResponse(
                status_code=404,
                content={"error": "Parallel processing not available"}
            )

        parallel_processor = camera.parallel_processor
        if not parallel_processor:
            return JSONResponse(
                status_code=404,
                content={"error": "Parallel processor not initialized"}
            )

        # Get comprehensive performance metrics
        performance_metrics = parallel_processor.get_performance_metrics()

        return {
            "timestamp": performance_metrics.get('performance_report', {}).get('report_timestamp'),
            "performance_report": performance_metrics
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to get performance report: {str(e)}"}
        )

@router.post("/camera/parallel_config")
def update_parallel_config(config: dict):
    """Update parallel processing configuration."""
    try:
        camera = camera_manager.get_camera("basler", camera_id)

        if not camera or not hasattr(camera, 'parallel_processor'):
            return JSONResponse(
                status_code=404,
                content={"error": "Parallel processing not available"}
            )

        parallel_processor = camera.parallel_processor
        if not parallel_processor:
            return JSONResponse(
                status_code=404,
                content={"error": "Parallel processor not initialized"}
            )

        # Update configuration
        if 'enabled' in config:
            if config['enabled']:
                parallel_processor.enable_parallel_processing()
            else:
                parallel_processor.disable_parallel_processing()

        # Update resource optimizer config if available
        if hasattr(parallel_processor, 'resource_optimizer') and 'optimization' in config:
            parallel_processor.resource_optimizer.update_config(config['optimization'])

        return {
            "success": True,
            "message": "Configuration updated successfully",
            "current_config": {
                "enabled": parallel_processor.enabled,
                "thread_count": parallel_processor.thread_count
            }
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to update configuration: {str(e)}"}
        )
