const { createProxyMiddleware } = require('http-proxy-middleware');
const os = require('os');

// Ensure fetch is available in Node.js environment
if (!global.fetch) {
  try {
    global.fetch = require('node-fetch');
  } catch (error) {
    console.warn('[PROXY] node-fetch not available, some features may be limited');
    // Provide a minimal fallback that always rejects
    global.fetch = () => Promise.reject(new Error('fetch not available'));
  }
}

console.log('[PROXY] ===== DYNAMIC BACKEND DISCOVERY PROXY =====');
console.log('[PROXY] Loading environment variables...');
console.log('[PROXY] REACT_APP_NETWORK_MODE:', process.env.REACT_APP_NETWORK_MODE);
console.log('[PROXY] REACT_APP_API_URL:', process.env.REACT_APP_API_URL);
console.log('[PROXY] REACT_APP_BACKEND_HOST:', process.env.REACT_APP_BACKEND_HOST);
console.log('[PROXY] REACT_APP_ENABLE_BACKEND_DISCOVERY:', process.env.REACT_APP_ENABLE_BACKEND_DISCOVERY);
console.log('[PROXY] REACT_APP_DEBUG_PROXY:', process.env.REACT_APP_DEBUG_PROXY);

// CRITICAL: Force override any hardcoded IP configurations
if (process.env.REACT_APP_API_URL && process.env.REACT_APP_API_URL.includes('192.168.2.104')) {
  console.error('[PROXY] CRITICAL: Hardcoded IP detected in REACT_APP_API_URL! Forcing override.');
  process.env.REACT_APP_API_URL = '';
  process.env.REACT_APP_BACKEND_HOST = 'auto';
}
if (process.env.REACT_APP_BACKEND_HOST === '192.168.2.104') {
  console.error('[PROXY] CRITICAL: Hardcoded IP detected in REACT_APP_BACKEND_HOST! Forcing override.');
  process.env.REACT_APP_BACKEND_HOST = 'auto';
}

// Dynamic backend configuration manager
class DynamicProxyManager {
  constructor() {
    this.currentBackend = null;
    this.fallbackHosts = this.parseFallbackHosts();
    this.isDiscovering = false;
    this.lastDiscovery = 0;
    this.healthCheckInterval = null;
    this.backendCache = new Map();
  }

  // Get machine IP addresses with virtual interface filtering
  getMachineIPs() {
    const ips = [];
    
    try {
      const networkInterfaces = os.networkInterfaces();
      
      for (const [name, interfaces] of Object.entries(networkInterfaces)) {
        for (const iface of interfaces) {
          // Enhanced filtering to exclude virtual interfaces
          if (iface.family === 'IPv4' && 
              !iface.internal && 
              !name.includes('VirtualBox') &&
              !name.includes('VMware') &&
              !name.includes('docker') &&
              !name.includes('vEthernet') &&
              !name.includes('Hyper-V') &&
              !name.includes('Loopback') &&
              !name.toLowerCase().includes('virtual') &&
              !name.toLowerCase().includes('tap') &&
              !name.toLowerCase().includes('tun')) {
            ips.push(iface.address);
          }
        }
      }
      
      console.log('[PROXY] Detected machine IPs:', ips);
    } catch (error) {
      console.warn('[PROXY] Could not detect machine IPs:', error.message);
    }
    
    return ips;
  }

  parseFallbackHosts() {
    const fallbackString = process.env.REACT_APP_FALLBACK_HOSTS || 'localhost,127.0.0.1';
    return fallbackString.split(',').map(h => h.trim()).filter(h => h.length > 0);
  }

  // Synchronous backend detection (follows memory requirement)
  detectBackend() {
    console.log('[PROXY] Starting backend detection...');
    
    // Priority 1: Explicit API URL
    const explicitUrl = process.env.REACT_APP_API_URL;
    if (explicitUrl && explicitUrl.startsWith('http')) {
      console.log('[PROXY] Using explicit API URL:', explicitUrl);
      // Check for hardcoded IP
      if (explicitUrl.includes('192.168.2.104')) {
        console.error('[PROXY] HARDCODED IP DETECTED in REACT_APP_API_URL! Ignoring.');
      } else {
        return this.parseUrlToBackend(explicitUrl);
      }
    }

    // Priority 2: Explicit host/port
    const explicitHost = process.env.REACT_APP_BACKEND_HOST;
    const port = process.env.REACT_APP_BACKEND_PORT || '8000';
    
    console.log('[PROXY] Environment variables:', {
      REACT_APP_BACKEND_HOST: explicitHost,
      REACT_APP_BACKEND_PORT: port,
      REACT_APP_NETWORK_MODE: process.env.REACT_APP_NETWORK_MODE
    });
    
    if (explicitHost && explicitHost !== 'auto') {
      // Check for hardcoded IP
      if (explicitHost === '192.168.2.104') {
        console.error('[PROXY] HARDCODED IP DETECTED in REACT_APP_BACKEND_HOST! Using auto-detection instead.');
      } else {
        const backendUrl = `http://${explicitHost}:${port}`;
        console.log('[PROXY] Using explicit backend host:', backendUrl);
        return this.parseUrlToBackend(backendUrl);
      }
    }

    // Priority 3: Auto-detection with network mode prioritization
    const networkMode = process.env.REACT_APP_NETWORK_MODE === 'true';
    const machineIPs = this.getMachineIPs();
    
    if (networkMode && machineIPs.length > 0) {
      // Prioritize machine IPs for external device access
      const machineUrl = `http://${machineIPs[0]}:${port}`;
      console.log('[PROXY] Network mode: prioritizing machine IP:', machineUrl);
      return this.parseUrlToBackend(machineUrl);
    }

    // Priority 4: Localhost fallback
    const localhostUrl = `http://localhost:${port}`;
    console.log('[PROXY] Using localhost fallback:', localhostUrl);
    return this.parseUrlToBackend(localhostUrl);
  }

  parseUrlToBackend(url) {
    try {
      const parsedUrl = new URL(url);
      return {
        url,
        host: parsedUrl.hostname,
        port: parsedUrl.port || '8000',
        isHealthy: null // Will be determined by health checks
      };
    } catch (error) {
      console.error('[PROXY] Invalid URL:', url, error.message);
      return {
        url: 'http://localhost:8000',
        host: 'localhost',
        port: '8000',
        isHealthy: false
      };
    }
  }

  // Router function that guarantees valid URL (follows memory requirement)
  createRouter() {
    const self = this;
    return function(req) {
      // Force fresh backend detection every time to eliminate caching
      if (!self.currentBackend || !self.currentBackend.isHealthy) {
        console.log('[PROXY] Refreshing backend detection...');
        self.currentBackend = self.detectBackend();
      }
      
      // Always return a valid URL string (memory requirement)
      const targetUrl = self.currentBackend?.url || 'http://localhost:8000';
      
      if (process.env.REACT_APP_DEBUG_PROXY === 'true') {
        console.log(`[PROXY ROUTER] ${req.method} ${req.url} -> ${targetUrl}`);
      }
      
      // Ensure we NEVER return the hardcoded IP
      if (targetUrl.includes('192.168.2.104')) {
        console.error('[PROXY ERROR] Detected hardcoded IP! Forcing localhost fallback.');
        return 'http://localhost:8000';
      }
      
      return targetUrl;
    };
  }

  // Mark backend as healthy when requests succeed
  markBackendHealthy() {
    if (this.currentBackend) {
      this.currentBackend.isHealthy = true;
      this.lastSuccessTime = Date.now();
    }
  }

  // Mark backend as unhealthy and trigger rediscovery
  markBackendUnhealthy() {
    if (this.currentBackend) {
      this.currentBackend.isHealthy = false;
      console.log('[PROXY] Backend marked as unhealthy, will trigger rediscovery');
    }
  }

  // Start adaptive health checking
  startHealthChecking() {
    if (this.healthCheckInterval) {
      clearInterval(this.healthCheckInterval);
    }

    const getHealthCheckInterval = () => {
      // Adaptive intervals: 5s when unhealthy, 30s when healthy
      return (!this.currentBackend?.isHealthy) ? 5000 : 30000;
    };

    const runHealthCheck = () => {
      if (!this.currentBackend) return;

      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 3000);

      fetch(`${this.currentBackend.url}/health`, {
        signal: controller.signal,
        method: 'GET'
      })
      .then(response => {
        clearTimeout(timeout);
        if (response.ok) {
          this.markBackendHealthy();
        } else {
          this.markBackendUnhealthy();
        }
      })
      .catch(() => {
        clearTimeout(timeout);
        this.markBackendUnhealthy();
      });
    };

    // Run initial health check
    setTimeout(runHealthCheck, 1000);

    // Set up periodic health checks with adaptive interval
    const scheduleNext = () => {
      setTimeout(() => {
        runHealthCheck();
        scheduleNext();
      }, getHealthCheckInterval());
    };

    scheduleNext();
  }
}

// Create global proxy manager instance
const proxyManager = new DynamicProxyManager();

// Initialize backend detection
proxyManager.currentBackend = proxyManager.detectBackend();
console.log('[PROXY] Initial backend:', proxyManager.currentBackend.url);

module.exports = function(app) {
  console.log('[PROXY] Setting up dynamic proxy middleware...');

  // Start health checking
  proxyManager.startHealthChecking();

  // Create proxy with static target and router function (memory requirement)
  const proxyMiddleware = createProxyMiddleware({
    target: 'http://localhost:8000', // Static fallback target
    router: proxyManager.createRouter(), // Dynamic router function
    changeOrigin: true,
    logLevel: process.env.REACT_APP_DEBUG_PROXY === 'true' ? 'debug' : 'warn',
    timeout: parseInt(process.env.REACT_APP_PROXY_TIMEOUT || '30000'),
    proxyTimeout: parseInt(process.env.REACT_APP_PROXY_TIMEOUT || '30000'),
    
    onError: (err, req, res) => {
      console.error('[PROXY ERROR]:', {
        error: err.message,
        code: err.code,
        url: req.url,
        method: req.method,
        target: proxyManager.currentBackend?.url
      });

      // Mark backend as unhealthy
      proxyManager.markBackendUnhealthy();

      if (!res.headersSent) {
        res.status(502).json({
          error: 'Backend Connection Failed',
          message: 'Unable to connect to backend server',
          details: err.message,
          timestamp: new Date().toISOString(),
          currentTarget: proxyManager.currentBackend?.url
        });
      }
    },

    onProxyReq: (proxyReq, req, res) => {
      if (process.env.REACT_APP_DEBUG_PROXY === 'true') {
        console.log(`[PROXY REQ] ${req.method} ${req.url} -> ${proxyReq.path}`);
      }
      
      // Add debugging headers
      proxyReq.setHeader('X-Forwarded-For', req.ip || req.connection.remoteAddress);
      proxyReq.setHeader('X-Proxy-Target', proxyManager.currentBackend?.url);
    },

    onProxyRes: (proxyRes, req, res) => {
      if (process.env.REACT_APP_DEBUG_PROXY === 'true') {
        console.log(`[PROXY RES] ${proxyRes.statusCode} ${req.url}`);
      }

      // Mark backend as healthy on successful response
      if (proxyRes.statusCode >= 200 && proxyRes.statusCode < 300) {
        proxyManager.markBackendHealthy();
      }

      // Ensure CORS headers
      if (!proxyRes.headers['access-control-allow-origin']) {
        proxyRes.headers['access-control-allow-origin'] = '*';
      }
    }
  });

  // Apply proxy to all API routes
  app.use('/api', proxyMiddleware);
  app.use('/health', proxyMiddleware);
  app.use('/settings', proxyMiddleware);

  // Add proxy status endpoint for debugging
  app.get('/proxy/status', (req, res) => {
    res.json({
      currentBackend: proxyManager.currentBackend,
      machineIPs: proxyManager.getMachineIPs(),
      fallbackHosts: proxyManager.fallbackHosts,
      environment: {
        REACT_APP_NETWORK_MODE: process.env.REACT_APP_NETWORK_MODE,
        REACT_APP_BACKEND_HOST: process.env.REACT_APP_BACKEND_HOST,
        REACT_APP_ENABLE_BACKEND_DISCOVERY: process.env.REACT_APP_ENABLE_BACKEND_DISCOVERY
      },
      timestamp: new Date().toISOString()
    });
  });

  console.log(`[PROXY] Dynamic proxy setup complete`);
  console.log(`[PROXY] Current target: ${proxyManager.currentBackend.url}`);
  console.log(`[PROXY] Status endpoint: http://localhost:3000/proxy/status`);
};
