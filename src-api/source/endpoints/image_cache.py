from fastapi import APIRouter, HTTPException, Query, Response, BackgroundTasks, Depends
from fastapi.responses import FileResponse
import os
import mimetypes
import cv2
import tempfile
import time
import hashlib
import shutil
from typing import Dict, Optional, List, Union
from pydantic import BaseModel
from threading import Lock
import threading
import logging
import traceback

# Set up logging
logger = logging.getLogger("image_cache")
logger.setLevel(logging.INFO)

router = APIRouter(
    prefix="/api/image-cache",
    tags=["image-cache"],
)

# Cache directory setup
CACHE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/image_cache"))
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR, exist_ok=True)

# In-memory cache for path mappings (source path -> cached path)
path_cache: Dict[str, Dict] = {}
cache_lock = Lock()  # Thread safety for the cache

# Cache stats for monitoring
cache_stats = {
    "hits": 0,
    "misses": 0,
    "errors": 0,
    "cached_files": 0,
    "total_size_bytes": 0,
    "last_cleanup": time.time()
}
stats_lock = Lock()

# Cache settings
MAX_CACHE_SIZE_BYTES = 1024 * 1024 * 1024  # 1 GB
MAX_CACHE_AGE = 60 * 60 * 24 * 7  # 7 days in seconds
CLEANUP_INTERVAL = 60 * 60 * 1  # 1 hour


class CacheInfo(BaseModel):
    """Model for cache information response"""
    hits: int
    misses: int
    errors: int
    cached_files: int
    total_size_bytes: int
    total_size_mb: float
    last_cleanup: str
    cache_directory: str


def get_file_hash(file_path: str) -> str:
    """Generate a unique hash for a file based on its path and modification time"""
    if not os.path.exists(file_path):
        return hashlib.md5(file_path.encode()).hexdigest()
    
    stats = os.stat(file_path)
    unique_id = f"{file_path}:{stats.st_mtime}:{stats.st_size}"
    return hashlib.md5(unique_id.encode()).hexdigest()


def cache_path_for_file(original_path: str, convert_format: Optional[str] = None) -> str:
    """Generate a cache path for a given file"""
    file_hash = get_file_hash(original_path)
    filename = os.path.basename(original_path)
    base_name, ext = os.path.splitext(filename)
    
    # If converting, use the target format as extension
    if convert_format:
        ext = f".{convert_format.lower()}"
    
    # Create a cache filename with the hash to avoid collisions
    cache_filename = f"{base_name}_{file_hash}{ext}"
    return os.path.join(CACHE_DIR, cache_filename)


def maybe_cleanup_cache(force: bool = False) -> None:
    """Clean up old cache files if needed"""
    with stats_lock:
        # Check if cleanup is needed
        now = time.time()
        if not force and now - cache_stats["last_cleanup"] < CLEANUP_INTERVAL:
            return
        
        cache_stats["last_cleanup"] = now
    
    # Do cleanup in a separate thread to avoid blocking
    thread = threading.Thread(target=do_cleanup_cache)
    thread.daemon = True
    thread.start()


def do_cleanup_cache() -> None:
    """Perform actual cache cleanup"""
    logger.info("Starting image cache cleanup")
    try:
        # Get all files in the cache
        files = []
        total_size = 0
        
        for file_name in os.listdir(CACHE_DIR):
            file_path = os.path.join(CACHE_DIR, file_name)
            if os.path.isfile(file_path):
                file_stats = os.stat(file_path)
                files.append((file_path, file_stats.st_mtime, file_stats.st_size))
                total_size += file_stats.st_size
        
        # Update stats
        with stats_lock:
            cache_stats["cached_files"] = len(files)
            cache_stats["total_size_bytes"] = total_size
        
        # Check if we need to clean up based on size or age
        now = time.time()
        files_to_delete = []
        
        # First mark files for deletion by age
        for file_path, mtime, size in files:
            if now - mtime > MAX_CACHE_AGE:
                files_to_delete.append((file_path, mtime, size))
        
        # If still over size limit, remove oldest files until under limit
        if total_size > MAX_CACHE_SIZE_BYTES:
            # Sort remaining files by modification time (oldest first)
            remaining_files = [f for f in files if f not in files_to_delete]
            remaining_files.sort(key=lambda x: x[1])
            
            current_size = total_size - sum(f[2] for f in files_to_delete)
            for file_path, mtime, size in remaining_files:
                if current_size <= MAX_CACHE_SIZE_BYTES:
                    break
                files_to_delete.append((file_path, mtime, size))
                current_size -= size
        
        # Delete the files
        for file_path, _, _ in files_to_delete:
            try:
                os.remove(file_path)
                logger.info(f"Removed cached file: {file_path}")
            except Exception as e:
                logger.error(f"Error removing cached file {file_path}: {e}")
        
        # After cleanup, update stats again
        remaining_size = total_size - sum(f[2] for f in files_to_delete)
        remaining_count = len(files) - len(files_to_delete)
        
        with stats_lock:
            cache_stats["cached_files"] = remaining_count
            cache_stats["total_size_bytes"] = remaining_size
        
        logger.info(f"Image cache cleanup complete. Removed {len(files_to_delete)} files. "
                   f"Remaining: {remaining_count} files, {remaining_size / (1024*1024):.2f} MB")
        
    except Exception as e:
        logger.error(f"Error during cache cleanup: {e}")
        logger.error(traceback.format_exc())


@router.get("/stats", response_model=CacheInfo)
async def get_cache_stats():
    """Get statistics about the image cache"""
    with stats_lock:
        stats = {
            "hits": cache_stats["hits"],
            "misses": cache_stats["misses"],
            "errors": cache_stats["errors"],
            "cached_files": cache_stats["cached_files"],
            "total_size_bytes": cache_stats["total_size_bytes"],
            "total_size_mb": cache_stats["total_size_bytes"] / (1024 * 1024),
            "last_cleanup": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(cache_stats["last_cleanup"])),
            "cache_directory": CACHE_DIR
        }
    return stats


@router.get("/cleanup")
async def trigger_cleanup():
    """Manually trigger cache cleanup"""
    maybe_cleanup_cache(force=True)
    return {"status": "cleanup started"}


@router.get("/image")
async def get_cached_image(
    path: str = Query(..., description="Path to the image file"),
    convert: str = Query(None, description="Convert image format (e.g., 'jpg')"),
    background_tasks: BackgroundTasks = None
):
    """
    Serve an image from the cache, or cache it if not already cached.
    This provides fast image loading by avoiding repeated format conversions.
    """
    original_path = path
    
    try:
        logger.info(f"Requested image: {path} (convert: {convert})")
        
        # Normalize path
        path = path.replace('\\', '/')
        
        # Check if this path is already cached
        cache_key = f"{path}:{convert or 'original'}"
        
        with cache_lock:
            cache_hit = cache_key in path_cache and os.path.exists(path_cache[cache_key]["cache_path"])
        
        if cache_hit:
            # Cache hit - serve from cache
            cached_info = path_cache[cache_key]
            cached_path = cached_info["cache_path"]
            content_type = cached_info["content_type"]
            
            # Update stats
            with stats_lock:
                cache_stats["hits"] += 1
            
            logger.info(f"Cache hit for {path} -> {cached_path}")
            
            # Schedule cleanup check in the background
            if background_tasks:
                background_tasks.add_task(maybe_cleanup_cache)
            
            # Return the cached file
            return FileResponse(
                path=cached_path,
                media_type=content_type,
                filename=os.path.basename(cached_path)
            )
        
        # Cache miss - we need to process the file
        with stats_lock:
            cache_stats["misses"] += 1
        
        logger.info(f"Cache miss for {path}")
        
        # Check if the original file exists
        if not os.path.isfile(path):
            with stats_lock:
                cache_stats["errors"] += 1
            raise HTTPException(status_code=404, detail=f"File not found: {path}")
        
        # Determine the cache path for this file
        cached_path = cache_path_for_file(path, convert)
        content_type, _ = mimetypes.guess_type(cached_path)
        
        # Process the file based on conversion request
        if convert and convert.lower() == 'jpg' and path.lower().endswith('.bmp'):
            try:
                # Read the image
                img = cv2.imread(path)
                if img is None:
                    with stats_lock:
                        cache_stats["errors"] += 1
                    raise HTTPException(
                        status_code=500, 
                        detail=f"Failed to read image file: {path}"
                    )
                
                # Write as JPG with quality 85
                cv2.imwrite(cached_path, img, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                
                # Update the content type
                content_type = 'image/jpeg'
                
                logger.info(f"Converted {path} to JPG: {cached_path}")
            except Exception as e:
                with stats_lock:
                    cache_stats["errors"] += 1
                logger.error(f"Error converting image: {e}")
                logger.error(traceback.format_exc())
                raise HTTPException(
                    status_code=500, 
                    detail=f"Error converting image: {str(e)}"
                )
        else:
            # Just copy the file to the cache without conversion
            try:
                shutil.copy2(path, cached_path)
                logger.info(f"Copied {path} to cache: {cached_path}")
            except Exception as e:
                with stats_lock:
                    cache_stats["errors"] += 1
                logger.error(f"Error copying file to cache: {e}")
                logger.error(traceback.format_exc())
                raise HTTPException(
                    status_code=500, 
                    detail=f"Error copying file to cache: {str(e)}"
                )
        
        # Update the cache metadata
        with cache_lock:
            path_cache[cache_key] = {
                "original_path": path,
                "cache_path": cached_path,
                "content_type": content_type or 'application/octet-stream',
                "last_access": time.time(),
                "convert": convert
            }
        
        # Update cache stats
        file_size = os.path.getsize(cached_path)
        with stats_lock:
            cache_stats["cached_files"] += 1
            cache_stats["total_size_bytes"] += file_size
        
        # Schedule cleanup check in the background
        if background_tasks:
            background_tasks.add_task(maybe_cleanup_cache)
        
        # Return the newly cached file
        return FileResponse(
            path=cached_path,
            media_type=content_type or 'application/octet-stream',
            filename=os.path.basename(cached_path)
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Log and wrap other exceptions
        logger.error(f"Error serving cached image {original_path}: {str(e)}")
        logger.error(traceback.format_exc())
        
        with stats_lock:
            cache_stats["errors"] += 1
            
        raise HTTPException(
            status_code=500, 
            detail=f"Error serving cached image: {str(e)}"
        )