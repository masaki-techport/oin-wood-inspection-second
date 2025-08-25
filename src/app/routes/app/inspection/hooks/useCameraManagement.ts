import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { CameraType, UseCameraManagementReturn } from '../types';
import { getBaslerConfig, getWebcamConfig, getUSBConfig } from '@/config/camera-config';
import { getCameraApiConfig, logApiConfig } from '@/config/api-config';

// Enhanced error types for better error handling
export interface CameraError {
  type: 'network' | 'hardware' | 'configuration' | 'api' | 'unknown';
  message: string;
  details?: string;
  timestamp: number;
}

// Network status tracking
interface NetworkStatus {
  isOnline: boolean;
  lastCheck: number;
  retryCount: number;
}

/**
 * Hook for managing camera state and operations
 * @param enablePreview - Whether camera preview polling should be enabled
 * @returns Camera management state and functions
 */
export const useCameraManagement = (enablePreview: boolean = true): UseCameraManagementReturn => {
  const [image, setImage] = useState<string | null>(null);
  const [capturedImage, setCapturedImage] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState<boolean | null>(null);
  const [selectedCameraType, setSelectedCameraType] = useState<CameraType>('basler');
  const [droppedFrame, setDroppedFrame] = useState(false);
  const [cameraError, setCameraError] = useState<CameraError | null>(null);
  const [networkStatus, setNetworkStatus] = useState<NetworkStatus>({
    isOnline: true,
    lastCheck: Date.now(),
    retryCount: 0
  });

  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const hasInitializedRef = useRef(false);
  const droppedRef = useRef(false);
  const retryTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const isUnmountedRef = useRef(false);

  // Error categorization helper
  const categorizeError = (error: any): CameraError => {
    const timestamp = Date.now();
    
    if (axios.isAxiosError(error)) {
      if (error.code === 'ECONNREFUSED' || error.code === 'ENOTFOUND' || error.code === 'ETIMEDOUT') {
        return {
          type: 'network',
          message: 'ネットワーク接続エラー - バックエンドサーバーに接続できません',
          details: `${error.code}: ${error.message}`,
          timestamp
        };
      }
      
      if (error.response?.status === 404) {
        return {
          type: 'configuration',
          message: 'API エンドポイントが見つかりません',
          details: `404: ${error.config?.url}`,
          timestamp
        };
      }
      
      if (error.response?.status && error.response.status >= 500) {
        return {
          type: 'api',
          message: 'サーバーエラーが発生しました',
          details: `${error.response.status}: ${error.response.statusText || 'Unknown error'}`,
          timestamp
        };
      }
    }
    
    // Check for camera-specific errors
    if (error.response?.data?.error) {
      const errorMsg = String(error.response.data.error).toLowerCase();
      if (errorMsg.includes('camera') || errorMsg.includes('device')) {
        return {
          type: 'hardware',
          message: 'カメラハードウェアエラー',
          details: String(error.response.data.error),
          timestamp
        };
      }
    }
    
    return {
      type: 'unknown',
      message: 'カメラ接続で不明なエラーが発生しました',
      details: error.message || String(error),
      timestamp
    };
  };

  // Retry logic with exponential backoff
  const getRetryDelay = (retryCount: number, errorType: CameraError['type']): number => {
    switch (errorType) {
      case 'network':
        // Exponential backoff: 1s, 2s, 4s, 8s, max 30s
        return Math.min(1000 * Math.pow(2, retryCount), 30000);
      case 'hardware':
        // Linear retry every 5 seconds, max 3 attempts
        return retryCount < 3 ? 5000 : -1; // -1 means no more retries
      case 'configuration':
        // No automatic retry for configuration errors
        return -1;
      case 'api':
        // Linear retry every 2 seconds, max 5 attempts
        return retryCount < 5 ? 2000 : -1;
      default:
        return retryCount < 3 ? 3000 : -1;
    }
  };

  // Clear error state
  const clearError = () => {
    setCameraError(null);
    setNetworkStatus(prev => ({ ...prev, retryCount: 0 }));
  };

  // Set error with retry logic
  const setErrorWithRetry = (error: CameraError, retryCallback: () => void) => {
    // Check if component is unmounted before setting error or retrying
    if (isUnmountedRef.current) {
      console.log('[Camera Management] Component unmounted, skipping error retry');
      return;
    }
    
    setCameraError(error);
    
    const retryDelay = getRetryDelay(networkStatus.retryCount, error.type);
    
    if (retryDelay > 0) {
      console.log(`[Camera] Retrying in ${retryDelay}ms (attempt ${networkStatus.retryCount + 1})`);
      
      setNetworkStatus(prev => ({
        ...prev,
        retryCount: prev.retryCount + 1,
        lastCheck: Date.now()
      }));
      
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current);
      }
      
      retryTimeoutRef.current = setTimeout(() => {
        // Double-check if component is still mounted before retrying
        if (isUnmountedRef.current) {
          console.log('[Camera Management] Component unmounted during retry, cancelling');
          return;
        }
        console.log(`[Camera] Retrying connection...`);
        retryCallback();
      }, retryDelay);
    } else {
      console.log(`[Camera] Max retries reached or no retry for error type: ${error.type}`);
    }
  };

  // Log configuration on hook initialization
  useEffect(() => {
    const apiConfig = getCameraApiConfig();
    console.log('[Camera Management] Initialized with API config:', {
      baseUrl: apiConfig.baseUrl,
      isNetworkMode: apiConfig.isNetworkMode,
      enablePreview
    });
    
    if (!apiConfig.isNetworkMode) {
      console.log('[Camera Management] Running in localhost mode');
    } else {
      console.log('[Camera Management] Running in network mode with IP:', apiConfig.host);
    }
  }, [enablePreview]);

  // Basler camera functions
  const fetchBaslerImage = async () => {
    // Check if component is unmounted before making API call
    if (isUnmountedRef.current) {
      console.log('[Camera Management] Component unmounted, skipping Basler image fetch');
      return;
    }
    
    const config = getBaslerConfig();
    try {
      const res = await axios.get(`${config.apiBaseUrl}${config.endpoints.snapshot}`, {
        timeout: 5000 // 5 second timeout
      });

      // Check for error status in response
      if (res.data.status === "error" || res.data.status === "disconnected" || res.data.status === "no_frame") {
        console.warn(`Basler status: ${res.data.status}, error: ${res.data.error || 'Unknown error'}`);

        // Set dropped frame indicator
        if (!droppedRef.current) {
          droppedRef.current = true;
          setDroppedFrame(true);
        }

        // If disconnected, create hardware error and try to reconnect
        if (res.data.status === "disconnected") {
          const error: CameraError = {
            type: 'hardware',
            message: 'Baslerカメラが切断されました',
            details: res.data.error || 'Camera disconnected',
            timestamp: Date.now()
          };
          setErrorWithRetry(error, fetchBaslerImage);
          
          // Slow down polling when camera is disconnected
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = setInterval(fetchBaslerImage, config.pollInterval * 5);
          }
        }

        return;
      }

      // Handle valid image
      if (res.data.image) {
        // Check again if component is still mounted before updating state
        if (isUnmountedRef.current) {
          console.log('[Camera Management] Component unmounted during image processing, skipping state updates');
          return;
        }
        
        setImage(`data:image/jpeg;base64,${res.data.image}`);

        // Clear any previous errors on successful connection
        if (cameraError) {
          clearError();
        }

        // Reset dropped frame indicator
        if (droppedRef.current) {
          droppedRef.current = false;
          setDroppedFrame(false);
        }

        // Update network status
        setNetworkStatus(prev => ({
          isOnline: true,
          lastCheck: Date.now(),
          retryCount: 0
        }));

        // Reset polling interval if needed
        if (intervalRef.current && !isUnmountedRef.current) {
          // Always reset to normal polling interval when we get a successful frame
          clearInterval(intervalRef.current);
          intervalRef.current = setInterval(fetchBaslerImage, config.pollInterval);
        }
      } else {
        console.warn('画像データが空です');
      }
    } catch (err: any) {
      console.error('fetchBaslerImage失敗:', err);

      // Categorize and handle the error
      const error = categorizeError(err);
      setErrorWithRetry(error, fetchBaslerImage);

      // Set dropped frame indicator
      droppedRef.current = true;
      setDroppedFrame(true);

      // Update network status
      setNetworkStatus(prev => ({
        isOnline: error.type !== 'network',
        lastCheck: Date.now(),
        retryCount: prev.retryCount
      }));
    }
  };

  // Webcam/USB functions
  const fetchWebcamImage = async () => {
    // Check if component is unmounted before making API call
    if (isUnmountedRef.current) {
      console.log('[Camera Management] Component unmounted, skipping webcam image fetch');
      return;
    }
    
    const config = selectedCameraType === 'usb' ? getUSBConfig() : getWebcamConfig();
    try {
      const res = await axios.get(`${config.apiBaseUrl}${config.endpoints.snapshot}`, {
        timeout: 5000 // 5 second timeout
      });

      // Check response status
      if (res.data.status === "error" || res.data.status === "disconnected" || res.data.status === "no_frame") {
        console.warn(`Webcam status: ${res.data.status}, error: ${res.data.error || 'Unknown error'}`);

        // Set dropped frame indicator
        if (!droppedRef.current) {
          droppedRef.current = true;
          setDroppedFrame(true);
        }

        // If disconnected, create hardware error and try to reconnect
        if (res.data.status === "disconnected") {
          const error: CameraError = {
            type: 'hardware',
            message: `${selectedCameraType === 'usb' ? 'USB' : 'Web'}カメラが切断されました`,
            details: res.data.error || 'Camera disconnected',
            timestamp: Date.now()
          };
          setErrorWithRetry(error, fetchWebcamImage);
          
          // Slow down polling when camera is disconnected
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = setInterval(fetchWebcamImage, config.pollInterval * 5);
          }
        }

        return;
      }

      // Handle valid image
      if (res.data.image) {
        // Check again if component is still mounted before updating state
        if (isUnmountedRef.current) {
          console.log('[Camera Management] Component unmounted during webcam image processing, skipping state updates');
          return;
        }
        
        setImage(`data:image/jpeg;base64,${res.data.image}`);

        // Clear any previous errors on successful connection
        if (cameraError) {
          clearError();
        }

        // Reset dropped frame indicator
        if (droppedRef.current) {
          droppedRef.current = false;
          setDroppedFrame(false);
        }

        // Update network status
        setNetworkStatus(prev => ({
          isOnline: true,
          lastCheck: Date.now(),
          retryCount: 0
        }));

        // Reset polling interval if it was slowed down
        if (intervalRef.current && !isUnmountedRef.current) {
          // Always reset to normal polling interval when we get a successful frame
          clearInterval(intervalRef.current);
          intervalRef.current = setInterval(fetchWebcamImage, config.pollInterval);
        }
      } else {
        console.warn('Webcam: No image data received');
      }
    } catch (err: any) {
      console.error('fetchWebcamImage failed:', err);

      // Categorize and handle the error
      const error = categorizeError(err);
      setErrorWithRetry(error, fetchWebcamImage);

      // Set dropped frame indicator
      droppedRef.current = true;
      setDroppedFrame(true);

      // Update network status
      setNetworkStatus(prev => ({
        isOnline: error.type !== 'network',
        lastCheck: Date.now(),
        retryCount: prev.retryCount
      }));
    }
  };

  const initWebcam = async () => {
    // Check if component is unmounted before initialization
    if (isUnmountedRef.current) {
      console.log('[Camera Management] Component unmounted, skipping webcam initialization');
      return;
    }
    
    const config = selectedCameraType === 'usb' ? getUSBConfig() : getWebcamConfig();
    try {
      // Stop existing intervals
      if (intervalRef.current) clearInterval(intervalRef.current);

      // If preview is disabled, don't initialize camera for preview
      if (!enablePreview) {
        console.log('Camera preview disabled - skipping webcam initialization');
        setImage(null);
        setIsConnected(null);
        setDroppedFrame(false);
        return;
      }

      // Connect to webcam via Python backend
      await axios.post(`${config.apiBaseUrl}${config.endpoints.disconnect}`, {}).catch(() => { });
      await axios.post(`${config.apiBaseUrl}${config.endpoints.connect}`);

      // Check connection
      const res = await axios.get(`${config.apiBaseUrl}${config.endpoints.isConnected}`);
      const connected = res.data.connected === true;
      
      // Check if component is still mounted before updating state
      if (isUnmountedRef.current) {
        console.log('[Camera Management] Component unmounted during webcam connection check');
        return;
      }
      
      setIsConnected(connected);

      if (!connected) return;

      // Start continuous capture
      await axios.post(`${config.apiBaseUrl}${config.endpoints.start}`);
      await fetchWebcamImage();
      
      // Only set interval if component is still mounted
      if (!isUnmountedRef.current) {
        intervalRef.current = setInterval(fetchWebcamImage, config.pollInterval);
      }

    } catch (err) {
      console.error('Camera initialization failed:', err);
      setIsConnected(false);
    }
  };

  const stopWebcam = async () => {
    const config = selectedCameraType === 'usb' ? getUSBConfig() : getWebcamConfig();
    if (intervalRef.current) clearInterval(intervalRef.current);
    await axios.post(`${config.apiBaseUrl}${config.endpoints.stop}`, {}).catch(() => { });
    await axios.post(`${config.apiBaseUrl}${config.endpoints.disconnect}`, {}).catch(() => { });
  };

  const initBasler = async () => {
    // Check if component is unmounted before initialization
    if (isUnmountedRef.current) {
      console.log('[Camera Management] Component unmounted, skipping Basler initialization');
      return;
    }
    
    const config = getBaslerConfig();
    try {
      // 残っている場合は停止して切断する
      await axios.post(`${config.apiBaseUrl}${config.endpoints.stop}`, {}).catch(() => { });
      await axios.post(`${config.apiBaseUrl}${config.endpoints.disconnect}`, {}).catch(() => { });

      // If preview is disabled, don't initialize camera for preview
      if (!enablePreview) {
        console.log('Camera preview disabled - skipping Basler initialization');
        setImage(null);
        setIsConnected(null);
        setDroppedFrame(false);
        return;
      }

      // カメラに接続する
      await axios.post(`${config.apiBaseUrl}${config.endpoints.connect}`);

      // 接続を確認する
      const res = await axios.get(`${config.apiBaseUrl}${config.endpoints.isConnected}`);
      const connected = res.data.connected === true;
      
      // Check if component is still mounted before updating state
      if (isUnmountedRef.current) {
        console.log('[Camera Management] Component unmounted during Basler connection check');
        return;
      }
      
      setIsConnected(connected);

      if (!connected) return;

      // 接続が成功した場合は画像の取得を開始する
      await axios.post(`${config.apiBaseUrl}${config.endpoints.start}`);
      await fetchBaslerImage();
      
      // Only set interval if component is still mounted
      if (!isUnmountedRef.current) {
        intervalRef.current = setInterval(fetchBaslerImage, config.pollInterval);
      }

    } catch (err) {
      console.error('Basler camera initialization failed:', err);
      setIsConnected(false);
    }
  };

  const stopBasler = async () => {
    const config = getBaslerConfig();
    if (intervalRef.current) clearInterval(intervalRef.current);
    await axios.post(`${config.apiBaseUrl}${config.endpoints.stop}`, {}).catch(() => { });
    await axios.post(`${config.apiBaseUrl}${config.endpoints.disconnect}`, {}).catch(() => { });
  };

  const handleCameraTypeChange = async (newCameraType: CameraType) => {
    if (newCameraType === selectedCameraType) return;

    console.log(`Switching camera from ${selectedCameraType} to ${newCameraType} (preview enabled: ${enablePreview})`);

    // Stop current camera and polling
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    // Stop current camera only if preview was enabled
    if (enablePreview) {
      if (selectedCameraType === 'webcam' || selectedCameraType === 'usb') {
        await stopWebcam();
      } else {
        await stopBasler();
      }
    }

    // Reset states
    setImage(null);
    setIsConnected(null);
    setDroppedFrame(false);
    droppedRef.current = false;

    // Update camera type
    setSelectedCameraType(newCameraType);

    // Only initialize new camera if preview is enabled
    if (enablePreview) {
      // Initialize new camera type with a slight delay
      setTimeout(async () => {
        if (newCameraType === 'webcam' || newCameraType === 'usb') {
          await initWebcam();
        } else {
          await initBasler();
        }
      }, 300);  // Increased delay to ensure previous camera is fully stopped
    }
  };

  // Update useEffect to handle camera type changes and preview enable/disable
  useEffect(() => {
    console.log(`Camera management - type: ${selectedCameraType}, preview enabled: ${enablePreview}`);

    // Stop any existing polling
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    // If preview is disabled, stop everything and clear states
    if (!enablePreview) {
      console.log('Camera preview disabled - stopping all camera preview activities');
      setImage(null);
      setIsConnected(null);
      setDroppedFrame(false);
      droppedRef.current = false;
      hasInitializedRef.current = false;

      // Stop cameras but don't disconnect (they might be needed for inspections)
      const stopPreview = async () => {
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
      };
      stopPreview();
      return;
    }

    // Reset initialization flag when camera type changes or when preview is re-enabled
    hasInitializedRef.current = false;

    const init = async () => {
      // Check if component is unmounted before initialization
      if (isUnmountedRef.current) {
        console.log('[Camera Management] Component unmounted, skipping initialization');
        return;
      }
      
      if (selectedCameraType === 'webcam' || selectedCameraType === 'usb') {
        await initWebcam();
      } else {
        await initBasler();
      }
    };

    init();
    hasInitializedRef.current = true;

    return () => {
      console.log('[Camera Management] Cleanup triggered');
      
      // Mark as unmounted immediately to prevent any new operations
      isUnmountedRef.current = true;
      
      // Clear retry timeouts immediately (synchronous)
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current);
        retryTimeoutRef.current = null;
      }
      
      // Clear polling intervals immediately (synchronous)
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      
      // Reset flags immediately
      droppedRef.current = false;
      hasInitializedRef.current = false;
      
      // Async cleanup should be done separately to avoid React warnings
      if (enablePreview) {
        Promise.resolve().then(async () => {
          try {
            if (selectedCameraType === 'webcam' || selectedCameraType === 'usb') {
              await stopWebcam();
            } else {
              await stopBasler();
            }
            console.log('[Camera Management] Async cleanup completed successfully');
          } catch (error) {
            console.error('[Camera Management] Error during async cleanup:', error);
          }
        });
      }
    };
  }, [selectedCameraType, enablePreview]);

  // Manual stop camera function for cleanup before navigation
  const stopCamera = async () => {
    console.log('[Camera Management] Manually stopping camera...');
    
    // Mark as unmounted to prevent any new operations
    isUnmountedRef.current = true;
    
    // Clear any retry timeouts immediately
    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current);
      retryTimeoutRef.current = null;
    }
    
    // Clear polling intervals immediately
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    
    // Reset all refs
    droppedRef.current = false;
    hasInitializedRef.current = false;
    
    // Stop the appropriate camera type
    try {
      if (selectedCameraType === 'webcam' || selectedCameraType === 'usb') {
        await stopWebcam();
      } else {
        await stopBasler();
      }
    } catch (error) {
      console.error('[Camera Management] Error stopping camera:', error);
    }
    
    // Reset all states
    setImage(null);
    setIsConnected(null);
    setDroppedFrame(false);
    setCameraError(null);
    setNetworkStatus({
      isOnline: true,
      lastCheck: Date.now(),
      retryCount: 0
    });
    
    console.log('[Camera Management] Camera stopped successfully');
  };

  // Cleanup function for component unmount
  useEffect(() => {
    // Reset unmounted flag when component mounts
    isUnmountedRef.current = false;
    
    return () => {
      // Mark as unmounted and clear any remaining timeouts
      isUnmountedRef.current = true;
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current);
        retryTimeoutRef.current = null;
      }
    };
  }, []);

  return {
    image,
    capturedImage,
    isConnected,
    droppedFrame,
    selectedCameraType,
    handleCameraTypeChange,
    cameraError,
    networkStatus,
    clearError,
    stopCamera
  };
};