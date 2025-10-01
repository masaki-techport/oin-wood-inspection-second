import React, { useMemo, useRef, useEffect } from 'react';
import { sortSectionsAlphabetically } from '../../../../../../features/temp-sections/utils/ordering';
import { TempSection } from '../../../../../../types/temp-sections';
import ColorBorderCard, { ColorClassification } from './ColorBorderCard';

interface ScrollingTempSectionsProps {
  sections: TempSection[];
  isLoading: boolean;
}

const VISIBLE_SECTIONS = 5; // Always show 5 sections at a time

/**
 * Component for displaying temp sections with horizontal scrolling
 * Shows sections in alphabetical order (A, B, C, D...) with scrollbar navigation
 */
const ScrollingTempSections: React.FC<ScrollingTempSectionsProps> = ({ 
  sections, 
  isLoading 
}) => {
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // Sort sections alphabetically by label (A, B, C, D...)
  const sortedSections = useMemo(() => sortSectionsAlphabetically(sections), [sections]);

  // Auto-scroll to show the most recent sections (rightmost) when new sections are added
  useEffect(() => {
    if (scrollContainerRef.current && sortedSections.length > VISIBLE_SECTIONS) {
      // Scroll to the right to show the most recent sections
      const container = scrollContainerRef.current;
      container.scrollLeft = container.scrollWidth - container.clientWidth;
    }
  }, [sortedSections.length]);

  // Map summary color to classification
  const mapSummaryColorToClassification = (summaryColor: string): ColorClassification => {
    switch (summaryColor) {
      case 'red':
        return 'red';
      case 'yellow':
        return 'yellow';
      case 'green':
        return 'green';
      case 'gray':
      default:
        return 'gray';
    }
  };

  if (isLoading) {
    return (
      <div className="text-center py-8">
        <div className="text-gray-500">
          処理中 - リアルタイム分析を待機中...
        </div>
      </div>
    );
  }

  if (sortedSections.length === 0) {
    return (
      <div className="text-center py-8">
        <div className="text-gray-500">
          処理中 - リアルタイム分析を待機中...
        </div>
      </div>
    );
  }

  return (
    <div className="relative">
      {/* Section Counter */}
      {sortedSections.length > 0 && (
        <div className="flex items-center justify-between mb-4">
          <div className="text-sm text-gray-600">
            セクション {sortedSections.length}件
            {sortedSections.length > VISIBLE_SECTIONS && (
              <span className="ml-2 text-blue-600">
                (スクロールして全て表示)
              </span>
            )}
          </div>
        </div>
      )}

      {/* Sections Display with Scrollbar */}
      <div 
        ref={scrollContainerRef}
        className="overflow-x-auto pb-2 scrollbar-thin scrollbar-thumb-gray-400 scrollbar-track-gray-200"
        style={{
          scrollbarWidth: 'thin',
          scrollbarColor: '#9CA3AF #E5E7EB'
        }}
      >
        <div className="flex space-x-4 min-w-max">
          {sortedSections.map((section: TempSection) => (
            <ColorBorderCard
              key={section.id}
              groupName={section.label}
              imagePath={section.representativeImage || null}
              inspectionId={0} // Use 0 for temp sections (no inspection ID yet)
              colorClassification={mapSummaryColorToClassification(section.summaryColor)}
              borderWidth="medium"
              showColorIndicator={true}
              onImageTest={() => {}} // No-op for temp sections
              onOpenDetails={() => {}} // No-op for temp sections
            />
          ))}
        </div>
      </div>

      {/* Scroll hint for many sections */}
      {sortedSections.length > VISIBLE_SECTIONS && (
        <div className="text-center mt-2">
          <div className="text-xs text-gray-500">
            ← スクロールして全てのセクションを表示 → (最新のセクションを表示)
          </div>
        </div>
      )}
    </div>
  );
};

export default React.memo(ScrollingTempSections);
