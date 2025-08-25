/**
 * Centralized API configuration utility
 * Ensures consistent backend URL usage across the application
 */

export interface ApiConfig {
  baseUrl: string;
  host: string;
  port: number;
  protocol: string;
  isNetworkMode: boolean;
}

/**
 * Get the main API configuration from environment variables
 */
export const getApiConfig = (): ApiConfig => {
  // Check if we have a full API URL first
  const apiUrl = process.env.REACT_APP_API_URL;
  
  if (apiUrl) {
    try {
      const url = new URL(apiUrl);
      return {
        baseUrl: apiUrl,
        host: url.hostname,
        port: parseInt(url.port) || (url.protocol === 'https:' ? 443 : 80),
        protocol: url.protocol.replace(':', ''),
        isNetworkMode: url.hostname !== 'localhost' && url.hostname !== '127.0.0.1'
      };
    } catch (error) {
      console.warn('Invalid REACT_APP_API_URL, falling back to host/port configuration:', error);
    }
  }

  // Fall back to individual host/port configuration
  const host = process.env.REACT_APP_BACKEND_HOST || 'localhost';
  const port = parseInt(process.env.REACT_APP_BACKEND_PORT || '8000');
  const protocol = 'http';
  
  return {
    baseUrl: `${protocol}://${host}:${port}`,
    host,
    port,
    protocol,
    isNetworkMode: host !== 'localhost' && host !== '127.0.0.1'
  };
};

/**
 * Get camera-specific API configuration
 * Uses the same configuration as the main API to ensure consistency
 */
export const getCameraApiConfig = (): ApiConfig => {
  return getApiConfig();
};

/**
 * Validate that the API configuration is properly set up
 */
export const validateApiConfig = (): { isValid: boolean; warnings: string[] } => {
  const config = getApiConfig();
  const warnings: string[] = [];

  // Check if environment variables are set
  if (!process.env.REACT_APP_API_URL && !process.env.REACT_APP_BACKEND_HOST) {
    warnings.push('No backend configuration found in environment variables, using localhost default');
  }

  // Check if network mode is properly configured
  if (config.isNetworkMode) {
    if (!process.env.REACT_APP_API_URL && !process.env.REACT_APP_BACKEND_HOST) {
      warnings.push('Network mode detected but no explicit backend host configured');
    }
  }

  // Validate port number
  if (isNaN(config.port) || config.port < 1 || config.port > 65535) {
    warnings.push(`Invalid port number: ${config.port}`);
    return { isValid: false, warnings };
  }

  return { isValid: true, warnings };
};

/**
 * Log current API configuration for debugging
 */
export const logApiConfig = (): void => {
  const config = getApiConfig();
  const validation = validateApiConfig();
  
  console.log('[API Config] Current configuration:', {
    baseUrl: config.baseUrl,
    host: config.host,
    port: config.port,
    isNetworkMode: config.isNetworkMode,
    isValid: validation.isValid,
    warnings: validation.warnings
  });
  
  if (validation.warnings.length > 0) {
    validation.warnings.forEach(warning => console.warn('[API Config]', warning));
  }
};