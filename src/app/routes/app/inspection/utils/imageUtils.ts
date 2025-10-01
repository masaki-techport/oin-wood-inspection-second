/**
 * Utility functions for handling images in the inspection screen
 */

// URL cache to avoid recalculating the same URLs
const imageUrlCache: Record<string, string> = {};
const MAX_CACHE_SIZE = 1000; // Limit cache size to prevent memory growth

/**
 * Optimized image URL generation with caching and quality options
 * @param imagePath - The image path to convert
 * @param inspectionId - Inspection ID for the image
 * @param options - Quality and size options for optimization
 * @returns The API URL that can access the image
 */
export const getImageUrl = (imagePath: string, inspectionId: number, options: {
  quality?: 'low' | 'medium' | 'high';
  size?: 'thumbnail' | 'medium' | 'full';
  progressive?: boolean;
} = {}): string => {
  if (!imagePath) {
    return ''; // Return empty string for empty paths
  }

  const { quality = 'medium', size = 'full', progressive = false } = options;
  const cacheKey = `${imagePath}:${inspectionId}:${quality}:${size}:${progressive}`;

  // Return cached URL if available
  if (imageUrlCache[cacheKey]) {
    return imageUrlCache[cacheKey];
  }

  try {
    const apiBaseUrl = `${window.location.protocol}//${window.location.hostname}:8000`;
    let baseUrl = '';
    
    // Check if path already contains duplicated segments
    const duplicateCheck = imagePath.match(/inspection[/\\].*?inspection[/\\]/i);
    if (duplicateCheck) {
      // Find the last occurrence of "inspection/" and keep only what follows
      const lastInspectionIndex = imagePath.lastIndexOf("inspection");
      if (lastInspectionIndex !== -1) {
        const cleanPath = imagePath.substring(lastInspectionIndex);
        const relativePath = `src-api/data/images/${cleanPath.replace(/\\/g, '/')}`;
        baseUrl = `${apiBaseUrl}/api/file?path=${encodeURIComponent(relativePath)}&inspection_id=${inspectionId}`;
      }
    } else {
      // 1. Extract the part after "inspection/" if it exists
      const inspectionMatch = imagePath.match(/inspection[/\\](.*?)$/i);
      if (inspectionMatch && inspectionMatch[1]) {
        const relativePath = `src-api/data/images/inspection/${inspectionMatch[1].replace(/\\/g, '/')}`;
        baseUrl = `${apiBaseUrl}/api/file?path=${encodeURIComponent(relativePath)}&inspection_id=${inspectionId}`;
      } else {
        // 2. For full paths, assume they're already properly formatted
        baseUrl = `${apiBaseUrl}/api/file?path=${encodeURIComponent(imagePath)}&inspection_id=${inspectionId}`;
      }
    }

    // Add optimization parameters
    const params = new URLSearchParams();

    // Always convert BMP to JPG for better performance
    if (imagePath.toLowerCase().endsWith('.bmp')) {
      params.append('convert', 'jpg');
    }

    // Add quality parameter for JPG conversion
    if (quality === 'low') {
      params.append('quality', '60');
    } else if (quality === 'medium') {
      params.append('quality', '85');
    } else if (quality === 'high') {
      params.append('quality', '95');
    }

    // Add size parameter for potential server-side resizing (if supported)
    if (size === 'thumbnail') {
      params.append('size', '150x150');
    } else if (size === 'medium') {
      params.append('size', '500x500');
    }

    // Add progressive loading parameter
    if (progressive) {
      params.append('progressive', 'true');
    }

    const finalUrl = params.toString() ? `${baseUrl}&${params.toString()}` : baseUrl;

    // Cache the result
    if (Object.keys(imageUrlCache).length < MAX_CACHE_SIZE) {
      imageUrlCache[cacheKey] = finalUrl;
    } else {
      // Clear oldest 20% of cache entries
      const keys = Object.keys(imageUrlCache);
      const keysToRemove = Math.floor(keys.length * 0.2);
      for (let i = 0; i < keysToRemove; i++) {
        delete imageUrlCache[keys[i]];
      }
      imageUrlCache[cacheKey] = finalUrl;
    }
    
    return finalUrl;
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