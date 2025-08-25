import React, { useState, useEffect } from 'react';
import InspectionDetailsModal from '@/components/modal/InspectionDetailsModal';
import ResizableCameraModal from '@/components/modal/ResizableCameraModal';
import { 
  InspectionHeader, 
  ControlPanel, 
  InspectionDisplay, 
  CameraPreview, 
  DebugPanel 
} from './components';
import { 
  useCameraManagement, 
  useInspectionState, 
  useSensorMonitoring, 
  useDebugMode,
  useCameraSettings
} from './hooks';
import { getImageUrl } from './utils';

// Add TypeScript declaration
declare global {
  interface Window {
    debugFallbackImageLoading?: boolean;
    enableDebugToggle?: boolean;
  }
}

/**
 * Main InspectionScreen component
 */
const InspectionScreen: React.FC = () => {
  // Camera settings hook
  const { showCameraUI } = useCameraSettings();

  // Camera management hook - pass showCameraUI to control preview polling
  const { 
    image, 
    isConnected, 
    droppedFrame, 
    selectedCameraType, 
    handleCameraTypeChange,
    stopCamera
  } = useCameraManagement(showCameraUI);

  // Inspection state hook
  const { 
    status, 
    inspectionResult, 
    defectType, 
    measurements, 
    createdInspectionId, 
    presentationImages, 
    loadingPresentationImages, 
    selectedInspection, 
    showDetail, 
    handleShowDetail, 
    setShowDetail, 
    loadPresentationImages 
  } = useInspectionState();

  // Sensor monitoring hook
  const { 
    sensorStatus, 
    aiThreshold, 
    setAiThreshold, 
    handleStart, 
    handleStop, 
    triggerTestSequence, 
    toggleSensorA, 
    toggleSensorB 
  } = useSensorMonitoring(selectedCameraType);

  // Effect to update inspection result and status from sensor status
  useEffect(() => {
    if (sensorStatus) {
      // Make sensor status globally accessible for components that need inspection results
      (window as any).sensorStatus = sensorStatus;
      
      // Update inspection data if available
      if (sensorStatus.inspection_data && (window as any).updateInspectionResultFromSensorStatus) {
        // Call the function exposed by useInspectionState
        (window as any).updateInspectionResultFromSensorStatus(sensorStatus);
      }
      
      // Determine status based on sensor state and active status
      let statusValue = '待機中'; // Default status
      
      if (!sensorStatus.active) {
        // If stopping was requested, show 停止 briefly
        if ((window as any).stoppingRequested) {
          statusValue = '停止';
        } else {
          statusValue = '待機中';
        }
      } else if (sensorStatus.active) {
        // System is active
        if (sensorStatus.sensor_a || sensorStatus.sensor_b || 
            (sensorStatus.sensors && (sensorStatus.sensors.sensor_a || sensorStatus.sensors.sensor_b))) {
          // Sensors are active - processing
          statusValue = '処理中';
        } else {
          // No sensors triggered yet - searching
          statusValue = '検査中';
        }
      }
      
      // Update status if updateStatus function is available
      if ((window as any).updateStatus) {
        (window as any).updateStatus(statusValue);
      }
    }
  }, [sensorStatus]);
  
  // Mark stopping as requested when stop button is pressed
  const handleStopWithStatus = async () => {
    if ((window as any).updateStatus) {
      (window as any).updateStatus('停止');
      (window as any).stoppingRequested = true;
    }
    
    // Call the actual stop handler
    await handleStop();
    
    // Clear the stopping flag after a delay
    setTimeout(() => {
      (window as any).stoppingRequested = false;
      if ((window as any).updateStatus) {
        (window as any).updateStatus('待機中');
      }
    }, 1000); // Show '停止' for 1 second before switching to '待機中'
  };

  // Debug mode hook
  const { 
    debugMode, 
    showDebugPanel,
    setShowDebugPanel,
    recentInspections, 
    loadingInspections, 
    loadRecentInspections, 
    testImage 
  } = useDebugMode();

  // We no longer force showDebugPanel to be true initially
  // The useDebugMode hook will handle this based on settings.ini

  // Camera modal state
  const [showCameraModal, setShowCameraModal] = useState(false);

  // Handle top button click
  const handleTop = async () => {
    // Stop camera before navigating
    if (stopCamera) {
      await stopCamera();
    }
    window.location.href = '/';
  };

  return (
    <div className="h-screen bg-white flex flex-col">
      {/* Header */}
      <InspectionHeader title="木材検査システム 検査" />

      {/* Control Panel */}
      <ControlPanel
        selectedCameraType={selectedCameraType}
        onCameraTypeChange={handleCameraTypeChange}
        aiThreshold={aiThreshold}
        setAiThreshold={setAiThreshold}
        status={status}
        onStart={handleStart}
        onStop={handleStopWithStatus}
        onTop={handleTop}
        isActive={sensorStatus.active}
        debugMode={debugMode}
        isSimulationMode={sensorStatus.simulation_mode}
        showCameraSettings={showCameraUI}
        onTriggerTest={triggerTestSequence}
        onToggleSensorA={toggleSensorA}
        onToggleSensorB={toggleSensorB}
        sensorAActive={sensorStatus.sensor_a}
        sensorBActive={sensorStatus.sensor_b}
      />

      {/* Main Content Area */}
      <div className="flex-1 p-6 relative">
        {/* Main Inspection Display */}
        <InspectionDisplay
          inspectionResult={inspectionResult}
          defectType={defectType}
          measurements={measurements}
          presentationImages={presentationImages}
          loadingPresentationImages={loadingPresentationImages}
          createdInspectionId={createdInspectionId}
          onShowDetail={handleShowDetail}
          onImageTest={testImage}
        />

        {/* Camera Preview - Only show when showCameraUI is true */}
        {showCameraUI && (
          <CameraPreview
            image={image}
            isConnected={isConnected}
            selectedCameraType={selectedCameraType}
            droppedFrame={droppedFrame}
            onOpenModal={() => setShowCameraModal(true)}
          />
        )}

        {/* Modals */}
        {showDetail && selectedInspection && (
          <InspectionDetailsModal
            inspection={selectedInspection}
            onClose={() => setShowDetail(false)}
          />
        )}

        <ResizableCameraModal
          isOpen={showCameraModal}
          onClose={() => setShowCameraModal(false)}
          image={image}
          isConnected={isConnected}
          selectedCameraType={selectedCameraType}
          droppedFrame={droppedFrame}
        />

        {/* Debug Panel - Only shown when debug_mode and show_debug_panel are both enabled in settings.ini */}
        {debugMode && (
          <>
            <DebugPanel
              debugMode={debugMode}
              createdInspectionId={createdInspectionId}
              presentationImages={presentationImages}
              loadPresentationImages={loadPresentationImages}
              loadRecentInspections={loadRecentInspections}
              recentInspections={recentInspections}
              loadingPresentationImages={loadingPresentationImages}
              loadingInspections={loadingInspections}
              onImageTest={testImage}
              showDebugPanel={showDebugPanel}
              setShowDebugPanel={setShowDebugPanel}
            />

            {/* Debug Mode Toggle - Only visible when debug mode is enabled */}
            <div className="mt-2 flex justify-center">
              <button
                onClick={() => {
                  const newValue = !showDebugPanel;
                  setShowDebugPanel(newValue);
                  // No longer automatically loading inspections when opening the panel
                }}
                className="text-xs bg-gray-200 hover:bg-gray-300 text-gray-700 px-3 py-1 rounded border"
              >
                Debug Panel: {showDebugPanel ? 'HIDE' : 'SHOW'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

// Use named export to fix the TypeScript error in routes/index.tsx
export { InspectionScreen };
// Also keep default export for backward compatibility
export default InspectionScreen;