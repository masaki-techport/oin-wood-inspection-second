"""
Presentation Results Consolidator for Parallel Processing.

This module consolidates presentation image selection results from parallel groups
and manages database updates and frontend notifications.
"""

import os
import time
import logging
import threading
from typing import List, Dict, Any, Optional
from datetime import datetime

from db.inspection_presentation import InspectionPresentation
from db import Inspection
from .defect_classification_engine import GroupDefectAnalysis, DefectAnalysis

logger = logging.getLogger('BaslerCamera.PresentationResultsConsolidator')

class PresentationResultsConsolidator:
    """
    Consolidates presentation image selection results from parallel processing groups.
    
    Responsibilities:
    - Collect results from all processing groups (A-E)
    - Validate selected images and paths
    - Update database with final presentation images
    - Trigger frontend notifications
    - Provide performance metrics and logging
    """
    
    def __init__(self, camera_instance):
        """
        Initialize the presentation results consolidator.
        
        Args:
            camera_instance: Reference to the parent BaslerCamera object
        """
        self.camera = camera_instance
        self._lock = threading.Lock()
        
        # Processing state
        self.inspection_id = None
        self.group_results = {}  # group_name -> GroupDefectAnalysis
        self.consolidation_start_time = None
        self.consolidation_complete = False
        
        # Results tracking
        self.selected_images = {}  # group_name -> DefectAnalysis
        self.presentation_objects = []
        self.performance_metrics = {}
    
    def initialize_consolidation(self, inspection_id: int):
        """
        Initialize consolidation for a new inspection.
        
        Args:
            inspection_id: Inspection ID for this consolidation session
        """
        with self._lock:
            self.inspection_id = inspection_id
            self.consolidation_start_time = time.time()
            self.consolidation_complete = False
            
            # Reset state
            self.group_results = {}
            self.selected_images = {}
            self.presentation_objects = []
            self.performance_metrics = {}
            
            logger.info(f"Initialized presentation consolidation for inspection {inspection_id}")
    
    def add_group_result(self, group_analysis: GroupDefectAnalysis, 
                        selected_image: Optional[DefectAnalysis]) -> None:
        """
        Add a group's presentation selection result.
        
        Args:
            group_analysis: Analysis result for the group
            selected_image: Selected presentation image for the group
        """
        try:
            with self._lock:
                group_name = group_analysis.group_name
                self.group_results[group_name] = group_analysis
                
                if selected_image:
                    self.selected_images[group_name] = selected_image
                    logger.info(f"Added result for group {group_name}: "
                              f"image {selected_image.image_no} ({selected_image.classification.value})")
                else:
                    logger.warning(f"No selected image for group {group_name}")
                    
        except Exception as e:
            logger.error(f"Error adding group result for {group_analysis.group_name}: {e}")
    
    def consolidate_results(self) -> Dict[str, Any]:
        """
        Consolidate all group results and update the database.
        
        Returns:
            Dict[str, Any]: Consolidation results and metrics
        """
        try:
            consolidation_start = time.time()
            logger.info(f"Starting presentation results consolidation for inspection {self.inspection_id}")
            
            with self._lock:
                if not self.selected_images:
                    logger.warning("No selected images to consolidate")
                    return self._create_consolidation_result(success=False, reason="no_selected_images")
                
                # Validate and prepare presentation objects
                valid_presentations = self._prepare_presentation_objects()
                
                if not valid_presentations:
                    logger.error("No valid presentation objects created")
                    return self._create_consolidation_result(success=False, reason="no_valid_presentations")
                
                # Update database
                database_success = self._update_database(valid_presentations)
                
                if not database_success:
                    logger.error("Failed to update database with presentation images")
                    return self._create_consolidation_result(success=False, reason="database_update_failed")
                
                # Update camera's last inspection results
                self._update_camera_results()
                
                # Calculate performance metrics
                consolidation_time = time.time() - consolidation_start
                self.performance_metrics = {
                    'consolidation_time': consolidation_time,
                    'total_groups_processed': len(self.group_results),
                    'successful_selections': len(self.selected_images),
                    'database_objects_created': len(valid_presentations)
                }
                
                self.consolidation_complete = True
                
                logger.info(f"Presentation consolidation completed in {consolidation_time:.3f}s: "
                          f"{len(valid_presentations)} images from {len(self.group_results)} groups")
                
                return self._create_consolidation_result(success=True)
                
        except Exception as e:
            logger.error(f"Error consolidating presentation results: {e}")
            return self._create_consolidation_result(success=False, reason=f"exception: {e}")
    
    def _prepare_presentation_objects(self) -> List[InspectionPresentation]:
        """
        Prepare and validate presentation objects for database insertion.
        
        Returns:
            List[InspectionPresentation]: Valid presentation objects
        """
        try:
            valid_presentations = []
            
            for group_name, selected_image in self.selected_images.items():
                # Validate image path
                if not self._validate_image_path(selected_image.image_path):
                    logger.warning(f"Invalid image path for group {group_name}: {selected_image.image_path}")
                    continue
                
                # Normalize path for frontend compatibility
                normalized_path = self._normalize_image_path(selected_image.image_path)
                
                # Create presentation object
                presentation_obj = InspectionPresentation(
                    inspection_id=self.inspection_id,
                    group_name=group_name,
                    image_path=normalized_path
                )
                
                valid_presentations.append(presentation_obj)
                logger.debug(f"Created presentation object for group {group_name}: "
                           f"image {selected_image.image_no} -> {normalized_path}")
            
            self.presentation_objects = valid_presentations
            return valid_presentations
            
        except Exception as e:
            logger.error(f"Error preparing presentation objects: {e}")
            return []
    
    def _validate_image_path(self, image_path: str) -> bool:
        """
        Validate that the image path exists and is accessible.
        
        Args:
            image_path: Path to validate
            
        Returns:
            bool: True if path is valid
        """
        try:
            if not image_path:
                return False
            
            # Convert to absolute path if needed
            abs_path = os.path.abspath(image_path) if not os.path.isabs(image_path) else image_path
            
            # Check if file exists
            return os.path.isfile(abs_path)
            
        except Exception as e:
            logger.error(f"Error validating image path {image_path}: {e}")
            return False
    
    def _normalize_image_path(self, image_path: str) -> str:
        """
        Normalize image path for frontend compatibility.
        
        Args:
            image_path: Original image path
            
        Returns:
            str: Normalized path
        """
        try:
            # Convert to absolute path
            abs_path = os.path.abspath(image_path) if not os.path.isabs(image_path) else image_path
            
            # Normalize path separators for frontend
            normalized_path = abs_path.replace('\\', '/')
            
            return normalized_path
            
        except Exception as e:
            logger.error(f"Error normalizing image path {image_path}: {e}")
            return image_path
    
    def _update_database(self, presentation_objects: List[InspectionPresentation]) -> bool:
        """
        Update database with presentation images.
        
        Args:
            presentation_objects: List of presentation objects to insert
            
        Returns:
            bool: True if database update was successful
        """
        try:
            with self.camera.db_handler.Session() as session:
                session.begin()
                
                try:
                    # Clear existing presentation data for this inspection
                    session.query(InspectionPresentation).filter(
                        InspectionPresentation.inspection_id == self.inspection_id
                    ).delete(synchronize_session=False)
                    
                    # Insert new presentation objects
                    session.bulk_save_objects(presentation_objects)
                    session.commit()
                    
                    logger.info(f"Successfully updated database with {len(presentation_objects)} presentation images")
                    return True
                    
                except Exception as db_error:
                    session.rollback()
                    logger.error(f"Database transaction failed: {db_error}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error updating database: {e}")
            return False
    
    def _update_camera_results(self) -> None:
        """Update camera's last inspection results with presentation data."""
        try:
            if (self.camera.last_inspection_results and 
                self.camera.last_inspection_results.get("inspection_id") == self.inspection_id):
                
                # Prepare presentation images data for API
                presentation_images_data = [
                    {
                        "inspection_id": self.inspection_id,
                        "group_name": obj.group_name,
                        "image_path": obj.image_path
                    }
                    for obj in self.presentation_objects
                ]
                
                # Update camera results
                self.camera.last_inspection_results.update({
                    "presentation_ready": True,
                    "presentation_images": presentation_images_data
                })
                
                logger.info(f"Updated camera results with {len(presentation_images_data)} presentation images")
                
        except Exception as e:
            logger.error(f"Error updating camera results: {e}")
    
    def _create_consolidation_result(self, success: bool, reason: str = None) -> Dict[str, Any]:
        """
        Create consolidation result dictionary.
        
        Args:
            success: Whether consolidation was successful
            reason: Reason for failure (if applicable)
            
        Returns:
            Dict[str, Any]: Consolidation result
        """
        result = {
            'success': success,
            'inspection_id': self.inspection_id,
            'timestamp': datetime.now().isoformat(),
            'performance_metrics': self.performance_metrics
        }
        
        if not success and reason:
            result['failure_reason'] = reason
        
        if success:
            result.update({
                'total_groups': len(self.group_results),
                'successful_selections': len(self.selected_images),
                'presentation_objects_created': len(self.presentation_objects)
            })
        
        return result
    
    def get_consolidation_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the consolidation process.
        
        Returns:
            Dict[str, Any]: Consolidation summary
        """
        try:
            with self._lock:
                return {
                    'inspection_id': self.inspection_id,
                    'consolidation_complete': self.consolidation_complete,
                    'total_groups': len(self.group_results),
                    'successful_selections': len(self.selected_images),
                    'group_classifications': {
                        group_name: analysis.dominant_classification.value
                        for group_name, analysis in self.group_results.items()
                    },
                    'selected_images': {
                        group_name: {
                            'image_no': image.image_no,
                            'classification': image.classification.value,
                            'knot_count': image.knot_count,
                            'max_knot_size': image.max_knot_size
                        }
                        for group_name, image in self.selected_images.items()
                    },
                    'performance_metrics': self.performance_metrics
                }
                
        except Exception as e:
            logger.error(f"Error creating consolidation summary: {e}")
            return {'error': str(e)}
