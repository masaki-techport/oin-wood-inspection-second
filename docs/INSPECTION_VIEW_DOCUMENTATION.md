# Inspection View Component Architecture Documentation

## Overview

The Inspection View is the core interface of the wood inspection system, designed to display real-time inspection results, control camera operations, and manage the inspection workflow. This document provides a comprehensive analysis of component display patterns, data flow, and architectural decisions.

## System Architecture Summary

The inspection view follows a **hierarchical component architecture** with **centralized state management** and **real-time data streaming**. The system is designed around a **database-first approach** where inspection results are primarily sourced from the database rather than sensor data to ensure consistency and reliability.

## Component Hierarchy and Display Structure

### 1. Main Container - InspectionScreen
**File**: `InspectionScreen.tsx`
**Role**: Root container component that orchestrates the entire inspection interface

#### Display Structure:
```
┌─────────────────────────────────────────────────────────────┐
│ InspectionScreen (Root Container)                           │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ InspectionHeader (Top Bar)                              │ │
│ └─────────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ ControlPanel (Control Interface)                        │ │
│ └─────────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Main Content Area (flex-1)                              │ │
│ │ ┌─────────────────────────────────────────────────────┐ │ │
│ │ │ InspectionDisplay (Primary Display)                 │ │ │
│ │ └─────────────────────────────────────────────────────┘ │ │
│ │ ┌─────────────────────────────────────────────────────┐ │ │
│ │ │ CameraPreview (Bottom-left, conditional)            │ │ │
│ │ └─────────────────────────────────────────────────────┘ │ │
│ │ ┌─────────────────────────────────────────────────────┐ │ │
│ │ │ DebugPanel (Bottom, conditional)                    │ │ │
│ │ └─────────────────────────────────────────────────────┘ │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

#### Key Layout Characteristics:
- **Full Screen Layout**: Uses `h-screen` for complete viewport coverage
- **Flex Column**: Vertical stacking with `flex flex-col`
- **Fixed Header & Control Panel**: Static positioning at top
- **Dynamic Content Area**: `flex-1` for remaining space
- **Absolute Positioned Overlays**: Camera preview and debug panels

### 2. Header Section - InspectionHeader
**File**: `InspectionHeader.tsx`
**Role**: Simple title bar using StandardHeader component

#### Display Features:
- Reuses `StandardHeader` component for consistency
- Shows "木材検査システム 検査" title
- Primary variant with logo display
- Fixed at top of viewport

### 3. Control Interface - ControlPanel
**File**: `ControlPanel.tsx`
**Role**: Centralized control interface for inspection operations

#### Display Components:
1. **CameraSelector** (conditional): Camera type dropdown (Basler/USB/Webcam)
2. **StatusDisplay**: Current system status (待機中/検査中/処理中/停止)
3. **ControlButtons**: Start/Stop/TOP navigation buttons
4. **SensorControls** (debug mode): Additional sensor testing controls

#### Layout Structure:
```
┌─────────────────────────────────────────────────────────────┐
│ Control Panel (Horizontal Flex, Centered)                  │
│ [Camera Selector] [Status Display] [Control Buttons]       │
│                                                             │
│ Debug Mode Only:                                            │
│ [Sensor Controls] [Test Button]                             │
└─────────────────────────────────────────────────────────────┘
```

### 4. Primary Display - InspectionDisplay
**File**: `InspectionDisplay.tsx`
**Role**: Main inspection results and image display area

#### Display Architecture:
The InspectionDisplay serves as the **primary visual container** with dynamic background colors and multiple overlaid elements:

```
┌─────────────────────────────────────────────────────────────┐
│ InspectionDisplay (Dynamic Background Color)                │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ ResultDisplay (Floating, Top-Center)                    │ │
│ │ • Inspection Result (節あり/無欠点/こぶし)               │ │
│ │ • Defect Type (穴発生/変色発生/穴●変色発生)              │ │
│ │ • Detailed Results Panel (Debug Mode)                   │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ PresentationImagesGrid (Center)                         │ │
│ │ • Groups A-E Image Display                              │ │
│ │ • Loading States                                        │ │
│ │ • Detail Button                                         │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ MeasurementsDisplay (Bottom-Right)                      │ │
│ │ • 歩出し Measurement Value                              │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

#### Dynamic Background Colors:
- **Green** (`bg-green-500`): 無欠点 (No defects)
- **Yellow** (`bg-yellow-500`): こぶし (Small knots)
- **Red** (`bg-red-500`): 節あり (Large knots/defects)
- **Gray** (`bg-gray-300`): No result/waiting state

### 5. Result Display - ResultDisplay
**File**: `ResultDisplay.tsx`
**Role**: Primary inspection result visualization

#### Display Elements:
1. **Primary Result Box**: Large white box with main classification
2. **Secondary Defect Type Box**: Orange box for hole/discoloration alerts
3. **Detailed Results Panel**: Expandable debug information (conditional)

#### Positioning Strategy:
- **Absolute Positioning**: `absolute top-6 left-1/2 transform -translate-x-1/2`
- **High Z-Index**: `z-10` to float above background
- **Responsive Text**: `text-4xl` for primary, `text-3xl` for secondary

#### Data Sources (Database-First):
1. **Primary**: `useSensorData().batchResult` (from database)
2. **Secondary**: `useSensorData().defectType` (processed from database)
3. **Fallback**: Props from parent component

### 6. Image Display - PresentationImagesGrid
**File**: `PresentationImagesGrid.tsx`
**Role**: Grid display of inspection result images

#### Grid Architecture:
```
┌─────────────────────────────────────────────────────────────┐
│ PresentationImagesGrid                                      │
│ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐                     │
│ │  A  │ │  B  │ │  C  │ │  D  │ │  E  │                     │
│ │Img  │ │ Img │ │ Img │ │ Img │ │ Img │                     │
│ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘                     │
│                                                             │
│ [検査結果詳細 Button]                                        │
└─────────────────────────────────────────────────────────────┘
```

#### Display States:
1. **Loading State**: Shows loading GIF with message
2. **Placeholder State**: Empty slots with group labels A-E
3. **Image State**: Actual inspection images with group labels
4. **Error Handling**: Fallback image loading with multiple URL attempts

#### Image Loading Strategy:
- **Eager Loading**: `loading="eager"` for immediate display
- **Multiple URL Attempts**: Progressive fallback for failed image loads
- **Error Recovery**: Loading GIF fallback for persistent failures

### 7. Individual Image Cards - PresentationImageCard
**File**: `PresentationImageCard.tsx`
**Role**: Single image display with group labeling

#### Card Structure:
```
┌─────────────────┐
│      Group A    │ ← Header with group name
├─────────────────┤
│                 │
│   [Image Area]  │ ← 4:3 aspect ratio container
│                 │
└─────────────────┘
```

#### Error Handling Features:
- **Progressive URL Construction**: Multiple image path attempts
- **DOM Safety Checks**: Prevents memory leaks during failures
- **Visual Feedback**: Loading indicators and error states

### 8. Measurements Display - MeasurementsDisplay
**File**: `MeasurementsDisplay.tsx`
**Role**: Shows calculated measurement values

#### Display Layout:
```
歩出し [Measurement Value] mm
```

#### Positioning:
- **Bottom-Right**: `absolute bottom-12 right-12`
- **Dynamic Styling**: Background changes based on inspection result
- **Calculated Values**: Uses `useInspectionSettings` for defect-specific measurements

### 9. Camera Preview - CameraPreview
**File**: `CameraPreview.tsx`
**Role**: Live camera feed preview (conditional display)

#### Display Characteristics:
- **Size**: 144px × 112px (`w-36 h-28`)
- **Position**: Bottom-left (`absolute bottom-6 left-6`)
- **Interactive**: Click to open modal view
- **Zoom Support**: Uses `react-zoom-pan-pinch` for interaction

#### Conditional Display:
Only shown when `showCameraUI` setting is enabled in settings.ini

### 10. Debug Panel - DebugPanel
**File**: `DebugPanel.tsx`
**Role**: Development and testing interface (conditional)

#### Debug Features:
- **Image Testing**: Upload and analyze test images
- **Recent Inspections**: Browse historical inspection data
- **Workflow Testing**: Test full BaslerCamera workflow
- **Presentation Processor**: Test image processing pipeline

#### Conditional Display:
Only shown when `debug_mode` is enabled in settings.ini

## Data Flow Architecture

### 1. State Management Pattern

The inspection view uses a **hook-based state management** pattern with specialized hooks:

```
┌─────────────────────────────────────────────────────────────┐
│ State Management Hooks                                      │
│                                                             │
│ useInspectionState     ← Main inspection data & images     │
│ useSensorData          ← Real-time sensor data processing  │
│ useSensorMonitoring    ← Sensor control & AI threshold     │
│ useCameraManagement    ← Camera operations & image feed    │
│ useDebugMode           ← Debug features & testing          │
│ useInspectionSettings  ← Settings & measurement values     │
└─────────────────────────────────────────────────────────────┘
```

### 2. Database-First Data Flow

The system implements a **database-first approach** to ensure data consistency:

```
Database (PostgreSQL)
       ↓
API Endpoints (/api/inspections/result)
       ↓
useSensorData Hook (fetchInspectionResult)
       ↓
ResultDisplay & InspectionDisplay Components
       ↓
UI Display (consistent results)
```

### 3. Real-time Data Streaming

Multiple data streams provide real-time updates:

```
Sensor Status API (/api/sensor-inspection/status)
       ↓
useSensorData Hook (1-second polling)
       ↓
State Updates (batchResult, defectType)
       ↓
Component Re-renders
```

### 4. Event-Driven Communication

Custom events coordinate between components:

```
inspectionDataUpdate     ← Inspection result updates
presentationImagesReady  ← Image processing completion
presentationImagesUpdated ← New images available
inspectionSaved          ← Database save completion
```

## Display Modes and States

### 1. Waiting State (待機中)
- Gray background (`bg-gray-300`)
- No result display
- Empty image placeholders
- System ready for inspection

### 2. Inspection Active (検査中)
- Status shows "検査中" 
- Camera feed active (if enabled)
- Waiting for sensor triggers
- Processing indicators visible

### 3. Processing State (処理中)
- Status shows "処理中"
- Images being analyzed
- Loading states in image grid
- Results pending

### 4. Results Display
- Dynamic background color based on result
- Primary result in large white box
- Secondary defect types in orange box
- Image grid with actual inspection images
- Measurement values calculated and displayed

### 5. Debug Mode Enhancements
- Additional sensor controls
- Debug panel with testing tools
- Detailed result information
- Recent inspection browsing

## Responsive Design Considerations

### 1. Layout Adaptability
- **Flex-based Layout**: Adapts to different screen sizes
- **Responsive Text**: Text sizes scale with screen size
- **Dynamic Image Sizing**: Images scale based on viewport

### 2. Image Grid Optimization
- **Aspect Ratio Preservation**: 4:3 aspect ratio for wood inspection images
- **Conservative Sizing**: Prevents scrollbars on smaller screens
- **Flexible Grid**: Adapts to available space

### 3. Component Positioning
- **Absolute Positioning**: For floating elements like result display
- **Relative Units**: Uses viewport units (vw, vh) for scalability
- **Safe Margins**: Prevents UI elements from being cut off

## Performance Optimizations

### 1. Component Memoization
- `React.memo()` wrapping for expensive components
- Memoized calculations using `useMemo()`
- Callback memoization with `useCallback()`

### 2. Image Loading Strategy
- **Eager Loading**: For critical presentation images
- **Progressive Enhancement**: Multiple fallback URL attempts
- **Preloading**: Background preloading of expected images

### 3. Polling Optimization
- **Debounced Updates**: Prevents rapid UI flicker
- **Intelligent Intervals**: Different polling rates for different data types
- **Cleanup Management**: Proper cleanup of intervals and timeouts

## Integration Points

### 1. API Endpoints
- `/api/sensor-inspection/status` - Real-time sensor status
- `/api/inspections/result` - Database inspection results
- `/api/file` - Image serving with conversion
- `/api/settings/*` - Configuration management

### 2. Configuration Dependencies
- `settings.ini` - Debug mode and camera UI toggles
- `streaming_config.json` - Real-time data configuration
- `inspections.yaml` - Inspection workflow settings

### 3. External Libraries
- `react-zoom-pan-pinch` - Camera preview interaction
- `lucide-react` - Icon components
- React Query - API state management
- Zustand - Global state management

## Error Handling and Recovery

### 1. Image Loading Failures
- **Progressive URL Attempts**: Multiple image path constructions
- **Graceful Degradation**: Loading GIF fallbacks
- **DOM Safety**: Memory leak prevention during failures

### 2. API Communication Errors
- **Retry Logic**: Automatic retry with exponential backoff
- **Fallback Data**: Use cached or default data when APIs fail
- **User Feedback**: Clear error messages and recovery options

### 3. State Inconsistency Prevention
- **Database-First**: Single source of truth from database
- **Event Coordination**: Synchronized updates across components
- **Validation**: Data consistency checks before state updates

## Accessibility Considerations

### 1. Visual Indicators
- **High Contrast**: Clear distinction between different result states
- **Color Independence**: Text labels complement color coding
- **Size Flexibility**: Scalable text and UI elements

### 2. Interaction Design
- **Keyboard Navigation**: Focus management for interactive elements
- **Click Targets**: Adequate size for touch interaction
- **Loading States**: Clear feedback during async operations

### 3. Screen Reader Support
- **Alt Text**: Descriptive alt text for images
- **ARIA Labels**: Semantic labeling for complex UI elements
- **Status Announcements**: Dynamic content updates

## Future Enhancement Opportunities

### 1. Mobile Optimization
- **Touch Gestures**: Enhanced touch interaction for image viewing
- **Responsive Breakpoints**: Mobile-specific layout adjustments
- **Offline Support**: Progressive Web App capabilities

### 2. Advanced Visualization
- **3D Rendering**: Three-dimensional defect visualization
- **Interactive Annotations**: Clickable defect regions
- **Measurement Tools**: Visual measurement overlays

### 3. Real-time Collaboration
- **Multi-user Support**: Shared inspection sessions
- **Live Updates**: Real-time synchronization across devices
- **Annotation Sharing**: Collaborative defect marking

## Conclusion

The Inspection View represents a sophisticated interface that balances real-time performance requirements with data consistency and user experience. The database-first architecture ensures reliable results while the component hierarchy provides clear separation of concerns and maintainable code structure.

The system's event-driven communication pattern and hook-based state management create a flexible foundation that can adapt to future requirements while maintaining the robust performance needed for industrial inspection applications.