import { ApiResult, Inspection } from '@/types/api';
import { PresentationImage, RecentInspection } from '@/features/inspections/api/inspections-details';

// Camera Types
export type CameraType = 'basler' | 'webcam' | 'usb';

// Sensor Status Types
export interface SensorState {
  sensor_a: boolean;
  sensor_b: boolean;
  current_state: string;
  last_result: string | null;
}

export interface BufferStatus {
  is_recording: boolean;
  buffer_size: number;
  max_buffer_size: number;
}

export interface CaptureStatus {
  status: string;
  last_save_message: string;
  total_saves: number;
  total_discards: number;
  buffer_status: BufferStatus;
  sensor_a?: boolean;
  sensor_b?: boolean;
}

export interface InspectionDetail {
  id: number;
  error_type: number;
  error_type_name: string;
  x_position: number;
  y_position: number;
  width: number;
  height: number;
  length: number;
  confidence: number;
  image_path: string | null;
}

export interface InspectionData {
  inspection_id: number;
  inspection_details: InspectionDetail[];
  confidence_above_threshold: boolean;
  ai_threshold: number;
  results?: string;
  presentation_ready?: boolean;
  presentation_images?: PresentationImage[];
  inspection_dt?: string;
}

export interface InspectionResultData {
  inspection_id: number;
  discoloration: boolean;
  hole: boolean;
  knot: boolean;
  dead_knot: boolean;
  live_knot: boolean;
  tight_knot: boolean;
  length: number | null;
}

export interface SensorStatus {
  active: boolean;
  sensor_a: boolean;
  sensor_b: boolean;
  current_state: string;
  simulation_mode: boolean;
  sensors: SensorState;
  capture_status: CaptureStatus;
  inspection_data: InspectionData | null;
  inspection_results: InspectionResultData | null;
  inspection_results_loading?: boolean;
  inspection_results_error?: string | null;
}

// Event Types
export interface PresentationImagesUpdatedEvent extends CustomEvent {
  detail: {
    images: PresentationImage[];
    inspectionId: number;
    inspectionDt: string;
  };
}

export interface InspectionSavedEvent extends CustomEvent {
  detail: {
    timestamp: number;
    inspectionId?: number | null;
  };
}

// Component Props Types
export interface InspectionHeaderProps {
  title: string;
}

export interface CameraSelectorProps {
  selectedCameraType: CameraType;
  onCameraTypeChange: (type: CameraType) => void;
  disabled: boolean;
}

export interface AIThresholdInputProps {
  aiThreshold: number;
  setAiThreshold: (value: number) => void;
  disabled: boolean;
}

export interface StatusDisplayProps {
  status: string;
}

export interface ControlButtonsProps {
  onStart: () => void;
  onStop: () => void;
  onTop: () => void;
  isActive: boolean;
}

export interface SensorControlsProps {
  isActive: boolean;
  isSimulationMode: boolean;
  onTriggerTest: () => void;
  onToggleSensorA: () => void;
  onToggleSensorB: () => void;
  sensorAActive: boolean;
  sensorBActive: boolean;
}

export interface ControlPanelProps {
  selectedCameraType: CameraType;
  onCameraTypeChange: (type: CameraType) => void;
  aiThreshold: number;
  setAiThreshold: (value: number) => void;
  status: string;
  onStart: () => void;
  onStop: () => void;
  onTop: () => void;
  isActive: boolean;
  debugMode: boolean;
  isSimulationMode: boolean;
  showCameraSettings: boolean;
  onTriggerTest?: () => void;
  onToggleSensorA?: () => void;
  onToggleSensorB?: () => void;
  sensorAActive?: boolean;
  sensorBActive?: boolean;
}

export interface ResultDisplayProps {
  inspectionResult: string;
  defectType: string;
}

export interface PresentationImageCardProps {
  groupName: string;
  imagePath: string | null;
  inspectionId?: number;
  onImageTest?: (path: string) => void;
}

export interface PresentationImagesGridProps {
  presentationImages: PresentationImage[];
  loading: boolean;
  onImageTest?: (path: string) => void;
}

export interface MeasurementsDisplayProps {
  measurements: string;
  inspectionResult: string;
  defectType?: string;
}

export interface InspectionDisplayProps {
  inspectionResult: string;
  defectType: string;
  measurements: string;
  presentationImages: PresentationImage[];
  loadingPresentationImages: boolean;
  createdInspectionId: number | null;
  onShowDetail: (id: number) => void;
  onImageTest?: (path: string) => void;
}

export interface CameraPreviewProps {
  image: string | null;
  isConnected: boolean | null;
  selectedCameraType: CameraType;
  droppedFrame: boolean;
  onOpenModal: () => void;
}

export interface DebugPanelProps {
  debugMode: boolean;
  createdInspectionId: number | null;
  presentationImages: PresentationImage[];
  loadPresentationImages: (id: number) => Promise<void>;
  loadRecentInspections: () => Promise<void>;
  recentInspections: RecentInspection[];
  loadingPresentationImages: boolean;
  loadingInspections: boolean;
  onImageTest: (path: string) => void;
  showDebugPanel: boolean;
  setShowDebugPanel: (show: boolean) => void;
}

// Camera Error Types
export interface CameraError {
  type: 'network' | 'hardware' | 'configuration' | 'api' | 'unknown';
  message: string;
  details?: string;
  timestamp: number;
}

export interface NetworkStatus {
  isOnline: boolean;
  lastCheck: number;
  retryCount: number;
}

// Hook Return Types
export interface UseCameraManagementReturn {
  image: string | null;
  capturedImage: string | null;
  isConnected: boolean | null;
  droppedFrame: boolean;
  selectedCameraType: CameraType;
  handleCameraTypeChange: (newType: CameraType) => Promise<void>;
  cameraError: CameraError | null;
  networkStatus: NetworkStatus;
  clearError: () => void;
  stopCamera: () => Promise<void>;
}

export interface UseInspectionStateReturn {
  status: string;
  inspectionResult: string;
  defectType: string;
  measurements: string;
  createdInspectionId: number | null;
  presentationImages: PresentationImage[];
  loadingPresentationImages: boolean;
  selectedInspection: Inspection | null;
  showDetail: boolean;
  handleShowDetail: (id: number) => Promise<void>;
  setShowDetail: (show: boolean) => void;
  loadPresentationImages: (id: number) => Promise<void>;
}

export interface UseSensorMonitoringReturn {
  sensorStatus: SensorStatus;
  aiThreshold: number;
  setAiThreshold: (value: number) => void;
  handleStart: () => Promise<void>;
  handleStop: () => Promise<void>;
  triggerTestSequence: () => Promise<void>;
  toggleSensorA: () => Promise<void>;
  toggleSensorB: () => Promise<void>;
  fetchInspectionResults: (inspectionId: number) => Promise<void>;
}

export interface UseDebugModeReturn {
  debugMode: boolean;
  showDebugPanel: boolean;
  setShowDebugPanel: (show: boolean) => void;
  debugInspectionId: string;
  setDebugInspectionId: (id: string) => void;
  recentInspections: RecentInspection[];
  loadingInspections: boolean;
  loadingPresentationImages: boolean;
  loadRecentInspections: () => Promise<void>;
  loadImagesForInspectionId: (manualId?: number) => Promise<void>;
  testImageUrl: string;
  showTestImage: boolean;
  setShowTestImage: (show: boolean) => void;
  testImage: (imagePath: string) => void;
}