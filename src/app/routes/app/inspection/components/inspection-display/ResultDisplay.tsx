import React, { useEffect, useState, useRef, useCallback, useMemo } from 'react';
import { ResultDisplayProps, InspectionResultData } from '../../types';
import { useSensorData } from '../../hooks/useSensorData';
import { isDebugModeEnabledSync } from '@/utils/settingsReader';
import { getColorScheme, determineDefectType } from '../../utils/colorManager';
import { getInspectionId, getSensorStatus, getFetchInspectionResults } from '../../utils/stateManager';

/**
 * Component for displaying inspection results with detailed defect classifications
 * Shows both basic results and detailed inspection result data
 */
const ResultDisplay: React.FC<ResultDisplayProps> = ({ inspectionResult, defectType: propDefectType, titleOnly }) => {
  const {
    batchResult: sensorBatchResult,
    defectType: sensorDefectType,
    fetchInspectionResult,
    dbResultLoaded
  } = useSensorData();
  const [displayResult, setDisplayResult] = useState<string | null>(null);
  const [displayDefectType, setDisplayDefectType] = useState<string | null>(null);
  const [inspectionResults, setInspectionResults] = useState<InspectionResultData | null>(null);
  const currentInspectionIdRef = useRef<number | null>(null);

  // State for tracking loading and error states
  const [isLoadingResults, setIsLoadingResults] = useState(false);
  const [resultsError, setResultsError] = useState<string | null>(null);

  // Access inspection results from global sensor status
  useEffect(() => {
    const checkForInspectionResults = () => {
      const sensorStatus = (window as any).sensorStatus;
      
      if (sensorStatus) {
        // Update loading state
        setIsLoadingResults(sensorStatus.inspection_results_loading || false);
        
        // Update error state
        setResultsError(sensorStatus.inspection_results_error || null);
        
        // Update results
        if (sensorStatus.inspection_results) {
          setInspectionResults(sensorStatus.inspection_results);
          console.log('Updated inspection results from sensor status:', sensorStatus.inspection_results);
        } else if (!sensorStatus.inspection_results_loading) {
          // Only clear results if not currently loading
          setInspectionResults(null);
        }
      } else {
        // Clear all states if sensor status not available
        setInspectionResults(null);
        setIsLoadingResults(false);
        setResultsError(null);
      }
    };

    // Check immediately
    checkForInspectionResults();

    // Set up an interval to periodically check for updates - reduced frequency with error suppression
    const interval = setInterval(checkForInspectionResults, 2000); // Reduced from 1000ms to 2000ms

    return () => clearInterval(interval);
  }, []);

  // Fetch inspection results from database when needed
  useEffect(() => {
    // Check if inspectionId is available in state manager
    const inspectionId = getInspectionId();
    if (inspectionId && inspectionId !== currentInspectionIdRef.current) {
      currentInspectionIdRef.current = inspectionId;
      fetchInspectionResult(inspectionId);
      console.log(`Fetching results for inspection ID: ${inspectionId}`);
    }
  }, [fetchInspectionResult]);

  // Process inspection data and determine what to display
  useEffect(() => {
    // Use batch processing result from inspection_results table
    if (sensorBatchResult) {
      // Use batch processing
      setDisplayResult(sensorBatchResult);
      setDisplayDefectType(sensorDefectType);
      console.log(`Using batch processing result: "${sensorBatchResult}", defectType="${sensorDefectType}"`);
    } else {
      // No batch processing result, keep screen empty
      setDisplayResult(null);
      setDisplayDefectType(null);
    }
  }, [sensorBatchResult, sensorDefectType]);

  // Listen for clear events to reset display
  useEffect(() => {
    const onClear = () => {
      console.log('🧹 ResultDisplay: Clearing display due to inspection:clear event');
      setDisplayResult(null);
      setDisplayDefectType(null);
      setInspectionResults(null);
    };
    window.addEventListener('inspection:clear', onClear);
    return () => window.removeEventListener('inspection:clear', onClear);
  }, []);

  // Use centralized color manager - no local color definitions needed

  // Helper function to render defect classification details - memoized
  const renderDefectDetails = useCallback(() => {
    // Check if debug mode is disabled in settings.ini
    const debugModeEnabled = isDebugModeEnabledSync();
    
    // If debug mode is disabled, just return null (don't show debug panel)
    if (!debugModeEnabled) {
      return null;
    }
    
    // Show loading state
    if (isLoadingResults) {
      return (
        <div className="mt-4 bg-white bg-opacity-90 rounded-lg p-4 shadow-lg">
          <h3 className="text-lg font-bold text-black mb-3">詳細検査結果</h3>
          <div className="text-center">
            <div className="flex items-center justify-center space-x-2">
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600"></div>
              <span className="text-blue-600 font-medium">詳細結果を取得中...</span>
            </div>
          </div>
        </div>
      );
    }

    // Show error state
    if (resultsError) {
      const handleRetry = () => {
        // Try to get the current inspection ID and retry fetching results
        const currentInspectionId = getSensorStatus()?.inspection_data?.inspection_id || 
                                   currentInspectionIdRef.current ||
                                   getInspectionId();
        
        if (currentInspectionId && getFetchInspectionResults()) {
          console.log(`Manual retry for inspection ID: ${currentInspectionId}`);
          getFetchInspectionResults()!(currentInspectionId);
        }
      };

      return (
        <div className="mt-4 bg-white bg-opacity-90 rounded-lg p-4 shadow-lg">
          <h3 className="text-lg font-bold text-black mb-3">詳細検査結果</h3>
          <div className="text-center">
            <div className="bg-red-50 border border-red-200 rounded-lg p-3">
              <div className="flex items-center justify-center space-x-2 mb-2">
                <svg className="w-5 h-5 text-red-500" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                <span className="text-red-700 font-medium">エラー</span>
              </div>
              <p className="text-red-600 text-sm mb-3">{resultsError}</p>
              <button
                onClick={handleRetry}
                className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded text-sm font-medium transition-colors"
              >
                再試行
              </button>
            </div>
          </div>
        </div>
      );
    }

    // Show no data state when not loading and no error
    if (!inspectionResults) {
      return (
        <div className="mt-4 bg-white bg-opacity-90 rounded-lg p-4 shadow-lg">
          <h3 className="text-lg font-bold text-black mb-3">詳細検査結果</h3>
          <div className="text-center">
            <span className="bg-gray-100 text-gray-600 px-4 py-2 rounded">
              詳細結果データなし
            </span>
          </div>
        </div>
      );
    }

    try {
      // Safely extract defect data with fallbacks
    const defectTypes = [
      { key: 'discoloration', label: '変色', value: Boolean(inspectionResults.discoloration) },
      { key: 'hole', label: '穴', value: Boolean(inspectionResults.hole) },
      { key: 'knot', label: '節', value: Boolean(inspectionResults.knot) },
      { key: 'dead_knot', label: '死節', value: Boolean(inspectionResults.dead_knot) },
      { key: 'live_knot', label: '生節', value: Boolean(inspectionResults.live_knot) },
      { key: 'tight_knot', label: '堅節', value: Boolean(inspectionResults.tight_knot) }
    ];

    const detectedDefects = defectTypes.filter(defect => defect.value);
    const hasDefects = detectedDefects.length > 0;

    return (
      <div className="mt-4 bg-white bg-opacity-90 rounded-lg p-4 shadow-lg">
        <h3 className="text-lg font-bold text-black mb-3">詳細検査結果</h3>

        {hasDefects ? (
          <div className="space-y-2">
            <div className="grid grid-cols-2 gap-4">
              {defectTypes.map(defect => (
                <div key={defect.key} className="flex items-center justify-between">
                  <span className="text-black font-medium">{defect.label}:</span>
                  <span className={`px-2 py-1 rounded text-sm font-bold ${defect.value
                    ? 'bg-red-100 text-red-800'
                    : 'bg-green-100 text-green-800'
                    }`}>
                    {defect.value ? '検出' : '正常'}
                  </span>
                </div>
              ))}
            </div>

            {inspectionResults.length !== null && inspectionResults.length !== undefined && (
              <div className="mt-3 pt-3 border-t border-gray-300">
                <div className="flex items-center justify-between">
                  <span className="text-black font-medium">長さ測定:</span>
                  <span className="bg-blue-100 text-blue-800 px-2 py-1 rounded text-sm font-bold">
                    {typeof inspectionResults.length === 'number' 
                      ? inspectionResults.length.toFixed(1) 
                      : inspectionResults.length} mm
                  </span>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="text-center">
            <span className="bg-green-100 text-green-800 px-4 py-2 rounded font-bold">
              欠陥なし - 検査合格
            </span>
          </div>
        )}
      </div>
    );
  } catch (error) {
      console.error('Error rendering defect details:', error);
      return (
        <div className="mt-4 bg-white bg-opacity-90 rounded-lg p-4 shadow-lg">
          <h3 className="text-lg font-bold text-black mb-3">詳細検査結果</h3>
          <div className="text-center">
            <div className="bg-red-50 border border-red-200 rounded-lg p-3">
              <div className="flex items-center justify-center space-x-2 mb-2">
                <svg className="w-5 h-5 text-red-500" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                <span className="text-red-700 font-medium">表示エラー</span>
              </div>
              <p className="text-red-600 text-sm">詳細結果の表示中にエラーが発生しました</p>
            </div>
          </div>
        </div>
      );
    }
  }, [isLoadingResults, resultsError, inspectionResults]);

  // Suppress any cached result while processing temp sections/new circle
  try {
    const ss: any = (window as any).sensorStatus;
    const createdInspectionId = (window as any).inspectionId as number | undefined;
    const images = (window as any).presentationImages as any[] | undefined;
    const isProcessing = Boolean(
      ss?.capture?.status === '処理中' ||
      ss?.sensors?.clear_requested === true ||
      ss?.capture?.processing_active === true ||
      ss?.processing_active === true
    );
    // Additionally, hide if the currently displayed presentation images are not for
    // the current inspection id (prevents mismatch hydration)
    const mismatchedImages = Array.isArray(images) && images.length > 0 &&
      createdInspectionId && images.some(img => img?.inspection_id !== createdInspectionId);
    if (mismatchedImages) {
      return null;
    }
    if (isProcessing) {
      return null;
    }
  } catch (_) { /* noop */ }

  // Don't render anything if we don't have a result to display
  if (!displayResult) return null;

  try {
    // Get the current status colors using centralized color manager
    const statusColors = getColorScheme(displayResult);

    return (
      <>
        {/* Title showing current defect status - positioned to not block content */}
        <div className="absolute top-6 left-1/2 transform -translate-x-1/2 flex items-center gap-6" style={{ zIndex: 10 }}>
          {/* Main result display */}
          <div className="text-4xl font-bold px-12 py-6 rounded-lg shadow-lg flex items-center justify-center bg-white text-black">
            {displayResult}
          </div>

          {/* Additional defect type information */}
          {displayDefectType && (
            <div className="text-3xl font-bold bg-orange-500 text-black px-8 py-6 rounded-lg shadow-lg flex items-center justify-center">
              {displayDefectType}
            </div>
          )}
        </div>

        {/* Background and details are omitted in titleOnly mode */}
        {!titleOnly && (
          <>
            <div className={`absolute inset-0 ${statusColors.background}`} style={{ zIndex: -1 }} />
            <div className="absolute bottom-6 left-1/2 transform -translate-x-1/2" style={{ zIndex: 5 }}>
              {renderDefectDetails()}
            </div>
          </>
        )}
      </>
    );
  } catch (error) {
    console.error('Error rendering ResultDisplay component:', error);
    return (
      <div className="absolute inset-0 bg-red-500 flex flex-col items-center justify-center">
        <div className="bg-white rounded-lg p-6 shadow-lg text-center">
          <h3 className="text-lg font-bold text-red-600 mb-2">表示エラー</h3>
          <p className="text-gray-600">検査結果の表示中にエラーが発生しました</p>
        </div>
      </div>
    );
  }
};

export default React.memo(ResultDisplay);