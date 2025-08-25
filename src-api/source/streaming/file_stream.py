"""
File streaming service for efficient large file serving
"""
import os
import mimetypes
import tempfile
import cv2
from typing import AsyncGenerator, Optional, Dict, Any
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from .base import BaseStreamingService
from .error_handling import StreamErrorHandler


class FileStreamService(BaseStreamingService):
    """Service for streaming files efficiently"""
    
    def __init__(self):
        super().__init__()
        self.error_handler = StreamErrorHandler()
        self.conversion_cache = {}
    
    async def stream_file(self, file_path: str) -> AsyncGenerator[bytes, None]:
        """Stream file in chunks"""
        stream_id = self.generate_stream_id()
        status = self.register_stream(stream_id, "file_stream")
        
        try:
            if not os.path.isfile(file_path):
                raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
            
            file_size = os.path.getsize(file_path)
            self.logger.info(f"Starting file stream {stream_id} for {file_path} ({file_size} bytes)")
            
            with open(file_path, 'rb') as file:
                while status.is_active:
                    chunk = file.read(self.config.file.chunk_size)
                    if not chunk:
                        break
                    
                    yield chunk
                    self.update_stream_activity(stream_id, len(chunk))
        
        except Exception as e:
            self.logger.error(f"Error streaming file {file_path}: {e}")
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(status_code=500, detail=f"Error streaming file: {str(e)}")
        
        finally:
            await self.cleanup_stream(stream_id)
    
    async def stream_with_conversion(self, file_path: str, target_format: str) -> AsyncGenerator[bytes, None]:
        """Stream file with format conversion"""
        stream_id = self.generate_stream_id()
        status = self.register_stream(stream_id, f"file_conversion_{target_format}")
        
        try:
            if not os.path.isfile(file_path):
                raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
            
            # Check if conversion is needed
            file_ext = os.path.splitext(file_path)[1].lower()
            target_ext = f".{target_format.lower()}"
            
            if file_ext == target_ext:
                # No conversion needed, stream original file
                async for chunk in self.stream_file(file_path):
                    yield chunk
                return
            
            # Perform conversion and stream
            if target_format.lower() == 'jpg' and file_ext == '.bmp':
                async for chunk in self._convert_bmp_to_jpg_stream(file_path, stream_id):
                    yield chunk
            else:
                # For other conversions, fall back to original file
                self.logger.warning(f"Conversion from {file_ext} to {target_ext} not supported, serving original")
                async for chunk in self.stream_file(file_path):
                    yield chunk
        
        except Exception as e:
            self.logger.error(f"Error in file conversion stream: {e}")
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(status_code=500, detail=f"Error in file conversion: {str(e)}")
        
        finally:
            await self.cleanup_stream(stream_id)
    
    async def _convert_bmp_to_jpg_stream(self, bmp_path: str, stream_id: str) -> AsyncGenerator[bytes, None]:
        """Convert BMP to JPG and stream the result"""
        try:
            # Read BMP image
            img = cv2.imread(bmp_path)
            if img is None:
                raise ValueError(f"Failed to read BMP image: {bmp_path}")
            
            # Convert to JPG in memory
            encode_params = [cv2.IMWRITE_JPEG_QUALITY, 85]
            success, buffer = cv2.imencode('.jpg', img, encode_params)
            
            if not success:
                raise ValueError("Failed to encode image as JPG")
            
            # Stream the converted image in chunks
            jpg_bytes = buffer.tobytes()
            total_size = len(jpg_bytes)
            
            self.logger.info(f"Converted BMP to JPG: {bmp_path} -> {total_size} bytes")
            
            # Stream in chunks
            for i in range(0, total_size, self.config.file.chunk_size):
                chunk = jpg_bytes[i:i + self.config.file.chunk_size]
                yield chunk
                self.update_stream_activity(stream_id, len(chunk))
        
        except Exception as e:
            self.logger.error(f"Error converting BMP to JPG: {e}")
            raise
    
    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """Get file metadata"""
        if not os.path.isfile(file_path):
            return {"exists": False}
        
        stat = os.stat(file_path)
        content_type, _ = mimetypes.guess_type(file_path)
        
        return {
            "exists": True,
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "content_type": content_type or 'application/octet-stream',
            "filename": os.path.basename(file_path)
        }
    
    async def cleanup_stream(self, stream_id: str):
        """Clean up resources for a specific stream"""
        if stream_id in self.active_streams:
            self.active_streams[stream_id].is_active = False
        
        self.unregister_stream(stream_id)
        self.logger.info(f"Cleaned up file stream {stream_id}")


# Global file stream service instance
file_stream_service = FileStreamService()


def create_file_stream_response(file_path: str, convert_format: Optional[str] = None) -> StreamingResponse:
    """Create a StreamingResponse for file streaming"""
    
    # Get file info
    file_info = file_stream_service.get_file_info(file_path)
    
    if not file_info["exists"]:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Determine content type
    content_type = file_info["content_type"]
    filename = file_info["filename"]
    
    # Adjust content type for conversion
    if convert_format:
        if convert_format.lower() == 'jpg':
            content_type = 'image/jpeg'
            filename = os.path.splitext(filename)[0] + '.jpg'
    
    # Create appropriate stream generator
    if convert_format:
        stream_generator = file_stream_service.stream_with_conversion(file_path, convert_format)
    else:
        stream_generator = file_stream_service.stream_file(file_path)
    
    # Prepare headers
    headers = {
        "Content-Type": content_type,
        "Content-Disposition": f"inline; filename={filename}",
        "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
        "Accept-Ranges": "bytes"
    }
    
    # Add content length if no conversion
    if not convert_format:
        headers["Content-Length"] = str(file_info["size"])
    
    return StreamingResponse(
        stream_generator,
        media_type=content_type,
        headers=headers
    )