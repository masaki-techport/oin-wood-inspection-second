import React, { useState, useRef, useEffect } from 'react';
import { useProgressiveAnalysis } from '../hooks/useStreamingData';
import { DetectionResult, ProgressiveAnalysisData } from '../types/streaming';

interface AnalysisResult {
  file_index: number;
  filename: string;
  status: 'processing' | 'completed' | 'error';
  progress?: number;
  result?: {
    detected_defects: string[];
    confidence_scores: Record<string, number>;
    overall_confidence: number | boolean;
    processing_time_ms: number;
    file_size: number;
    mock?: boolean;
  };
  error?: string;
  timestamp: number;
}


interface ProgressiveAnalysisResultsProps {
  className?: string;
  inspectionId?: number | null;
  onAnalysisComplete?: (data: ProgressiveAnalysisData) => void;
}

export const ProgressiveAnalysisResults: React.FC<ProgressiveAnalysisResultsProps> = ({
  className = '',
  inspectionId = null,
  onAnalysisComplete
}) => {
  const [results, setResults] = useState<AnalysisResult[]>([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [totalFiles, setTotalFiles] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  
  // Use progressive analysis hook for SSE-based streaming
  const {
    data: streamData,
    isConnected: streamConnected,
    error: streamError,
    startProgressiveAnalysis
  } = useProgressiveAnalysis();
  
  // Start analysis when inspection ID is available
  useEffect(() => {
    if (inspectionId) {
      startProgressiveAnalysis(inspectionId);
    }
  }, [inspectionId, startProgressiveAnalysis]);
  
  // Notify parent when analysis is complete
  useEffect(() => {
    if (streamData && streamData.analysis_complete && onAnalysisComplete) {
      onAnalysisComplete(streamData);
    }
  }, [streamData, onAnalysisComplete]);
  
  // Use stream error for the SSE mode
  const [localError, setLocalError] = useState<string | null>(null);
  // Determine which error to use based on the mode
  const error = inspectionId !== null ? streamError : localError;

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (files && files.length > 0) {
      analyzeFiles(Array.from(files));
    }
  };

  // Create a worker URL for JSON parsing
  const createJsonParserWorker = () => {
    const workerCode = `
      // Web Worker for JSON parsing
      self.onmessage = function(e) {
        const { buffer, action } = e.data;
        
        if (action === 'parse') {
          // Process the buffer to extract JSON objects
          try {
            let braceCount = 0;
            let start = 0;
            let inString = false;
            let escaped = false;
            let results = [];
            let newStart = 0;
            
            for (let i = 0; i < buffer.length; i++) {
              const char = buffer[i];
              
              if (escaped) {
                escaped = false;
                continue;
              }
              
              if (char === '\\\\') {
                escaped = true;
                continue;
              }
              
              if (char === '"') {
                inString = !inString;
                continue;
              }
              
              if (!inString) {
                if (char === '{') {
                  if (braceCount === 0) start = i;
                  braceCount++;
                } else if (char === '}') {
                  braceCount--;
                  
                  if (braceCount === 0) {
                    // Found complete JSON object
                    const jsonStr = buffer.substring(start, i + 1);
                    try {
                      const result = JSON.parse(jsonStr);
                      results.push(result);
                      newStart = i + 1;
                      // Skip comma if present
                      while (newStart < buffer.length && (buffer[newStart] === ',' || buffer[newStart] === ' ')) {
                        newStart++;
                      }
                    } catch (parseError) {
                      // Skip invalid JSON
                    }
                  }
                }
              }
            }
            
            self.postMessage({ results, newStart, complete: false });
          } catch (error) {
            self.postMessage({ error: error.toString(), complete: false });
          }
        } else if (action === 'complete') {
          self.postMessage({ complete: true });
          self.close();
        }
      };
    `;
    return URL.createObjectURL(new Blob([workerCode], { type: 'application/javascript' }));
  };

  const analyzeFiles = async (files: File[]) => {
    // Cancel any existing analysis
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    abortControllerRef.current = new AbortController();
    setIsAnalyzing(true);
    setLocalError(null);
    setResults([]);
    setTotalFiles(files.length);

    // Create worker for JSON parsing
    const workerUrl = createJsonParserWorker();
    const jsonParserWorker = new Worker(workerUrl);
    
    // Track accumulated results to batch updates
    let accumulatedResults: AnalysisResult[] = [];
    let resultUpdateTimeoutId: number | null = null;
    
    // Function to batch update results
    const batchUpdateResults = () => {
      if (accumulatedResults.length === 0) return;
      
      setResults(prev => {
        const updated = [...prev];
        
        // Update or add each result
        accumulatedResults.forEach(result => {
          const existingIndex = updated.findIndex(r => r.file_index === result.file_index);
          if (existingIndex !== -1) {
            updated[existingIndex] = result;
          } else {
            updated.push(result);
          }
        });
        
        accumulatedResults = [];
        return updated;
      });
    };

    // Set up worker message handling
    jsonParserWorker.onmessage = (e) => {
      const { results, newStart, error, complete } = e.data;
      
      if (complete) {
        // Worker is done, clean up
        URL.revokeObjectURL(workerUrl);
        if (resultUpdateTimeoutId) {
          clearTimeout(resultUpdateTimeoutId);
          batchUpdateResults(); // Ensure any remaining results are processed
        }
        return;
      }
      
      if (error) {
        console.warn('Worker error:', error);
        return;
      }
      
      if (results && results.length > 0) {
        // Accumulate results for batch update
        accumulatedResults.push(...results);
        
        // Schedule a batch update (debounced)
        if (resultUpdateTimeoutId) clearTimeout(resultUpdateTimeoutId);
        resultUpdateTimeoutId = window.setTimeout(batchUpdateResults, 50);
      }
      
      if (newStart !== undefined) {
        // Tell the main thread where to continue parsing from
        return newStart;
      }
    };

    try {
      // Prepare form data
      const formData = new FormData();
      files.forEach(file => {
        formData.append('files', file);
      });

      const response = await fetch(
        'http://localhost:8000/api/stream/analysis/multi-image',
        {
          method: 'POST',
          body: formData,
          signal: abortControllerRef.current.signal
        }
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
        if (!jsonStarted && buffer.includes('{"result": true, "data": {')) {
          jsonStarted = true;
          // Find the results array
          const resultsIndex = buffer.indexOf('"results": [');
          if (resultsIndex !== -1) {
            arrayStarted = true;
            buffer = buffer.substring(resultsIndex + '"results": ['.length);
          }
        }

        if (arrayStarted && buffer.length > 0) {
          // Offload JSON parsing to the worker
          jsonParserWorker.postMessage({
            buffer,
            action: 'parse'
          });
          
          // Reset buffer after sending to worker
          buffer = '';
        }

        // Check for end of results array
        if (buffer.includes(']')) {
          break;
        }
      }
      
      // Final update and cleanup
      if (resultUpdateTimeoutId) {
        clearTimeout(resultUpdateTimeoutId);
        batchUpdateResults();
      }
      jsonParserWorker.postMessage({ action: 'complete' });

    } catch (err) {
      if (err instanceof Error && err.name !== 'AbortError') {
        setLocalError(err.message || 'Analysis failed');
      } else if (!(err instanceof Error)) {
        setLocalError('Analysis failed with unknown error');
      }
    } finally {
      setIsAnalyzing(false);
    }
  };

  const stopAnalysis = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    setIsAnalyzing(false);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'processing':
        return 'text-yellow-600 bg-yellow-50';
      case 'completed':
        return 'text-green-600 bg-green-50';
      case 'error':
        return 'text-red-600 bg-red-50';
      default:
        return 'text-gray-600 bg-gray-50';
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const completedCount = results.filter(r => r.status === 'completed').length;
  const errorCount = results.filter(r => r.status === 'error').length;
  const overallProgress = totalFiles > 0 ? (completedCount + errorCount) / totalFiles * 100 : 0;

  // Show either inspection-based streaming analysis or file-upload analysis
  if (inspectionId !== null) {
    return (
      <div className={`progressive-analysis-results ${className}`}>
        {/* Header */}
        <div className="mb-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">
            リアルタイム解析 {streamConnected && <span className="text-green-500">(接続中)</span>}
          </h3>
        </div>
        
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
                <h3 className="text-sm font-medium text-red-800">解析エラー</h3>
                <p className="text-sm text-red-700 mt-1">{error}</p>
              </div>
            </div>
          </div>
        )}

        {/* Loading state */}
        {streamConnected && !streamData && (
          <div className="flex items-center space-x-2 text-gray-500 mb-3">
            <div className="animate-spin h-4 w-4 border-2 border-blue-500 border-t-transparent rounded-full"></div>
            <span>解析データを読み込み中...</span>
          </div>
        )}

        {/* Stream data display */}
        {streamData && (
          <div className="space-y-4">
            {/* Progress indicator */}
            <div className="mb-3">
              <div className="flex justify-between text-sm text-gray-600 mb-1">
                <span>解析進行状況</span>
                <span>{Math.round(streamData.progress || 0)}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2.5">
                <div 
                  className="bg-blue-600 h-2.5 rounded-full" 
                  style={{ width: `${streamData.progress || 0}%` }}
                ></div>
              </div>
            </div>

            {/* Detection results */}
            {streamData.detections && streamData.detections.length > 0 && (
              <div>
                <h4 className="font-medium text-gray-700 mb-2">検出した不具合</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {streamData.detections.map((detection: DetectionResult, index: number) => (
                    <div key={index} className="bg-gray-50 p-2 rounded">
                      <div className="flex justify-between">
                        <span className="font-medium">{detection.class_name || 'Unknown'}</span>
                        <span className="text-sm bg-blue-100 text-blue-800 px-2 py-0.5 rounded">
                          {Math.round((detection.confidence || 0) * 100)}%
                        </span>
                      </div>
                      {detection.area && (
                        <div className="text-sm text-gray-500">
                          面積: {Math.round(detection.area)} px²
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Analysis results summary */}
            {streamData.confidence_above_threshold !== undefined && (
              <div className={`p-3 rounded-md ${
                streamData.confidence_above_threshold 
                  ? 'bg-red-50 text-red-700' 
                  : 'bg-green-50 text-green-700'
              }`}>
                <h4 className="font-medium mb-1">解析結果</h4>
                <p>
                  {streamData.confidence_above_threshold 
                    ? '✖ 不具合が検出されました' 
                    : '✓ 合格基準を満たしています'}
                </p>
                {streamData.threshold_value !== undefined && (
                  <p className="text-sm mt-1">
                    閾値: {streamData.threshold_value}%
                  </p>
                )}
              </div>
            )}

            {/* Processing time */}
            {streamData.processing_time_ms && (
              <div className="text-sm text-gray-500">
                処理時間: {streamData.processing_time_ms}ms
                {streamData.analysis_complete && ' (完了)'}
              </div>
            )}
          </div>
        )}
      </div>
    );
  }
  
  // Original file-upload based analysis UI
  return (
    <div className={`progressive-analysis-results ${className}`}>
      {/* Header */}
      <div className="mb-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">
          Progressive Image Analysis
        </h3>
        
        {/* File input */}
        <div className="flex items-center space-x-4">
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept="image/*"
            onChange={handleFileSelect}
            disabled={isAnalyzing}
            className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
          />
          
          {isAnalyzing && (
            <button
              onClick={stopAnalysis}
              className="px-4 py-2 bg-red-600 text-white text-sm rounded hover:bg-red-700"
            >
              Stop Analysis
            </button>
          )}
        </div>
      </div>

      {/* Overall progress */}
      {totalFiles > 0 && (
        <div className="mb-6">
          <div className="flex justify-between items-center mb-2">
            <span className="text-sm font-medium text-gray-700">
              Overall Progress
            </span>
            <span className="text-sm text-gray-600">
              {completedCount + errorCount} / {totalFiles} files
            </span>
          </div>
          
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-blue-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${overallProgress}%` }}
            ></div>
          </div>
          
          <div className="flex justify-between text-xs text-gray-600 mt-1">
            <span>{completedCount} completed</span>
            {errorCount > 0 && <span className="text-red-600">{errorCount} errors</span>}
            <span>{Math.round(overallProgress)}%</span>
          </div>
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
              <h3 className="text-sm font-medium text-red-800">Analysis Error</h3>
              <p className="text-sm text-red-700 mt-1">{error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Results list */}
      {results.length > 0 && (
        <div className="space-y-3">
          {results.map((result) => (
            <div
              key={result.file_index}
              className="border rounded-lg p-4 bg-white"
            >
              <div className="flex justify-between items-start mb-3">
                <div className="flex-1">
                  <div className="flex items-center space-x-3">
                    <span className="font-medium text-gray-900">
                      {result.filename}
                    </span>
                    
                    <span className={`px-2 py-1 text-xs rounded-full ${getStatusColor(result.status)}`}>
                      {result.status}
                    </span>
                    
                    {result.result?.mock && (
                      <span className="px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded-full">
                        Mock Data
                      </span>
                    )}
                  </div>
                  
                  {result.progress !== undefined && (
                    <div className="mt-2">
                      <div className="w-full bg-gray-200 rounded-full h-1">
                        <div
                          className="bg-blue-600 h-1 rounded-full transition-all duration-300"
                          style={{ width: `${result.progress}%` }}
                        ></div>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Results details */}
              {result.status === 'completed' && result.result && (
                <div className="mt-3 p-3 bg-gray-50 rounded">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <h4 className="text-sm font-medium text-gray-700 mb-2">Detected Defects</h4>
                      {result.result.detected_defects.length > 0 ? (
                        <div className="space-y-1">
                          {result.result.detected_defects.map((defect, index) => (
                            <div key={index} className="flex justify-between text-sm">
                              <span>{defect}</span>
                              <span className="text-gray-600">
                                {Math.round((result.result?.confidence_scores[defect] || 0) * 100)}%
                              </span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="text-sm text-gray-600">No defects detected</p>
                      )}
                    </div>
                    
                    <div>
                      <h4 className="text-sm font-medium text-gray-700 mb-2">Analysis Info</h4>
                      <div className="space-y-1 text-sm text-gray-600">
                        <div>File Size: {formatFileSize(result.result.file_size)}</div>
                        <div>Processing Time: {result.result.processing_time_ms}ms</div>
                        <div>
                          Overall Confidence: {
                            typeof result.result.overall_confidence === 'boolean' 
                              ? (result.result.overall_confidence ? 'High' : 'Low')
                              : `${Math.round(result.result.overall_confidence * 100)}%`
                          }
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Error details */}
              {result.status === 'error' && result.error && (
                <div className="mt-3 p-3 bg-red-50 rounded">
                  <p className="text-sm text-red-700">{result.error}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Empty state */}
      {!isAnalyzing && results.length === 0 && (
        <div className="text-center py-8 text-gray-500">
          <svg className="w-12 h-12 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
          <p>Select images to start progressive analysis</p>
        </div>
      )}
    </div>
  );
};