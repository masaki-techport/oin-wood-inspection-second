import React, { useEffect } from 'react';
import { InspectionDetailsImg } from '@/types/api';
import { DefectStatus, defectStatusColors, defectLabelColors } from '@/utils/defectStatus';
import CleanImageWithBoundingBoxes from '@/components/ui/CleanImageWithBoundingBoxes';

interface ImagePopupModalProps {
  isOpen: boolean;
  onClose: () => void;
  imageUrl: string;
  imageIdentifier: string; // A, B, C, D, E, or grid position
  defectData: InspectionDetailsImg | InspectionDetailsImg[] | null;
  defectStatus: DefectStatus; // 'none' | 'minor' | 'major'
  isLoading?: boolean;
  error?: string | null;
  onRetry?: () => void;
}

// Defect type names mapping
const defectTypeNames: { [key: number]: string } = {
  0: '変色',      // Discoloration
  1: '穴',        // Hole
  2: '死に節',    // Dead knot
  3: '流れ節_死', // Tight knot dead
  4: '流れ節_生', // Tight knot live
  5: '生き節',    // Live knot
};

const ImagePopupModal: React.FC<ImagePopupModalProps> = ({
  isOpen,
  onClose,
  imageUrl,
  imageIdentifier,
  defectData,
  defectStatus,
  isLoading = false,
  error = null,
  onRetry
}) => {

  // Handle escape key press
  useEffect(() => {
    const handleEscapeKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscapeKey);
      // Prevent body scroll when modal is open
      document.body.style.overflow = 'hidden';
    }

    return () => {
      document.removeEventListener('keydown', handleEscapeKey);
      document.body.style.overflow = 'unset';
    };
  }, [isOpen, onClose]);

  // Don't render if modal is not open
  if (!isOpen) return null;

  // Get unique defect types from defectData
  const getUniqueDefectTypes = () => {
    if (!defectData) return [];

    const defects = Array.isArray(defectData) ? defectData : [defectData];
    const uniqueTypes = new Set<number>();

    defects.forEach(defect => {
      uniqueTypes.add(defect.error_type);
    });

    return Array.from(uniqueTypes).map(type => ({
      type,
      name: defectTypeNames[type] || `Type ${type}`
    }));
  };

  const uniqueDefectTypes = getUniqueDefectTypes();

  // Get background color based on defect status - use solid colors like the reference image
  const getBackgroundColor = () => {
    if (isLoading) return 'bg-gray-500';
    if (error) return 'bg-yellow-500';

    switch (defectStatus) {
      case 'none':
        return 'bg-green-500';
      case 'minor':
        return 'bg-yellow-500';
      case 'major':
        return 'bg-red-500';
      default:
        return 'bg-gray-500';
    }
  };



  // Handle backdrop click (click outside modal)
  const handleBackdropClick = (event: React.MouseEvent<HTMLDivElement>) => {
    if (event.target === event.currentTarget) {
      onClose();
    }
  };

  // Handle modal container click to prevent event bubbling
  const handleModalClick = (event: React.MouseEvent<HTMLDivElement>) => {
    event.stopPropagation();
  };

  return (
    <div
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      onClick={handleBackdropClick}
    >
      <div
        className={`relative w-[90vw] max-w-6xl h-[90vh] rounded-lg shadow-xl overflow-hidden ${getBackgroundColor()}`}
        onClick={handleModalClick}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
      >
        {/* Header Section - Match InspectionDetailsModal colors */}
        <div className="bg-cyan-800 text-white p-4 flex items-center justify-between">
          <div className="flex items-center space-x-4">
            {/* OiN Logo */}
            <div className="bg-white text-cyan-800 px-2 py-1 rounded font-bold text-lg">
              OIN
            </div>
            <h1 className="text-2xl font-bold">木材検査システム　詳細</h1>
          </div>
        </div>

        {/* Main Content Area */}
        <div className="flex h-[calc(100%-120px)] p-6 gap-6">
          {/* Left Side - Defect Labels */}
          <div className="w-80 flex flex-col space-y-4">
            {isLoading ? (
              <div className="flex items-center justify-center p-8">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-white"></div>
              </div>
            ) : error ? (
              <div className="bg-white bg-opacity-20 rounded-lg p-4 text-white">
                <p className="font-medium">Error loading defect data</p>
                <p className="text-sm opacity-80">{error}</p>
              </div>
            ) : uniqueDefectTypes.length > 0 ? (
              uniqueDefectTypes.map((defectType, index) => {
                const colors = defectLabelColors[defectType.type as keyof typeof defectLabelColors] || defectLabelColors[0];
                return (
                  <div
                    key={defectType.type}
                    className={`bg-white rounded-lg p-6 shadow-md border-8 ${colors.border}`}
                  >
                    <div className="text-2xl font-bold text-gray-800 text-center">
                      {defectType.name}
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="bg-white rounded-lg p-6 shadow-md border-8 border-green-500">
                <div className="text-2xl font-bold text-gray-800 text-center">
                  無欠点
                </div>
              </div>
            )}
          </div>

          {/* Right Side - Image */}
          <div className="flex-1 flex items-center justify-center">
            {imageUrl ? (
              <CleanImageWithBoundingBoxes
                imageUrl={imageUrl}
                boxes={defectData}
              />
            ) : (
              <div className="w-[600px] h-[400px] bg-gray-100 flex items-center justify-center rounded">
                <span className="text-gray-500">No image available</span>
              </div>
            )}
          </div>
        </div>

        {/* Footer with Close Button - Match InspectionDetailsModal style */}
        <div className="absolute bottom-6 left-1/2 transform -translate-x-1/2">
          <button
            onClick={onClose}
            className="bg-cyan-800 hover:bg-cyan-900 text-white font-bold text-lg px-4 py-1 rounded border-2 border-white transition-colors duration-200"
            type="button"
          >
            閉じる
          </button>
        </div>
      </div>
    </div>
  );
};

export default ImagePopupModal;