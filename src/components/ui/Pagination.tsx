import React from 'react';
import { cn } from '@/utils/cn';

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  totalItems: number;
  itemsPerPage: number;
  onPageChange: (page: number) => void;
  onItemsPerPageChange?: (itemsPerPage: number) => void;
  className?: string;
  showItemsPerPageSelector?: boolean;
  itemsPerPageOptions?: number[];
}

const Pagination: React.FC<PaginationProps> = ({
  currentPage,
  totalPages,
  totalItems,
  itemsPerPage,
  onPageChange,
  onItemsPerPageChange,
  className,
  showItemsPerPageSelector = true,
  itemsPerPageOptions = [10, 20, 50, 100]
}) => {
  // Calculate display range
  const startItem = (currentPage - 1) * itemsPerPage + 1;
  const endItem = Math.min(currentPage * itemsPerPage, totalItems);

  // Generate page numbers to display
  const getPageNumbers = () => {
    const pages: (number | string)[] = [];
    const maxVisiblePages = 5;

    if (totalPages <= maxVisiblePages) {
      // Show all pages if total is small
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i);
      }
    } else {
      // Always show first page
      pages.push(1);

      if (currentPage > 3) {
        pages.push('...');
      }

      // Show pages around current page
      const start = Math.max(2, currentPage - 1);
      const end = Math.min(totalPages - 1, currentPage + 1);

      for (let i = start; i <= end; i++) {
        if (i !== 1 && i !== totalPages) {
          pages.push(i);
        }
      }

      if (currentPage < totalPages - 2) {
        pages.push('...');
      }

      // Always show last page
      if (totalPages > 1) {
        pages.push(totalPages);
      }
    }

    return pages;
  };

  const pageNumbers = getPageNumbers();

  return (
    <div className={cn("flex flex-col sm:flex-row items-center justify-between gap-4 p-4 bg-gray-50 border-t", className)}>
      {/* Items per page selector */}
      {showItemsPerPageSelector && onItemsPerPageChange && (
        <div className="flex items-center gap-2 text-sm text-gray-600">
          <span>表示件数:</span>
          <select
            value={itemsPerPage}
            onChange={(e) => onItemsPerPageChange(Number(e.target.value))}
            className="px-2 py-1 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            {itemsPerPageOptions.map(option => (
              <option key={option} value={option}>
                {option}件
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Page info */}
      <div className="text-sm text-gray-600">
        {totalItems > 0 ? (
          <>
            {startItem}-{endItem}件 / 全{totalItems}件
          </>
        ) : (
          'データがありません'
        )}
      </div>

      {/* Pagination controls */}
      {totalPages > 1 && (
        <div className="flex items-center gap-1">
          {/* First page button */}
          <button
            onClick={() => onPageChange(1)}
            disabled={currentPage === 1}
            className={cn(
              "px-2 py-1 text-sm border rounded transition-colors",
              currentPage === 1
                ? "bg-gray-100 text-gray-400 border-gray-200 cursor-not-allowed"
                : "bg-white text-gray-700 border-gray-300 hover:bg-gray-50 hover:border-gray-400"
            )}
            aria-label="最初のページへ"
          >
            最初
          </button>

          {/* Previous page button */}
          <button
            onClick={() => onPageChange(currentPage - 1)}
            disabled={currentPage === 1}
            className={cn(
              "px-2 py-1 text-sm border rounded transition-colors",
              currentPage === 1
                ? "bg-gray-100 text-gray-400 border-gray-200 cursor-not-allowed"
                : "bg-white text-gray-700 border-gray-300 hover:bg-gray-50 hover:border-gray-400"
            )}
            aria-label="前のページへ"
          >
            ←
          </button>

          {/* Page numbers */}
          <div className="flex items-center gap-1">
            {pageNumbers.map((page, index) => (
              <React.Fragment key={index}>
                {page === '...' ? (
                  <span className="px-2 py-1 text-sm text-gray-500">...</span>
                ) : (
                  <button
                    onClick={() => onPageChange(page as number)}
                    className={cn(
                      "px-3 py-1 text-sm border rounded transition-colors min-w-[2.5rem]",
                      currentPage === page
                        ? "bg-blue-600 text-white border-blue-600"
                        : "bg-white text-gray-700 border-gray-300 hover:bg-gray-50 hover:border-gray-400"
                    )}
                    aria-label={`ページ ${page} へ`}
                    aria-current={currentPage === page ? 'page' : undefined}
                  >
                    {page}
                  </button>
                )}
              </React.Fragment>
            ))}
          </div>

          {/* Next page button */}
          <button
            onClick={() => onPageChange(currentPage + 1)}
            disabled={currentPage === totalPages}
            className={cn(
              "px-2 py-1 text-sm border rounded transition-colors",
              currentPage === totalPages
                ? "bg-gray-100 text-gray-400 border-gray-200 cursor-not-allowed"
                : "bg-white text-gray-700 border-gray-300 hover:bg-gray-50 hover:border-gray-400"
            )}
            aria-label="次のページへ"
          >
            →
          </button>

          {/* Last page button */}
          <button
            onClick={() => onPageChange(totalPages)}
            disabled={currentPage === totalPages}
            className={cn(
              "px-2 py-1 text-sm border rounded transition-colors",
              currentPage === totalPages
                ? "bg-gray-100 text-gray-400 border-gray-200 cursor-not-allowed"
                : "bg-white text-gray-700 border-gray-300 hover:bg-gray-50 hover:border-gray-400"
            )}
            aria-label="最後のページへ"
          >
            最後
          </button>
        </div>
      )}
    </div>
  );
};

export default Pagination;
