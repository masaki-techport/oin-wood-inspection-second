import React from 'react';
import PresentationImageCard from './PresentationImageCard';
import { PresentationImageCardProps } from '../../types';

/**
 * Color classification mapping based on parallel processing rules
 */
export type ColorClassification = 'red' | 'yellow' | 'green' | 'gray';

/**
 * Props for ColorBorderCard component
 */
export interface ColorBorderCardProps extends PresentationImageCardProps {
  colorClassification?: ColorClassification;
  borderWidth?: 'thin' | 'medium' | 'thick';
  showColorIndicator?: boolean;
}

/**
 * Color mapping for different classifications
 */
const COLOR_MAP: Record<ColorClassification, {
  border: string;
  background: string;
  indicator: string;
  description: string;
}> = {
  red: {
    border: 'border-red-500',
    background: 'bg-red-50',
    indicator: 'bg-red-500',
    description: '節あり (Large knots ≥10mm)'
  },
  yellow: {
    border: 'border-yellow-500',
    background: 'bg-yellow-50',
    indicator: 'bg-yellow-500',
    description: 'こぶし (Small knots <10mm)'
  },
  green: {
    border: 'border-green-500',
    background: 'bg-green-50',
    indicator: 'bg-green-500',
    description: '無欠点 (No knots)'
  },
  gray: {
    border: 'border-gray-400',
    background: 'bg-gray-50',
    indicator: 'bg-gray-500',
    description: 'Unknown/Default'
  }
};

/**
 * Border width mapping
 */
const BORDER_WIDTH_MAP: Record<NonNullable<ColorBorderCardProps['borderWidth']>, string> = {
  thin: 'border-2',
  medium: 'border-4',
  thick: 'border-6'
};

/**
 * ColorBorderCard - A wrapper component that adds color classification borders to PresentationImageCard
 * 
 * This component reuses the existing PresentationImageCard and adds:
 * - Color-coded borders based on defect classification
 * - Optional color indicator dot
 * - Consistent styling with the parallel processing rules
 */
const ColorBorderCard: React.FC<ColorBorderCardProps> = ({
  colorClassification = 'gray',
  borderWidth = 'medium',
  showColorIndicator = true,
  ...presentationCardProps
}) => {
  const colorConfig = COLOR_MAP[colorClassification];
  const borderClass = BORDER_WIDTH_MAP[borderWidth];

  return (
    <div 
      className={`
        ${colorConfig.border} 
        ${borderClass}
        ${colorConfig.background}
        rounded-lg shadow-md
        relative
        transition-all duration-200
        hover:shadow-lg
      `}
      title={colorConfig.description}
    >
      {/* Color indicator dot */}
      {showColorIndicator && (
        <div 
          className={`
            absolute top-2 right-2 
            w-4 h-4 rounded-full 
            ${colorConfig.indicator}
            border-2 border-white
            shadow-sm
            z-10
          `}
          title={colorConfig.description}
        />
      )}
      
      {/* Reuse existing PresentationImageCard */}
      <PresentationImageCard
        {...presentationCardProps}
      />
    </div>
  );
};

export default React.memo(ColorBorderCard);
