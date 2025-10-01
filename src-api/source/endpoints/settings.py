"""
Settings API endpoints
Provides CRUD access to configuration file-based settings for the wood inspection application
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from typing import Dict, Any, Optional
import logging
from datetime import datetime

# Import configuration service
from services.config_settings_service import get_config_settings_service

# Configure logging
logger = logging.getLogger('SettingsAPI')
router = APIRouter()

# Pydantic models for request/response
class SettingsResponse(BaseModel):
    """Response model for settings data"""
    camera_exposure: int
    lighting_intensity: int
    ai_threshold: int
    length_threshold: float
    horizontal_mm_per_pixel: float
    vertical_mm_per_pixel: float
    last_updated: datetime = Field(default_factory=datetime.now)

class SettingsUpdateRequest(BaseModel):
    """Request model for updating settings"""
    camera_exposure: Optional[int] = Field(None, ge=0, le=100000, description="カメラ露光時間")
    lighting_intensity: Optional[int] = Field(None, ge=0, le=100, description="照明強度")
    ai_threshold: Optional[int] = Field(None, ge=10, le=100, description="AI閾値")
    length_threshold: Optional[float] = Field(None, gt=0, description="長さ閾値 (任意の正の値)")  # Removed range limit
    horizontal_mm_per_pixel: Optional[float] = Field(None, gt=0, description="分解能_横 (mm per pixel)")
    vertical_mm_per_pixel: Optional[float] = Field(None, gt=0, description="分解能_縦 (mm per pixel)")
    
    @validator('ai_threshold')
    def validate_ai_threshold(cls, v):
        if v is not None and not 10 <= v <= 100:
            raise ValueError('AI threshold must be between 10 and 100')
        return v

class ThresholdUpdateRequest(BaseModel):
    """Request model for single threshold updates"""
    value: float = Field(..., gt=0, description="Threshold value (any positive value)")  # Removed range limit

class AIThresholdUpdateRequest(BaseModel):
    """Request model for AI threshold updates"""
    value: int = Field(..., ge=10, le=100, description="AI threshold value")

class ResolutionUpdateRequest(BaseModel):
    """Request model for resolution updates"""
    horizontal_mm_per_pixel: float = Field(..., gt=0, description="分解能_横 (mm per pixel)")
    vertical_mm_per_pixel: float = Field(..., gt=0, description="分解能_縦 (mm per pixel)")

# Helper functions
def get_config_service():
    """Get the configuration settings service"""
    return get_config_settings_service()

# API Endpoints
@router.get("/settings/current", response_model=SettingsResponse)
async def get_current_settings_endpoint():
    """
    Get currently active settings from configuration file
    
    Returns:
        Current settings from configuration with all parameters including resolution
    """
    try:
        config_service = get_config_service()
        settings = config_service.get_all_settings()
        
        return SettingsResponse(
            camera_exposure=settings['camera_exposure'],
            lighting_intensity=settings['lighting_intensity'],
            ai_threshold=settings['ai_threshold'],
            length_threshold=settings['length_threshold'],
            horizontal_mm_per_pixel=settings['horizontal_mm_per_pixel'],
            vertical_mm_per_pixel=settings['vertical_mm_per_pixel']
        )
    except Exception as e:
        logger.error(f"Error getting current settings: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving settings")

@router.get("/settings", response_model=Dict[str, Any])
async def get_settings_legacy():
    """
    Legacy endpoint: Get settings organized by section for backwards compatibility
    
    Returns:
        Settings organized by section
    """
    try:
        config_service = get_config_service()
        
        # Get inspection settings from config service
        inspection_settings = config_service.get_all_settings()
        
        # Get other config sections from the INI file directly
        config = config_service.config
        all_settings = {}
        
        for section_name in config.sections():
            all_settings[section_name] = {}
            for key, value in config.items(section_name):
                all_settings[section_name][key] = value
        
        return all_settings
    except Exception as e:
        logger.error(f"Error getting legacy settings: {e}")
        return {}

@router.put("/settings", response_model=SettingsResponse)
async def update_settings(settings_update: SettingsUpdateRequest):
    """
    Update settings in configuration file
    
    Args:
        settings_update: Settings update request with new values
        
    Returns:
        Updated settings including resolution
    """
    try:
        config_service = get_config_service()
        
        # Prepare update data (only include non-None values)
        update_data = {}
        if settings_update.camera_exposure is not None:
            update_data['camera_exposure'] = settings_update.camera_exposure
        if settings_update.lighting_intensity is not None:
            update_data['lighting_intensity'] = settings_update.lighting_intensity
        if settings_update.ai_threshold is not None:
            update_data['ai_threshold'] = settings_update.ai_threshold
        if settings_update.length_threshold is not None:
            update_data['length_threshold'] = settings_update.length_threshold
        
        # Handle mm per pixel updates separately
        mm_per_pixel_update = {}
        if settings_update.horizontal_mm_per_pixel is not None:
            mm_per_pixel_update['horizontal_mm_per_pixel'] = settings_update.horizontal_mm_per_pixel
        if settings_update.vertical_mm_per_pixel is not None:
            mm_per_pixel_update['vertical_mm_per_pixel'] = settings_update.vertical_mm_per_pixel
        
        # Update settings in config file
        success = True
        if update_data:
            success = config_service.update_settings(**update_data)
        
        # Update mm per pixel values if provided
        if mm_per_pixel_update and success:
            if len(mm_per_pixel_update) == 2:
                success = config_service.update_resolution_mm_per_pixel(
                    mm_per_pixel_update['horizontal_mm_per_pixel'],
                    mm_per_pixel_update['vertical_mm_per_pixel']
                )
            else:
                # Handle partial updates
                current_settings = config_service.get_all_settings()
                horizontal = mm_per_pixel_update.get('horizontal_mm_per_pixel', current_settings['horizontal_mm_per_pixel'])
                vertical = mm_per_pixel_update.get('vertical_mm_per_pixel', current_settings['vertical_mm_per_pixel'])
                success = config_service.update_resolution_mm_per_pixel(horizontal, vertical)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update settings")
        
        # Return updated settings
        updated_settings = config_service.get_all_settings()
        updated_keys = list(update_data.keys()) + list(mm_per_pixel_update.keys())
        logger.info(f"Settings updated: {updated_keys}")
        
        return SettingsResponse(
            camera_exposure=updated_settings['camera_exposure'],
            lighting_intensity=updated_settings['lighting_intensity'],
            ai_threshold=updated_settings['ai_threshold'],
            length_threshold=updated_settings['length_threshold'],
            horizontal_mm_per_pixel=updated_settings['horizontal_mm_per_pixel'],
            vertical_mm_per_pixel=updated_settings['vertical_mm_per_pixel']
        )
        
    except ValueError as e:
        logger.error(f"Validation error updating settings: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating settings: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/settings/length-threshold", response_model=Dict[str, Any])
async def update_length_threshold(threshold_update: ThresholdUpdateRequest):
    """
    Update length threshold only (no range limitation)
    
    Args:
        threshold_update: New length threshold value (any positive value)
        
    Returns:
        Success message with updated threshold
    """
    try:
        config_service = get_config_service()
        success = config_service.update_length_threshold(threshold_update.value)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update length threshold")
        
        logger.info(f"Length threshold updated to {threshold_update.value}")
        
        return {
            "success": True,
            "message": "Length threshold updated successfully",
            "length_threshold": threshold_update.value
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating length threshold: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/settings/ai-threshold", response_model=Dict[str, Any])
async def update_ai_threshold(threshold_update: AIThresholdUpdateRequest):
    """
    Update AI threshold only
    
    Args:
        threshold_update: New AI threshold value
        
    Returns:
        Success message with updated threshold
    """
    try:
        config_service = get_config_service()
        success = config_service.update_ai_threshold(threshold_update.value)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update AI threshold")
        
        logger.info(f"AI threshold updated to {threshold_update.value}")
        
        return {
            "success": True,
            "message": "AI threshold updated successfully", 
            "ai_threshold": threshold_update.value
        }
        
    except Exception as e:
        logger.error(f"Error updating AI threshold: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/settings/resolution", response_model=Dict[str, Any])
async def update_resolution(resolution_update: ResolutionUpdateRequest):
    """
    Update resolution settings (mm per pixel values)
    
    Args:
        resolution_update: New resolution values (horizontal and vertical mm per pixel)
        
    Returns:
        Success message with updated resolution
    """
    try:
        config_service = get_config_service()
        success = config_service.update_resolution_mm_per_pixel(
            resolution_update.horizontal_mm_per_pixel, 
            resolution_update.vertical_mm_per_pixel
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update resolution")
        
        logger.info(f"Resolution updated to {resolution_update.horizontal_mm_per_pixel} x {resolution_update.vertical_mm_per_pixel} mm per pixel")
        
        return {
            "success": True,
            "message": "Resolution updated successfully",
            "horizontal_mm_per_pixel": resolution_update.horizontal_mm_per_pixel,
            "vertical_mm_per_pixel": resolution_update.vertical_mm_per_pixel
        }
        
    except Exception as e:
        logger.error(f"Error updating resolution: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/settings/reset", response_model=SettingsResponse)
async def reset_settings_to_defaults():
    """
    Reset settings to default values
    
    Returns:
        Settings with default values including resolution
    """
    try:
        config_service = get_config_service()
        
        # Reset to default values
        default_settings = {
            'camera_exposure': 1000,
            'lighting_intensity': 50,
            'ai_threshold': 50,
            'length_threshold': 10.0
        }
        
        success = config_service.update_settings(**default_settings)
        
        # Reset mm per pixel values
        if success:
            success = config_service.update_resolution_mm_per_pixel(0.245833, 0.288889)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to reset settings")
        
        logger.info("Settings reset to defaults")
        
        # Get the updated settings to return
        updated_settings = config_service.get_all_settings()
        
        return SettingsResponse(
            camera_exposure=updated_settings['camera_exposure'],
            lighting_intensity=updated_settings['lighting_intensity'],
            ai_threshold=updated_settings['ai_threshold'],
            length_threshold=updated_settings['length_threshold'],
            horizontal_mm_per_pixel=updated_settings['horizontal_mm_per_pixel'],
            vertical_mm_per_pixel=updated_settings['vertical_mm_per_pixel']
        )
        
    except Exception as e:
        logger.error(f"Error resetting settings: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Legacy endpoints for backwards compatibility
@router.get("/settings/{section}")
async def get_settings_section_legacy(section: str) -> Dict[str, str]:
    """
    Legacy endpoint: Get settings for a specific section
    
    Args:
        section: The section name (e.g., 'DEBUG', 'CAMERA', 'INSPECTION', etc.)
        
    Returns:
        Dictionary containing settings for the specified section
    """
    try:
        config_service = get_config_service()
        config = config_service.config
        
        if config.has_section(section):
            return dict(config.items(section))
        else:
            return {}
    except Exception as e:
        logger.error(f"Error getting section {section}: {e}")
        return {}

@router.get("/settings/{section}/{key}")
async def get_setting_value_legacy(section: str, key: str) -> Dict[str, Any]:
    """
    Legacy endpoint: Get a specific setting value
    
    Args:
        section: The section name
        key: The setting key
        
    Returns:
        Dictionary containing the setting value and metadata
    """
    try:
        config_service = get_config_service()
        config = config_service.config
        
        if config.has_option(section, key):
            value = config.get(section, key)
            return {
                "section": section,
                "key": key,
                "value": value,
                "exists": True
            }
        else:
            return {
                "section": section,
                "key": key,
                "value": None,
                "exists": False
            }
    except Exception as e:
        logger.error(f"Error getting setting {section}.{key}: {e}")
        return {
            "section": section,
            "key": key,
            "value": None,
            "exists": False,
            "error": str(e)
        }