/**
 * Centralized color management for inspection results
 * Single source of truth for all color-related logic
 */

export interface ColorScheme {
  background: string;
  textBg: string;
  textColor: string;
  titleColor: string;
}

export interface InspectionResultColors {
  [key: string]: ColorScheme;
}

/**
 * Centralized color definitions for inspection results
 * This is the single source of truth for all color logic
 */
export const INSPECTION_RESULT_COLORS: InspectionResultColors = {
  '節あり': {
    background: 'bg-red-500',
    textBg: 'bg-white',
    textColor: 'text-black',
    titleColor: 'text-white'
  },
  'こぶし': {
    background: 'bg-yellow-500',
    textBg: 'bg-white',
    textColor: 'text-black',
    titleColor: 'text-black'
  },
  '無欠点': {
    background: 'bg-green-500',
    textBg: 'bg-white',
    textColor: 'text-black',
    titleColor: 'text-white'
  },
  '通信エラー': {
    background: 'bg-red-800',
    textBg: 'bg-white',
    textColor: 'text-white',
    titleColor: 'text-white'
  },
  'default': {
    background: 'bg-gray-300',
    textBg: 'bg-white',
    textColor: 'text-black',
    titleColor: 'text-white'
  }
};

/**
 * Get color scheme for a given inspection result
 * @param result - The inspection result string
 * @returns ColorScheme object with all color classes
 */
export const getColorScheme = (result: string | null | undefined): ColorScheme => {
  if (!result) {
    return INSPECTION_RESULT_COLORS.default;
  }
  
  return INSPECTION_RESULT_COLORS[result] || INSPECTION_RESULT_COLORS.default;
};

/**
 * Get background color class for a given inspection result
 * @param result - The inspection result string
 * @returns Background color class string
 */
export const getBackgroundColor = (result: string | null | undefined): string => {
  return getColorScheme(result).background;
};

/**
 * Get text color class for a given inspection result
 * @param result - The inspection result string
 * @returns Text color class string
 */
export const getTextColor = (result: string | null | undefined): string => {
  return getColorScheme(result).textColor;
};

/**
 * Get title color class for a given inspection result
 * @param result - The inspection result string
 * @returns Title color class string
 */
export const getTitleColor = (result: string | null | undefined): string => {
  return getColorScheme(result).titleColor;
};

/**
 * Get text background color class for a given inspection result
 * @param result - The inspection result string
 * @returns Text background color class string
 */
export const getTextBackgroundColor = (result: string | null | undefined): string => {
  return getColorScheme(result).textBg;
};

/**
 * Determine inspection result from defect data
 * Centralized logic for determining the primary inspection result
 * @param hasKnot - Whether any knots are detected
 * @param maxKnotLength - Maximum knot length found
 * @param hasHole - Whether holes are detected
 * @param hasDiscoloration - Whether discoloration is detected
 * @returns Primary inspection result string
 */
export const determineInspectionResult = (
  hasKnot: boolean,
  maxKnotLength: number = 0,
  hasHole: boolean = false,
  hasDiscoloration: boolean = false
): string => {
  if (hasKnot) {
    return maxKnotLength > 10 ? '節あり' : 'こぶし';
  }
  
  return '無欠点';
};

/**
 * Determine defect type from defect data
 * Centralized logic for determining the defect type display
 * @param hasHole - Whether holes are detected
 * @param hasDiscoloration - Whether discoloration is detected
 * @returns Defect type string
 */
export const determineDefectType = (
  hasHole: boolean = false,
  hasDiscoloration: boolean = false
): string => {
  if (hasHole && hasDiscoloration) {
    return '穴●変色発生';
  } else if (hasHole) {
    return '穴発生';
  } else if (hasDiscoloration) {
    return '変色発生';
  }
  
  return '';
};
