# source/endpoints/camera.py
from fastapi import APIRouter
from fastapi.responses import JSONResponse
import base64
import cv2
from camera_manager import camera_manager
import logging

# Optional import for Basler camera
try:
    from camera.basler import BaslerCamera
    BASLER_AVAILABLE = True
except ImportError:
    logging.getLogger(__name__).warning("Basler camera not available - pypylon not installed")
    BaslerCamera = None
    BASLER_AVAILABLE = False

router = APIRouter()
logger = logging.getLogger(__name__)
# Use camera manager instead of direct instantiation
camera_id = "camera_endpoint"

@router.post("/camera/connect")
def connect_camera():
    logger.info("Camera connect request received")
    # Get camera from manager
    camera = camera_manager.get_camera("basler", camera_id)
    success = camera.is_connected()
    logger.info(f"Connection status: {'Connected' if success else 'Not connected'}")
    return {
        "connected": success,
        "message": "Camera connected successfully" if success else "No camera detected - running in development mode"
    }

@router.post("/camera/disconnect")
def disconnect_camera():
    logger.info("Camera disconnect request received")
    # Release camera from manager
    camera_manager.release_camera(camera_id)
    logger.info("Camera disconnected successfully")
    return {"disconnected": True}

@router.get("/camera/is_connected")
def check_camera_connection():
    logger.debug("Checking camera connection status")
    status = camera_manager.get_status()
    is_connected = status["is_connected"]
    logger.info(f"Connection check result: {'Connected' if is_connected else 'Disconnected'}")
    logger.debug(f"Camera details: Type={status['active_camera_type']}, Class={status['actual_camera_class']}")
    return {
        "connected": is_connected,
        "camera_type": status["active_camera_type"],
        "actual_camera_class": status["actual_camera_class"],
        "development_mode": status["development_mode"]
    }

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
    """Get camera snapshot with improved timeout handling"""
    import time
    start_time = time.time()
    
    try:
        logger.info(f"Snapshot request received at {start_time}")
        
        # Get camera manager status to determine which camera to use
        status = camera_manager.get_status()
        logger.debug(f"Camera manager status: {status}")

        # Quick timeout check - if no camera connected, return immediately
        if not status["is_connected"]:
            return {
                "image": "",
                "error": "No camera connected",
                "status": "disconnected",
                "camera_type": "none",
                "response_time_ms": int((time.time() - start_time) * 1000)
            }

        # Determine which camera type to request
        if status["development_mode"] and status["preferred_camera_type"] == "webcam":
            requested_camera_type = "webcam"
        else:
            requested_camera_type = "basler"
        
        logger.info(f"Requesting {requested_camera_type} camera for snapshot")

        # Try to get the requested camera type with timeout protection
        camera_get_start = time.time()
        try:
            logger.debug(f"Getting {requested_camera_type} camera from manager...")
            camera = camera_manager.get_camera(requested_camera_type, camera_id)
            camera_type_used = requested_camera_type
            camera_get_time = int((time.time() - camera_get_start) * 1000)
            logger.info(f"Successfully obtained {camera_type_used} camera in {camera_get_time}ms")
        except (ValueError, RuntimeError) as e:
            # Return error response instead of fallback
            error_time = int((time.time() - start_time) * 1000)
            logger.error(f"Failed to get {requested_camera_type} camera: {e} (took {error_time}ms)")
            return {
                "image": "",
                "error": f"Failed to connect to {requested_camera_type} camera: {str(e)}",
                "status": "camera_connection_failed",
                "camera_type": requested_camera_type,
                "connection_error": True,
                "response_time_ms": error_time
            }

        # Check connection status with timeout
        if not camera.is_connected():
            connection_check_time = int((time.time() - start_time) * 1000)
            logger.error(f"{camera_type_used} camera not connected, returning empty image (took {connection_check_time}ms)")
            return {
                "image": "",
                "error": f"{camera_type_used} camera not connected",
                "status": "disconnected",
                "camera_type": camera_type_used,
                "response_time_ms": connection_check_time
            }

        # Capture frame with timeout monitoring
        frame_start = time.time()
        logger.debug(f"Capturing frame from {camera_type_used} camera...")
        frame = camera.get_frame()
        frame_time = int((time.time() - frame_start) * 1000)
        
        if not frame:
            total_time = int((time.time() - start_time) * 1000)
            logger.error(f"Failed to grab image from {camera_type_used}, frame capture took {frame_time}ms, total {total_time}ms")
            return {
                "image": "",
                "error": "Failed to grab image",
                "status": "no_frame",
                "camera_type": camera_type_used,
                "frame_capture_time_ms": frame_time,
                "response_time_ms": total_time
            }

        # Handle different frame formats
        img = None
        if isinstance(frame, dict):
            # Check if this is a fallback image
            if "is_fallback" in frame and frame["is_fallback"]:
                logger.info(f"Using fallback image from {camera_type_used}")

            # Get image from frame data
            if "image" in frame:
                img = frame["image"]
            elif "frame" in frame:
                img = frame["frame"]
            else:
                logger.error(f"Frame data doesn't contain image data from {camera_type_used}")
                return {
                    "image": "",
                    "error": "Invalid frame format",
                    "status": "invalid_format",
                    "camera_type": camera_type_used
                }
        else:
            # Direct image array
            img = frame

        # Convert image to base64
        if img is not None:
            # Handle different color formats
            if len(img.shape) == 3:
                if img.shape[2] == 3:
                    # RGB image - convert to BGR for OpenCV
                    img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                else:
                    # Already BGR
                    img_bgr = img
            else:
                # Grayscale image
                img_bgr = img

            _, buffer = cv2.imencode(".jpg", img_bgr)
            base64_img = base64.b64encode(buffer).decode("utf-8")

            return {
                "image": base64_img,
                "status": "ok",
                "camera_type": camera_type_used,
                "actual_camera_class": camera.__class__.__name__,
                "frame_capture_time_ms": frame_time,
                "response_time_ms": int((time.time() - start_time) * 1000)
            }
        else:
            total_time = int((time.time() - start_time) * 1000)
            logger.error(f"No image data available from {camera_type_used} (total time: {total_time}ms)")
            return {
                "image": "",
                "error": "No image data available",
                "status": "no_image",
                "camera_type": camera_type_used,
                "response_time_ms": total_time
            }

    except Exception as e:
        total_time = int((time.time() - start_time) * 1000)
        logger.exception(f"Error in get_snapshot: {e} (total time: {total_time}ms)")
        return {
            "image": "",
            "error": str(e),
            "status": "error",
            "camera_type": "unknown",
            "response_time_ms": total_time
        }

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

@router.get("/camera/manager/status")
def get_camera_manager_status():
    """Get detailed camera manager status."""
    try:
        status = camera_manager.get_status()
        return {
            "success": True,
            "status": status
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to get camera manager status: {str(e)}"}
        )

@router.post("/camera/manager/development_mode")
def set_development_mode(config: dict):
    """Enable or disable development mode."""
    try:
        if "enabled" not in config:
            return JSONResponse(
                status_code=400,
                content={"error": "Missing 'enabled' parameter"}
            )

        camera_manager.set_development_mode(config["enabled"])

        return {
            "success": True,
            "message": f"Development mode {'enabled' if config['enabled'] else 'disabled'}",
            "development_mode": config["enabled"]
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to set development mode: {str(e)}"}
        )

@router.post("/camera/manager/switch_camera")
def switch_camera_type(config: dict):
    """Switch to a specific camera type."""
    try:
        if "camera_type" not in config:
            return JSONResponse(
                status_code=400,
                content={"error": "Missing 'camera_type' parameter"}
            )

        camera_type = config["camera_type"]
        if camera_type not in ["basler", "webcam"]:
            return JSONResponse(
                status_code=400,
                content={"error": "camera_type must be 'basler' or 'webcam'"}
            )

        # Force switch to the specified camera type
        try:
            camera = camera_manager.force_camera_type(camera_type, f"{camera_id}_switch")

            # Get updated status
            status = camera_manager.get_status()

            return {
                "success": True,
                "message": f"Successfully switched to {camera_type} camera",
                "status": status
            }
        except (ValueError, RuntimeError) as e:
            return JSONResponse(
                status_code=422,
                content={
                    "error": f"Failed to connect to {camera_type} camera",
                    "details": str(e),
                    "camera_type": camera_type,
                    "connection_error": True
                }
            )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Unexpected error: {str(e)}"}
        )

@router.post("/camera/manager/preferred_camera")
def set_preferred_camera_type(config: dict):
    """Set preferred camera type for development mode."""
    try:
        if "camera_type" not in config:
            return JSONResponse(
                status_code=400,
                content={"error": "Missing 'camera_type' parameter"}
            )

        camera_type = config["camera_type"]
        camera_manager.set_preferred_camera_type(camera_type)

        return {
            "success": True,
            "message": f"Preferred camera type set to {camera_type}",
            "preferred_camera_type": camera_type
        }
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={"error": str(e)}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to set preferred camera type: {str(e)}"}
        )
