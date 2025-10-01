"""
Presentation Image Selector for Parallel Processing.

This module implements the selection algorithms for each defect classification category:
- 節あり (FUSHIARI): Select by defect count (最も数が多いもの) - tie → first image
- こぶし (KOBUSHI): Select by knot size (サイズ) - tie → first image
- 無欠点 (MUKETSUTON): Select middle image of group (ignore holes and discoloration)
"""

import logging
from typing import List, Optional, Dict, Any
from .defect_classification_engine import DefectAnalysis, GroupDefectAnalysis, DefectClassification

logger = logging.getLogger('BaslerCamera.PresentationImageSelector')

class PresentationImageSelector:
    """
    Selector for presentation images based on defect classification and priority rules.

    Implements the specific selection criteria for each classification:
    1. 節あり: Select image with most defects (同数の場合初めの一枚)
    2. こぶし: Select image with largest knot (同数のものは初めの一枚)
    3. 無欠点: Select middle image of group (ignore holes and discoloration)
       - Even numbers: Select "lower middle" (e.g., 4 images → image 2)
       - Odd numbers: Select true middle (e.g., 5 images → image 3)
    """
    
    def __init__(self):
        """Initialize the presentation image selector."""
        self.knot_error_types = {2, 3, 4, 5}
    
    def select_presentation_image(self, group_analysis: GroupDefectAnalysis) -> Optional[DefectAnalysis]:
        """
        Select the best presentation image from a group based on its dominant classification.
        
        Args:
            group_analysis: Analysis of the group with classification information
            
        Returns:
            Optional[DefectAnalysis]: Selected image analysis or None if no suitable image
        """
        try:
            if not group_analysis.image_analyses:
                logger.warning(f"Group {group_analysis.group_name}: No images to select from")
                return None
            
            # Select based on dominant classification
            if group_analysis.dominant_classification == DefectClassification.FUSHIARI:
                selected = self._select_fushiari_image(group_analysis)
            elif group_analysis.dominant_classification == DefectClassification.KOBUSHI:
                selected = self._select_kobushi_image(group_analysis)
            else:  # MUKETSUTON
                selected = self._select_muketsuton_image(group_analysis)
            
            if selected:
                logger.info(f"Group {group_analysis.group_name}: Selected image {selected.image_no} "
                          f"({selected.classification.value}) from {len(group_analysis.image_analyses)} candidates")
            else:
                logger.warning(f"Group {group_analysis.group_name}: No image selected")
            
            return selected
            
        except Exception as e:
            logger.error(f"Error selecting presentation image for group {group_analysis.group_name}: {e}")
            return self._fallback_selection(group_analysis.image_analyses)
    
    def _select_fushiari_image(self, group_analysis: GroupDefectAnalysis) -> Optional[DefectAnalysis]:
        """
        Select 節あり image based on defect count (最も数が多いもの).
        Tie-breaking: 同数の場合初めの一枚 (first image if same count).
        
        Args:
            group_analysis: Group analysis with 節あり classification
            
        Returns:
            Optional[DefectAnalysis]: Selected image or None
        """
        try:
            # Filter images that have 節あり classification (knots >= 10mm)
            fushiari_images = [
                analysis for analysis in group_analysis.image_analyses
                if analysis.classification == DefectClassification.FUSHIARI
            ]
            
            if not fushiari_images:
                logger.warning(f"Group {group_analysis.group_name}: No 節あり images found, using fallback")
                return self._fallback_selection(group_analysis.image_analyses)
            
            # Sort by image_no to ensure consistent "first image" tie-breaking
            fushiari_images.sort(key=lambda x: x.image_no)
            
            # Find image with most defects (knots >= 10mm)
            max_large_knot_count = 0
            selected_image = None
            
            for analysis in fushiari_images:
                # Count large knots (>= 10mm) in this image
                large_knot_count = sum(
                    1 for defect in analysis.defect_details
                    if defect.get('error_type') in self.knot_error_types and defect.get('length', 0) >= 10
                )
                
                # Select if more large knots, or if same count and this is the first image
                if large_knot_count > max_large_knot_count or (large_knot_count == max_large_knot_count and selected_image is None):
                    max_large_knot_count = large_knot_count
                    selected_image = analysis
            
            if selected_image:
                logger.info(f"Group {group_analysis.group_name}: Selected 節あり image {selected_image.image_no} "
                          f"with {max_large_knot_count} large knots")
            
            return selected_image
            
        except Exception as e:
            logger.error(f"Error selecting 節あり image for group {group_analysis.group_name}: {e}")
            return self._fallback_selection(group_analysis.image_analyses)
    
    def _select_kobushi_image(self, group_analysis: GroupDefectAnalysis) -> Optional[DefectAnalysis]:
        """
        Select こぶし image based on knot size (サイズ).
        Tie-breaking: 同数のものは初めの一枚 (first image if same size).
        
        Args:
            group_analysis: Group analysis with こぶし classification
            
        Returns:
            Optional[DefectAnalysis]: Selected image or None
        """
        try:
            # Filter images that have こぶし classification (knots < 10mm)
            kobushi_images = [
                analysis for analysis in group_analysis.image_analyses
                if analysis.classification == DefectClassification.KOBUSHI
            ]
            
            if not kobushi_images:
                logger.warning(f"Group {group_analysis.group_name}: No こぶし images found, using fallback")
                return self._fallback_selection(group_analysis.image_analyses)
            
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
                logger.info(f"Group {group_analysis.group_name}: Selected こぶし image {selected_image.image_no} "
                          f"with max knot size {max_knot_size}mm")
            
            return selected_image
            
        except Exception as e:
            logger.error(f"Error selecting こぶし image for group {group_analysis.group_name}: {e}")
            return self._fallback_selection(group_analysis.image_analyses)
    
    def _select_muketsuton_image(self, group_analysis: GroupDefectAnalysis) -> Optional[DefectAnalysis]:
        """
        Select 無欠点 image by choosing the middle image of the group.
        For images with no knots, ignore holes and discoloration and select middle image:
        - Even numbers: Select "lower middle" (e.g., 4 images → select image 2)
        - Odd numbers: Select true middle (e.g., 5 images → select image 3)

        Args:
            group_analysis: Group analysis with 無欠点 classification

        Returns:
            Optional[DefectAnalysis]: Selected middle image or None
        """
        try:
            # Filter images that have 無欠点 classification (no knots)
            muketsuton_images = [
                analysis for analysis in group_analysis.image_analyses
                if analysis.classification == DefectClassification.MUKETSUTON
            ]

            if not muketsuton_images:
                logger.warning(f"Group {group_analysis.group_name}: No 無欠点 images found, using fallback")
                return self._fallback_selection(group_analysis.image_analyses)

            # Sort by image_no for consistent selection
            muketsuton_images.sort(key=lambda x: x.image_no)

            # For 無欠点 cases, select middle image with special handling for even numbers
            # Even numbers: select "lower middle" (last image of first half)
            # Odd numbers: select true middle
            num_images = len(muketsuton_images)
            if num_images % 2 == 0:
                # Even number: select (len // 2) - 1 (e.g., 4 images → index 1 → image 2)
                middle_index = (num_images // 2) - 1
            else:
                # Odd number: select len // 2 (e.g., 5 images → index 2 → image 3)
                middle_index = num_images // 2

            selected_image = muketsuton_images[middle_index]

            # Log the selection with details about ignored defects and selection logic
            defect_info = []
            if selected_image.has_hole:
                defect_info.append("holes")
            if selected_image.has_discoloration:
                defect_info.append("discoloration")

            # Determine selection type for logging
            selection_type = "lower middle" if num_images % 2 == 0 else "middle"

            if defect_info:
                logger.info(f"Group {group_analysis.group_name}: Selected 無欠点 {selection_type} image {selected_image.image_no} "
                          f"from {num_images} images (ignoring {', '.join(defect_info)})")
            else:
                logger.info(f"Group {group_analysis.group_name}: Selected 無欠点 {selection_type} image {selected_image.image_no} "
                          f"from {num_images} images (no defects present)")

            return selected_image

        except Exception as e:
            logger.error(f"Error selecting 無欠点 image for group {group_analysis.group_name}: {e}")
            return self._fallback_selection(group_analysis.image_analyses)
    
    def _fallback_selection(self, image_analyses: List[DefectAnalysis]) -> Optional[DefectAnalysis]:
        """
        Fallback selection when other methods fail.
        Selects the middle image from the sorted list with proper even/odd handling.
        
        Args:
            image_analyses: List of image analyses
            
        Returns:
            Optional[DefectAnalysis]: Selected image or None
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
    
    def get_selection_summary(self, group_analysis: GroupDefectAnalysis, 
                            selected_image: Optional[DefectAnalysis]) -> Dict[str, Any]:
        """
        Get a summary of the selection process for logging and debugging.
        
        Args:
            group_analysis: Group analysis result
            selected_image: Selected image analysis
            
        Returns:
            Dict[str, Any]: Selection summary
        """
        try:
            if not selected_image:
                return {
                    'group_name': group_analysis.group_name,
                    'selection_result': 'no_selection',
                    'total_candidates': len(group_analysis.image_analyses)
                }
            
            return {
                'group_name': group_analysis.group_name,
                'selection_result': 'success',
                'selected_image_no': selected_image.image_no,
                'selected_classification': selected_image.classification.value,
                'selection_criteria': self._get_selection_criteria(group_analysis.dominant_classification),
                'total_candidates': len(group_analysis.image_analyses),
                'selected_knot_count': selected_image.knot_count,
                'selected_max_knot_size': selected_image.max_knot_size,
                'selected_total_defects': selected_image.total_defect_count
            }
            
        except Exception as e:
            logger.error(f"Error creating selection summary: {e}")
            return {
                'group_name': group_analysis.group_name,
                'error': str(e)
            }
    
    def _get_selection_criteria(self, classification: DefectClassification) -> str:
        """Get human-readable selection criteria for the classification."""
        criteria_map = {
            DefectClassification.FUSHIARI: "defect_count_priority",
            DefectClassification.KOBUSHI: "knot_size_priority",
            DefectClassification.MUKETSUTON: "middle_image_priority"
        }
        return criteria_map.get(classification, "unknown")
