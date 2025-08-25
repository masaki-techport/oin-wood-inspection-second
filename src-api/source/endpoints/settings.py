"""
Settings API endpoints
Provides access to application settings from settings.ini
"""

from fastapi import APIRouter
from typing import Dict, Any
from app_config import app_config

router = APIRouter()

@router.get("/settings")
async def get_settings() -> Dict[str, Dict[str, str]]:
    """
    Get all application settings from settings.ini
    
    Returns:
        Dictionary containing all settings organized by section
    """
    try:
        settings = {}
        
        # Get all sections from the config
        for section_name in app_config.config.sections():
            settings[section_name] = {}
            
            # Get all items in each section
            for key, value in app_config.config.items(section_name):
                settings[section_name][key] = value
        
        return settings
    except Exception as e:
        print(f"[SETTINGS API] Error getting settings: {e}")
        # Return empty settings if there's an error
        return {}

@router.get("/settings/{section}")
async def get_settings_section(section: str) -> Dict[str, str]:
    """
    Get settings for a specific section
    
    Args:
        section: The section name (e.g., 'DEBUG', 'CAMERA', etc.)
        
    Returns:
        Dictionary containing settings for the specified section
    """
    try:
        if app_config.config.has_section(section):
            return dict(app_config.config.items(section))
        else:
            return {}
    except Exception as e:
        print(f"[SETTINGS API] Error getting section {section}: {e}")
        return {}

@router.get("/settings/{section}/{key}")
async def get_setting_value(section: str, key: str) -> Dict[str, Any]:
    """
    Get a specific setting value
    
    Args:
        section: The section name
        key: The setting key
        
    Returns:
        Dictionary containing the setting value and metadata
    """
    try:
        value = app_config.get(section, key)
        return {
            "section": section,
            "key": key,
            "value": value,
            "exists": value is not None
        }
    except Exception as e:
        print(f"[SETTINGS API] Error getting setting {section}.{key}: {e}")
        return {
            "section": section,
            "key": key,
            "value": None,
            "exists": False,
            "error": str(e)
        }