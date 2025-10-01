"""
Memory Group Distributor for memory analysis system.

This module provides image distribution capabilities for the memory analysis system,
similar to the parallel system's ImageDistributionManager but optimized for memory-based
analysis with 5-group presentation selection.
"""

import os
import logging
import math
from typing import Dict, List, Any
from utils.labeling import to_label

logger = logging.getLogger('BaslerCamera.MemoryGroupDistributor')

class MemoryGroupDistributor:
    """
    Manages distribution of images across 5 groups (A-E) for memory analysis.
    
    Implements the same sequential range distribution logic as the parallel system
    to ensure consistent grouping with frontend logic:
    - Group A: images 0-4 (No_0000, No_0001, No_0002, No_0003, No_0004)
    - Group B: images 5-9 (No_0005, No_0006, No_0007, No_0008, No_0009)
    - Group C: images 10-14 (No_0010, No_0011, No_0012, No_0013, No_0014)
    - Group D: images 15-19 (No_0015, No_0016, No_0017, No_0018, No_0019)
    - Group E: images 20-24 (No_0020, No_0021, No_0022, No_0023, No_0024)
    """
    
    def __init__(self):
        """Initialize the memory group distributor."""
        self.max_groups = 5  # Fixed to 5 groups (A-E) for presentation
        self.distribution_strategy = 'balanced'  # Use sequential range distribution
        
        logger.info("MemoryGroupDistributor initialized for 5-group distribution")
    
    def distribute_images_5_groups(self, image_paths: List[str]) -> Dict[str, List[str]]:
        """
        Distribute images across exactly 5 groups (A-E) using sequential range distribution.
        
        Args:
            image_paths: List of image file paths to distribute
            
        Returns:
            Dict[str, List[str]]: Dictionary mapping group names (A-E) to image paths
        """
        if not image_paths:
            logger.warning("No images to distribute")
            return {}
        
        logger.info(f"Distributing {len(image_paths)} images across 5 groups (A-E) using {self.distribution_strategy} strategy")
        
        # Sort images by image number to ensure consistent grouping with frontend
        sorted_image_paths = self._sort_images_by_number(image_paths)
        
        # Generate group names for 5 groups (A-E)
        group_names = [to_label(i + 1) for i in range(5)]  # A, B, C, D, E
        distributed_images = {group: [] for group in group_names}
        
        # Calculate images per group
        images_per_group = len(sorted_image_paths) // 5
        remainder = len(sorted_image_paths) % 5
        
        # Distribute images sequentially across groups
        start_index = 0
        for i, group_name in enumerate(group_names):
            # Calculate how many images this group should get
            group_size = images_per_group + (1 if i < remainder else 0)
            end_index = start_index + group_size
            
            # Assign images to this group
            distributed_images[group_name] = sorted_image_paths[start_index:end_index]
            start_index = end_index
        
        # Log distribution results
        for group_name, paths in distributed_images.items():
            logger.info(f"Group {group_name}: {len(paths)} images")
            if paths:
                logger.debug(f"Group {group_name} images: {[os.path.basename(p) for p in paths[:3]]}{'...' if len(paths) > 3 else ''}")
        
        return distributed_images
    
    def _sort_images_by_number(self, image_paths: List[str]) -> List[str]:
        """
        Sort images by their image number extracted from filename.
        This ensures consistent grouping with frontend logic.
        
        Args:
            image_paths: List of image file paths to sort
            
        Returns:
            List[str]: Sorted image paths by image number
        """
        import re
        
        def extract_image_no(image_path: str) -> int:
            """Extract image number from path using 'No_????' pattern."""
            if not image_path:
                return 0
            
            try:
                # Look for "No_" followed by digits in the path
                matches = re.findall(r'No_(\d+)', image_path)
                if matches:
                    # Use the last match in case there are multiple "No_" patterns
                    image_no_str = matches[-1]
                    return int(image_no_str)
                else:
                    logger.warning(f"Could not extract image_no from path: {image_path}")
                    return 0
            except Exception as e:
                logger.error(f"Error extracting image_no from path {image_path}: {e}")
                return 0
        
        # Create list of (image_path, image_no) tuples for sorting
        image_data = [(path, extract_image_no(path)) for path in image_paths]
        
        # Sort by image number
        image_data.sort(key=lambda x: x[1])
        
        # Extract sorted paths
        sorted_paths = [item[0] for item in image_data]
        
        logger.debug(f"Sorted {len(sorted_paths)} images by image number")
        for i, (path, image_no) in enumerate(image_data[:5]):  # Log first 5 for debugging
            logger.debug(f"  {i}: image_no={image_no}, path={os.path.basename(path)}")
        
        return sorted_paths
    
    def get_distribution_stats(self, distributed_images: Dict[str, List[str]]) -> Dict[str, Any]:
        """
        Get statistics about the image distribution.
        
        Args:
            distributed_images: Dictionary mapping group names to image paths
            
        Returns:
            Dict[str, Any]: Distribution statistics
        """
        total_images = sum(len(paths) for paths in distributed_images.values())
        group_sizes = {group: len(paths) for group, paths in distributed_images.items()}
        
        if total_images > 0:
            min_size = min(group_sizes.values())
            max_size = max(group_sizes.values())
            avg_size = total_images / len(distributed_images)
            balance_ratio = min_size / max_size if max_size > 0 else 1.0
        else:
            min_size = max_size = avg_size = balance_ratio = 0
        
        return {
            'total_images': total_images,
            'group_count': len(distributed_images),
            'group_sizes': group_sizes,
            'min_group_size': min_size,
            'max_group_size': max_size,
            'average_group_size': avg_size,
            'balance_ratio': balance_ratio,
            'distribution_strategy': self.distribution_strategy
        }
    
    def validate_distribution(self, image_paths: List[str], 
                            distributed_images: Dict[str, List[str]]) -> bool:
        """
        Validate that the distribution is correct and complete.
        
        Args:
            image_paths: Original list of image paths
            distributed_images: Distributed images by group
            
        Returns:
            bool: True if distribution is valid, False otherwise
        """
        # Check total count
        distributed_count = sum(len(paths) for paths in distributed_images.values())
        if distributed_count != len(image_paths):
            logger.error(f"Distribution count mismatch: {distributed_count} != {len(image_paths)}")
            return False
        
        # Check for duplicates
        all_distributed = []
        for paths in distributed_images.values():
            all_distributed.extend(paths)
        
        if len(set(all_distributed)) != len(all_distributed):
            logger.error("Duplicate images found in distribution")
            return False
        
        # Check that all original images are included
        original_set = set(image_paths)
        distributed_set = set(all_distributed)
        
        if original_set != distributed_set:
            missing = original_set - distributed_set
            extra = distributed_set - original_set
            if missing:
                logger.error(f"Missing images in distribution: {missing}")
            if extra:
                logger.error(f"Extra images in distribution: {extra}")
            return False
        
        # Check that we have exactly 5 groups
        if len(distributed_images) != 5:
            logger.error(f"Expected 5 groups, got {len(distributed_images)}")
            return False
        
        # Check group names are A-E
        expected_groups = {'A', 'B', 'C', 'D', 'E'}
        actual_groups = set(distributed_images.keys())
        if expected_groups != actual_groups:
            logger.error(f"Expected groups {expected_groups}, got {actual_groups}")
            return False
        
        logger.debug("Distribution validation passed")
        return True
