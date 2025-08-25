import React from 'react';
import { TransformWrapper, TransformComponent } from 'react-zoom-pan-pinch';
import { AlertTriangle } from 'lucide-react';
import { CameraPreviewProps } from '../types';

/**
 * Component for displaying camera preview
 */
const CameraPreview: React.FC<CameraPreviewProps> = ({
  image,
  isConnected,
  selectedCameraType,
  droppedFrame,
  onOpenModal
}) => {
  return (
    <div 
      className="absolute bottom-6 left-6 w-36 h-28 border-4 border-gray-700 bg-gray-800 rounded-lg overflow-hidden shadow-lg cursor-pointer hover:border-blue-500 transition-colors duration-200"
      onClick={onOpenModal}
      title="クリックして拡大表示"
    >
      <div className="w-full h-full">
        <TransformWrapper>
          {() => (
            <TransformComponent>
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
                  {isConnected === false ? (
                    <div className="text-center text-white text-xs">
                      <p>{selectedCameraType === 'webcam' ? 'ウェブカメラ' : 
                          selectedCameraType === 'usb' ? 'USBカメラ' : 'Baslerカメラ'}</p>
                      <p>未接続</p>
                    </div>
                  ) : (
                    <p className="text-xs text-white">取得中...</p>
                  )}
                </div>
              )}
            </TransformComponent>
          )}
        </TransformWrapper>
      </div>
      
      {/* Camera Label */}
      <div className="absolute bottom-0 left-0 right-0 bg-gray-700 text-white text-xs text-center py-1 font-bold">
        {selectedCameraType === 'webcam' ? 'ウェブカメラ' : 
          selectedCameraType === 'usb' ? 'USBカメラ' : 'Baslerカメラ'}
      </div>
    </div>
  );
};

export default CameraPreview;