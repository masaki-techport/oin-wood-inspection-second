// Extend the Window interface to include our custom properties
interface Window {
  loadPresentationImages?: (id: number) => void;
  inspectionId?: number;
  updateInspectionResultFromSensorStatus?: (sensorStatus: any) => void;
  clearInspectionResults?: () => void;
  debugFallbackImageLoading?: boolean;
}