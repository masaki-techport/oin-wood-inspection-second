import { useEffect, useRef, useState } from 'react';
import { dateToString } from '@/utils/cn';
import { Inspection, InspectionDetailsImg } from '@/types/api';
import { fetchAllImagesByPath, fetchInspectionResultById, fetchImageDetailsByImage, fetchPresentationImages, PresentationImage } from '@/features/inspections/api/inspections-details';
import { errorTypeColors, determineDefectStatus } from '@/utils/defectStatus';
import ImagePopupModal from '@/components/modal/ImagePopupModal';

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

// Propsの型定義
type Props = {
    inspection: Inspection;
    onClose: () => void;
};

// 画像一覧の型定義
type ImageItem = {
    id: number;
    path: string;
};

// Progressive image loading component with low-quality placeholders
function ProgressiveImage({
    src,
    alt,
    className = '',
    style = {},
    onLoad,
    onClick,
    loading = 'lazy'
}: {
    src: string;
    alt: string;
    className?: string;
    style?: React.CSSProperties;
    onLoad?: () => void;
    onClick?: () => void;
    loading?: 'lazy' | 'eager';
}) {
    const [imageLoaded, setImageLoaded] = useState(false);
    const [lowQualityLoaded, setLowQualityLoaded] = useState(false);

    const lowQualityUrl = getImageUrl(src, { quality: 'low', progressive: true });
    const highQualityUrl = getImageUrl(src, { quality: 'high' });

    return (
        <div
            style={{ position: 'relative', ...style }}
            className={className}
            onClick={onClick}
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
                    position: imageLoaded ? 'absolute' : 'static'
                }}
                onLoad={() => setLowQualityLoaded(true)}
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
                        transition: 'opacity 0.3s ease'
                    }}
                    onLoad={() => {
                        setImageLoaded(true);
                        onLoad?.();
                    }}
                    loading={loading}
                />
            )}
        </div>
    );
}

// 画像とバウンディングボックスを表示するコンポーネント
function ImageWithBoundingBoxes({ imageUrl, boxes }: { imageUrl: string; boxes: InspectionDetailsImg | InspectionDetailsImg[] | null; }) {

    const imgRef = useRef<HTMLImageElement>(null);
    const [imgSize, setImgSize] = useState<{ width: number; height: number } | null>(null);
    const displayWidth = 500; // 画像の表示幅
    const onImageLoad = () => {
        if (imgRef.current) {
            setImgSize({
                width: imgRef.current.naturalWidth,
                height: imgRef.current.naturalHeight,
            });
            // console.log("Image size:", imgRef.current.naturalWidth, "x", imgRef.current.naturalHeight); ok
        }
    };

    // バウンディングボックスがない場合は画像のみを表示
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



    // 画像のサイズに基づいてスケーリング
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
                        >
                            <span
                                style={{
                                    position: 'absolute',
                                    top: -20,
                                    left: 0,
                                    backgroundColor: color,
                                    color: 'white',
                                    fontSize: '12px',
                                    padding: '2px 4px',
                                    borderRadius: '2px',
                                    whiteSpace: 'nowrap',
                                    zIndex: 10,
                                }}
                            >
                                {box.error_type_name}
                            </span>
                        </div>
                    );
                }).filter(Boolean); // Remove null entries
            })()}
        </div>
    );
}

const InspectionDetailsModal = ({ inspection, onClose }: Props) => {
    // 画像一覧（フォルダ内の検査画像）
    const [images, setImages] = useState<ImageItem[]>([]);
    const totalImages = images.length;
    const groupCount = 5;
    const rangeSize = Math.ceil(totalImages / groupCount); // 100/5=20

    // 選択中のグループ（A〜E）
    const [selectedGroup, setSelectedGroup] = useState<string>('');

    // 代表的な画像 (Presentation images)
    const [presentationImages, setPresentationImages] = useState<PresentationImage[]>([]);

    // FIXED: Memoized group mapping to match backend grouping logic
    const [groupMapping, setGroupMapping] = useState<Record<number, string>>({});
    
    // Calculate group mapping when images change
    useEffect(() => {
        if (images.length === 0) return;
        
        // Get all image numbers and sort them (same as backend logic)
        const imageNoData = images
            .map(img => ({
                path: img.path,
                imageNo: extractImageNoFromPath(img.path)
            }))
            .filter(item => item.imageNo !== null);
        
        // Sort by image_no
        imageNoData.sort((a, b) => a.imageNo! - b.imageNo!);
        
        // Calculate group assignments using backend logic
        const totalImages = imageNoData.length;
        const groupCount = Math.min(5, totalImages);
        const newGroupMapping: Record<number, string> = {};
        
        if (groupCount <= 5 && totalImages > 0) {
            const groupSize = Math.floor(totalImages / groupCount);
            const remainder = totalImages % groupCount;
            
            let currentIndex = 0;
            const labels = ['A', 'B', 'C', 'D', 'E'];
            
            for (let i = 0; i < groupCount; i++) {
                const currentGroupSize = groupSize + (i < remainder ? 1 : 0);
                
                for (let j = 0; j < currentGroupSize && currentIndex < totalImages; j++) {
                    const imageNo = imageNoData[currentIndex].imageNo!;
                    newGroupMapping[imageNo] = labels[i];
                    currentIndex++;
                }
            }
        }
        
        setGroupMapping(newGroupMapping);
        console.log('🔄 Updated group mapping:', newGroupMapping);
        
    }, [images]);
    
    const getGroupLabel = (imagePath: string) => {
        const imageNo = extractImageNoFromPath(imagePath);
        if (imageNo === null) {
            console.warn(`Could not extract image_no from path: ${imagePath}`);
            return 'A'; // Default fallback
        }
        
        return groupMapping[imageNo] || 'A'; // Use memoized mapping
    };

    // 検査結果ラベルと詳細ステータス
    const [resultLabel, setResultLabel] = useState('読み込み中...');
    const [detailedStatus, setDetailedStatus] = useState('');
    const [isLoading, setIsLoading] = useState(true);
    // Remove caching to always fetch fresh data since inspection results can be updated

    // 選択中の画像・詳細
    const [selectedImage, setSelectedImage] = useState<string | null>(null);
    const [selectedPopupInfo, setSelectedPopupInfo] = useState<InspectionDetailsImg | InspectionDetailsImg[] | null>(null);
    const [loadingDetail, setLoadingDetail] = useState(false);
    const [apiError, setApiError] = useState<string | null>(null);

    // Enhanced defect status caching system with inspection result data
    const [imageDefectStatus, setImageDefectStatus] = useState<Record<number, {
        hasDefects: boolean;
        hasKnots: boolean;
        length: number;
        hasLargeKnot?: boolean;
        hasDiscoloration: boolean;
        hasHole: boolean;
    }>>({});

    // Note: Global inspection result data is still loaded for status indicators, but not used for border colors

    // Group filter state
    const [selectedGroupFilter, setSelectedGroupFilter] = useState<string>('A');

    // Track which images are currently loading defect data
    const [loadingImageDefects, setLoadingImageDefects] = useState<Set<number>>(new Set());

    // Helper function to extract image_no from image path using "No_????" pattern
    const extractImageNoFromPath = (imagePath: string): number | null => {
        if (!imagePath) return null;

        try {
            // Look for "No_" followed by digits in the path
            // Handle both forward and backward slashes, use the last occurrence
            const matches = imagePath.match(/No_(\d+)/g);
            if (matches && matches.length > 0) {
                // Use the last match in case there are multiple "No_" patterns
                const lastMatch = matches[matches.length - 1];
                const imageNoStr = lastMatch.replace('No_', '');
                const imageNo = parseInt(imageNoStr, 10);

                if (!isNaN(imageNo)) {
                    console.log(`Extracted image_no ${imageNo} from path: ${imagePath}`);
                    return imageNo;
                }
            }

            console.warn(`Could not extract image_no from path: ${imagePath}`);
            return null;
        } catch (error) {
            console.error(`Error extracting image_no from path ${imagePath}:`, error);
            return null;
        }
    };

    // Image preloading for better performance
    const preloadedImages = useRef<Set<string>>(new Set());
    const gridRef = useRef<HTMLDivElement>(null);

    const preloadImage = (imagePath: string) => {
        if (preloadedImages.current.has(imagePath)) return;

        const img = new Image();
        img.src = getImageUrl(imagePath, { quality: 'medium' });
        img.onload = () => {
            preloadedImages.current.add(imagePath);
        };
    };

    // Intersection observer for advanced lazy loading and defect data loading
    useEffect(() => {
        if (!gridRef.current) return;

        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        const img = entry.target as HTMLElement;
                        const imagePath = img.dataset.imagePath;
                        const imageNo = img.dataset.imageNo;

                        if (imagePath) {
                            preloadImage(imagePath);
                        }

                        // Also load defect data for visible images
                        if (imageNo) {
                            const imageId = parseInt(imageNo, 10);
                            if (!isNaN(imageId)) {
                                loadImageDefectData(imageId);
                            }
                        }
                    }
                });
            },
            {
                root: gridRef.current,
                rootMargin: '50px',
                threshold: 0.1
            }
        );

        // Observe all image containers
        const imageContainers = gridRef.current.querySelectorAll('[data-image-path]');
        imageContainers.forEach((container) => observer.observe(container));

        return () => observer.disconnect();
    }, [images, selectedGroupFilter]);



    // Cleanup function to prevent memory leaks
    useEffect(() => {
        const currentPreloadedImages = preloadedImages.current;
        return () => {
            // Clear image cache when component unmounts
            Object.keys(imageUrlCache).forEach(key => {
                delete imageUrlCache[key];
            });
            currentPreloadedImages.clear();
        };
    }, []);

    // Helper function to determine if image has defects based on cached data
    const hasDefects = (imageNo: number): boolean => {
        const defectData = imageDefectStatus[imageNo];
        return defectData ? defectData.hasDefects : false;
    };

    // Function to automatically load individual image defect data
    const loadImageDefectData = async (imageId: number) => {
        // Use imageId as the key for caching (this will be img.id which is 0-based)
        // Skip if already loaded or currently loading
        if (imageDefectStatus[imageId] || loadingImageDefects.has(imageId)) {
            return;
        }

        // Mark as loading
        setLoadingImageDefects(prev => new Set(prev).add(imageId));

        try {
            // Use imageId directly for API call (0-based to match database)
            const res = await fetchImageDetailsByImage({
                inspection_id: inspection.inspection_id,
                image_no: imageId
            });

            if (res && res.result && res.data && res.data.length > 0) {
                // Analyze the defect data to determine knot information
                const hasKnots = res.data.some((defect: any) =>
                    defect.error_type === 2 || // 死に節 (dead knot)
                    defect.error_type === 3 || // 流れ節_死 (tight knot dead)
                    defect.error_type === 4 || // 流れ節_生 (tight knot live)
                    defect.error_type === 5    // 生き節 (live knot)
                );

                const hasDiscoloration = res.data.some((defect: any) => defect.error_type === 0);
                const hasHole = res.data.some((defect: any) => defect.error_type === 1);

                // Calculate length based on knot defects (if any)
                // Check if ANY knot defect has length >= 10 (for 節あり vs こぶし classification)
                let maxLength = 0;
                let hasLargeKnot = false;
                if (hasKnots) {
                    res.data.forEach((defect: any) => {
                        if (defect.error_type >= 2 && defect.error_type <= 5) {
                            // Use the length field directly from the database if available
                            const defectLength = defect.length || 0;
                            maxLength = Math.max(maxLength, defectLength);

                            // Check if this defect is large (>= 10)
                            if (defectLength >= 10) {
                                hasLargeKnot = true;
                            }
                        }
                    });
                }

                setImageDefectStatus(prev => ({
                    ...prev,
                    [imageId]: {
                        hasDefects: true,
                        hasKnots,
                        length: maxLength,
                        hasLargeKnot,
                        hasDiscoloration,
                        hasHole
                    }
                }));
            } else {
                // No defects found
                setImageDefectStatus(prev => ({
                    ...prev,
                    [imageId]: {
                        hasDefects: false,
                        hasKnots: false,
                        length: 0,
                        hasLargeKnot: false,
                        hasDiscoloration: false,
                        hasHole: false
                    }
                }));
            }
        } catch (error) {
            console.error(`Failed to load defect data for image ${imageId}:`, error);
            // Cache as no defects to avoid repeated failed calls
            setImageDefectStatus(prev => ({
                ...prev,
                [imageId]: {
                    hasDefects: false,
                    hasKnots: false,
                    length: 0,
                    hasLargeKnot: false,
                    hasDiscoloration: false,
                    hasHole: false
                }
            }));
        } finally {
            // Remove from loading set
            setLoadingImageDefects(prev => {
                const newSet = new Set(prev);
                newSet.delete(imageId);
                return newSet;
            });
        }
    };

    // Helper function to get border color based on individual image defect data
    const getBorderColor = (imageId: number): string => {
        // Automatically load defect data for this image if not already loaded/loading
        if (!imageDefectStatus[imageId] && !loadingImageDefects.has(imageId)) {
            loadImageDefectData(imageId);
        }

        // If we have specific defect data for this image, use it
        const defectData = imageDefectStatus[imageId];
        if (defectData) {
            if (!defectData.hasDefects) {
                return 'border-green-500'; // 無欠点 (no defects)
            }

            // Check if image has knots and determine classification
            if (defectData.hasKnots) {
                // If ANY knot defect has length >= 10, it's 節あり (red)
                // If ALL knot defects have length < 10, it's こぶし (yellow)
                return defectData.hasLargeKnot ? 'border-red-500' : 'border-yellow-500';
            }

            // If has defects but no knots (discoloration/hole only), default to green
            return 'border-green-500';
        }

        // If data is still loading, show gray border
        if (loadingImageDefects.has(imageId)) {
            return 'border-gray-400';
        }

        // Default to gray while waiting for data to load
        return 'border-gray-400';
    };

    // 画像クリック時の詳細取得処理 - Fixed to properly handle extracted image_no and group labels
    const onClickImage = async (src: string, imageNo: number, groupLabel?: string) => {
        console.log(`onClickImage called: src=${src}, imageNo=${imageNo}, groupLabel=${groupLabel}`);

        // For presentation images, use the provided group label directly
        // For grid images, calculate the group from imageNo using the mapping
        const group = groupLabel || (groupMapping[imageNo] || 'A');
        console.log(`Setting selected group to: ${group}`);

        setSelectedGroup(group);
        setSelectedImage(src);
        setLoadingDetail(true);
        setApiError(null);
        setSelectedPopupInfo(null);

        try {
            // Use the API to get defect details for popup display (use imageNo directly)
            console.log(`Fetching image details for inspection_id=${inspection.inspection_id}, image_no=${imageNo}`);
            const res = await fetchImageDetailsByImage({
                inspection_id: inspection.inspection_id,
                image_no: imageNo
            });

            console.log(`API response for image ${imageNo}:`, res);

            if (res && res.result && res.data && res.data.length > 0) {
                // If multiple bounding boxes exist for this image, pass them all
                // If only one, pass it as a single object for backward compatibility
                setSelectedPopupInfo(res.data.length === 1 ? res.data[0] : res.data);
                console.log(`Found ${res.data.length} defects for image ${imageNo}`);
            } else {
                // For images with no defects (無欠点), this is normal - don't show as error
                setSelectedPopupInfo(null);
                console.log(`No defects found for image ${imageNo} - this is normal for 無欠点 images`);

                // Only show error if the API actually failed with a real error message
                if (res && !res.result && res.message) {
                    // Don't show error for "no data found" messages - these are normal for 無欠点 images
                    const normalNoDataMessages = [
                        '指定された検査情報が存在しません',
                        'No inspection details found',
                        'no data found',
                        'データが見つかりません'
                    ];

                    const isNormalNoData = normalNoDataMessages.some(msg =>
                        res.message.toLowerCase().includes(msg.toLowerCase())
                    );

                    if (!isNormalNoData) {
                        setApiError(res.message || '画像詳細の読み込みに失敗しました');
                        console.error(`API error for image ${imageNo}:`, res.message);
                    }
                }
            }
        } catch (e: any) {
            setSelectedPopupInfo(null);
            setApiError('通信エラーが発生しました。ネットワーク接続を確認してください。');
            console.error('Error fetching image details:', e);
        } finally {
            setLoadingDetail(false);
        }
    };


    useEffect(() => {
        // Always fetch fresh data when modal opens or inspection changes
        console.log(`Fetching fresh data for inspection ${inspection.inspection_id}`);

        // Set loading state
        setIsLoading(true);
        setResultLabel('読み込み中...');
        setDetailedStatus('');
        // Reset individual image defect status when modal opens
        setImageDefectStatus({});
        setLoadingImageDefects(new Set());

        // Load presentation images for the inspection with better error handling and deduplication
        fetchPresentationImages({ id: inspection.inspection_id })
            .then((res) => {
                if (res && res.result && res.data && res.data.length > 0) {
                    console.log(`Loaded ${res.data.length} presentation images for inspection ${inspection.inspection_id}`);
                    console.log('Raw presentation images data:', res.data);

                    // Enhanced database debugging to identify duplication issues
                    const groupCounts: Record<string, number> = {};
                    const duplicateDetails: Record<string, any[]> = {};

                    res.data.forEach((img: any) => {
                        if (!groupCounts[img.group_name]) {
                            groupCounts[img.group_name] = 0;
                            duplicateDetails[img.group_name] = [];
                        }
                        groupCounts[img.group_name]++;
                        duplicateDetails[img.group_name].push({
                            id: img.id,
                            path: img.image_path,
                            inspection_id: img.inspection_id
                        });
                    });

                    // Log database duplication issues
                    const duplicateGroups = Object.keys(groupCounts).filter(group => groupCounts[group] > 1);
                    if (duplicateGroups.length > 0) {
                        console.error(`DATABASE ISSUE: Found duplicate presentation images for groups: ${duplicateGroups.join(', ')}`);
                        duplicateGroups.forEach(group => {
                            console.error(`  Group ${group} has ${groupCounts[group]} entries:`);
                            duplicateDetails[group].forEach((detail, index) => {
                                console.error(`    ${index + 1}. ID=${detail.id}, Path=${detail.path}, InspectionID=${detail.inspection_id}`);
                            });
                        });
                        console.error('This indicates a database integrity issue that should be investigated.');
                    }

                    // Frontend deduplication: Keep the first occurrence of each group_name
                    // This handles database duplicates gracefully while the backend issue is resolved
                    const uniquePresentationImages = res.data.filter((img: any, index: number, array: any[]) =>
                        array.findIndex((item: any) => item.group_name === img.group_name) === index
                    );

                    if (uniquePresentationImages.length !== res.data.length) {
                        const filteredCount = res.data.length - uniquePresentationImages.length;
                        console.warn(`FRONTEND DEDUPLICATION: Filtered out ${filteredCount} duplicate presentation images`);
                        console.warn('Unique images after deduplication:', uniquePresentationImages.map((img: any) => ({
                            group: img.group_name,
                            id: img.id,
                            path: img.image_path
                        })));
                    }

                    setPresentationImages(uniquePresentationImages);

                    // Preload presentation images and load their defect data for better performance
                    uniquePresentationImages.forEach((img) => {
                        if (img && img.image_path) {
                            preloadImage(img.image_path);

                            // Extract image_no from path and load defect data
                            const imageNo = extractImageNoFromPath(img.image_path);
                            if (imageNo !== null) {
                                // Load defect data for presentation images immediately since they're always visible
                                loadImageDefectData(imageNo);
                                console.log(`Loading defect data for presentation image ${img.group_name}: image_no=${imageNo}, path=${img.image_path}`);
                            } else {
                                console.error(`プレゼンテーション画像の画像番号の取得に失敗しました: グループ=${img.group_name}, パス=${img.image_path}`);
                            }
                        }
                    });
                } else {
                    console.warn('No presentation images found or API returned empty result');
                    setPresentationImages([]);
                }
            })
            .catch((err) => {
                console.error('Failed to load presentation images:', err);
                setPresentationImages([]);
            });

        const getRelativePath = (fullPath: string) => {
            if (!fullPath) return '';
            const idx = fullPath.lastIndexOf('inspection');
            if (idx !== -1) {
                return fullPath.substring(idx).replace(/\\/g, '/');
            }
            return fullPath.replace(/\\/g, '/');
        };

        const relativePath = getRelativePath(inspection.file_path);

        // 1. 検査画像一覧APIの呼び出し with better error handling
        if (relativePath) {
            fetchAllImagesByPath({ path: relativePath })
                .then((res) => {
                    if (res && res.result && res.data && Array.isArray(res.data)) {
                        // map id + path
                        const fullData: ImageItem[] = res.data.map((name: string, index: number) => ({
                            id: index,
                            path: `data/images/${relativePath}/${name}`,
                        }));
                        setImages(fullData);

                        // Preload first 20 images for better performance
                        fullData.slice(0, 20).forEach((img) => {
                            if (img && img.path) {
                                preloadImage(img.path);
                            }
                        });
                    } else {
                        console.error('API画像エラー:', res?.message || 'Invalid response format');
                        setImages([]);
                    }
                })
                .catch((err) => {
                    console.error('API画像呼び出し失敗:', err);
                    setImages([]);
                });
        } else {
            console.warn('Invalid file path, cannot load images');
            setImages([]);
        }

        // 2. 検査結果詳細APIの呼び出し with better error handling
        console.log(`Fetching inspection result for ID: ${inspection.inspection_id}`);
        fetchInspectionResultById({ id: inspection.inspection_id })
            .then((res) => {
                console.log(`Inspection result API response:`, res);
                if (res && res.result && res.data) {
                    const {
                        discoloration,
                        hole,
                        knot,
                        dead_knot,
                        live_knot,
                        tight_knot,
                        length,
                    } = res.data;

                    // ラベル設定 - Primary result based on knots only
                    if (knot || dead_knot || live_knot || tight_knot) {
                        setResultLabel(length >= 10 ? '節あり​' : 'こぶし');
                    } else {
                        setResultLabel('無欠点');
                    }

                    // 詳細ステータスを作成 - Secondary defect type for holes/discoloration
                    const statusList: string[] = [];

                    if (discoloration) statusList.push('変色発生');
                    if (hole) statusList.push('穴発生');

                    const combinedStatus = statusList.join('●');
                    setDetailedStatus(combinedStatus || '');

                    // Global inspection result data is no longer used for border colors
                    // Individual images now load their own defect data automatically

                } else {
                    console.error('API検査結果エラー:', res?.message || 'Invalid response format');
                    setResultLabel('データなし');
                }
            })
            .catch((err) => {
                console.error('API検査結果呼び出し失敗:', err);
                console.error('Error details:', {
                    message: err?.message,
                    response: err?.response,
                    status: err?.response?.status,
                    data: err?.response?.data
                });
                setResultLabel('通信エラー');
            })
            .finally(() => {
                setIsLoading(false);
            });
    }, [inspection.inspection_id, inspection.file_path]); // Use inspection_id and file_path as dependencies

    // getImageUrl is now defined at the top level of the file

    return (
        <div className="fixed inset-0 bg-black bg-opacity-40 flex items-center justify-center z-50">
            <div className="bg-white w-[1000px] relative border-4 border-gray-800">

                {/* Header with OIN logo */}
                <div className="text-white bg-cyan-800 text-2xl font-bold py-3 px-4 mb-4 flex items-center justify-between">
                    <div className="flex items-center">
                        <div className="bg-white text-cyan-800 px-2 py-1 rounded mr-4 font-bold text-lg">
                            OIN
                        </div>
                        <span>木材検査システム　検査結果</span>
                    </div>
                </div>

                {/* Body */}
                <div className='relative px-6 pb-6'>
                    {/* 時間・板No - Centered and on same row */}
                    <div className="text-center mb-6 text-xl font-bold">
                        <span className="mr-12">
                            {inspection.inspection_dt ? dateToString(inspection.inspection_dt) : '日時不明'}
                        </span>
                        <span>板No:{inspection.inspection_id || 'ID不明'}</span>
                    </div>

                    {/* 閉じるボタン - Positioned in top right of body */}
                    <div className="absolute top-4 right-6">
                        <button
                            onClick={onClose}
                            className="bg-cyan-800 text-white font-bold text-lg px-4 py-1 rounded border-2 border-white"
                        >
                            閉じる
                        </button>
                    </div>

                    {/* Status indicators - Center layout */}
                    <div className="flex justify-center gap-4 mb-8">
                        <div className={`${isLoading ? 'bg-gray-500' :
                                resultLabel === '通信エラー' ? 'bg-red-800' :
                                    resultLabel === '無欠点' ? 'bg-green-600' :
                                        resultLabel === 'こぶし' ? 'bg-yellow-600' :
                                            resultLabel === '節あり​' ? 'bg-red-600' :
                                                'bg-red-600'
                            } text-white font-bold text-lg px-8 py-2 border-2 border-black`}>
                            {resultLabel}
                        </div>
                        {detailedStatus && (
                            <div className="bg-orange-500 text-white font-bold text-lg px-8 py-2 border-2 border-black">
                                {detailedStatus}
                            </div>
                        )}
                    </div>

                    {/* Presentation Images (A-E) - Top section with wood board visualization */}
                    <div className="flex justify-center mb-8">
                        <div className="grid grid-cols-5 gap-4">
                            {['A', 'B', 'C', 'D', 'E'].map((label, i) => {
                                const presentationImage = presentationImages.find(img => img.group_name === label);
                                console.log(`Group ${label}: found image:`, presentationImage);

                                if (presentationImage) {
                                    console.log(`  - Group ${label}: ID=${presentationImage.id}, Path=${presentationImage.image_path}`);
                                } else {
                                    console.warn(`  - Group ${label}: No presentation image found`);
                                }

                                // Extract image_no from path, log failure if not found
                                let imageNo: number | null = null;
                                if (presentationImage) {
                                    imageNo = extractImageNoFromPath(presentationImage.image_path);
                                    if (imageNo === null) {
                                        console.error(`❌ FRONTEND: Failed to extract image_no for presentation image:`);
                                        console.error(`  Group: ${label}`);
                                        console.error(`  Path: ${presentationImage.image_path}`);
                                        console.error(`  Database ID: ${presentationImage.id}`);
                                        console.error(`  Inspection ID: ${presentationImage.inspection_id}`);
                                        console.error(`  This indicates a path format issue that needs backend investigation.`);
                                    } else {
                                        console.log(`✅ FRONTEND: Successfully extracted image_no ${imageNo} for group ${label}`);
                                        console.log(`  Path: ${presentationImage.image_path}`);
                                        console.log(`  Database ID: ${presentationImage.id}`);
                                        console.log(`  This image_no will be used for defect detection and border colors.`);
                                    }
                                }

                                const borderColor = (presentationImage && imageNo !== null) ? getBorderColor(imageNo) : 'border-green-500';

                                return (
                                    <div key={`presentation-${label}-${presentationImage?.id || i}`} className="flex flex-col items-center">
                                        {/* Wood board visualization */}
                                        <div className={`w-40 h-30 border-4 ${borderColor} bg-white mb-2 relative cursor-pointer overflow-hidden`}
                                            onClick={() => {
                                                if (presentationImage && imageNo !== null) {
                                                    console.log(`Presentation image clicked: Group=${label}, ImageNo=${imageNo}, Path=${presentationImage.image_path}`);
                                                    onClickImage(presentationImage.image_path, imageNo, label);
                                                } else {
                                                    console.warn(`Cannot click presentation image: Group=${label}, ImageNo=${imageNo}, HasImage=${!!presentationImage}`);
                                                }
                                            }}>
                                            {/* Show actual image instead of yellow section */}
                                            {presentationImage ? (
                                                <ProgressiveImage
                                                    src={presentationImage.image_path}
                                                    alt={`Group ${label}`}
                                                    className="w-full h-full object-cover"
                                                    loading="eager"
                                                />
                                            ) : (
                                                <div className="w-full h-full bg-gray-200 flex items-center justify-center text-gray-500 text-sm">
                                                    No Image
                                                </div>
                                            )}
                                        </div>
                                        {/* Label */}
                                        <div className="text-xl font-bold">
                                            {label}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    {/* Bottom section with group dropdown above image grid */}
                    <div className="flex flex-col gap-4">
                        {/* Group dropdown - moved above image grid */}
                        <div className="flex justify-start">
                            <select
                                value={selectedGroupFilter}
                                onChange={(e) => setSelectedGroupFilter(e.target.value)}
                                className="border-2 border-gray-400 rounded px-3 py-2 text-sm bg-white min-w-[100px]"
                            >
                                <option value="all">全て</option>
                                <option value="A">A</option>
                                <option value="B">B</option>
                                <option value="C">C</option>
                                <option value="D">D</option>
                                <option value="E">E</option>
                            </select>
                        </div>

                        {/* Image grid */}
                        <div className="w-full">
                            <div
                                ref={gridRef}
                                className="border-4 border-gray-800 bg-white p-2"
                                style={{
                                    height: '200px',
                                    overflowY: images.filter((img) => {
                                        if (selectedGroupFilter === 'all') return true;
                                        // FIXED: Use path-based grouping to match backend logic
                                        const imageGroup = getGroupLabel(img.path);
                                        return imageGroup === selectedGroupFilter;
                                    }).length > 40 ? 'auto' : 'hidden'
                                }}
                            >
                                <div className="grid grid-cols-10 gap-1">
                                    {images.length > 0 ? images
                                        .filter((img) => {
                                            if (selectedGroupFilter === 'all') return true;
                                            // FIXED: Use path-based grouping to match backend logic
                                            const imageGroup = getGroupLabel(img.path);
                                            return imageGroup === selectedGroupFilter;
                                        })
                                        .map((img, i) => {
                                            // FIXED: Extract actual image_no from path for consistency
                                            const extractedImageNo = extractImageNoFromPath(img.path);
                                            const imageGroup = getGroupLabel(img.path);
                                            
                                            // Use extracted image_no for API calls and border colors
                                            const borderColor = extractedImageNo !== null ? getBorderColor(extractedImageNo) : 'border-gray-400';

                                            return (
                                                <div
                                                    key={`grid-${img.id}-${imageDefectStatus[extractedImageNo || img.id] ? 'loaded' : 'loading'}`}
                                                    className={`w-16 h-12 border-2 ${borderColor} bg-white cursor-pointer relative overflow-hidden`}
                                                    data-image-path={img.path}
                                                    data-image-no={extractedImageNo || img.id}
                                                    onClick={() => {
                                                        if (extractedImageNo !== null) {
                                                            console.log(`✅ Grid image clicked: ExtractedImageNo=${extractedImageNo}, Path=${img.path}, Group=${imageGroup}`);
                                                            onClickImage(img.path, extractedImageNo, imageGroup);
                                                        } else {
                                                            console.error(`❌ Could not extract image_no from path: ${img.path}`);
                                                        }
                                                    }}
                                                >
                                                    {/* Show actual thumbnail image instead of yellow section */}
                                                    <ProgressiveImage
                                                        src={img.path}
                                                        alt={`Image ${extractedImageNo || img.id}`}
                                                        className="w-full h-full object-cover"
                                                        loading="lazy"
                                                    />
                                                </div>
                                            );
                                        }) : (
                                        <div className="col-span-10 flex items-center justify-center h-20 text-gray-500">
                                            {isLoading ? (
                                                <img
                                                    src="/image-loading.gif"
                                                    alt="画像を読み込み中..."
                                                    style={{
                                                        width: '40px',
                                                        height: '40px',
                                                        objectFit: 'contain'
                                                    }}
                                                />
                                            ) : '画像データがありません'}
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>

                </div>

                {/* 画像が選択されたときにポップアップを表示する */}
                {selectedImage !== null && (
                    <ImagePopupModal
                        isOpen={selectedImage !== null}
                        onClose={() => {
                            setSelectedImage(null);
                            setSelectedPopupInfo(null);
                            setApiError(null);
                            setLoadingDetail(false);
                        }}
                        imageUrl={selectedImage}
                        imageIdentifier={selectedGroup}
                        defectData={selectedPopupInfo}
                        defectStatus={determineDefectStatus(selectedPopupInfo)}
                        isLoading={loadingDetail}
                        error={apiError}
                        onRetry={() => {
                            // Retry logic - re-trigger the API call for the current image
                            if (selectedImage) {
                                // Extract image number from the selected image path to retry the API call
                                const imageNo = extractImageNoFromPath(selectedImage);
                                if (imageNo !== null) {
                                    onClickImage(selectedImage, imageNo, selectedGroup);
                                }
                            }
                        }}
                    />
                )}
            </div>
        </div>
    );
};

export default InspectionDetailsModal;

