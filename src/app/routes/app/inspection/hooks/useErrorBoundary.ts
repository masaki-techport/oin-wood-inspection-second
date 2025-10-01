import { useState, useCallback, useRef, useEffect } from 'react';
import { useNotifications } from '@/components/ui/notifications';

export interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorId: string;
  retryCount: number;
  lastErrorTime: number;
}

export interface ErrorBoundaryActions {
  resetError: () => void;
  reportError: (error: Error, errorInfo?: any) => void;
  retry: () => void;
}

/**
 * Hook for managing error boundary state and actions
 */
export const useErrorBoundary = (maxRetries: number = 3) => {
  const { addNotification } = useNotifications();
  const [state, setState] = useState<ErrorBoundaryState>({
    hasError: false,
    error: null,
    errorId: '',
    retryCount: 0,
    lastErrorTime: 0
  });

  const retryTimeoutRef = useRef<number | null>(null);
  const errorHistoryRef = useRef<Error[]>([]);

  const resetError = useCallback(() => {
    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current);
    }

    setState({
      hasError: false,
      error: null,
      errorId: '',
      retryCount: 0,
      lastErrorTime: 0
    });
  }, []);

  const reportError = useCallback((error: Error, errorInfo?: any) => {
    const errorId = `error_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    console.error('Error reported to useErrorBoundary:', error, errorInfo);
    
    // Add to error history
    errorHistoryRef.current.push(error);
    if (errorHistoryRef.current.length > 10) {
      errorHistoryRef.current.shift(); // Keep only last 10 errors
    }

    setState({
      hasError: true,
      error,
      errorId,
      retryCount: 0,
      lastErrorTime: Date.now()
    });

    // Show notification
    addNotification({
      type: 'error',
      title: 'システムエラー',
      message: `エラーが発生しました (ID: ${errorId})`
    });
  }, [addNotification]);

  const retry = useCallback(() => {
    const { retryCount } = state;
    
    if (retryCount < maxRetries) {
      console.log(`Retrying error boundary (attempt ${retryCount + 1}/${maxRetries})`);
      
      setState(prevState => ({
        ...prevState,
        retryCount: prevState.retryCount + 1
      }));

      // Reset after a short delay
      retryTimeoutRef.current = window.setTimeout(() => {
        resetError();
      }, 1000);
    } else {
      console.error('Max retries exceeded for error boundary');
      resetError();
    }
  }, [state.retryCount, maxRetries, resetError]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current);
      }
    };
  }, []);

  return {
    state,
    actions: {
      resetError,
      reportError,
      retry
    },
    errorHistory: errorHistoryRef.current
  };
};

/**
 * Hook for detecting and handling data conflicts
 */
export const useDataConflictDetection = () => {
  const { addNotification } = useNotifications();
  const [conflicts, setConflicts] = useState<Array<{
    id: string;
    dataSource: string;
    timestamp: number;
    resolved: boolean;
  }>>([]);

  const detectConflict = useCallback((dataSource: string, error: Error) => {
    const conflictId = `conflict_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    console.warn(`Data conflict detected in ${dataSource}:`, error);
    
    const newConflict = {
      id: conflictId,
      dataSource,
      timestamp: Date.now(),
      resolved: false
    };

    setConflicts(prev => [...prev, newConflict]);

    addNotification({
      type: 'warning',
      title: 'データ競合検出',
      message: `${dataSource}でデータ競合が発生しました`
    });

    return conflictId;
  }, [addNotification]);

  const resolveConflict = useCallback((conflictId: string) => {
    setConflicts(prev => 
      prev.map(conflict => 
        conflict.id === conflictId 
          ? { ...conflict, resolved: true }
          : conflict
      )
    );
  }, []);

  const clearResolvedConflicts = useCallback(() => {
    setConflicts(prev => prev.filter(conflict => !conflict.resolved));
  }, []);

  return {
    conflicts,
    detectConflict,
    resolveConflict,
    clearResolvedConflicts
  };
};

/**
 * Hook for monitoring system health
 */
export const useSystemHealth = () => {
  const [health, setHealth] = useState({
    status: 'healthy' as 'healthy' | 'degraded' | 'unhealthy',
    lastCheck: Date.now(),
    errorRate: 0,
    dataConflicts: 0
  });

  const updateHealth = useCallback((status: 'healthy' | 'degraded' | 'unhealthy', errorRate?: number, dataConflicts?: number) => {
    setHealth(prev => ({
      ...prev,
      status,
      lastCheck: Date.now(),
      errorRate: errorRate ?? prev.errorRate,
      dataConflicts: dataConflicts ?? prev.dataConflicts
    }));
  }, []);

  const checkHealth = useCallback(() => {
    // In a real application, this would check various system metrics
    const now = Date.now();
    const timeSinceLastCheck = now - health.lastCheck;
    
    // Simple health check - in reality you'd check API responses, memory usage, etc.
    if (timeSinceLastCheck > 30000) { // 30 seconds
      updateHealth('degraded');
    } else if (health.errorRate > 0.1) { // 10% error rate
      updateHealth('unhealthy');
    } else {
      updateHealth('healthy');
    }
  }, [health.lastCheck, health.errorRate, updateHealth]);

  return {
    health,
    updateHealth,
    checkHealth
  };
};
