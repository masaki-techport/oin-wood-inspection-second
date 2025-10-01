import { getCameraApiConfig, logApiConfig, validateApiConfig } from './api-config';

// Camera configuration settings
export interface CameraConfig {
  type: 'basler' | 'webcam' | 'usb';
  basler: {
    apiBaseUrl: string;
    endpoints: {
      connect: string;
      disconnect: string;
      start: string;
      stop: string;
      snapshot: string;
      isConnected: string;
    };
    pollInterval: number;
  };
  webcam: {
    apiBaseUrl: string;
    endpoints: {
      connect: string;
      disconnect: string;
      start: string;
      stop: string;
      snapshot: string;
      isConnected: string;
      save: string;
      listCameras: string;
      setCameraIndex: string;
    };
    pollInterval: number;
    constraints: MediaStreamConstraints;
    fallbackConstraints: MediaStreamConstraints;
  };
  usb: {
    apiBaseUrl: string;
    endpoints: {
      connect: string;
      disconnect: string;
      start: string;
      stop: string;
      snapshot: string;
      isConnected: string;
      save: string;
      listCameras: string;
      setCameraIndex: string;
    };
    pollInterval: number;
    constraints: MediaStreamConstraints;
    fallbackConstraints: MediaStreamConstraints;
  };
}

// Get the dynamic API base URL from centralized configuration
const getApiBaseUrl = (): string => {
  const config = getCameraApiConfig();
  return config.baseUrl;
};

// Initialize camera configuration with dynamic API URLs
const createCameraConfig = (): CameraConfig => {
  const apiBaseUrl = getApiBaseUrl();
  
  return {
    // Switch this to change camera type: 'basler' | 'webcam' | 'usb'
    type: 'webcam',
    
    basler: {
      apiBaseUrl,
      endpoints: {
        connect: '/camera/connect',
        disconnect: '/camera/disconnect',
        start: '/camera/start',
        stop: '/camera/stop',
        snapshot: '/camera/snapshot',
        isConnected: '/camera/is_connected',
      },
      pollInterval: 200, // Reduced from 100ms to 200ms for better stability
    },
    
    webcam: {
      apiBaseUrl,
      endpoints: {
        connect: '/webcam/connect',
        disconnect: '/webcam/disconnect',
        start: '/webcam/start',
        stop: '/webcam/stop',
        snapshot: '/webcam/snapshot',
        isConnected: '/webcam/is_connected',
        save: '/webcam/save',
        listCameras: '/webcam/list_cameras',
        setCameraIndex: '/webcam/set_camera_index',
      },
      pollInterval: 200, // Reduced from 100ms to 200ms for better stability
      constraints: {
        video: {
          width: { ideal: 1280 },
          height: { ideal: 720 },
          facingMode: 'environment' // Use back camera if available
        },
        audio: false
      },
      fallbackConstraints: {
        video: true,
        audio: false
      }
    },

    usb: {
      apiBaseUrl,
      endpoints: {
        connect: '/webcam/connect',
        disconnect: '/webcam/disconnect',
        start: '/webcam/start',
        stop: '/webcam/stop',
        snapshot: '/webcam/snapshot',
        isConnected: '/webcam/is_connected',
        save: '/webcam/save',
        listCameras: '/webcam/list_cameras',
        setCameraIndex: '/webcam/set_camera_index',
      },
      pollInterval: 200, // Reduced from 100ms to 200ms for better stability
      constraints: {
        video: {
          width: { ideal: 1920 },
          height: { ideal: 1080 },
          // USB cameras typically don't have facingMode
          frameRate: { ideal: 30 }
        },
        audio: false
      },
      fallbackConstraints: {
        video: {
          width: { ideal: 1280 },
          height: { ideal: 720 }
        },
        audio: false
      }
    }
  };
};

// Create the camera configuration instance
export const cameraConfig: CameraConfig = createCameraConfig();

// Log configuration on module load for debugging
const validation = validateApiConfig();
if (validation.warnings.length > 0 || !validation.isValid) {
  console.warn('[Camera Config] Configuration issues detected:');
  logApiConfig();
} else {
  console.log('[Camera Config] Using API base URL:', cameraConfig.basler.apiBaseUrl);
}

export const getCameraType = (): 'basler' | 'webcam' | 'usb' => {
  return cameraConfig.type;
};

export const getBaslerConfig = () => {
  return cameraConfig.basler;
};

export const getWebcamConfig = () => {
  return cameraConfig.webcam;
};

export const getUSBConfig = () => {
  return cameraConfig.usb;
}; 