"""
TempSectionAssembler - Groups analyzed images into temporary sections
"""

import threading
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from collections import OrderedDict
import time

from services.settings_service import get_settings_service
from utils.labeling import to_label

# Import parallel presentation selection logic
try:
    from ..parallel.defect_classification_engine import DefectClassification, DefectAnalysis, DefectClassificationEngine
    from ..parallel.presentation_image_selector import PresentationImageSelector
    PARALLEL_AVAILABLE = True
except ImportError:
    PARALLEL_AVAILABLE = False
    import logging
    logger = logging.getLogger('TempSectionAssembler')
    logger.warning("Parallel presentation selection modules not available, using fallback logic")

logger = logging.getLogger('TempSectionAssembler')

@dataclass
class TempSection:
    """Temporary section containing analyzed images"""
    id: str
    label: str
    status: str  # 'building', 'completed', 'saved'
    image_indices: List[int]
    representative_image: Optional[str] = None
    summary_color: str = 'gray'
    created_at: float = 0.0
    completed_at: Optional[float] = None

class TempSectionAssembler:
    """
    Thread-safe assembler for grouping analyzed images into temporary sections.
    
    Features:
    - Groups by temp_section_size from settings
    - Infinite retention when temp_section_max_visible = -1
    - Memory-pressure cleanup when needed
    - Representative selection using parallel processing rules:
      * 節あり (FUSHIARI): Select by defect count (最も数が多いもの) - tie → first image
      * こぶし (KOBUSHI): Select by knot size (サイズ) - tie → first image  
      * 無欠点 (MUKETSUTON): Select middle image of group (ignore holes and discoloration)
    - Excel-style labeling (A, B, ..., Z, AA, AB, ...)
    """
    
    def __init__(self):
        self._lock = threading.RLock()
        self._sections: OrderedDict[str, TempSection] = OrderedDict()
        self._current_section: Optional[TempSection] = None
        self._section_counter = 0
        self._settings_service = get_settings_service()
        self._last_reset_time = time.time()  # Track when assembler was last reset
        
        # Initialize parallel presentation selection components
        if PARALLEL_AVAILABLE:
            self._defect_classification_engine = DefectClassificationEngine()
            self._presentation_selector = PresentationImageSelector()
            logger.info("TempSectionAssembler initialized with parallel presentation selection")
        else:
            self._defect_classification_engine = None
            self._presentation_selector = None
            logger.info("TempSectionAssembler initialized with fallback presentation selection")
        
        # Store analysis results for each section to enable proper selection
        self._section_analyses: Dict[str, List[DefectAnalysis]] = {}
        
        # Subscribe to settings changes
        self._settings_service.subscribe(self)
        
        logger.info("TempSectionAssembler initialized")
    
    def on_parameter_updated(self, parameter_name: str, old_value: Any, new_value: Any) -> bool:
        """Handle parameter updates from settings service"""
        if parameter_name in ['temp_section_size', 'temp_section_max_visible']:
            logger.info(f"Settings updated: {parameter_name} = {new_value}")
            return True
        return True
    
    def add_analyzed_image(self, image_index: int, analysis_result: Dict[str, Any]) -> Optional[TempSection]:
        """
        Add an analyzed image to the current section.
        
        Args:
            image_index: Index of the image in the buffer
            analysis_result: Analysis result from memory analysis
            
        Returns:
            Completed TempSection if section is full, None otherwise
        """
        logger.debug(f"Adding analyzed image {image_index} to temp section, analysis_result type: {type(analysis_result)}")
        with self._lock:
            # Get current settings
            section_size = self._settings_service.get_temp_section_size()
            max_visible = self._settings_service.get_temp_section_max_visible()
            
            # Create new section if needed
            if self._current_section is None or len(self._current_section.image_indices) >= section_size:
                if self._current_section is not None:
                    # Complete the current section with proper presentation selection
                    logger.debug(f"Completing section {self._current_section.label} (had {len(self._current_section.image_indices)} images)")
                    self._complete_section_with_selection(self._current_section)
                    self._sections[self._current_section.id] = self._current_section
                    logger.debug(f"✅ Completed section {self._current_section.label} with {len(self._current_section.image_indices)} images")
                
                # Create new section
                self._section_counter += 1
                section_id = f"temp_section_{self._section_counter}"
                section_label = to_label(self._section_counter)
                
                self._current_section = TempSection(
                    id=section_id,
                    label=section_label,
                    status='building',
                    image_indices=[],
                    created_at=time.time()
                )
                # Initialize analysis storage for this section
                self._section_analyses[section_id] = []
                logger.info(f"🆕 Created new section {section_label} (counter: {self._section_counter}) - FIRST SECTION: {self._section_counter == 1}")
            
            # Add image to current section
            self._current_section.image_indices.append(image_index)
            
            # Store analysis result for proper selection later
            self._store_analysis_result(self._current_section.id, image_index, analysis_result)
            
            # Update representative and summary color based on analysis result (fallback)
            self._update_section_metadata(self._current_section, analysis_result)
            
            # Check if section is now complete
            if len(self._current_section.image_indices) >= section_size:
                # Complete the current section with proper presentation selection
                logger.info(f"Section {self._current_section.label} reached size limit ({len(self._current_section.image_indices)} >= {section_size}) - FIRST SECTION: {self._current_section.label == 'A'}")
                self._complete_section_with_selection(self._current_section)
                self._sections[self._current_section.id] = self._current_section
                logger.info(f"✅ Completed section {self._current_section.label} with {len(self._current_section.image_indices)} images - FIRST SECTION: {self._current_section.label == 'A'}")
                
                completed_section = self._current_section
                self._current_section = None
                return completed_section
            
            return None
    
    def _store_analysis_result(self, section_id: str, image_index: int, analysis_result):
        """Store analysis result for proper presentation selection later"""
        try:
            logger.debug(f"Storing analysis result for image {image_index} in section {section_id}")
            logger.debug(f"Analysis result type: {type(analysis_result)}")
            
            if not PARALLEL_AVAILABLE or not self._defect_classification_engine:
                logger.debug(f"Parallel processing not available or engine not initialized")
                return
            
            # Convert analysis result to DefectAnalysis format
            defect_analysis = self._convert_to_defect_analysis(image_index, analysis_result)
            if defect_analysis:
                self._section_analyses[section_id].append(defect_analysis)
                logger.debug(f"✅ Stored analysis for image {image_index} in section {section_id}: {defect_analysis.classification.value}")
            else:
                logger.warning(f"Failed to convert analysis result for image {image_index}")
        except Exception as e:
            logger.error(f"Error storing analysis result for image {image_index}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    def _convert_to_defect_analysis(self, image_index: int, analysis_result) -> Optional[DefectAnalysis]:
        """Convert analysis result to DefectAnalysis format for parallel selection"""
        try:
            if not PARALLEL_AVAILABLE or not self._defect_classification_engine:
                return None
            
            # Handle both AnalysisResult objects and dictionaries
            if hasattr(analysis_result, 'detections'):
                # AnalysisResult object
                detections = analysis_result.detections
                image_path = getattr(analysis_result, 'image_path', f"presentation/image_{image_index}.jpg")
            else:
                # Dictionary
                detections = analysis_result.get('detections', [])
                image_path = analysis_result.get('image_path', f"presentation/image_{image_index}.jpg")
            
            # Separate knot defects from other defects
            knot_error_types = {2, 3, 4, 5}  # Knot types
            knot_defects = [d for d in detections if d.get('error_type') in knot_error_types]
            other_defects = [d for d in detections if d.get('error_type') not in knot_error_types]
            
            # Analyze knot characteristics
            knot_count = len(knot_defects)
            max_knot_size = 0.0
            large_knots = []
            
            if knot_defects:
                knot_sizes = [d.get('length', 0.0) for d in knot_defects]
                max_knot_size = max(knot_sizes) if knot_sizes else 0.0
                large_knots = [d for d in knot_defects if d.get('length', 0.0) >= 10.0]
            
            # Check for other defect types
            has_discoloration = any(d.get('error_type') == 0 for d in other_defects)
            has_hole = any(d.get('error_type') == 1 for d in other_defects)
            
            # Classify the image based on knot characteristics
            if large_knots:
                classification = DefectClassification.FUSHIARI
            elif knot_defects:
                classification = DefectClassification.KOBUSHI
            else:
                classification = DefectClassification.MUKETSUTON
            
            logger.debug(f"Converted analysis for image {image_index}: {classification.value} "
                        f"(knots: {knot_count}, max_size: {max_knot_size}, large_knots: {len(large_knots)})")
            
            return DefectAnalysis(
                image_path=image_path,
                image_no=image_index,
                classification=classification,
                knot_count=knot_count,
                max_knot_size=max_knot_size,
                total_defect_count=len(detections),
                has_discoloration=has_discoloration,
                has_hole=has_hole,
                defect_details=detections
            )
            
        except Exception as e:
            logger.error(f"Error converting analysis result to DefectAnalysis: {e}")
            return None
    
    def _complete_section_with_selection(self, section: TempSection):
        """Complete section with proper presentation image selection using parallel rules"""
        try:
            section.status = 'completed'
            section.completed_at = time.time()
            
            # Always ensure section is marked as completed, even if selection fails
            logger.debug(f"Completing section {section.label} with {len(section.image_indices)} images")
            
            if not PARALLEL_AVAILABLE or not self._defect_classification_engine or not self._presentation_selector:
                logger.debug(f"Using fallback selection for section {section.label}")
                # Set default values for fallback
                if not section.representative_image and section.image_indices:
                    # Use in-memory preview virtual path as we no longer write files during analysis
                    section.representative_image = f"memory-preview/{section.image_indices[0]}"
                section.summary_color = 'gray'
                return
            
            # Get stored analyses for this section
            section_analyses = self._section_analyses.get(section.id, [])
            if not section_analyses:
                logger.warning(f"No analyses stored for section {section.label}, using fallback")
                # Set default values for fallback
                if not section.representative_image and section.image_indices:
                    section.representative_image = f"memory-preview/{section.image_indices[0]}"
                section.summary_color = 'gray'
                return
            
            # Analyze group defects to determine dominant classification
            group_analysis = self._defect_classification_engine.analyze_group_defects(
                section.label, section_analyses
            )
            
            # Select presentation image using parallel rules
            selected_image = self._presentation_selector.select_presentation_image(group_analysis)
            
            if selected_image:
                section.representative_image = selected_image.image_path
                # Update summary color based on classification
                if selected_image.classification == DefectClassification.FUSHIARI:
                    section.summary_color = 'red'
                elif selected_image.classification == DefectClassification.KOBUSHI:
                    section.summary_color = 'yellow'
                else:
                    section.summary_color = 'green'
                
                logger.info(f"Selected presentation image for section {section.label}: "
                          f"image {selected_image.image_no} ({selected_image.classification.value})")
            else:
                logger.warning(f"No presentation image selected for section {section.label}")
                # Set default values for fallback
                if not section.representative_image and section.image_indices:
                    section.representative_image = f"image_{section.image_indices[0]}.jpg"
                section.summary_color = 'gray'
                
        except Exception as e:
            logger.error(f"Error completing section {section.label} with selection: {e}")
            # Ensure section is still marked as completed even if selection fails
            section.status = 'completed'
            section.completed_at = time.time()
            if not section.representative_image and section.image_indices:
                section.representative_image = f"image_{section.image_indices[0]}.jpg"
            section.summary_color = 'gray'
    
    def _update_section_metadata(self, section: TempSection, analysis_result):
        """Update representative image and summary color based on analysis result"""
        try:
            logger.debug(f"Updating section metadata for section {section.label}, analysis_result type: {type(analysis_result)}")
            
            # Handle both AnalysisResult objects and dictionaries
            if hasattr(analysis_result, 'detections'):
                # AnalysisResult object
                detections = analysis_result.detections
                logger.debug(f"AnalysisResult object - image_path: {getattr(analysis_result, 'image_path', 'NOT_FOUND')}, image_index: {getattr(analysis_result, 'image_index', 'NOT_FOUND')}")
                
                # Get the image path from the analysis result (not from detections)
                if hasattr(analysis_result, 'image_path') and analysis_result.image_path:
                    section.representative_image = analysis_result.image_path
                    logger.debug(f"Set representative_image from image_path: {analysis_result.image_path}")
                elif hasattr(analysis_result, 'image_index'):
                    # Construct image path from image index
                    # Fallback to in-memory preview path by index
                    section.representative_image = f"memory-preview/{analysis_result.image_index}"
                    logger.debug(f"Set representative_image from image_index: image_{analysis_result.image_index}.jpg")
            else:
                # Dictionary
                detections = analysis_result.get('detections', [])
                # Prefer provided path; otherwise point to in-memory preview
                image_path = analysis_result.get('image_path', f"memory-preview/{analysis_result.get('image_index', 'unknown')}")
                section.representative_image = image_path
                logger.debug(f"Set representative_image from dict: {image_path}")
            
            # Determine summary color based on detections and confidence
            if detections:
                # Find the highest confidence detection
                max_confidence = 0.0
                for detection in detections:
                    if hasattr(detection, 'get'):
                        # Dictionary
                        confidence = detection.get('confidence', 0.0)
                    else:
                        # Object with attributes
                        confidence = getattr(detection, 'confidence', 0.0)
                    max_confidence = max(max_confidence, confidence)
                
                # Determine summary color based on highest confidence
                if max_confidence >= 0.8:
                    section.summary_color = 'red'  # High confidence defect
                elif max_confidence >= 0.5:
                    section.summary_color = 'yellow'  # Medium confidence
                else:
                    section.summary_color = 'green'  # Low confidence or no defect
            else:
                # No detections - green for clean
                section.summary_color = 'green'
                
        except Exception as e:
            logger.error(f"Error updating section metadata: {e}")
            section.summary_color = 'gray'
    
    def get_recent_sections(self, limit: int = -1) -> List[TempSection]:
        """
        Get completed sections in FIFO order (oldest first).
        
        Args:
            limit: Maximum number of sections to return (-1 for unlimited)
            
        Returns:
            List of TempSection objects in FIFO order (oldest first)
        """
        with self._lock:
            # Get completed sections only
            completed_sections = [s for s in self._sections.values() if s.status == 'completed']
            
            # Sort by creation time for FIFO order (oldest first)
            completed_sections.sort(key=lambda s: s.created_at)
            
            # Debug logging
            labels = [s.label for s in completed_sections]
            logger.info(f"📋 get_recent_sections: {len(completed_sections)} completed sections: {labels}")
            
            # Return sections (all if limit is -1, otherwise limited)
            if limit == -1:
                result = completed_sections
            else:
                result = completed_sections[:limit] if completed_sections else []
            
            result_labels = [s.label for s in result]
            logger.info(f"📤 Returning {len(result)} sections: {result_labels}")
        
            return result
    
    def get_all_sections(self) -> List[TempSection]:
        """Get all sections (for debugging/monitoring)"""
        with self._lock:
            return list(self._sections.values())
    
    def cleanup_old_sections(self):
        """Clean up old sections based on memory pressure and max_visible setting"""
        with self._lock:
            max_visible = self._settings_service.get_temp_section_max_visible()
            
            # If max_visible is -1 (infinite), only clean up very old sections under memory pressure
            if max_visible == -1:
                # Keep only the last 100 sections to prevent memory issues
                if len(self._sections) > 100:
                    # Remove oldest sections
                    sections_to_remove = list(self._sections.keys())[:-100]
                    for section_id in sections_to_remove:
                        del self._sections[section_id]
                    logger.info(f"Cleaned up {len(sections_to_remove)} old sections (memory pressure)")
            else:
                # Keep only the most recent max_visible sections
                if len(self._sections) > max_visible:
                    sections_to_remove = list(self._sections.keys())[:-max_visible]
                    for section_id in sections_to_remove:
                        del self._sections[section_id]
                    logger.info(f"Cleaned up {len(sections_to_remove)} old sections (max_visible={max_visible})")
    
    def mark_section_saved(self, section_id: str):
        """Mark a section as saved (after PASS_L_TO_R)"""
        with self._lock:
            if section_id in self._sections:
                self._sections[section_id].status = 'saved'
                logger.info(f"Marked section {section_id} as saved")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get assembler statistics for monitoring"""
        with self._lock:
            completed_count = sum(1 for s in self._sections.values() if s.status == 'completed')
            saved_count = sum(1 for s in self._sections.values() if s.status == 'saved')
            building_count = 1 if self._current_section else 0
            
            return {
                'total_sections': len(self._sections),
                'completed_sections': completed_count,
                'saved_sections': saved_count,
                'building_sections': building_count,
                'current_section_size': len(self._current_section.image_indices) if self._current_section else 0,
                'section_counter': self._section_counter,
                'last_reset_time': self._last_reset_time
            }
    
    def get_last_reset_time(self) -> float:
        """Get the timestamp when the assembler was last reset."""
        with self._lock:
            return self._last_reset_time
    
    def reset(self):
        """Reset the assembler (for testing or restart)"""
        with self._lock:
            self._sections.clear()
            self._current_section = None
            self._section_counter = 0
            self._section_analyses.clear()
            self._last_reset_time = time.time()  # Update reset timestamp
            logger.info("🔄 TempSectionAssembler reset - counter reset to 0")
