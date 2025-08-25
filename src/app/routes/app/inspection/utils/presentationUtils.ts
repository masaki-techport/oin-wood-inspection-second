import { fetchLatestPresentationImages } from '@/features/inspections/api/inspections-details';

/**
 * Fetch latest presentation images with retry mechanism
 * @param retryCount - Current retry count
 * @param maxRetries - Maximum number of retries
 * @returns Promise with fetch result
 */
export const fetchLatestPresentationImagesWithRetry = async (retryCount = 0, maxRetries = 5) => {
  try {
    console.log(`Fetching latest presentation images after inspection completed (attempt ${retryCount + 1}/${maxRetries + 1})`);

    const result = await fetchLatestPresentationImages();
    
    if (result.result && result.data) {
      const { inspection_id, inspection_dt, images } = result.data;
      
      // Only process if this is a new inspection or we don't have cached data
      // Always process any valid inspection, regardless of ID
      console.log(`Found inspection ID: ${inspection_id} with ${images.length} images`);
      
      if (images && images.length > 0) {
        console.log(`Processing ${images.length} presentation images for inspection ${inspection_id}`);
        
        // Dispatch a custom event with the presentation images
        const presentationEvent = new CustomEvent('presentationImagesUpdated', { 
          detail: { 
            images,
            inspectionId: inspection_id,
            inspectionDt: inspection_dt
          } 
        });
        window.dispatchEvent(presentationEvent);
        return { success: true, inspectionId: inspection_id };
      } else if (retryCount < maxRetries) {
        console.log(`No presentation images found for inspection ${inspection_id}, retrying in 500ms...`);
        return new Promise(resolve => {
          setTimeout(() => {
            fetchLatestPresentationImagesWithRetry(retryCount + 1, maxRetries)
              .then(resolve);
          }, 500);
        });
      } else {
        console.log(`No presentation images found for inspection ${inspection_id} after ${maxRetries + 1} attempts`);
        return { success: false, reason: 'no_images' };
      }
    } else if (retryCount < maxRetries) {
      console.log(`Failed to get latest presentation images: ${result.message}, retrying in 500ms...`);
      return new Promise(resolve => {
        setTimeout(() => {
          fetchLatestPresentationImagesWithRetry(retryCount + 1, maxRetries)
            .then(resolve);
        }, 500);
      });
    } else {
      console.log(`Failed to get latest presentation images after ${maxRetries + 1} attempts: ${result.message}`);
      return { success: false, reason: 'api_error', message: result.message };
    }
  } catch (error) {
    console.error(`Error fetching latest presentation images (attempt ${retryCount + 1}/${maxRetries + 1}):`, error);
    if (retryCount < maxRetries) {
      return new Promise(resolve => {
        setTimeout(() => {
          fetchLatestPresentationImagesWithRetry(retryCount + 1, maxRetries)
            .then(resolve);
        }, 500);
      });
    }
    return { success: false, reason: 'exception', error };
  }
};

/**
 * Helper function to dispatch an inspection saved event
 * @param inspectionId - Optional inspection ID to include in the event
 */
export const dispatchSaveEvent = (inspectionId?: number | null) => {
  console.log('Dispatching inspectionSaved event to trigger image loading');
  const saveEvent = new CustomEvent('inspectionSaved', { 
    detail: { 
      timestamp: Date.now(),
      inspectionId
    } 
  });
  window.dispatchEvent(saveEvent);
};