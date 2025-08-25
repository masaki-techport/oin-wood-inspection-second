import { useState, useEffect, useRef, useCallback } from 'react';
import { AnalysisResponse, DetectionResult, ProgressiveAnalysisData, SensorStatusData, StreamingResult } from '../types/streaming';

interface StreamingConfig {
  baseUrl?: string;
  reconnectDelay?: number;
  maxReconnectAttempts?: number;
}

interface SSEHookReturn<T> {
  data: T | null;
  isConnected: boolean;
  error: string | null;
  reconnect: () => void;
  disconnect: () => void;
}

interface CameraStreamHookReturn {
  streamUrl: string;
  isLoading: boolean;
  error: string | null;
  refreshStream: () => void;
}

const DEFAULT_CONFIG: StreamingConfig = {
  baseUrl: 'http://localhost:8000',
  reconnectDelay: 1000,
  maxReconnectAttempts: 5
};

/**
 * Hook for consuming Server-Sent Events streams
 */
export function useSSEStream<T>(endpoint: string, config: StreamingConfig = {}): SSEHookReturn<T> {
  const [data, setData] = useState<T | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  
  const finalConfig = { ...DEFAULT_CONFIG, ...config };
  const url = `${finalConfig.baseUrl}${endpoint}`;

  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    
    setIsConnected(false);
    reconnectAttemptsRef.current = 0;
  }, []);

  const connect = useCallback(() => {
    if (eventSourceRef.current) {
      disconnect();
    }

    try {
      const eventSource = new EventSource(url);
      eventSourceRef.current = eventSource;

      eventSource.onopen = () => {
        console.log(`SSE connected to ${endpoint}`);
        setIsConnected(true);
        setError(null);
        reconnectAttemptsRef.current = 0;
      };

      eventSource.onmessage = (event) => {
        try {
          const parsedData = JSON.parse(event.data);
          setData(parsedData);
        } catch (e) {
          console.warn('Failed to parse SSE data:', event.data);
          setData(event.data);
        }
      };

      // Handle specific event types
      eventSource.addEventListener('sensor-status', (event) => {
        try {
          const statusData = JSON.parse(event.data) as T;
          setData(statusData);
        } catch (e) {
          console.warn('Failed to parse sensor status:', event.data);
        }
      });

      eventSource.addEventListener('connected', (event) => {
        console.log('SSE connection confirmed:', event.data);
      });

      eventSource.addEventListener('keepalive', (event) => {
        // Handle keepalive messages
        console.debug('SSE keepalive received');
      });

      eventSource.onerror = (event) => {
        console.error(`SSE error on ${endpoint}:`, event);
        setIsConnected(false);
        
        // Attempt reconnection
        if (reconnectAttemptsRef.current < (finalConfig.maxReconnectAttempts || 5)) {
          reconnectAttemptsRef.current++;
          setError(`Connection lost. Reconnecting... (${reconnectAttemptsRef.current}/${finalConfig.maxReconnectAttempts})`);
          
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, finalConfig.reconnectDelay);
        } else {
          setError('Connection failed. Maximum reconnection attempts reached.');
        }
      };

    } catch (e) {
      setError(`Failed to create SSE connection: ${e}`);
    }
  }, [url, endpoint, finalConfig, disconnect]);

  const reconnect = useCallback(() => {
    reconnectAttemptsRef.current = 0;
    connect();
  }, [connect]);

  useEffect(() => {
    connect();
    
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    data,
    isConnected,
    error,
    reconnect,
    disconnect
  };
}

/**
 * Hook for consuming camera video streams
 */
export function useCameraStream(cameraType: string = 'basler', config: StreamingConfig = {}): CameraStreamHookReturn {
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [streamKey, setStreamKey] = useState(0); // For forcing stream refresh
  
  const finalConfig = { ...DEFAULT_CONFIG, ...config };
  const streamUrl = `${finalConfig.baseUrl}/api/stream/camera/${cameraType}?t=${streamKey}`;

  const refreshStream = useCallback(() => {
    setStreamKey(prev => prev + 1);
    setIsLoading(true);
    setError(null);
  }, []);

  // Handle image load events
  const handleImageLoad = useCallback(() => {
    setIsLoading(false);
    setError(null);
  }, []);

  const handleImageError = useCallback(() => {
    setIsLoading(false);
    setError('Failed to load camera stream');
  }, []);

  return {
    streamUrl,
    isLoading,
    error,
    refreshStream
  };
}

/**
 * Hook for sensor status streaming via SSE
 */
export function useSensorStatusStream(config: StreamingConfig = {}) {
  return useSSEStream<SensorStatusData>('/api/stream/sensor/status', config);
}

/**
 * Hook for streaming file data
 */
export function useFileStream(filePath: string | null, convertFormat?: string, config: StreamingConfig = {}) {
  const [streamUrl, setStreamUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const finalConfig = { ...DEFAULT_CONFIG, ...config };

  useEffect(() => {
    if (!filePath) {
      setStreamUrl(null);
      return;
    }

    setIsLoading(true);
    setError(null);

    const params = new URLSearchParams({ path: filePath });
    if (convertFormat) {
      params.append('convert', convertFormat);
    }

    const url = `${finalConfig.baseUrl}/api/stream/file?${params.toString()}`;
    setStreamUrl(url);
    setIsLoading(false);
  }, [filePath, convertFormat, finalConfig.baseUrl]);

  return {
    streamUrl,
    isLoading,
    error
  };
}

/**
 * Hook for streaming analysis results
 */
export function useAnalysisStream(config: StreamingConfig = {}) {
  const [results, setResults] = useState<StreamingResult[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [totalFiles, setTotalFiles] = useState(0);
  
  const finalConfig = { ...DEFAULT_CONFIG, ...config };
  
  const startAnalysis = async (files: File[]) => {
    if (isProcessing) return;
    
    setIsProcessing(true);
    setResults([]);
    setProgress(0);
    setError(null);
    setTotalFiles(files.length);
    
    try {
      // Create form data with files
      const formData = new FormData();
      files.forEach(file => {
        formData.append('files', file);
      });
      
      // Prepare the fetch request
      const response = await fetch(`${finalConfig.baseUrl}/api/stream/analysis/batch`, {
        method: 'POST',
        body: formData
      });
      
      if (!response.ok) {
        throw new Error(`Server responded with ${response.status}: ${response.statusText}`);
      }
      
      // Process the streaming response
      const reader = response.body?.getReader();
      if (!reader) throw new Error('Response body reader not available');
      
      // Read and process chunks
      let receivedText = '';
      let receivedResults: any[] = [];
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        // Decode the chunk
        const chunk = new TextDecoder().decode(value);
        receivedText += chunk;
        
        // Process complete JSON objects
        try {
          // Find complete JSON objects
          const jsonStr = receivedText.trim();
          if (jsonStr.startsWith('{') && jsonStr.endsWith('}')) {
            // Parse the JSON response
            const data = JSON.parse(jsonStr);
            
            if (data.result === false) {
              setError(data.error || 'Analysis failed');
              break;
            }
            
            if (data.data && data.data.batches) {
              // Process batch results
              const newResults = data.data.batches.flatMap((batch: any) => batch.results);
              receivedResults = newResults;
              setResults(newResults);
              
              // Update progress
              const completedFiles = data.data.batches.reduce(
                (sum: number, batch: any) => sum + batch.batch_size, 0
              );
              const progress = Math.min(100, (completedFiles / data.data.total_files) * 100);
              setProgress(progress);
            }
          }
        } catch (e) {
          console.warn('Error parsing streaming JSON:', e);
          // Continue reading, as we might have incomplete JSON
        }
      }
      
      setProgress(100);
      setIsProcessing(false);
      
    } catch (e) {
      if (e instanceof Error) {
        setError(e.message || 'Analysis stream failed');
      } else {
        setError('Analysis stream failed with unknown error');
      }
      setIsProcessing(false);
    }
  };
  
  return {
    results,
    isProcessing,
    progress,
    error,
    totalFiles,
    startAnalysis
  };
}

/**
 * Hook for streaming progressive analysis results
 */
export function useProgressiveAnalysis(config: StreamingConfig = {}) {
  const [data, setData] = useState<ProgressiveAnalysisData | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  
  const finalConfig = { ...DEFAULT_CONFIG, ...config };
  
  const startProgressiveAnalysis = async (inspectionId: number) => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
    
    setData(null);
    setError(null);
    
    try {
      const url = `${finalConfig.baseUrl}/api/stream/inspection/${inspectionId}/progressive`;
      const eventSource = new EventSource(url);
      eventSourceRef.current = eventSource;
      
      eventSource.onopen = () => {
        console.log(`Progressive analysis SSE connected for inspection ${inspectionId}`);
        setIsConnected(true);
      };
      
      eventSource.addEventListener('analysis-update', (event) => {
        try {
          const progressData = JSON.parse(event.data) as ProgressiveAnalysisData;
          setData(progressData);
        } catch (e) {
          console.warn('Failed to parse progressive analysis data:', event.data);
        }
      });
      
      eventSource.addEventListener('analysis-complete', (event) => {
        try {
          const finalData = JSON.parse(event.data) as ProgressiveAnalysisData;
          setData(finalData);
          eventSource.close();
        } catch (e) {
          console.warn('Failed to parse final analysis data:', event.data);
        }
      });
      
      eventSource.onerror = (event) => {
        console.error(`Progressive analysis SSE error:`, event);
        setIsConnected(false);
        setError('Connection to analysis stream lost');
        eventSource.close();
      };
      
    } catch (e) {
      if (e instanceof Error) {
        setError(`Failed to create progressive analysis connection: ${e.message}`);
      } else {
        setError('Failed to create progressive analysis connection: unknown error');
      }
    }
  };
  
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);
  
  return {
    data,
    isConnected,
    error,
    startProgressiveAnalysis
  };
}

/**
 * Utility function to get streaming statistics
 */
export async function getStreamingStats(config: StreamingConfig = {}) {
  const finalConfig = { ...DEFAULT_CONFIG, ...config };
  
  try {
    const response = await fetch(`${finalConfig.baseUrl}/api/stream/stats`);
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Failed to fetch streaming stats:', error);
    throw error;
  }
}

/**
 * Utility function to configure camera stream
 */
export async function configureCameraStream(
  frameRate?: number, 
  quality?: number, 
  config: StreamingConfig = {}
) {
  const finalConfig = { ...DEFAULT_CONFIG, ...config };
  
  try {
    const params = new URLSearchParams();
    if (frameRate !== undefined) params.append('frame_rate', frameRate.toString());
    if (quality !== undefined) params.append('quality', quality.toString());
    
    const response = await fetch(
      `${finalConfig.baseUrl}/api/stream/camera/configure?${params.toString()}`,
      { method: 'POST' }
    );
    
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Failed to configure camera stream:', error);
    throw error;
  }
}