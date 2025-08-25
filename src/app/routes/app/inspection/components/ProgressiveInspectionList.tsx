import React, { useState, useEffect, useRef } from 'react';

interface Inspection {
  inspection_id: number;
  inspection_dt: string | null;
  results: string;
  confidence_above_threshold: boolean;
  ai_threshold: number;
  presentation_ready: boolean;
  inspection_results?: any;
  inspection_details?: any[];
}

interface ProgressiveInspectionListProps {
  limit?: number;
  dateFrom?: string;
  dateTo?: string;
  onInspectionClick?: (inspection: Inspection) => void;
  className?: string;
}

export const ProgressiveInspectionList: React.FC<ProgressiveInspectionListProps> = ({
  limit,
  dateFrom,
  dateTo,
  onInspectionClick,
  className = ''
}) => {
  const [inspections, setInspections] = useState<Inspection[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isComplete, setIsComplete] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  const loadInspections = async () => {
    // Cancel any existing request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    abortControllerRef.current = new AbortController();
    setIsLoading(true);
    setError(null);
    setInspections([]);
    setIsComplete(false);

    try {
      // Build query parameters
      const params = new URLSearchParams();
      if (limit) params.append('limit', limit.toString());
      if (dateFrom) params.append('date_from', dateFrom);
      if (dateTo) params.append('date_to', dateTo);

      const response = await fetch(
        `http://localhost:8000/api/stream/inspections?${params.toString()}`,
        { signal: abortControllerRef.current.signal }
      );

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('No response body reader available');
      }

      const decoder = new TextDecoder();
      let buffer = '';
      let jsonStarted = false;
      let arrayStarted = false;

      while (true) {
        const { done, value } = await reader.read();
        
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Process the buffer
        if (!jsonStarted && buffer.includes('{"result": true, "data": [')) {
          jsonStarted = true;
          arrayStarted = true;
          buffer = buffer.substring(buffer.indexOf('[') + 1);
        }

        if (arrayStarted) {
          // Try to extract complete JSON objects
          let braceCount = 0;
          let start = 0;
          let inString = false;
          let escaped = false;

          for (let i = 0; i < buffer.length; i++) {
            const char = buffer[i];

            if (escaped) {
              escaped = false;
              continue;
            }

            if (char === '\\') {
              escaped = true;
              continue;
            }

            if (char === '"') {
              inString = !inString;
              continue;
            }

            if (!inString) {
              if (char === '{') {
                braceCount++;
              } else if (char === '}') {
                braceCount--;
                
                if (braceCount === 0) {
                  // Found complete JSON object
                  const jsonStr = buffer.substring(start, i + 1);
                  
                  try {
                    const inspection = JSON.parse(jsonStr);
                    setInspections(prev => [...prev, inspection]);
                  } catch (parseError) {
                    console.warn('Failed to parse inspection JSON:', jsonStr);
                  }

                  // Move to next object
                  start = i + 1;
                  // Skip comma if present
                  while (start < buffer.length && (buffer[start] === ',' || buffer[start] === ' ')) {
                    start++;
                  }
                }
              }
            }
          }

          // Keep unprocessed part of buffer
          buffer = buffer.substring(start);
        }

        // Check for end of array
        if (buffer.includes(']}')) {
          setIsComplete(true);
          break;
        }
      }

    } catch (err: any) {
      if (err.name !== 'AbortError') {
        setError(err.message || 'Failed to load inspections');
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadInspections();

    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [limit, dateFrom, dateTo]);

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'N/A';
    try {
      return new Date(dateStr).toLocaleString();
    } catch {
      return dateStr;
    }
  };

  const getResultColor = (result: string) => {
    switch (result.toLowerCase()) {
      case '無欠点':
      case 'no defect':
        return 'text-green-600 bg-green-50';
      case '節あり':
      case 'defect found':
        return 'text-red-600 bg-red-50';
      default:
        return 'text-gray-600 bg-gray-50';
    }
  };

  return (
    <div className={`progressive-inspection-list ${className}`}>
      {/* Header */}
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-medium text-gray-900">
          Inspection Results
          {inspections.length > 0 && (
            <span className="ml-2 text-sm text-gray-500">
              ({inspections.length} loaded{isComplete ? '' : ', loading...'})
            </span>
          )}
        </h3>
        
        <button
          onClick={loadInspections}
          disabled={isLoading}
          className="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {isLoading ? 'Loading...' : 'Refresh'}
        </button>
      </div>

      {/* Loading indicator */}
      {isLoading && inspections.length === 0 && (
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600 mr-2"></div>
          <span className="text-gray-600">Loading inspections...</span>
        </div>
      )}

      {/* Error message */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4 mb-4">
          <div className="flex">
            <div className="text-red-600">
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-800">Error loading inspections</h3>
              <p className="text-sm text-red-700 mt-1">{error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Inspection list */}
      {inspections.length > 0 && (
        <div className="space-y-2">
          {inspections.map((inspection) => (
            <div
              key={inspection.inspection_id}
              onClick={() => onInspectionClick?.(inspection)}
              className={`border rounded-lg p-4 transition-colors ${
                onInspectionClick ? 'cursor-pointer hover:bg-gray-50' : ''
              }`}
            >
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  <div className="flex items-center space-x-3">
                    <span className="font-medium text-gray-900">
                      ID: {inspection.inspection_id}
                    </span>
                    
                    <span className={`px-2 py-1 text-xs rounded-full ${getResultColor(inspection.results)}`}>
                      {inspection.results}
                    </span>
                    
                    {inspection.confidence_above_threshold && (
                      <span className="px-2 py-1 text-xs bg-yellow-100 text-yellow-800 rounded-full">
                        High Confidence
                      </span>
                    )}
                    
                    {inspection.presentation_ready && (
                      <span className="px-2 py-1 text-xs bg-blue-100 text-blue-800 rounded-full">
                        Presentation Ready
                      </span>
                    )}
                  </div>
                  
                  <div className="mt-2 text-sm text-gray-600">
                    <div>Date: {formatDate(inspection.inspection_dt)}</div>
                    <div>AI Threshold: {inspection.ai_threshold}%</div>
                    {inspection.inspection_details && (
                      <div>Details: {inspection.inspection_details.length} items</div>
                    )}
                  </div>
                </div>
                
                {onInspectionClick && (
                  <div className="text-gray-400">
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
                    </svg>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Loading more indicator */}
      {isLoading && inspections.length > 0 && (
        <div className="flex items-center justify-center py-4">
          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600 mr-2"></div>
          <span className="text-sm text-gray-600">Loading more...</span>
        </div>
      )}

      {/* Complete indicator */}
      {isComplete && inspections.length > 0 && (
        <div className="text-center py-4 text-sm text-gray-500">
          All inspections loaded ({inspections.length} total)
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !error && inspections.length === 0 && (
        <div className="text-center py-8 text-gray-500">
          <svg className="w-12 h-12 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
          </svg>
          <p>No inspections found</p>
        </div>
      )}
    </div>
  );
};