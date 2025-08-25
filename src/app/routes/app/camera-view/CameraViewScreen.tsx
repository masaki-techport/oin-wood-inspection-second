import React, { useState } from 'react';
import useNavigate from '@/hooks/use-navigate';
import { useCameraManagement } from '../inspection/hooks/useCameraManagement';
import { useDebugMode } from '@/hooks/use-settings';
import { CameraViewHeader, MainCameraDisplay, CameraPreviewModal } from './components';
import ResizableCameraModal from '@/components/modal/ResizableCameraModal';

/**
 * Main CameraViewScreen component
 * Provides a dedicated camera view accessible from the TOP screen
 */
const CameraViewScreen: React.FC = () => {
  const { navigate } = useNavigate();
  const { isDebugMode } = useDebugMode();
  const [showCameraModal, setShowCameraModal] = useState(false);

  // Use the camera management hook to handle camera operations
  const {
    image,
    isConnected,
    droppedFrame,
    selectedCameraType,
    handleCameraTypeChange,
    cameraError,
    networkStatus,
    clearError,
    stopCamera
  } = useCameraManagement();

  // Handle navigation back to TOP view
  const handleNavigateHome = async () => {
    // Stop camera before navigating
    if (stopCamera) {
      await stopCamera();
    }
    navigate('/');
  };

  return (
    <div className="h-screen bg-white flex flex-col">
      {/* Header */}
      <CameraViewHeader
        title="木材検査システム ピント調整​"
      />

      {/* Main Content Area */}
      <div className="flex-1 p-6 flex flex-col relative">
        {/* Debug Mode Camera Selection */}
        {isDebugMode && (
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6">
            <h3 className="text-lg font-medium text-yellow-800 mb-3">デバッグモード - カメラ選択</h3>
            <div className="flex items-center gap-4 mb-3">
              <label htmlFor="camera-type" className="text-sm font-medium text-yellow-700">
                カメラタイプ:
              </label>
              <select
                id="camera-type"
                value={selectedCameraType}
                onChange={(e) => handleCameraTypeChange(e.target.value as 'basler' | 'webcam' | 'usb')}
                className="border border-yellow-300 rounded-md px-3 py-1 bg-white focus:outline-none focus:ring-2 focus:ring-yellow-500 text-sm"
              >
                <option value="basler">Baslerカメラ</option>
                <option value="webcam">ウェブカメラ</option>
                <option value="usb">USBカメラ</option>
              </select>
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}></div>
                <span className="text-sm text-gray-600">
                  {isConnected ? '接続済み' : '未接続'}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${networkStatus.isOnline ? 'bg-blue-500' : 'bg-orange-500'}`}></div>
                <span className="text-sm text-gray-600">
                  {networkStatus.isOnline ? 'ネットワーク正常' : 'ネットワーク問題'}
                </span>
              </div>
            </div>
            {/* Network Configuration Info */}
            <div className="text-xs text-yellow-700 bg-yellow-100 rounded p-2">
              <div>API URL: {process.env.REACT_APP_API_URL || `http://${process.env.REACT_APP_BACKEND_HOST || 'localhost'}:${process.env.REACT_APP_BACKEND_PORT || '8000'}`}</div>
              <div>ネットワークモード: {process.env.REACT_APP_BACKEND_HOST && process.env.REACT_APP_BACKEND_HOST !== 'localhost' ? 'ON' : 'OFF'}</div>
            </div>
          </div>
        )}

        {/* Error Display */}
        {cameraError && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <h3 className="text-lg font-medium text-red-800 mb-2">カメラ接続エラー</h3>
                <p className="text-red-700 mb-2">{cameraError.message}</p>
                {cameraError.details && (
                  <p className="text-sm text-red-600 mb-3">詳細: {cameraError.details}</p>
                )}
                <div className="flex items-center gap-4">
                  <span className="text-sm text-red-600">
                    エラータイプ: {cameraError.type === 'network' ? 'ネットワーク' : 
                                 cameraError.type === 'hardware' ? 'ハードウェア' :
                                 cameraError.type === 'configuration' ? '設定' :
                                 cameraError.type === 'api' ? 'API' : '不明'}
                  </span>
                  {networkStatus.retryCount > 0 && (
                    <span className="text-sm text-red-600">
                      再試行回数: {networkStatus.retryCount}
                    </span>
                  )}
                </div>
              </div>
              <button
                onClick={clearError}
                className="ml-4 bg-red-100 hover:bg-red-200 text-red-800 px-3 py-1 rounded text-sm transition-colors"
              >
                エラーをクリア
              </button>
            </div>
          </div>
        )}

         {/* Camera Preview Modal Trigger (bigger version) */}
         <CameraPreviewModal
          image={image}
          isConnected={isConnected}
          selectedCameraType={selectedCameraType}
          droppedFrame={droppedFrame}
          onOpenModal={() => setShowCameraModal(true)}
        />

        {/* Resizable Camera Modal */}
        <ResizableCameraModal
          isOpen={showCameraModal}
          onClose={() => setShowCameraModal(false)}
          image={image}
          isConnected={isConnected}
          selectedCameraType={selectedCameraType}
          droppedFrame={droppedFrame}
        />

        {/* 完了 Button - Bottom Right */}
        <button
          onClick={() => handleNavigateHome()}
          className="absolute bottom-6 right-6 bg-cyan-800 hover:bg-cyan-900 text-white px-8 py-3 rounded text-lg font-medium transition-colors shadow-lg"
        >
          完了
        </button>
      </div>
    </div>
  );
};

export default CameraViewScreen;