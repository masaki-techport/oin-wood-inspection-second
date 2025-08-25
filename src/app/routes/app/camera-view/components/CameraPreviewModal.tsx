import React from 'react';
import { AlertTriangle } from 'lucide-react';

interface CameraPreviewModalProps {
  image: string | null;
  isConnected: boolean | null;
  selectedCameraType: string;
  droppedFrame?: boolean;
  onOpenModal: () => void;
}

/**
 * Component for displaying camera preview modal trigger (bigger version)
 */
const CameraPreviewModal: React.FC<CameraPreviewModalProps> = ({
  image,
  isConnected,
  selectedCameraType,
  droppedFrame = false,
  onOpenModal
}) => {
  const getCameraDisplayName = () => {
    switch (selectedCameraType) {
      case 'basler':
        return 'Baslerカメラ';
      case 'webcam':
        return 'ウェブカメラ';
      case 'usb':
        return 'USBカメラ';
      default:
        return 'Baslerカメラ';
    }
  };

  return (
    <div
      className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-[32rem] h-96 border-4 border-gray-700 bg-gray-800 rounded-lg overflow-hidden shadow-lg cursor-pointer hover:border-blue-500 transition-colors duration-200"
      onClick={onOpenModal}
      title="クリックして拡大表示"
    >
      <div className="w-full h-full">
        {image ? (
          <div className="relative w-full h-full">
            <img
              src={image}
              alt="Camera Feed"
              className="w-full h-full object-cover"
            />
            {droppedFrame && (
              <div className="absolute top-1 right-1 bg-yellow-100 border border-yellow-400 text-yellow-800 text-xs px-1 py-1 rounded flex items-center gap-1 z-20">
                <AlertTriangle className="w-2 h-2" />
              </div>
            )}
          </div>
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-gray-600">
            <p className="text-xs text-white">取得中...</p>
          </div>
        )}
      </div>

      {/* Camera Label */}
      <div className="absolute bottom-0 left-0 right-0 bg-gray-700 text-white text-sm text-center py-2 font-bold">
        {getCameraDisplayName()}
      </div>
    </div>
  );
};

export default CameraPreviewModal;