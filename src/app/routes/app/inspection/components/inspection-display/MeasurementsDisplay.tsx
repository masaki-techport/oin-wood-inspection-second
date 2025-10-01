import React from 'react';
import { useMeasurementManager } from '../../hooks/useMeasurementManager';

/**
 * Component for displaying measurement values based on inspection result and defect type.
 * Now uses centralized measurement manager to eliminate data source conflicts.
 */
const MeasurementsDisplay: React.FC = () => {
  const { measurementValue, inspectionResult, shouldShowMeasurement, isLoading } = useMeasurementManager();

  // Hide measurement when processing temp sections/new circle
  try {
    const ss: any = (window as any).sensorStatus;
    const createdInspectionId = (window as any).inspectionId as number | undefined;
    const images = (window as any).presentationImages as any[] | undefined;
    const isProcessing = Boolean(
      ss?.capture?.status === '処理中' ||
      ss?.sensors?.clear_requested === true ||
      ss?.capture?.processing_active === true ||
      ss?.processing_active === true
    );
    const mismatchedImages = Array.isArray(images) && images.length > 0 &&
      createdInspectionId && images.some(img => img?.inspection_id !== createdInspectionId);
    if (isProcessing || mismatchedImages) {
      return null;
    }
  } catch (_) { /* noop */ }

  return (
    <div className="absolute bottom-12 right-12 flex items-center gap-6">
      <span className="text-black text-2xl font-bold">歩出し</span>
      <div className={`${!shouldShowMeasurement ? 'bg-gray-200' : 'bg-white'} border-4 border-black px-8 py-4 rounded-lg shadow-lg`}>
        <span className="text-4xl font-bold">
          {isLoading ? '...' : (shouldShowMeasurement ? measurementValue : '')}
        </span>
      </div>
      <span className="text-black text-2xl font-bold">mm</span>
    </div>
  );
};

export default MeasurementsDisplay;