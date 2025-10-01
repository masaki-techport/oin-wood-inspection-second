"""
Knot Type Classification Engine for Presentation Image Selection.

This module implements the knot type classification logic as specified in the 
presentation_image_flow.mermaid diagram:
- 節あり (Large knot): Knots >= 10mm  
- 小節 (Small knot): Knots < 10mm
- 無欠点 (No knot): No knots detected

This replaces the previous DefectClassification system with a knot-focused approach
that matches the required flow diagram logic.
"""

import logging
from enum import Enum
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger('BaslerCamera.KnotTypeClassificationEngine')

class KnotType(Enum):
    """Knot type classification for presentation image selection."""
    FUSHIARI = "節あり"    # Large knot: knots >= 10mm
    SHOBUSHI = "小節"      # Small knot: knots < 10mm  
    MUKETSUTON = "無欠点"  # No knot: no knots detected

@dataclass
class KnotAnalysis:
    """Analysis result for a single image's knot characteristics."""
    image_path: str
    image_no: int
    knot_type: KnotType
    total_knot_count: int  # Total number of knots
    large_knot_count: int  # Number of large knots (>= 10mm)
    small_knot_count: int  # Number of small knots (< 10mm)
    largest_knot_size: float  # Size of the largest knot
    knot_details: List[Dict[str, Any]]  # Details of all knots
    has_discoloration: bool
    has_hole: bool
    all_defect_details: List[Dict[str, Any]]  # All defects for reference

@dataclass
class SectionKnotAnalysis:
    """Analysis result for a section of images."""
    section_id: str
    image_analyses: List[KnotAnalysis]
    fushiari_images: List[KnotAnalysis]  # Images with 節あり
    shobushi_images: List[KnotAnalysis]  # Images with 小節
    muketsuton_images: List[KnotAnalysis]  # Images with 無欠点

class KnotTypeClassificationEngine:
    """
    Engine for classifying images by knot types following the flow diagram logic.
    
    This engine implements the sequential filtering approach:
    1. Classify each image by knot type (節あり/小節/無欠点)
    2. Group images by knot type for section-level analysis
    3. Support filtering operations as required by the flow
    """
    
    def __init__(self):
        """Initialize the knot type classification engine."""
        # Knot error types (2-5 are various knot types)
        self.knot_error_types = {2, 3, 4, 5}
        
        # Error type definitions for reference
        self.error_type_names = {
            0: "変色",      # Discoloration
            1: "穴",        # Hole
            2: "死に節",    # Dead knot
            3: "流れ節_死", # Dead flow knot
            4: "流れ節_生", # Live flow knot
            5: "生き節"     # Live knot
        }
        
        # Knot size threshold for classification
        self.knot_size_threshold = 10.0  # mm
    
    def analyze_image_knot_type(self, image_path: str, image_no: int, 
                               inspection_details: List[Dict[str, Any]]) -> KnotAnalysis:
        """
        Analyze knot characteristics in a single image and classify by knot type.
        
        Args:
            image_path: Path to the image file
            image_no: Image number for identification
            inspection_details: List of defect details from database
            
        Returns:
            KnotAnalysis: Complete knot analysis of the image
        """
        try:
            # Separate knot defects from other defects
            knot_defects = [d for d in inspection_details if d.get('error_type') in self.knot_error_types]
            other_defects = [d for d in inspection_details if d.get('error_type') not in self.knot_error_types]
            
            # Analyze knot characteristics
            total_knot_count = len(knot_defects)
            large_knot_count = 0
            small_knot_count = 0
            largest_knot_size = 0.0
            
            if knot_defects:
                for knot in knot_defects:
                    knot_size = knot.get('length', 0.0)
                    largest_knot_size = max(largest_knot_size, knot_size)
                    
                    if knot_size >= self.knot_size_threshold:
                        large_knot_count += 1
                    else:
                        small_knot_count += 1
            
            # Check for other defect types
            has_discoloration = any(d.get('error_type') == 0 for d in other_defects)
            has_hole = any(d.get('error_type') == 1 for d in other_defects)
            
            # Classify knot type based on the flow diagram logic
            if large_knot_count > 0:
                # Has large knots (>= 10mm) → 節あり
                knot_type = KnotType.FUSHIARI
                logger.debug(f"Image {image_no}: Classified as 節あり (large knots: {large_knot_count}, largest: {largest_knot_size}mm)")
            elif small_knot_count > 0:
                # Has small knots (< 10mm) → 小節
                knot_type = KnotType.SHOBUSHI
                logger.debug(f"Image {image_no}: Classified as 小節 (small knots: {small_knot_count}, largest: {largest_knot_size}mm)")
            else:
                # No knots → 無欠点
                knot_type = KnotType.MUKETSUTON
                logger.debug(f"Image {image_no}: Classified as 無欠点 (no knots detected)")
            
            return KnotAnalysis(
                image_path=image_path,
                image_no=image_no,
                knot_type=knot_type,
                total_knot_count=total_knot_count,
                large_knot_count=large_knot_count,
                small_knot_count=small_knot_count,
                largest_knot_size=largest_knot_size,
                knot_details=knot_defects,
                has_discoloration=has_discoloration,
                has_hole=has_hole,
                all_defect_details=inspection_details
            )
            
        except Exception as e:
            logger.error(f"Error analyzing knot type for image {image_no}: {e}")
            # Return fallback classification
            return KnotAnalysis(
                image_path=image_path,
                image_no=image_no,
                knot_type=KnotType.MUKETSUTON,
                total_knot_count=0,
                large_knot_count=0,
                small_knot_count=0,
                largest_knot_size=0.0,
                knot_details=[],
                has_discoloration=False,
                has_hole=False,
                all_defect_details=[]
            )
    
    def analyze_section_knot_types(self, section_id: str, 
                                   image_analyses: List[KnotAnalysis]) -> SectionKnotAnalysis:
        """
        Analyze knot types across a section of images and group by knot type.
        
        This method implements the filtering logic required by the flow diagram.
        
        Args:
            section_id: Section identifier (e.g., Group A-E)
            image_analyses: List of individual image knot analyses
            
        Returns:
            SectionKnotAnalysis: Analysis grouped by knot types
        """
        try:
            if not image_analyses:
                logger.warning(f"Section {section_id}: No image analyses provided")
                return SectionKnotAnalysis(
                    section_id=section_id,
                    image_analyses=[],
                    fushiari_images=[],
                    shobushi_images=[],
                    muketsuton_images=[]
                )
            
            # Filter images by knot type as required by the flow diagram
            fushiari_images = [img for img in image_analyses if img.knot_type == KnotType.FUSHIARI]
            shobushi_images = [img for img in image_analyses if img.knot_type == KnotType.SHOBUSHI]
            muketsuton_images = [img for img in image_analyses if img.knot_type == KnotType.MUKETSUTON]
            
            logger.info(f"Section {section_id}: Knot type distribution:")
            logger.info(f"  節あり (large knot): {len(fushiari_images)} images")
            logger.info(f"  小節 (small knot): {len(shobushi_images)} images")
            logger.info(f"  無欠点 (no knot): {len(muketsuton_images)} images")
            
            return SectionKnotAnalysis(
                section_id=section_id,
                image_analyses=image_analyses,
                fushiari_images=fushiari_images,
                shobushi_images=shobushi_images,
                muketsuton_images=muketsuton_images
            )
            
        except Exception as e:
            logger.error(f"Error analyzing section {section_id} knot types: {e}")
            return SectionKnotAnalysis(
                section_id=section_id,
                image_analyses=image_analyses,
                fushiari_images=[],
                shobushi_images=[],
                muketsuton_images=[]
            )
    
    def filter_images_by_knot_type(self, image_analyses: List[KnotAnalysis], 
                                   knot_type: KnotType) -> List[KnotAnalysis]:
        """
        Filter images by specific knot type as required by the flow diagram.
        
        Args:
            image_analyses: List of image analyses to filter
            knot_type: Knot type to filter by
            
        Returns:
            List[KnotAnalysis]: Filtered images matching the knot type
        """
        try:
            filtered_images = [img for img in image_analyses if img.knot_type == knot_type]
            logger.debug(f"Filtered {len(filtered_images)} images with knot type {knot_type.value}")
            return filtered_images
            
        except Exception as e:
            logger.error(f"Error filtering images by knot type {knot_type}: {e}")
            return []
    
    def count_images(self, image_analyses: List[KnotAnalysis]) -> int:
        """
        Count the number of images as required by the flow diagram.
        
        Args:
            image_analyses: List of image analyses to count
            
        Returns:
            int: Number of images
        """
        return len(image_analyses)
    
    def get_knot_classification_summary(self, section_analysis: SectionKnotAnalysis) -> Dict[str, Any]:
        """
        Get a summary of the knot classification analysis for logging and debugging.
        
        Args:
            section_analysis: Section knot analysis result
            
        Returns:
            Dict[str, Any]: Summary information
        """
        try:
            total_images = len(section_analysis.image_analyses)
            
            return {
                'section_id': section_analysis.section_id,
                'total_images': total_images,
                'fushiari_count': len(section_analysis.fushiari_images),
                'shobushi_count': len(section_analysis.shobushi_images),
                'muketsuton_count': len(section_analysis.muketsuton_images),
                'knot_type_distribution': {
                    '節あり': len(section_analysis.fushiari_images),
                    '小節': len(section_analysis.shobushi_images),
                    '無欠点': len(section_analysis.muketsuton_images)
                }
            }
            
        except Exception as e:
            logger.error(f"Error creating knot classification summary: {e}")
            return {
                'section_id': section_analysis.section_id,
                'error': str(e)
            }