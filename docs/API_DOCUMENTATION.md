# API Documentation - Wood Inspection System

## 📋 API Overview

The Wood Inspection System provides a comprehensive REST API built with FastAPI, featuring real-time data streaming, file handling, and hardware integration capabilities.

## 🌐 Base Configuration

### API Client Setup

```typescript
// Frontend API Client Configuration
const baseURL = getApiUrl(); // Auto-detects development proxy or production URL

export const api = Axios.create({
  baseURL,
  timeout: 20000,
  headers: { 'Content-Type': 'application/json' }
});
```

### URL Detection Logic

```typescript
export const getApiUrl = () => {
  // Development: Use proxy
  if (process.env.NODE_ENV === 'development') {
    return '/api'; // Routes through setupProxy.js
  }
  
  // Production: Auto-detect or explicit URL
  const apiUrl = process.env.REACT_APP_API_URL;
  const backendHost = process.env.REACT_APP_BACKEND_HOST || 'localhost';
  const backendPort = process.env.REACT_APP_BACKEND_PORT || '8000';
  
  return apiUrl || `http://${backendHost}:${backendPort}`;
};
```

## 🔄 Core API Endpoints

### 1. Inspection Management

#### Get Latest Inspection
```http
GET /api/inspections/latest?product_no={productNo}
```

**Response:**
```json
{
  "result": true,
  "message": "Success!!",
  "data": {
    "inspection_id": 123,
    "inspection_dt": "2024-01-15T10:30:00",
    "product_no": "WOOD001",
    "status": true,
    "measurements": "Length: 2.5m, Width: 0.3m",
    "image_data": "base64encodedstring..."
  }
}
```

**Frontend Usage:**
```typescript
// src/features/inspections/api/get-latest-inspections.ts
export const getLatestInspection = ({ productNo }: { productNo: string }) => {
  return api.get(`/inspections/latest`, {
    params: { product_no: productNo },
  });
};

export const UseLatestInspection = ({ productNo, queryConfig }) => {
  return useQuery({
    queryKey: ['latestInspection', productNo],
    queryFn: () => getLatestInspection({ productNo }),
    ...queryConfig,
  });
};
```

#### Get Inspection Details
```http
GET /api/inspections/details?id={inspectionId}
```

**Response:**
```json
{
  "result": true,
  "message": "Success!!",
  "data": {
    "inspection_id": 123,
    "inspection_dt": "2024-01-15T10:30:00",
    "defect_details": [
      {
        "error_type": 2,
        "length": 15.5,
        "confidence": 0.92,
        "coordinates": "[[100,200],[150,250]]"
      }
    ],
    "presentation_images": [...]
  }
}
```

#### Get Presentation Images
```http
GET /api/inspections/presentation-images?id={inspectionId}
```

**Response:**
```json
{
  "result": true,
  "data": [
    {
      "presentation_id": 1,
      "inspection_id": 123,
      "image_path": "inspection/123/presentation_1.jpg",
      "group_number": 1,
      "image_order": 1
    }
  ]
}
```

**Frontend Implementation:**
```typescript
// Continuous polling for presentation images
const loadPresentationImages = async (id: number) => {
  const result = await fetchPresentationImages({ id });
  
  if (result.data && result.data.length > 0) {
    // Preload images for performance
    result.data.forEach((img) => {
      const apiUrl = `/api/file?path=${encodeURIComponent(img.image_path)}&inspection_id=${img.inspection_id}&convert=jpg`;
      const preloadImg = new Image();
      preloadImg.src = apiUrl;
    });
    
    setPresentationImages(result.data);
  }
};
```

### 2. Sensor Control & Monitoring

#### Get Sensor Status
```http
GET /api/sensor-inspection/status
```

**Response:**
```json
{
  "active": true,
  "simulation_mode": false,
  "sensor_a": false,
  "sensor_b": false,
  "sensors": {
    "sensor_a": false,
    "sensor_b": false
  },
  "inspection_data": {
    "inspection_id": 123,
    "inspection_details": [...],
    "measurements": "..."
  },
  "inspection_results": {
    "knot": true,
    "dead_knot": false,
    "live_knot": true,
    "length": 15.5,
    "hole": false,
    "discoloration": false
  }
}
```

#### Start Monitoring
```http
POST /api/sensor-inspection/start
Content-Type: application/json

{
  "camera_type": "basler",
  "ai_threshold": 75
}
```

#### Stop Monitoring
```http
POST /api/sensor-inspection/stop
```

**Frontend Hook Implementation:**
```typescript
// useSensorMonitoring.ts
export const useSensorMonitoring = (cameraType: string) => {
  const [sensorStatus, setSensorStatus] = useState<SensorStatus>({
    active: false,
    simulation_mode: false,
    sensor_a: false,
    sensor_b: false
  });

  const handleStart = async () => {
    try {
      const response = await api.post('/sensor-inspection/start', {
        camera_type: cameraType,
        ai_threshold: aiThreshold
      });
      
      if (response.result) {
        addNotification({
          type: 'success',
          title: 'システム開始',
          message: 'センサー監視を開始しました'
        });
      }
    } catch (error) {
      console.error('Failed to start monitoring:', error);
    }
  };

  // Real-time polling
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const status = await api.get('/sensor-inspection/status', {
          suppressGlobalError: true
        });
        setSensorStatus(status);
      } catch (error) {
        console.error('Sensor status polling error:', error);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  return { sensorStatus, handleStart, handleStop };
};
```

### 3. Camera Operations

#### Camera Preview
```http
GET /api/camera/preview?camera_type={cameraType}
```

**Response:** Binary image data (JPEG)

#### Camera Settings
```http
GET /api/camera/settings
POST /api/camera/settings
```

### 4. File Operations

#### Get File/Image
```http
GET /api/file?path={filePath}&inspection_id={id}&convert=jpg&cache={cacheKey}
```

**Parameters:**
- `path`: Relative file path
- `inspection_id`: Associated inspection ID
- `convert`: Convert to format (jpg, png)
- `cache`: Cache key for performance

### 5. Settings Management

#### Get Current Settings
```http
GET /api/settings/current
```

#### Save Settings
```http
POST /api/settings
Content-Type: application/json

{
  "ai_threshold": 75,
  "camera_settings": {...},
  "sensor_config": {...}
}
```

## 🔄 Real-time Streaming APIs

### WebSocket Connections

#### Latest Inspection Stream
```javascript
const ws = new WebSocket('ws://localhost:8000/api/inspections/latest');

ws.onmessage = (event) => {
  const inspection = JSON.parse(event.data);
  updateInspectionDisplay(inspection);
};
```

#### Sensor Data Stream
```javascript
const eventSource = new EventSource('/api/streaming/sensor');

eventSource.onmessage = (event) => {
  const sensorData = JSON.parse(event.data);
  updateSensorStatus(sensorData);
};
```

### Streaming Configuration

```http
GET /api/streaming/config
POST /api/streaming/config
```

## 🔧 Error Handling

### Standard Error Response
```json
{
  "result": false,
  "message": "Error description",
  "error_code": "VALIDATION_ERROR",
  "details": {...}
}
```

### Frontend Error Handling

```typescript
// Global error interceptor
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    // Circuit breaker pattern
    const errorKey = `${error.code}-${error.config?.url}-${error.response?.status}`;
    const consecutiveCount = consecutiveErrors.get(errorKey) || 0;
    
    if (consecutiveCount < MAX_CONSECUTIVE_ERRORS) {
      useNotifications.getState().addNotification({
        type: 'error',
        title: 'Connection Error',
        message: getErrorMessage(error),
      });
    }
    
    return Promise.reject(error);
  }
);
```

## 📊 Data Models

### Inspection Model
```typescript
interface Inspection {
  inspection_id: number;
  inspection_dt: string;
  product_no: string;
  status: boolean;
  measurements?: string;
  image_data?: string; // base64 encoded
}
```

### Sensor Status Model
```typescript
interface SensorStatus {
  active: boolean;
  simulation_mode: boolean;
  sensor_a: boolean;
  sensor_b: boolean;
  sensors: {
    sensor_a: boolean;
    sensor_b: boolean;
  };
  inspection_data?: InspectionData;
  inspection_results?: InspectionResults;
}
```

### Inspection Results Model
```typescript
interface InspectionResults {
  knot: boolean;
  dead_knot: boolean;
  live_knot: boolean;
  tight_knot: boolean;
  length: number;
  hole: boolean;
  discoloration: boolean;
}
```

## 🚀 Performance Considerations

### Caching Strategy
- **React Query**: Automatic caching with configurable TTL
- **Image Preloading**: Proactive loading of presentation images
- **Response Caching**: Server-side caching for static data

### Optimization Techniques
- **Debounced Polling**: Prevents excessive API calls
- **Connection Pooling**: Efficient database connections
- **Binary Encoding**: Base64 encoding for image transmission
- **Compression**: GZIP compression for large responses

### Rate Limiting
- **Polling Intervals**: Configurable intervals for real-time data
- **Circuit Breaker**: Automatic error suppression after threshold
- **Timeout Configuration**: Appropriate timeouts for different operations

## 📈 Monitoring & Health Checks

### Health Check Endpoint
```http
GET /api/health
```

**Response:**
```json
{
  "status": "ok",
  "message": "Backend is running and accessible",
  "timestamp": "2024-01-15T10:30:00Z",
  "services": {
    "database": "connected",
    "camera": "available",
    "sensors": "active"
  }
}
```

### Network Diagnostics
```http
GET /api/network/status
```

### Streaming Monitoring
```http
GET /api/streaming/monitoring/status
```

---

*For implementation examples and best practices, see the [Frontend Integration Guide](./FRONTEND_INTEGRATION.md) and [Backend Development Guide](./BACKEND_DEVELOPMENT.md).*