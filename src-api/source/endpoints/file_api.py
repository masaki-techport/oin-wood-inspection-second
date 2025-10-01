from fastapi import APIRouter, HTTPException, Query, Response, Depends
from fastapi.responses import FileResponse
import os
import mimetypes
import re
import traceback
import glob
import cv2
import tempfile
from dependencies import get_session
from db import Inspection
from db.inspection_images import InspectionImage
from sqlalchemy.orm import Session
import logging

router = APIRouter(
    prefix="/api/file",
    tags=["file"],
)
logger = logging.getLogger(__name__)

def get_inspection_folder(inspection_id: int, session: Session) -> str:
    """
    Get the date folder for a specific inspection ID by querying the database.

    Args:
        inspection_id: The inspection ID to look up
        session: Database session

    Returns:
        The date folder name (e.g., "20250819_162320") or None if not found
    """
    try:
        # First try to get from inspection table
        inspection = session.query(Inspection).filter(Inspection.inspection_id == inspection_id).first()
        if inspection and inspection.folder_path:
            # Extract date folder from folder_path
            # folder_path might be like "data/images/inspection/20250819_162320"
            match = re.search(r'(\d{8}_\d{4,6})', inspection.folder_path)
            if match:
                logger.debug(f"Found date folder from inspection.folder_path: {match.group(1)}")
                return match.group(1)

        # If not found in inspection table, try inspection_images table
        inspection_image = session.query(InspectionImage).filter(
            InspectionImage.inspection_id == inspection_id
        ).first()
        if inspection_image and inspection_image.image_path:
            # Extract date folder from image_path
            match = re.search(r'(\d{8}_\d{4,6})', inspection_image.image_path)
            if match:
                logger.debug(f"Found date folder from inspection_images.image_path: {match.group(1)}")
                return match.group(1)

        logger.info(f"No date folder found for inspection_id: {inspection_id}")
        return None

    except Exception as e:
        logger.exception(f"Error getting inspection folder for ID {inspection_id}: {str(e)}")
        return None

@router.get("")
async def get_file(path: str = Query(..., description="Path to the file to serve"),
                  convert: str = Query(None, description="Convert image format (e.g., 'jpg')"),
                  inspection_id: int | None = Query(None, description="Inspection ID - required for inspection-bound files; not required for presentation cache"),
                  session: Session = Depends(get_session)):
    """
    Serve a file from the filesystem. Requires inspection_id to ensure files are only accessed from the correct inspection.
    """
    original_path = path
    
    try:
        logger.info(f"Requested file: {path}")
        
        # Attempt to normalize path separators
        path = path.replace('\\', '/')
        
        # Check for duplicated path segments like "inspection/...inspection/"
        duplicate_check = re.search(r'(inspection/.*?)inspection/', path, re.IGNORECASE)
        if duplicate_check:
            logger.debug(f"Detected duplicated path segments: {duplicate_check.group(0)}")
            # Find the last occurrence of "inspection/" and keep only what follows
            last_inspection_index = path.lower().rindex("inspection/")
            if last_inspection_index != -1:
                path = "src-api/data/images/" + path[last_inspection_index:]
                logger.debug(f"Cleaned duplicated path to: {path}")
        
        # Create a list to track all the paths we try and their existence status
        tried_paths = []
        
        # Special case: presentation cache files do not require inspection_id
        if 'presentation' in path.lower():
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/images/presentation"))
            # Normalize to absolute project path for src-api prefixed paths
            if path.startswith('src-api/'):
                rel = path[8:].replace('\\', '/')
                # Build absolute path under project root (src-api/...)
                project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
                candidate = os.path.join(project_root, rel)
                tried_paths.append({"path": candidate, "exists": os.path.isfile(candidate)})
                possible_paths = [candidate]
            else:
                # Fall back to joining with presentation directory by filename
                filename = os.path.basename(path)
                candidate = os.path.join(base_dir, filename)
                tried_paths.append({"path": candidate, "exists": os.path.isfile(candidate)})
                possible_paths = [candidate]

        # Handle Windows-style absolute paths
        if re.match(r'^[a-zA-Z]:[/\\]', path):
            # This is a Windows absolute path
            logger.debug(f"Detected Windows absolute path: {path}")
            
            # Try to extract the project-relative portion of the path
            project_name = "oin-wood-inspection"
            # Escape special regex characters in project name to avoid character set issues
            escaped_project_name = re.escape(project_name)
            match = re.search(rf'{escaped_project_name}[/\\](.*)', path, re.IGNORECASE)
            
            if match:
                # Found the project-relative path
                relative_path = match.group(1).replace('\\', '/')
                base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
                path = os.path.join(base_dir, relative_path)
                logger.debug(f"Converted to project-relative path: {path}")
                tried_paths.append({"path": path, "exists": os.path.isfile(path)})
            else:
                # Try to extract just the 'src-api/data/images/inspection' part
                inspection_match = re.search(r'inspection[/\\](.*)', path, re.IGNORECASE)
                if inspection_match:
                    relative_path = inspection_match.group(1).replace('\\', '/')
                    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/images/inspection"))
                    path = os.path.join(base_dir, relative_path)
                    logger.debug(f"Converted to inspection-relative path: {path}")
                    tried_paths.append({"path": path, "exists": os.path.isfile(path)})
        
        # Handle src-api prefix in path
        elif path.startswith('src-api/'):
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
            path = os.path.join(base_dir, path[8:])  # Remove the 'src-api/' prefix
            logger.debug(f"Converted src-api path to: {path}")
            tried_paths.append({"path": path, "exists": os.path.isfile(path)})
            
        else:
            # For non-absolute paths, try treating as relative to src-api/data/images/inspection
            if 'inspection' in path:
                # This might be a path like "images/inspection/folder/file.jpg"
                inspection_match = re.search(r'inspection[/\\](.*)', path, re.IGNORECASE)
                if inspection_match:
                    relative_path = inspection_match.group(1).replace('\\', '/')
                    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/images/inspection"))
                    inspection_path = os.path.join(base_dir, relative_path)
                    logger.debug(f"Trying inspection-relative path: {inspection_path}")
                    tried_paths.append({"path": inspection_path, "exists": os.path.isfile(inspection_path)})
                    
                    # If this path exists, use it
                    if os.path.isfile(inspection_path):
                        path = inspection_path
        
        # Alternative path construction for troubleshooting - try all possible variations
        possible_paths = [
            path,  # Original path after conversion
        ]
        tried_paths.append({"path": path, "exists": os.path.isfile(path)})
        
        # Extract the filename as a last resort
        filename = os.path.basename(path)
        if filename:
            # Try to find the file in the images/inspection directory
            inspection_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/images/inspection"))

            # Check if the inspection directory exists
            if not os.path.exists(inspection_dir):
                logger.warning(f"Inspection directory does not exist: {inspection_dir}")
                os.makedirs(inspection_dir, exist_ok=True)
                logger.info(f"Created inspection directory: {inspection_dir}")

            # If inspection_id is provided, try to get the specific date folder first
            if inspection_id:
                logger.debug(f"Using inspection_id {inspection_id} to find specific folder")
                with session:
                    date_folder = get_inspection_folder(inspection_id, session)
                    if date_folder:
                        # Try the specific date folder first
                        folder_path = os.path.join(inspection_dir, date_folder)
                        file_path = os.path.join(folder_path, filename)
                        if os.path.isfile(file_path):
                            logger.debug(f"Found file in inspection-specific folder: {file_path}")
                            possible_paths.append(file_path)
                            tried_paths.append({"path": file_path, "exists": True})
                        else:
                            logger.debug(f"File not found in inspection-specific folder: {file_path}")
                            tried_paths.append({"path": file_path, "exists": False})

            # Require inspection_id to be provided for inspection-scoped files only
            if ('presentation' not in path.lower()) and not inspection_id:
                logger.warning("No inspection_id provided. Inspection ID is required to access inspection-scoped files.")
                raise HTTPException(
                    status_code=400,
                    detail="inspection_id parameter is required for inspection-scoped files."
                )
            elif inspection_id and not possible_paths:
                logger.info(f"File not found in inspection {inspection_id} folder. Not searching other inspections.")
                        

            
        # Try all possible paths
        found_path = None
        for p in possible_paths:
            if os.path.isfile(p):
                found_path = p
                if p != path:
                    logger.debug(f"Using alternative path: {p}")
                break
        
        # If no path was found, provide detailed debug information
        if not found_path:
            logger.error(f"File not found: {path} (original path: {original_path})")
            logger.debug(f"Tried the following paths:")
            for i, p in enumerate(tried_paths):
                logger.debug(f"  {i+1}. {p['path']} - {'EXISTS' if p['exists'] else 'NOT FOUND'}")
            
            # List all available paths for debugging
            inspection_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/images/inspection"))
            if os.path.exists(inspection_dir):
                logger.debug(f"Available inspection directories:")
                for item in os.listdir(inspection_dir):
                    item_path = os.path.join(inspection_dir, item)
                    if os.path.isdir(item_path):
                        file_count = len([f for f in os.listdir(item_path) if os.path.isfile(os.path.join(item_path, f))])
                        logger.debug(f"  - {item}: {file_count} files")
            else:
                logger.warning(f"Inspection directory does not exist: {inspection_dir}")
            
            raise HTTPException(
                status_code=404, 
                detail=f"File not found: {path}. Tried {len(tried_paths)} path variations."
            )
        
        # Get the file's content type
        content_type, _ = mimetypes.guess_type(found_path)
        
        # Check if we need to convert the image
        if convert and convert.lower() == 'jpg' and found_path.lower().endswith('.bmp'):
            logger.info(f"Converting BMP to JPG for faster loading: {found_path}")
            try:
                # Read the BMP image
                img = cv2.imread(found_path)
                if img is None:
                    logger.error(f"Failed to read BMP image: {found_path}")
                    # Fall back to serving the original file
                    return FileResponse(
                        path=found_path,
                        media_type=content_type or 'application/octet-stream',
                        filename=os.path.basename(found_path)
                    )
                
                # Create a temporary file for the JPG
                with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
                    temp_path = temp_file.name
                
                # Write the image as JPG with quality 85 (good balance between quality and size)
                cv2.imwrite(temp_path, img, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                
                logger.info(f"Successfully converted to JPG: {temp_path}")
                
                # Serve the converted JPG file
                return FileResponse(
                    path=temp_path,
                    media_type='image/jpeg',
                    filename=os.path.basename(found_path).replace('.bmp', '.jpg')
                )
            except Exception as e:
                logger.exception(f"Error converting BMP to JPG: {str(e)}")
                # Fall back to serving the original file
        
        logger.info(f"Serving file: {found_path} with content type: {content_type}")
        
        # Return the file as a response
        return FileResponse(
            path=found_path,
            media_type=content_type or 'application/octet-stream',
            filename=os.path.basename(found_path)
        )
    except Exception as e:
        logger.exception(f"Error serving file {original_path}: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error serving file: {str(e)}") 

@router.get("/check")
async def check_file_exists(path: str = Query(..., description="Path to check if file exists"),
                           inspection_id: int = Query(..., description="Inspection ID - required to check files from specific inspection"),
                           session: Session = Depends(get_session)):
    """
    Check if a file exists without serving it. Requires inspection_id to ensure files are only checked from the correct inspection.
    """
    original_path = path
    
    try:
        logger.info(f"Checking if file exists: {path}")
        
        # Attempt to normalize path separators
        path = path.replace('\\', '/')
        
        # Check for duplicated path segments
        duplicate_check = re.search(r'(inspection/.*?)inspection/', path, re.IGNORECASE)
        if duplicate_check:
            logger.debug(f"Detected duplicated path segments: {duplicate_check.group(0)}")
            last_inspection_index = path.lower().rindex("inspection/")
            if last_inspection_index != -1:
                path = "src-api/data/images/" + path[last_inspection_index:]
                logger.debug(f"Cleaned duplicated path to: {path}")
        
        # Create a list to track all the paths we try
        tried_paths = []
        
        # Try the path as-is first
        absolute_path = os.path.abspath(path)
        tried_paths.append({"path": absolute_path, "exists": os.path.isfile(absolute_path)})
        
        # Handle Windows-style absolute paths
        if re.match(r'^[a-zA-Z]:[/\\]', path):
            # This is a Windows absolute path
            logger.debug(f"Detected Windows absolute path: {path}")
            
            # Try to extract the project-relative portion of the path
            project_name = "oin-wood-inspection"
            # Escape special regex characters in project name to avoid character set issues
            escaped_project_name = re.escape(project_name)
            match = re.search(rf'{escaped_project_name}[/\\](.*)', path, re.IGNORECASE)
            
            if match:
                relative_path = match.group(1).replace('\\', '/')
                base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
                project_path = os.path.join(base_dir, relative_path)
                tried_paths.append({"path": project_path, "exists": os.path.isfile(project_path)})
        
        # Handle src-api prefix in path
        elif path.startswith('src-api/'):
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
            api_path = os.path.join(base_dir, path[8:])  # Remove the 'src-api/' prefix
            tried_paths.append({"path": api_path, "exists": os.path.isfile(api_path)})
        
        # Try inspection-relative path
        inspection_match = re.search(r'inspection[/\\](.*)', path, re.IGNORECASE)
        if inspection_match:
            relative_path = inspection_match.group(1).replace('\\', '/')
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/images/inspection"))
            inspection_path = os.path.join(base_dir, relative_path)
            tried_paths.append({"path": inspection_path, "exists": os.path.isfile(inspection_path)})
        
        # Extract the filename as a last resort
        filename = os.path.basename(path)
        if filename:
            # Try to find the file in the images/inspection directory
            inspection_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/images/inspection"))

            # If inspection_id is provided, try to get the specific date folder first
            if inspection_id and os.path.exists(inspection_dir):
                logger.debug(f"Using inspection_id {inspection_id} to find specific folder")
                with session:
                    date_folder = get_inspection_folder(inspection_id, session)
                    if date_folder:
                        # Try the specific date folder first
                        folder_path = os.path.join(inspection_dir, date_folder)
                        file_path = os.path.join(folder_path, filename)
                        tried_paths.append({"path": file_path, "exists": os.path.isfile(file_path)})

            # Require inspection_id to be provided
            if not inspection_id:
                logger.warning("No inspection_id provided. Inspection ID is required to check files.")
                return {
                    "error": "inspection_id parameter is required. Please specify which inspection the file belongs to.",
                    "original_path": original_path,
                    "file_exists": False
                }
            elif inspection_id and os.path.exists(inspection_dir):
                logger.info(f"File not found in inspection {inspection_id} folder. Not searching other inspections.")
        
        # Find the first path that exists
        found_path = None
        for p in tried_paths:
            if p["exists"]:
                found_path = p["path"]
                break
        
        # Return the results
        return {
            "original_path": original_path,
            "normalized_path": path,
            "paths_checked": tried_paths,
            "file_exists": found_path is not None,
            "found_path": found_path if found_path else None,
            "inspection_dir_exists": os.path.exists(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/images/inspection")))
        }
    except Exception as e:
        logger.exception(f"Error checking file {original_path}: {str(e)}")
        return {
            "error": str(e),
            "original_path": original_path,
            "traceback": traceback.format_exc()
        }