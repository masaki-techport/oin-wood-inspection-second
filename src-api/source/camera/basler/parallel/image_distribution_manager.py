"""
Image Distribution Manager for parallel processing.

This module handles the distribution of images across multiple processing groups
to enable parallel analysis while maintaining the existing 5-group structure (A-E).
"""

import os
import logging
import math
from typing import Dict, List, Any
from .processing_group import ProcessingGroup

logger = logging.getLogger('BaslerCamera.ImageDistributionManager')

class ImageDistributionManager:
    """
    Manages distribution of images across processing groups for parallel analysis.

    Implements sequential range distribution logic to split images into 5 groups (A-E).
    Images are first sorted by their image number (extracted from filename) to ensure
    consistent grouping with frontend logic:
    - Group A: images 0-4 (No_0000, No_0001, No_0002, No_0003, No_0004)
    - Group B: images 5-9 (No_0005, No_0006, No_0007, No_0008, No_0009)
    - Group C: images 10-14 (No_0010, No_0011, No_0012, No_0013, No_0014)
    - Group D: images 15-19 (No_0015, No_0016, No_0017, No_0018, No_0019)
    - Group E: images 20-24 (No_0020, No_0021, No_0022, No_0023, No_0024)
    """
    
    def __init__(self):
        """Initialize the image distribution manager."""
        # Remove hardcoded 5-group limitation - support unlimited groups for FIFO
        self.max_groups = None  # No limit on number of groups
        self.distribution_strategy = 'balanced'  # Use sequential range distribution
        
    def distribute_images(self, image_paths: List[str]) -> Dict[str, List[str]]:
        """
        Distribute images across unlimited groups using sequential range distribution.

        Args:
            image_paths: List of image file paths to distribute

        Returns:
            Dict[str, List[str]]: Dictionary mapping group names to image paths
        """
        if not image_paths:
            logger.warning("No images to distribute")
            return {}

        # Calculate optimal number of groups (one group per image for maximum FIFO granularity)
        num_groups = len(image_paths)
        logger.info(f"Distributing {len(image_paths)} images across {num_groups} groups using {self.distribution_strategy} strategy")

        # Sort images by image number to ensure consistent grouping with frontend
        sorted_image_paths = self._sort_images_by_number(image_paths)
        
        if self.distribution_strategy == 'balanced':
            return self._distribute_balanced(sorted_image_paths, num_groups)
        elif self.distribution_strategy == 'round_robin':
            return self._distribute_round_robin(sorted_image_paths, num_groups)
        else:
            # Default to balanced (sequential range) distribution
            return self._distribute_balanced(sorted_image_paths, num_groups)
    
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
    
    def _distribute_round_robin(self, image_paths: List[str], num_groups: int) -> Dict[str, List[str]]:
        """
        Distribute images using round-robin algorithm.
        
        This ensures even distribution across groups, with any remainder
        distributed to the first groups.
        
        Args:
            image_paths: List of image paths to distribute
            num_groups: Number of groups to distribute across
            
        Returns:
            Dict[str, List[str]]: Distributed images by group
        """
        from utils.labeling import to_label
        
        # Generate group names using Excel-style labeling
        group_names = [to_label(i + 1) for i in range(num_groups)]
        distributed_images = {group: [] for group in group_names}
        
        # Round-robin distribution
        for i, image_path in enumerate(image_paths):
            group_index = i % num_groups
            group_name = group_names[group_index]
            distributed_images[group_name].append(image_path)
        
        # Log distribution results
        for group_name, paths in distributed_images.items():
            logger.info(f"Group {group_name}: {len(paths)} images")
            if paths:
                logger.debug(f"Group {group_name} images: {[os.path.basename(p) for p in paths[:3]]}{'...' if len(paths) > 3 else ''}")
        
        return distributed_images
    
    def _distribute_balanced(self, image_paths: List[str], num_groups: int) -> Dict[str, List[str]]:
        """
        Sequential range distribution strategy for balanced groups.

        This method distributes images in sequential ranges based on their sorted order:
        - Group A gets the first N images (No_0000, No_0001, No_0002, No_0003, No_0004)
        - Group B gets the next N images (No_0005, No_0006, No_0007, No_0008, No_0009)
        - etc.

        Each group gets exactly the same number of images (or as close as possible).
        Images are expected to be pre-sorted by image number.

        Args:
            image_paths: List of image paths to distribute (should be sorted by image number)
            num_groups: Number of groups to distribute across

        Returns:
            Dict[str, List[str]]: Distributed images by group
        """
        from utils.labeling import to_label
        
        # Generate group names using Excel-style labeling
        group_names = [to_label(i + 1) for i in range(num_groups)]
        distributed_images = {group: [] for group in group_names}
        
        images_per_group = len(image_paths) // num_groups
        remainder = len(image_paths) % num_groups
        
        start_index = 0
        for i, group_name in enumerate(group_names):
            # Calculate how many images this group should get
            group_size = images_per_group + (1 if i < remainder else 0)
            end_index = start_index + group_size
            
            # Assign images to this group
            distributed_images[group_name] = image_paths[start_index:end_index]
            start_index = end_index
        
        return distributed_images
    
    def create_processing_groups(self, distributed_images: Dict[str, List[str]], 
                               threads_per_group: int = 2) -> List[ProcessingGroup]:
        """
        Create ProcessingGroup instances for each group with distributed images.
        
        Args:
            distributed_images: Dictionary mapping group names to image paths
            threads_per_group: Number of threads to allocate per group (default: 2)
            
        Returns:
            List[ProcessingGroup]: List of configured processing groups
        """
        processing_groups = []
        
        for group_name, image_paths in distributed_images.items():
            if image_paths:  # Only create groups that have images
                group = ProcessingGroup(
                    group_name=group_name,
                    image_paths=image_paths,
                    thread_pool_size=threads_per_group
                )
                processing_groups.append(group)
                logger.info(f"Created ProcessingGroup {group_name} with {len(image_paths)} images and {threads_per_group} threads")
            else:
                logger.debug(f"Skipping empty group {group_name}")
        
        logger.info(f"Created {len(processing_groups)} processing groups")
        return processing_groups
    
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
        
        logger.debug("Distribution validation passed")
        return True
    
    def set_distribution_strategy(self, strategy: str):
        """
        Set the distribution strategy.
        
        Args:
            strategy: Distribution strategy ('round_robin' or 'balanced')
        """
        if strategy in ['round_robin', 'balanced']:
            self.distribution_strategy = strategy
            logger.info(f"Distribution strategy set to: {strategy}")
        else:
            logger.warning(f"Unknown distribution strategy: {strategy}, keeping current: {self.distribution_strategy}")
