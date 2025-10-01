# Current System Analysis and Implementation Plan for Abnormal Case Handling

## Current System Analysis

### 1. Current Sensor Monitoring Behavior
Based on the code analysis, the current system has these characteristics:

#### Frontend (InspectionScreen.tsx):
- **Issue ①**: Sensor monitoring starts immediately when the component mounts via `useSensorMonitoring` hook
- The hook polls `/api/sensor-inspection/status` every 1 second automatically
- This causes previous results to appear when navigating back to the inspection view
- The polling happens regardless of whether the 開始 button has been pressed

#### Backend (sensor_inspection.py):
- **Status Endpoint**: `/sensor-inspection/status` returns sensor data even when not officially "started"
- **Start Endpoint**: `/sensor-inspection/start` initializes the monitoring system
- **Stop Endpoint**: `/sensor-inspection/stop` cleans up resources

#### Navigation System:
- Uses React Router with `createBrowserRouter`
- Has basic `beforeunload` handling in `main-provider.tsx` but commented out `popstate` handling
- No current session/tab management system
- No inspection state persistence across browser actions

### 2. Current Browser Event Handling
The system currently has:
- Basic `beforeunload` event handling in `AppProvider` (main-provider.tsx)
- Commented out `popstate` event handling (back button)
- Navigation guard in `useNavigate` hook for dirty state confirmation
- No specific inspection process protection

### 3. Current Data Sources
- **Database-first approach**: Primary data from PostgreSQL via API
- **Real-time polling**: 1-second intervals to sensor status endpoint  
- **State management**: Hook-based with `useSensorMonitoring`, `useInspectionState`
- **Global state**: Zustand store for app-level state

## Issues Identified

### ① Sensor Watching Before 開始 Button
**Root Cause**: `useSensorMonitoring` hook automatically starts polling on component mount
**Impact**: Shows previous inspection results when navigating back to inspection view
**Location**: `hooks/useSensorMonitoring.ts` lines 238-272 (polling logic)

### ② Multiple Tab Concurrent Access
**Root Cause**: No session/tab management or inspection process locking
**Impact**: Multiple tabs can start inspection simultaneously
**Missing**: Tab instance identification and backend process locking

### ③ Browser Navigation During Inspection
**Root Cause**: No specific event handling for inspection process protection
**Impact**: Users can navigate away during inspection without proper cleanup
**Missing**: Inspection-aware navigation guards and cleanup procedures

## Implementation Plan

### Phase 1: Fix Sensor Watching Issue (① Priority: High)

#### 1.1 Modify Sensor Monitoring Hook
**File**: `src/app/routes/app/inspection/hooks/useSensorMonitoring.ts`

**Changes**:
- Add a `shouldPoll` parameter to control when polling starts
- Only start polling when inspection is actively started
- Separate status checking from active monitoring

**Implementation**:
```typescript
// Add new state for polling control
const [shouldStartPolling, setShouldStartPolling] = useState(false);

// Modify handleStart to enable polling
const handleStart = async () => {
  // ... existing start logic
  setShouldStartPolling(true);
  // Start polling after successful API call
};

// Modify handleStop to disable polling
const handleStop = async () => {
  // Stop polling first
  setShouldStartPolling(false);
  // ... existing stop logic
};

// Conditional polling based on shouldStartPolling flag
useEffect(() => {
  if (shouldStartPolling && sensorStatus.active) {
    // Start polling interval
  } else {
    // Clear polling interval
  }
}, [shouldStartPolling, sensorStatus.active]);
```

#### 1.2 Update Backend Status Logic
**File**: `src-api/source/endpoints/sensor_inspection.py`

**Changes**:
- Add `inspection_active` flag to distinguish between system status and active inspection
- Modify status endpoint to return different data based on inspection state
- Clear previous results when starting new inspection

### Phase 2: Multi-Tab Session Management (② Priority: High)

#### 2.1 Create Session Management Service
**New File**: `src/services/SessionManager.ts`

**Features**:
- Unique tab instance ID generation
- Session storage for tab identification
- Inspection process locking mechanism
- Cross-tab communication via BroadcastChannel API

**Implementation**:
```typescript
export class SessionManager {
  private tabId: string;
  private inspectionChannel: BroadcastChannel;
  
  constructor() {
    this.tabId = this.generateTabId();
    this.inspectionChannel = new BroadcastChannel('inspection-process');
  }
  
  requestInspectionLock(): Promise<boolean> {
    // Check if another tab has active inspection
    // Use BroadcastChannel for cross-tab communication
  }
  
  releaseInspectionLock(): void {
    // Release the inspection lock
  }
}
```

#### 2.2 Backend Process Locking
**File**: `src-api/source/endpoints/sensor_inspection.py`

**Changes**:
- Add session tracking for active inspections
- Implement mutex lock for inspection start/stop
- Return error when inspection already active in another session

### Phase 3: Browser Navigation Protection (③ Priority: Medium)

#### 3.1 Enhanced Navigation Guards
**File**: `src/app/routes/app/inspection/hooks/useInspectionNavigationGuard.ts`

**Features**:
- Inspection state-aware navigation blocking
- Custom confirmation dialogs based on inspection phase
- Proper cleanup procedures for different exit scenarios

**Implementation**:
```typescript
export const useInspectionNavigationGuard = (isActive: boolean, isProcessing: boolean) => {
  // Handle beforeunload (close/refresh)
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (isActive || isProcessing) {
        const message = "検査を終了してよろしいですか？";
        e.returnValue = message;
        return message;
      }
    };
    
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [isActive, isProcessing]);
  
  // Handle popstate (back button)
  useEffect(() => {
    const handlePopState = (e: PopStateEvent) => {
      if (isActive || isProcessing) {
        // Show custom modal instead of browser confirm
        e.preventDefault();
        // Implement custom modal logic
      }
    };
    
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, [isActive, isProcessing]);
};
```

#### 3.2 Custom Confirmation Modals
**New Component**: `src/components/modal/InspectionExitConfirmation.tsx`

**Features**:
- Different messages based on inspection state
- Proper cleanup options (complete current process vs force exit)
- Integration with session management for lock release

### Phase 4: Integration and State Management

#### 4.1 Update InspectionScreen Component
**File**: `src/app/routes/app/inspection/InspectionScreen.tsx`

**Changes**:
- Integrate session management
- Add navigation guard hook
- Implement proper state cleanup procedures

#### 4.2 Enhanced State Management
**Updates**:
- Add inspection process state to Zustand store
- Implement proper state persistence across navigation
- Add tab instance tracking

## Implementation Timeline

### Week 1: Core Infrastructure
- [ ] Implement sensor monitoring control (Issue ①)
- [ ] Create session management service foundation
- [ ] Update backend process locking

### Week 2: Multi-Tab Management
- [ ] Complete session management implementation (Issue ②)  
- [ ] Add cross-tab communication
- [ ] Backend session tracking

### Week 3: Navigation Protection
- [ ] Implement navigation guards (Issue ③)
- [ ] Create custom confirmation modals
- [ ] Integration testing

### Week 4: Testing and Refinement
- [ ] Comprehensive testing across scenarios
- [ ] Performance optimization
- [ ] Documentation updates

## Technical Considerations

### 1. Browser Compatibility
- BroadcastChannel API support (IE11+ not supported, but modern browsers OK)
- beforeunload/popstate event handling differences across browsers
- Session storage limitations and cleanup

### 2. Performance Impact
- Polling frequency optimization when multiple tabs open
- Memory management for session tracking
- Network request optimization

### 3. User Experience
- Non-blocking modal dialogs for better UX
- Clear messaging about inspection state
- Graceful degradation when features not supported

### 4. Error Handling
- Network failure during inspection process
- Browser crash recovery
- Session timeout handling

## Testing Strategy

### 1. Unit Testing
- Session management functions
- Navigation guard logic
- State management updates

### 2. Integration Testing  
- Multi-tab scenarios
- Browser navigation edge cases
- Backend process locking

### 3. User Acceptance Testing
- Real-world inspection workflows
- Browser compatibility testing
- Performance under load

## Documentation Requirements

### 1. Technical Documentation
- Session management API reference
- Navigation guard usage guide
- Troubleshooting guide for common issues

### 2. User Documentation
- Multi-tab usage guidelines
- Expected behavior during inspection process
- Error message explanations

This comprehensive plan addresses all three identified issues while maintaining system reliability and user experience. The phased approach ensures minimal disruption to current operations while systematically improving the abnormal case handling.