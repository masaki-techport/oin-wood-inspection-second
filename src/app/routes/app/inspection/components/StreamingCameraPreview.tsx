import React, { useState, useRef, useCallback } from 'react';
import { useCameraStream, configureCameraStream } from '../hooks/useStreamingData';

interface StreamingCameraPreviewProps {
  cameraType?: 'basler' | 'webcam';
  className?: string;
  onError?: (error: string) => void;
  showControls?: boolean;
}

export const StreamingCameraPreview: React.FC<StreamingCameraPreviewProps> = ({
  cameraType = 'basler',
  className = '',
  onError,
  showControls = true
}) => {
  const { streamUrl, isLoading, error, refreshStream } = useCameraStream(cameraType);
  const [imageLoaded, setImageLoaded] = useState(false);
  const [frameRate, setFrameRate] = useState(10);
  const [quality, setQuality] = useState(85);
  const [isConfiguring, setIsConfiguring] = useState(false);
  const imgRef = useRef<HTMLImageElement>(null);

  // Handle image load events
  const handleImageLoad = useCallback(() => {
    setImageLoaded(true);
  }, []);

  const handleImageError = useCallback(() => {
    setImageLoaded(false);
    if (onError) {
      onError('Failed to load camera stream');
    }
  }, [onError]);

  // Handle stream configuration
  const handleConfigureStream = useCallback(async () => {
    setIsConfiguring(true);
    try {
      await configureCameraStream(frameRate, quality);
      refreshStream(); // Refresh stream with new settings
    } catch (error) {
      console.error('Failed to configure stream:', error);
      if (onError) {
        onError('Failed to configure camera stream');
      }
    } finally {
      setIsConfiguring(false);
    }
  }, [frameRate, quality, refreshStream, onError]);

  // Handle manual refresh
  const handleRefresh = useCallback(() => {
    setImageLoaded(false);
    refreshStream();
  }, [refreshStream]);

  return (
    <div className={`streaming-camera-preview ${className}`}>
      {/* Camera Stream Display */}
      <div className="relative bg-gray-100 rounded-lg overflow-hidden">
        {streamUrl && (
          <img
            ref={imgRef}
            src={streamUrl}
            alt={`${cameraType} camera stream`}
            className="w-full h-auto"
            onLoad={handleImageLoad}
            onError={handleImageError}
            style={{ 
              display: imageLoaded ? 'block' : 'none',
              maxHeight: '400px',
              objectFit: 'contain'
            }}
          />
        )}
        
        {/* Loading Overlay */}
        {(isLoading || !imageLoaded) && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-200">
            <div className="text-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
              <p className="text-sm text-gray-600">Loading camera stream...</p>
            </div>
          </div>
        )}
        
        {/* Error Overlay */}
        {error && (
          <div className="absolute inset-0 flex items-center justify-center bg-red-50">
            <div className="text-center p-4">
              <div className="text-red-600 mb-2">
                <svg className="w-8 h-8 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <p className="text-sm text-red-600 mb-2">{error}</p>
              <button
                onClick={handleRefresh}
                className="px-3 py-1 bg-red-600 text-white text-sm rounded hover:bg-red-700"
              >
                Retry
              </button>
            </div>
          </div>
        )}
        
        {/* Stream Status Indicator */}
        <div className="absolute top-2 right-2">
          <div className={`flex items-center space-x-1 px-2 py-1 rounded text-xs ${
            imageLoaded ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'
          }`}>
            <div className={`w-2 h-2 rounded-full ${
              imageLoaded ? 'bg-green-500' : 'bg-yellow-500'
            }`}></div>
            <span>{imageLoaded ? 'LIVE' : 'CONNECTING'}</span>
          </div>
        </div>
      </div>

      {/* Stream Controls */}
      {showControls && (
        <div className="mt-4 p-4 bg-gray-50 rounded-lg">
          <h4 className="text-sm font-medium text-gray-700 mb-3">Stream Settings</h4>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Frame Rate Control */}
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Frame Rate: {frameRate} FPS
              </label>
              <input
                type="range"
                min="1"
                max="30"
                value={frameRate}
                onChange={(e) => setFrameRate(parseInt(e.target.value))}
                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
              />
            </div>
            
            {/* Quality Control */}
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Quality: {quality}%
              </label>
              <input
                type="range"
                min="10"
                max="100"
                value={quality}
                onChange={(e) => setQuality(parseInt(e.target.value))}
                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
              />
            </div>
          </div>
          
          {/* Control Buttons */}
          <div className="flex space-x-2 mt-4">
            <button
              onClick={handleConfigureStream}
              disabled={isConfiguring}
              className="px-4 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:opacity-50"
            >
              {isConfiguring ? 'Applying...' : 'Apply Settings'}
            </button>
            
            <button
              onClick={handleRefresh}
              className="px-4 py-2 bg-gray-600 text-white text-sm rounded hover:bg-gray-700"
            >
              Refresh Stream
            </button>
          </div>
        </div>
      )}
    </div>
  );
};