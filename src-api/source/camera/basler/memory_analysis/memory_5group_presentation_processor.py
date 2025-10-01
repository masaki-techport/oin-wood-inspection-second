"""
Memory 5-Group Presentation Processor for memory analysis system.

This module provides 5-group presentation image selection using pre-analyzed results
from the memory analysis system, implementing the same logic as the parallel system
but optimized for memory-based analysis results.
"""

import os
import time
import logging
import threading
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .analysis_queue import AnalysisResult
from .memory_group_distributor import MemoryGroupDistributor
from ..parallel.defect_classification_engine import DefectAnalysis, GroupDefectAnalysis, DefectClassification
from ..parallel.presentation_image_selector import PresentationImageSelector

# Import database components
from db.engine import SessionLocal
from db.inspection_presentation import InspectionPresentation

logger = logging.getLogger('BaslerCamera.Memory5GroupPresentationProcessor')

@dataclass
class GroupPresentationResult:
    """Result of presentation image selection for a group."""
    group_name: str
    selected_image_path: str
    selected_image_no: int
    classification: str
    confidence_score: float
    defect_count: int
    max_defect_length: float
    selection_reason: str

class Memory5GroupPresentationProcessor:
    """
    Memory-aware 5-group presentation processor.
    
    Implements the same presentation selection logic as the parallel system
    but uses pre-analyzed results from memory analysis instead of real-time analysis.
    """
    
    def __init__(self, camera_instance):
        """
        Initialize the memory 5-group presentation processor.
        
        Args:
            camera_instance: Reference to the parent BaslerCamera object
        """
        self.camera = camera_instance
        self.enabled = True
        
        # Initialize components
        self.group_distributor = MemoryGroupDistributor()
        self.presentation_selector = PresentationImageSelector()
        
        # Processing state
        self._lock = threading.Lock()
        self.current_inspection_id = None
        self.processing_active = False
        
        # Performance tracking
        self.processing_metrics = {}
        
        logger.info("Memory 5-group presentation processor initialized")
    
    def process_5group_presentation_memory_aware(self, inspection_id: int, 
                                               image_paths: List[str]) -> Dict[str, Any]:
        """
        Process 5-group presentation selection using memory analysis results.
        
        Args:
            inspection_id: Inspection ID to associate images with
            image_paths: List of image file paths to process
            
        Returns:
            Dict[str, Any]: Processing results and metrics
        """
        if not self.enabled:
            logger.warning("Memory 5-group presentation processing is disabled")
            return self._fallback_to_sequential(inspection_id, image_paths)
        
        processing_start = time.time()
        
        try:
            with self._lock:
                self.current_inspection_id = inspection_id
                self.processing_active = True
            
            logger.info(f"Starting memory-aware 5-group presentation processing for inspection {inspection_id}")
            logger.info(f"Processing {len(image_paths)} images")
            
            # Distribute images into 5 groups (A-E)
            distributed_images = self.group_distributor.distribute_images_5_groups(image_paths)
            
            # Validate distribution
            if not self.group_distributor.validate_distribution(image_paths, distributed_images):
                logger.error("Image distribution validation failed")
                return self._fallback_to_sequential(inspection_id, image_paths)
            
            # Process each group using memory analysis results
            group_results = self._process_groups_memory_aware(inspection_id, distributed_images)
            
            # Calculate final metrics
            processing_time = time.time() - processing_start
            self.processing_metrics = {
                'total_processing_time': processing_time,
                'groups_processed': len(group_results),
                'successful_groups': len([r for r in group_results if r.get('success', False)]),
                'total_images': len(image_paths)
            }
            
            logger.info(f"Memory-aware 5-group presentation processing completed in {processing_time:.3f}s")
            
            return {
                'success': True,
                'inspection_id': inspection_id,
                'processing_metrics': self.processing_metrics,
                'group_results': group_results,
                'distributed_images': distributed_images
            }
            
        except Exception as e:
            logger.error(f"Error in memory-aware 5-group presentation processing: {e}")
            logger.info("Attempting fallback to sequential processing")
            
            # Try fallback processing
            try:
                fallback_result = self._fallback_to_sequential(inspection_id, image_paths)
                if fallback_result.get('success'):
                    logger.info("Fallback processing completed successfully")
                    return fallback_result
                else:
                    logger.error("Fallback processing also failed")
            except Exception as fallback_error:
                logger.error(f"Fallback processing failed: {fallback_error}")
            
            return {
                'success': False,
                'inspection_id': inspection_id,
                'error': str(e)
            }
        finally:
            with self._lock:
                self.processing_active = False
    
    def _process_groups_memory_aware(self, inspection_id: int, 
                                   distributed_images: Dict[str, List[str]]) -> List[Dict[str, Any]]:
        """
        Process presentation selection for each group using memory analysis results.
        
        Args:
            inspection_id: Inspection ID
            distributed_images: Dictionary mapping group names to image paths
            
        Returns:
            List[Dict[str, Any]]: Results from all groups
        """
        results = []
        
        for group_name, image_paths in distributed_images.items():
            if not image_paths:
                logger.debug(f"Group {group_name} has no images, skipping")
                continue
            
            try:
                result = self._process_single_group_memory_aware(inspection_id, group_name, image_paths)
                results.append(result)
                logger.info(f"Group {group_name} presentation processing completed")
            except Exception as e:
                logger.error(f"Group {group_name} presentation processing failed: {e}")
                results.append({
                    'group_name': group_name,
                    'success': False,
                    'error': str(e)
                })
        
        return results
    
    def _process_single_group_memory_aware(self, inspection_id: int, group_name: str, 
                                         image_paths: List[str]) -> Dict[str, Any]:
        """
        Process presentation selection for a single group using memory analysis results.
        
        Args:
            inspection_id: Inspection ID
            group_name: Group name (A-E)
            image_paths: List of image paths in this group
            
        Returns:
            Dict[str, Any]: Processing result for this group
        """
        group_start = time.time()
        
        try:
            logger.info(f"Processing group {group_name} with {len(image_paths)} images using memory analysis results")
            
            # Get analysis results from memory for each image in the group
            analysis_results = []
            for image_path in image_paths:
                image_no = self._extract_image_no_from_path(image_path)
                if image_no is None:
                    logger.warning(f"Could not extract image_no from path: {image_path}")
                    continue
                
                # Get analysis result from memory
                analysis_result = self._get_analysis_result_from_memory(image_no)
                if analysis_result:
                    analysis_results.append(analysis_result)
                else:
                    logger.debug(f"No analysis result found in memory for image {image_no} (may not be analyzed yet)")
            
            if not analysis_results:
                logger.warning(f"Group {group_name}: No analysis results found in memory")
                return {
                    'group_name': group_name,
                    'success': False,
                    'reason': 'no_analysis_results'
                }
            
            # Convert analysis results to defect analyses for presentation selection
            defect_analyses = []
            for analysis_result in analysis_results:
                defect_analysis = self._convert_memory_result_to_defect_analysis(analysis_result)
                if defect_analysis:
                    defect_analyses.append(defect_analysis)
            
            if not defect_analyses:
                logger.warning(f"Group {group_name}: No valid defect analyses")
                return {
                    'group_name': group_name,
                    'success': False,
                    'reason': 'no_defect_analyses'
                }
            
            # Create group defect analysis
            group_defect_analysis = self._create_group_defect_analysis(group_name, defect_analyses)
            
            # Select presentation image using the same logic as parallel system
            selected_image = self.presentation_selector.select_presentation_image(group_defect_analysis)
            
            # Save presentation image to database
            if selected_image:
                self._save_presentation_image(inspection_id, group_name, selected_image)
            
            # Calculate processing time
            group_time = time.time() - group_start
            
            logger.info(f"Group {group_name} completed (memory-aware) in {group_time:.3f}s: "
                       f"selected image {selected_image.image_no if selected_image else 'None'}")
            
            return {
                'group_name': group_name,
                'success': True,
                'processing_time': group_time,
                'images_analyzed': len(analysis_results),
                'logic_type': 'memory_aware',
                'selected_image_no': selected_image.image_no if selected_image else None,
                'selected_classification': selected_image.classification.value if selected_image else None,
                'total_defects': sum(da.total_defect_count for da in defect_analyses),
                'max_defect_length': max((da.max_knot_size for da in defect_analyses), default=0.0)
            }
            
        except Exception as e:
            group_time = time.time() - group_start
            logger.error(f"Error processing group {group_name}: {e}")
            return {
                'group_name': group_name,
                'success': False,
                'processing_time': group_time,
                'error': str(e)
            }
    
    def _get_analysis_result_from_memory(self, image_no: int) -> Optional[AnalysisResult]:
        """
        Get analysis result from memory storage.
        
        Args:
            image_no: Image number to look up
            
        Returns:
            Optional[AnalysisResult]: Analysis result from memory or None
        """
        try:
            if hasattr(self.camera, 'buffer_manager') and self.camera.buffer_manager:
                if hasattr(self.camera.buffer_manager, 'results_storage'):
                    result = self.camera.buffer_manager.results_storage.get_result_by_image_index(image_no)
                    if result and not getattr(result, 'is_discarded', False):
                        return result
                
                if hasattr(self.camera.buffer_manager, 'result_cache'):
                    cache_key = f"image_{image_no}"
                    result = self.camera.buffer_manager.result_cache.get(cache_key)
                    if result and not getattr(result, 'is_discarded', False):
                        return result
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting analysis result from memory for image {image_no}: {e}")
            return None
    
    def _convert_memory_result_to_defect_analysis(self, analysis_result: AnalysisResult) -> Optional[DefectAnalysis]:
        """
        Convert AnalysisResult from memory to DefectAnalysis for presentation selection.
        
        Args:
            analysis_result: Analysis result from memory
            
        Returns:
            Optional[DefectAnalysis]: Converted defect analysis or None
        """
        try:
            if not analysis_result or not hasattr(analysis_result, 'detections'):
                return None
            
            # Determine classification based on detections
            classification = self._determine_classification_from_detections(analysis_result.detections)
            
            # Count knots and calculate max knot size
            knot_count = 0
            max_knot_size = 0.0
            total_defect_count = len(analysis_result.detections)
            
            for detection in analysis_result.detections:
                class_id = detection.get('class_id', -1)
                if class_id in [2, 3, 4, 5]:  # knot types
                    knot_count += 1
                    length = detection.get('length', 0.0)
                    max_knot_size = max(max_knot_size, length)
            
            # Check for other defect types
            has_discoloration = any(d.get('class_id') == 0 for d in analysis_result.detections)
            has_hole = any(d.get('class_id') == 1 for d in analysis_result.detections)
            
            # Use the image path from analysis result (should be actual disk path after event processor fix)
            image_path = getattr(analysis_result, 'image_path', '')
            
            return DefectAnalysis(
                image_path=image_path,
                image_no=getattr(analysis_result, 'image_index', 0),
                classification=classification,
                knot_count=knot_count,
                max_knot_size=max_knot_size,
                total_defect_count=total_defect_count,
                has_discoloration=has_discoloration,
                has_hole=has_hole,
                defect_details=analysis_result.detections
            )
            
        except Exception as e:
            logger.error(f"Error converting memory result to defect analysis: {e}")
            return None
    
    def _determine_classification_from_detections(self, detections: List[Dict[str, Any]]) -> DefectClassification:
        """
        Determine defect classification from detections.
        
        Args:
            detections: List of detection dictionaries
            
        Returns:
            DefectClassification: Classification based on detections
        """
        try:
            # Check for large knots (>= 10mm) - 節あり
            for detection in detections:
                class_id = detection.get('class_id', -1)
                if class_id in [2, 3, 4, 5]:  # knot types
                    length = detection.get('length', 0.0)
                    if length >= 10.0:
                        return DefectClassification.FUSHIARI
            
            # Check for small knots (< 10mm) - こぶし
            for detection in detections:
                class_id = detection.get('class_id', -1)
                if class_id in [2, 3, 4, 5]:  # knot types
                    return DefectClassification.KOBUSHI
            
            # No knots - 無欠点
            return DefectClassification.MUKETSUTON
            
        except Exception as e:
            logger.error(f"Error determining classification: {e}")
            return DefectClassification.MUKETSUTON
    
    def _create_group_defect_analysis(self, group_name: str, 
                                    defect_analyses: List[DefectAnalysis]) -> GroupDefectAnalysis:
        """
        Create group defect analysis from individual defect analyses.
        
        Args:
            group_name: Group name
            defect_analyses: List of defect analyses
            
        Returns:
            GroupDefectAnalysis: Group analysis result
        """
        try:
            # Determine dominant classification based on priority
            # Priority: 節あり > こぶし > 無欠点
            dominant_classification = DefectClassification.MUKETSUTON
            highest_priority = 0
            
            classification_priority = {
                DefectClassification.FUSHIARI: 3,    # 節あり (highest)
                DefectClassification.KOBUSHI: 2,     # こぶし (medium)
                DefectClassification.MUKETSUTON: 1   # 無欠点 (lowest)
            }
            
            for analysis in defect_analyses:
                priority = classification_priority.get(analysis.classification, 1)
                if priority > highest_priority:
                    highest_priority = priority
                    dominant_classification = analysis.classification
            
            return GroupDefectAnalysis(
                group_name=group_name,
                image_analyses=defect_analyses,
                dominant_classification=dominant_classification,
                selected_image=None  # Will be set by the selector
            )
            
        except Exception as e:
            logger.error(f"Error creating group defect analysis: {e}")
            return GroupDefectAnalysis(
                group_name=group_name,
                image_analyses=defect_analyses,
                dominant_classification=DefectClassification.MUKETSUTON,
                selected_image=None
            )
    
    def _save_presentation_image(self, inspection_id: int, group_name: str, 
                               selected_image: DefectAnalysis) -> None:
        """
        Save presentation image to database.
        
        Args:
            inspection_id: Inspection ID
            group_name: Group name
            selected_image: Selected image analysis
        """
        try:
            with SessionLocal() as session:
                try:
                    # Clear any existing presentation images for this inspection and group
                    session.query(InspectionPresentation).filter(
                        InspectionPresentation.inspection_id == inspection_id,
                        InspectionPresentation.group_name == group_name
                    ).delete()
                    
                    # Create new presentation image record
                    presentation_image = InspectionPresentation(
                        inspection_id=inspection_id,
                        group_name=group_name,
                        image_path=selected_image.image_path
                    )
                    
                    session.add(presentation_image)
                    session.commit()
                    
                    logger.info(f"Saved presentation image for group {group_name}: "
                               f"image {selected_image.image_no}")
                    
                except Exception as e:
                    session.rollback()
                    logger.error(f"Error saving presentation image: {e}")
                    raise
                    
        except Exception as e:
            logger.error(f"Error in _save_presentation_image: {e}")
            raise
    
    def _extract_image_no_from_path(self, image_path: str) -> Optional[int]:
        """
        Extract image_no from image path using "No_????" pattern.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Optional[int]: Extracted image number or None if not found
        """
        import re
        
        if not image_path:
            return None
        
        try:
            # Look for "No_" followed by digits in the path
            matches = re.findall(r'No_(\d+)', image_path)
            if matches:
                # Use the last match in case there are multiple "No_" patterns
                image_no_str = matches[-1]
                image_no = int(image_no_str)
                return image_no
            else:
                return None
        except Exception as e:
            logger.error(f"Error extracting image_no from path {image_path}: {e}")
            return None
    
    def _fallback_to_sequential(self, inspection_id: int, image_paths: List[str]) -> Dict[str, Any]:
        """
        Fallback to sequential processing when memory-aware processing fails.
        
        Args:
            inspection_id: Inspection ID
            image_paths: List of image paths
            
        Returns:
            Dict[str, Any]: Fallback processing result
        """
        try:
            logger.warning("Falling back to sequential presentation processing")
            
            # Use the existing memory presentation processor as fallback
            if hasattr(self.camera, 'memory_presentation_processor'):
                distributed_images = self.group_distributor.distribute_images_5_groups(image_paths)
                result = self.camera.memory_presentation_processor.process_presentation_images_memory_aware(
                    inspection_id, distributed_images
                )
                return {
                    'success': result.get('success', False),
                    'inspection_id': inspection_id,
                    'fallback_used': True,
                    'groups_processed': len(distributed_images),
                    'total_images': len(image_paths)
                }
            else:
                logger.error("No fallback presentation processor available")
                return {
                    'success': False,
                    'inspection_id': inspection_id,
                    'error': 'no_fallback_available'
                }
                
        except Exception as e:
            logger.error(f"Error in fallback processing: {e}")
            return {
                'success': False,
                'inspection_id': inspection_id,
                'error': f'fallback_failed: {e}'
            }
    
    def get_processing_status(self) -> Dict[str, Any]:
        """
        Get current processing status.
        
        Returns:
            Dict[str, Any]: Processing status information
        """
        with self._lock:
            return {
                'enabled': self.enabled,
                'processing_active': self.processing_active,
                'current_inspection_id': self.current_inspection_id,
                'processing_metrics': self.processing_metrics
            }
