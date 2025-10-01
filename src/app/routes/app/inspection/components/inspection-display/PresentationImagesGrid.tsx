import React, { useEffect, useMemo } from 'react';
import { PresentationImagesGridProps } from '../../types';
import PresentationImageCard from './PresentationImageCard';
import ColorBorderCard, { ColorClassification } from './ColorBorderCard';
import ScrollingTempSections from './ScrollingTempSections';
import { useTempSections } from '../../../../../../features/temp-sections/hooks/use-temp-sections';
import { useStatusManager } from '../../hooks/useStatusManager';
import { useSensorData } from '../../hooks/useSensorData';
import { TempSection, SaveSectionGroup } from '../../../../../../types/temp-sections';

/**
 * Component for displaying a grid of presentation images
 * Uses the current presentationImages prop directly without persisting old images
 */
const PresentationImagesGrid: React.FC<PresentationImagesGridProps> = ({ 
  presentationImages,
  loading,
  onImageTest,
  onOpenDetails
}) => {
  // Get sensor data and status manager
  const { sensorStatus } = useSensorData();
  const { status, updateStatusFromSensor } = useStatusManager();
  
  // Update status based on sensor data
  useEffect(() => {
    updateStatusFromSensor(sensorStatus);
  }, [sensorStatus, updateStatusFromSensor]);
  
  // Define the available groups A-E for fixed display
  const fixedGroups = ['A', 'B', 'C', 'D', 'E'];
  
  // Helper function to map summaryColor to ColorClassification
  const mapSummaryColorToClassification = (summaryColor: string): ColorClassification => {
    switch (summaryColor) {
      case 'red':
        return 'red';
      case 'yellow':
        return 'yellow';
      case 'green':
        return 'green';
      case 'gray':
      default:
        return 'gray';
    }
  };
  
  // Determine if we should show infinite groups (処理中) or fixed groups (検査中)
  const isProcessing = status === '処理中';
  const isInspecting = status === '検査中';
  
  // Get temp sections with processing status for clearing
  const { sections: tempSections, saveSections, isSaveStage, isLoading: tempSectionsLoading } = useTempSections(-1, isProcessing);
  
  // Helper to build fetchable URL for presentation preview images
  const getPresentationImageUrl = (imagePath: string, completedAt?: number): string => {
    if (!imagePath) return '';
    const apiBaseUrl = `${window.location.protocol}//${window.location.hostname}:8000`;
    const normalized = imagePath.replace(/\\/g, '/');
    if (normalized.startsWith('presentation/')) {
      const relativePath = `src-api/data/images/${normalized}`;
      const cb = completedAt ? `&cb=${completedAt}` : `&cb=${Date.now()}`;
      return `${apiBaseUrl}/api/stream/file?path=${encodeURIComponent(relativePath)}&convert=jpg${cb}`;
    }
    return normalized;
  };
  
  // Debug logging
  console.log('🔍 PresentationImagesGrid Debug:');
  console.log('  Status:', status);
  console.log('  Is processing:', isProcessing);
  console.log('  Is inspecting:', isInspecting);
  console.log('  Sensor status:', sensorStatus);
  console.log('  Temp sections count:', tempSections?.length || 0);
  console.log('  Temp sections:', tempSections);
  console.log('  Save sections:', saveSections);
  console.log('  Is save stage:', isSaveStage);
  console.log('  Is loading temp sections:', tempSectionsLoading);
  
  // Debug logging
  console.log('PresentationImagesGrid Debug:', {
    status,
    tempSections: tempSections?.length || 0,
    saveSections: saveSections?.length || 0,
    isSaveStage,
    tempSectionsLoading,
    presentationImages: presentationImages?.length || 0,
    loading
  });

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

  // Determine which groups to show based on status
  const groupsToShow = useMemo(() => {
    if (isProcessing) {
      // During processing, show temp sections (infinite groups) - NO fallback to fixed groups
      const tempSectionLabels = tempSections.map((section: TempSection) => section.label);
      console.log('🔍 Processing mode - temp section labels:', tempSectionLabels);
      
      // Only show temp sections if they exist, otherwise show empty array (will show waiting message)
      return tempSectionLabels;
    } else if (isInspecting && isSaveStage) {
      // After PASS_L_TO_R signal, show fixed 5 groups from save sections
      console.log('🔍 Save stage mode - showing fixed groups from save sections');
      return saveSections ? saveSections.map((group: SaveSectionGroup) => group.label) : fixedGroups;
    } else {
      // Default: show empty array (no fixed groups on first load)
      console.log('🔍 Default mode - showing empty (no fixed groups)');
      return [];
    }
  }, [isProcessing, isInspecting, isSaveStage, tempSections, saveSections, availableGroups, fixedGroups]);

  // Just show placeholders if we don't have any images yet or are loading
  if (loading || tempSectionsLoading) {
    return (
      <div className="text-center py-8">
        <div className="flex items-center justify-center space-x-2">
          <img src="/image-loading.gif" alt="Loading..." className="w-6 h-6" />
          <span>画像を読み込み中...</span>
        </div>
        <div className="text-sm text-gray-500 mt-2">
          {isProcessing ? 'リアルタイム分析中...' : '検査結果の画像を取得しています'}
        </div>
      </div>
    );
  }

  // Show appropriate display based on status
  if (isProcessing) {
    // During processing, show temp sections with scrolling functionality
    return (
      <ScrollingTempSections 
        sections={tempSections}
        isLoading={loading}
      />
    );
  }

  // For inspection mode, show waiting message when no groups to display
  if (!presentationImages || presentationImages.length === 0) {
    // Show waiting message instead of fixed groups
    return (
      <div className="text-center py-8">
        <div className="text-gray-500">
          検査を開始してください
        </div>
        <div className="text-sm text-gray-400 mt-2">
          検査を開始すると、リアルタイムで画像が表示されます
        </div>
      </div>
    );
  }

  // If we have presentation images, show them directly (regardless of save stage logic)
  if (presentationImages && presentationImages.length > 0) {
    console.log('🔍 Showing presentation images directly:', presentationImages.length);
    
    // Create A-E groups from presentation images
    const fixedGroups = ['A', 'B', 'C', 'D', 'E'];
    
    return (
      <div className="inspection-presentation-grid">
        {fixedGroups.map((groupName: string) => {
          // Find the image for this group
          const groupImage = presentationImages.find(img => img.group_name === groupName);

          return (
            <PresentationImageCard
              key={`${groupName}-${groupImage?.inspection_id || 'none'}`}
              groupName={groupName}
              imagePath={groupImage?.image_path || null}
              inspectionId={groupImage?.inspection_id}
              onImageTest={onImageTest}
              onOpenDetails={onOpenDetails}
            />
          );
        })}
      </div>
    );
  }

  // Default: show regular presentation images or waiting message
  if (groupsToShow.length === 0) {
    return (
      <div className="text-center py-8">
        <div className="text-gray-500">
          検査を開始してください
        </div>
        <div className="text-sm text-gray-400 mt-2">
          検査を開始すると、リアルタイムで画像が表示されます
        </div>
      </div>
    );
  }

  return (
    <div className="inspection-presentation-grid">
      {groupsToShow.map((section: string) => {
        // Find the image for this group using current images
        const groupImage = presentationImages.find(img => img.group_name === section);

        return (
          <PresentationImageCard
            key={`${section}-${groupImage?.inspection_id || 'none'}`}
            groupName={section}
            imagePath={groupImage?.image_path || null}
            inspectionId={groupImage?.inspection_id}
            onImageTest={onImageTest}
            onOpenDetails={onOpenDetails}
          />
        );
      })}
    </div>
  );
};

export default React.memo(PresentationImagesGrid);