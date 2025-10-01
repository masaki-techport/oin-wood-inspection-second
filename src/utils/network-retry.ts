/**
 * Network retry mechanisms and fallback configurations for frontend
 */

export interface RetryConfig {
  maxRetries: number;
  baseDelay: number;
  maxDelay: number;
  backoffFactor: number;
  retryCondition?: (error: any) => boolean;
}

export interface FallbackConfig {
  primaryHost: string;
  fallbackHosts: string[];
  healthCheckPath: string;
  switchThreshold: number; // Number of consecutive failures before switching
}

export class NetworkRetryManager {
  private retryConfig: RetryConfig;
  private fallbackConfig: FallbackConfig;
  private currentHostIndex: number = 0;
  private consecutiveFailures: number = 0;
  private hostHealthStatus: Map<string, boolean> = new Map();

  constructor(retryConfig?: Partial<RetryConfig>, fallbackConfig?: Partial<FallbackConfig>) {
    this.retryConfig = {
      maxRetries: 3,
      baseDelay: 1000,
      maxDelay: 10000,
      backoffFactor: 2,
      retryCondition: this.defaultRetryCondition,
      ...retryConfig
    };

    this.fallbackConfig = {
      primaryHost: process.env.REACT_APP_BACKEND_HOST || 'localhost',
      fallbackHosts: ['localhost', '127.0.0.1'],
      healthCheckPath: '/health',
      switchThreshold: 3,
      ...fallbackConfig
    };

    // Initialize host health status
    this.updateHostHealthStatus();
  }

  /**
   * Execute a network request with retry logic and fallback hosts
   */
  async executeWithRetry<T>(
    requestFn: (baseUrl: string) => Promise<T>,
    options?: Partial<RetryConfig>
  ): Promise<T> {
    const config = { ...this.retryConfig, ...options };
    let lastError: any;

    // Try current host first, then fallbacks
    const hostsToTry = this.getHostsInOrder();

    for (const host of hostsToTry) {
      const baseUrl = this.buildBaseUrl(host);
      
      try {
        // Attempt request with retries for this host
        const result = await this.retryRequest(requestFn, baseUrl, config);
        
        // Success - update health status and reset failure count
        this.hostHealthStatus.set(host, true);
        this.consecutiveFailures = 0;
        
        // If we succeeded with a fallback host, consider switching
        if (host !== this.getCurrentHost()) {
          await this.considerHostSwitch(host);
        }
        
        return result;
        
      } catch (error) {
        lastError = error;
        this.hostHealthStatus.set(host, false);
        console.warn(`Request failed for host ${host}:`, error);
      }
    }

    // All hosts failed
    this.consecutiveFailures++;
    throw lastError || new Error('All hosts failed');
  }

  /**
   * Retry a request for a specific host
   */
  private async retryRequest<T>(
    requestFn: (baseUrl: string) => Promise<T>,
    baseUrl: string,
    config: RetryConfig
  ): Promise<T> {
    let lastError: any;

    for (let attempt = 0; attempt <= config.maxRetries; attempt++) {
      try {
        return await requestFn(baseUrl);
      } catch (error) {
        lastError = error;

        // Check if we should retry
        if (attempt === config.maxRetries || !config.retryCondition!(error)) {
          throw error;
        }

        // Calculate delay with exponential backoff
        const delay = Math.min(
          config.baseDelay * Math.pow(config.backoffFactor, attempt),
          config.maxDelay
        );

        console.log(`Request attempt ${attempt + 1} failed, retrying in ${delay}ms...`);
        await this.sleep(delay);
      }
    }

    throw lastError;
  }

  /**
   * Default retry condition - retry on network errors but not on 4xx client errors
   */
  private defaultRetryCondition(error: any): boolean {
    // Don't retry on client errors (4xx)
    if (error.response && error.response.status >= 400 && error.response.status < 500) {
      return false;
    }

    // Retry on network errors, timeouts, and server errors
    return (
      !error.response || // Network error
      error.code === 'ECONNREFUSED' ||
      error.code === 'ENOTFOUND' ||
      error.code === 'ETIMEDOUT' ||
      (error.response && error.response.status >= 500) // Server error
    );
  }

  /**
   * Get hosts in order of preference
   */
  private getHostsInOrder(): string[] {
    const currentHost = this.getCurrentHost();
    const allHosts = [this.fallbackConfig.primaryHost, ...this.fallbackConfig.fallbackHosts];
    
    // Remove duplicates and put current host first
    const uniqueHosts = Array.from(new Set(allHosts));
    const otherHosts = uniqueHosts.filter(host => host !== currentHost);
    
    return [currentHost, ...otherHosts];
  }

  /**
   * Get current active host
   */
  private getCurrentHost(): string {
    const allHosts = [this.fallbackConfig.primaryHost, ...this.fallbackConfig.fallbackHosts];
    return allHosts[this.currentHostIndex] || this.fallbackConfig.primaryHost;
  }

  /**
   * Build base URL for a host
   */
  private buildBaseUrl(host: string): string {
    const port = process.env.REACT_APP_BACKEND_PORT || '8000';
    return `http://${host}:${port}`;
  }

  /**
   * Consider switching to a different host if current one is failing
   */
  private async considerHostSwitch(successfulHost: string): Promise<void> {
    if (this.consecutiveFailures >= this.fallbackConfig.switchThreshold) {
      console.log(`Switching to host ${successfulHost} due to ${this.consecutiveFailures} consecutive failures`);
      
      const allHosts = [this.fallbackConfig.primaryHost, ...this.fallbackConfig.fallbackHosts];
      const newIndex = allHosts.indexOf(successfulHost);
      
      if (newIndex !== -1) {
        this.currentHostIndex = newIndex;
        this.consecutiveFailures = 0;
      }
    }
  }

  /**
   * Update host health status by checking health endpoints
   */
  private async updateHostHealthStatus(): Promise<void> {
    const allHosts = [this.fallbackConfig.primaryHost, ...this.fallbackConfig.fallbackHosts];

    for (const host of allHosts) {
      try {
        const baseUrl = this.buildBaseUrl(host);

        // Create AbortController for timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000);

        const response = await fetch(`${baseUrl}${this.fallbackConfig.healthCheckPath}`, {
          method: 'GET',
          signal: controller.signal
        });

        clearTimeout(timeoutId);
        this.hostHealthStatus.set(host, response.ok);
      } catch (error) {
        this.hostHealthStatus.set(host, false);
      }
    }
  }

  /**
   * Get current network status
   */
  getNetworkStatus(): {
    currentHost: string;
    consecutiveFailures: number;
    hostHealth: Record<string, boolean>;
    recommendedAction?: string;
  } {
    const hostHealth: Record<string, boolean> = {};
    this.hostHealthStatus.forEach((health, host) => {
      hostHealth[host] = health;
    });

    let recommendedAction: string | undefined;
    if (this.consecutiveFailures >= this.fallbackConfig.switchThreshold) {
      recommendedAction = 'Consider checking network connectivity or server status';
    }

    return {
      currentHost: this.getCurrentHost(),
      consecutiveFailures: this.consecutiveFailures,
      hostHealth,
      recommendedAction
    };
  }

  /**
   * Manually switch to a specific host
   */
  switchToHost(host: string): boolean {
    const allHosts = [this.fallbackConfig.primaryHost, ...this.fallbackConfig.fallbackHosts];
    const index = allHosts.indexOf(host);
    
    if (index !== -1) {
      this.currentHostIndex = index;
      this.consecutiveFailures = 0;
      console.log(`Manually switched to host: ${host}`);
      return true;
    }
    
    return false;
  }

  /**
   * Reset to primary host
   */
  resetToPrimaryHost(): void {
    this.currentHostIndex = 0;
    this.consecutiveFailures = 0;
    console.log(`Reset to primary host: ${this.fallbackConfig.primaryHost}`);
  }

  /**
   * Sleep utility
   */
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

/**
 * Create a fetch wrapper with retry and fallback logic
 */
export function createRetryFetch(retryManager: NetworkRetryManager) {
  return async function retryFetch(
    path: string,
    options?: RequestInit & { timeout?: number }
  ): Promise<Response> {
    return retryManager.executeWithRetry(async (baseUrl: string) => {
      const url = `${baseUrl}${path}`;

      // Handle timeout if specified
      let controller: AbortController | undefined;
      let timeoutId: NodeJS.Timeout | undefined;

      if (options?.timeout) {
        controller = new AbortController();
        timeoutId = setTimeout(() => controller!.abort(), options.timeout);
      }

      try {
        const fetchOptions: RequestInit = {
          ...options,
          signal: controller?.signal || options?.signal
        };

        // Remove timeout from options as it's not a valid RequestInit property
        if ('timeout' in fetchOptions) {
          delete (fetchOptions as any).timeout;
        }

        const response = await fetch(url, fetchOptions);

        if (timeoutId) {
          clearTimeout(timeoutId);
        }

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        return response;
      } catch (error) {
        if (timeoutId) {
          clearTimeout(timeoutId);
        }
        throw error;
      }
    });
  };
}

/**
 * Global retry manager instance
 */
export const globalRetryManager = new NetworkRetryManager();

/**
 * Global retry fetch function
 */
export const retryFetch = createRetryFetch(globalRetryManager);
