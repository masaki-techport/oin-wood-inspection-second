import { useState, useEffect, useRef } from 'react';
import { useNotifications } from '@/components/ui/notifications';
import { fetchInspectionDetailsById, fetchPresentationImages, fetchLatestPresentationImages, PresentationImage } from '@/features/inspections/api/inspections-details';
import { Inspection } from '@/types/api';
import { UseInspectionStateReturn, PresentationImagesUpdatedEvent, InspectionSavedEvent, SensorStatus } from '../types';
import { fetchLatestPresentationImagesWithRetry } from '../utils';

/**
 * Hook for managing inspection state
 * @returns Inspection state and functions
 */
export const useInspectionState = (): UseInspectionStateReturn => {
  const [status, setStatus] = useState('待機中');
  const [inspectionResult, setInspectionResult] = useState('');
  const [defectType, setDefectType] = useState('');
  const [measurements, setMeasurements] = useState('');
  const [createdInspectionId, setCreatedInspectionId] = useState<number | null>(null);
  const [showDetail, setShowDetail] = useState(false);
  const [selectedInspection, setSelectedInspection] = useState<Inspection | null>(null);
  const [presentationImages, setPresentationImages] = useState<PresentationImage[]>([]);
  const [loadingPresentationImages, setLoadingPresentationImages] = useState(false);

  const { addNotification } = useNotifications();

  // Refs to manage polling and prevent race conditions
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const loadingTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const currentLoadingIdRef = useRef<number | null>(null);
  const isLoadingRef = useRef(false);



  const handleShowDetail = async (id: number) => {
    const result = await fetchInspectionDetailsById({ id });
    if (result.result && result.data) {
      setSelectedInspection(result.data);
      setShowDetail(true);
    } else {
      alert(result.message);
    }
  };

  // Function to clear inspection results (called when starting new inspection)
  const clearInspectionResults = () => {
    console.log('🔍 Clearing inspection results for new inspection');
    setInspectionResult('');
    setDefectType('');
    setMeasurements('');
    setCreatedInspectionId(null);
    setPresentationImages([]);
    setStatus('待機中');

    // Clear any ongoing loading operations
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
    if (loadingTimeoutRef.current) {
      clearTimeout(loadingTimeoutRef.current);
      loadingTimeoutRef.current = null;
    }
    currentLoadingIdRef.current = null;
    isLoadingRef.current = false;
    setLoadingPresentationImages(false);
  };

  // Improved load presentation images function with continuous polling
  const loadPresentationImages = async (id: number) => {
    if (!id) {
      console.log('❌ loadPresentationImages called with invalid ID:', id);
      return;
    }

    // If already loading the same ID, skip duplicate request
    if (currentLoadingIdRef.current === id && isLoadingRef.current) {
      console.log(`🔍 Already loading images for inspection ${id}, skipping duplicate request`);
      return;
    }

    // Clear any existing operations
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
    if (loadingTimeoutRef.current) {
      clearTimeout(loadingTimeoutRef.current);
      loadingTimeoutRef.current = null;
    }

    // Set loading state
    currentLoadingIdRef.current = id;
    isLoadingRef.current = true;
    setLoadingPresentationImages(true);
    
    let isPollingActive = true;
    let attemptCount = 0;

    const pollForImages = async () => {
      // Check if polling is still active and for correct ID
      if (!isPollingActive || currentLoadingIdRef.current !== id) {
        console.log(`🔍 Polling cancelled for inspection ${id}`);
        return;
      }

      attemptCount++;
      console.log(`🔍 Polling attempt ${attemptCount} for inspection ${id}`);

      try {
        const result = await fetchPresentationImages({ id });

        // Check again after async operation
        if (!isPollingActive || currentLoadingIdRef.current !== id) {
          console.log(`🔍 Polling cancelled after fetch for inspection ${id}`);
          return;
        }

        if (result.result && result.data && result.data.length > 0) {
          console.log(`✅ Found ${result.data.length} presentation images for inspection ${id}`);

          // Preload images for better performance
          result.data.forEach((img) => {
            try {
              let apiUrl = '';
              if (img.image_path.startsWith('inspection/')) {
                const relativePath = `src-api/data/images/${img.image_path}`;
                apiUrl = `/api/file?path=${encodeURIComponent(relativePath)}&convert=jpg&cache=${img.inspection_id}`;
              } else {
                const pathMatch = img.image_path.match(/inspection[/\\](.*)/)
                if (pathMatch && pathMatch[1]) {
                  const relativePath = `src-api/data/images/inspection/${pathMatch[1].replace(/\\/g, '/')}`;
                  apiUrl = `/api/file?path=${encodeURIComponent(relativePath)}&convert=jpg&cache=${img.inspection_id}`;
                } else {
                  apiUrl = `/api/file?path=${encodeURIComponent(img.image_path)}&convert=jpg&cache=${img.inspection_id}`;
                }
              }

              const preloadImg = new Image();
              preloadImg.src = apiUrl;
            } catch (e) {
              console.error(`Error preloading image: ${e}`);
            }
          });

          setPresentationImages(result.data);
          isPollingActive = false;
          currentLoadingIdRef.current = null;
          isLoadingRef.current = false;
          setLoadingPresentationImages(false);

          // Clear polling and timeout
          if (pollingIntervalRef.current) {
            clearInterval(pollingIntervalRef.current);
            pollingIntervalRef.current = null;
          }
          return;
        }
        
        // Continue polling indefinitely - no maximum attempts
        console.log(`🔍 No images found yet for inspection ${id}, continuing to poll`);
      } catch (err) {
        console.error(`Error polling for presentation images (attempt ${attemptCount}):`, err);
        // Continue polling even after errors - just log the error
      }
    };

    // Start immediate first attempt
    await pollForImages();

    // Start continuous polling - no maximum attempts limit
    pollingIntervalRef.current = setInterval(() => {
      if (isPollingActive && currentLoadingIdRef.current === id) {
        pollForImages();
      } else {
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current);
          pollingIntervalRef.current = null;
        }
      }
    }, 1000); // Poll every second
  };

  // Effect to load presentation images when inspection ID changes
  useEffect(() => {
    if (createdInspectionId) {
      console.log(`🆔 Inspection ID changed to ${createdInspectionId}, loading images...`);
      loadPresentationImages(createdInspectionId);
    }

    // Make the loadPresentationImages function available globally
    window.loadPresentationImages = (id: number) => {
      loadPresentationImages(id);
    };

    return () => {
      // Cleanup on unmount or ID change
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
      if (loadingTimeoutRef.current) {
        clearTimeout(loadingTimeoutRef.current);
        loadingTimeoutRef.current = null;
      }
      if (window.loadPresentationImages) {
        delete window.loadPresentationImages;
      }
    };
  }, [createdInspectionId]);

  // Effect to listen for presentation ready events
  useEffect(() => {
    const handlePresentationReady = (event: CustomEvent) => {
      const { inspectionId } = event.detail;
      if (inspectionId && inspectionId === createdInspectionId) {
        console.log(`🔍 Presentation images ready for inspection ${inspectionId}, loading immediately...`);
        loadPresentationImages(inspectionId); // Load with continuous polling
      }
    };

    window.addEventListener('presentationImagesReady', handlePresentationReady as EventListener);

    return () => {
      window.removeEventListener('presentationImagesReady', handlePresentationReady as EventListener);
    };
  }, [createdInspectionId]);

  // Custom event for updating inspection results from sensor data
  useEffect(() => {
    const handleInspectionDataUpdate = (event: CustomEvent) => {
      const inspectionData = event.detail;
      if (!inspectionData) return;

      console.log('🔍 Received inspection data update:', inspectionData);

      // Store previous values to check if we need to update
      const prevInspectionId = createdInspectionId;
      const hadPresentationImages = presentationImages && presentationImages.length > 0;

      // Handle presentation images first to avoid images disappearing
      if (inspectionData.presentation_images && Array.isArray(inspectionData.presentation_images) &&
        inspectionData.presentation_images.length > 0) {
        console.log(`🔍 Found ${inspectionData.presentation_images.length} presentation images in inspection data`);
        // Note: Presentation images are now managed by the centralized manager
      }

      // Update inspection ID for loading images if needed
      if (inspectionData.inspection_id && (!prevInspectionId || prevInspectionId !== inspectionData.inspection_id)) {
        console.log(`🆔 Inspection ID update: ${prevInspectionId} → ${inspectionData.inspection_id}`);

        // Verify this is actually the latest inspection ID
        fetchLatestPresentationImages().then(latestResult => {
          if (latestResult.result && latestResult.data) {
            const latestId = latestResult.data.inspection_id;
            if (inspectionData.inspection_id < latestId) {
              console.log(`⚠️ Received old inspection ID ${inspectionData.inspection_id}, latest is ${latestId}. Using latest instead.`);
              setCreatedInspectionId(latestId);
              window.inspectionId = latestId;

              // Load images for the latest inspection
              if (latestResult.data.images && latestResult.data.images.length > 0) {
                setPresentationImages(latestResult.data.images);
              } else {
                loadPresentationImages(latestId);
              }
            } else {
              // Use the received inspection ID as it's current
              setCreatedInspectionId(inspectionData.inspection_id);
              window.inspectionId = inspectionData.inspection_id;
            }
          } else {
            // Fallback to using the received ID
            setCreatedInspectionId(inspectionData.inspection_id);
            window.inspectionId = inspectionData.inspection_id;
          }
        }).catch(() => {
          // Fallback to using the received ID
          setCreatedInspectionId(inspectionData.inspection_id);
          window.inspectionId = inspectionData.inspection_id;
        });

        // Clear old presentation images when starting a new inspection
        if (prevInspectionId && prevInspectionId !== inspectionData.inspection_id) {
          console.log('🔄 New inspection detected, clearing old presentation images');
          setPresentationImages([]);
        }
      }

      // Update inspection result based on data
      if (inspectionData.confidence_above_threshold === true) {
        // Check different types of defects in inspection_details
        const details = inspectionData.inspection_details || [];
        let hasHole = false;
        let hasDiscoloration = false;
        let hasKnot = false;

        // Process inspection details to determine defect types
        details.forEach((detail: any) => {
          const errorType = detail.error_type;
          if (errorType === 0) hasDiscoloration = true; // 変色 (discoloration)
          if (errorType === 1) hasHole = true;         // 穴 (hole)
          if (errorType >= 2 && errorType <= 5) hasKnot = true; // Various knot types
        });

        // Set defect type based on detected defects - prioritize in specific order
        let defectTypeText = '';
        let inspectionResultText = '';

        // Calculate result based on detected defects instead of using inspectionData.results field
        // This ensures we use inspection_results data not inspection.results
        if (hasKnot) {
          // Find the maximum knot length to determine severity
          let maxKnotLength = 0;
          details.forEach((detail: any) => {
            if (detail.error_type >= 2 && detail.error_type <= 5 && detail.length > maxKnotLength) {
              maxKnotLength = detail.length;
            }
          });

          // Determine result based on knot size
          inspectionResultText = maxKnotLength > 10 ? '節あり' : 'こぶし';
          // Calculated knot result based on length
        } else {
          // No knots detected - primary result should be 無欠点
          inspectionResultText = '無欠点';
        }

        // Set defect type for supplementary display (holes/discoloration)
        if (hasHole && hasDiscoloration) {
          defectTypeText = '穴●変色発生';
        } else if (hasHole) {
          defectTypeText = '穴発生';
        } else if (hasDiscoloration) {
          defectTypeText = '変色発生';
        }

        // Set the states
        setDefectType(defectTypeText);
        setInspectionResult(inspectionResultText);

        console.log(`🔍 Set results: "${inspectionResultText}" / "${defectTypeText}"`);
      } else {
        // No defects above threshold - but only update if we don't have presentation images or if this is completely new data
        // This prevents changing from a defect result with images to "no defect" without images
        const shouldUpdateNoDefect =
          !hadPresentationImages ||
          !presentationImages ||
          presentationImages.length === 0 ||
          (inspectionData.inspection_id && inspectionData.inspection_id !== prevInspectionId);

        if (shouldUpdateNoDefect) {
          setDefectType('');
          setInspectionResult('無欠点');
          console.log('🔍 Set result to 無欠点 (no defects above threshold)');
        } else {
          console.log('🔍 Skipping update to 無欠点 to prevent losing presentation images with detected defects');
        }
      }

      // Update measurements if available (placeholder for now)
      setMeasurements(`幅: ${Math.round(Math.random() * 10 + 10)}mm`);

      // Handle presentation images - always poll continuously regardless of ready status
      if (inspectionData.inspection_id) {
        if (inspectionData.presentation_ready === true) {
          console.log('🔍 Presentation images marked as ready, starting continuous polling');
          loadPresentationImages(inspectionData.inspection_id);
        } else if (inspectionData.presentation_ready === false) {
          console.log('🔍 Presentation images not ready yet, starting continuous polling anyway');
          // Clear any existing presentation images since they're not ready for this inspection
          setPresentationImages([]);
          // Start polling anyway - it will keep trying until images are available
          loadPresentationImages(inspectionData.inspection_id);
        } else {
          // If presentation_ready status is not provided, start continuous polling
          console.log('🔍 Presentation ready status unknown, starting continuous polling');
          loadPresentationImages(inspectionData.inspection_id);
        }
      }
    };

    // Register the event listener
    window.addEventListener('inspectionDataUpdate', handleInspectionDataUpdate as EventListener);

    return () => {
      window.removeEventListener('inspectionDataUpdate', handleInspectionDataUpdate as EventListener);
    };
  }, []);

  // In the component, add a useEffect to clear capturedImage when there are presentation images
  useEffect(() => {
    // When presentation images are loaded, always clear the capturedImage to show the presentation grid
    if (presentationImages.length > 0) {
      // This would be handled in the parent component
      console.log('Presentation images loaded, should clear captured image');
    }
  }, [presentationImages]);

  // Function to update inspection result from sensor status
  const updateInspectionResultFromSensorStatus = (sensorStatus: SensorStatus) => {
    console.log('🔍 Updated inspection results from sensor status:', sensorStatus);

    // Extract inspection ID from sensor status (this should be the newest one)
    const sensorInspectionId = sensorStatus.inspection_data?.inspection_id;
    if (sensorInspectionId && sensorInspectionId !== createdInspectionId) {
      console.log(`🆔 Sensor status has new inspection ID: ${createdInspectionId} → ${sensorInspectionId}`);
      setCreatedInspectionId(sensorInspectionId);

      // Clear old presentation images for new inspection
      setPresentationImages([]);

      // Start loading presentation images for the new inspection
      loadPresentationImages(sensorInspectionId);
    }

    // First check if inspection_results is available directly - prefer using that
    if (sensorStatus && sensorStatus.inspection_results) {
      console.log('🔍 Using inspection_results from sensor status');

      // Process inspection_results data to get display values
      const resultData = sensorStatus.inspection_results;

      // Check for knot defects
      const hasAnyKnot = resultData.knot || resultData.dead_knot || resultData.live_knot || resultData.tight_knot;

      // Check for hole and discoloration
      const hasHole = resultData.hole;
      const hasDiscoloration = resultData.discoloration;

      // Get the length value
      const knotLength = resultData.length || 0;

      // Determine knot status based on presence and length
      let knotStatus = '無欠点';
      if (hasAnyKnot) {
        knotStatus = knotLength > 10 ? '節あり' : 'こぶし';
      }

      // Determine defect type
      let defectTypeResult = '';
      if (hasHole && hasDiscoloration) {
        defectTypeResult = '穴●変色発生';
      } else if (hasHole) {
        defectTypeResult = '穴発生';
      } else if (hasDiscoloration) {
        defectTypeResult = '変色発生';
      }

      // Update state directly with calculated values
      setInspectionResult(knotStatus);
      setDefectType(defectTypeResult);

      console.log(`🔍 Results: "${knotStatus}" / "${defectTypeResult}"`);
      return;
    }

    // Fall back to using inspection_data if inspection_results is not available
    if (!sensorStatus || !sensorStatus.inspection_data) {
      console.log('🔍 updateInspectionResultFromSensorStatus called but no inspection data:', {
        hasSensorStatus: !!sensorStatus,
        hasInspectionData: !!(sensorStatus && sensorStatus.inspection_data)
      });
      return;
    }

    const newInspectionData = sensorStatus.inspection_data;

    // Only update if this is actually new data or if we don't have current results
    // Or if we already have this inspection ID but presentation images now exist where they didn't before
    const hasNewPresentationImages = newInspectionData.inspection_id === createdInspectionId &&
      newInspectionData.presentation_images &&
      (!presentationImages || presentationImages.length === 0);

    const shouldUpdate = !createdInspectionId ||
      newInspectionData.inspection_id !== createdInspectionId ||
      !inspectionResult ||
      hasNewPresentationImages;

    if (shouldUpdate) {
      console.log('🔍 Updating inspection result from sensor status:', newInspectionData);
      console.log(`🔍 Update reason: ID ${createdInspectionId} → ${newInspectionData.inspection_id}`);

      // Create and dispatch custom event
      const event = new CustomEvent('inspectionDataUpdate', {
        detail: newInspectionData
      });
      window.dispatchEvent(event);
    } else {
      console.log('🔍 Skipping update - same inspection data already displayed');
    }
  };

  // Function to update status directly
  const updateStatus = (newStatus: string) => {
    if (newStatus !== status) {
      console.log(`🔍 Updating status from ${status} to ${newStatus}`);
      setStatus(newStatus);
    }
  };

  // Export the update functions
  useEffect(() => {
    // Make the update functions available globally for external components
    (window as any).updateInspectionResultFromSensorStatus = updateInspectionResultFromSensorStatus;
    (window as any).clearInspectionResults = clearInspectionResults;
    (window as any).updateStatus = updateStatus;

    // Removed debugImageLoading function as requested

    // Add function to load latest presentation images
    (window as any).loadLatestPresentationImages = async () => {
      console.log('🔍 Loading latest presentation images...');

      try {
        const result = await fetchLatestPresentationImages();

        if (result.result && result.data) {
          console.log(`📊 Latest inspection ID: ${result.data.inspection_id}`);
          console.log(`📊 Found ${result.data.images.length} presentation images`);

          // Stop any current polling first
          if (pollingIntervalRef.current) {
            clearInterval(pollingIntervalRef.current);
            pollingIntervalRef.current = null;
          }

          // Set the inspection ID and images
          setCreatedInspectionId(result.data.inspection_id);
          setPresentationImages(result.data.images);
          setLoadingPresentationImages(false);

          console.log('✅ Successfully loaded latest presentation images');
        } else {
          console.log('❌ No latest presentation images found');
        }
      } catch (error) {
        console.error('❌ Error loading latest presentation images:', error);
      }
    };

    // Add function to manually load presentation images for a specific ID
    (window as any).loadPresentationImagesForId = (id: number) => {
      console.log(`🔍 Manually loading presentation images for ID: ${id}`);
      loadPresentationImages(id);
    };

    // Add function to show current state
    (window as any).showInspectionState = () => {
      console.log('🔍 Current inspection state:');
      console.log(`   - ID: ${createdInspectionId} | Images: ${presentationImages.length} | Loading: ${loadingPresentationImages}`);
      console.log(`   - Result: "${inspectionResult}" | Defect: "${defectType}" | Status: "${status}"`);
      if (presentationImages.length > 0) {
        console.log(`   - Image inspection IDs: ${presentationImages.map(img => img.inspection_id).join(', ')}`);
        console.log(`   - Image paths: ${presentationImages.map(img => img.image_path).join(', ')}`);
      }
    };

    // Add function to compare with latest
    (window as any).compareWithLatest = async () => {
      try {
        const result = await fetchLatestPresentationImages();
        if (result.result && result.data) {
          console.log('🔍 Comparison with latest:');
          console.log(`   - Current ID: ${createdInspectionId} | Latest ID: ${result.data.inspection_id}`);
          console.log(`   - Current Images: ${presentationImages.length} | Latest Images: ${result.data.images.length}`);
          console.log(`   - Match: ${createdInspectionId === result.data.inspection_id ? '✅' : '❌'}`);
          if (result.data.images.length > 0) {
            console.log(`   - Latest paths: ${result.data.images.map(img => img.image_path).join(', ')}`);
          }
        }
      } catch (error) {
        console.error('Error comparing with latest:', error);
      }
    };

    // Add function to force load the latest inspection
    (window as any).forceLoadLatestInspection = async () => {
      console.log('🔄 Force loading latest inspection...');

      try {
        // Stop any current polling
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current);
          pollingIntervalRef.current = null;
        }

        // Get the latest inspection ID
        const result = await fetchLatestPresentationImages();
        if (result.result && result.data) {
          const latestId = result.data.inspection_id;
          console.log(`✅ Latest inspection ID is: ${latestId}`);

          // Set the latest inspection ID and load its images
          setCreatedInspectionId(latestId);

          if (result.data.images && result.data.images.length > 0) {
            console.log(`✅ Found ${result.data.images.length} presentation images for inspection ${latestId}`);
            setPresentationImages(result.data.images);
            setLoadingPresentationImages(false);
          } else {
            // Start continuous polling for the latest inspection
            loadPresentationImages(latestId);
          }
        } else {
          console.log('❌ Could not get latest inspection ID');
        }
      } catch (error) {
        console.error('❌ Error loading latest inspection:', error);
      }
    };

    // Add function to clear presentation images manually
    (window as any).clearPresentationImages = () => {
      console.log('🔄 Manually clearing presentation images');
      setPresentationImages([]);
      setCreatedInspectionId(null);
    };

    // Add function to trigger presentation ready event manually
    (window as any).triggerPresentationReady = (inspectionId: number) => {
      console.log(`🔍 Manually triggering presentation ready for inspection ${inspectionId}`);
      const event = new CustomEvent('presentationImagesReady', {
        detail: { inspectionId }
      });
      window.dispatchEvent(event);
    };

    // Add function to force immediate loading (for testing)
    (window as any).forceLoadPresentationImages = (id: number) => {
      console.log(`🔍 Force loading presentation images for ID: ${id}`);
      loadPresentationImages(id); // Use continuous polling
    };

    // Add function to stop polling
    (window as any).stopPollingPresentationImages = () => {
      console.log(`🔍 Stopping presentation images polling`);
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
        setLoadingPresentationImages(false);
      }
      currentLoadingIdRef.current = null;
    };

    // Add function to test fast requests (for debugging the fix)
    (window as any).testFastRequests = (inspectionId: number, count: number = 5) => {
      console.log(`🔍 Testing ${count} fast requests for inspection ${inspectionId}`);
      for (let i = 0; i < count; i++) {
        setTimeout(() => {
          console.log(`🔍 Fast request ${i + 1}/${count}`);
          loadPresentationImages(inspectionId);
        }, i * 50); // 50ms apart
      }
    };

    return () => {
      delete (window as any).updateInspectionResultFromSensorStatus;
      delete (window as any).clearInspectionResults;
      delete (window as any).updateStatus;
      delete (window as any).loadLatestPresentationImages;
      delete (window as any).loadPresentationImagesForId;
      delete (window as any).showInspectionState;
      delete (window as any).clearPresentationImages;
      delete (window as any).triggerPresentationReady;
      delete (window as any).forceLoadPresentationImages;
      delete (window as any).stopPollingPresentationImages;
      delete (window as any).compareWithLatest;
      delete (window as any).forceLoadLatestInspection;
      delete (window as any).testFastRequests;
    };
  }, [updateInspectionResultFromSensorStatus, clearInspectionResults, updateStatus]);

  // Update presentation images listener
  useEffect(() => {
    // Listen for presentation image updates
    const handlePresentationImagesUpdated = (event: PresentationImagesUpdatedEvent) => {
      const { images, inspectionId } = event.detail;
      console.log(`Received ${images.length} presentation images for inspection ${inspectionId}`);

      // Update state with the new images
      setPresentationImages(images);
      setCreatedInspectionId(inspectionId);

      // Show notification
      addNotification({
        type: 'success',
        title: '画像が更新されました',
        message: `検査ID: ${inspectionId} の画像を表示しています`
      });
    };

    window.addEventListener('presentationImagesUpdated', handlePresentationImagesUpdated as EventListener);

    return () => {
      window.removeEventListener('presentationImagesUpdated', handlePresentationImagesUpdated as EventListener);
    };
  }, [addNotification]);

  // Add a listener for inspection saved events
  useEffect(() => {
    const handleSaveEvent = (event: InspectionSavedEvent) => {
      console.log("Save event detected, fetching presentation images once", event.detail);

      // Check if the event includes an inspectionId
      if (event.detail.inspectionId) {
        console.log(`Using inspection ID from event: ${event.detail.inspectionId}`);
        // Just set the inspection ID, the coordinated update will handle loading
        console.log(`Setting inspection ID ${event.detail.inspectionId} from event`);
        setCreatedInspectionId(event.detail.inspectionId);
      } else {
        // Fall back to latest images if no ID provided
        console.log("No inspection ID in event, fetching latest images");
        fetchLatestPresentationImagesWithRetry(0, 10); // Try up to 10 times
      }
    };

    window.addEventListener('inspectionSaved', handleSaveEvent as EventListener);

    // Cleanup save event listener
    return () => {
      window.removeEventListener('inspectionSaved', handleSaveEvent as EventListener);
    };
  }, []);

  // Create a wrapper function that matches the expected signature for external use
  const loadPresentationImagesWrapper = async (id: number): Promise<void> => {
    await loadPresentationImages(id);
  };

  return {
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
    loadPresentationImages: loadPresentationImagesWrapper
  };
};