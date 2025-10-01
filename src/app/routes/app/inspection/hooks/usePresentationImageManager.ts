import { useState, useEffect, useRef, useCallback } from 'react';
import { fetchPresentationImages, PresentationImage } from '@/features/inspections/api/inspections-details';
import { buildApiFileUrl } from '@/utils/image-path';
import { createStandardPollingManager } from '../utils/pollingManager';

/**
 * Centralized presentation image management hook
 * Provides single source of truth for presentation image loading and state
 */
export const usePresentationImageManager = () => {
  const [presentationImages, setPresentationImages] = useState<PresentationImage[]>([]);
  const [loadingPresentationImages, setLoadingPresentationImages] = useState(false);
  const [currentInspectionId, setCurrentInspectionId] = useState<number | null>(null);

  // Refs to manage polling and prevent race conditions
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const loadingTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const currentLoadingIdRef = useRef<number | null>(null);
  const isLoadingRef = useRef(false);
  const pollingManagerRef = useRef<any>(null);

  /**
   * Clear presentation images and reset state
   */
  const clearPresentationImages = useCallback(() => {
    console.log('🔍 Clearing presentation images');
    setPresentationImages([]);
    setCurrentInspectionId(null);
    setLoadingPresentationImages(false);

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
  }, []);

  /**
   * Load presentation images for a specific inspection ID
   * Uses smart polling with increasing intervals to reduce server load
   */
  const loadPresentationImages = useCallback(async (id: number) => {
    if (!id || typeof id !== 'number' || id <= 0 || !isFinite(id)) {
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
    setCurrentInspectionId(id);
    
    let isPollingActive = true;
    let attemptCount = 0;
    const maxAttempts = 30; // Maximum 30 attempts (1 minute total)
    let pollInterval = 1000; // Start with 1 second, increase gradually

    const pollForImages = async () => {
      // Check if polling is still active and for correct ID
      if (!isPollingActive || currentLoadingIdRef.current !== id) {
        console.log(`🔍 Polling cancelled for inspection ${id}`);
        return;
      }

      // Check maximum attempts
      if (attemptCount >= maxAttempts) {
        console.log(`🔍 Maximum polling attempts reached for inspection ${id}, stopping`);
        isPollingActive = false;
        currentLoadingIdRef.current = null;
        isLoadingRef.current = false;
        setLoadingPresentationImages(false);
        
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current);
          pollingIntervalRef.current = null;
        }
        return;
      }

      attemptCount++;
      console.log(`🔍 Polling attempt ${attemptCount}/${maxAttempts} for inspection ${id}`);

      try {
        const result = await fetchPresentationImages({ id });

        // Check again after async operation
        if (!isPollingActive || currentLoadingIdRef.current !== id) {
          console.log(`🔍 Polling cancelled after fetch for inspection ${id}`);
          return;
        }

        if (result.result && result.data && result.data.length > 0) {
          console.log(`✅ Found ${result.data.length} presentation images for inspection ${id}`);

          // Preload images for better performance with optimized URLs
          result.data.forEach((img) => {
            try {
              const preloadImg = new Image();
              preloadImg.src = buildApiFileUrl(img.image_path, img.inspection_id, { quality: 'low', progressive: true });
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
        
        // Increase polling interval gradually to reduce server load
        if (attemptCount > 5) {
          pollInterval = Math.min(pollInterval * 1.2, 5000); // Max 5 seconds
        }
        
        console.log(`🔍 No images found yet for inspection ${id}, continuing to poll (next attempt in ${pollInterval}ms)`);
      } catch (err) {
        console.error(`Error polling for presentation images (attempt ${attemptCount}):`, err);
        // Increase interval on error to reduce server load
        pollInterval = Math.min(pollInterval * 1.5, 5000);
      }
    };

    // Start immediate first attempt
    await pollForImages();

    // Create standardized polling manager
    const pollingManager = createStandardPollingManager(
      async () => {
        if (isPollingActive && currentLoadingIdRef.current === id) {
          await pollForImages();
        }
      },
      (error) => {
        console.error('Error polling presentation images:', error);
      }
    );

    // Store polling manager reference for cleanup
    pollingManagerRef.current = pollingManager;

    // Start polling
    pollingManager.start();
  }, []);

  /**
   * Stop current polling operation
   */
  const stopPolling = useCallback(() => {
    console.log('🔍 Stopping presentation images polling');
    if (pollingManagerRef.current) {
      pollingManagerRef.current.stop();
      pollingManagerRef.current = null;
    }
    if (loadingTimeoutRef.current) {
      clearTimeout(loadingTimeoutRef.current);
      loadingTimeoutRef.current = null;
    }
    currentLoadingIdRef.current = null;
    isLoadingRef.current = false;
    setLoadingPresentationImages(false);
  }, []);

  /**
   * Set presentation images directly (for external updates)
   */
  const setPresentationImagesDirect = useCallback((images: PresentationImage[], inspectionId: number) => {
    setPresentationImages(images);
    setCurrentInspectionId(inspectionId);
    setLoadingPresentationImages(false);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
      if (loadingTimeoutRef.current) {
        clearTimeout(loadingTimeoutRef.current);
        loadingTimeoutRef.current = null;
      }
    };
  }, []);

  return {
    presentationImages,
    loadingPresentationImages,
    currentInspectionId,
    loadPresentationImages,
    clearPresentationImages,
    stopPolling,
    setPresentationImagesDirect
  };
};
