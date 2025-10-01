"""
Memory-based Presentation Processor for BaslerCamera.

This module provides memory-aware presentation image selection using pre-analyzed
results from the memory analysis system, replacing the parallel analysis approach
while maintaining the same group splitting logic (A-E groups).
"""

import os
import time
import logging
import threading
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from .analysis_queue import AnalysisResult
from .results_storage import MemoryResultsStorage
from .result_cache import AnalysisResultCache
from ..parallel.defect_classification_engine import DefectAnalysis, GroupDefectAnalysis, DefectClassification

# Import database components
from db.engine import SessionLocal
from db.inspection_presentation import InspectionPresentation

logger = logging.getLogger('BaslerCamera.MemoryPresentationProcessor')

@dataclass
class GroupAnalysis:
    """Analysis result for a single group."""
    group_name: str
    image_paths: List[str]
    analysis_results: List[AnalysisResult]
    selected_image_path: Optional[str] = None
    selected_image_no: Optional[int] = None
    dominant_classification: str = "無欠点"
    total_defects: int = 0
    max_defect_length: float = 0.0
    has_high_confidence: bool = False

@dataclass
class PresentationSelectionResult:
    """Result of presentation image selection."""
    group_name: str
    selected_image_path: str
    selected_image_no: int
    classification: str
    confidence_score: float
    defect_count: int
    max_defect_length: float
    selection_reason: str

class MemoryPresentationProcessor:
    """
    Memory-aware presentation processor that uses pre-analyzed results
    from the memory analysis system to select presentation images.
    """
    
    def __init__(self, camera_instance):
        """
        Initialize the memory presentation processor.
        
        Args:
            camera_instance: Reference to the parent BaslerCamera object
        """
        self.camera = camera_instance
        self.enabled = True
        
        # Get memory analysis components
        self.results_storage = None
        self.result_cache = None
        self._initialize_memory_components()
        
        # Processing state
        self._lock = threading.Lock()
        self.current_inspection_id = None
        self.processing_active = False
        
        # Performance tracking
        self.processing_metrics = {}
        
        logger.info("Memory presentation processor initialized")
    
    def _initialize_memory_components(self):
        """Initialize memory analysis components."""
        try:
            if hasattr(self.camera, 'buffer_manager') and self.camera.buffer_manager:
                if hasattr(self.camera.buffer_manager, 'results_storage'):
                    self.results_storage = self.camera.buffer_manager.results_storage
                if hasattr(self.camera.buffer_manager, 'result_cache'):
                    self.result_cache = self.camera.buffer_manager.result_cache
                    
                logger.info("Memory components initialized successfully")
            else:
                logger.warning("Buffer manager not available for memory components")
        except Exception as e:
            logger.error(f"Error initializing memory components: {e}")
    
    def process_presentation_images_memory_aware(self, inspection_id: int, 
                                               distributed_images: Dict[str, List[str]]) -> Dict[str, Any]:
        """
        Process presentation images using memory-aware analysis.
        
        This replaces the parallel presentation processing by using pre-analyzed
        results from the memory analysis system.
        
        Args:
            inspection_id: Inspection ID to associate images with
            distributed_images: Dictionary mapping group names (A-E) to image paths
            
        Returns:
            Dict[str, Any]: Processing results and metrics
        """
        if not self.enabled:
            logger.warning("Memory presentation processing is disabled")
            return self._fallback_to_sequential(inspection_id, distributed_images)
        
        processing_start = time.time()
        
        # Start timing measurement for presentation processing
        timing_collector = getattr(self.camera, 'timing_collector', None)
        presentation_measurement_id = None
        if timing_collector:
            presentation_measurement_id = timing_collector.start_measurement(
                "presentation_processing", 
                {"inspection_id": inspection_id, "group_count": len(distributed_images)}
            )
        
        try:
            with self._lock:
                self.current_inspection_id = inspection_id
                self.processing_active = True
            
            logger.info(f"Starting memory-aware presentation processing for inspection {inspection_id}")
            logger.info(f"Processing {len(distributed_images)} groups with "
                       f"{sum(len(paths) for paths in distributed_images.values())} total images")
            
            # Process groups using memory analysis
            group_results = self._process_groups_memory_aware(inspection_id, distributed_images)
            
            # Calculate final metrics
            processing_time = time.time() - processing_start
            self.processing_metrics = {
                'total_processing_time': processing_time,
                'groups_processed': len(group_results),
                'successful_groups': len([r for r in group_results if r.get('success', False)]),
                'memory_analysis_used': True
            }
            
            logger.info(f"Memory-aware presentation processing completed in {processing_time:.3f}s")
            
            return {
                'success': True,
                'inspection_id': inspection_id,
                'processing_metrics': self.processing_metrics,
                'group_results': group_results,
                'analysis_type': 'memory_aware'
            }
            
        except Exception as e:
            logger.error(f"Error in memory-aware presentation processing: {e}")
            logger.info("Attempting fallback to sequential processing")
            
            try:
                fallback_result = self._fallback_to_sequential(inspection_id, distributed_images)
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
            
            # End timing measurement for presentation processing
            if timing_collector and presentation_measurement_id:
                timing_collector.end_measurement("presentation_processing", presentation_measurement_id)
    
    def _process_groups_memory_aware(self, inspection_id: int, 
                                   distributed_images: Dict[str, List[str]]) -> List[Dict[str, Any]]:
        """
        Process presentation selection for each group using memory analysis.
        
        Args:
            inspection_id: Inspection ID
            distributed_images: Dictionary mapping group names to image paths
            
        Returns:
            List[Dict[str, Any]]: Results from all groups
        """
        results = []
        
        # Start timing measurement for group processing
        timing_collector = getattr(self.camera, 'timing_collector', None)
        group_processing_measurement_id = None
        if timing_collector:
            group_processing_measurement_id = timing_collector.start_measurement(
                "group_processing", 
                {"inspection_id": inspection_id, "group_count": len(distributed_images)}
            )
        
        for group_name, image_paths in distributed_images.items():
            if not image_paths:
                logger.debug(f"Group {group_name} has no images, skipping")
                continue
                
            group_start = time.time()
            
            try:
                logger.info(f"Processing group {group_name} with {len(image_paths)} images using memory analysis")
                
                # Get analysis results for this group's images
                group_analysis = self._analyze_group_with_memory(group_name, image_paths)
                
                # Select best presentation image
                selection_result = self._select_presentation_image(group_analysis)
                
                # Save presentation image to database
                if selection_result:
                    self._save_presentation_image(inspection_id, selection_result)
                
                group_time = time.time() - group_start
                
                result = {
                    'group_name': group_name,
                    'success': True,
                    'processing_time': group_time,
                    'images_analyzed': len(group_analysis.analysis_results),
                    'logic_type': 'memory_aware',
                    'selected_image_no': selection_result.selected_image_no if selection_result else None,
                    'selected_classification': selection_result.classification if selection_result else None,
                    'selection_reason': selection_result.selection_reason if selection_result else None,
                    'total_defects': group_analysis.total_defects,
                    'max_defect_length': group_analysis.max_defect_length,
                    'has_high_confidence': group_analysis.has_high_confidence
                }
                
                results.append(result)
                logger.info(f"Group {group_name} memory analysis completed in {group_time:.3f}s: "
                           f"selected image {selection_result.selected_image_no if selection_result else 'None'}")
                
            except Exception as e:
                group_time = time.time() - group_start
                logger.error(f"Error processing group {group_name}: {e}")
                results.append({
                    'group_name': group_name,
                    'success': False,
                    'processing_time': group_time,
                    'error': str(e)
                })
        
        # End timing measurement for group processing
        if timing_collector and group_processing_measurement_id:
            timing_collector.end_measurement("group_processing", group_processing_measurement_id)
        
        return results
    
    def _analyze_group_with_memory(self, group_name: str, image_paths: List[str]) -> GroupAnalysis:
        """
        Analyze a group using pre-analyzed results from memory.
        
        Args:
            group_name: Group name (A-E)
            image_paths: List of image paths in this group
            
        Returns:
            GroupAnalysis: Analysis result for the group
        """
        analysis_results = []
        total_defects = 0
        max_defect_length = 0.0
        has_high_confidence = False
        
        for image_path in image_paths:
            # Extract image number from path
            image_no = self._extract_image_no_from_path(image_path)
            if image_no is None:
                logger.warning(f"Could not extract image_no from path: {image_path}")
                continue
            
            # Try to get pre-analyzed result from memory
            analysis_result = self._get_analysis_result_from_memory(image_no)
            
            if analysis_result:
                analysis_results.append(analysis_result)
                
                # Aggregate statistics
                if analysis_result.detections:
                    total_defects += len(analysis_result.detections)
                    max_defect_length = max(max_defect_length, analysis_result.max_length)
                
                if analysis_result.confidence_above_threshold:
                    has_high_confidence = True
                    
                logger.debug(f"Found memory analysis for image {image_no}: "
                           f"{analysis_result.inspection_result}, {len(analysis_result.detections)} defects")
            else:
                logger.warning(f"No memory analysis found for image {image_no}, will use fallback")
        
        # Determine dominant classification
        dominant_classification = self._determine_dominant_classification(analysis_results)
        
        return GroupAnalysis(
            group_name=group_name,
            image_paths=image_paths,
            analysis_results=analysis_results,
            dominant_classification=dominant_classification,
            total_defects=total_defects,
            max_defect_length=max_defect_length,
            has_high_confidence=has_high_confidence
        )
    
    def _get_analysis_result_from_memory(self, image_no: int) -> Optional[AnalysisResult]:
        """
        Get analysis result from memory storage.
        
        Args:
            image_no: Image number to look up
            
        Returns:
            Optional[AnalysisResult]: Analysis result if found, None otherwise
        """
        try:
            # Try result cache first (faster)
            if self.result_cache:
                cache_key = f"image_{image_no}"
                result = self.result_cache.get(cache_key)
                if result:
                    return result
            
            # Try results storage
            if self.results_storage:
                result = self.results_storage.get_result_by_image_index(image_no)
                if result:
                    return result
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting analysis result from memory for image {image_no}: {e}")
            return None
    
    def _determine_dominant_classification(self, analysis_results: List[AnalysisResult]) -> str:
        """
        Determine the dominant classification for a group.
        
        Args:
            analysis_results: List of analysis results
            
        Returns:
            str: Dominant classification
        """
        if not analysis_results:
            return "無欠点"
        
        # Count classifications
        classifications = {}
        for result in analysis_results:
            classification = result.inspection_result
            classifications[classification] = classifications.get(classification, 0) + 1
        
        # Return most common classification
        if classifications:
            return max(classifications, key=classifications.get)
        
        return "無欠点"
    
    def _select_presentation_image(self, group_analysis: GroupAnalysis) -> Optional[PresentationSelectionResult]:
        """
        Select the best presentation image for a group using sophisticated selection logic.
        
        This implements the same logic as presentation_image_selector.py but uses
        pre-analyzed results from memory instead of real-time analysis.
        
        Args:
            group_analysis: Group analysis result
            
        Returns:
            Optional[PresentationSelectionResult]: Selected presentation image
        """
        if not group_analysis.analysis_results:
            logger.warning(f"No analysis results for group {group_analysis.group_name}")
            return None
        
        # Convert memory analysis results to DefectAnalysis format
        defect_analyses = []
        for result in group_analysis.analysis_results:
            defect_analysis = self._convert_memory_result_to_defect_analysis(result)
            if defect_analysis:
                defect_analyses.append(defect_analysis)
        
        if not defect_analyses:
            logger.warning(f"No valid defect analyses for group {group_analysis.group_name}")
            return None
        
        # Determine dominant classification
        dominant_classification = self._determine_dominant_classification_from_defect_analyses(defect_analyses)
        
        # Create GroupDefectAnalysis for selection logic
        group_defect_analysis = GroupDefectAnalysis(
            group_name=group_analysis.group_name,
            image_analyses=defect_analyses,
            dominant_classification=dominant_classification,
            selected_image=None
        )
        
        # Use sophisticated selection logic
        selected_defect_analysis = self._select_using_sophisticated_logic(group_defect_analysis)
        
        if not selected_defect_analysis:
            logger.warning(f"No image selected for group {group_analysis.group_name}")
            return None
        
        # Find corresponding image path
        selected_image_path = None
        for path in group_analysis.image_paths:
            if self._extract_image_no_from_path(path) == selected_defect_analysis.image_no:
                selected_image_path = path
                break
        
        if not selected_image_path:
            logger.warning(f"Could not find image path for selected image {selected_defect_analysis.image_no}")
            return None
        
        return PresentationSelectionResult(
            group_name=group_analysis.group_name,
            selected_image_path=selected_image_path,
            selected_image_no=selected_defect_analysis.image_no,
            classification=selected_defect_analysis.classification.value,
            confidence_score=selected_defect_analysis.total_defect_count,
            defect_count=selected_defect_analysis.total_defect_count,
            max_defect_length=selected_defect_analysis.max_knot_size,
            selection_reason=f"Selected using {dominant_classification.value} logic"
        )
    
    def _save_presentation_image(self, inspection_id: int, selection_result: PresentationSelectionResult) -> None:
        """
        Save presentation image to database.
        
        Args:
            inspection_id: Inspection ID
            selection_result: Selected presentation image result
        """
        try:
            with SessionLocal() as session:
                try:
                    # Clear any existing presentation images for this inspection and group
                    session.query(InspectionPresentation).filter(
                        InspectionPresentation.inspection_id == inspection_id,
                        InspectionPresentation.group_name == selection_result.group_name
                    ).delete()
                    
                    # Create new presentation image record
                    presentation_image = InspectionPresentation(
                        inspection_id=inspection_id,
                        group_name=selection_result.group_name,
                        image_path=selection_result.selected_image_path
                    )
                    
                    session.add(presentation_image)
                    session.commit()
                    
                    logger.info(f"Saved presentation image for group {selection_result.group_name}: "
                               f"image {selection_result.selected_image_no}")
                    
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
    
    def _fallback_to_sequential(self, inspection_id: int,
                              distributed_images: Dict[str, List[str]]) -> Dict[str, Any]:
        """
        Fallback to sequential processing when memory analysis fails.
        
        Args:
            inspection_id: Inspection ID
            distributed_images: Dictionary mapping group names to image paths
            
        Returns:
            Dict[str, Any]: Fallback processing result
        """
        try:
            logger.warning("Falling back to sequential presentation processing")
            
            # Use the camera's existing presentation processor if available
            if hasattr(self.camera, 'presentation_processor'):
                # Call the existing sequential processor
                result = self.camera.presentation_processor.save_presentation_images(inspection_id)
                return {
                    'success': True,
                    'inspection_id': inspection_id,
                    'fallback_used': True,
                    'groups_processed': len(distributed_images),
                    'total_images': sum(len(paths) for paths in distributed_images.values())
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
                'processing_metrics': self.processing_metrics,
                'memory_components_available': {
                    'results_storage': self.results_storage is not None,
                    'result_cache': self.result_cache is not None
                }
            }
    
    def _convert_memory_result_to_defect_analysis(self, result: AnalysisResult) -> Optional[DefectAnalysis]:
        """
        Convert memory analysis result to DefectAnalysis format.
        
        Args:
            result: Memory analysis result
            
        Returns:
            Optional[DefectAnalysis]: Converted defect analysis
        """
        try:
            # Determine classification based on inspection result and detections
            if result.inspection_result == "欠点あり" and result.detections:
                # Check if it's 節あり (large knots >= 10mm) or こぶし (small knots < 10mm)
                has_large_knots = any(d.get('length', 0) >= 10 for d in result.detections)
                if has_large_knots:
                    classification = DefectClassification.FUSHIARI
                else:
                    classification = DefectClassification.KOBUSHI
            else:
                classification = DefectClassification.MUKETSUTON
            
            # Count knots and calculate max knot size
            knot_count = len([d for d in result.detections if d.get('error_type') in {2, 3, 4, 5}])
            max_knot_size = max([d.get('length', 0) for d in result.detections], default=0.0)
            
            # Check for holes and discoloration
            has_hole = any(d.get('error_type') == 4 for d in result.detections)
            has_discoloration = any(d.get('error_type') == 5 for d in result.detections)
            
            return DefectAnalysis(
                image_path=result.image_path,  # Should be actual disk path after event processor fix
                image_no=result.image_index,
                classification=classification,
                knot_count=knot_count,
                max_knot_size=max_knot_size,
                total_defect_count=len(result.detections),
                has_discoloration=has_discoloration,
                has_hole=has_hole,
                defect_details=result.detections
            )
            
        except Exception as e:
            logger.error(f"Error converting memory result to defect analysis: {e}")
            return None
    
    def _determine_dominant_classification_from_defect_analyses(self, defect_analyses: List[DefectAnalysis]) -> DefectClassification:
        """
        Determine the dominant classification from defect analyses.
        
        Args:
            defect_analyses: List of defect analyses
            
        Returns:
            DefectClassification: Dominant classification
        """
        if not defect_analyses:
            return DefectClassification.MUKETSUTON
        
        # Count classifications
        classifications = {}
        for analysis in defect_analyses:
            classification = analysis.classification
            classifications[classification] = classifications.get(classification, 0) + 1
        
        # Return most common classification
        if classifications:
            return max(classifications, key=classifications.get)
        
        return DefectClassification.MUKETSUTON
    
    def _select_using_sophisticated_logic(self, group_defect_analysis: GroupDefectAnalysis) -> Optional[DefectAnalysis]:
        """
        Use sophisticated selection logic based on classification.
        
        This implements the same logic as presentation_image_selector.py:
        - 節あり: Select by defect count (最も数が多いもの)
        - こぶし: Select by knot size (サイズ)
        - 無欠点: Select middle image of group
        
        Args:
            group_defect_analysis: Group defect analysis
            
        Returns:
            Optional[DefectAnalysis]: Selected image analysis
        """
        try:
            if not group_defect_analysis.image_analyses:
                return None
            
            # Select based on dominant classification
            if group_defect_analysis.dominant_classification == DefectClassification.FUSHIARI:
                return self._select_fushiari_image(group_defect_analysis)
            elif group_defect_analysis.dominant_classification == DefectClassification.KOBUSHI:
                return self._select_kobushi_image(group_defect_analysis)
            else:  # MUKETSUTON
                return self._select_muketsuton_image(group_defect_analysis)
                
        except Exception as e:
            logger.error(f"Error in sophisticated selection logic: {e}")
            return self._fallback_selection(group_defect_analysis.image_analyses)
    
    def _select_fushiari_image(self, group_defect_analysis: GroupDefectAnalysis) -> Optional[DefectAnalysis]:
        """
        Select 節あり image based on defect count (最も数が多いもの).
        Tie-breaking: 同数の場合初めの一枚 (first image if same count).
        """
        try:
            # Filter images that have 節あり classification
            fushiari_images = [
                analysis for analysis in group_defect_analysis.image_analyses
                if analysis.classification == DefectClassification.FUSHIARI
            ]
            
            if not fushiari_images:
                return self._fallback_selection(group_defect_analysis.image_analyses)
            
            # Sort by image_no to ensure consistent "first image" tie-breaking
            fushiari_images.sort(key=lambda x: x.image_no)
            
            # Find image with most large knots (>= 10mm)
            knot_error_types = {2, 3, 4, 5}
            max_large_knot_count = 0
            selected_image = None
            
            for analysis in fushiari_images:
                # Count large knots (>= 10mm) in this image
                large_knot_count = sum(
                    1 for defect in analysis.defect_details
                    if defect.get('error_type') in knot_error_types and defect.get('length', 0) >= 10
                )
                
                # Select if more large knots, or if same count and this is the first image
                if large_knot_count > max_large_knot_count or (large_knot_count == max_large_knot_count and selected_image is None):
                    max_large_knot_count = large_knot_count
                    selected_image = analysis
            
            if selected_image:
                logger.info(f"Group {group_defect_analysis.group_name}: Selected 節あり image {selected_image.image_no} "
                          f"with {max_large_knot_count} large knots")
            
            return selected_image
            
        except Exception as e:
            logger.error(f"Error selecting 節あり image: {e}")
            return self._fallback_selection(group_defect_analysis.image_analyses)
    
    def _select_kobushi_image(self, group_defect_analysis: GroupDefectAnalysis) -> Optional[DefectAnalysis]:
        """
        Select こぶし image based on knot size (サイズ).
        Tie-breaking: 同数のものは初めの一枚 (first image if same size).
        """
        try:
            # Filter images that have こぶし classification
            kobushi_images = [
                analysis for analysis in group_defect_analysis.image_analyses
                if analysis.classification == DefectClassification.KOBUSHI
            ]
            
            if not kobushi_images:
                return self._fallback_selection(group_defect_analysis.image_analyses)
            
            # Sort by image_no to ensure consistent "first image" tie-breaking
            kobushi_images.sort(key=lambda x: x.image_no)
            
            # Find image with largest knot size
            max_knot_size = 0.0
            selected_image = None
            
            for analysis in kobushi_images:
                # Get the largest knot size in this image (should be < 10mm for こぶし)
                image_max_knot_size = analysis.max_knot_size
                
                # Select if larger knot, or if same size and this is the first image
                if image_max_knot_size > max_knot_size or (image_max_knot_size == max_knot_size and selected_image is None):
                    max_knot_size = image_max_knot_size
                    selected_image = analysis
            
            if selected_image:
                logger.info(f"Group {group_defect_analysis.group_name}: Selected こぶし image {selected_image.image_no} "
                          f"with max knot size {max_knot_size}mm")
            
            return selected_image
            
        except Exception as e:
            logger.error(f"Error selecting こぶし image: {e}")
            return self._fallback_selection(group_defect_analysis.image_analyses)
    
    def _select_muketsuton_image(self, group_defect_analysis: GroupDefectAnalysis) -> Optional[DefectAnalysis]:
        """
        Select 無欠点 image by choosing the middle image of the group.
        For images with no knots, ignore holes and discoloration and select middle image:
        - Even numbers: Select "lower middle" (e.g., 4 images → select image 2)
        - Odd numbers: Select true middle (e.g., 5 images → select image 3)
        """
        try:
            # Filter images that have 無欠点 classification
            muketsuton_images = [
                analysis for analysis in group_defect_analysis.image_analyses
                if analysis.classification == DefectClassification.MUKETSUTON
            ]
            
            if not muketsuton_images:
                return self._fallback_selection(group_defect_analysis.image_analyses)
            
            # Sort by image_no for consistent selection
            muketsuton_images.sort(key=lambda x: x.image_no)
            
            # For 無欠点 cases, select middle image with special handling for even numbers
            num_images = len(muketsuton_images)
            if num_images % 2 == 0:
                # Even number: select (len // 2) - 1 (e.g., 4 images → index 1 → image 2)
                middle_index = (num_images // 2) - 1
            else:
                # Odd number: select len // 2 (e.g., 5 images → index 2 → image 3)
                middle_index = num_images // 2
            
            selected_image = muketsuton_images[middle_index]
            
            # Log the selection with details
            selection_type = "lower middle" if num_images % 2 == 0 else "middle"
            logger.info(f"Group {group_defect_analysis.group_name}: Selected 無欠点 {selection_type} image {selected_image.image_no} "
                      f"from {num_images} images")
            
            return selected_image
            
        except Exception as e:
            logger.error(f"Error selecting 無欠点 image: {e}")
            return self._fallback_selection(group_defect_analysis.image_analyses)
    
    def _fallback_selection(self, image_analyses: List[DefectAnalysis]) -> Optional[DefectAnalysis]:
        """
        Fallback selection when other methods fail.
        Selects the middle image from the sorted list with proper even/odd handling.
        """
        try:
            if not image_analyses:
                return None
            
            # Sort by image_no and select middle image with even/odd handling
            sorted_analyses = sorted(image_analyses, key=lambda x: x.image_no)
            num_images = len(sorted_analyses)
            
            if num_images % 2 == 0:
                # Even number: select (len // 2) - 1 (e.g., 4 images → index 1 → image 2)
                middle_index = (num_images // 2) - 1
            else:
                # Odd number: select len // 2 (e.g., 5 images → index 2 → image 3)
                middle_index = num_images // 2
            
            selected = sorted_analyses[middle_index]
            
            selection_type = "lower middle" if num_images % 2 == 0 else "middle"
            logger.info(f"Fallback selection: Selected {selection_type} image {selected.image_no} "
                      f"from {num_images} images")
            
            return selected
            
        except Exception as e:
            logger.error(f"Error in fallback selection: {e}")
            return image_analyses[0] if image_analyses else None
