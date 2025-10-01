import React, { useState, useEffect } from 'react';
import { api, apiDebug } from '@/lib/api-client';

interface NetworkStatus {
  isOnline: boolean;
  apiUrl: string;
  lastCheck: Date | null;
  error: string | null;
  responseTime: number | null;
  connectionDetails?: any;
}

export const NetworkStatusIndicator: React.FC = () => {
  const [status, setStatus] = useState<NetworkStatus>({
    isOnline: false,
    apiUrl: '',
    lastCheck: null,
    error: null,
    responseTime: null,
    connectionDetails: null
  });

  const checkConnection = async () => {
    const startTime = Date.now();
    try {
      console.log('[NETWORK STATUS] 🔍 Starting connection check...');
      
      // Get current API configuration
      const config = apiDebug.getCurrentConfig();
      console.log('[NETWORK STATUS] ⚙️ Current config:', config);
      
      // Test connection using the debug utility
      const testResult = await apiDebug.testConnection();
      
      const responseTime = Date.now() - startTime;
      
      if (testResult.success) {
        console.log('[NETWORK STATUS] ✅ Connection successful');
        setStatus({
          isOnline: true,
          apiUrl: config.baseURL || 'unknown',
          lastCheck: new Date(),
          error: null,
          responseTime,
          connectionDetails: {
            config,
            testResult: testResult.data
          }
        });
      } else {
        throw testResult.error;
      }
      
    } catch (error: any) {
      const responseTime = Date.now() - startTime;
      console.error('[NETWORK STATUS] ❌ Connection failed:', error);
      
      // Get detailed error information
      const errorDetails = {
        message: error.message,
        code: error.code,
        status: error.response?.status,
        baseURL: error.config?.baseURL,
        url: error.config?.url,
        fullURL: error.config ? `${error.config.baseURL}${error.config.url}` : 'unknown'
      };
      
      console.log('[NETWORK STATUS] 📊 Error details:', errorDetails);
      
      setStatus({
        isOnline: false,
        apiUrl: apiDebug.getBaseURL() || 'unknown',
        lastCheck: new Date(),
        error: error.message || 'Connection failed',
        responseTime,
        connectionDetails: {
          config: apiDebug.getCurrentConfig(),
          errorDetails
        }
      });
    }
  };

  useEffect(() => {
    console.log('[NETWORK STATUS] 🚀 Component initialized');
    
    // Initial check
    checkConnection();
    
    // Check every 30 seconds
    const interval = setInterval(checkConnection, 30000);
    
    return () => {
      console.log('[NETWORK STATUS] 🛑 Component cleanup');
      clearInterval(interval);
    };
  }, []);

  const getStatusColor = () => {
    if (status.isOnline) return 'bg-green-500';
    return 'bg-red-500';
  };

  const getStatusText = () => {
    if (status.isOnline) return 'Online';
    return 'Offline';
  };

  const handleManualRefresh = () => {
    console.log('[NETWORK STATUS] 🔄 Manual refresh triggered');
    checkConnection();
  };

  return (
    <div className="flex items-center gap-2 text-sm">
      <div className={`w-2 h-2 rounded-full ${getStatusColor()}`} />
      <span className="text-gray-600">{getStatusText()}</span>
      {status.responseTime && (
        <span className="text-gray-500">({status.responseTime}ms)</span>
      )}
      
      {/* Debug Info */}
      {process.env.NODE_ENV === 'development' && (
        <div className="ml-4 text-xs text-gray-400">
          <div>API: {status.apiUrl}</div>
          {status.error && (
            <div className="text-red-500">Error: {status.error}</div>
          )}
          {status.connectionDetails && (
            <details className="mt-1">
              <summary className="cursor-pointer text-blue-500">Debug Info</summary>
              <pre className="mt-1 text-xs bg-gray-100 p-2 rounded max-w-md overflow-auto">
                {JSON.stringify(status.connectionDetails, null, 2)}
              </pre>
            </details>
          )}
        </div>
      )}
      
      <button
        onClick={handleManualRefresh}
        className="ml-2 text-xs text-blue-500 hover:text-blue-700"
        title="Refresh connection status"
      >
        🔄
      </button>
    </div>
  );
};