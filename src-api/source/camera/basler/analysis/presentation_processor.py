"""
Presentation image processing functionality for BaslerCamera.
"""

import os
import time
import logging
import threading
import numpy as np
from typing import Dict, Any, List, Tuple
from datetime import datetime

from db.inspection_presentation import InspectionPresentation
from db import Inspection
from db.inspection_details import InspectionDetails

logger = logging.getLogger('BaslerCamera.PresentationProcessor')

class PresentationProcessor:
    """Handles presentation image processing for display and UI"""
    
    def __init__(self, camera_instance):
        """Initialize with a reference to the parent camera object"""
        self.camera = camera_instance
        
    def process_presentation_images_background(self, inspection_id: int, image_paths: List[str]) -> None:
        """
        Process presentation images in a background thread
        
        Args:
            inspection_id: Inspection ID to associate images with
            image_paths: List of image paths to process
        """
        try:
            logger.info(f"Background thread: Processing presentation images for inspection {inspection_id}")
            self.save_presentation_images(inspection_id, image_paths)
            logger.info(f"Background thread: Completed processing presentation images")
        except Exception as e:
            logger.error(f"Background thread: Error processing presentation images: {e}")
    
    def _select_best_image_by_severity(self, session, image_paths: List[str], inspection_id: int) -> Tuple[str, int]:
        """
        Select the best image from a group based on defect severity.
        Priority order: largest knot > hole > discoloration > middle image
        
        Args:
            session: Database session
            image_paths: List of image paths to check
            inspection_id: Inspection ID
            
        Returns:
            Tuple[str, int]: (Path to the selected image, extracted image_no) or (None, None) if no suitable image found
        """
        try:
            # Initialize variables to track best image
            best_image = None
            best_image_no = None
            best_score = -1
            best_length = -1
            best_priority = -1
            
            # Define defect priority (higher number = higher priority)
            defect_priority = {
                2: 3,  # knot_dead (highest priority)
                3: 3,  # flow_dead (highest priority)
                5: 3,  # knot_live (highest priority)
                4: 3,  # flow_live (highest priority)
                1: 2,  # hole (medium priority)
                0: 1   # discoloration (lowest priority)
            }
            
            # Check each image for defects
            for image_path in image_paths:
                # Extract image_no from path for consistent logic
                image_no = self._extract_image_no_from_path(image_path)
                if image_no is None:
                    logger.warning(f"Could not extract image_no from path: {image_path}")
                    continue
                
                # Query inspection details using image_no for consistency with frontend
                details = session.query(InspectionDetails).filter(
                    InspectionDetails.inspection_id == inspection_id,
                    InspectionDetails.image_no == image_no
                ).all()
                
                if not details:
                    # Also try querying by image_path as fallback
                    details = session.query(InspectionDetails).filter(
                        InspectionDetails.inspection_id == inspection_id,
                        InspectionDetails.image_path == image_path
                    ).all()
                
                if not details:
                    continue
                    
                # Find the most severe defect in this image
                image_best_priority = -1
                image_best_length = -1
                for detail in details:
                    error_type = detail.error_type
                    priority = defect_priority.get(error_type, 0)
                    length = detail.length
                    
                    # Update if higher priority or same priority but larger length
                    if (priority > image_best_priority or 
                        (priority == image_best_priority and length > image_best_length)):
                        image_best_priority = priority
                        image_best_length = length
                
                # Calculate score combining priority and length
                # Priority is the main factor, length is secondary
                image_score = image_best_priority * 1000 + image_best_length
                
                # Update if this image has a better score
                if image_score > best_score:
                    best_score = image_score
                    best_image = image_path
                    best_image_no = image_no
                    best_priority = image_best_priority
                    best_length = image_best_length
            
            # Log selection decision
            if best_image:
                logger.info(f"_select_best_image_by_severity: Selected image with priority {best_priority}, length {best_length}, image_no {best_image_no}: {best_image}")
            else:
                logger.info("_select_best_image_by_severity: No image with defects found in this group")
                
            return best_image, best_image_no
            
        except Exception as e:
            logger.error(f"Error selecting best image by severity: {e}")
            return None, None

    def _extract_image_no_from_path(self, image_path: str) -> int:
        """
        Extract image_no from image path using "No_????" pattern.
        This matches the frontend logic for consistency.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            int: Extracted image number or None if not found
        """
        import re
        
        if not image_path:
            return None

        try:
            # Look for "No_" followed by digits in the path
            # Handle both forward and backward slashes, use the last occurrence
            matches = re.findall(r'No_(\d+)', image_path)
            if matches:
                # Use the last match in case there are multiple "No_" patterns
                image_no_str = matches[-1]
                image_no = int(image_no_str)
                logger.debug(f"Extracted image_no {image_no} from path: {image_path}")
                return image_no
            else:
                logger.debug(f"Could not extract image_no from path: {image_path}")
                return None
        except Exception as e:
            logger.error(f"Error extracting image_no from path {image_path}: {e}")
            return None
    
    def save_presentation_images(self, inspection_id: int, image_paths: List[str]) -> None:
        """
        Save representative images for presentation groups A-E with optimized performance
        
        Args:
            inspection_id: The inspection ID to associate with the presentation images
            image_paths: List of paths to the saved images
        """
        if not image_paths:
            logger.warning("No images to select for presentation")
            return
            
        # Track performance metrics
        start_time = time.time()
        logger.info(f"Selecting presentation images from {len(image_paths)} images for inspection {inspection_id}")
        
        # Use atomic operations for better performance
        try:
            # Use a single database session for the entire operation
            with self.camera.db_handler.Session() as session:
                # Use a transaction for atomicity
                session.begin()
                
                try:
                    # Clear existing data with optimized query
                    session.query(InspectionPresentation).filter(
                        InspectionPresentation.inspection_id == inspection_id
                    ).delete(synchronize_session=False)  # Faster deletion
                    
                    # FIXED: Create image data with extracted image_no for proper alignment
                    # Extract image_no from each path and create a sorted list
                    image_data = []
                    for image_path in image_paths:
                        image_no = self._extract_image_no_from_path(image_path)
                        if image_no is not None:
                            image_data.append({
                                'image_path': image_path,
                                'image_no': image_no
                            })
                        else:
                            logger.warning(f"Could not extract image_no from path: {image_path}")
                    
                    # Sort by image_no to ensure consistent ordering that matches frontend expectations
                    image_data.sort(key=lambda x: x['image_no'])
                    
                    if not image_data:
                        logger.error("No valid images with extractable image_no found")
                        return
                    
                    logger.info(f"Processing {len(image_data)} images with valid image_no values")
                    for img in image_data:
                        logger.debug(f"  Image {img['image_no']}: {img['image_path']}")
                    
                    # Calculate group ranges based on sorted image_data (not raw image_paths)
                    total_images = len(image_data)
                    group_count = min(5, total_images)  # Maximum of 5 groups (A-E)
                    
                    # Pre-allocate group_images dictionary
                    group_images = {}
                    normalized_group_images = {}
                    presentation_objects = []
                    
                    # Calculate group ranges using the sorted image_data
                    if group_count == 1:
                        # Single image case - assign to group A
                        group_ranges = {'A': (0, total_images)}
                    elif group_count <= 5:
                        # Use numpy for faster calculations
                        group_sizes = np.full(group_count, total_images // group_count)
                        remainder = total_images % group_count
                        if remainder > 0:
                            group_sizes[:remainder] += 1
                        
                        # Assign group names (A-E)
                        group_names = [chr(65 + i) for i in range(group_count)]
                        
                        # Calculate indices in a single pass
                        indices = np.cumsum(group_sizes)
                        start_indices = np.concatenate(([0], indices[:-1]))
                        
                        # Create group ranges
                        group_ranges = {}
                        for i, group_name in enumerate(group_names):
                            start_idx = start_indices[i]
                            end_idx = indices[i]
                            group_ranges[group_name] = (start_idx, end_idx)
                            logger.info(f"Group {group_name}: indices {start_idx}-{end_idx-1} (images {[image_data[j]['image_no'] for j in range(start_idx, end_idx)]})")
                    else:
                        # Evenly distributed samples - use numpy for optimized calculation
                        indices = np.linspace(0, total_images, 6, dtype=int)
                        group_names = ['A', 'B', 'C', 'D', 'E']
                        
                        # Create group ranges
                        group_ranges = {}
                        for i, group_name in enumerate(group_names):
                            start_idx = indices[i]
                            end_idx = indices[i+1]
                            group_ranges[group_name] = (start_idx, end_idx)
                            logger.info(f"Group {group_name}: indices {start_idx}-{end_idx-1} (images {[image_data[j]['image_no'] for j in range(start_idx, end_idx)]})")
                    
                    # Find images with defects in each group with severity prioritization
                    for group_name, (start_idx, end_idx) in group_ranges.items():
                        # Get the image data for this group (not just paths)
                        group_image_data = image_data[start_idx:end_idx]
                        if not group_image_data:
                            continue
                        
                        # Extract just the paths for the severity selection method
                        group_image_paths = [img['image_path'] for img in group_image_data]
                        
                        logger.info(f"Selecting best image for group {group_name} from {len(group_image_paths)} images:")
                        for img in group_image_data:
                            logger.info(f"  Candidate: image_no={img['image_no']}, path={img['image_path']}")
                            
                        # Select best image based on severity criteria
                        selected_image, selected_image_no = self._select_best_image_by_severity(session, group_image_paths, inspection_id)
                        if selected_image:
                            group_images[group_name] = selected_image
                            logger.info(f"Selected image for group {group_name}: image_no={selected_image_no}, path={selected_image}")
                        else:
                            # Fallback to middle image if no defects found
                            middle_idx = len(group_image_data) // 2
                            fallback_image = group_image_data[middle_idx]
                            group_images[group_name] = fallback_image['image_path']
                            logger.info(f"No defects found for group {group_name}, using middle image: image_no={fallback_image['image_no']}, path={fallback_image['image_path']}")
                    
                    # Normalize paths and validate files in parallel
                    valid_groups = set()
                    for group, path in group_images.items():
                        # Enhanced path normalization for frontend compatibility
                        abs_path = os.path.abspath(path) if not os.path.isabs(path) else path
                        
                        # Quick file existence check
                        if os.path.isfile(abs_path):
                            # Create frontend-compatible path format
                            try:
                                # Normalize path separators first
                                normalized_abs_path = abs_path.replace('\\', '/')
                                
                                # Extract the relative path from the data/images directory
                                # The frontend expects paths relative to src-api/data/images/
                                if "/data/images/" in normalized_abs_path:
                                    # Get everything after data/images/
                                    data_images_index = normalized_abs_path.find("/data/images/")
                                    relative_part = normalized_abs_path[data_images_index + len("/data/images/"):]
                                    normalized_path = relative_part
                                elif "inspection" in normalized_abs_path:
                                    # Fallback: Get the part after inspection folder
                                    inspection_index = normalized_abs_path.rfind("inspection")
                                    relative_part = normalized_abs_path[inspection_index:]
                                    normalized_path = relative_part
                                else:
                                    # Last resort: just normalize separators
                                    normalized_path = normalized_abs_path
                                    
                                logger.info(f"Path normalization for group {group}:")
                                logger.info(f"  Original: {path}")
                                logger.info(f"  Absolute: {abs_path}")
                                logger.info(f"  Normalized: {normalized_path}")
                                
                            except Exception as e:
                                logger.warning(f"Error normalizing path {abs_path}: {e}, using fallback")
                                # Fallback: just normalize separators and use relative path
                                normalized_path = path.replace('\\', '/')
                            
                            normalized_group_images[group] = normalized_path
                            valid_groups.add(group)
                            
                            # Create database object for batch insertion
                            presentation_objects.append(
                                InspectionPresentation(
                                    inspection_id=inspection_id,
                                    group_name=group,
                                    image_path=normalized_path
                                )
                            )
                    
                    # Batch insert all objects for better performance
                    if presentation_objects:
                        session.bulk_save_objects(presentation_objects)
                        logger.info(f"Batch inserted {len(presentation_objects)} presentation images")
                    
                    # Prepare presentation data for API retrieval
                    presentation_images_data = [
                        {
                            "inspection_id": inspection_id,
                            "group_name": obj.group_name,
                            "image_path": obj.image_path
                        }
                        for obj in presentation_objects
                    ]
                    
                    # Get inspection date with minimal query
                    inspection_dt = None
                    inspection = session.query(Inspection.inspection_dt).filter(Inspection.inspection_id == inspection_id).first()
                    if inspection:
                        inspection_dt = inspection[0].isoformat()
                    
                    # Update last_inspection_results with minimal overhead
                    inspection_results_update = {
                        "inspection_id": inspection_id,
                        "presentation_images": presentation_images_data,
                        "inspection_dt": inspection_dt,
                        "presentation_ready": True
                    }
                    
                    # Commit all changes in a single transaction
                    session.commit()
                    
                    # Update the results after successful commit
                    with self.camera.lock:  # Thread-safe update
                        if self.camera.last_inspection_results is None:
                            self.camera.last_inspection_results = inspection_results_update
                        else:
                            # Preserve inspection_details if it exists in current results
                            inspection_details = self.camera.last_inspection_results.get('inspection_details', [])
                            self.camera.last_inspection_results.update(inspection_results_update)
                            # Restore inspection_details if not in the update
                            if 'inspection_details' not in inspection_results_update and inspection_details:
                                self.camera.last_inspection_results['inspection_details'] = inspection_details
                    
                    end_time = time.time()
                    logger.info(f"Saved {len(presentation_objects)} presentation images in {end_time - start_time:.3f}s")
                    
                except Exception as db_error:
                    # Rollback transaction on error
                    session.rollback()
                    logger.error(f"Database error: {db_error}")
                    raise  # Re-raise for outer exception handling
        
        except Exception as e:
            logger.error(f"Error saving presentation images: {e}")
            # If we failed completely, make sure presentation_ready is set to False
            if self.camera.last_inspection_results and self.camera.last_inspection_results.get("inspection_id") == inspection_id:
                self.camera.last_inspection_results["presentation_ready"] = False