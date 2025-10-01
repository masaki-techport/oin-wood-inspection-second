"""
Temp Sections API endpoints for temporary section management
"""

import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
import json
import asyncio
import time

from camera_manager import camera_manager

logger = logging.getLogger('TempSectionsAPI')

router = APIRouter()

@router.get("/temp-sections")
async def get_temp_sections(limit: int = Query(-1, ge=-1, description="Maximum number of sections to return (-1 for unlimited)")):
    """
    Get temporary sections in FIFO order (oldest first) for scrolling display.
    
    Args:
        limit: Maximum number of sections to return (-1 for unlimited, default -1)
        
    Returns:
        List of temp sections in FIFO order (oldest first) - frontend can scroll through all
    """
    try:
        # Get camera from manager
        camera = camera_manager.get_camera("basler", "temp_sections_api")
        if not camera or not hasattr(camera, 'buffer_manager') or not camera.buffer_manager:
            raise HTTPException(status_code=503, detail="Camera not available")
        
        # Get sections in FIFO order (oldest first) - frontend can scroll through all
        sections = camera.buffer_manager.get_temp_sections(limit)
        
        # Convert snake_case to camelCase for frontend compatibility
        converted_sections = []
        for section in sections:
            converted_section = {
                "id": section["id"],
                "label": section["label"],
                "status": section["status"],
                "imageIndices": section["image_indices"],
                "representativeImage": section.get("representative_image"),
                "summaryColor": section["summary_color"],
                "createdAt": section["created_at"],
                "completedAt": section["completed_at"]
            }
            converted_sections.append(converted_section)
        
        # Get reset timestamp from assembler
        last_reset_time = None
        if camera.buffer_manager.temp_section_assembler:
            last_reset_time = camera.buffer_manager.temp_section_assembler.get_last_reset_time()
        
        return {
            "sections": converted_sections,
            "count": len(converted_sections),
            "timestamp": time.time(),
            "cleared": len(converted_sections) == 0,  # Indicate if sections are cleared
            "last_reset_time": last_reset_time  # When sections were last reset
        }
        
    except Exception as e:
        logger.error(f"Error getting temp sections: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get temp sections: {str(e)}")

@router.get("/temp-sections/stats")
async def get_temp_section_stats():
    """Get temp section assembler statistics."""
    try:
        # Get camera from manager
        camera = camera_manager.get_camera("basler", "temp_sections_api")
        if not camera or not hasattr(camera, 'buffer_manager') or not camera.buffer_manager:
            raise HTTPException(status_code=503, detail="Camera not available")
        
        stats = camera.buffer_manager.get_temp_section_stats()
        
        return {
            "stats": stats,
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"Error getting temp section stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get temp section stats: {str(e)}")

@router.get("/temp-sections/live")
async def stream_temp_sections_live():
    """
    Server-Sent Events stream for real-time temp section updates.
    
    Events:
    - section_completed: New section completed
    - window_reset: Display window reset
    - save_sections: Sections saved after PASS_L_TO_R
    """
    async def event_generator():
        try:
            # Get camera from manager
            camera = camera_manager.get_camera("basler", "temp_sections_api")
            if not camera or not hasattr(camera, 'buffer_manager') or not camera.buffer_manager:
                yield f"data: {json.dumps({'error': 'Camera not available'})}\n\n"
                return
            
            last_section_count = 0
            last_saved_count = 0
            
            while True:
                try:
                    # Get current stats
                    stats = camera.buffer_manager.get_temp_section_stats()
                    current_section_count = stats.get('completed_sections', 0)
                    current_saved_count = stats.get('saved_sections', 0)
                    
                    # Check for new completed sections
                    if current_section_count > last_section_count:
                        sections = camera.buffer_manager.get_temp_sections(5)
                        event_data = {
                            "event": "section_completed",
                            "data": {
                                "sections": sections,
                                "count": current_section_count
                            }
                        }
                        yield f"data: {json.dumps(event_data)}\n\n"
                        last_section_count = current_section_count
                    
                    # Check for saved sections (PASS_L_TO_R triggered)
                    if current_saved_count > last_saved_count:
                        event_data = {
                            "event": "save_sections",
                            "data": {
                                "saved_count": current_saved_count,
                                "message": "Sections saved after PASS_L_TO_R"
                            }
                        }
                        yield f"data: {json.dumps(event_data)}\n\n"
                        last_saved_count = current_saved_count
                    
                    # Send heartbeat every 30 seconds
                    yield f"data: {json.dumps({'event': 'heartbeat', 'timestamp': time.time()})}\n\n"
                    
                    await asyncio.sleep(1)  # Check every second
                    
                except Exception as e:
                    logger.error(f"Error in SSE stream: {e}")
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
                    await asyncio.sleep(5)  # Wait before retrying
                    
        except Exception as e:
            logger.error(f"SSE stream error: {e}")
            yield f"data: {json.dumps({'error': 'Stream ended'})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )

@router.post("/temp-sections/reset")
async def reset_temp_sections():
    """Reset temp section assembler (for testing/debugging)."""
    try:
        # Get camera from manager
        camera = camera_manager.get_camera("basler", "temp_sections_api")
        if not camera or not hasattr(camera, 'buffer_manager') or not camera.buffer_manager:
            raise HTTPException(status_code=503, detail="Camera not available")
        
        if camera.buffer_manager.temp_section_assembler:
            camera.buffer_manager.temp_section_assembler.reset()
            logger.info("Temp section assembler reset")
        
        return {"message": "Temp sections reset successfully"}
        
    except Exception as e:
        logger.error(f"Error resetting temp sections: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reset temp sections: {str(e)}")
