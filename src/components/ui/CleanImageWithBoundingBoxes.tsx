import React, { useRef, useState } from 'react';
import { InspectionDetailsImg } from '@/types/api';
import { errorTypeColors } from '@/utils/defectStatus';

// URL cache to avoid recalculating the same URLs
const imageUrlCache: Record<string, string> = {};
const MAX_CACHE_SIZE = 1000;

// Function to properly convert image paths to URLs that work with the API with performance optimizations
const getImageUrl = (imagePath: string, options: {
    quality?: 'low' | 'medium' | 'high';
    size?: 'thumbnail' | 'medium' | 'full';
    progressive?: boolean;
} = {}): string => {
    if (!imagePath) return '';

    const { quality = 'medium', size = 'full', progressive = false } = options;
    const cacheKey = `${imagePath}:${quality}:${size}:${progressive}`;

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
            baseUrl = `${apiBaseUrl}/api/file?path=${encodeURIComponent(relativePath)}`;
        }
    } else {
        // 1. Extract the part after "inspection/" if it exists
        const inspectionMatch = imagePath.match(/inspection[/\\](.*?)$/i);
        if (inspectionMatch && inspectionMatch[1]) {
            const relativePath = `src-api/data/images/inspection/${inspectionMatch[1].replace(/\\/g, '/')}`;
            baseUrl = `${apiBaseUrl}/api/file?path=${encodeURIComponent(relativePath)}`;
        } else {
            // 2. For full paths, assume they're already properly formatted
            baseUrl = `${apiBaseUrl}/api/file?path=${encodeURIComponent(imagePath)}`;
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
};

interface CleanImageWithBoundingBoxesProps {
    imageUrl: string;
    boxes: InspectionDetailsImg | InspectionDetailsImg[] | null;
}

const CleanImageWithBoundingBoxes: React.FC<CleanImageWithBoundingBoxesProps> = ({ imageUrl, boxes }) => {
    const imgRef = useRef<HTMLImageElement>(null);
    const [imgSize, setImgSize] = useState<{ width: number; height: number } | null>(null);
    const displayWidth = 600; // Increased from 500px to 600px for better visibility

    const onImageLoad = () => {
        if (imgRef.current) {
            setImgSize({
                width: imgRef.current.naturalWidth,
                height: imgRef.current.naturalHeight,
            });
        }
    };

    // If no bounding boxes, display image only
    if (!boxes) {
        return (
            <div style={{ position: 'relative', display: 'inline-block' }}>
                <img
                    ref={imgRef}
                    src={getImageUrl(imageUrl, { quality: 'high' })}
                    alt="Selected"
                    style={{ display: 'block', width: displayWidth, height: 'auto' }}
                    onLoad={onImageLoad}
                />
            </div>
        );
    }

    // Calculate scaling based on image size
    const scaleX = imgSize ? displayWidth / imgSize.width : 1;
    const scaleY = scaleX; // Same scaling factor to maintain aspect ratio

    return (
        <div style={{ position: 'relative', display: 'inline-block' }}>
            <img
                ref={imgRef}
                src={getImageUrl(imageUrl, { quality: 'high' })}
                alt="Selected"
                style={{ display: 'block', width: displayWidth, height: 'auto' }}
                onLoad={onImageLoad}
            />
            {imgSize && boxes && (() => {
                // Handle both single object and array of InspectionDetailsImg
                const boxArray = Array.isArray(boxes) ? boxes : [boxes];

                return boxArray.map((box, index) => {
                    // Validate bounding box coordinates
                    if (!box || typeof box.x_position !== 'number' || typeof box.y_position !== 'number' ||
                        typeof box.width !== 'number' || typeof box.height !== 'number') {
                        return null;
                    }

                    // The database stores coordinates in xyxy format (x1, y1, x2, y2)
                    // but names them as x_position, y_position, width, height
                    // So we need to convert from xyxy to xywh format for display
                    const x1 = box.x_position;
                    const y1 = box.y_position;
                    const x2 = box.width;    // This is actually x2, not width
                    const y2 = box.height;   // This is actually y2, not height

                    // Convert to actual width and height
                    const actualWidth = x2 - x1;
                    const actualHeight = y2 - y1;

                    // Apply scaling
                    const left = x1 * scaleX;
                    const top = y1 * scaleY;
                    const width = actualWidth * scaleX;
                    const height = actualHeight * scaleY;

                    const color = errorTypeColors[box.error_type] || 'rgba(128, 128, 128, 0.7)'; // fallback color

                    return (
                        <div
                            key={index}
                            style={{
                                position: 'absolute',
                                border: `2px solid ${color}`,
                                left,
                                top,
                                width,
                                height,
                                pointerEvents: 'none',
                            }}
                        />
                    );
                }).filter(Boolean); // Remove null entries
            })()}
        </div>
    );
};

export default CleanImageWithBoundingBoxes;