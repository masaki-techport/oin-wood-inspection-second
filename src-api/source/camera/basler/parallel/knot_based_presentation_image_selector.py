"""
Flow-Based Presentation Image Selector for Parallel Processing.

This module implements the presentation image selection logic exactly as specified
in the presentation_image_flow.mermaid diagram:

1. Filter images by "節あり" (large knot)
2. If 節あり count == 0, filter by "小節" (small knot)  
3. If 小節 count == 0, select middle image
4. Apply appropriate selection criteria for each knot type
"""

import logging
from typing import List, Optional, Dict, Any
try:
    from .knot_type_classification_engine import KnotAnalysis, SectionKnotAnalysis, KnotType
except ImportError:
    from knot_type_classification_engine import KnotAnalysis, SectionKnotAnalysis, KnotType

logger = logging.getLogger('BaslerCamera.KnotBasedPresentationImageSelector')

class KnotBasedPresentationImageSelector:
    """
    Presentation image selector that follows the exact flow diagram logic.
    
    Implements the sequential filtering approach:
    1. filterImagesByKnotType("節あり") 
    2. countImages(節ありImages)
    3. If count == 0: filterImagesByKnotType("小節")
    4. Apply selection criteria based on knot type and count
    """
    
    def __init__(self):
        """Initialize the flow-based presentation image selector."""
        pass
    
    def select_representative_image(self, section_analysis: SectionKnotAnalysis) -> Optional[KnotAnalysis]:
        """
        Select the best representative image from a section following the flow diagram logic.
        
        This method implements the exact sequence from presentation_image_flow.mermaid:
        1. filterImagesByKnotType("節あり")
        2. countImages(節ありImages) 
        3. Apply 節あり selection logic or fallback to 小節
        
        Args:
            section_analysis: Analysis of the section with knot type classification
            
        Returns:
            Optional[KnotAnalysis]: Selected image analysis or None if no suitable image
        """
        try:
            if not section_analysis.image_analyses:
                logger.warning(f"Section {section_analysis.section_id}: No images to select from")
                return None
            
            logger.info(f"Section {section_analysis.section_id}: Starting representative image selection")
            
            # Step 1: filterImagesByKnotType("節あり")
            fushiari_images = section_analysis.fushiari_images
            logger.debug(f"Section {section_analysis.section_id}: Filtered {len(fushiari_images)} 節あり images")
            
            # Step 2: countImages(節ありImages)
            fushiari_count = self.count_images(fushiari_images)
            logger.info(f"Section {section_analysis.section_id}: 節あり count = {fushiari_count}")
            
            if fushiari_count == 0:
                # Step 3a: filterImagesByKnotType("小節")
                shobushi_images = section_analysis.shobushi_images
                logger.debug(f"Section {section_analysis.section_id}: Filtered {len(shobushi_images)} 小節 images")
                
                # Step 3b: countImages(小節Images)
                shobushi_count = self.count_images(shobushi_images)
                logger.info(f"Section {section_analysis.section_id}: 小節 count = {shobushi_count}")
                
                if shobushi_count == 0:
                    # Step 3c: getMiddleImage(allImages)
                    selected = self.get_middle_image(section_analysis.image_analyses)
                    logger.info(f"Section {section_analysis.section_id}: No knots found, selected middle image {selected.image_no if selected else 'None'}")
                    return selected
                    
                elif shobushi_count == 1:
                    # Step 3d: selectFirstImage(小節Images)
                    selected = self.select_first_image(shobushi_images)
                    logger.info(f"Section {section_analysis.section_id}: Single 小節 image, selected image {selected.image_no if selected else 'None'}")
                    return selected
                    
                else:  # shobushi_count > 1
                    # Step 3e: findImageWithLargestKnot(小節Images)
                    selected = self.find_image_with_largest_knot(shobushi_images)
                    logger.info(f"Section {section_analysis.section_id}: Multiple 小節 images, selected image with largest knot {selected.image_no if selected else 'None'}")
                    return selected
                    
            elif fushiari_count == 1:
                # Step 4a: selectFirstImage(節ありImages)
                selected = self.select_first_image(fushiari_images)
                logger.info(f"Section {section_analysis.section_id}: Single 節あり image, selected image {selected.image_no if selected else 'None'}")
                return selected
                
            else:  # fushiari_count > 1
                # Step 4b: findImageWithMostKnots(節ありImages)
                selected = self.find_image_with_most_knots(fushiari_images)
                logger.info(f"Section {section_analysis.section_id}: Multiple 節あり images, selected image with most knots {selected.image_no if selected else 'None'}")
                return selected
            
        except Exception as e:
            logger.error(f"Error selecting representative image for section {section_analysis.section_id}: {e}")
            return self._fallback_selection(section_analysis.image_analyses)
    
    def count_images(self, image_analyses: List[KnotAnalysis]) -> int:
        """
        Count the number of images as required by the flow diagram.
        
        Args:
            image_analyses: List of image analyses to count
            
        Returns:
            int: Number of images
        """
        return len(image_analyses)
    
    def select_first_image(self, image_analyses: List[KnotAnalysis]) -> Optional[KnotAnalysis]:
        """
        Select the first image from a list as specified in the flow diagram.
        
        Args:
            image_analyses: List of image analyses
            
        Returns:
            Optional[KnotAnalysis]: First image or None if list is empty
        """
        try:
            if not image_analyses:
                return None
            
            # Sort by image_no to ensure consistent "first image" selection
            sorted_images = sorted(image_analyses, key=lambda x: x.image_no)
            selected = sorted_images[0]
            
            logger.debug(f"Selected first image: {selected.image_no}")
            return selected
            
        except Exception as e:
            logger.error(f"Error selecting first image: {e}")
            return None
    
    def get_middle_image(self, image_analyses: List[KnotAnalysis]) -> Optional[KnotAnalysis]:
        """
        Get the middle image from all images as specified in the flow diagram.
        
        For even numbers: Select "lower middle" (e.g., 4 images → select image 2)
        For odd numbers: Select true middle (e.g., 5 images → select image 3)
        
        Args:
            image_analyses: List of all image analyses
            
        Returns:
            Optional[KnotAnalysis]: Middle image or None if list is empty
        """
        try:
            if not image_analyses:
                return None
            
            # Sort by image_no for consistent ordering
            sorted_images = sorted(image_analyses, key=lambda x: x.image_no)
            
            # Select middle image with special handling for even numbers
            # Even numbers: select "lower middle" (last image of first half)
            # Odd numbers: select true middle
            num_images = len(sorted_images)
            if num_images % 2 == 0:
                # Even number: select (len // 2) - 1 (e.g., 4 images → index 1 → image 2)
                middle_index = (num_images // 2) - 1
            else:
                # Odd number: select len // 2 (e.g., 5 images → index 2 → image 3)
                middle_index = num_images // 2
            
            selected = sorted_images[middle_index]
            
            # Determine selection type for logging
            selection_type = "lower middle" if num_images % 2 == 0 else "middle"
            logger.debug(f"Selected {selection_type} image: {selected.image_no} (index {middle_index} of {num_images})")
            return selected
            
        except Exception as e:
            logger.error(f"Error selecting middle image: {e}")
            return None
    
    def find_image_with_largest_knot(self, image_analyses: List[KnotAnalysis]) -> Optional[KnotAnalysis]:
        """
        Find the image with the largest knot as specified in the flow diagram.
        If tie, select first one.
        
        Args:
            image_analyses: List of image analyses with 小節 knot type
            
        Returns:
            Optional[KnotAnalysis]: Image with largest knot or None
        """
        try:
            if not image_analyses:
                return None
            
            # Sort by image_no to ensure consistent tie-breaking (first image)
            sorted_images = sorted(image_analyses, key=lambda x: x.image_no)
            
            # Find image with largest knot size
            selected = None
            max_knot_size = -1.0
            
            for image in sorted_images:
                knot_size = image.largest_knot_size
                
                # Select if larger knot, or if same size and this is the first occurrence
                if knot_size > max_knot_size:
                    max_knot_size = knot_size
                    selected = image
            
            if selected:
                logger.debug(f"Selected image with largest knot: image {selected.image_no}, knot size {max_knot_size}mm")
            
            return selected
            
        except Exception as e:
            logger.error(f"Error finding image with largest knot: {e}")
            return None
    
    def find_image_with_most_knots(self, image_analyses: List[KnotAnalysis]) -> Optional[KnotAnalysis]:
        """
        Find the image with the most knots detected as specified in the flow diagram.
        If tie, select first one.
        
        Args:
            image_analyses: List of image analyses with 節あり knot type
            
        Returns:
            Optional[KnotAnalysis]: Image with most knots or None
        """
        try:
            if not image_analyses:
                return None
            
            # Sort by image_no to ensure consistent tie-breaking (first image)
            sorted_images = sorted(image_analyses, key=lambda x: x.image_no)
            
            # Find image with most knots (large knots for 節あり)
            selected = None
            max_knot_count = -1
            
            for image in sorted_images:
                # For 節あり images, count large knots (>= 10mm)
                knot_count = image.large_knot_count
                
                # Select if more knots, or if same count and this is the first occurrence
                if knot_count > max_knot_count:
                    max_knot_count = knot_count
                    selected = image
            
            if selected:
                logger.debug(f"Selected image with most knots: image {selected.image_no}, knot count {max_knot_count}")
            
            return selected
            
        except Exception as e:
            logger.error(f"Error finding image with most knots: {e}")
            return None
    
    def _fallback_selection(self, image_analyses: List[KnotAnalysis]) -> Optional[KnotAnalysis]:
        """
        Fallback selection when other methods fail.
        Selects the middle image from the sorted list with proper even/odd handling.
        
        Args:
            image_analyses: List of image analyses
            
        Returns:
            Optional[KnotAnalysis]: Selected image or None
        """
        try:
            if not image_analyses:
                return None
            
            # Sort by image_no and select middle image with even/odd handling
            sorted_images = sorted(image_analyses, key=lambda x: x.image_no)
            num_images = len(sorted_images)
            
            if num_images % 2 == 0:
                # Even number: select (len // 2) - 1 (e.g., 4 images → index 1 → image 2)
                middle_index = (num_images // 2) - 1
            else:
                # Odd number: select len // 2 (e.g., 5 images → index 2 → image 3)
                middle_index = num_images // 2
            
            selected = sorted_images[middle_index]
            
            selection_type = "lower middle" if num_images % 2 == 0 else "middle"
            logger.warning(f"Fallback selection: Selected {selection_type} image {selected.image_no} "
                         f"from {num_images} images")
            
            return selected
            
        except Exception as e:
            logger.error(f"Error in fallback selection: {e}")
            return image_analyses[0] if image_analyses else None
    
    def get_selection_summary(self, section_analysis: SectionKnotAnalysis, 
                            selected_image: Optional[KnotAnalysis]) -> Dict[str, Any]:
        """
        Get a summary of the selection process for logging and debugging.
        
        Args:
            section_analysis: Section grain analysis result
            selected_image: Selected image analysis
            
        Returns:
            Dict[str, Any]: Selection summary
        """
        try:
            if not selected_image:
                return {
                    'section_id': section_analysis.section_id,
                    'selection_result': 'no_selection',
                    'total_candidates': len(section_analysis.image_analyses),
                    'fushiari_count': len(section_analysis.fushiari_images),
                    'shobushi_count': len(section_analysis.shobushi_images),
                    'muketsuton_count': len(section_analysis.muketsuton_images)
                }
            
            # Determine selection method based on grain type and counts
            fushiari_count = len(section_analysis.fushiari_images)
            shobushi_count = len(section_analysis.shobushi_images)
            
            if fushiari_count > 1:
                selection_method = "most_knots_fushiari"
            elif fushiari_count == 1:
                selection_method = "single_fushiari"
            elif shobushi_count > 1:
                selection_method = "largest_knot_shobushi"
            elif shobushi_count == 1:
                selection_method = "single_shobushi"
            else:
                selection_method = "middle_image_fallback"
            
            return {
                'section_id': section_analysis.section_id,
                'selection_result': 'success',
                'selected_image_no': selected_image.image_no,
                'selected_knot_type': selected_image.knot_type.value,
                'selection_method': selection_method,
                'total_candidates': len(section_analysis.image_analyses),
                'fushiari_count': fushiari_count,
                'shobushi_count': shobushi_count,
                'muketsuton_count': len(section_analysis.muketsuton_images),
                'selected_knot_count': selected_image.total_knot_count,
                'selected_largest_knot_size': selected_image.largest_knot_size,
                'selected_large_knot_count': selected_image.large_knot_count
            }
            
        except Exception as e:
            logger.error(f"Error creating selection summary: {e}")
            return {
                'section_id': section_analysis.section_id,
                'error': str(e)
            }