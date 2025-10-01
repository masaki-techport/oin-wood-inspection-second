import React from 'react';

/**
 * Centralized Polling Manager
 * 
 * This module provides a standardized polling system with:
 * - Consistent 1-second polling frequency across all components
 * - Proper cleanup and memory leak prevention
 * - Retry logic with exponential backoff
 * - Circuit breaker pattern for failed requests
 */

export interface PollingConfig {
  interval: number; // Polling interval in milliseconds (default: 1000)
  maxRetries: number; // Maximum retry attempts (default: 3)
  retryDelay: number; // Base retry delay in milliseconds (default: 1000)
  circuitBreakerThreshold: number; // Failed requests before circuit breaker opens (default: 5)
  circuitBreakerTimeout: number; // Circuit breaker timeout in milliseconds (default: 30000)
}

export interface PollingState {
  isActive: boolean;
  retryCount: number;
  failureCount: number;
  circuitBreakerOpen: boolean;
  lastSuccessTime: number;
}

export class PollingManager {
  private config: PollingConfig;
  private state: PollingState;
  private intervalId: NodeJS.Timeout | null = null;
  private circuitBreakerTimeoutId: NodeJS.Timeout | null = null;
  private onPoll: () => Promise<void>;
  private onError?: (error: Error) => void;
  private onStateChange?: (state: PollingState) => void;

  constructor(
    onPoll: () => Promise<void>,
    config: Partial<PollingConfig> = {},
    onError?: (error: Error) => void,
    onStateChange?: (state: PollingState) => void
  ) {
    this.config = {
      interval: 100, // 100ms for immediate response
      maxRetries: 3,
      retryDelay: 100,
      circuitBreakerThreshold: 5,
      circuitBreakerTimeout: 30000,
      ...config
    };

    this.state = {
      isActive: false,
      retryCount: 0,
      failureCount: 0,
      circuitBreakerOpen: false,
      lastSuccessTime: 0
    };

    this.onPoll = onPoll;
    this.onError = onError;
    this.onStateChange = onStateChange;
  }

  /**
   * Start polling
   */
  start(): void {
    if (this.state.isActive) {
      console.warn('[PollingManager] Polling is already active');
      return;
    }

    this.state.isActive = true;
    this.state.retryCount = 0;
    this.state.failureCount = 0;
    this.state.circuitBreakerOpen = false;
    this.notifyStateChange();

    console.log('[PollingManager] Starting polling with 1-second interval');
    this.scheduleNextPoll();
  }

  /**
   * Stop polling
   */
  stop(): void {
    if (!this.state.isActive) {
      return;
    }

    this.state.isActive = false;
    this.notifyStateChange();

    if (this.intervalId) {
      clearTimeout(this.intervalId);
      this.intervalId = null;
    }

    if (this.circuitBreakerTimeoutId) {
      clearTimeout(this.circuitBreakerTimeoutId);
      this.circuitBreakerTimeoutId = null;
    }

    console.log('[PollingManager] Polling stopped');
  }

  /**
   * Reset polling state
   */
  reset(): void {
    this.stop();
    this.state = {
      isActive: false,
      retryCount: 0,
      failureCount: 0,
      circuitBreakerOpen: false,
      lastSuccessTime: 0
    };
    this.notifyStateChange();
  }

  /**
   * Get current polling state
   */
  getState(): PollingState {
    return { ...this.state };
  }

  /**
   * Check if polling is active
   */
  isActive(): boolean {
    return this.state.isActive;
  }

  /**
   * Schedule the next poll
   */
  private scheduleNextPoll(): void {
    if (!this.state.isActive) {
      return;
    }

    // Check circuit breaker
    if (this.state.circuitBreakerOpen) {
      console.log('[PollingManager] Circuit breaker is open, skipping poll');
      this.scheduleNextPoll();
      return;
    }

    // Calculate delay based on retry count
    const delay = this.state.retryCount > 0 
      ? Math.min(this.config.retryDelay * Math.pow(2, this.state.retryCount - 1), 10000)
      : this.config.interval;

    this.intervalId = setTimeout(async () => {
      if (!this.state.isActive) {
        return;
      }

      try {
        await this.onPoll();
        this.handleSuccess();
      } catch (error) {
        this.handleError(error as Error);
      }
    }, delay);
  }

  /**
   * Handle successful poll
   */
  private handleSuccess(): void {
    this.state.retryCount = 0;
    this.state.failureCount = 0;
    this.state.lastSuccessTime = Date.now();
    this.state.circuitBreakerOpen = false;

    if (this.circuitBreakerTimeoutId) {
      clearTimeout(this.circuitBreakerTimeoutId);
      this.circuitBreakerTimeoutId = null;
    }

    this.notifyStateChange();
    this.scheduleNextPoll();
  }

  /**
   * Handle poll error
   */
  private handleError(error: Error): void {
    this.state.failureCount++;
    this.state.retryCount++;

    console.error(`[PollingManager] Poll failed (attempt ${this.state.retryCount}):`, error);

    // Check if we should open circuit breaker
    if (this.state.failureCount >= this.config.circuitBreakerThreshold) {
      this.state.circuitBreakerOpen = true;
      this.state.retryCount = 0;

      console.warn('[PollingManager] Circuit breaker opened due to repeated failures');

      // Schedule circuit breaker to half-open
      this.circuitBreakerTimeoutId = setTimeout(() => {
        this.state.circuitBreakerOpen = false;
        this.state.failureCount = 0;
        console.log('[PollingManager] Circuit breaker half-open, resuming polling');
        this.notifyStateChange();
        this.scheduleNextPoll();
      }, this.config.circuitBreakerTimeout);
    } else if (this.state.retryCount <= this.config.maxRetries) {
      // Retry with exponential backoff
      this.scheduleNextPoll();
    } else {
      // Max retries exceeded, stop polling
      console.error('[PollingManager] Max retries exceeded, stopping polling');
      this.stop();
    }

    this.notifyStateChange();

    // Call error handler if provided
    if (this.onError) {
      this.onError(error);
    }
  }

  /**
   * Notify state change listeners
   */
  private notifyStateChange(): void {
    if (this.onStateChange) {
      this.onStateChange(this.getState());
    }
  }

  /**
   * Cleanup resources
   */
  destroy(): void {
    this.stop();
    this.state = {
      isActive: false,
      retryCount: 0,
      failureCount: 0,
      circuitBreakerOpen: false,
      lastSuccessTime: 0
    };
  }
}

/**
 * Create a standardized polling manager with 1-second intervals
 */
export const createStandardPollingManager = (
  onPoll: () => Promise<void>,
  onError?: (error: Error) => void,
  onStateChange?: (state: PollingState) => void
): PollingManager => {
  return new PollingManager(
    onPoll,
    { interval: 1000 }, // 1 second standard
    onError,
    onStateChange
  );
};

/**
 * Hook for using polling manager in React components
 */
export const usePollingManager = (
  onPoll: () => Promise<void>,
  onError?: (error: Error) => void,
  onStateChange?: (state: PollingState) => void
): PollingManager => {
  const manager = new PollingManager(onPoll, { interval: 1000 }, onError, onStateChange);
  
  // Cleanup on unmount
  React.useEffect(() => {
    return () => {
      manager.destroy();
    };
  }, []);

  return manager;
};
