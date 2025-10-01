# Frontend Integration Guide - Wood Inspection System

## 🎯 Overview

This guide explains how the React frontend integrates with the FastAPI backend, covering data fetching patterns, state management, real-time updates, and performance optimizations.

## 🔗 API Integration Architecture

### Centralized API Client

The frontend uses a centralized API client that handles all backend communication:

```typescript
// src/lib/api-client.ts
import Axios from 'axios';

export const api = Axios.create({
  baseURL: getApiUrl(), // Auto-detects proxy or production URL
  timeout: 20000,
  headers: { 'Content-Type': 'application/json' }
});

// Development: /api (proxy) | Production: http://host:port
export const getApiUrl = () => {
  if (process.env.NODE_ENV === 'development') {
    return '/api'; // Routes through setupProxy.js
  }
  
  return process.env.REACT_APP_API_URL || 
         `http://${process.env.REACT_APP_BACKEND_HOST || 'localhost'}:${process.env.REACT_APP_BACKEND_PORT || '8000'}`;
};
```

### Error Handling Strategy

```typescript
// Global error interceptor with circuit breaker
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const errorKey = `${error.code}-${error.config?.url}-${error.response?.status}`;
    const consecutiveCount = consecutiveErrors.get(errorKey) || 0;
    
    // Circuit breaker: stop notifications after threshold
    if (consecutiveCount < MAX_CONSECUTIVE_ERRORS) {
      useNotifications.getState().addNotification({
        type: 'error',
        title: 'Connection Error',
        message: getErrorMessage(error),
      });
    }
    
    consecutiveErrors.set(errorKey, consecutiveCount + 1);
    return Promise.reject(error);
  }
);
```

## 🎣 Data Fetching Patterns

### 1. React Query Integration

The system uses React Query for efficient data fetching with automatic caching:

```typescript
// src/features/inspections/api/get-latest-inspections.ts
import { queryOptions, useQuery } from '@tanstack/react-query';

export const getLatestInspection = ({ productNo }: { productNo: string }) => {
  return api.get(`/inspections/latest`, {
    params: { product_no: productNo },
  });
};

export const getLatestInspectionQueryOptions = (productNo: string) => {
  return queryOptions({
    queryKey: ['latestInspection', productNo],
    queryFn: () => getLatestInspection({ productNo }),
    staleTime: 30000, // 30 seconds
    cacheTime: 300000, // 5 minutes
  });
};

export const UseLatestInspection = ({ productNo, queryConfig }) => {
  return useQuery({
    ...getLatestInspectionQueryOptions(productNo),
    ...queryConfig,
  });
};
```

### 2. Real-time Data Hooks

Custom hooks manage real-time data streams and polling:

```typescript
// src/app/routes/app/inspection/hooks/useSensorMonitoring.ts
export const useSensorMonitoring = (cameraType: string) => {
  const [sensorStatus, setSensorStatus] = useState<SensorStatus>({
    active: false,
    simulation_mode: false,
    sensor_a: false,
    sensor_b: false
  });

  // Real-time polling with error handling
  useEffect(() => {
    const pollSensorStatus = async () => {
      try {
        const status = await api.get('/sensor-inspection/status', {
          suppressGlobalError: true // Prevent notification spam
        });
        setSensorStatus(status);
      } catch (error) {
        console.error('Sensor polling error:', error);
      }
    };

    const interval = setInterval(pollSensorStatus, 1000);
    pollSensorStatus(); // Initial fetch

    return () => clearInterval(interval);
  }, []);

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

  return { sensorStatus, handleStart, handleStop };
};
```

## 🎛️ State Management Architecture

### Hook-based State Management

The frontend uses specialized hooks for different aspects of the application:

```typescript
// src/app/routes/app/inspection/InspectionScreen.tsx
const InspectionScreen: React.FC = () => {
  // Specialized hooks for different concerns
  const { selectedCameraType, handleCameraTypeChange } = useCameraManagement();
  
  const { 
    status, 
    inspectionResult, 
    presentationImages, 
    loadPresentationImages 
  } = useInspectionState();
  
  const { 
    sensorStatus, 
    aiThreshold, 
    handleStart, 
    handleStop 
  } = useSensorMonitoring(selectedCameraType);
  
  const { batchResult, defectType } = useSensorData();

  // Cross-hook coordination via effects
  useEffect(() => {
    if (sensorStatus?.inspection_data) {
      // Update inspection results from sensor data
      updateInspectionResultFromSensorStatus(sensorStatus);
    }
  }, [sensorStatus]);

  // ... component render
};
```

### Database-First Approach

Following the database-first architecture specification:

```typescript
// useInspectionState.ts - Database-only fetching
const forceRefreshLatestResult = useCallback(async () => {
  try {
    setIsRefreshing(true);
    
    // Only fetch from database, ignore sensor data
    const result = await fetchInspectionResultFromDatabase();
    
    if (result.result && result.data) {
      const dbResult = result.data;
      
      // Process database results
      const hasAnyKnot = dbResult.knot || dbResult.dead_knot || 
                        dbResult.live_knot || dbResult.tight_knot;
      const knotLength = dbResult.length || 0;
      const knotStatus = hasAnyKnot && knotLength > 10 ? '節あり' : 
                        hasAnyKnot ? 'こぶし' : '無欠点';
      
      setInspectionResult(knotStatus);
      setCreatedInspectionId(dbResult.inspection_id);
    }
  } catch (error) {
    console.error('Failed to refresh inspection result:', error);
  } finally {
    setIsRefreshing(false);
  }
}, []);
```

## 🖼️ Image Processing & Display

### Presentation Images Pipeline

```typescript
// Continuous polling for presentation images
const loadPresentationImages = async (id: number) => {
  if (!id) return;

  setLoadingPresentationImages(true);
  let attemptCount = 0;

  const pollForImages = async () => {
    attemptCount++;
    console.log(`Polling attempt ${attemptCount} for inspection ${id}`);

    try {
      const result = await fetchPresentationImages({ id });

      if (result.result && result.data && result.data.length > 0) {
        console.log(`Found ${result.data.length} presentation images`);

        // Preload images for better performance
        result.data.forEach((img) => {
          const apiUrl = `/api/file?path=${encodeURIComponent(img.image_path)}&inspection_id=${img.inspection_id}&convert=jpg&cache=${img.inspection_id}`;
          const preloadImg = new Image();
          preloadImg.src = apiUrl;
        });

        setPresentationImages(result.data);
        setLoadingPresentationImages(false);
        return true; // Success
      }
      
      return false; // No images yet
    } catch (err) {
      console.error(`Error polling for images:`, err);
      return false;
    }
  };

  // Start continuous polling
  const interval = setInterval(async () => {
    const success = await pollForImages();
    if (success) {
      clearInterval(interval);
    }
  }, 2000);

  // Initial attempt
  const success = await pollForImages();
  if (success) {
    clearInterval(interval);
  }
};
```

### Image URL Generation

```typescript
// src/app/routes/app/inspection/utils/imageUtils.ts
export const getImageUrl = (imagePath: string, inspectionId: number): string => {
  if (imagePath.startsWith('inspection/')) {
    const relativePath = `src-api/data/images/${imagePath}`;
    return `/api/file?path=${encodeURIComponent(relativePath)}&inspection_id=${inspectionId}&convert=jpg&cache=${inspectionId}`;
  } else {
    const pathMatch = imagePath.match(/inspection[/\\](.*)/)
    if (pathMatch && pathMatch[1]) {
      const relativePath = `src-api/data/images/inspection/${pathMatch[1].replace(/\\/g, '/')}`;
      return `/api/file?path=${encodeURIComponent(relativePath)}&inspection_id=${inspectionId}&convert=jpg&cache=${inspectionId}`;
    } else {
      return `/api/file?path=${encodeURIComponent(imagePath)}&inspection_id=${inspectionId}&convert=jpg&cache=${inspectionId}`;
    }
  }
};
```

## 🔄 Real-time Communication

### WebSocket Integration

```typescript
// WebSocket connection for real-time inspection updates
export const useInspectionWebSocket = () => {
  const [inspection, setInspection] = useState<Inspection | null>(null);

  useEffect(() => {
    const ws = new WebSocket(`ws://${window.location.host}/api/inspections/latest`);

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data && data !== 'null') {
          setInspection(data);
          
          // Trigger custom event for other components
          window.dispatchEvent(new CustomEvent('inspectionUpdated', {
            detail: data
          }));
        }
      } catch (error) {
        console.error('WebSocket message parsing error:', error);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    return () => {
      ws.close();
    };
  }, []);

  return inspection;
};
```

### Custom Events for Component Coordination

```typescript
// Custom event system for cross-component communication
export const dispatchSaveEvent = (inspectionId: number) => {
  const event = new CustomEvent('inspectionSaved', {
    detail: { inspectionId }
  });
  window.dispatchEvent(event);
};

// Component listening for events
useEffect(() => {
  const handleInspectionSaved = (event: CustomEvent) => {
    const { inspectionId } = event.detail;
    loadPresentationImages(inspectionId);
  };

  window.addEventListener('inspectionSaved', handleInspectionSaved);
  
  return () => {
    window.removeEventListener('inspectionSaved', handleInspectionSaved);
  };
}, []);
```

## 🎨 UI Components Integration

### Result Display Component

```typescript
// src/app/routes/app/inspection/components/inspection-display/ResultDisplay.tsx
export const ResultDisplay: React.FC = () => {
  const { inspectionResult, defectType, measurements } = useInspectionState();

  return (
    <div className="bg-white p-6 rounded-lg shadow-lg">
      <h3 className="text-xl font-bold mb-4">検査結果</h3>
      
      <div className="space-y-4">
        <div className="flex justify-between">
          <span className="font-medium">結果:</span>
          <span className={`font-bold ${
            inspectionResult === '節あり' ? 'text-red-600' : 
            inspectionResult === 'こぶし' ? 'text-yellow-600' : 
            'text-green-600'
          }`}>
            {inspectionResult || '待機中'}
          </span>
        </div>
        
        {defectType && (
          <div className="flex justify-between">
            <span className="font-medium">欠陥種類:</span>
            <span className="text-red-600 font-bold">{defectType}</span>
          </div>
        )}
        
        {measurements && (
          <div className="flex justify-between">
            <span className="font-medium">寸法:</span>
            <span>{measurements}</span>
          </div>
        )}
      </div>
    </div>
  );
};
```

### Presentation Images Grid

```typescript
// src/app/routes/app/inspection/components/inspection-display/PresentationImagesGrid.tsx
export const PresentationImagesGrid: React.FC = () => {
  const { presentationImages, loadingPresentationImages } = useInspectionState();

  if (loadingPresentationImages) {
    return <div className="flex justify-center p-8">画像を読み込み中...</div>;
  }

  return (
    <div className="max-w-[96vw] mx-auto p-4">
      <div className="flex flex-nowrap gap-4 overflow-x-auto">
        {presentationImages.map((image, index) => (
          <PresentationImageCard
            key={`${image.inspection_id}-${image.presentation_id}`}
            image={image}
            index={index}
          />
        ))}
      </div>
    </div>
  );
};
```

## ⚡ Performance Optimizations

### Caching Strategy

```typescript
// React Query configuration
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30000, // 30 seconds
      cacheTime: 300000, // 5 minutes
      retry: 3,
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
    },
  },
});
```

### Debounced Updates

```typescript
// Prevent UI flickering with debounced updates
const [debouncedResult, setDebouncedResult] = useState('');
const resultStableCountRef = useRef(0);
const STABILITY_THRESHOLD = 2;

useEffect(() => {
  if (batchResult === lastResultRef.current) {
    resultStableCountRef.current++;
    
    if (resultStableCountRef.current >= STABILITY_THRESHOLD) {
      setDebouncedResult(batchResult);
    }
  } else {
    resultStableCountRef.current = 0;
    lastResultRef.current = batchResult;
  }
}, [batchResult]);
```

### Image Preloading

```typescript
// Preload images for smooth user experience
const preloadImages = (images: PresentationImage[]) => {
  images.forEach((img) => {
    const apiUrl = getImageUrl(img.image_path, img.inspection_id);
    const preloadImg = new Image();
    preloadImg.onload = () => console.log(`Preloaded: ${img.image_path}`);
    preloadImg.onerror = () => console.error(`Failed to preload: ${img.image_path}`);
    preloadImg.src = apiUrl;
  });
};
```

## 🔧 Development Best Practices

### Error Boundaries

```typescript
// Global error boundary for component errors
export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Error boundary caught an error:', error, errorInfo);
    
    // Report to monitoring service
    useNotifications.getState().addNotification({
      type: 'error',
      title: 'Application Error',
      message: 'An unexpected error occurred. Please refresh the page.',
    });
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback;
    }

    return this.props.children;
  }
}
```

### Testing Integration

```typescript
// Mock API client for testing
export const createMockApi = () => {
  return {
    get: jest.fn(),
    post: jest.fn(),
    put: jest.fn(),
    delete: jest.fn(),
  };
};

// Test hook with mock data
test('useSensorMonitoring should handle start/stop operations', async () => {
  const mockApi = createMockApi();
  mockApi.post.mockResolvedValue({ result: true });

  const { result } = renderHook(() => useSensorMonitoring('basler'), {
    wrapper: QueryClientProvider,
  });

  await act(async () => {
    await result.current.handleStart();
  });

  expect(mockApi.post).toHaveBeenCalledWith('/sensor-inspection/start', {
    camera_type: 'basler',
    ai_threshold: expect.any(Number),
  });
});
```

## 📱 Responsive Design Integration

### CSS Variables for Dynamic Sizing

```css
/* src/index.css */
:root {
  --aspect-wood-inspection: 0.75; /* 4:3 aspect ratio */
  --image-width-sm: 140px;
  --image-width-md: 180px;
  --image-width-lg: 250px;
  --image-width-xl: 280px;
}

@media (max-width: 768px) {
  .presentation-image {
    width: var(--image-width-sm);
    height: calc(var(--image-width-sm) * var(--aspect-wood-inspection));
  }
}

@media (min-width: 1200px) {
  .presentation-image {
    width: var(--image-width-lg);
    height: calc(var(--image-width-lg) * var(--aspect-wood-inspection));
  }
}
```

### Responsive Grid Layout

```typescript
// Single-row grid with dynamic sizing
export const PresentationImagesGrid: React.FC = () => {
  return (
    <div className="max-w-[96vw] mx-auto">
      <div className="flex flex-nowrap gap-4 overflow-x-auto">
        {presentationImages.map((image, index) => (
          <img
            key={image.presentation_id}
            src={getImageUrl(image.image_path, image.inspection_id)}
            className="presentation-image object-contain flex-shrink-0"
            alt={`Presentation ${index + 1}`}
          />
        ))}
      </div>
    </div>
  );
};
```

---

*This guide provides comprehensive coverage of frontend-backend integration patterns. For backend-specific implementation details, see the [Backend Development Guide](./BACKEND_DEVELOPMENT.md).*