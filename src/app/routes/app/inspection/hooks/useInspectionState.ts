import { useState, useEffect, useRef, useCallback } from 'react';
import { useNotifications } from '@/components/ui/notifications';
import { fetchInspectionDetailsById, fetchLatestPresentationImages, PresentationImage } from '@/features/inspections/api/inspections-details';
import { Inspection } from '@/types/api';
import { UseInspectionStateReturn, PresentationImagesUpdatedEvent, InspectionSavedEvent, SensorStatus } from '../types';
import { fetchLatestPresentationImagesWithRetry } from '../utils';
import { determineInspectionResult, determineDefectType } from '../utils/colorManager';
import { usePresentationImageManager } from './usePresentationImageManager';
import { useInspectionIdManager } from './useInspectionIdManager';
import { eventManager, EVENTS, InspectionDataUpdateEvent, PresentationImagesUpdatedEvent as EventPresentationImagesUpdatedEvent, InspectionSavedEvent as EventInspectionSavedEvent } from '../utils/eventManager';
import { stateManager, setInspectionId, setSensorStatus, setUpdateInspectionResultFromSensorStatus, setLoadLatestPresentationImages, setClearPresentationImages, setForceLoadLatestInspection, setStopPollingPresentationImages, setForceRefreshCurrentInspection } from '../utils/stateManager';
import { useDataValidation } from '../utils/dataValidator';
import { useDataConsistencyMonitoring } from '../utils/dataConsistencyMonitor';

/**
 * Hook for managing inspection state
 * @returns Inspection state and functions
 */
export const useInspectionState = (): UseInspectionStateReturn => {
  // Status is now managed by useStatusManager - removed from here
  const [inspectionResult, setInspectionResult] = useState('');
  const [defectType, setDefectType] = useState('');
  const [showDetail, setShowDetail] = useState(false);
  const [selectedInspection, setSelectedInspection] = useState<Inspection | null>(null);
  
  // Use centralized inspection ID manager
  const {
    inspectionId: createdInspectionId,
    setCurrentInspectionId,
    clearInspectionId
  } = useInspectionIdManager();

  // Use centralized presentation image manager
  const {
    presentationImages,
    loadingPresentationImages,
    loadPresentationImages,
    clearPresentationImages,
    stopPolling,
    setPresentationImagesDirect
  } = usePresentationImageManager();

  const { addNotification } = useNotifications();

  // Data validation and consistency monitoring
  const { validateInspectionData, getValidationStats } = useDataValidation();
  const { startMonitoring, stopMonitoring, getConsistencyStats } = useDataConsistencyMonitoring();

  // Function to clear inspection results (called when starting new inspection)
  const clearInspectionResults = useCallback(() => {
    setInspectionResult('');
    setDefectType('');
    // Use centralized managers
    clearInspectionId();
    clearPresentationImages();
  }, [clearInspectionId, clearPresentationImages]);

  // Function to handle inspection data updates
  const handleInspectionDataUpdate = (inspectionData: any) => {
    console.log('🔍 Handling inspection data update:', inspectionData);
    
    if (!inspectionData) return;

    // Store previous values to check if we need to update
    const prevInspectionId = createdInspectionId;
    const hadPresentationImages = presentationImages && presentationImages.length > 0;

    // Handle presentation images first to avoid images disappearing
    if (inspectionData.presentation_images && Array.isArray(inspectionData.presentation_images) &&
      inspectionData.presentation_images.length > 0) {
      console.log(`🔍 Found ${inspectionData.presentation_images.length} presentation images in inspection data`);
      // Note: Presentation images are now managed by the centralized manager
    }

    // Verify this is actually the latest inspection ID
    fetchLatestPresentationImages().then(latestResult => {
      if (latestResult.result && latestResult.data) {
        const latestId = latestResult.data.inspection_id;
        if (inspectionData.inspection_id < latestId) {
          console.log(`⚠️ Received old inspection ID ${inspectionData.inspection_id}, latest is ${latestId}. Using latest instead.`);
          setCurrentInspectionId(latestId);

          // Load images for the latest inspection
          if (latestResult.data.images && latestResult.data.images.length > 0) {
            setPresentationImagesDirect(latestResult.data.images, latestId);
          } else {
            loadPresentationImages(latestId);
          }
        } else {
          // Use the received inspection ID as it's current
          setCurrentInspectionId(inspectionData.inspection_id);
        }
      } else {
        // Fallback to using the received ID
        setCurrentInspectionId(inspectionData.inspection_id);
      }
    }).catch(() => {
      // Fallback to using the received ID
      setCurrentInspectionId(inspectionData.inspection_id);
    });

    // Clear old presentation images when starting a new inspection
    if (prevInspectionId && prevInspectionId !== inspectionData.inspection_id) {
      console.log('🔄 New inspection detected, clearing old presentation images');
      clearPresentationImages();
    }

    // Update inspection result and defect type using centralized logic
    const newInspectionResult = determineInspectionResult(inspectionData);
    const newDefectType = determineDefectType(inspectionData);

    // Only update if the result has actually changed
    if (newInspectionResult !== inspectionResult) {
      console.log(`🔍 Updating inspection result: ${inspectionResult} → ${newInspectionResult}`);
      setInspectionResult(newInspectionResult);
    }

    if (newDefectType !== defectType) {
      console.log(`🔍 Updating defect type: ${defectType} → ${newDefectType}`);
      setDefectType(newDefectType);
    }

    // Handle presentation images - always poll continuously regardless of ready status
    if (inspectionData.inspection_id) {
      if (inspectionData.presentation_ready === true) {
        console.log('🔍 Presentation images marked as ready, starting continuous polling');
        loadPresentationImages(inspectionData.inspection_id);
      } else {
        console.log('🔍 Presentation images not ready, starting continuous polling anyway');
        loadPresentationImages(inspectionData.inspection_id);
      }
    }
  };

  // Function to update inspection result from sensor status
  const updateInspectionResultFromSensorStatus = (sensorStatus: SensorStatus) => {
    console.log('🔍 Updated inspection results from sensor status:', sensorStatus);

    // Extract inspection ID from sensor status (this should be the newest one)
    const sensorInspectionId = sensorStatus.inspection_data?.inspection_id;
    if (sensorInspectionId && sensorInspectionId !== createdInspectionId) {
      console.log(`🆔 Sensor status has new inspection ID: ${createdInspectionId} → ${sensorInspectionId}`);
      setCurrentInspectionId(sensorInspectionId);

      // Clear old presentation images for new inspection
      clearPresentationImages();

      // Start loading presentation images for the new inspection
      loadPresentationImages(sensorInspectionId);
    }

    // Update inspection result and defect type using centralized logic
    if (sensorStatus.inspection_data) {
      // Extract the necessary parameters from inspection data
      const inspectionData = sensorStatus.inspection_data;
      const hasKnot = inspectionData.results === 'こぶし' || inspectionData.results === '節あり';
      
      // Calculate max knot length from inspection details
      const maxKnotLength = inspectionData.inspection_details?.reduce((max, detail) => 
        Math.max(max, detail.length || 0), 0) || 0;
      
      // Check for holes and discoloration from inspection details
      const hasHole = inspectionData.inspection_details?.some(detail => 
        detail.error_type_name?.includes('穴') || detail.error_type_name?.includes('hole')) || false;
      const hasDiscoloration = inspectionData.inspection_details?.some(detail => 
        detail.error_type_name?.includes('変色') || detail.error_type_name?.includes('discoloration')) || false;
      
      const newInspectionResult = determineInspectionResult(hasKnot, maxKnotLength, hasHole, hasDiscoloration);
      const newDefectType = determineDefectType(hasHole, hasDiscoloration);

      // Validate the data before updating
      const validationResult = validateInspectionData({
        inspectionId: inspectionData.inspection_id || 0,
        inspectionResult: newInspectionResult,
        defectType: newDefectType,
        measurements: '', // Will be calculated by measurement manager
        presentationImages: Array.isArray(presentationImages) ? presentationImages : [],
        sensorStatus: sensorStatus,
        timestamp: Date.now()
      });

      if (!validationResult.isValid) {
        console.warn('Data validation failed:', validationResult.errors);
        addNotification({
          type: 'warning',
          title: 'データ検証エラー',
          message: `データの整合性に問題があります: ${validationResult.errors.map(e => e.message).join(', ')}`
        });
      }

      if (validationResult.warnings.length > 0) {
        console.warn('Data validation warnings:', validationResult.warnings);
      }

      if (newInspectionResult !== inspectionResult) {
        console.log(`🔍 Updating inspection result from sensor: ${inspectionResult} → ${newInspectionResult}`);
        setInspectionResult(newInspectionResult);
      }

      if (newDefectType !== defectType) {
        console.log(`🔍 Updating defect type from sensor: ${defectType} → ${newDefectType}`);
        setDefectType(newDefectType);
      }
    }
  };

  // Effect to load presentation images when inspection ID changes
  useEffect(() => {
    if (createdInspectionId) {
      console.log(`🆔 Inspection ID changed to ${createdInspectionId}, loading images...`);
      loadPresentationImages(createdInspectionId);
    }
  }, [createdInspectionId, loadPresentationImages]);

  // Effect to start data consistency monitoring
  useEffect(() => {
    console.log('🔍 Starting data consistency monitoring...');
    startMonitoring(5000); // Check every 5 seconds

    return () => {
      console.log('🔍 Stopping data consistency monitoring...');
      stopMonitoring();
    };
  }, [startMonitoring, stopMonitoring]);

  // Effect to listen for presentation ready events
  useEffect(() => {
    const handlePresentationReady = (data: any) => {
      const { inspectionId } = data;
      if (inspectionId && inspectionId === createdInspectionId) {
        console.log(`🔍 Presentation images ready for inspection ${inspectionId}, loading immediately...`);
        loadPresentationImages(inspectionId);
      }
    };

    const unsubscribe = eventManager.on(EVENTS.PRESENTATION_IMAGES_READY, handlePresentationReady);

    return unsubscribe;
  }, [createdInspectionId, loadPresentationImages]);

  // Custom event for updating inspection results from sensor data
  useEffect(() => {
    const handleInspectionDataUpdateEvent = (data: InspectionDataUpdateEvent) => {
      const inspectionData = data.inspectionData;
      if (!inspectionData) return;

      console.log('🔍 Received inspection data update:', inspectionData);
      handleInspectionDataUpdate(inspectionData);
    };

    // Register the event listener
    const unsubscribe = eventManager.on(EVENTS.INSPECTION_DATA_UPDATE, handleInspectionDataUpdateEvent);

    return unsubscribe;
  }, []);

  // Effect to listen for presentation image updates
  useEffect(() => {
    const handlePresentationImagesUpdated = (data: EventPresentationImagesUpdatedEvent) => {
      const { images, inspectionId } = data;
      console.log(`Received ${images.length} presentation images for inspection ${inspectionId}`);

      // Update state with the new images using centralized manager
      setPresentationImagesDirect(images, inspectionId);
      setCurrentInspectionId(inspectionId);

      // Show notification
      addNotification({
        type: 'success',
        title: '画像が更新されました',
        message: `検査ID: ${inspectionId} の画像を表示しています`
      });
    };

    const unsubscribe = eventManager.on(EVENTS.PRESENTATION_IMAGES_UPDATED, handlePresentationImagesUpdated);

    return unsubscribe;
  }, [addNotification, setPresentationImagesDirect]);

  // Add a listener for inspection saved events
  useEffect(() => {
    const handleSaveEvent = (data: EventInspectionSavedEvent) => {
      console.log("Save event detected, fetching presentation images once", data);

      // Check if the event includes an inspectionId
      if (data.inspectionId) {
        console.log(`Using inspection ID from event: ${data.inspectionId}`);
        // Just set the inspection ID, the coordinated update will handle loading
        console.log(`Setting inspection ID ${data.inspectionId} from event`);
        setCurrentInspectionId(data.inspectionId);
      } else {
        // Fall back to latest images if no ID provided
        console.log("No inspection ID in event, fetching latest images");
        fetchLatestPresentationImagesWithRetry(0, 10); // Try up to 10 times
      }
    };

    const unsubscribe = eventManager.on(EVENTS.INSPECTION_SAVED, handleSaveEvent);

    // Cleanup save event listener
    return unsubscribe;
  }, []);

  // Register functions in state manager for external components
  useEffect(() => {
    // Register core functions in state manager
    setUpdateInspectionResultFromSensorStatus(updateInspectionResultFromSensorStatus);
    setLoadLatestPresentationImages(async () => {
      console.log('🔍 Loading latest presentation images...');
      try {
        const result = await fetchLatestPresentationImages();
        if (result.result && result.data) {
          console.log(`📊 Found ${result.data.images.length} presentation images`);
          stopPolling();
          setCurrentInspectionId(result.data.inspection_id);
          setPresentationImagesDirect(result.data.images, result.data.inspection_id);
          console.log('✅ Successfully loaded latest presentation images');
        } else {
          console.log('❌ No latest presentation images found');
        }
      } catch (error) {
        console.error('❌ Error loading latest presentation images:', error);
      }
    });
    setClearPresentationImages(clearPresentationImages);
    setForceLoadLatestInspection(async () => {
      console.log('🔄 Force loading latest inspection...');
      try {
        const result = await fetchLatestPresentationImages();
        if (result.result && result.data) {
          const latestId = result.data.inspection_id;
          console.log(`✅ Latest inspection ID is: ${latestId}`);
          setCurrentInspectionId(latestId);
          if (result.data.images && result.data.images.length > 0) {
            setPresentationImagesDirect(result.data.images, latestId);
          } else {
            loadPresentationImages(latestId);
          }
        } else {
          console.log('❌ No latest inspection found');
        }
      } catch (error) {
        console.error('❌ Error force loading latest inspection:', error);
      }
    });
    setStopPollingPresentationImages(stopPolling);
    setForceRefreshCurrentInspection(async () => {
      if (createdInspectionId) {
        console.log(`🔍 Force refreshing current inspection ID: ${createdInspectionId}`);
        clearPresentationImages();
        await loadPresentationImages(createdInspectionId);
        console.log('✅ Force refresh completed');
      } else {
        console.log('❌ No current inspection ID to refresh');
      }
    });

    return () => {
      // Cleanup state manager registrations
      setUpdateInspectionResultFromSensorStatus(null);
      setLoadLatestPresentationImages(null);
      setClearPresentationImages(null);
      setForceLoadLatestInspection(null);
      setStopPollingPresentationImages(null);
      setForceRefreshCurrentInspection(null);
    };
  }, [updateInspectionResultFromSensorStatus, loadPresentationImages, clearPresentationImages, stopPolling, setPresentationImagesDirect, createdInspectionId]);

  // Function to handle showing inspection details
  const handleShowDetail = async (id: number) => {
    try {
      console.log(`🔍 Loading inspection details for ID: ${id}`);
      const result = await fetchInspectionDetailsById({ id });
      if (result.result && result.data) {
        setSelectedInspection(result.data);
        setShowDetail(true);
        console.log('✅ Inspection details loaded successfully');
      } else {
        console.error('❌ Failed to load inspection details');
        addNotification({
          type: 'error',
          title: 'エラー',
          message: '検査詳細の読み込みに失敗しました'
        });
      }
    } catch (error) {
      console.error('❌ Error loading inspection details:', error);
      addNotification({
        type: 'error',
        title: 'エラー',
        message: '検査詳細の読み込み中にエラーが発生しました'
      });
    }
  };

  // Create a wrapper function that matches the expected signature for external use
  const loadPresentationImagesWrapper = async (id: number): Promise<void> => {
    await loadPresentationImages(id);
  };

  // Make clearInspectionResults available globally for sensor monitoring
  useEffect(() => {
    (window as any).clearInspectionResults = clearInspectionResults;
    return () => {
      delete (window as any).clearInspectionResults;
    };
  }, [clearInspectionResults]);

  return {
    // status removed - now managed by useStatusManager
    inspectionResult,
    defectType,
    createdInspectionId,
    presentationImages,
    loadingPresentationImages,
    selectedInspection,
    showDetail,
    handleShowDetail,
    setShowDetail,
    loadPresentationImages: loadPresentationImagesWrapper,
    clearInspectionResults
  };
};
