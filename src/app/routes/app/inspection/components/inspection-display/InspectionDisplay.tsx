import React, { useMemo, useState, useEffect } from 'react';
import { InspectionDisplayProps } from '../../types';
import { useSensorData } from '../../hooks/useSensorData';
import ResultDisplay from './ResultDisplay';
import PresentationImagesGrid from './PresentationImagesGrid';
import MeasurementsDisplay from './MeasurementsDisplay';
import { getBackgroundColor } from '../../utils/colorManager';

/**
 * Main component for displaying inspection results and images
 */
const InspectionDisplay: React.FC<InspectionDisplayProps> = ({
  inspectionResult,
  defectType,
  presentationImages,
  loadingPresentationImages,
  createdInspectionId,
  onShowDetail,
  onImageTest,
  onOpenDetails,
  hideResults
}) => {
  // Use the same data source as ResultDisplay for consistency
  const { batchResult, sensorStatus } = useSensorData();
  
  // Use batchResult (same as ResultDisplay) instead of inspectionResult prop
  const actualInspectionResult = batchResult || inspectionResult;
  
  // Debug mode state
  const [debugMode, setDebugMode] = useState(false);
  
  // Check debug mode from settings
  useEffect(() => {
    const checkDebugMode = async () => {
      try {
        const response = await fetch('/api/settings/current');
        if (response.ok) {
          const data = await response.json();
          setDebugMode(data.debug_mode === 1);
        }
      } catch (error) {
        console.log('Could not load debug mode setting, defaulting to false');
      }
    };
    
    checkDebugMode();
  }, []);

  // Expose debug mode toggle function globally for testing
  useEffect(() => {
    (window as any).toggleDebugMode = () => {
      setDebugMode(prev => !prev);
      console.log('Debug mode toggled:', !debugMode);
    };
    
    (window as any).setDebugMode = (enabled: boolean) => {
      setDebugMode(enabled);
      console.log('Debug mode set to:', enabled);
    };

    (window as any).checkDebugModeSetting = async () => {
      try {
        const response = await fetch('/api/settings/current');
        if (response.ok) {
          const data = await response.json();
          const currentDebugMode = data.debug_mode === 1;
          console.log('Current debug mode setting from backend:', currentDebugMode);
          setDebugMode(currentDebugMode);
          return currentDebugMode;
        }
      } catch (error) {
        console.error('Could not check debug mode setting:', error);
        return false;
      }
    };

    return () => {
      delete (window as any).toggleDebugMode;
      delete (window as any).setDebugMode;
      delete (window as any).checkDebugModeSetting;
    };
  }, [debugMode]);
  
  // Determine if we are in a new circle/processing state where temp sections are shown
  const isProcessing = useMemo(() => {
    try {
      const ss: any = sensorStatus as any;
      return Boolean(
        ss?.sensors?.clear_requested === true ||
        ss?.capture?.processing_active === true ||
        ss?.processing_active === true ||
        ss?.capture?.status === '処理中'
      );
    } catch (_) {
      return false;
    }
  }, [sensorStatus]);

  // Use neutral background during processing/temp presentation; otherwise map by result
  const backgroundColorClass = useMemo(() => {
    if (isProcessing) {
      return 'bg-gray-200';
    }
    return getBackgroundColor(actualInspectionResult);
  }, [isProcessing, actualInspectionResult]);

  // Fixed 5-group mode only when:
  //  - not processing, and
  //  - we have presentation images belonging to the current createdInspectionId (fresh set)
  const isFixedGroupsMode = useMemo(() => {
    if (isProcessing) return false;
    if (!Array.isArray(presentationImages) || presentationImages.length === 0) return false;
    if (createdInspectionId == null) return false;
    const allMatchCurrent = presentationImages.every(img => img?.inspection_id === createdInspectionId);
    return allMatchCurrent;
  }, [isProcessing, presentationImages, createdInspectionId]);

  return (
    <div className={`h-full ${backgroundColorClass} border-4 border-teal-600 rounded-lg relative`}>
      {/* Current Inspection ID Display - Only shown when debug mode is enabled */}
      {debugMode && createdInspectionId && (
        <div className="absolute top-4 left-1/2 transform -translate-x-1/2 z-20">
          <div className="bg-white border-4 border-red-600 rounded-lg px-8 py-4 shadow-2xl">
            <div className="text-center">
              <div className="text-2xl font-bold text-gray-800 mb-2">
                現在の検査ID
              </div>
              <div className="text-4xl font-bold text-red-600">
                {createdInspectionId}
              </div>
              <div className="text-lg text-gray-600 mt-2">
                {new Date().toLocaleDateString('ja-JP')} {new Date().toLocaleTimeString('ja-JP')}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Debug Mode Indicator - Shows when debug mode is active */}
      {debugMode && (
        <div className="absolute top-4 left-4 z-20">
          <div className="bg-red-600 border-2 border-white rounded-lg px-3 py-1 shadow-lg">
            <div className="text-center">
              <div className="text-xs font-bold text-white">
                DEBUG MODE
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Debug Component - Shows inspection results text when debug mode is enabled */}
      {debugMode && actualInspectionResult && (
        <div className="absolute top-4 right-4 z-20">
          <div className="bg-yellow-400 border-4 border-orange-600 rounded-lg px-6 py-3 shadow-2xl">
            <div className="text-center">
              <div className="text-lg font-bold text-gray-800 mb-1">
                DEBUG: 検査結果
              </div>
              <div className="text-3xl font-bold text-orange-700">
                {actualInspectionResult}
              </div>
              {defectType && (
                <div className="text-sm font-semibold text-gray-700 mt-1">
                  {defectType}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Result Display - show only with fixed 5-group presentation images */}
      {isFixedGroupsMode && (
        <ResultDisplay 
          inspectionResult={inspectionResult} 
          defectType={defectType} 
          titleOnly={Boolean(hideResults)}
        />
      )}

      {/* Captured Image Display or Sample Sections */}
      <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-full max-w-[98vw]">
        {/* Always show PresentationImagesGrid - it handles its own display logic based on status */}
        <div className="bg-white rounded-lg shadow-xl container-responsive inspection-presentation-container">
          <PresentationImagesGrid
            presentationImages={presentationImages}
            loading={loadingPresentationImages}
            onImageTest={onImageTest}
            onOpenDetails={onOpenDetails || (createdInspectionId !== null ? () => onShowDetail(createdInspectionId) : undefined)}
          />

          {/* Only show detail button when we have inspection results and fixed groups */}
          {isFixedGroupsMode && actualInspectionResult && (
            <button
              className="bg-cyan-800 text-white px-6 py-2 rounded mx-auto mt-3 block text-responsive-lg"
              onClick={() => {
                if (createdInspectionId !== null) onShowDetail(createdInspectionId);
              }}
              disabled={createdInspectionId === null}
            >
              検査結果詳細​
            </button>
          )}
        </div>
      </div>

      {/* Measurements Section - show only with fixed groups */}
      {isFixedGroupsMode && <MeasurementsDisplay />}

      {/* Debug Info Panel - Shows detailed debug information when debug mode is enabled */}
      {debugMode && (
        <div className="absolute bottom-4 left-4 z-20">
          <div className="bg-blue-900 border-4 border-blue-600 rounded-lg px-4 py-3 shadow-2xl max-w-xs">
            <div className="text-center">
              <div className="text-sm font-bold text-white mb-2">
                DEBUG INFO
              </div>
              <div className="text-xs text-blue-200 space-y-1">
                <div>ID: {createdInspectionId || 'N/A'}</div>
                <div>Result: {actualInspectionResult || 'N/A'}</div>
                <div>Defect: {defectType || 'N/A'}</div>
                <div>Images: {presentationImages.length}</div>
                <div>Loading: {loadingPresentationImages ? 'Yes' : 'No'}</div>
                <div>Time: {new Date().toLocaleTimeString('ja-JP')}</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default React.memo(InspectionDisplay);