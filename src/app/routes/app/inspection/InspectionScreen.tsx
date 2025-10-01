import React, { useState, useEffect, useCallback } from 'react';
import InspectionDetailsModal from '@/components/modal/InspectionDetailsModal';
import ResizableCameraModal from '@/components/modal/ResizableCameraModal';
import useNavigate from '@/hooks/use-navigate';
import BrowserNavigationDialog from './components/BrowserNavigationDialog';
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
  useCameraSettings,
  useBrowserNavigation
} from './hooks';
import { useStatusManager } from './hooks/useStatusManager';
import { getImageUrl } from './utils';
import { setSensorStatus, getUpdateInspectionResultFromSensorStatus } from './utils/stateManager';
import ErrorBoundary from './components/ErrorBoundary';
import DataConflictErrorBoundary from './components/DataConflictErrorBoundary';

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
  // Navigation hook
  const { navigate } = useNavigate();

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

  // Status manager hook - single source of truth for status
  const { 
    status, 
    updateStatusFromSensor
  } = useStatusManager();

  // Inspection state hook
  const { 
    inspectionResult, 
    defectType, 
    createdInspectionId, 
    presentationImages, 
    loadingPresentationImages, 
    selectedInspection, 
    showDetail, 
    handleShowDetail, 
    setShowDetail, 
    loadPresentationImages,
    clearInspectionResults
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

  // Clear any stale last-inspection result on first open
  useEffect(() => {
    try {
      // Clear hook-managed state if available
      if ((window as any).clearInspectionResults) {
        (window as any).clearInspectionResults();
      }

      // Clear any globally cached sensor results to avoid auto display
      if ((window as any).sensorStatus) {
        (window as any).sensorStatus.inspection_results = null;
        (window as any).sensorStatus.inspection_results_loading = false;
        (window as any).sensorStatus.inspection_results_error = null;
      }

      // Reset current inspection id so ResultDisplay won't fetch old DB data
      (window as any).inspectionId = null;
    } catch (e) {
      // no-op
    }
  }, []);

  // Effect to update inspection result and status from sensor status
  useEffect(() => {
    if (sensorStatus) {
      // Store sensor status in centralized state manager
      setSensorStatus(sensorStatus);
      
      // Get the update function from state manager and call it
      const updateFunction = getUpdateInspectionResultFromSensorStatus();
      if (sensorStatus.inspection_data && updateFunction) {
        updateFunction(sensorStatus);
      }
      
      // Update status using centralized status manager (includes immediate sensor detection)
      updateStatusFromSensor(sensorStatus);
    }
  }, [sensorStatus, updateStatusFromSensor]);


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
  const [isNavigatingHome, setIsNavigatingHome] = useState(false);

  // Handle top button click with immediate feedback
  const handleTop = async () => {
    console.log('[INSPECTION] TOP button clicked - navigating to home');
    
    // Set loading state immediately for instant feedback
    setIsNavigatingHome(true);
    
    // Navigate immediately without waiting for camera to stop
    navigate('/');
    
    // Stop camera in background (don't await to prevent blocking navigation)
    if (stopCamera) {
      stopCamera().catch((error) => {
        console.error('[INSPECTION] Error stopping camera:', error);
      });
    }
  };
  
  // Browser navigation handling
  const {
    showConfirmDialog,
    confirmDialogProps,
    handleNavigationAction
  } = useBrowserNavigation({
    status,
    sensorStatus,
    stopInspection: async () => {
      // First stop the inspection
      await handleStop();
      
      // Then explicitly stop the camera
      if (stopCamera) {
        try {
          await stopCamera();
          console.log('[NAVIGATION] Camera successfully stopped');
        } catch (error) {
          console.error('[NAVIGATION] Error stopping camera:', error);
        }
      }
    }
  });
  
  // Create a function to handle the back button press
  const handleBackButton = useCallback(() => {
    handleNavigationAction('back');
  }, [handleNavigationAction]);
  
  // Create a function to handle the close button press
  const handleCloseButton = useCallback(() => {
    handleNavigationAction('close');
  }, [handleNavigationAction]);
  
  // Create a function to handle the refresh button press
  const handleRefreshButton = useCallback(() => {
    handleNavigationAction('refresh');
  }, [handleNavigationAction]);
  
  // Expose these handlers for external use
  useEffect(() => {
    (window as any).handleInspectionBackButton = handleBackButton;
    (window as any).handleInspectionCloseButton = handleCloseButton;
    (window as any).handleInspectionRefreshButton = handleRefreshButton;
    
    // Add history entry when component mounts
    // This ensures the back button can be captured
    window.history.pushState({ inspectionScreen: true }, document.title, window.location.href);
    
    return () => {
      delete (window as any).handleInspectionBackButton;
      delete (window as any).handleInspectionCloseButton;
      delete (window as any).handleInspectionRefreshButton;
    };
  }, [handleBackButton, handleCloseButton, handleRefreshButton]);

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
        onStop={handleStop}
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
        isNavigatingHome={isNavigatingHome}
      />

      {/* Main Content Area */}
      <div className="flex-1 p-6 relative">
        {/* Main Inspection Display with Error Boundaries */}
        <ErrorBoundary
          resetOnPropsChange={true}
          resetKeys={[inspectionResult, defectType, createdInspectionId?.toString() || '']}
          onError={(error, errorInfo) => {
            console.error('InspectionDisplay error:', error, errorInfo);
          }}
        >
          <DataConflictErrorBoundary
            dataSource="inspection-display"
            onDataConflict={(error, dataSource) => {
              console.error(`Data conflict in ${dataSource}:`, error);
            }}
          >
            <InspectionDisplay
              inspectionResult={inspectionResult}
              defectType={defectType}
              presentationImages={presentationImages}
              loadingPresentationImages={loadingPresentationImages}
              createdInspectionId={createdInspectionId}
              onShowDetail={handleShowDetail}
              onImageTest={testImage}
              hideResults={showDetail}
              onOpenDetails={(id, options) => {
                // Open details, then (after modal mounts) programmatically trigger the same image popup
                handleShowDetail(id).then(() => {
                  if (options?.group || options?.imagePath) {
                    // Store the intent on window for the modal to read and open the popup
                    (window as any).__inspectionOpenImageIntent = options;
                  }
                });
              }}
            />
          </DataConflictErrorBoundary>
        </ErrorBoundary>

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
      
      {/* Confirmation Dialog for browser navigation */}
      <BrowserNavigationDialog
        open={showConfirmDialog}
        onClose={confirmDialogProps.onClose}
        onConfirm={confirmDialogProps.onConfirm}
        title={confirmDialogProps.title}
        content={confirmDialogProps.content}
      />
    </div>
  );
};

// Use named export to fix the TypeScript error in routes/index.tsx
export { InspectionScreen };
// Also keep default export for backward compatibility
export default InspectionScreen;