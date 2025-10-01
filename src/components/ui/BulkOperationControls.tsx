import React, { useEffect, useRef } from 'react';

interface BulkOperationControlsProps {
  selectedCount: number;
  totalCount: number;
  onSelectAll: () => void;
  onDeselectAll: () => void;
  onDelete: () => void;
  deleteError: string | null;
  isDeleting: boolean;
  isLoading?: boolean;
}

const BulkOperationControls: React.FC<BulkOperationControlsProps> = ({
  selectedCount,
  totalCount,
  onSelectAll,
  onDeselectAll,
  onDelete,
  deleteError,
  isDeleting,
  isLoading = false,
}) => {
  // Ref for accessibility announcements
  const announcementRef = useRef<HTMLDivElement>(null);
  // Determine if all items are selected
  const isAllSelected = selectedCount === totalCount && totalCount > 0;
  
  // Determine if select all button should be disabled
  const isSelectAllDisabled = totalCount <= 0 || isDeleting || isLoading;
  
  // Determine if delete button should be visible
  const isDeleteVisible = selectedCount > 0;
  
  // Determine if any operation is in progress
  const isOperationInProgress = isDeleting || isLoading;

  const handleSelectToggle = () => {
    if (isOperationInProgress) return;
    
    if (isAllSelected) {
      onDeselectAll();
    } else {
      onSelectAll();
    }
  };

  const handleDelete = () => {
    if (selectedCount === 0 || isOperationInProgress) {
      // This should not happen due to conditional visibility, but adding as safety
      return;
    }
    onDelete();
  };

  // Accessibility announcements for state changes
  useEffect(() => {
    if (announcementRef.current) {
      let announcement = '';
      
      if (isDeleting) {
        announcement = `削除処理中です。${selectedCount}件の項目を削除しています。`;
      } else if (isLoading) {
        announcement = '読み込み中です。';
      } else if (selectedCount > 0) {
        announcement = `${selectedCount}件の項目が選択されています。`;
      }
      
      if (announcement) {
        announcementRef.current.textContent = announcement;
      }
    }
  }, [selectedCount, isDeleting, isLoading]);

  return (
    <div className="mb-4 space-y-2">
      {/* Control buttons row */}
      <div className="flex gap-4 items-center">
        {/* Select All/Deselect All Button */}
        <button
          onClick={handleSelectToggle}
          disabled={isSelectAllDisabled}
          className={`px-4 py-2 rounded shadow text-white font-medium transition-colors duration-200 ${
            isSelectAllDisabled
              ? 'bg-gray-400 cursor-not-allowed'
              : 'bg-[#155f83] hover:bg-[#0f4a66] active:bg-[#0d3f57] focus:ring-2 focus:ring-blue-500 focus:ring-offset-2'
          }`}
          aria-describedby={totalCount > 0 ? 'selection-count' : undefined}
        >
          {isOperationInProgress ? (
            <span className="flex items-center">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2" role="status" aria-hidden="true"></div>
              {isAllSelected ? '解除中...' : '選択中...'}
            </span>
          ) : (
            isAllSelected ? '全て解除' : '全て選択'
          )}
        </button>

        {/* Delete Button - conditionally visible */}
        {isDeleteVisible && (
          <button
            onClick={handleDelete}
            disabled={isOperationInProgress}
            className={`px-4 py-2 rounded shadow text-white font-medium transition-colors duration-200 ${
              isOperationInProgress
                ? 'bg-gray-400 cursor-not-allowed'
                : 'bg-red-600 hover:bg-red-700 active:bg-red-800 focus:ring-2 focus:ring-red-500 focus:ring-offset-2'
            }`}
            aria-describedby="selection-count"
          >
            {isDeleting ? (
              <span className="flex items-center">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2" role="status" aria-hidden="true"></div>
                削除中...
              </span>
            ) : (
              '削除'
            )}
          </button>
        )}

        {/* Loading indicator for general operations */}
        {isLoading && !isDeleting && (
          <div className="flex items-center text-gray-600">
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-gray-600 mr-2" role="status" aria-label="読み込み中"></div>
            <span className="text-sm">読み込み中...</span>
          </div>
        )}

        {/* Selection count indicator with enhanced feedback */}
        {totalCount > 0 && (
          <span 
            id="selection-count" 
            className={`text-sm transition-colors duration-200 ${
              selectedCount > 0 ? 'text-blue-600 font-medium' : 'text-gray-600'
            }`}
            aria-live="polite"
          >
            {selectedCount} / {totalCount} 件選択
            {selectedCount === totalCount && totalCount > 0 && (
              <span className="ml-1 text-green-600">(全選択)</span>
            )}
          </span>
        )}
      </div>

      {/* Error message display with enhanced accessibility */}
      {deleteError && (
        <div 
          className="text-red-600 text-sm font-medium bg-red-50 border border-red-200 rounded p-2" 
          role="alert"
          aria-live="assertive"
        >
          <span className="inline-block mr-2" aria-hidden="true">⚠️</span>
          {deleteError}
        </div>
      )}

      {/* Screen reader announcements */}
      <div 
        ref={announcementRef}
        className="sr-only" 
        aria-live="polite" 
        aria-atomic="true"
      ></div>
    </div>
  );
};

export default BulkOperationControls;