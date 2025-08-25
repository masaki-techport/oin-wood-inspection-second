import { InspectionDetailsImg } from '@/types/api';

// Type definition for image defect status (extracted from InspectionDetailsModal)
export type ImageDefectStatus = {
    hasDefects: boolean;
    hasKnots: boolean;
    length: number;
    hasLargeKnot?: boolean;
    hasDiscoloration: boolean;
    hasHole: boolean;
};

// Defect status type for background colors
export type DefectStatus = 'none' | 'minor' | 'major';

// Error type colors mapping (extracted from InspectionDetailsModal lines ~236-243)
export const errorTypeColors: { [key: number]: string } = {
    0: 'rgba(128, 0, 128, 0.7)',   // 変色 (discoloration) - Purple
    1: 'rgba(255, 0, 0, 0.7)',     // 穴 (hole) - Red  
    2: 'rgba(255, 165, 0, 0.7)',   // 死に節 (dead knot) - Orange
    3: 'rgba(255, 255, 0, 0.7)',   // 流れ節_死 (tight knot dead) - Yellow
    4: 'rgba(0, 255, 0, 0.7)',     // 流れ節_生 (tight knot live) - Green
    5: 'rgba(0, 0, 255, 0.7)',     // 生き節 (live knot) - Blue
};

// Background color configuration that matches existing border colors
// Colors chosen for optimal contrast and accessibility
export const defectStatusColors = {
    none: {
        background: 'bg-green-50',      // Light green background for 無欠点 (no defects)
        border: 'border-green-300',     // Slightly darker border for better contrast
        text: 'text-green-900',         // Darker text for better readability
        accent: 'text-green-700'
    },
    minor: {
        background: 'bg-yellow-50',     // Light yellow background for こぶし (minor defects)
        border: 'border-yellow-300',    // Slightly darker border for better contrast
        text: 'text-yellow-900',        // Darker text for better readability
        accent: 'text-yellow-700'
    },
    major: {
        background: 'bg-red-50',        // Light red background for 節あり (major defects)
        border: 'border-red-300',       // Slightly darker border for better contrast
        text: 'text-red-900',           // Darker text for better readability
        accent: 'text-red-700'
    }
};

// Defect label colors for external labels (matching errorTypeColors with Tailwind classes)
export const defectLabelColors = {
    0: { bg: 'bg-purple-100', border: 'border-purple-500', text: 'text-purple-800' }, // 変色
    1: { bg: 'bg-red-100', border: 'border-red-500', text: 'text-red-800' },         // 穴
    2: { bg: 'bg-orange-100', border: 'border-orange-500', text: 'text-orange-800' }, // 死に節
    3: { bg: 'bg-yellow-100', border: 'border-yellow-500', text: 'text-yellow-800' }, // 流れ節_死
    4: { bg: 'bg-green-100', border: 'border-green-500', text: 'text-green-800' },   // 流れ節_生
    5: { bg: 'bg-blue-100', border: 'border-blue-500', text: 'text-blue-800' },     // 生き節
};

/**
 * Analyzes defect data to determine defect status information
 * Extracted from loadImageDefectData function in InspectionDetailsModal
 */
export const analyzeDefectData = (defectData: InspectionDetailsImg[]): ImageDefectStatus => {
    if (!defectData || defectData.length === 0) {
        return {
            hasDefects: false,
            hasKnots: false,
            length: 0,
            hasLargeKnot: false,
            hasDiscoloration: false,
            hasHole: false
        };
    }

    // Analyze the defect data to determine knot information
    const hasKnots = defectData.some((defect: any) =>
        defect.error_type === 2 || // 死に節 (dead knot)
        defect.error_type === 3 || // 流れ節_死 (tight knot dead)
        defect.error_type === 4 || // 流れ節_生 (tight knot live)
        defect.error_type === 5    // 生き節 (live knot)
    );

    const hasDiscoloration = defectData.some((defect: any) => defect.error_type === 0);
    const hasHole = defectData.some((defect: any) => defect.error_type === 1);

    // Calculate length based on knot defects (if any)
    // Check if ANY knot defect has length >= 10 (for 節あり vs こぶし classification)
    let maxLength = 0;
    let hasLargeKnot = false;
    if (hasKnots) {
        defectData.forEach((defect: any) => {
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

    return {
        hasDefects: true,
        hasKnots,
        length: maxLength,
        hasLargeKnot,
        hasDiscoloration,
        hasHole
    };
};

/**
 * Gets border color based on defect status
 * Extracted from getBorderColor function in InspectionDetailsModal
 */
export const getBorderColorFromDefectStatus = (defectStatus: ImageDefectStatus): string => {
    if (!defectStatus.hasDefects) {
        return 'border-green-500'; // 無欠点 (no defects)
    }

    // Check if image has knots and determine classification
    if (defectStatus.hasKnots) {
        // If ANY knot defect has length >= 10, it's 節あり (red)
        // If ALL knot defects have length < 10, it's こぶし (yellow)
        return defectStatus.hasLargeKnot ? 'border-red-500' : 'border-yellow-500';
    }

    // If has defects but no knots (discoloration/hole only), default to green
    return 'border-green-500';
};

/**
 * Determines defect status for background color mapping
 * Maps border colors to background status categories
 */
export const determineDefectStatus = (defectData: InspectionDetailsImg | InspectionDetailsImg[] | null): DefectStatus => {
    if (!defectData) return 'none';
    
    const defects = Array.isArray(defectData) ? defectData : [defectData];
    const defectStatus = analyzeDefectData(defects);
    
    if (!defectStatus.hasDefects) {
        return 'none'; // 無欠点 (no defects) - green
    }
    
    // Check if image has knots and determine classification
    if (defectStatus.hasKnots) {
        // If ANY knot defect has length >= 10, it's major (節あり - red)
        // If ALL knot defects have length < 10, it's minor (こぶし - yellow)
        return defectStatus.hasLargeKnot ? 'major' : 'minor';
    }
    
    // If has defects but no knots (discoloration/hole only), default to none
    return 'none';
};