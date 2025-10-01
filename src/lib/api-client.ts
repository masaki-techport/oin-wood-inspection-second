import Axios from 'axios';

import { useNotifications } from '@/components/ui/notifications';

// Enhanced API URL detection with proxy support and fallback mechanisms
export const getApiUrl = () => {
  // Priority 1: Force proxy usage in development mode for better reliability
  if (process.env.NODE_ENV === 'development') {
    console.log('[API CLIENT] 🔧 Development mode: using proxy at /api');
    console.log('[API CLIENT] 📍 This will route through setupProxy.js to backend');
    return '/api';
  }
  
  // Priority 2: Explicit API URL for production
  let apiUrl = process.env.REACT_APP_API_URL;
  
  if (apiUrl && apiUrl.trim()) {
    // Ensure URL has protocol
    if (!apiUrl.startsWith('http://') && !apiUrl.startsWith('https://')) {
      apiUrl = `http://${apiUrl}`;
    }
    console.log('[API CLIENT] 🎯 Using explicit API URL:', apiUrl);
    return apiUrl;
  }

  // Priority 3: Build URL from host/port with network mode support
  const backendHost = process.env.REACT_APP_BACKEND_HOST || 'localhost';
  const backendPort = process.env.REACT_APP_BACKEND_PORT || '8000';
  const networkMode = process.env.REACT_APP_NETWORK_MODE === 'true';
  
  let targetHost = backendHost;
  
  // Handle auto detection for network mode
  if (targetHost === 'auto') {
    if (networkMode) {
      // In network mode, try to use the current window location host IP
      const currentHost = window.location.hostname;
      if (currentHost !== 'localhost' && currentHost !== '127.0.0.1') {
        targetHost = currentHost;
        console.log('[API CLIENT] 🌐 Network mode: using current host IP:', targetHost);
      } else {
        targetHost = 'localhost';
        console.log('[API CLIENT] 🏠 Network mode but on localhost, using localhost');
      }
    } else {
      targetHost = 'localhost';
      console.log('[API CLIENT] 🔧 Auto mode with network disabled, using localhost');
    }
  }
  
  const finalUrl = `http://${targetHost}:${backendPort}`;
  console.log('[API CLIENT] 🔗 Built API URL:', finalUrl);
  console.log('[API CLIENT] ⚙️  Network mode:', networkMode);
  console.log('[API CLIENT] 🖥️  Backend host config:', backendHost);
  
  return finalUrl;
};

// Initialize API client with enhanced configuration
const baseURL = getApiUrl();
console.log('[API CLIENT] 🚀 Initializing Axios with baseURL:', baseURL);

export const api = Axios.create({
  baseURL,
  timeout: 20000, // Increased to 20 second timeout to reduce timeout errors
  headers: {
    'Content-Type': 'application/json',
  },
});

// Enhanced request interceptor for debugging
api.interceptors.request.use(
  (config) => {
    const debugEnabled = process.env.REACT_APP_DEBUG_API === 'true';
    if (debugEnabled) {
      console.log('[API CLIENT] 📤 Request:', {
        method: config.method?.toUpperCase(),
        url: config.url,
        baseURL: config.baseURL,
        fullURL: `${config.baseURL}${config.url}`,
      });
    }
    return config;
  },
  (error) => {
    console.error('[API CLIENT] ❌ Request Error:', error);
    return Promise.reject(error);
  }
);

// Enhanced response interceptor with better error handling and debouncing
const errorDebounce = new Map<string, number>();
const consecutiveErrors = new Map<string, number>();
const ERROR_DEBOUNCE_TIME = 10000; // 10 seconds
const MAX_CONSECUTIVE_ERRORS = 5; // Suppress notifications after 5 consecutive errors

api.interceptors.response.use(
  (response) => {
    const debugEnabled = process.env.REACT_APP_DEBUG_API === 'true';
    if (debugEnabled) {
      console.log('[API CLIENT] 📥 Response:', {
        status: response.status,
        url: response.config.url,
        data: response.data,
      });
    }
    
    // Clear consecutive errors for this endpoint on successful response
    const errorKey = `${response.config.url || 'unknown'}`;
    if (consecutiveErrors.has(errorKey)) {
      consecutiveErrors.delete(errorKey);
    }
    
    return response.data;
  },
  (error) => {
    // Enhanced error logging
    console.error('[API CLIENT] ❌ Response Error:', {
      message: error.message,
      code: error.code,
      status: error.response?.status,
      statusText: error.response?.statusText,
      url: error.config?.url,
      baseURL: error.config?.baseURL,
      fullURL: error.config ? `${error.config.baseURL}${error.config.url}` : 'unknown',
    });
    
    // Create debounce key for similar errors
    const errorKey = `${error.code || 'unknown'}-${error.config?.url || 'unknown'}-${error.response?.status || 'no-status'}`;
    const now = Date.now();
    const lastShown = errorDebounce.get(errorKey) || 0;
    const consecutiveCount = consecutiveErrors.get(errorKey) || 0;
    
    // Increment consecutive error count
    consecutiveErrors.set(errorKey, consecutiveCount + 1);
    
    // Only show user notifications for non-suppressed errors and if not recently shown
    // AND if we haven't hit the consecutive error limit (circuit breaker)
    if (!error.config?.suppressGlobalError && 
        (now - lastShown) > ERROR_DEBOUNCE_TIME &&
        consecutiveCount < MAX_CONSECUTIVE_ERRORS) {
      const message = error.response?.data?.message || error.message;
      
      // Different messages for different error types
      let userMessage = message;
      let shouldShowNotification = true;
      
      if (error.code === 'ECONNREFUSED' || error.code === 'NETWORK_ERROR') {
        userMessage = 'Unable to connect to server. Please check if the backend is running.';
      } else if (error.code === 'ENOTFOUND') {
        userMessage = 'Server not found. Please check your network connection.';
      } else if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
        userMessage = 'Request timeout. The server may be slow or busy.';
        // Don't show timeout notifications as frequently
        shouldShowNotification = (now - lastShown) > (ERROR_DEBOUNCE_TIME * 3); // 30 seconds for timeout errors
      } else if (error.response?.status === 404) {
        userMessage = 'Requested resource not found.';
      } else if (error.response?.status >= 500) {
        userMessage = 'Server error occurred. Please try again later.';
      }
      
      if (shouldShowNotification) {
        errorDebounce.set(errorKey, now);
        
        useNotifications.getState().addNotification({
          type: 'error',
          title: 'Connection Error',
          message: userMessage,
        });
      }
    } else if (consecutiveCount >= MAX_CONSECUTIVE_ERRORS) {
      console.log(`[API CLIENT] 🚫 Circuit breaker activated: suppressing error notification after ${consecutiveCount} consecutive errors for ${errorKey}`);
    }

    // Handle authentication errors
    if (error.response?.status === 401) {
      const searchParams = new URLSearchParams();
      const redirectTo = searchParams.get('redirectTo');
      window.location.href = `/auth/login?redirectTo=${redirectTo}`;
    }

    return Promise.reject(error);
  }
);

// Export utility functions for debugging
export const apiDebug = {
  getBaseURL: () => api.defaults.baseURL,
  testConnection: async () => {
    try {
      const response = await api.get('/health');
      console.log('[API CLIENT] ✅ Connection test successful:', response);
      return { success: true, data: response };
    } catch (error) {
      console.error('[API CLIENT] ❌ Connection test failed:', error);
      return { success: false, error };
    }
  },
  getCurrentConfig: () => ({
    baseURL: api.defaults.baseURL,
    timeout: api.defaults.timeout,
    NODE_ENV: process.env.NODE_ENV,
    REACT_APP_API_URL: process.env.REACT_APP_API_URL,
    REACT_APP_BACKEND_HOST: process.env.REACT_APP_BACKEND_HOST,
    REACT_APP_NETWORK_MODE: process.env.REACT_APP_NETWORK_MODE,
  }),
};

