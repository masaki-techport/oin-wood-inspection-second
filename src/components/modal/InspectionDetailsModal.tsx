import { useEffect, useRef, useState } from 'react';
import { dateToString } from '@/utils/cn';
import { Inspection, InspectionDetailsImg } from '@/types/api';
import { fetchInspectionResultById, fetchImageDetailsByImage, fetchPresentationImages, fetchInspectionImages, PresentationImage, InspectionImage } from '@/features/inspections/api/inspections-details';
import { errorTypeColors, determineDefectStatus } from '@/utils/defectStatus';
import { buildApiFileUrl, extractImageNoFromPath as extractImageNoFromPathUtil } from '@/utils/image-path';
import ImagePopupModal from '@/components/modal/ImagePopupModal';
import StandardHeader from '@/components/ui/StandardHeader';
import NoImagePlaceholder from '@/components/ui/NoImagePlaceholder';
import { getBackgroundColor, determineInspectionResult, determineDefectType } from '@/app/routes/app/inspection/utils/colorManager';

// URL cache to avoid recalculating the same URLs
const imageUrlCache: Record<string, string> = {};
const MAX_CACHE_SIZE = 1000;



// Function to properly convert image paths to URLs that work with the API with performance optimizations
const getImageUrl = (imagePath: string, inspectionId: number, options: {
    quality?: 'low' | 'medium' | 'high';
    size?: 'thumbnail' | 'medium' | 'full';
    progressive?: boolean;
} = {}): string => {
    // Delegate to shared util while retaining local caching key to avoid widespread changes
    const url = buildApiFileUrl(imagePath, inspectionId, options as any);
    return url;
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
    image_no?: number;
    image_type?: string;
};

// Progressive image loading component with low-quality placeholders
function ProgressiveImage({
    src,
    alt,
    inspectionId,
    className = '',
    style = {},
    onLoad,
    onClick,
    loading = 'lazy',
    onImageError
}: {
    src: string;
    alt: string;
    inspectionId: number;
    className?: string;
    style?: React.CSSProperties;
    onLoad?: () => void;
    onClick?: () => void;
    loading?: 'lazy' | 'eager';
    onImageError?: () => void;
}) {
    const [imageLoaded, setImageLoaded] = useState(false);
    const [lowQualityLoaded, setLowQualityLoaded] = useState(false);
    const [imageError, setImageError] = useState(false);

    const lowQualityUrl = getImageUrl(src, inspectionId, { quality: 'low', progressive: true });
    const highQualityUrl = getImageUrl(src, inspectionId, { quality: 'high' });

    // Reset error state when src changes
    useEffect(() => {
        setImageError(false);
        setImageLoaded(false);
        setLowQualityLoaded(false);
    }, [src]);

    const handleImageError = () => {
        setImageError(true);
        setLowQualityLoaded(true); // Stop showing loading spinner
        onImageError?.(); // Notify parent component of image error
    };

    // Show no-image placeholder if there's an error
    if (imageError) {
        return (
            <div
                style={{
                    position: 'relative',
                    minHeight: '48px',
                    cursor: 'default', // Ensure no-image state is not clickable
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
                    objectFit: 'cover'
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
                        objectFit: 'cover'
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

// 画像とバウンディングボックスを表示するコンポーネント
function ImageWithBoundingBoxes({ imageUrl, boxes, inspectionId }: { imageUrl: string; boxes: InspectionDetailsImg | InspectionDetailsImg[] | null; inspectionId: number; }) {

    const imgRef = useRef<HTMLImageElement>(null);
    const [imgSize, setImgSize] = useState<{ width: number; height: number } | null>(null);
    const [imageError, setImageError] = useState(false);
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

    const onImageError = () => {
        setImageError(true);
    };

    // Show no-image placeholder if there's an error
    if (imageError) {
        return (
            <div style={{ 
                position: 'relative', 
                display: 'inline-block',
                cursor: 'default' // Ensure no-image state is not clickable
            }}>
                <NoImagePlaceholder 
                    style={{ display: 'block', width: displayWidth, height: 'auto' }}
                    alt="No Image"
                    // No onClick passed to NoImagePlaceholder for error state
                />
            </div>
        );
    }

    // バウンディングボックスがない場合は画像のみを表示
    if (!boxes) {
        return (
            <div style={{ position: 'relative', display: 'inline-block' }}>
                <img
                    ref={imgRef}
                    src={getImageUrl(imageUrl, inspectionId, { quality: 'high' })}
                    alt="Selected"
                    style={{ display: 'block', width: displayWidth, height: 'auto' }}
                    onLoad={onImageLoad}
                    onError={onImageError}
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
                src={getImageUrl(imageUrl, inspectionId, { quality: 'high' })}
                alt="Selected"
                style={{ display: 'block', width: displayWidth, height: 'auto' }}
                onLoad={onImageLoad}
                onError={onImageError}
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



                    // Use the correct coordinates from the database
                    const x1 = box.x_position;
                    const y1 = box.y_position;
                    const x2 = box.x2_position;
                    const y2 = box.y2_position;

                    // Calculate width and height from coordinates
                    const actualWidth = box.width;
                    const actualHeight = box.height;

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
    
    // Helper function to check if an image is a presentation image
    const isPresentationImage = (imagePath: string): boolean => {
        if (!presentationImages.length || !imagePath) return false;
        
        // Extract filename from path (e.g., "No_0002.bmp")
        const getFilename = (path: string) => path.split('/').pop()?.split('\\').pop() || path;
        const currentFilename = getFilename(imagePath);
        
        // Check if this filename matches any presentation image filename
        return presentationImages.some(presentationImg => {
            const presentationFilename = getFilename(presentationImg.image_path);
            return presentationFilename === currentFilename;
        });
    };
    
    // Calculate group mapping when images change
    useEffect(() => {
        if (images.length === 0) return;
        
        // Get all image numbers and sort them (same as backend logic)
        const imageNoData = images
            .map(img => ({
                path: img.path,
                imageNo: img.image_no || extractImageNoFromPath(img.path)
            }))
            .filter(item => item.imageNo !== null && item.imageNo !== undefined);
        
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
        
    }, [images]);
    
    const getGroupLabel = (imagePath: string, imageNo?: number) => {
        // Use imageNo from database if available, otherwise extract from path
        const actualImageNo = imageNo !== undefined ? imageNo : extractImageNoFromPath(imagePath);
        if (actualImageNo === null) {
            console.warn(`Could not determine image_no for path: ${imagePath}`);
            return 'A'; // Default fallback
        }
        
        return groupMapping[actualImageNo] || 'A'; // Use memoized mapping
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
    
    // Track which presentation images have failed to load
    const [failedPresentationImages, setFailedPresentationImages] = useState<Set<string>>(new Set());
    // Track which grid images have failed to load
    const [failedGridImages, setFailedGridImages] = useState<Set<string>>(new Set());

    // Helper function to extract image_no from image path using "No_????" pattern
    const extractImageNoFromPath = (imagePath: string): number | null => extractImageNoFromPathUtil(imagePath);

    // Image preloading for better performance
    const preloadedImages = useRef<Set<string>>(new Set());
    const gridRef = useRef<HTMLDivElement>(null);

    const preloadImage = (imagePath: string) => {
        if (preloadedImages.current.has(imagePath)) return;

        const img = new Image();
        img.src = buildApiFileUrl(imagePath, inspection.inspection_id, { quality: 'medium' });
        img.onload = () => {
            preloadedImages.current.add(imagePath);
        };
    };

    // If the opener passed an intent to open a specific presentation image, handle it once on mount
    useEffect(() => {
        const intent = (window as any).__inspectionOpenImageIntent as { group?: string; imagePath?: string } | undefined;
        if (intent) {
            try {
                if (intent.group) setSelectedGroupFilter(intent.group);
                const path = intent.imagePath || (presentationImages.find(p => p.group_name === intent.group)?.image_path);
                if (path) {
                    const imageNo = extractImageNoFromPath(path);
                    if (imageNo !== null) {
                        // Defer slightly to ensure modal content is mounted
                        setTimeout(() => onClickImage(path, imageNo, intent.group || getGroupLabel(path)), 0);
                    }
                }
            } finally {
                delete (window as any).__inspectionOpenImageIntent;
            }
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

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
                // Use centralized logic for defect analysis
                const hasKnots = res.data.some((defect: any) =>
                    defect.error_type === 2 || // 死に節 (dead knot)
                    defect.error_type === 3 || // 流れ節_死 (tight knot dead)
                    defect.error_type === 4 || // 流れ節_生 (tight knot live)
                    defect.error_type === 5    // 生き節 (live knot)
                );

                const hasDiscoloration = res.data.some((defect: any) => defect.error_type === 0);
                const hasHole = res.data.some((defect: any) => defect.error_type === 1);

                // Calculate maximum knot length using centralized logic
                let maxLength = 0;
                if (hasKnots) {
                    res.data.forEach((defect: any) => {
                        if (defect.error_type >= 2 && defect.error_type <= 5) {
                            const defectLength = defect.length || 0;
                            maxLength = Math.max(maxLength, defectLength);
                        }
                    });
                }

                setImageDefectStatus(prev => ({
                    ...prev,
                    [imageId]: {
                        hasDefects: true,
                        hasKnots,
                        length: maxLength,
                        hasLargeKnot: maxLength >= 10,
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

        // 1. 検査画像一覧APIの呼び出し - 新しいAPIを使用してt_inspection_imagesから取得
        fetchInspectionImages({ id: inspection.inspection_id })
            .then((res) => {
                if (res && res.result && res.data && Array.isArray(res.data)) {
                    // Convert InspectionImage[] to ImageItem[]
                    const fullData: ImageItem[] = res.data.map((img: InspectionImage) => ({
                        id: img.id,
                        path: img.image_path,
                        image_no: img.image_no,
                        image_type: img.image_type,
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
                console.error('Failed to load image list:', err);
                setImages([]);
            })
            .finally(() => {
                setIsLoading(false);
            });

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

                    // Use centralized logic for classification
                    const hasKnots = knot || dead_knot || live_knot || tight_knot;
                    const classification = determineInspectionResult(hasKnots, length, hole, discoloration);
                    setResultLabel(classification);

                    // Use centralized logic for defect type
                    const defectType = determineDefectType(hole, discoloration);
                    setDetailedStatus(defectType);

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
                // Loading state is now managed by the image loading API call
            });
    }, [inspection.inspection_id, inspection.file_path]); // Use inspection_id and file_path as dependencies

    // getImageUrl is now defined at the top level of the file

    return (
        <div className="fixed inset-0 bg-black bg-opacity-40 flex items-center justify-center z-50 p-4">
            <div className="bg-white modal-container max-w-[1600px] relative border-4 border-gray-800 flex flex-col">

                {/* Header with standardized styling */}
                <StandardHeader
                    title="木材検査システム　検査結果"
                    variant="modal"
                    showLogo={true}
                />

                {/* Body */}
                <div className='relative modal-body'>
                    {/* 時間・板No - Left aligned */}
                    <div className="text-left mb-4 text-responsive-xl font-bold">
                        <span className="mr-12">
                            {inspection.inspection_dt ? dateToString(inspection.inspection_dt) : '日時不明'}
                        </span>
                        <span>板No:{inspection.inspection_id || 'ID不明'}</span>
                    </div>

                    {/* 閉じるボタン - Positioned in top right of body */}
                    <div className="absolute top-4 right-4">
                        <button
                            onClick={onClose}
                            className="bg-cyan-800 text-white font-bold text-responsive-lg px-4 py-1 rounded border-2 border-white"
                        >
                            閉じる
                        </button>
                    </div>

                    {/* Status indicators - Left layout */}
                    <div className="flex justify-start gap-4 mb-4 flex-wrap">
                        <div className={`${getBackgroundColor(resultLabel)} text-white font-bold text-responsive-lg px-8 py-2 border-2 border-black`}>
                            {resultLabel}
                        </div>
                        {detailedStatus && (
                            <div className="bg-orange-500 text-white font-bold text-responsive-lg px-8 py-2 border-2 border-black">
                                {detailedStatus}
                            </div>
                        )}
                    </div>

                    {/* Presentation Images (A-E) - Centered and bigger */}
                    <div className="flex justify-center mb-8" style={{ margin: '20px 0 40px 0' }}>
                        <div className="presentation-grid">
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

                                const borderColor = (presentationImage && imageNo !== null) ? getBorderColor(imageNo) : 'border-gray-400';

                                return (
                                    <div key={`presentation-${label}-${presentationImage?.id || i}`} className="flex flex-col items-center">
                                        {/* Wood board visualization */}
                                        <div className={`presentation-image ${presentationImage && !failedPresentationImages.has(presentationImage.image_path) ? `border-4 ${borderColor}` : 'border-4 border-gray-400'} bg-white mb-2 relative overflow-hidden`}
                                            // Remove onClick from parent container - let ProgressiveImage handle it
                                            >
                                            {/* Show actual image instead of yellow section */}
                                            {presentationImage ? (
                                                <ProgressiveImage
                                                    src={presentationImage.image_path}
                                                    alt={`Group ${label}`}
                                                    inspectionId={inspection.inspection_id}
                                                    className="w-full h-full object-contain"
                                                    loading="eager"
                                                    // Only pass onClick if we have a valid presentation image that hasn't failed to load
                                                    onClick={presentationImage && imageNo !== null && !failedPresentationImages.has(presentationImage.image_path) ? () => {
                                                        setSelectedGroupFilter(label);
                                                        onClickImage(presentationImage.image_path, imageNo!, label);
                                                    } : undefined}
                                                    onImageError={() => {
                                                        // Track failed presentation images
                                                        setFailedPresentationImages(prev => new Set(prev).add(presentationImage.image_path));
                                                    }}
                                                />
                                            ) : (
                                                <NoImagePlaceholder 
                                                    className="w-full h-full"
                                                    alt="No Image Available"
                                                    // No onClick passed to NoImagePlaceholder for no-image state
                                                />
                                            )}
                                        </div>
                                        {/* Group Label Only */}
                                        <div className="text-responsive-lg font-bold">
                                            {label}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    {/* Bottom section with dropdown and image grid on same row - Moved down for larger presentation images */}
                    <div className="flex gap-4 mt-8">
                        {/* Group dropdown - on same row as grid */}
                        <div className="flex flex-col justify-start">
                            <select
                                value={selectedGroupFilter}
                                onChange={(e) => setSelectedGroupFilter(e.target.value)}
                                className="border-2 border-gray-400 rounded px-3 py-2 text-sm bg-white min-w-[100px]"
                                style={{ height: 'fit-content' }}
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
                        <div className="flex-1">
                            <div
                                ref={gridRef}
                                className="border-4 border-gray-800 bg-white overflow-x-hidden"
                                style={{
                                    height: 'clamp(140px, 20vh, 180px)',
                                    minHeight: '140px',
                                    maxHeight: '180px',
                                    padding: '12px 16px',
                                    overflowY: images.filter((img) => {
                                        if (selectedGroupFilter === 'all') return true;
                                        // Use database image_no for grouping
                                        const imageGroup = getGroupLabel(img.path, img.image_no);
                                        return imageGroup === selectedGroupFilter;
                                    }).length > 20 ? 'auto' : 'hidden'
                                }}
                            >
                                <div className="responsive-grid h-full">
                                    {images.length > 0 ? images
                                        .filter((img) => {
                                            if (selectedGroupFilter === 'all') return true;
                                            // Use database image_no for grouping
                                            const imageGroup = getGroupLabel(img.path, img.image_no);
                                            return imageGroup === selectedGroupFilter;
                                        })
                                        .map((img, i) => {
                                            // Use image_no from database if available, otherwise extract from path
                                            const extractedImageNo = img.image_no || extractImageNoFromPath(img.path);
                                            const imageGroup = getGroupLabel(img.path, img.image_no);

                                            // Determine if this image failed to load
                                            const isFailedImage = failedGridImages.has(img.path);
                                            // Use extracted image_no for API calls and border colors; force gray when failed
                                            const borderColor = extractedImageNo !== null && !isFailedImage ? getBorderColor(extractedImageNo) : 'border-gray-400';

                                            // Check if this image is a presentation image
                                            const isPresentation = isPresentationImage(img.path);
                                            
                                            return (
                                                <div
                                                    key={`grid-${img.id}-${imageDefectStatus[extractedImageNo || img.id] ? 'loaded' : 'loading'}`}
                                                    className={`grid-image ${isPresentation ? `presentation-thumbnail ${borderColor}` : `border-2 ${borderColor}`} bg-white relative overflow-hidden`}
                                                    data-image-path={img.path}
                                                    data-image-no={extractedImageNo || img.id}
                                                    // Remove onClick from parent container - let ProgressiveImage handle it
                                                    style={{ 
                                                        // Add visual indication for non-clickable state
                                                        opacity: extractedImageNo !== null && !isFailedImage ? 1 : 0.7
                                                    }}
                                                >
                                                    {/* Show actual thumbnail image instead of yellow section */}
                                                    <ProgressiveImage
                                                        src={img.path}
                                                        alt={`Image ${extractedImageNo || img.id}`}
                                                        inspectionId={inspection.inspection_id}
                                                        className="w-full h-full object-cover"
                                                        loading="lazy"
                                                        // Only pass onClick if we have a valid image number and image not failed to load
                                                        onClick={extractedImageNo !== null && !isFailedImage ? () => {
                                                            console.log(`✅ Grid image clicked: ExtractedImageNo=${extractedImageNo}, Path=${img.path}, Group=${imageGroup}`);
                                                            onClickImage(img.path, extractedImageNo, imageGroup);
                                                        } : undefined}
                                                        onImageError={() => {
                                                            setFailedGridImages(prev => new Set(prev).add(img.path));
                                                        }}
                                                    />
                                                    
                                                </div>
                                            );
                                        }) : (
                                        <div className="flex items-center justify-center w-full h-full text-gray-500">
                                            {isLoading ? (
                                                <div className="flex flex-col items-center justify-center">
                                                    <img
                                                        src="/image-loading.gif"
                                                        alt="画像を読み込み中..."
                                                        style={{
                                                            width: '40px',
                                                            height: '40px',
                                                            objectFit: 'contain'
                                                        }}
                                                    />
                                                    <span className="mt-2 text-sm">画像を読み込み中...</span>
                                                </div>
                                            ) : (
                                                <span>画像データがありません</span>
                                            )}
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
                        inspectionId={inspection.inspection_id}
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

