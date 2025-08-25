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
    
    Implements round-robin distribution logic to split images into 5 groups (A-E)
    with load balancing for uneven image counts.
    """
    
    def __init__(self):
        """Initialize the image distribution manager."""
        self.group_names = ['A', 'B', 'C', 'D', 'E']
        self.distribution_strategy = 'round_robin'  # Can be extended to other strategies
        
    def distribute_images(self, image_paths: List[str]) -> Dict[str, List[str]]:
        """
        Distribute images across 5 groups (A-E) using round-robin logic.
        
        Args:
            image_paths: List of image file paths to distribute
            
        Returns:
            Dict[str, List[str]]: Dictionary mapping group names to image paths
        """
        if not image_paths:
            logger.warning("No images to distribute")
            return {group: [] for group in self.group_names}
        
        logger.info(f"Distributing {len(image_paths)} images across {len(self.group_names)} groups")
        
        if self.distribution_strategy == 'round_robin':
            return self._distribute_round_robin(image_paths)
        else:
            # Default to round-robin if unknown strategy
            return self._distribute_round_robin(image_paths)
    
    def _distribute_round_robin(self, image_paths: List[str]) -> Dict[str, List[str]]:
        """
        Distribute images using round-robin algorithm.
        
        This ensures even distribution across groups, with any remainder
        distributed to the first groups.
        
        Args:
            image_paths: List of image paths to distribute
            
        Returns:
            Dict[str, List[str]]: Distributed images by group
        """
        distributed_images = {group: [] for group in self.group_names}
        
        # Round-robin distribution
        for i, image_path in enumerate(image_paths):
            group_index = i % len(self.group_names)
            group_name = self.group_names[group_index]
            distributed_images[group_name].append(image_path)
        
        # Log distribution results
        for group_name, paths in distributed_images.items():
            logger.info(f"Group {group_name}: {len(paths)} images")
            if paths:
                logger.debug(f"Group {group_name} images: {[os.path.basename(p) for p in paths[:3]]}{'...' if len(paths) > 3 else ''}")
        
        return distributed_images
    
    def _distribute_balanced(self, image_paths: List[str]) -> Dict[str, List[str]]:
        """
        Alternative distribution strategy for perfectly balanced groups.
        
        This method ensures each group gets exactly the same number of images
        (or as close as possible), which may be useful for certain scenarios.
        
        Args:
            image_paths: List of image paths to distribute
            
        Returns:
            Dict[str, List[str]]: Distributed images by group
        """
        distributed_images = {group: [] for group in self.group_names}
        
        images_per_group = len(image_paths) // len(self.group_names)
        remainder = len(image_paths) % len(self.group_names)
        
        start_index = 0
        for i, group_name in enumerate(self.group_names):
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
            avg_size = total_images / len(self.group_names)
            balance_ratio = min_size / max_size if max_size > 0 else 1.0
        else:
            min_size = max_size = avg_size = balance_ratio = 0
        
        return {
            'total_images': total_images,
            'group_count': len(self.group_names),
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
