"""
Settings Validation Utilities
Provides comprehensive validation for settings data with detailed error messages
"""

from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field, validator
import logging

logger = logging.getLogger('SettingsValidation')

class ValidationError(Exception):
    """Custom exception for validation errors"""
    def __init__(self, field: str, message: str, value: Any = None):
        super().__init__(message)
        self.field = field
        self.message = message
        self.value = value

class ValidationResult:
    """Result of validation operation"""
    def __init__(self):
        self.is_valid = True
        self.errors: List[ValidationError] = []
        self.warnings: List[str] = []
    
    def add_error(self, field: str, message: str, value: Any = None):
        """Add validation error"""
        self.is_valid = False
        self.errors.append(ValidationError(field, message, value))
    
    def add_warning(self, message: str):
        """Add validation warning"""
        self.warnings.append(message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            'is_valid': self.is_valid,
            'errors': [
                {
                    'field': error.field,
                    'message': error.message,
                    'value': error.value
                }
                for error in self.errors
            ],
            'warnings': self.warnings
        }

class SettingsValidator:
    """Comprehensive settings validator with business logic"""
    
    # Validation rules
    CAMERA_EXPOSURE_MIN = 0
    CAMERA_EXPOSURE_MAX = 100000
    CAMERA_EXPOSURE_RECOMMENDED_MIN = 1000
    CAMERA_EXPOSURE_RECOMMENDED_MAX = 50000
    
    LIGHTING_INTENSITY_MIN = 0
    LIGHTING_INTENSITY_MAX = 100
    LIGHTING_INTENSITY_RECOMMENDED_MIN = 20
    LIGHTING_INTENSITY_RECOMMENDED_MAX = 80
    
    AI_THRESHOLD_MIN = 10
    AI_THRESHOLD_MAX = 100
    AI_THRESHOLD_RECOMMENDED_MIN = 30
    AI_THRESHOLD_RECOMMENDED_MAX = 80
    
    LENGTH_THRESHOLD_MIN = 1.0
    LENGTH_THRESHOLD_MAX = 50.0
    LENGTH_THRESHOLD_RECOMMENDED_MIN = 5.0
    LENGTH_THRESHOLD_RECOMMENDED_MAX = 20.0
    
    @classmethod
    def validate_camera_exposure(cls, value: Any) -> ValidationResult:
        """Validate camera exposure value"""
        result = ValidationResult()
        
        # Type validation
        if not isinstance(value, (int, float)):
            result.add_error('camera_exposure', 'カメラ露光は数値で入力してください', value)
            return result
        
        value = int(value)
        
        # Range validation
        if value < cls.CAMERA_EXPOSURE_MIN or value > cls.CAMERA_EXPOSURE_MAX:
            result.add_error(
                'camera_exposure', 
                f'カメラ露光は{cls.CAMERA_EXPOSURE_MIN}～{cls.CAMERA_EXPOSURE_MAX}μsの範囲で入力してください', 
                value
            )
            return result
        
        # Recommended range warning
        if value < cls.CAMERA_EXPOSURE_RECOMMENDED_MIN or value > cls.CAMERA_EXPOSURE_RECOMMENDED_MAX:
            result.add_warning(
                f'カメラ露光の推奨範囲は{cls.CAMERA_EXPOSURE_RECOMMENDED_MIN}～{cls.CAMERA_EXPOSURE_RECOMMENDED_MAX}μsです'
            )
        
        return result
    
    @classmethod
    def validate_lighting_intensity(cls, value: Any) -> ValidationResult:
        """Validate lighting intensity value"""
        result = ValidationResult()
        
        # Type validation
        if not isinstance(value, (int, float)):
            result.add_error('lighting_intensity', '照明強度は数値で入力してください', value)
            return result
        
        value = int(value)
        
        # Range validation
        if value < cls.LIGHTING_INTENSITY_MIN or value > cls.LIGHTING_INTENSITY_MAX:
            result.add_error(
                'lighting_intensity', 
                f'照明強度は{cls.LIGHTING_INTENSITY_MIN}～{cls.LIGHTING_INTENSITY_MAX}%の範囲で入力してください', 
                value
            )
            return result
        
        # Recommended range warning
        if value < cls.LIGHTING_INTENSITY_RECOMMENDED_MIN or value > cls.LIGHTING_INTENSITY_RECOMMENDED_MAX:
            result.add_warning(
                f'照明強度の推奨範囲は{cls.LIGHTING_INTENSITY_RECOMMENDED_MIN}～{cls.LIGHTING_INTENSITY_RECOMMENDED_MAX}%です'
            )
        
        return result
    
    @classmethod
    def validate_ai_threshold(cls, value: Any) -> ValidationResult:
        """Validate AI threshold value"""
        result = ValidationResult()
        
        # Type validation
        if not isinstance(value, (int, float)):
            result.add_error('ai_threshold', 'AI閾値は数値で入力してください', value)
            return result
        
        value = int(value)
        
        # Range validation
        if value < cls.AI_THRESHOLD_MIN or value > cls.AI_THRESHOLD_MAX:
            result.add_error(
                'ai_threshold', 
                f'AI閾値は{cls.AI_THRESHOLD_MIN}～{cls.AI_THRESHOLD_MAX}%の範囲で入力してください', 
                value
            )
            return result
        
        # Recommended range warning
        if value < cls.AI_THRESHOLD_RECOMMENDED_MIN or value > cls.AI_THRESHOLD_RECOMMENDED_MAX:
            result.add_warning(
                f'AI閾値の推奨範囲は{cls.AI_THRESHOLD_RECOMMENDED_MIN}～{cls.AI_THRESHOLD_RECOMMENDED_MAX}%です'
            )
        
        return result
    
    @classmethod
    def validate_length_threshold(cls, value: Any) -> ValidationResult:
        """Validate length threshold value"""
        result = ValidationResult()
        
        # Type validation
        if not isinstance(value, (int, float)):
            result.add_error('length_threshold', '長さ閾値は数値で入力してください', value)
            return result
        
        value = float(value)
        
        # Range validation
        if value < cls.LENGTH_THRESHOLD_MIN or value > cls.LENGTH_THRESHOLD_MAX:
            result.add_error(
                'length_threshold', 
                f'長さ閾値は{cls.LENGTH_THRESHOLD_MIN}～{cls.LENGTH_THRESHOLD_MAX}mmの範囲で入力してください', 
                value
            )
            return result
        
        # Recommended range warning
        if value < cls.LENGTH_THRESHOLD_RECOMMENDED_MIN or value > cls.LENGTH_THRESHOLD_RECOMMENDED_MAX:
            result.add_warning(
                f'長さ閾値の推奨範囲は{cls.LENGTH_THRESHOLD_RECOMMENDED_MIN}～{cls.LENGTH_THRESHOLD_RECOMMENDED_MAX}mmです'
            )
        
        return result
    
    @classmethod
    def validate_settings_data(cls, data: Dict[str, Any]) -> ValidationResult:
        """Validate complete settings data"""
        result = ValidationResult()
        
        # Validate each field if present
        if 'camera_exposure' in data:
            field_result = cls.validate_camera_exposure(data['camera_exposure'])
            if not field_result.is_valid:
                result.errors.extend(field_result.errors)
                result.is_valid = False
            result.warnings.extend(field_result.warnings)
        
        if 'lighting_intensity' in data:
            field_result = cls.validate_lighting_intensity(data['lighting_intensity'])
            if not field_result.is_valid:
                result.errors.extend(field_result.errors)
                result.is_valid = False
            result.warnings.extend(field_result.warnings)
        
        if 'ai_threshold' in data:
            field_result = cls.validate_ai_threshold(data['ai_threshold'])
            if not field_result.is_valid:
                result.errors.extend(field_result.errors)
                result.is_valid = False
            result.warnings.extend(field_result.warnings)
        
        if 'length_threshold' in data:
            field_result = cls.validate_length_threshold(data['length_threshold'])
            if not field_result.is_valid:
                result.errors.extend(field_result.errors)
                result.is_valid = False
            result.warnings.extend(field_result.warnings)
        
        # Cross-field validation
        cls._validate_cross_field_rules(data, result)
        
        return result
    
    @classmethod
    def _validate_cross_field_rules(cls, data: Dict[str, Any], result: ValidationResult):
        """Validate cross-field business rules"""
        
        # Example: Check if AI threshold and length threshold are in good balance
        if 'ai_threshold' in data and 'length_threshold' in data:
            ai_threshold = data['ai_threshold']
            length_threshold = data['length_threshold']
            
            # High AI threshold with very low length threshold might cause issues
            if ai_threshold >= 80 and length_threshold <= 2.0:
                result.add_warning(
                    'AI閾値が高く、長さ閾値が低い設定です。誤検知が増える可能性があります。'
                )
            
            # Low AI threshold with high length threshold might miss defects
            if ai_threshold <= 20 and length_threshold >= 30.0:
                result.add_warning(
                    'AI閾値が低く、長さ閾値が高い設定です。欠陥を見逃す可能性があります。'
                )
        
        # Example: Camera exposure and lighting intensity balance
        if 'camera_exposure' in data and 'lighting_intensity' in data:
            exposure = data['camera_exposure']
            lighting = data['lighting_intensity']
            
            # Very high exposure with very high lighting might cause overexposure
            if exposure >= 30000 and lighting >= 90:
                result.add_warning(
                    'カメラ露光と照明強度が両方とも高い設定です。露出オーバーの可能性があります。'
                )
            
            # Very low exposure with very low lighting might cause underexposure
            if exposure <= 2000 and lighting <= 10:
                result.add_warning(
                    'カメラ露光と照明強度が両方とも低い設定です。露出不足の可能性があります。'
                )

def validate_settings_middleware(data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """
    Middleware function for settings validation
    
    Args:
        data: Settings data to validate
        
    Returns:
        Tuple of (is_valid, validation_result)
    """
    try:
        validation_result = SettingsValidator.validate_settings_data(data)
        
        if validation_result.is_valid:
            logger.info(f"Settings validation passed with {len(validation_result.warnings)} warnings")
        else:
            logger.warning(f"Settings validation failed with {len(validation_result.errors)} errors")
        
        return validation_result.is_valid, validation_result.to_dict()
        
    except Exception as e:
        logger.error(f"Unexpected error during settings validation: {e}")
        return False, {
            'is_valid': False,
            'errors': [
                {
                    'field': 'validation',
                    'message': f'Validation error: {str(e)}',
                    'value': None
                }
            ],
            'warnings': []
        }

# Convenience functions for single field validation
def validate_camera_exposure(value: Any) -> ValidationResult:
    """Validate camera exposure value"""
    return SettingsValidator.validate_camera_exposure(value)

def validate_lighting_intensity(value: Any) -> ValidationResult:
    """Validate lighting intensity value"""
    return SettingsValidator.validate_lighting_intensity(value)

def validate_ai_threshold(value: Any) -> ValidationResult:
    """Validate AI threshold value"""
    return SettingsValidator.validate_ai_threshold(value)

def validate_length_threshold(value: Any) -> ValidationResult:
    """Validate length threshold value"""
    return SettingsValidator.validate_length_threshold(value)