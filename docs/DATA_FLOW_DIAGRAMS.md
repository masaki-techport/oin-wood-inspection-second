# Data Flow Diagrams - Wood Inspection System

## 🔄 System Data Flow Overview

This document provides comprehensive diagrams illustrating how data flows through the Wood Inspection System, from hardware sensors to user interface display.

## 📊 High-Level System Architecture

```mermaid
graph TB
    subgraph "Hardware Layer"
        H1[Basler Camera]
        H2[Sensor A]
        H3[Sensor B]
        H4[DIO Device]
    end
    
    subgraph "Backend Services"
        B1[Camera Manager]
        B2[Sensor Monitor]
        B3[State Machine]
        B4[AI Inference Engine]
        B5[Database Services]
        B6[API Endpoints]
        B7[Streaming Services]
    end
    
    subgraph "Communication Layer"
        C1[HTTP REST APIs]
        C2[WebSocket Connections]
        C3[Server-Sent Events]
        C4[File Streaming]
    end
    
    subgraph "Frontend Application"
        F1[API Client]
        F2[State Management Hooks]
        F3[React Components]
        F4[User Interface]
    end
    
    subgraph "Data Storage"
        D1[(PostgreSQL Database)]
        D2[File System Images]
        D3[Configuration Files]
    end
    
    H1 --> B1
    H2 --> B2
    H3 --> B2
    H4 --> B2
    
    B1 --> B4
    B2 --> B3
    B3 --> B5
    B4 --> B5
    B5 --> D1
    B1 --> D2
    
    B6 --> C1
    B7 --> C2
    B7 --> C3
    B6 --> C4
    
    C1 --> F1
    C2 --> F1
    C3 --> F1
    C4 --> F1
    
    F1 --> F2
    F2 --> F3
    F3 --> F4
    
    B5 --> D1
    D3 --> B6
    
    style H1 fill:#fff3e0
    style H2 fill:#fff3e0
    style H3 fill:#fff3e0
    style H4 fill:#fff3e0
    style B1 fill:#f3e5f5
    style B2 fill:#f3e5f5
    style B3 fill:#f3e5f5
    style B4 fill:#f3e5f5
    style B5 fill:#f3e5f5
    style B6 fill:#f3e5f5
    style B7 fill:#f3e5f5
    style F1 fill:#e1f5fe
    style F2 fill:#e1f5fe
    style F3 fill:#e1f5fe
    style F4 fill:#e1f5fe
    style D1 fill:#e8f5e8
    style D2 fill:#e8f5e8
    style D3 fill:#e8f5e8
```

## 🔍 Inspection Process Flow

```mermaid
sequenceDiagram
    participant U as User Interface
    participant SM as useSensorMonitoring
    participant API as Backend API
    participant SS as Sensor System
    participant CM as Camera Manager
    participant AI as AI Inference
    participant DB as Database
    participant IS as useInspectionState
    participant UI as UI Components
    
    U->>SM: Click "Start" button
    SM->>API: POST /sensor-inspection/start
    API->>SS: Initialize sensors
    API->>CM: Start camera capture
    SS-->>API: Sensor status updates
    
    loop Real-time Monitoring
        SM->>API: GET /sensor-inspection/status
        API-->>SM: Sensor status + inspection data
        SM->>IS: Update inspection state
    end
    
    SS->>CM: Trigger image capture
    CM->>AI: Process captured images
    AI->>DB: Save inspection results
    DB-->>API: Return inspection ID
    
    IS->>API: GET /inspections/presentation-images
    API->>DB: Query presentation images
    DB-->>API: Return image metadata
    API-->>IS: Image paths and IDs
    
    IS->>API: GET /file?path=image_path
    API-->>IS: Actual image data
    IS->>UI: Update presentation display
    
    U->>SM: Click "Stop" button
    SM->>API: POST /sensor-inspection/stop
    API->>SS: Stop sensor monitoring
    API->>CM: Stop camera capture
```

## 🎯 Real-time Data Streaming

```mermaid
graph LR
    subgraph "Data Sources"
        A[Sensor Hardware]
        B[Camera Stream]
        C[AI Processing]
        D[Database Changes]
    end
    
    subgraph "Backend Streaming"
        E[Sensor Monitor]
        F[WebSocket Manager]
        G[SSE Handler]
        H[File Stream API]
    end
    
    subgraph "Frontend Hooks"
        I[useSensorMonitoring]
        J[useInspectionState]
        K[useCameraManagement]
        L[useStreamingData]
    end
    
    subgraph "UI Components"
        M[ControlPanel]
        N[ResultDisplay]
        O[CameraPreview]
        P[PresentationGrid]
    end
    
    A --> E
    B --> E
    C --> E
    D --> E
    
    E --> F
    E --> G
    E --> H
    
    F --> I
    G --> J
    H --> K
    F --> L
    
    I --> M
    J --> N
    K --> O
    L --> P
    
    style A fill:#ffeb3b
    style B fill:#ffeb3b
    style C fill:#ffeb3b
    style D fill:#ffeb3b
    style E fill:#4caf50
    style F fill:#4caf50
    style G fill:#4caf50
    style H fill:#4caf50
    style I fill:#2196f3
    style J fill:#2196f3
    style K fill:#2196f3
    style L fill:#2196f3
    style M fill:#9c27b0
    style N fill:#9c27b0
    style O fill:#9c27b0
    style P fill:#9c27b0
```

## 📸 Image Processing Pipeline

```mermaid
flowchart TD
    A[Image Capture Trigger] --> B[Camera Buffer]
    B --> C[Frame Extraction]
    C --> D[AI Analysis]
    D --> E{Has Defects?}
    
    E -->|Yes| F[Generate Bounding Boxes]
    E -->|No| G[Mark as Clean]
    
    F --> H[Create Presentation Images]
    G --> H
    
    H --> I[Save to File System]
    I --> J[Store Metadata in DB]
    J --> K[Trigger Database Event]
    
    K --> L[Frontend Polling Detects]
    L --> M[Fetch Image Metadata]
    M --> N[Generate Image URLs]
    N --> O[Preload Images]
    O --> P[Display in UI]
    
    subgraph "Backend Processing"
        B
        C
        D
        E
        F
        G
        H
        I
        J
        K
    end
    
    subgraph "Frontend Processing"
        L
        M
        N
        O
        P
    end
    
    style A fill:#ff9800
    style D fill:#4caf50
    style I fill:#2196f3
    style P fill:#9c27b0
```

## 🔄 State Management Data Flow

```mermaid
graph TB
    subgraph "Frontend State Management"
        A[useInspectionState]
        B[useSensorMonitoring]
        C[useSensorData]
        D[useCameraManagement]
    end
    
    subgraph "Shared State"
        E[Inspection Results]
        F[Sensor Status]
        G[Presentation Images]
        H[Camera State]
    end
    
    subgraph "Backend APIs"
        I[/api/inspections/latest]
        J[/api/sensor-inspection/status]
        K[/api/inspections/presentation-images]
        L[/api/camera/preview]
    end
    
    subgraph "UI Components"
        M[InspectionScreen]
        N[ControlPanel]
        O[ResultDisplay]
        P[PresentationGrid]
        Q[CameraPreview]
    end
    
    A --> E
    B --> F
    C --> E
    D --> H
    
    A --> G
    
    E --> I
    F --> J
    G --> K
    H --> L
    
    I --> A
    J --> B
    K --> A
    L --> D
    
    A --> M
    B --> N
    A --> O
    A --> P
    D --> Q
    
    style A fill:#e1f5fe
    style B fill:#e1f5fe
    style C fill:#e1f5fe
    style D fill:#e1f5fe
    style E fill:#f3e5f5
    style F fill:#f3e5f5
    style G fill:#f3e5f5
    style H fill:#f3e5f5
    style I fill:#e8f5e8
    style J fill:#e8f5e8
    style K fill:#e8f5e8
    style L fill:#e8f5e8
```

## 🔌 API Communication Patterns

```mermaid
sequenceDiagram
    participant C as React Component
    participant RQ as React Query
    participant AC as API Client
    participant RT as Retry Manager
    participant BE as Backend API
    participant DB as Database
    
    Note over C,DB: Synchronous Data Fetching
    
    C->>RQ: useQuery hook call
    RQ->>AC: Check cache, then fetch
    AC->>RT: Apply retry logic
    RT->>BE: HTTP request
    BE->>DB: Query database
    DB-->>BE: Return data
    BE-->>RT: JSON response (base64 encoded)
    RT-->>AC: Success/error handling
    AC-->>RQ: Cache and return
    RQ-->>C: Update component state
    
    Note over C,DB: Error Handling Flow
    
    RT->>RT: Retry with backoff
    RT->>AC: Circuit breaker check
    AC->>AC: Global error handling
    AC->>RQ: Notification system
    RQ->>C: Error state update
```

## 📊 Database Schema Relationships

```mermaid
erDiagram
    Inspection ||--o{ InspectionResult : has
    Inspection ||--o{ InspectionDetails : contains
    Inspection ||--o{ InspectionPresentation : displays
    Inspection ||--o{ InspectionImages : stores
    Product ||--o{ Inspection : undergoes
    Setting ||--|| System : configures
    
    Inspection {
        int inspection_id PK
        datetime inspection_dt
        string product_no FK
        boolean status
        text measurements
        blob image_data
    }
    
    InspectionResult {
        int result_id PK
        int inspection_id FK
        boolean knot
        boolean dead_knot
        boolean live_knot
        boolean tight_knot
        float length
        boolean hole
        boolean discoloration
        datetime created_at
    }
    
    InspectionDetails {
        int detail_id PK
        int inspection_id FK
        int error_type
        float length
        float confidence
        text coordinates
        text additional_data
    }
    
    InspectionPresentation {
        int presentation_id PK
        int inspection_id FK
        string image_path
        int group_number
        int image_order
        datetime created_at
    }
    
    InspectionImages {
        int image_id PK
        int inspection_id FK
        string image_path
        string image_type
        blob image_data
        datetime captured_at
    }
    
    Product {
        string product_no PK
        string product_name
        text specifications
        boolean active
    }
    
    Setting {
        int setting_id PK
        string setting_key
        string setting_value
        text description
        datetime updated_at
    }
```

## 🎨 Frontend Component Data Flow

```mermaid
flowchart TD
    A[InspectionScreen] --> B[ControlPanel]
    A --> C[InspectionDisplay]
    A --> D[CameraPreview]
    A --> E[DebugPanel]
    
    B --> F[StatusDisplay]
    B --> G[ControlButtons]
    B --> H[AIThresholdInput]
    B --> I[SensorControls]
    
    C --> J[ResultDisplay]
    C --> K[MeasurementsDisplay]
    C --> L[PresentationImagesGrid]
    
    L --> M[PresentationImageCard]
    M --> N[ImagePreviewDialog]
    
    subgraph "State Hooks"
        O[useInspectionState]
        P[useSensorMonitoring]
        Q[useCameraManagement]
        R[useDebugMode]
    end
    
    A --> O
    A --> P
    A --> Q
    A --> R
    
    O --> J
    O --> K
    O --> L
    P --> F
    P --> G
    P --> I
    Q --> D
    R --> E
    
    style A fill:#1976d2
    style O fill:#388e3c
    style P fill:#388e3c
    style Q fill:#388e3c
    style R fill:#388e3c
    style J fill:#7b1fa2
    style K fill:#7b1fa2
    style L fill:#7b1fa2
```

## 🔄 Real-time Update Cycle

```mermaid
graph LR
    subgraph "1. Data Generation"
        A[Hardware Sensors]
        B[Camera Capture]
        C[AI Processing]
    end
    
    subgraph "2. Backend Processing"
        D[Event Detection]
        E[Data Validation]
        F[Database Update]
    end
    
    subgraph "3. Communication"
        G[WebSocket Broadcast]
        H[HTTP Polling]
        I[SSE Streaming]
    end
    
    subgraph "4. Frontend Processing"
        J[State Update]
        K[Component Re-render]
        L[UI Feedback]
    end
    
    A --> D
    B --> D
    C --> D
    
    D --> E
    E --> F
    F --> G
    F --> H
    F --> I
    
    G --> J
    H --> J
    I --> J
    
    J --> K
    K --> L
    
    L -.-> A
    
    style A fill:#ff5722
    style D fill:#4caf50
    style G fill:#2196f3
    style J fill:#9c27b0
```

## ⚡ Performance Optimization Flow

```mermaid
flowchart TD
    A[API Request] --> B{Cache Hit?}
    B -->|Yes| C[Return Cached Data]
    B -->|No| D[Network Request]
    
    D --> E{Error?}
    E -->|Yes| F[Retry Logic]
    E -->|No| G[Process Response]
    
    F --> H{Max Retries?}
    H -->|Yes| I[Circuit Breaker]
    H -->|No| D
    
    G --> J[Update Cache]
    J --> K[Preload Related Data]
    K --> L[Update UI]
    
    I --> M[Error Notification]
    C --> L
    
    subgraph "Image Processing"
        N[Image Request] --> O[Check Preload Cache]
        O -->|Hit| P[Immediate Display]
        O -->|Miss| Q[Background Load]
        Q --> R[Progressive Enhancement]
    end
    
    L --> N
    
    style A fill:#2196f3
    style C fill:#4caf50
    style D fill:#ff9800
    style I fill:#f44336
    style P fill:#4caf50
    style Q fill:#ff9800
```

## 🔧 Development Data Flow

```mermaid
graph TB
    subgraph "Development Environment"
        A[React Dev Server<br/>localhost:3000]
        B[setupProxy.js<br/>Proxy Configuration]
        C[FastAPI Backend<br/>localhost:8000]
    end
    
    subgraph "Production Environment"
        D[Built React App<br/>Static Files]
        E[FastAPI Server<br/>+ Static Serving]
        F[PostgreSQL Database]
    end
    
    A --> B
    B --> C
    
    D --> E
    E --> F
    
    subgraph "API Path Resolution"
        G[Development: /api → proxy → localhost:8000]
        H[Production: /api → direct backend]
    end
    
    B --> G
    E --> H
    
    style A fill:#64b5f6
    style C fill:#81c784
    style D fill:#64b5f6
    style E fill:#81c784
    style F fill:#ffb74d
```

---

*These diagrams provide a visual representation of the complete data flow architecture. For implementation details, refer to the [System Architecture](./SYSTEM_ARCHITECTURE.md) and [Frontend Integration Guide](./FRONTEND_INTEGRATION.md).*