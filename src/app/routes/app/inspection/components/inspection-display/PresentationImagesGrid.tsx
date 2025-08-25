import React, { useEffect, useMemo } from 'react';
import { PresentationImagesGridProps } from '../../types';
import PresentationImageCard from './PresentationImageCard';

/**
 * Component for displaying a grid of presentation images
 * Uses the current presentationImages prop directly without persisting old images
 */
const PresentationImagesGrid: React.FC<PresentationImagesGridProps> = ({ 
  presentationImages,
  loading,
  onImageTest
}) => {
  // Define the available groups A-E
  const allGroups = ['A', 'B', 'C', 'D', 'E'];

  // Log when presentation images change
  useEffect(() => {
    if (presentationImages && presentationImages.length > 0) {
      console.log('Received new presentation images:', presentationImages);

      // Log inspection ID for debugging
      const inspectionIds = presentationImages.map(img => img.inspection_id);
      const uniqueIds = Array.from(new Set(inspectionIds));
      console.log(`Images are from inspection ID(s): ${uniqueIds.join(', ')}`);
      
      // Debug: Print each image path
      presentationImages.forEach((img, index) => {
        console.log(`Image ${index+1}/${presentationImages.length}:`);
        console.log(`  Group: ${img.group_name}`);
        console.log(`  Path: ${img.image_path}`);
        console.log(`  Inspection ID: ${img.inspection_id}`);
      });
    }
  }, [presentationImages]);

  // Get the actual groups we have images for - memoized to prevent recalculation
  const availableGroups = useMemo(() => {
    return presentationImages ? presentationImages.map(img => img.group_name) : [];
  }, [presentationImages]);

  // Determine how many groups to show based on available images - memoized
  const groupsToShow = useMemo(() => {
    return availableGroups.length > 0
      ? allGroups.slice(0, availableGroups.length)
      : allGroups;
  }, [availableGroups, allGroups]);

  // Just show placeholders if we don't have any images yet or are loading
  if (loading) {
    return (
      <div className="text-center py-8">
        <div className="flex items-center justify-center space-x-2">
          <img src="/image-loading.gif" alt="Loading..." className="w-6 h-6" />
          <span>画像を読み込み中...</span>
        </div>
        <div className="text-sm text-gray-500 mt-2">
          検査結果の画像を取得しています
        </div>
      </div>
    );
  }

  if (!presentationImages || presentationImages.length === 0) {
    // Create placeholder slots for groups A-E
    return (
      <div className="grid grid-cols-5 gap-4 w-full">
        {allGroups.map((section) => (
          <div key={section} className="bg-white border-2 border-gray-400 text-center rounded-lg shadow-md">
            <div className="bg-gray-100 text-xl font-bold py-3 border-b-2 border-gray-400">{section}</div>
            <div className="p-2">
              <div className="w-full h-20 mx-auto flex items-center justify-center">
                <img src="/image-loading.gif" alt="Loading..." className="max-w-full max-h-full object-contain" />
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-5 gap-4 w-full">
      {groupsToShow.map((section) => {
        // Find the image for this group using current images
        const groupImage = presentationImages.find(img => img.group_name === section);

        return (
          <PresentationImageCard
            key={`${section}-${groupImage?.inspection_id || 'none'}`}
            groupName={section}
            imagePath={groupImage?.image_path || null}
            inspectionId={groupImage?.inspection_id}
            onImageTest={onImageTest}
          />
        );
      })}
    </div>
  );
};

export default React.memo(PresentationImagesGrid);