"""
Streaming endpoints for the wood inspection system
"""
from fastapi import APIRouter, HTTPException, Query, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from typing import Optional, List
from datetime import date
import os

from streaming.camera_stream import camera_stream_manager, create_camera_stream_response
from streaming.sensor_sse import create_sensor_sse_response, sensor_broadcaster
from streaming.file_stream import create_file_stream_response, file_stream_service
from streaming.inspection_stream import inspection_streamer
from streaming.analysis_stream import analysis_streamer

router = APIRouter(prefix="/api/stream", tags=["streaming"])


# Camera streaming endpoints
@router.get("/camera/{camera_type}")
async def stream_camera_feed(
    camera_type: str = "basler",
    camera_id: str = "default"
):
    """
    Stream live camera feed using multipart streaming
    
    Args:
        camera_type: Type of camera (basler, webcam)
        camera_id: Camera identifier
        
    Returns:
        Multipart streaming response with MJPEG frames
    """
    if camera_type not in ["basler", "webcam"]:
        raise HTTPException(status_code=400, detail="Invalid camera type")
    
    return create_camera_stream_response(camera_id, camera_type)


@router.get("/camera/status")
async def get_camera_stream_status():
    """Get camera streaming status and statistics"""
    return {
        "result": True,
        "data": camera_stream_manager.get_stream_stats()
    }


@router.post("/camera/configure")
async def configure_camera_stream(
    frame_rate: Optional[int] = Query(None, ge=1, le=30, description="Frame rate (1-30 FPS)"),
    quality: Optional[int] = Query(None, ge=10, le=100, description="JPEG quality (10-100)")
):
    """Configure camera stream parameters"""
    camera_stream_manager.configure_stream(frame_rate, quality)
    
    return {
        "result": True,
        "message": "Camera stream configuration updated",
        "data": {
            "frame_rate": camera_stream_manager.config.camera_frame_rate,
            "quality": camera_stream_manager.config.camera_quality
        }
    }


# Sensor status streaming endpoints
@router.get("/sensor/status")
async def stream_sensor_status():
    """
    Stream real-time sensor status updates via Server-Sent Events
    
    Returns:
        SSE stream with sensor status updates
    """
    return await create_sensor_sse_response()


@router.get("/sensor/connections")
async def get_sensor_stream_connections():
    """Get sensor SSE connection statistics"""
    return {
        "result": True,
        "data": {
            "active_connections": sensor_broadcaster.get_connection_count(),
            "stream_stats": sensor_broadcaster.get_stream_stats()
        }
    }


# File streaming endpoints
@router.get("/file")
async def stream_file(
    path: str = Query(..., description="Path to the file to stream"),
    convert: Optional[str] = Query(None, description="Convert to format (e.g., 'jpg')")
):
    """
    Stream file with optional format conversion
    
    Args:
        path: File path to stream
        convert: Optional format conversion (jpg, png, etc.)
        
    Returns:
        Streaming file response
    """
    # Use the same path resolution logic from the original file_api
    from endpoints.file_api import get_file
    
    # First, resolve the file path using existing logic
    try:
        # This is a bit of a hack - we'll call the original function to resolve the path
        # but catch any FileResponse and extract the path
        original_response = await get_file(path, convert)
        
        # If it's a FileResponse, we can get the path
        if hasattr(original_response, 'path'):
            resolved_path = original_response.path
        else:
            # If it's not a FileResponse, there might be an error
            raise HTTPException(status_code=404, detail="File not found")
            
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error resolving file path: {str(e)}")
    
    # Now stream the resolved file
    return create_file_stream_response(resolved_path, convert)


@router.get("/file/info")
async def get_file_info(path: str = Query(..., description="Path to the file")):
    """Get file information without streaming"""
    # Resolve path using the same logic as stream_file
    try:
        from endpoints.file_api import get_file
        original_response = await get_file(path)
        
        if hasattr(original_response, 'path'):
            resolved_path = original_response.path
            file_info = file_stream_service.get_file_info(resolved_path)
            
            return {
                "result": True,
                "data": file_info
            }
        else:
            raise HTTPException(status_code=404, detail="File not found")
            
    except HTTPException as e:
        raise e
    except Exception as e:
        return {
            "result": False,
            "error": str(e)
        }


# Inspection data streaming endpoints
@router.get("/inspections")
async def stream_inspections(
    limit: Optional[int] = Query(None, description="Maximum number of inspections to stream"),
    date_from: Optional[date] = Query(None, description="Filter inspections from this date"),
    date_to: Optional[date] = Query(None, description="Filter inspections to this date")
):
    """
    Stream inspection data progressively
    
    Args:
        limit: Maximum number of inspections to return
        date_from: Start date filter
        date_to: End date filter
        
    Returns:
        Streaming JSON response with inspection data
    """
    filters = {}
    if date_from:
        filters['date_from'] = date_from
    if date_to:
        filters['date_to'] = date_to
    
    return StreamingResponse(
        inspection_streamer.stream_inspections(filters, limit),
        media_type="application/json",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )


@router.get("/inspections/history")
async def stream_inspection_history(
    start_date: date = Query(..., description="Start date for history range"),
    end_date: date = Query(..., description="End date for history range")
):
    """
    Stream historical inspection data for date range
    
    Args:
        start_date: Start date for the range
        end_date: End date for the range
        
    Returns:
        Streaming JSON response with historical inspection data
    """
    return StreamingResponse(
        inspection_streamer.stream_inspection_history((start_date, end_date)),
        media_type="application/json",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )


@router.post("/inspections/analysis")
async def stream_analysis_results(
    inspection_ids: List[int] = Query(..., description="List of inspection IDs to analyze")
):
    """
    Stream analysis results for multiple inspections
    
    Args:
        inspection_ids: List of inspection IDs to get analysis for
        
    Returns:
        Streaming JSON response with analysis results
    """
    if not inspection_ids:
        raise HTTPException(status_code=400, detail="No inspection IDs provided")
    
    return StreamingResponse(
        inspection_streamer.stream_analysis_results(inspection_ids),
        media_type="application/json",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )


# Analysis pipeline streaming endpoints
@router.post("/analysis/multi-image")
async def stream_multi_image_analysis(files: List[UploadFile] = File(...)):
    """
    Stream analysis results for multiple images as processing completes
    
    Args:
        files: List of image files to analyze
        
    Returns:
        Streaming JSON response with analysis progress and results
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    # Validate file types
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
    for file in files:
        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file format: {file.filename}"
            )
    
    return StreamingResponse(
        analysis_streamer.stream_multi_image_analysis(files),
        media_type="application/json",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )


@router.post("/analysis/batch")
async def stream_batch_analysis(
    files: List[UploadFile] = File(...),
    batch_size: int = Query(3, ge=1, le=10, description="Number of files to process per batch")
):
    """
    Stream batch analysis results
    
    Args:
        files: List of image files to analyze
        batch_size: Number of files to process in each batch
        
    Returns:
        Streaming JSON response with batch processing results
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    return StreamingResponse(
        analysis_streamer.stream_batch_processing(files, batch_size),
        media_type="application/json",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )


# Streaming statistics endpoint
@router.get("/stats")
async def get_streaming_stats():
    """Get overall streaming statistics"""
    camera_stats = camera_stream_manager.get_stream_stats()
    sensor_stats = sensor_broadcaster.get_stream_stats()
    inspection_stats = inspection_streamer.get_stream_stats()
    
    analysis_stats = analysis_streamer.get_stream_stats()
    
    return {
        "result": True,
        "data": {
            "camera_streams": camera_stats,
            "sensor_streams": sensor_stats,
            "inspection_streams": inspection_stats,
            "analysis_streams": analysis_stats,
            "total_active_streams": (
                camera_stats.get("active_streams", 0) + 
                sensor_stats.get("active_streams", 0) +
                inspection_stats.get("active_streams", 0) +
                analysis_stats.get("active_streams", 0)
            ),
            "total_bytes_sent": (
                camera_stats.get("total_bytes_sent", 0) + 
                sensor_stats.get("total_bytes_sent", 0) +
                inspection_stats.get("total_bytes_sent", 0) +
                analysis_stats.get("total_bytes_sent", 0)
            )
        }
    }