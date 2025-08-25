/**
 * Utility functions for handling images in the inspection screen
 */

// URL cache to avoid recalculating the same URLs
const imageUrlCache: Record<string, string> = {};
const MAX_CACHE_SIZE = 1000; // Limit cache size to prevent memory growth

/**
 * Converts a Windows path to an API-accessible URL
 * @param windowsPath - The windows path to convert
 * @param inspectionId - Optional inspection ID to use as a cache-busting parameter
 * @returns The API URL that can access the image
 */
export const getImageUrl = (windowsPath: string, inspectionId?: number): string => {
  console.log(`getImageUrl called with path: ${windowsPath}, inspectionId: ${inspectionId}`);
  if (!windowsPath) {
    return ''; // Return empty string for empty paths
  }

  // Create cache key from path and inspection ID
  const cacheKey = `${windowsPath}:${inspectionId || 'default'}`;
  
  // Return cached value if available
  if (imageUrlCache[cacheKey]) {
    console.log(`Using cached URL for ${cacheKey}`);
    return imageUrlCache[cacheKey];
  }
  
  try {
    // Use relative URL instead of hardcoded localhost
    // This ensures the URL works in any environment (dev, prod, etc.)
    const apiBaseUrl = window.location.origin;
    
    // Add cache-busting parameter based on inspection ID
    const cacheBuster = inspectionId ? `&cache=${inspectionId}` : '';
    
    let result = '';
    
    // Check if path already contains duplicated segments
    const duplicateCheck = windowsPath.match(/inspection[\/\\].*?inspection[\/\\]/i);
    if (duplicateCheck) {
      // Find the last occurrence of "inspection/" and keep only what follows
      const lastInspectionIndex = windowsPath.lastIndexOf("inspection");
      if (lastInspectionIndex !== -1) {
        const cleanPath = windowsPath.substring(lastInspectionIndex);
        const relativePath = `src-api/data/images/${cleanPath.replace(/\\/g, '/')}`;
        // Use file API for image loading
        result = `${apiBaseUrl}/api/file?path=${encodeURIComponent(relativePath)}&convert=jpg${cacheBuster}`;
      }
    }
    
    // If not resolved yet, try other methods
    if (!result) {
      // 1. Extract the part after "inspection/" if it exists
      const inspectionMatch = windowsPath.match(/inspection[\/\\](.*?)$/i);
      if (inspectionMatch && inspectionMatch[1]) {
        const relativePath = `src-api/data/images/inspection/${inspectionMatch[1].replace(/\\/g, '/')}`;
        result = `${apiBaseUrl}/api/file?path=${encodeURIComponent(relativePath)}&convert=jpg${cacheBuster}`;
      }
      // 2. Handle paths that start with "inspection/" (common for presentation images)
      else if (windowsPath.startsWith('inspection/')) {
        const relativePath = `src-api/data/images/${windowsPath.replace(/\\/g, '/')}`;
        result = `${apiBaseUrl}/api/file?path=${encodeURIComponent(relativePath)}&convert=jpg${cacheBuster}`;
      }
      // 3. For Windows absolute paths, try to extract just the filename
      else if (windowsPath.match(/^[a-zA-Z]:[\/\\]/)) {
        const filename = windowsPath.split(/[\/\\]/).pop();
        if (filename) {
          // Try to find the date folder pattern (YYYYMMDD_HHMM)
          const dateMatch = windowsPath.match(/\d{8}_\d{4}/);
          if (dateMatch) {
            const dateFolder = dateMatch[0];
            const relativePath = `src-api/data/images/inspection/${dateFolder}/${filename}`;
            result = `${apiBaseUrl}/api/file?path=${encodeURIComponent(relativePath)}&convert=jpg${cacheBuster}`;
          } else {
            // Just use the filename as a last resort, but try to find date folder patterns in the windows path
            // For more robustness, check for any folder pattern with 8 digits followed by underscore and 4 digits
            const datePattern = windowsPath.match(/\d{8}_\d{4}/g);
            const dateFolder = datePattern ? datePattern[datePattern.length - 1] : '';
            
            let simplePath;
            if (dateFolder) {
              simplePath = `src-api/data/images/inspection/${dateFolder}/${filename}`;
              console.log(`Trying date folder path: ${simplePath}`);
            } else {
              simplePath = `src-api/data/images/inspection/${filename}`;
              console.log(`Using simple filename path: ${simplePath}`);
            }
            result = `${apiBaseUrl}/api/file?path=${encodeURIComponent(simplePath)}&convert=jpg${cacheBuster}`;
          }
        } else {
          // If we can't extract a filename, use the full path
          result = `${apiBaseUrl}/api/file?path=${encodeURIComponent(windowsPath)}&convert=jpg${cacheBuster}`;
        }
      }
      // 4. If path starts with src-api, ensure we don't duplicate it
      else if (windowsPath.startsWith('src-api/') || windowsPath.startsWith('src-api\\')) {
        result = `${apiBaseUrl}/api/file?path=${encodeURIComponent(windowsPath.replace(/\\/g, '/'))}&convert=jpg${cacheBuster}`;
      }
      // 5. For any other path, try using as-is
      else {
        result = `${apiBaseUrl}/api/file?path=${encodeURIComponent(windowsPath.replace(/\\/g, '/'))}&convert=jpg${cacheBuster}`;
      }
    }
    
    // Add to cache only if we have room
    if (Object.keys(imageUrlCache).length < MAX_CACHE_SIZE) {
      imageUrlCache[cacheKey] = result;
    } else {
      // If cache is full, clear the oldest 20% of entries
      const keys = Object.keys(imageUrlCache);
      const keysToRemove = Math.floor(keys.length * 0.2);
      for (let i = 0; i < keysToRemove; i++) {
        delete imageUrlCache[keys[i]];
      }
      // Then add the new entry
      imageUrlCache[cacheKey] = result;
    }
    
    console.log(`Generated image URL: ${result}`);
    
    return result;
  } catch (error) {
    console.error('Error converting image path:', error);
    return ''; // Return empty string on error
  }
};

/**
 * Checks if the given image path is a BMP image
 * @param imagePath - The image path to check
 * @returns Boolean indicating if the image is BMP format
 */
export const isBmpImage = (imagePath: string): boolean => {
  if (!imagePath) return false;
  return imagePath.toLowerCase().endsWith('.bmp');
};