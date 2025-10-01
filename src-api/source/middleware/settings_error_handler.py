"""
Settings Error Handling Middleware
Provides centralized error handling for settings operations
"""

import logging
import traceback
from typing import Dict, Any, Optional
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from pydantic import ValidationError as PydanticValidationError

logger = logging.getLogger('SettingsErrorHandler')

class SettingsErrorHandler:
    """Centralized error handling for settings operations"""
    
    @staticmethod
    def handle_database_error(error: SQLAlchemyError, operation: str) -> HTTPException:
        """
        Handle database-related errors
        
        Args:
            error: SQLAlchemy error
            operation: Operation that caused the error
            
        Returns:
            HTTPException with appropriate status code and message
        """
        logger.error(f"Database error during {operation}: {error}")
        
        if isinstance(error, IntegrityError):
            return HTTPException(
                status_code=400,
                detail={
                    "error": "データベース整合性エラー",
                    "message": "設定データの整合性に問題があります",
                    "operation": operation,
                    "error_type": "integrity_error"
                }
            )
        
        return HTTPException(
            status_code=500,
            detail={
                "error": "データベースエラー",
                "message": "データベース操作中にエラーが発生しました",
                "operation": operation,
                "error_type": "database_error"
            }
        )
    
    @staticmethod
    def handle_validation_error(error: PydanticValidationError, operation: str) -> HTTPException:
        """
        Handle validation-related errors
        
        Args:
            error: Pydantic validation error
            operation: Operation that caused the error
            
        Returns:
            HTTPException with validation details
        """
        logger.warning(f"Validation error during {operation}: {error}")
        
        # Extract validation details
        validation_details = []
        for error_detail in error.errors():
            field_name = '.'.join(str(loc) for loc in error_detail['loc'])
            validation_details.append({
                'field': field_name,
                'message': error_detail['msg'],
                'input_value': error_detail.get('input'),
                'error_type': error_detail['type']
            })
        
        return HTTPException(
            status_code=422,
            detail={
                "error": "入力検証エラー",
                "message": "入力データに問題があります",
                "operation": operation,
                "validation_details": validation_details,
                "error_type": "validation_error"
            }
        )
    
    @staticmethod
    def handle_settings_not_found() -> HTTPException:
        """Handle case when settings are not found"""
        logger.warning("Settings not found in database")
        
        return HTTPException(
            status_code=404,
            detail={
                "error": "設定が見つかりません",
                "message": "設定データが存在しません。デフォルト設定を作成してください。",
                "error_type": "not_found"
            }
        )
    
    @staticmethod
    def handle_settings_service_error(error: Exception, operation: str) -> HTTPException:
        """
        Handle settings service-related errors
        
        Args:
            error: Service error
            operation: Operation that caused the error
            
        Returns:
            HTTPException with service error details
        """
        logger.error(f"Settings service error during {operation}: {error}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        return HTTPException(
            status_code=500,
            detail={
                "error": "設定サービスエラー",
                "message": "設定サービスの処理中にエラーが発生しました",
                "operation": operation,
                "error_type": "service_error"
            }
        )
    
    @staticmethod
    def handle_hardware_integration_error(error: Exception, hardware_type: str) -> HTTPException:
        """
        Handle hardware integration errors
        
        Args:
            error: Hardware error
            hardware_type: Type of hardware (camera, lighting, etc.)
            
        Returns:
            HTTPException with hardware error details
        """
        logger.error(f"Hardware integration error with {hardware_type}: {error}")
        
        return HTTPException(
            status_code=503,
            detail={
                "error": "ハードウェア連携エラー",
                "message": f"{hardware_type}との連携中にエラーが発生しました",
                "hardware_type": hardware_type,
                "error_type": "hardware_error"
            }
        )
    
    @staticmethod
    def handle_unexpected_error(error: Exception, operation: str) -> HTTPException:
        """
        Handle unexpected errors
        
        Args:
            error: Unexpected error
            operation: Operation that caused the error
            
        Returns:
            HTTPException with generic error message
        """
        logger.error(f"Unexpected error during {operation}: {error}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        return HTTPException(
            status_code=500,
            detail={
                "error": "予期しないエラー",
                "message": "システムエラーが発生しました。管理者にお問い合わせください。",
                "operation": operation,
                "error_type": "unexpected_error"
            }
        )

def create_error_response(
    status_code: int,
    error_title: str,
    error_message: str,
    error_details: Optional[Dict[str, Any]] = None
) -> JSONResponse:
    """
    Create standardized error response
    
    Args:
        status_code: HTTP status code
        error_title: Error title
        error_message: Error message
        error_details: Additional error details
        
    Returns:
        JSONResponse with error information
    """
    response_data = {
        "success": False,
        "error": error_title,
        "message": error_message,
        "timestamp": logger.handlers[0].formatter.formatTime(logger.makeRecord(
            'error', logging.ERROR, '', 0, '', (), None
        )) if logger.handlers else None
    }
    
    if error_details:
        response_data.update(error_details)
    
    return JSONResponse(
        status_code=status_code,
        content=response_data
    )

# Decorator for error handling
def handle_settings_errors(operation_name: str):
    """
    Decorator for handling settings operation errors
    
    Args:
        operation_name: Name of the operation for logging
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except SQLAlchemyError as e:
                raise SettingsErrorHandler.handle_database_error(e, operation_name)
            except PydanticValidationError as e:
                raise SettingsErrorHandler.handle_validation_error(e, operation_name)
            except HTTPException:
                # Re-raise HTTP exceptions as-is
                raise
            except Exception as e:
                raise SettingsErrorHandler.handle_unexpected_error(e, operation_name)
        
        return wrapper
    return decorator

# Async version of the decorator
def handle_settings_errors_async(operation_name: str):
    """
    Async decorator for handling settings operation errors
    
    Args:
        operation_name: Name of the operation for logging
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except SQLAlchemyError as e:
                raise SettingsErrorHandler.handle_database_error(e, operation_name)
            except PydanticValidationError as e:
                raise SettingsErrorHandler.handle_validation_error(e, operation_name)
            except HTTPException:
                # Re-raise HTTP exceptions as-is
                raise
            except Exception as e:
                raise SettingsErrorHandler.handle_unexpected_error(e, operation_name)
        
        return wrapper
    return decorator

# Context manager for error handling
class SettingsErrorContext:
    """Context manager for settings error handling"""
    
    def __init__(self, operation_name: str):
        self.operation_name = operation_name
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            return False  # No exception occurred
        
        if issubclass(exc_type, SQLAlchemyError):
            raise SettingsErrorHandler.handle_database_error(exc_val, self.operation_name)
        elif issubclass(exc_type, PydanticValidationError):
            raise SettingsErrorHandler.handle_validation_error(exc_val, self.operation_name)
        elif issubclass(exc_type, HTTPException):
            return False  # Let HTTP exceptions pass through
        else:
            raise SettingsErrorHandler.handle_unexpected_error(exc_val, self.operation_name)

# Example usage functions
def safe_settings_operation(operation_name: str, operation_func, *args, **kwargs):
    """
    Safely execute a settings operation with error handling
    
    Args:
        operation_name: Name of the operation
        operation_func: Function to execute
        *args, **kwargs: Function arguments
        
    Returns:
        Operation result or raises HTTPException
    """
    try:
        return operation_func(*args, **kwargs)
    except SQLAlchemyError as e:
        raise SettingsErrorHandler.handle_database_error(e, operation_name)
    except PydanticValidationError as e:
        raise SettingsErrorHandler.handle_validation_error(e, operation_name)
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        raise SettingsErrorHandler.handle_unexpected_error(e, operation_name)