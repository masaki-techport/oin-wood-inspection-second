import React, { Component, ErrorInfo, ReactNode } from 'react';
import { useNotifications } from '@/components/ui/notifications';

interface Props {
  children: ReactNode;
  dataSource: string;
  onDataConflict?: (error: Error, dataSource: string) => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
  dataSource: string;
  retryCount: number;
}

/**
 * Specialized Error Boundary for Data Conflicts
 * 
 * Catches errors specifically related to data source conflicts
 * and provides specialized handling and recovery.
 */
class DataConflictErrorBoundary extends Component<Props, State> {
  private maxRetries = 3;
  private retryTimeoutId: number | null = null;

  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      dataSource: props.dataSource,
      retryCount: 0
    };
  }

  static getDerivedStateFromError(error: Error): Partial<State> | null {
    // Check if this is a data conflict error
    const isDataConflict = error.message.includes('data conflict') || 
                          error.message.includes('conflicting data') ||
                          error.message.includes('race condition') ||
                          error.message.includes('inconsistent state');

    if (isDataConflict) {
      return {
        hasError: true,
        error,
        retryCount: 0
      };
    }

    // Let other error boundaries handle non-data conflict errors
    return null;
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error(`DataConflictErrorBoundary caught error in ${this.props.dataSource}:`, error, errorInfo);
    
    this.setState({
      error,
      dataSource: this.props.dataSource
    });

    // Call custom data conflict handler
    if (this.props.onDataConflict) {
      this.props.onDataConflict(error, this.props.dataSource);
    }

    // Log data conflict to monitoring service
    this.logDataConflict(error, errorInfo);
  }

  componentDidUpdate(prevProps: Props) {
    // Reset error boundary when data source changes
    if (this.state.hasError && prevProps.dataSource !== this.props.dataSource) {
      this.resetErrorBoundary();
    }
  }

  componentWillUnmount() {
    if (this.retryTimeoutId) {
      clearTimeout(this.retryTimeoutId);
    }
  }

  private logDataConflict = (error: Error, errorInfo: ErrorInfo) => {
    const conflictReport = {
      dataSource: this.props.dataSource,
      errorMessage: error.message,
      stack: error.stack,
      componentStack: errorInfo.componentStack,
      timestamp: new Date().toISOString(),
      retryCount: this.state.retryCount,
      userAgent: navigator.userAgent,
      url: window.location.href
    };

    console.error('Data Conflict Report:', conflictReport);
    
    // Send to monitoring service
    // Example: Sentry.captureException(error, { 
    //   tags: { dataSource: this.props.dataSource, errorType: 'data_conflict' },
    //   extra: conflictReport 
    // });
  };

  private resetErrorBoundary = () => {
    if (this.retryTimeoutId) {
      clearTimeout(this.retryTimeoutId);
    }

    this.setState({
      hasError: false,
      error: null,
      retryCount: 0
    });
  };

  private handleRetry = () => {
    const { retryCount } = this.state;
    
    if (retryCount < this.maxRetries) {
      console.log(`Retrying data source ${this.props.dataSource} (attempt ${retryCount + 1}/${this.maxRetries})`);
      
      this.setState(prevState => ({
        retryCount: prevState.retryCount + 1
      }));

      // Reset error boundary after a short delay
      this.retryTimeoutId = window.setTimeout(() => {
        this.resetErrorBoundary();
      }, 1000);
    } else {
      console.error(`Max retries exceeded for data source ${this.props.dataSource}`);
      this.resetErrorBoundary();
    }
  };

  private handleForceReset = () => {
    console.log(`Force resetting data source ${this.props.dataSource}`);
    this.resetErrorBoundary();
  };

  private handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      const { retryCount } = this.state;
      const canRetry = retryCount < this.maxRetries;

      return (
        <div className="min-h-screen flex items-center justify-center bg-gray-100">
          <div className="max-w-lg w-full bg-white shadow-lg rounded-lg p-6">
            <div className="flex items-center mb-4">
              <div className="flex-shrink-0">
                <svg className="h-8 w-8 text-orange-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
                </svg>
              </div>
              <div className="ml-3">
                <h3 className="text-lg font-medium text-gray-900">
                  データ競合エラー
                </h3>
                <p className="text-sm text-gray-500">
                  データソース: {this.props.dataSource}
                </p>
              </div>
            </div>

            <div className="mb-4">
              <p className="text-sm text-gray-600">
                データソース間で競合が発生しました。システムは自動的に復旧を試みます。
              </p>
              {retryCount > 0 && (
                <p className="text-sm text-orange-600 mt-2">
                  再試行回数: {retryCount}/{this.maxRetries}
                </p>
              )}
            </div>

            {process.env.NODE_ENV === 'development' && this.state.error && (
              <div className="mb-4 p-3 bg-orange-50 border border-orange-200 rounded-md">
                <h4 className="text-sm font-medium text-orange-800 mb-2">データ競合詳細:</h4>
                <pre className="text-xs text-orange-700 whitespace-pre-wrap overflow-auto max-h-32">
                  {this.state.error.message}
                </pre>
              </div>
            )}

            <div className="flex space-x-3">
              {canRetry && (
                <button
                  onClick={this.handleRetry}
                  className="flex-1 bg-orange-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-orange-700 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:ring-offset-2"
                >
                  再試行 ({retryCount + 1}/{this.maxRetries})
                </button>
              )}
              <button
                onClick={this.handleForceReset}
                className="flex-1 bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
              >
                強制リセット
              </button>
              <button
                onClick={this.handleReload}
                className="flex-1 bg-gray-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2"
              >
                ページ再読み込み
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default DataConflictErrorBoundary;
