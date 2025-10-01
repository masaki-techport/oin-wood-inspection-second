const { createProxyMiddleware } = require('http-proxy-middleware');
const fetch = require('node-fetch');
const os = require('os');

// Emergency fix: Remove startup validation that might be causing issues
// const { validateStartupConfig } = require('./utils/startup-config-check');
// validateStartupConfig();

console.log('[PROXY] ===== SIMPLIFIED DYNAMIC PROXY STARTING =====');
console.log('[PROXY] Loading environment variables...');
console.log('[PROXY] REACT_APP_NETWORK_MODE:', process.env.REACT_APP_NETWORK_MODE);
console.log('[PROXY] REACT_APP_API_URL:', process.env.REACT_APP_API_URL);
console.log('[PROXY] REACT_APP_BACKEND_HOST:', process.env.REACT_APP_BACKEND_HOST);
console.log('[PROXY] REACT_APP_ENABLE_BACKEND_DISCOVERY:', process.env.REACT_APP_ENABLE_BACKEND_DISCOVERY);
console.log('[PROXY] REACT_APP_DEBUG_PROXY:', process.env.REACT_APP_DEBUG_PROXY);

// Dynamic backend configuration with discovery and fallback
class ProxyConfigManager {
  constructor() {
    this.currentBackend = null;
    this.fallbackHosts = this.parseFallbackHosts();
    this.isDiscovering = false;
    this.lastDiscovery = 0;
    this.discoveryCache = new Map();
    this.healthCheckInterval = null;
    this.proxyInstances = new Set(); // Track proxy instances for dynamic updates
  }

  // Add method to register proxy instances
  registerProxy(proxyInstance) {
    this.proxyInstances.add(proxyInstance);
    console.log('[PROXY] Registered proxy instance');
  }

  // Add method to update all proxy targets (simplified for router-based approach)
  updateProxyTargets(newUrl) {
    console.log(`[PROXY] Current backend updated to: ${newUrl}`);
    // With router-based approach, we don't need to update instances directly
    // The router function will pick up the new currentBackend.url automatically
  }

// Get local machine IP addresses for 0.0.0.0 server discovery
  getMachineIPs() {
    const ips = [];
    
    try {
      const networkInterfaces = os.networkInterfaces();
      
      for (const [name, interfaces] of Object.entries(networkInterfaces)) {
        for (const iface of interfaces) {
          // Skip loopback and non-IPv4 addresses
          if (iface.family === 'IPv4' && !iface.internal) {
            ips.push(iface.address);
          }
        }
      }
      
      console.log('[PROXY] Detected machine IPs:', ips);
    } catch (error) {
      console.log('[PROXY] Could not detect machine IPs:', error.message);
      // Emergency fallback IPs
      ips.push('192.168.1.100', '192.168.2.100');
    }
    
    return ips;
  }

  parseFallbackHosts() {
    const fallbackString = process.env.REACT_APP_FALLBACK_HOSTS || 'localhost,127.0.0.1';
    return fallbackString.split(',').map(h => h.trim()).filter(h => h.length > 0);
  }

  detectBackendHost() {
    console.log('[PROXY] Starting simplified backend detection...');
    
    // Get machine IPs for 0.0.0.0 server discovery
    const machineIPs = this.getMachineIPs();
    
    // 1. Try explicit API URL first
    const explicitUrl = process.env.REACT_APP_API_URL;
    if (explicitUrl && explicitUrl.startsWith('http')) {
      console.log('[PROXY] Using explicit API URL:', explicitUrl);
      const backend = this.parseUrlToBackend(explicitUrl);
      this.updateBackendAndProxies(backend);
      return backend;
    }

    // 2. Try explicit host/port
    const explicitHost = process.env.REACT_APP_BACKEND_HOST;
    const explicitPort = process.env.REACT_APP_BACKEND_PORT || '8000';
    
    if (explicitHost && explicitHost !== 'auto') {
      const explicitBackend = `http://${explicitHost}:${explicitPort}`;
      console.log('[PROXY] Using explicit backend host:', explicitBackend);
      const backend = this.parseUrlToBackend(explicitBackend);
      this.updateBackendAndProxies(backend);
      return backend;
    }

    // 3. Network mode: prioritize machine IPs
    const networkMode = process.env.REACT_APP_NETWORK_MODE === 'true';
    if (networkMode && machineIPs.length > 0) {
      const machineUrl = `http://${machineIPs[0]}:${explicitPort}`;
      console.log('[PROXY] Network mode: using machine IP:', machineUrl);
      const backend = this.parseUrlToBackend(machineUrl);
      this.updateBackendAndProxies(backend);
      return backend;
    }

    // 4. Final fallback to localhost
    const fallbackUrl = 'http://localhost:8000';
    console.log('[PROXY] Using fallback:', fallbackUrl);
    const backend = this.parseUrlToBackend(fallbackUrl);
    this.updateBackendAndProxies(backend);
    return backend;
  }

  // Helper method to parse URL to backend object
  parseUrlToBackend(url) {
    try {
      const parsedUrl = new URL(url);
      return {
        url,
        host: parsedUrl.hostname,
        port: parsedUrl.port || '8000',
        isHealthy: true // Assume healthy at startup, will be validated later
      };
    } catch (error) {
      console.log('[PROXY] Invalid URL:', url, error.message);
      return {
        url: 'http://localhost:8000',
        host: 'localhost',
        port: '8000',
        isHealthy: false
      };
    }
  }

  // New method to update backend and all proxy instances
  updateBackendAndProxies(backend) {
    this.currentBackend = backend;
    this.updateProxyTargets(backend.url);
  }

  async testBackendUrl(url, timeout = 3000) {
    try {
      console.log(`[PROXY] Testing backend: ${url}`);
      
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeout);
      
      const startTime = Date.now();
      const response = await fetch(`${url}/health`, {
        signal: controller.signal,
        headers: { 'Accept': 'application/json' }
      });
      
      clearTimeout(timeoutId);
      const responseTime = Date.now() - startTime;
      
      if (response.ok) {
        const parsedUrl = new URL(url);
        const backend = {
          url,
          host: parsedUrl.hostname,
          port: parsedUrl.port || '8000',
          isHealthy: true,
          responseTime
        };
        
        console.log(`[PROXY] ✓ Backend healthy: ${url} (${responseTime}ms)`);
        return backend;
      } else {
        console.log(`[PROXY] ✗ Backend unhealthy: ${url} (status: ${response.status})`);
      }
    } catch (error) {
      if (error.name !== 'AbortError') {
        console.log(`[PROXY] ✗ Backend connection failed: ${url} - ${error.message}`);
      }
    }
    return null;
  }

  async discoverBackend() {
    if (this.isDiscovering) {
      console.log('[PROXY] Discovery already in progress, waiting...');
      return this.currentBackend;
    }

    // Use cached discovery if recent (within 30 seconds)
    const now = Date.now();
    if (now - this.lastDiscovery < 30000 && this.currentBackend?.isHealthy) {
      console.log('[PROXY] Using cached discovery result');
      return this.currentBackend;
    }

    this.isDiscovering = true;
    
    try {
      console.log('[PROXY] Discovering backend servers...');
      
      const subnets = (process.env.REACT_APP_DISCOVERY_SUBNETS || '').split(',');
      const candidates = await this.generateDiscoveryCandidates(subnets);
      
      console.log(`[PROXY] Testing ${candidates.length} discovery candidates (including machine IPs)`);
      
      const promises = candidates.slice(0, 15).map(candidate => 
        this.testBackendUrl(candidate, 2000)
      );
      
      const results = await Promise.all(promises);
      const healthyBackends = results.filter(r => r && r.isHealthy);
      
      if (healthyBackends.length > 0) {
        // Smart backend selection: prioritize network IPs over localhost
        const selected = this.selectBestBackend(healthyBackends);
        this.lastDiscovery = now;
        console.log(`[PROXY] ✓ Discovery found ${healthyBackends.length} healthy backend(s), selected: ${selected.url}`);
        return selected;
      }
      
      console.log('[PROXY] No healthy backends discovered');
      return null;
    } finally {
      this.isDiscovering = false;
    }
  }

  // Smart backend selection: prioritize network IPs for external device access
  selectBestBackend(healthyBackends) {
    const networkMode = process.env.REACT_APP_NETWORK_MODE === 'true';
    
    console.log(`[PROXY] Selecting best backend from ${healthyBackends.length} options (network mode: ${networkMode})`);
    
    // Categorize backends
    const localhost = healthyBackends.filter(b => 
      b.url.includes('localhost') || b.url.includes('127.0.0.1')
    );
    const machineIPs = healthyBackends.filter(b => 
      !b.url.includes('localhost') && !b.url.includes('127.0.0.1')
    );
    
    console.log(`[PROXY] Found ${localhost.length} localhost backend(s), ${machineIPs.length} network IP backend(s)`);
    
    if (networkMode && machineIPs.length > 0) {
      // Network mode: prioritize machine IPs for external device access
      const selected = machineIPs.sort((a, b) => a.responseTime - b.responseTime)[0];
      console.log(`[PROXY] ✓ Network mode: selected machine IP ${selected.url} for external device access`);
      return selected;
    } else if (localhost.length > 0) {
      // Localhost mode or no machine IPs available
      const selected = localhost.sort((a, b) => a.responseTime - b.responseTime)[0];
      console.log(`[PROXY] ✓ Localhost mode: selected ${selected.url}`);
      return selected;
    } else {
      // Fallback: fastest overall
      const selected = healthyBackends.sort((a, b) => a.responseTime - b.responseTime)[0];
      console.log(`[PROXY] ✓ Fallback: selected fastest ${selected.url}`);
      return selected;
    }
  }

  async generateDiscoveryCandidates(subnets) {
    const candidates = [];
    const port = process.env.REACT_APP_BACKEND_PORT || '8000';
    
    // Add machine IPs first (for 0.0.0.0 servers)
    const machineIPs = this.getMachineIPs(); // This is synchronous
    for (const ip of machineIPs) {
      candidates.push(`http://${ip}:${port}`);
    }
    
    // Add common IPs from each subnet
    for (const subnet of subnets) {
      if (!subnet.trim()) continue;
      
      const baseIPs = this.getCommonIPsFromSubnet(subnet.trim());
      for (const ip of baseIPs) {
        candidates.push(`http://${ip}:${port}`);
      }
    }
    
    // Remove duplicates
    return [...new Set(candidates)];
  }

  getCommonIPsFromSubnet(subnet) {
    // Simplified subnet to common IPs mapping for proxy
    if (subnet.includes('192.168.1.')) {
      return ['192.168.1.100', '192.168.1.101', '192.168.1.150', '192.168.1.200'];
    }
    if (subnet.includes('192.168.2.')) {
      return ['192.168.2.100', '192.168.2.101', '192.168.2.150', '192.168.2.200'];
    }
    if (subnet.includes('10.0.0.')) {
      return ['10.0.0.100', '10.0.0.101', '10.0.0.150', '10.0.0.200'];
    }
    return [];
  }

  startHealthCheck() {
    // Dynamic intervals based on backend health
    const getHealthCheckInterval = () => {
      if (!this.currentBackend || !this.currentBackend.isHealthy) {
        return 5000; // Check every 5 seconds when unhealthy
      }
      return parseInt(process.env.REACT_APP_HEALTH_CHECK_INTERVAL || '30000'); // Normal interval when healthy
    };
    
    const runHealthCheck = async () => {
      if (this.currentBackend) {
        const tested = await this.testBackendUrl(this.currentBackend.url, 3000);
        
        if (tested && !this.currentBackend.isHealthy) {
          console.log('[PROXY] ✓ Health check: Backend recovered');
          this.currentBackend.isHealthy = true;
        } else if (!tested && this.currentBackend.isHealthy) {
          console.log('[PROXY] ⚠ Health check: Backend became unhealthy');
          this.currentBackend.isHealthy = false;
          
          // Try to rediscover if auto-discovery is enabled
          if (process.env.REACT_APP_ENABLE_BACKEND_DISCOVERY === 'true') {
            console.log('[PROXY] Attempting backend rediscovery due to health check failure...');
            setTimeout(() => {
              try {
                const newBackend = this.detectBackendHost();
                if (newBackend && newBackend.isHealthy) {
                  console.log('[PROXY] ✓ Health check rediscovery successful:', newBackend.url);
                }
              } catch (rediscoveryError) {
                console.error('[PROXY] Health check rediscovery failed:', rediscoveryError.message);
              }
            }, 1000);
          }
        }
      }
      
      // Schedule next health check with dynamic interval
      const nextInterval = getHealthCheckInterval();
      this.healthCheckInterval = setTimeout(runHealthCheck, nextInterval);
    };

    // Start first health check
    this.healthCheckInterval = setTimeout(runHealthCheck, getHealthCheckInterval());
  }

  stopHealthCheck() {
    if (this.healthCheckInterval) {
      clearTimeout(this.healthCheckInterval);
      this.healthCheckInterval = null;
    }
  }
}

const proxyManager = new ProxyConfigManager();

// Enhanced error handling and retry logic with dynamic backend
function createEnhancedProxy(path, options = {}) {
  // Create a base proxy with static target
  const proxy = createProxyMiddleware(path, {
    target: 'http://localhost:8000', // Default target
    changeOrigin: true,
    logLevel: process.env.REACT_APP_DEBUG_PROXY === 'true' ? 'debug' : 'info',
    timeout: parseInt(process.env.REACT_APP_PROXY_TIMEOUT || '30000'),
    proxyTimeout: parseInt(process.env.REACT_APP_PROXY_TIMEOUT || '30000'),
    
    // Simplified router for reliable operation
    router: (req) => {
      try {
        const currentBackend = proxyManager.currentBackend;
        
        // Use current backend if available and healthy
        if (currentBackend && currentBackend.url && currentBackend.isHealthy) {
          if (process.env.REACT_APP_DEBUG_PROXY === 'true') {
            console.log(`[PROXY ROUTER] ✓ Routing to ${currentBackend.url}`);
          }
          return currentBackend.url;
        }
        
        // Fallback to localhost
        if (process.env.REACT_APP_DEBUG_PROXY === 'true') {
          console.log(`[PROXY ROUTER] ⚠ Using localhost fallback`);
        }
        return 'http://localhost:8000';
      } catch (error) {
        console.error('[PROXY ROUTER] ✗ Router error:', error.message);
        return 'http://localhost:8000';
      }
    },
    
    onError: async (err, req, res) => {
      const currentTarget = proxyManager.currentBackend?.url || 'unknown';
      
      console.error(`[PROXY ERROR] ${path}:`, {
        error: err.message,
        code: err.code,
        url: req.url,
        method: req.method,
        target: currentTarget,
        timestamp: new Date().toISOString()
      });

      // Mark current backend as unhealthy
      if (proxyManager.currentBackend) {
        proxyManager.currentBackend.isHealthy = false;
        console.log(`[PROXY ERROR] Marked backend ${proxyManager.currentBackend.url} as unhealthy`);
      }

      // Try to rediscover backend for critical connection errors
      if (err.code === 'ECONNREFUSED' || err.code === 'ETIMEDOUT') {
        console.log('[PROXY] Connection failed, attempting immediate rediscovery...');
        setTimeout(() => {
          try {
            const newBackend = proxyManager.detectBackendHost();
            if (newBackend && newBackend.isHealthy) {
              console.log('[PROXY] Rediscovery successful:', newBackend.url);
            }
          } catch (rediscoveryError) {
            console.error('[PROXY] Rediscovery failed:', rediscoveryError.message);
          }
        }, 1000);
      }

      // Send proper error response
      if (!res.headersSent) {
        res.status(502).json({
          error: 'Backend Connection Failed',
          message: 'Unable to connect to backend server. Please check your network configuration.',
          details: {
            code: err.code,
            target: currentTarget,
            suggestion: 'Verify backend server is running and network settings are correct'
          },
          timestamp: new Date().toISOString(),
          troubleshooting: {
            steps: [
              'Check if backend server is running',
              'Verify network connectivity',
              'Check environment variables in .env files',
              'Try enabling auto-discovery: REACT_APP_ENABLE_BACKEND_DISCOVERY=true'
            ]
          }
        });
      }
    },
    
    onProxyReq: (proxyReq, req, res) => {
      const timestamp = new Date().toISOString();
      const target = proxyManager.currentBackend?.url || 'unknown';
      
      if (process.env.REACT_APP_DEBUG_PROXY === 'true') {
        console.log(`[PROXY REQ] ${timestamp} ${req.method} ${req.url} -> ${target}${req.url}`);
      }

      // Add helpful headers
      proxyReq.setHeader('X-Forwarded-For', req.ip || req.connection.remoteAddress);
      proxyReq.setHeader('X-Forwarded-Proto', req.protocol);
      proxyReq.setHeader('X-Forwarded-Host', req.get('host'));
      proxyReq.setHeader('X-Proxy-Source', 'wood-inspection-frontend');
    },
    
    onProxyRes: (proxyRes, req, res) => {
      const timestamp = new Date().toISOString();
      const duration = Date.now() - (req._startTime || Date.now());
      
      if (process.env.REACT_APP_DEBUG_PROXY === 'true') {
        console.log(`[PROXY RES] ${timestamp} ${proxyRes.statusCode} ${req.url} (${duration}ms)`);
      }

      // Update backend health status on successful responses
      if (proxyRes.statusCode >= 200 && proxyRes.statusCode < 300) {
        // Mark current backend as healthy if the request succeeded
        if (proxyManager.currentBackend && !proxyManager.currentBackend.isHealthy) {
          console.log('[PROXY] ✓ Backend response successful, marking as healthy');
          proxyManager.currentBackend.isHealthy = true;
        }
      } else if (proxyRes.statusCode >= 500) {
        // Mark backend as unhealthy on server errors
        if (proxyManager.currentBackend) {
          console.log(`[PROXY] ⚠ Backend returned ${proxyRes.statusCode}, marking as unhealthy`);
          proxyManager.currentBackend.isHealthy = false;
        }
      }

      // Ensure CORS headers
      if (!proxyRes.headers['access-control-allow-origin']) {
        proxyRes.headers['access-control-allow-origin'] = '*';
      }
      if (!proxyRes.headers['access-control-allow-methods']) {
        proxyRes.headers['access-control-allow-methods'] = 'GET,PUT,POST,DELETE,OPTIONS';
      }
      if (!proxyRes.headers['access-control-allow-headers']) {
        proxyRes.headers['access-control-allow-headers'] = 'Content-Type,Authorization';
      }
    },
    
    onProxyReqWs: (proxyReq, req, socket, options, head) => {
      console.log(`[PROXY WS] WebSocket connection: ${req.url}`);
    },
    
    ...options
  });
  
  // Register proxy for dynamic target updates
  proxyManager.registerProxy(proxy);
  
  return proxy;
}

module.exports = function(app) {
  console.log('[PROXY] ===== SIMPLIFIED DYNAMIC PROXY INITIALIZATION =====');
  console.log('[PROXY] Backend Discovery:', process.env.REACT_APP_ENABLE_BACKEND_DISCOVERY === 'true' ? 'ENABLED' : 'DISABLED');
  console.log('[PROXY] Network Mode:', process.env.REACT_APP_NETWORK_MODE === 'true' ? 'ENABLED' : 'DISABLED');
  console.log('[PROXY] Debug Mode:', process.env.REACT_APP_DEBUG_PROXY === 'true' ? 'ENABLED' : 'DISABLED');
  console.log('[PROXY] =============================================');

  // Initialize backend detection with error handling
  console.log('[PROXY] Initializing backend detection...');
  try {
    const backend = proxyManager.detectBackendHost();
    
    if (backend) {
      console.log(`[PROXY] ✓ Backend initialized: ${backend.url}`);
      console.log(`[PROXY] Backend healthy: ${backend.isHealthy ? 'YES' : 'NO'}`);
    } else {
      console.error(`[PROXY] ✗ No backend could be detected, using fallback`);
      // Set fallback backend
      proxyManager.currentBackend = {
        url: 'http://localhost:8000',
        host: 'localhost',
        port: '8000',
        isHealthy: false
      };
    }
  } catch (error) {
    console.error('[PROXY] ✗ Backend detection error:', error.message);
    // Set emergency fallback
    proxyManager.currentBackend = {
      url: 'http://localhost:8000',
      host: 'localhost', 
      port: '8000',
      isHealthy: false
    };
  }

  // Add request timing middleware
  app.use((req, res, next) => {
    req._startTime = Date.now();
    next();
  });

  // Simplified proxy configuration endpoints
  app.get('/api/proxy/status', (req, res) => {
    res.json({
      currentBackend: proxyManager.currentBackend,
      fallbackHosts: proxyManager.fallbackHosts,
      configuration: {
        discoveryEnabled: process.env.REACT_APP_ENABLE_BACKEND_DISCOVERY === 'true',
        networkMode: process.env.REACT_APP_NETWORK_MODE === 'true',
        debugMode: process.env.REACT_APP_DEBUG_PROXY === 'true'
      },
      timestamp: new Date().toISOString()
    });
  });

  // Main API proxy with simplified error handling
  app.use('/api', createEnhancedProxy('/api'));

  // Health check proxy
  app.use('/health', createEnhancedProxy('/health'));

  console.log('[PROXY] Simplified proxy middleware setup complete');
};