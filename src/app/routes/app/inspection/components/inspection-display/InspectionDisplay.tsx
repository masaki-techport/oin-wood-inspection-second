import React, { useMemo } from 'react';
import { InspectionDisplayProps } from '../../types';
import ResultDisplay from './ResultDisplay';
import PresentationImagesGrid from './PresentationImagesGrid';
import MeasurementsDisplay from './MeasurementsDisplay';

/**
 * Main component for displaying inspection results and images
 */
const InspectionDisplay: React.FC<InspectionDisplayProps> = ({
  inspectionResult,
  defectType,
  measurements,
  presentationImages,
  loadingPresentationImages,
  createdInspectionId,
  onShowDetail,
  onImageTest
}) => {
  // Memoize the background color calculation to prevent recalculation on every render
  const backgroundColorClass = useMemo(() => {
    if (!inspectionResult) return 'bg-gray-300';
    if (inspectionResult === '無欠点') return 'bg-green-500';
    if (inspectionResult === 'こぶし') return 'bg-yellow-500';
    return 'bg-red-500';
  }, [inspectionResult]);

  return (
    <div className={`h-full ${backgroundColorClass} border-4 border-teal-600 rounded-lg relative`}>
      {/* Result Display */}
      <ResultDisplay inspectionResult={inspectionResult} defectType={defectType} />

      {/* Captured Image Display or Sample Sections */}
      <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2">
        {/* Only show content when we have either presentation images or inspection results */}
        {(presentationImages.length > 0 || inspectionResult) ? (
          <div className="bg-white p-6 rounded-lg shadow-xl w-full max-w-4xl">
            <PresentationImagesGrid 
              presentationImages={presentationImages} 
              loading={loadingPresentationImages}
              onImageTest={onImageTest}
            />
            
            <button
              className="bg-cyan-800 text-white px-6 py-2 rounded mx-auto mt-5 block"
              onClick={() => {
                if (createdInspectionId !== null) onShowDetail(createdInspectionId);
              }}
              disabled={createdInspectionId === null}
            >
              検査結果詳細​
            </button>
          </div>
        ) : null}
      </div>

      {/* Measurements Section */}
      <MeasurementsDisplay measurements={measurements} inspectionResult={inspectionResult} defectType={defectType} />
    </div>
  );
};

export default React.memo(InspectionDisplay);