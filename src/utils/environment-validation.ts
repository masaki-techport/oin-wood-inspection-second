/**
 * Environment validation utilities for network configuration
 */

export interface EnvironmentConfig {
  backendHost: string;
  backendPort: number;
  apiUrl: string;
  networkMode: boolean;
  enableDiagnostics: boolean;
}

export interface ValidationResult {
  isValid: boolean;
  errors: string[];
  warnings: string[];
  config: EnvironmentConfig;
}

/**
 * Validate environment configuration for network access
 */
export function validateEnvironmentConfig(): ValidationResult {
  const errors: string[] = [];
  const warnings: string[] = [];
  
  // Get environment variables
  const backendHost = process.env.REACT_APP_BACKEND_HOST || 'localhost';
  const backendPort = parseInt(process.env.REACT_APP_BACKEND_PORT || '8000');
  const apiUrl = process.env.REACT_APP_API_URL || `http://${backendHost}:${backendPort}`;
  const networkMode = process.env.REACT_APP_NETWORK_MODE === 'true';
  const enableDiagnostics = process.env.REACT_APP_ENABLE_NETWORK_DIAGNOSTICS === 'true';
  
  // Validate backend host
  if (!backendHost) {
    errors.push('REACT_APP_BACKEND_HOST is not defined');
  } else if (backendHost === 'localhost' && networkMode) {
    warnings.push('Network mode is enabled but backend host is localhost - external devices may not be able to connect');
  }
  
  // Validate backend port
  if (isNaN(backendPort) || backendPort < 1 || backendPort > 65535) {
    errors.push('REACT_APP_BACKEND_PORT must be a valid port number (1-65535)');
  }
  
  // Validate API URL
  try {
    const url = new URL(apiUrl);
    if (url.protocol !== 'http:' && url.protocol !== 'https:') {
      errors.push('REACT_APP_API_URL must use http or https protocol');
    }
    if (url.hostname !== backendHost) {
      warnings.push('API URL hostname does not match backend host');
    }
    if (parseInt(url.port || '80') !== backendPort) {
      warnings.push('API URL port does not match backend port');
    }
  } catch (error) {
    errors.push('REACT_APP_API_URL is not a valid URL');
  }
  
  // Network mode validation
  if (networkMode) {
    if (backendHost === 'localhost' || backendHost === '127.0.0.1') {
      warnings.push('Network mode enabled with localhost - consider using actual IP address for external access');
    }
    if (!isPrivateIP(backendHost) && !isLocalhost(backendHost)) {
      warnings.push('Backend host appears to be a public IP - ensure this is intentional');
    }
  }
  
  const config: EnvironmentConfig = {
    backendHost,
    backendPort,
    apiUrl,
    networkMode,
    enableDiagnostics
  };
  
  return {
    isValid: errors.length === 0,
    errors,
    warnings,
    config
  };
}

/**
 * Check if an IP address is in a private network range
 */
function isPrivateIP(ip: string): boolean {
  const privateRanges = [
    /^10\./,
    /^172\.(1[6-9]|2[0-9]|3[0-1])\./,
    /^192\.168\./
  ];
  
  return privateRanges.some(range => range.test(ip));
}

/**
 * Check if an IP address is localhost
 */
function isLocalhost(ip: string): boolean {
  return ip === 'localhost' || ip === '127.0.0.1' || ip === '::1';
}

/**
 * Get network configuration recommendations
 */
export function getNetworkRecommendations(validation: ValidationResult): string[] {
  const recommendations: string[] = [];
  
  if (!validation.config.networkMode) {
    recommendations.push('Enable network mode (REACT_APP_NETWORK_MODE=true) for external device access');
  }
  
  if (validation.config.backendHost === 'localhost' && validation.config.networkMode) {
    recommendations.push('Use actual machine IP address instead of localhost for external access');
  }
  
  if (!validation.config.enableDiagnostics) {
    recommendations.push('Enable network diagnostics (REACT_APP_ENABLE_NETWORK_DIAGNOSTICS=true) for troubleshooting');
  }
  
  if (validation.warnings.length > 0) {
    recommendations.push('Review configuration warnings for potential issues');
  }
  
  return recommendations;
}

/**
 * Test backend connectivity
 */
export async function testBackendConnectivity(config: EnvironmentConfig): Promise<{
  success: boolean;
  error?: string;
  responseTime?: number;
}> {
  try {
    const startTime = Date.now();
    const response = await fetch(`${config.apiUrl}/health`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
      // Add timeout
      signal: AbortSignal.timeout(5000)
    });
    
    const endTime = Date.now();
    const responseTime = endTime - startTime;
    
    if (response.ok) {
      return { success: true, responseTime };
    } else {
      return { 
        success: false, 
        error: `HTTP ${response.status}: ${response.statusText}`,
        responseTime 
      };
    }
  } catch (error) {
    return { 
      success: false, 
      error: error instanceof Error ? error.message : 'Unknown error' 
    };
  }
}

/**
 * Log environment configuration for debugging
 */
export function logEnvironmentConfig(): void {
  const validation = validateEnvironmentConfig();
  
  console.group('🔧 Environment Configuration');
  console.log('Backend Host:', validation.config.backendHost);
  console.log('Backend Port:', validation.config.backendPort);
  console.log('API URL:', validation.config.apiUrl);
  console.log('Network Mode:', validation.config.networkMode ? 'ENABLED' : 'DISABLED');
  console.log('Diagnostics:', validation.config.enableDiagnostics ? 'ENABLED' : 'DISABLED');
  
  if (validation.errors.length > 0) {
    console.group('❌ Configuration Errors');
    validation.errors.forEach(error => console.error(error));
    console.groupEnd();
  }
  
  if (validation.warnings.length > 0) {
    console.group('⚠️ Configuration Warnings');
    validation.warnings.forEach(warning => console.warn(warning));
    console.groupEnd();
  }
  
  const recommendations = getNetworkRecommendations(validation);
  if (recommendations.length > 0) {
    console.group('💡 Recommendations');
    recommendations.forEach(rec => console.info(rec));
    console.groupEnd();
  }
  
  console.groupEnd();
}

/**
 * Initialize environment validation on app startup
 */
export function initializeEnvironmentValidation(): ValidationResult {
  const validation = validateEnvironmentConfig();
  
  // Log configuration in development
  if (process.env.NODE_ENV === 'development') {
    logEnvironmentConfig();
  }
  
  // Test connectivity if diagnostics are enabled
  if (validation.config.enableDiagnostics && validation.isValid) {
    testBackendConnectivity(validation.config).then(result => {
      if (result.success) {
        console.log(`✅ Backend connectivity test successful (${result.responseTime}ms)`);
      } else {
        console.error(`❌ Backend connectivity test failed: ${result.error}`);
      }
    });
  }
  
  return validation;
}
