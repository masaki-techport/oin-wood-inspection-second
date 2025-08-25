// Global type declarations
import { SensorStatusData } from '../app/routes/app/inspection/types/streaming';

interface Window {
  loadPresentationImages?: (id: number) => void;
  inspectionId?: number;
  updateInspectionResultFromSensorStatus?: (sensorStatus: SensorStatusData) => void;
  clearInspectionResults?: () => void;
  debugFallbackImageLoading?: boolean;
  fetchInspectionResults?: (id: number) => void;
}