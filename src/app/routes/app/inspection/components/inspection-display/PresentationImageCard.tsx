import React, { useState, useEffect } from 'react';
import { PresentationImageCardProps } from '../../types';
import { getImageUrl } from '../../utils';
import NoImagePlaceholder from '@/components/ui/NoImagePlaceholder';

// URL cache to avoid recalculating the same URLs
const imageUrlCache: Record<string, string> = {};
const MAX_CACHE_SIZE = 1000;

/**
 * Optimized image URL generation with caching (similar to InspectionDetailsModal)
 */
const getOptimizedImageUrl = (imagePath: string, inspectionId: number, options: {
  quality?: 'low' | 'medium' | 'high';
  size?: 'thumbnail' | 'medium' | 'full';
  progressive?: boolean;
} = {}): string => {
  if (!imagePath) return '';

  const { quality = 'medium', size = 'full', progressive = false } = options;
  const cacheKey = `${imagePath}:${inspectionId}:${quality}:${size}:${progressive}`;

  // Return cached URL if available
  if (imageUrlCache[cacheKey]) {
    return imageUrlCache[cacheKey];
  }

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
      // For temp sections (inspectionId = 0), don't include inspection_id parameter
      if (inspectionId > 0) {
        baseUrl = `${apiBaseUrl}/api/file?path=${encodeURIComponent(relativePath)}&inspection_id=${inspectionId}`;
      } else {
        baseUrl = `${apiBaseUrl}/api/stream/file?path=${encodeURIComponent(relativePath)}&convert=jpg`;
      }
    }
  } else {
    // 1. Extract the part after "inspection/" if it exists
    const inspectionMatch = imagePath.match(/inspection[/\\](.*?)$/i);
    if (inspectionMatch && inspectionMatch[1]) {
      const relativePath = `src-api/data/images/inspection/${inspectionMatch[1].replace(/\\/g, '/')}`;
      // For temp sections (inspectionId = 0), don't include inspection_id parameter
      if (inspectionId > 0) {
        baseUrl = `${apiBaseUrl}/api/file?path=${encodeURIComponent(relativePath)}&inspection_id=${inspectionId}`;
      } else {
        baseUrl = `${apiBaseUrl}/api/stream/file?path=${encodeURIComponent(relativePath)}&convert=jpg`;
      }
    } else {
      // 2a. Memory preview virtual path (no disk)
      const memPreviewMatch = imagePath.match(/^memory-preview\//i);
      if (memPreviewMatch) {
        baseUrl = `${apiBaseUrl}/api/stream/memory-preview/${encodeURIComponent(imagePath.split('/')[1])}`;
      } else {
      // 2b. If path points to presentation cache, serve directly without inspection_id binding
      const presentationMatch = imagePath.match(/^presentation\//i);
      if (presentationMatch) {
        const relativePath = `src-api/data/images/${imagePath.replace(/\\/g, '/')}`;
        // Use streaming endpoint which doesn't enforce inspection_id
        baseUrl = `${apiBaseUrl}/api/stream/file?path=${encodeURIComponent(relativePath)}&convert=jpg`;
      } else {
        // 2c. Plain filenames like image_123.jpg should map to memory-preview/123 (temp sections)
        const plainImageMatch = imagePath.match(/^image_(\d+)\.(jpg|jpeg|png|bmp)$/i);
        if (plainImageMatch) {
          const idx = plainImageMatch[1];
          baseUrl = `${apiBaseUrl}/api/stream/memory-preview/${encodeURIComponent(idx)}`;
        } else {
        // 3. For other paths, assume they're already properly formatted
        if (inspectionId > 0) {
          baseUrl = `${apiBaseUrl}/api/file?path=${encodeURIComponent(imagePath)}&inspection_id=${inspectionId}`;
        } else {
          baseUrl = `${apiBaseUrl}/api/stream/file?path=${encodeURIComponent(imagePath)}&convert=jpg`;
        }
      }}}
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

  // Append params with correct separator (use '?' if none yet, otherwise '&')
  const finalUrl = params.toString()
    ? `${baseUrl}${baseUrl.includes('?') ? '&' : '?'}${params.toString()}`
    : baseUrl;

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
};

/**
 * Progressive image loading component (similar to InspectionDetailsModal)
 */
function ProgressiveImage({
  src,
  alt,
  inspectionId,
  className = '',
  style = {},
  onLoad,
  onClick,
  loading = 'lazy'
}: {
  src: string;
  alt: string;
  inspectionId: number;
  className?: string;
  style?: React.CSSProperties;
  onLoad?: () => void;
  onClick?: () => void;
  loading?: 'lazy' | 'eager';
}) {
  const [imageLoaded, setImageLoaded] = useState(false);
  const [lowQualityLoaded, setLowQualityLoaded] = useState(false);
  const [imageError, setImageError] = useState(false);

  const lowQualityUrl = getOptimizedImageUrl(src, inspectionId, { quality: 'low', progressive: true });
  const highQualityUrl = getOptimizedImageUrl(src, inspectionId, { quality: 'high' });

  // Reset error state when src changes
  useEffect(() => {
    setImageError(false);
    setImageLoaded(false);
    setLowQualityLoaded(false);
  }, [src]);

  const handleImageError = () => {
    setImageError(true);
    setLowQualityLoaded(true); // Stop showing loading spinner
  };

  // Show no-image placeholder if there's an error
  if (imageError) {
    return (
      <div
        style={{
          position: 'relative',
          minHeight: '48px',
          ...style
        }}
        className={className}
        // Remove onClick handler for no-image state - should not be clickable
      >
        <NoImagePlaceholder 
          className="w-full h-full"
          alt="No Image"
          // No onClick passed to NoImagePlaceholder for error state
        />
      </div>
    );
  }

  return (
    <div
      style={{
        position: 'relative',
        minHeight: '48px', // Ensure minimum height to prevent layout shift
        cursor: onClick ? 'pointer' : 'default', // Only show pointer cursor if clickable
        ...style
      }}
      className={className}
      {...(onClick && { onClick })}
    >
      {/* Low quality placeholder */}
      {!lowQualityLoaded && (
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            backgroundColor: '#f3f4f6',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}
        >
          <img
            src="/image-loading.gif"
            alt="Loading..."
            style={{
              width: '100%',
              height: '100%',
              objectFit: 'contain'
            }}
          />
        </div>
      )}

      {/* Low quality image */}
      <img
        src={lowQualityUrl}
        alt={alt}
        style={{
          ...style,
          opacity: imageLoaded ? 0 : 1,
          transition: 'opacity 0.3s ease',
          filter: 'blur(2px)',
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          objectFit: 'contain'
        }}
        onLoad={() => setLowQualityLoaded(true)}
        onError={handleImageError}
        loading={loading}
      />

      {/* High quality image */}
      {lowQualityLoaded && (
        <img
          src={highQualityUrl}
          alt={alt}
          style={{
            ...style,
            opacity: imageLoaded ? 1 : 0,
            transition: 'opacity 0.3s ease',
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            objectFit: 'contain'
          }}
          onLoad={() => {
            setImageLoaded(true);
            onLoad?.();
          }}
          onError={handleImageError}
          loading={loading}
        />
      )}
    </div>
  );
}

/**
 * Component for displaying a presentation image card with progressive loading
 */
const PresentationImageCard: React.FC<PresentationImageCardProps> = ({ 
  groupName, 
  imagePath,
  inspectionId,
  onImageTest,
  onOpenDetails 
}) => {
  return (
    <div className="bg-blue-100 border-2 border-gray-400 text-center rounded-lg shadow-md inspection-presentation-image flex-shrink-0 flex flex-col">
      <div className="bg-gray-100 text-responsive-xl font-bold py-0.5 border-b-2 border-gray-400 flex-shrink-0">
        {groupName}
      </div>
      <div className="flex-1 flex items-center justify-center p-0">
        {imagePath ? (
          <div className="w-full h-full relative overflow-hidden">
            <ProgressiveImage
              src={imagePath}
              alt={`Group ${groupName}`}
              inspectionId={inspectionId || 0} // Use 0 as fallback for temp sections
              className="w-full h-full"
              style={{ cursor: 'pointer' }}
              loading="eager"
              onLoad={() => {
                console.log(`✅ Image for group ${groupName} loaded successfully`);
                console.log(`✅ Loaded image path: ${imagePath}`);
              }}
              onClick={() => {
                // Always open the details modal from presentation images
                if (inspectionId) {
                  onOpenDetails?.(inspectionId, { group: groupName, imagePath });
                }
              }}
            />
          </div>
        ) : (
          <NoImagePlaceholder 
            className="w-full h-full"
            alt="No Image Available"
          />
        )}
      </div>
    </div>
  );
};

export default React.memo(PresentationImageCard);