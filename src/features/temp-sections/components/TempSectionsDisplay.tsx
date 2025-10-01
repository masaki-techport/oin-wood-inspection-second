/**
 * Display component for temporary sections
 */

import React from 'react';
import { TempSection, SaveSectionGroup } from '../../../types/temp-sections';

interface TempSectionsDisplayProps {
  sections: TempSection[];
  saveSections: SaveSectionGroup[] | null;
  isSaveStage: boolean;
  isLoading: boolean;
  error: string | null;
  isConnected: boolean;
  onRefresh?: () => void;
  onReset?: () => void;
  onClearSaveStage?: () => void;
}

const getColorClass = (color: string) => {
  switch (color) {
    case 'red': return 'bg-red-500';
    case 'yellow': return 'bg-yellow-500';
    case 'green': return 'bg-green-500';
    default: return 'bg-gray-500';
  }
};

const TempSectionCard: React.FC<{ section: TempSection }> = ({ section }) => (
  <div className="bg-white rounded-lg shadow-md p-4 border border-gray-200 min-w-[200px]">
    <div className="flex items-center justify-between mb-2">
      <h3 className="text-lg font-semibold text-gray-800">
        Section {section.label}
      </h3>
      <div className={`w-4 h-4 rounded-full ${getColorClass(section.summaryColor)}`} 
           title={`Status: ${section.summaryColor}`} />
    </div>
    
    <div className="text-sm text-gray-600 space-y-1">
      <p>Images: {section.imageIndices.length}</p>
      <p>Status: {section.status}</p>
      {section.completedAt && (
        <p>Completed: {new Date(section.completedAt * 1000).toLocaleTimeString()}</p>
      )}
    </div>
    
    {section.representativeImage && (
      <div className="mt-3">
        <img 
          src={section.representativeImage} 
          alt={`Representative for section ${section.label}`}
          className="w-full h-20 object-cover rounded"
        />
      </div>
    )}
  </div>
);

const SaveSectionCard: React.FC<{ group: SaveSectionGroup }> = ({ group }) => (
  <div className="bg-blue-50 rounded-lg shadow-md p-4 border border-blue-200 min-w-[200px]">
    <div className="flex items-center justify-between mb-2">
      <h3 className="text-lg font-semibold text-blue-800">
        Group {group.label}
      </h3>
      <div className="w-4 h-4 rounded-full bg-blue-500" />
    </div>
    
    <div className="text-sm text-blue-600 space-y-1">
      <p>Images: {group.count}</p>
      <p>Range: {group.imageNumbers[0]}-{group.imageNumbers[group.imageNumbers.length - 1]}</p>
    </div>
  </div>
);

export const TempSectionsDisplay: React.FC<TempSectionsDisplayProps> = ({
  sections,
  saveSections,
  isSaveStage,
  isLoading,
  error,
  isConnected,
  onRefresh,
  onReset,
  onClearSaveStage
}) => {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-2"></div>
          <p className="text-gray-600">Loading temp sections...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-red-800 font-semibold">Error</h3>
            <p className="text-red-600 text-sm">{error}</p>
          </div>
          {onRefresh && (
            <button
              onClick={onRefresh}
              className="px-3 py-1 bg-red-100 text-red-700 rounded hover:bg-red-200"
            >
              Retry
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <h2 className="text-xl font-bold text-gray-800">
            {isSaveStage ? 'Save Stage (Fixed Groups)' : 'Temporary Sections'}
          </h2>
          <div className="flex items-center space-x-2">
            <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
            <span className="text-sm text-gray-600">
              {isConnected ? 'Live' : 'Offline'}
            </span>
          </div>
        </div>
        
        <div className="flex space-x-2">
          {onRefresh && (
            <button
              onClick={onRefresh}
              className="px-3 py-1 bg-blue-100 text-blue-700 rounded hover:bg-blue-200"
            >
              Refresh
            </button>
          )}
          {onReset && (
            <button
              onClick={onReset}
              className="px-3 py-1 bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
            >
              Reset
            </button>
          )}
          {isSaveStage && onClearSaveStage && (
            <button
              onClick={onClearSaveStage}
              className="px-3 py-1 bg-yellow-100 text-yellow-700 rounded hover:bg-yellow-200"
            >
              Clear Save Stage
            </button>
          )}
        </div>
      </div>

      {/* Content */}
      {isSaveStage ? (
        // Save stage view - fixed 5 groups
        <div>
          <p className="text-gray-600 mb-4">
            Images have been saved and split into fixed groups after PASS_L_TO_R signal.
          </p>
          <div className="flex space-x-4 overflow-x-auto pb-2">
            {saveSections?.map((group) => (
              <SaveSectionCard key={group.label} group={group} />
            ))}
          </div>
        </div>
      ) : (
        // Temp stage view - growing sections
        <div>
          <p className="text-gray-600 mb-4">
            Real-time temporary sections growing from A to Z, then AA, AB, etc.
          </p>
          {sections.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              No sections available yet. Start recording to see temp sections.
            </div>
          ) : (
            <div className="flex space-x-4 overflow-x-auto pb-2">
              {sections.map((section) => (
                <TempSectionCard key={section.id} section={section} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
