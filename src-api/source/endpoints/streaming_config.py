"""
Streaming Configuration API Endpoints
Provides REST API for managing streaming configuration
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
import logging

from streaming.config import (
    config_manager,
    get_streaming_config,
    update_streaming_config,
    StreamingConfig,
    CameraStreamConfig,
    SSEConfig,
    FileStreamConfig,
    DataStreamConfig,
    ErrorHandlingConfig,
    MonitoringConfig
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/streaming/config", tags=["streaming-config"])


@router.get("/", response_model=Dict[str, Any])
async def get_current_config():
    """
    Get current streaming configuration
    
    Returns:
        Complete streaming configuration
    """
    try:
        config = get_streaming_config()
        return {
            "success": True,
            "config": config.to_dict(),
            "last_modified": config_manager._last_modified.isoformat() if config_manager._last_modified else None
        }
    except Exception as e:
        logger.error(f"Error getting streaming configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/camera", response_model=Dict[str, Any])
async def get_camera_config():
    """
    Get camera streaming configuration
    
    Returns:
        Camera streaming configuration
    """
    try:
        config = get_streaming_config()
        return {
            "success": True,
            "config": config.camera.__dict__
        }
    except Exception as e:
        logger.error(f"Error getting camera configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sse", response_model=Dict[str, Any])
async def get_sse_config():
    """
    Get SSE configuration
    
    Returns:
        SSE configuration
    """
    try:
        config = get_streaming_config()
        return {
            "success": True,
            "config": config.sse.__dict__
        }
    except Exception as e:
        logger.error(f"Error getting SSE configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/file", response_model=Dict[str, Any])
async def get_file_config():
    """
    Get file streaming configuration
    
    Returns:
        File streaming configuration
    """
    try:
        config = get_streaming_config()
        return {
            "success": True,
            "config": config.file.__dict__
        }
    except Exception as e:
        logger.error(f"Error getting file configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/data", response_model=Dict[str, Any])
async def get_data_config():
    """
    Get data streaming configuration
    
    Returns:
        Data streaming configuration
    """
    try:
        config = get_streaming_config()
        return {
            "success": True,
            "config": config.data.__dict__
        }
    except Exception as e:
        logger.error(f"Error getting data configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/error-handling", response_model=Dict[str, Any])
async def get_error_handling_config():
    """
    Get error handling configuration
    
    Returns:
        Error handling configuration
    """
    try:
        config = get_streaming_config()
        return {
            "success": True,
            "config": config.error_handling.__dict__
        }
    except Exception as e:
        logger.error(f"Error getting error handling configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/monitoring", response_model=Dict[str, Any])
async def get_monitoring_config():
    """
    Get monitoring configuration
    
    Returns:
        Monitoring configuration
    """
    try:
        config = get_streaming_config()
        return {
            "success": True,
            "config": config.monitoring.__dict__
        }
    except Exception as e:
        logger.error(f"Error getting monitoring configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/", response_model=Dict[str, Any])
async def update_complete_config(updates: Dict[str, Any]):
    """
    Update complete streaming configuration
    
    Args:
        updates: Configuration updates to apply
        
    Returns:
        Success status and validation results
    """
    try:
        # Validate the updates first
        current_config = get_streaming_config()
        current_dict = current_config.to_dict()
        
        # Apply updates to a copy for validation
        test_dict = current_dict.copy()
        config_manager._deep_update(test_dict, updates)
        
        # Create test configuration for validation
        test_config = StreamingConfig.from_dict(test_dict)
        validation_errors = test_config.validate()
        
        if validation_errors:
            return {
                "success": False,
                "error": "Configuration validation failed",
                "validation_errors": validation_errors
            }
        
        # Apply the updates
        success = update_streaming_config(updates)
        
        if success:
            return {
                "success": True,
                "message": "Configuration updated successfully",
                "config": get_streaming_config().to_dict()
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to update configuration")
            
    except Exception as e:
        logger.error(f"Error updating streaming configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/camera", response_model=Dict[str, Any])
async def update_camera_config(updates: Dict[str, Any]):
    """
    Update camera streaming configuration
    
    Args:
        updates: Camera configuration updates
        
    Returns:
        Success status and updated configuration
    """
    try:
        success = update_streaming_config({"camera": updates})
        
        if success:
            config = get_streaming_config()
            return {
                "success": True,
                "message": "Camera configuration updated successfully",
                "config": config.camera.__dict__
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to update camera configuration")
            
    except Exception as e:
        logger.error(f"Error updating camera configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/sse", response_model=Dict[str, Any])
async def update_sse_config(updates: Dict[str, Any]):
    """
    Update SSE configuration
    
    Args:
        updates: SSE configuration updates
        
    Returns:
        Success status and updated configuration
    """
    try:
        success = update_streaming_config({"sse": updates})
        
        if success:
            config = get_streaming_config()
            return {
                "success": True,
                "message": "SSE configuration updated successfully",
                "config": config.sse.__dict__
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to update SSE configuration")
            
    except Exception as e:
        logger.error(f"Error updating SSE configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/file", response_model=Dict[str, Any])
async def update_file_config(updates: Dict[str, Any]):
    """
    Update file streaming configuration
    
    Args:
        updates: File configuration updates
        
    Returns:
        Success status and updated configuration
    """
    try:
        success = update_streaming_config({"file": updates})
        
        if success:
            config = get_streaming_config()
            return {
                "success": True,
                "message": "File configuration updated successfully",
                "config": config.file.__dict__
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to update file configuration")
            
    except Exception as e:
        logger.error(f"Error updating file configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/data", response_model=Dict[str, Any])
async def update_data_config(updates: Dict[str, Any]):
    """
    Update data streaming configuration
    
    Args:
        updates: Data configuration updates
        
    Returns:
        Success status and updated configuration
    """
    try:
        success = update_streaming_config({"data": updates})
        
        if success:
            config = get_streaming_config()
            return {
                "success": True,
                "message": "Data configuration updated successfully",
                "config": config.data.__dict__
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to update data configuration")
            
    except Exception as e:
        logger.error(f"Error updating data configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/error-handling", response_model=Dict[str, Any])
async def update_error_handling_config(updates: Dict[str, Any]):
    """
    Update error handling configuration
    
    Args:
        updates: Error handling configuration updates
        
    Returns:
        Success status and updated configuration
    """
    try:
        success = update_streaming_config({"error_handling": updates})
        
        if success:
            config = get_streaming_config()
            return {
                "success": True,
                "message": "Error handling configuration updated successfully",
                "config": config.error_handling.__dict__
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to update error handling configuration")
            
    except Exception as e:
        logger.error(f"Error updating error handling configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/monitoring", response_model=Dict[str, Any])
async def update_monitoring_config(updates: Dict[str, Any]):
    """
    Update monitoring configuration
    
    Args:
        updates: Monitoring configuration updates
        
    Returns:
        Success status and updated configuration
    """
    try:
        success = update_streaming_config({"monitoring": updates})
        
        if success:
            config = get_streaming_config()
            return {
                "success": True,
                "message": "Monitoring configuration updated successfully",
                "config": config.monitoring.__dict__
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to update monitoring configuration")
            
    except Exception as e:
        logger.error(f"Error updating monitoring configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reload", response_model=Dict[str, Any])
async def reload_config():
    """
    Reload configuration from file
    
    Returns:
        Success status and current configuration
    """
    try:
        success = config_manager.load_config()
        
        if success:
            return {
                "success": True,
                "message": "Configuration reloaded successfully",
                "config": get_streaming_config().to_dict()
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to reload configuration")
            
    except Exception as e:
        logger.error(f"Error reloading configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate", response_model=Dict[str, Any])
async def validate_config(config_data: Optional[Dict[str, Any]] = None):
    """
    Validate configuration without applying changes
    
    Args:
        config_data: Configuration to validate (optional, uses current if not provided)
        
    Returns:
        Validation results
    """
    try:
        if config_data is None:
            config = get_streaming_config()
        else:
            config = StreamingConfig.from_dict(config_data)
        
        validation_errors = config.validate()
        
        return {
            "success": len(validation_errors) == 0,
            "validation_errors": validation_errors,
            "message": "Configuration is valid" if not validation_errors else "Configuration has validation errors"
        }
        
    except Exception as e:
        logger.error(f"Error validating configuration: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Configuration validation failed"
        }


@router.get("/defaults", response_model=Dict[str, Any])
async def get_default_config():
    """
    Get default streaming configuration
    
    Returns:
        Default configuration values
    """
    try:
        default_config = StreamingConfig()
        return {
            "success": True,
            "config": default_config.to_dict()
        }
    except Exception as e:
        logger.error(f"Error getting default configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset", response_model=Dict[str, Any])
async def reset_to_defaults():
    """
    Reset configuration to default values
    
    Returns:
        Success status and default configuration
    """
    try:
        default_config = StreamingConfig()
        success = update_streaming_config(default_config.to_dict())
        
        if success:
            return {
                "success": True,
                "message": "Configuration reset to defaults successfully",
                "config": default_config.to_dict()
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to reset configuration")
            
    except Exception as e:
        logger.error(f"Error resetting configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))