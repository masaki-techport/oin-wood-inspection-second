from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import FileResponse
import os
import mimetypes
import re
import traceback
import glob
import cv2
import tempfile

router = APIRouter(
    prefix="/api/file",
    tags=["file"],
)

@router.get("")
async def get_file(path: str = Query(..., description="Path to the file to serve"), 
                  convert: str = Query(None, description="Convert image format (e.g., 'jpg')")):
    """
    Serve a file from the filesystem
    """
    original_path = path
    
    try:
        print(f"[FILE_API] Requested file: {path}")
        
        # Attempt to normalize path separators
        path = path.replace('\\', '/')
        
        # Check for duplicated path segments like "inspection/...inspection/"
        duplicate_check = re.search(r'(inspection/.*?)inspection/', path, re.IGNORECASE)
        if duplicate_check:
            print(f"[FILE_API] Detected duplicated path segments: {duplicate_check.group(0)}")
            # Find the last occurrence of "inspection/" and keep only what follows
            last_inspection_index = path.lower().rindex("inspection/")
            if last_inspection_index != -1:
                path = "src-api/data/images/" + path[last_inspection_index:]
                print(f"[FILE_API] Cleaned duplicated path to: {path}")
        
        # Create a list to track all the paths we try and their existence status
        tried_paths = []
        
        # Handle Windows-style absolute paths
        if re.match(r'^[a-zA-Z]:[/\\]', path):
            # This is a Windows absolute path
            print(f"[FILE_API] Detected Windows absolute path: {path}")
            
            # Try to extract the project-relative portion of the path
            project_name = "oin-wood-inspection"
            match = re.search(f'{project_name}[/\\](.*)', path, re.IGNORECASE)
            
            if match:
                # Found the project-relative path
                relative_path = match.group(1).replace('\\', '/')
                base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
                path = os.path.join(base_dir, relative_path)
                print(f"[FILE_API] Converted to project-relative path: {path}")
                tried_paths.append({"path": path, "exists": os.path.isfile(path)})
            else:
                # Try to extract just the 'src-api/data/images/inspection' part
                inspection_match = re.search(r'inspection[/\\](.*)', path, re.IGNORECASE)
                if inspection_match:
                    relative_path = inspection_match.group(1).replace('\\', '/')
                    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/images/inspection"))
                    path = os.path.join(base_dir, relative_path)
                    print(f"[FILE_API] Converted to inspection-relative path: {path}")
                    tried_paths.append({"path": path, "exists": os.path.isfile(path)})
        
        # Handle src-api prefix in path
        elif path.startswith('src-api/'):
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
            path = os.path.join(base_dir, path[8:])  # Remove the 'src-api/' prefix
            print(f"[FILE_API] Converted src-api path to: {path}")
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
                    print(f"[FILE_API] Trying inspection-relative path: {inspection_path}")
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
                print(f"[FILE_API] Warning: Inspection directory does not exist: {inspection_dir}")
                os.makedirs(inspection_dir, exist_ok=True)
                print(f"[FILE_API] Created inspection directory: {inspection_dir}")
            
            # First try to see if there's a specific date folder with this file
            date_folders = [d for d in os.listdir(inspection_dir) 
                           if os.path.isdir(os.path.join(inspection_dir, d))]
            
            for folder in date_folders:
                folder_path = os.path.join(inspection_dir, folder)
                file_path = os.path.join(folder_path, filename)
                if os.path.isfile(file_path):
                    print(f"[FILE_API] Found file in date folder: {file_path}")
                    possible_paths.append(file_path)
                    tried_paths.append({"path": file_path, "exists": True})
            
            # If not found in date folders, search recursively
            for root, dirs, files in os.walk(inspection_dir):
                if filename in files:
                    alt_path = os.path.join(root, filename)
                    if alt_path not in possible_paths:
                        print(f"[FILE_API] Found alternative path by filename: {alt_path}")
                        possible_paths.append(alt_path)
                        tried_paths.append({"path": alt_path, "exists": True})
                        
            # Try checking for similar filenames in case of timestamp variations
            if '_' in filename:
                # Get the base part of the filename (without timestamps)
                base_parts = filename.split('_')
                if len(base_parts) > 2:
                    # Use the frame number as a pattern
                    frame_part = next((part for part in base_parts if part.startswith('frame')), None)
                    if frame_part:
                        pattern = os.path.join(inspection_dir, '**', f"{frame_part}*.bmp")
                        matching_files = glob.glob(pattern, recursive=True)
                        for match in matching_files:
                            if match not in possible_paths:
                                print(f"[FILE_API] Found similar file by pattern: {match}")
                                possible_paths.append(match)
                                tried_paths.append({"path": match, "exists": os.path.isfile(match)})
            
        # Try all possible paths
        found_path = None
        for p in possible_paths:
            if os.path.isfile(p):
                found_path = p
                if p != path:
                    print(f"[FILE_API] Using alternative path: {p}")
                break
        
        # If no path was found, provide detailed debug information
        if not found_path:
            print(f"[FILE_API] File not found: {path} (original path: {original_path})")
            print(f"[FILE_API] Tried the following paths:")
            for i, p in enumerate(tried_paths):
                print(f"  {i+1}. {p['path']} - {'EXISTS' if p['exists'] else 'NOT FOUND'}")
            
            # List all available paths for debugging
            inspection_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/images/inspection"))
            if os.path.exists(inspection_dir):
                print(f"[FILE_API] Available inspection directories:")
                for item in os.listdir(inspection_dir):
                    item_path = os.path.join(inspection_dir, item)
                    if os.path.isdir(item_path):
                        file_count = len([f for f in os.listdir(item_path) if os.path.isfile(os.path.join(item_path, f))])
                        print(f"  - {item}: {file_count} files")
            else:
                print(f"[FILE_API] Inspection directory does not exist: {inspection_dir}")
            
            raise HTTPException(
                status_code=404, 
                detail=f"File not found: {path}. Tried {len(tried_paths)} path variations."
            )
        
        # Get the file's content type
        content_type, _ = mimetypes.guess_type(found_path)
        
        # Check if we need to convert the image
        if convert and convert.lower() == 'jpg' and found_path.lower().endswith('.bmp'):
            print(f"[FILE_API] Converting BMP to JPG for faster loading: {found_path}")
            try:
                # Read the BMP image
                img = cv2.imread(found_path)
                if img is None:
                    print(f"[FILE_API] Failed to read BMP image: {found_path}")
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
                
                print(f"[FILE_API] Successfully converted to JPG: {temp_path}")
                
                # Serve the converted JPG file
                return FileResponse(
                    path=temp_path,
                    media_type='image/jpeg',
                    filename=os.path.basename(found_path).replace('.bmp', '.jpg')
                )
            except Exception as e:
                print(f"[FILE_API] Error converting BMP to JPG: {str(e)}")
                traceback.print_exc()
                # Fall back to serving the original file
        
        print(f"[FILE_API] Serving file: {found_path} with content type: {content_type}")
        
        # Return the file as a response
        return FileResponse(
            path=found_path,
            media_type=content_type or 'application/octet-stream',
            filename=os.path.basename(found_path)
        )
    except Exception as e:
        print(f"[FILE_API] Error serving file {original_path}: {str(e)}")
        traceback.print_exc()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error serving file: {str(e)}") 

@router.get("/check")
async def check_file_exists(path: str = Query(..., description="Path to check if file exists")):
    """
    Check if a file exists without serving it - useful for debugging
    """
    original_path = path
    
    try:
        print(f"[FILE_API] Checking if file exists: {path}")
        
        # Attempt to normalize path separators
        path = path.replace('\\', '/')
        
        # Check for duplicated path segments
        duplicate_check = re.search(r'(inspection/.*?)inspection/', path, re.IGNORECASE)
        if duplicate_check:
            print(f"[FILE_API] Detected duplicated path segments: {duplicate_check.group(0)}")
            last_inspection_index = path.lower().rindex("inspection/")
            if last_inspection_index != -1:
                path = "src-api/data/images/" + path[last_inspection_index:]
                print(f"[FILE_API] Cleaned duplicated path to: {path}")
        
        # Create a list to track all the paths we try
        tried_paths = []
        
        # Try the path as-is first
        absolute_path = os.path.abspath(path)
        tried_paths.append({"path": absolute_path, "exists": os.path.isfile(absolute_path)})
        
        # Handle Windows-style absolute paths
        if re.match(r'^[a-zA-Z]:[/\\]', path):
            # This is a Windows absolute path
            print(f"[FILE_API] Detected Windows absolute path: {path}")
            
            # Try to extract the project-relative portion of the path
            project_name = "oin-wood-inspection"
            match = re.search(f'{project_name}[/\\](.*)', path, re.IGNORECASE)
            
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
            
            # First try to see if there's a specific date folder with this file
            if os.path.exists(inspection_dir):
                date_folders = [d for d in os.listdir(inspection_dir) 
                               if os.path.isdir(os.path.join(inspection_dir, d))]
                
                for folder in date_folders:
                    folder_path = os.path.join(inspection_dir, folder)
                    file_path = os.path.join(folder_path, filename)
                    if os.path.isfile(file_path):
                        tried_paths.append({"path": file_path, "exists": True})
        
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
        print(f"[FILE_API] Error checking file {original_path}: {str(e)}")
        traceback.print_exc()
        return {
            "error": str(e),
            "original_path": original_path,
            "traceback": traceback.format_exc()
        }