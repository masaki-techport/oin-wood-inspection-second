"""
Defect Classification Engine for Parallel Presentation Processing.

This module provides defect classification logic for determining presentation image
selection based on the three-tier priority system:
- 節あり (FUSHIARI): Any knot >= 10mm
- こぶし (KOBUSHI): All knots < 10mm  
- 無欠点 (MUKETSUTON): No knots (only discoloration/holes)
"""

import logging
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger('BaslerCamera.DefectClassificationEngine')

class DefectClassification(Enum):
    """Defect classification categories for presentation image selection."""
    FUSHIARI = "節あり"      # Any knot >= 10mm (highest priority)
    KOBUSHI = "こぶし"       # All knots < 10mm (medium priority)  
    MUKETSUTON = "無欠点"    # No knots, only discolor/hole (lowest priority)

@dataclass
class DefectAnalysis:
    """Analysis result for a single image's defects."""
    image_path: str
    image_no: int
    classification: DefectClassification
    knot_count: int
    max_knot_size: float
    total_defect_count: int
    has_discoloration: bool
    has_hole: bool
    defect_details: List[Dict[str, Any]]

@dataclass
class GroupDefectAnalysis:
    """Analysis result for a group of images."""
    group_name: str
    image_analyses: List[DefectAnalysis]
    dominant_classification: DefectClassification
    selected_image: Optional[DefectAnalysis]

class DefectClassificationEngine:
    """
    Engine for classifying defects and determining presentation image selection criteria.
    
    Implements the three-tier classification system:
    1. 節あり: Images with any knot >= 10mm (select by defect count)
    2. こぶし: Images with knots but all < 10mm (select by largest knot size)
    3. 無欠点: Images with no knots, only discoloration/holes (fallback selection)
    """
    
    def __init__(self):
        """Initialize the defect classification engine."""
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
        
        # Classification priority (higher = higher priority for presentation)
        self.classification_priority = {
            DefectClassification.FUSHIARI: 3,    # 節あり (highest)
            DefectClassification.KOBUSHI: 2,     # こぶし (medium)
            DefectClassification.MUKETSUTON: 1   # 無欠点 (lowest)
        }
    
    def analyze_image_defects(self, image_path: str, image_no: int, 
                            inspection_details: List[Dict[str, Any]]) -> DefectAnalysis:
        """
        Analyze defects in a single image and classify it.
        
        Args:
            image_path: Path to the image file
            image_no: Image number for identification
            inspection_details: List of defect details from database
            
        Returns:
            DefectAnalysis: Complete analysis of the image's defects
        """
        try:
            # Separate knot defects from other defects
            knot_defects = [d for d in inspection_details if d.get('error_type') in self.knot_error_types]
            other_defects = [d for d in inspection_details if d.get('error_type') not in self.knot_error_types]
            
            # Analyze knot characteristics
            knot_count = len(knot_defects)
            max_knot_size = 0.0
            large_knots = []
            
            if knot_defects:
                knot_sizes = [d.get('length', 0.0) for d in knot_defects]
                max_knot_size = max(knot_sizes)
                large_knots = [d for d in knot_defects if d.get('length', 0.0) >= 10.0]
            
            # Check for other defect types
            has_discoloration = any(d.get('error_type') == 0 for d in other_defects)
            has_hole = any(d.get('error_type') == 1 for d in other_defects)
            
            # Classify the image based on knot characteristics
            if large_knots:
                # Any knot >= 10mm → 節あり
                classification = DefectClassification.FUSHIARI
                logger.debug(f"Image {image_no}: Classified as 節あり (large knots: {len(large_knots)}, max size: {max_knot_size})")
            elif knot_defects:
                # Has knots but all < 10mm → こぶし
                classification = DefectClassification.KOBUSHI
                logger.debug(f"Image {image_no}: Classified as こぶし (knot count: {knot_count}, max size: {max_knot_size})")
            else:
                # No knots, only discoloration/holes → 無欠点
                classification = DefectClassification.MUKETSUTON
                logger.debug(f"Image {image_no}: Classified as 無欠点 (discoloration: {has_discoloration}, hole: {has_hole})")
            
            return DefectAnalysis(
                image_path=image_path,
                image_no=image_no,
                classification=classification,
                knot_count=knot_count,
                max_knot_size=max_knot_size,
                total_defect_count=len(inspection_details),
                has_discoloration=has_discoloration,
                has_hole=has_hole,
                defect_details=inspection_details
            )
            
        except Exception as e:
            logger.error(f"Error analyzing defects for image {image_no}: {e}")
            # Return fallback classification
            return DefectAnalysis(
                image_path=image_path,
                image_no=image_no,
                classification=DefectClassification.MUKETSUTON,
                knot_count=0,
                max_knot_size=0.0,
                total_defect_count=0,
                has_discoloration=False,
                has_hole=False,
                defect_details=[]
            )
    
    def analyze_group_defects(self, group_name: str, 
                            image_analyses: List[DefectAnalysis]) -> GroupDefectAnalysis:
        """
        Analyze defects across a group of images and determine the dominant classification.
        
        Args:
            group_name: Name of the processing group (A-E)
            image_analyses: List of individual image analyses
            
        Returns:
            GroupDefectAnalysis: Analysis of the entire group
        """
        try:
            if not image_analyses:
                logger.warning(f"Group {group_name}: No image analyses provided")
                return GroupDefectAnalysis(
                    group_name=group_name,
                    image_analyses=[],
                    dominant_classification=DefectClassification.MUKETSUTON,
                    selected_image=None
                )
            
            # Count classifications in the group
            classification_counts = {}
            for analysis in image_analyses:
                classification = analysis.classification
                classification_counts[classification] = classification_counts.get(classification, 0) + 1
            
            # Determine dominant classification based on priority
            # Priority: 節あり > こぶし > 無欠点
            dominant_classification = DefectClassification.MUKETSUTON
            highest_priority = 0
            
            for classification, count in classification_counts.items():
                priority = self.classification_priority[classification]
                if priority > highest_priority:
                    highest_priority = priority
                    dominant_classification = classification
            
            logger.info(f"Group {group_name}: Dominant classification is {dominant_classification.value}")
            logger.debug(f"Group {group_name}: Classification counts: {classification_counts}")
            
            return GroupDefectAnalysis(
                group_name=group_name,
                image_analyses=image_analyses,
                dominant_classification=dominant_classification,
                selected_image=None  # Will be set by the selector
            )
            
        except Exception as e:
            logger.error(f"Error analyzing group {group_name} defects: {e}")
            return GroupDefectAnalysis(
                group_name=group_name,
                image_analyses=image_analyses,
                dominant_classification=DefectClassification.MUKETSUTON,
                selected_image=None
            )
    
    def get_classification_summary(self, group_analysis: GroupDefectAnalysis) -> Dict[str, Any]:
        """
        Get a summary of the classification analysis for logging and debugging.
        
        Args:
            group_analysis: Group analysis result
            
        Returns:
            Dict[str, Any]: Summary information
        """
        try:
            classification_counts = {}
            total_images = len(group_analysis.image_analyses)
            
            for analysis in group_analysis.image_analyses:
                classification = analysis.classification
                classification_counts[classification.value] = classification_counts.get(classification.value, 0) + 1
            
            return {
                'group_name': group_analysis.group_name,
                'total_images': total_images,
                'dominant_classification': group_analysis.dominant_classification.value,
                'classification_breakdown': classification_counts,
                'selected_image_no': group_analysis.selected_image.image_no if group_analysis.selected_image else None,
                'selected_image_path': group_analysis.selected_image.image_path if group_analysis.selected_image else None
            }
            
        except Exception as e:
            logger.error(f"Error creating classification summary: {e}")
            return {
                'group_name': group_analysis.group_name,
                'error': str(e)
            }
