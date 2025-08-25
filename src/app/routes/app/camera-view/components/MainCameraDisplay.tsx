import React from 'react';
import { AlertTriangle } from 'lucide-react';
import { MainCameraDisplayProps } from '../types';



/**
 * Main Camera Display Component
 * Displays the camera feed without zoom controls, matching the sample layout
 */
const MainCameraDisplay: React.FC<MainCameraDisplayProps> = ({
  image,
  isConnected,
  droppedFrame
}) => {

  return (
    <div className="relative w-full h-full bg-gray-50 border-2 border-red-400 rounded-lg flex items-center justify-center">
      {/* Frame Drop Warning */}
      {droppedFrame && (
        <div className="absolute top-4 left-4 z-10">
          <div className="flex items-center space-x-1 bg-yellow-100 text-yellow-800 text-xs px-2 py-1 rounded-full border border-yellow-300">
            <AlertTriangle className="w-3 h-3" />
            <span>フレームドロップ</span>
          </div>
        </div>
      )}

      {/* Camera Content */}
      {isConnected && image ? (
        <img
          src={image}
          alt="Camera Feed"
          className="w-full h-full object-contain rounded-lg"
        />
      ) : (
        <div className="flex flex-col items-center justify-center text-gray-500">
          <AlertTriangle className="w-16 h-16 mb-4" />
          <span className="text-lg font-medium">
            {isConnected === false ? 'カメラが接続されていません' : 'カメラを読み込み中...'}
          </span>
        </div>
      )}
    </div>
  );
};

export default MainCameraDisplay;