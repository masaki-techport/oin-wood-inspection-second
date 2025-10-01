"""
Parallel Presentation Processor for BaslerCamera.

This module provides parallel processing capabilities for presentation image selection
based on knot type classification (節あり, 小節, 無欠点) with specific
selection criteria following the flow diagram logic.
"""

import os
import time
import logging
import threading
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from db.inspection_details import InspectionDetails
from .defect_classification_engine import DefectAnalysis, GroupDefectAnalysis  # For compatibility layer
from .knot_type_classification_engine import KnotTypeClassificationEngine, KnotAnalysis, SectionKnotAnalysis
from .knot_based_presentation_image_selector import KnotBasedPresentationImageSelector
from .presentation_results_consolidator import PresentationResultsConsolidator

logger = logging.getLogger('BaslerCamera.ParallelPresentationProcessor')

class ParallelPresentationProcessor:
    """
    Main parallel presentation processor that orchestrates knot type classification
    and presentation image selection across processing groups.
    
    Implements knot-based classification system following the flow diagram:
    - 節あり: Select by knot count (最も数が多いもの)
    - 小節: Select by knot size (サイズ)
    - 無欠点: Fallback selection logic
    """
    
    def __init__(self, camera_instance):
        """
        Initialize the parallel presentation processor.
        
        Args:
            camera_instance: Reference to the parent BaslerCamera object
        """
        self.camera = camera_instance
        self.enabled = True
        
        # Initialize processing components - knot-based logic only
        self.knot_classification_engine = KnotTypeClassificationEngine()
        self.knot_based_selector = KnotBasedPresentationImageSelector()
        self.results_consolidator = PresentationResultsConsolidator(camera_instance)
        
        # Processing state
        self._lock = threading.Lock()
        self.current_inspection_id = None
        self.processing_active = False
        
        # Performance tracking
        self.processing_metrics = {}
        
        logger.info("Parallel presentation processor initialized")
    
    def process_presentation_images_parallel(self, inspection_id: int, 
                                           distributed_images: Dict[str, List[str]]) -> Dict[str, Any]:
        """
        Process presentation images in parallel across groups.
        
        This is the main entry point that replaces the sequential presentation processing.
        
        Args:
            inspection_id: Inspection ID to associate images with
            distributed_images: Dictionary mapping group names (A-E) to image paths
            
        Returns:
            Dict[str, Any]: Processing results and metrics
        """
        if not self.enabled:
            logger.warning("Parallel presentation processing is disabled")
            return self._fallback_to_sequential(inspection_id, distributed_images)
        
        processing_start = time.time()
        
        try:
            with self._lock:
                self.current_inspection_id = inspection_id
                self.processing_active = True
            
            logger.info(f"Starting parallel presentation processing for inspection {inspection_id}")
            logger.info(f"Processing {len(distributed_images)} groups with "
                       f"{sum(len(paths) for paths in distributed_images.values())} total images")
            
            # Initialize consolidation
            self.results_consolidator.initialize_consolidation(inspection_id)
            
            # Process groups in parallel
            group_results = self._process_groups_parallel(inspection_id, distributed_images)
            
            # Consolidate results
            consolidation_result = self.results_consolidator.consolidate_results()
            
            # Calculate final metrics
            processing_time = time.time() - processing_start
            self.processing_metrics = {
                'total_processing_time': processing_time,
                'groups_processed': len(group_results),
                'successful_groups': len([r for r in group_results if r.get('success', False)]),
                'consolidation_success': consolidation_result.get('success', False)
            }
            
            logger.info(f"Parallel presentation processing completed in {processing_time:.3f}s")
            
            return {
                'success': consolidation_result.get('success', False),
                'inspection_id': inspection_id,
                'processing_metrics': self.processing_metrics,
                'group_results': group_results,
                'consolidation_result': consolidation_result
            }
            
        except Exception as e:
            logger.error(f"Error in parallel presentation processing: {e}")
            logger.info("Attempting fallback to sequential processing with preserved groups")

            # Try fallback processing
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
    
    def _process_groups_parallel(self, inspection_id: int, 
                               distributed_images: Dict[str, List[str]]) -> List[Dict[str, Any]]:
        """
        Process presentation selection for each group in parallel.
        
        Args:
            inspection_id: Inspection ID
            distributed_images: Dictionary mapping group names to image paths
            
        Returns:
            List[Dict[str, Any]]: Results from all groups
        """
        results = []
        
        # Determine optimal thread count (one thread per group)
        # Remove 5-group limitation - support unlimited groups for FIFO
        max_workers = len(distributed_images)  # Support unlimited groups
        
        with ThreadPoolExecutor(max_workers=max_workers, 
                              thread_name_prefix="PresentationGroup") as executor:
            
            # Submit all group processing tasks
            future_to_group = {
                executor.submit(
                    self._process_single_group,
                    inspection_id,
                    group_name,
                    image_paths
                ): group_name for group_name, image_paths in distributed_images.items()
                if image_paths  # Only process groups with images
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_group):
                group_name = future_to_group[future]
                try:
                    result = future.result()
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
    
    def _process_single_group(self, inspection_id: int, group_name: str, 
                            image_paths: List[str]) -> Dict[str, Any]:
        """
        Process presentation selection for a single group.
        
        Args:
            inspection_id: Inspection ID
            group_name: Group name (A-E)
            image_paths: List of image paths in this group
            
        Returns:
            Dict[str, Any]: Processing result for this group
        """
        group_start = time.time()
        thread_id = threading.get_ident()
        
        try:
            logger.info(f"[Thread-{thread_id}] Processing group {group_name} with {len(image_paths)} images")
            
            return self._process_single_group_knot_based(inspection_id, group_name, image_paths, thread_id, group_start)
            
        except Exception as e:
            group_time = time.time() - group_start
            logger.error(f"[Thread-{thread_id}] Error processing group {group_name}: {e}")
            return {
                'group_name': group_name,
                'success': False,
                'processing_time': group_time,
                'error': str(e)
            }
    
    def _process_single_group_knot_based(self, inspection_id: int, group_name: str, 
                                        image_paths: List[str], thread_id: int, group_start: float) -> Dict[str, Any]:
        """
        Process presentation selection using the new knot-based knot type classification.
        
        Args:
            inspection_id: Inspection ID
            group_name: Group name (A-E)
            image_paths: List of image paths in this group
            thread_id: Thread identifier
            group_start: Processing start time
            
        Returns:
            Dict[str, Any]: Processing result for this group
        """
        # Analyze knot types for each image in the group
        knot_analyses = []
        
        with self.camera.db_handler.Session() as session:
            for image_path in image_paths:
                # Extract image number from path
                image_no = self._extract_image_no_from_path(image_path)
                if image_no is None:
                    logger.warning(f"Could not extract image_no from path: {image_path}")
                    continue
                
                # Get defect details for this image
                defect_details = self._get_image_defect_details(session, inspection_id, image_no)
                
                # Analyze knot type and characteristics
                knot_analysis = self.knot_classification_engine.analyze_image_knot_type(
                    image_path, image_no, defect_details
                )
                
                knot_analyses.append(knot_analysis)
        
        if not knot_analyses:
            logger.warning(f"Group {group_name}: No valid knot analyses")
            return {
                'group_name': group_name,
                'success': False,
                'reason': 'no_valid_analyses'
            }
        
        # Analyze the section and group by knot types
        section_analysis = self.knot_classification_engine.analyze_section_knot_types(group_name, knot_analyses)
        
        # Select the best representative image using knot-based logic
        selected_image = self.knot_based_selector.select_representative_image(section_analysis)
        
        # Add result to consolidator (adapt to existing interface)
        if selected_image:
            # Convert KnotAnalysis to DefectAnalysis for consolidator compatibility
            defect_analysis = self._convert_knot_to_defect_analysis(selected_image)
            group_analysis = self._create_group_analysis_from_section(section_analysis, defect_analysis)
            self.results_consolidator.add_group_result(group_analysis, defect_analysis)
        
        # Calculate processing time
        group_time = time.time() - group_start
        
        logger.info(f"[Thread-{thread_id}] Group {group_name} completed (knot-based) in {group_time:.3f}s: "
                   f"selected image {selected_image.image_no if selected_image else 'None'}")
        
        return {
            'group_name': group_name,
            'success': True,
            'processing_time': group_time,
            'images_analyzed': len(knot_analyses),
            'logic_type': 'knot_based',
            'knot_type_distribution': {
                '節あり': len(section_analysis.fushiari_images),
                '小節': len(section_analysis.shobushi_images),
                '無欠点': len(section_analysis.muketsuton_images)
            },
            'selected_image_no': selected_image.image_no if selected_image else None,
            'selected_knot_type': selected_image.knot_type.value if selected_image else None,
            'classification_summary': self.knot_classification_engine.get_knot_classification_summary(section_analysis),
            'selection_summary': self.knot_based_selector.get_selection_summary(section_analysis, selected_image)
        }
    
    def _get_image_defect_details(self, session, inspection_id: int, image_no: int) -> List[Dict[str, Any]]:
        """
        Get defect details for a specific image.
        
        Args:
            session: Database session
            inspection_id: Inspection ID
            image_no: Image number
            
        Returns:
            List[Dict[str, Any]]: List of defect details
        """
        try:
            details = session.query(InspectionDetails).filter(
                InspectionDetails.inspection_id == inspection_id,
                InspectionDetails.image_no == image_no
            ).all()
            
            # Convert to dictionary format
            defect_details = []
            for detail in details:
                defect_details.append({
                    'error_type': detail.error_type,
                    'length': detail.length,
                    'x_position': detail.x_position,
                    'y_position': detail.y_position,
                    'width': detail.width,
                    'height': detail.height,
                    'confidence': detail.confidence
                })
            
            return defect_details
            
        except Exception as e:
            logger.error(f"Error getting defect details for image {image_no}: {e}")
            return []
    
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
        Fallback to sequential processing when parallel processing fails.
        This method preserves the group assignments from the distributed images.

        Args:
            inspection_id: Inspection ID
            distributed_images: Dictionary mapping group names to image paths

        Returns:
            Dict[str, Any]: Fallback processing result
        """
        try:
            logger.warning("Falling back to sequential presentation processing with preserved group assignments")

            # Use the new group-aware sequential processing method
            if hasattr(self.camera, 'presentation_processor'):
                self._save_presentation_images_with_groups(inspection_id, distributed_images)
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
    
    def _convert_knot_to_defect_analysis(self, knot_analysis: KnotAnalysis) -> DefectAnalysis:
        """
        Convert KnotAnalysis to DefectAnalysis for consolidator compatibility.
            
        Args:
            knot_analysis: Knot analysis result
                
        Returns:
            DefectAnalysis: Converted defect analysis
        """
        try:
            # Map knot types to defect classifications
            from .defect_classification_engine import DefectClassification
                
            if knot_analysis.knot_type.value == "節あり":
                classification = DefectClassification.FUSHIARI
            elif knot_analysis.knot_type.value == "小節":
                classification = DefectClassification.KOBUSHI
            else:
                classification = DefectClassification.MUKETSUTON
                
            return DefectAnalysis(
                image_path=knot_analysis.image_path,
                image_no=knot_analysis.image_no,
                classification=classification,
                knot_count=knot_analysis.total_knot_count,
                max_knot_size=knot_analysis.largest_knot_size,
                total_defect_count=len(knot_analysis.all_defect_details),
                has_discoloration=knot_analysis.has_discoloration,
                has_hole=knot_analysis.has_hole,
                defect_details=knot_analysis.all_defect_details
            )
                
        except Exception as e:
            logger.error(f"Error converting knot analysis to defect analysis: {e}")
            # Return a fallback defect analysis
            from .defect_classification_engine import DefectClassification
            return DefectAnalysis(
                image_path=knot_analysis.image_path,
                image_no=knot_analysis.image_no,
                classification=DefectClassification.MUKETSUTON,
                knot_count=0,
                max_knot_size=0.0,
                total_defect_count=0,
                has_discoloration=False,
                has_hole=False,
                defect_details=[]
            )
    
    def _create_group_analysis_from_section(self, section_analysis: SectionKnotAnalysis, 
                                          selected_defect_analysis: DefectAnalysis) -> GroupDefectAnalysis:
        """
        Create GroupDefectAnalysis from SectionKnotAnalysis for consolidator compatibility.
            
        Args:
            section_analysis: Section knot analysis
            selected_defect_analysis: Selected image as defect analysis
                
        Returns:
            GroupDefectAnalysis: Converted group analysis
        """
        try:
            # Convert all knot analyses to defect analyses
            defect_analyses = []
            for knot_analysis in section_analysis.image_analyses:
                defect_analysis = self._convert_knot_to_defect_analysis(knot_analysis)
                defect_analyses.append(defect_analysis)
                
            # Determine dominant classification based on selected image
            dominant_classification = selected_defect_analysis.classification
                
            return GroupDefectAnalysis(
                group_name=section_analysis.section_id,
                image_analyses=defect_analyses,
                dominant_classification=dominant_classification,
                selected_image=selected_defect_analysis
            )
                
        except Exception as e:
            logger.error(f"Error creating group analysis from section: {e}")
            # Return a fallback group analysis
            from .defect_classification_engine import DefectClassification
            return GroupDefectAnalysis(
                group_name=section_analysis.section_id,
                image_analyses=[],
                dominant_classification=DefectClassification.MUKETSUTON,
                selected_image=None
            )

    def _save_presentation_images_with_groups(self, inspection_id: int,
                                            distributed_images: Dict[str, List[str]]) -> None:
        """
        Save presentation images while preserving the group assignments from parallel processing.
        This method respects the round-robin distribution used by the parallel processor.

        Args:
            inspection_id: Inspection ID
            distributed_images: Dictionary mapping group names to image paths (from parallel distribution)
        """
        try:
            logger.info(f"Saving presentation images with preserved group assignments for inspection {inspection_id}")

            # Use the camera's database handler for consistency
            with self.camera.db_handler.Session() as session:
                session.begin()

                try:
                    # Clear any existing presentation images for this inspection
                    from db.inspection_presentation import InspectionPresentation
                    session.query(InspectionPresentation).filter(
                        InspectionPresentation.inspection_id == inspection_id
                    ).delete()

                    presentation_objects = []

                    # Process each group with its assigned images
                    for group_name, image_paths in distributed_images.items():
                        if not image_paths:
                            logger.debug(f"Group {group_name} has no images, skipping")
                            continue

                        logger.info(f"Processing group {group_name} with {len(image_paths)} images")

                        # For now, select the first image in each group as the presentation image
                        # This maintains the group assignment while we implement the defect classification logic
                        selected_image_path = image_paths[0]

                        # Create presentation image record
                        presentation_image = InspectionPresentation(
                            inspection_id=inspection_id,
                            group_name=group_name,
                            image_path=selected_image_path
                        )
                        presentation_objects.append(presentation_image)

                        logger.info(f"Selected image for group {group_name}: {os.path.basename(selected_image_path)}")

                    # Bulk insert all presentation images
                    if presentation_objects:
                        session.add_all(presentation_objects)
                        session.commit()
                        logger.info(f"Successfully saved {len(presentation_objects)} presentation images with correct group assignments")
                    else:
                        logger.warning("No presentation images to save")
                        session.rollback()

                except Exception as e:
                    session.rollback()
                    logger.error(f"Error saving presentation images: {e}")
                    raise

        except Exception as e:
            logger.error(f"Error in _save_presentation_images_with_groups: {e}")
            raise
    
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
