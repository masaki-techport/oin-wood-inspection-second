import React, { useMemo } from 'react';
import { MeasurementsDisplayProps } from '../../types';
import { useInspectionSettings } from '../../hooks';

/**
 * Component for displaying measurement values based on inspection result and defect type
 */
const MeasurementsDisplay: React.FC<MeasurementsDisplayProps> = ({ measurements, inspectionResult, defectType }) => {
  const { settings, getMeasurementForDefectType } = useInspectionSettings();

  // Calculate measurement value based on defect type and inspection result
  const measurementValue = useMemo(() => {
    if (!settings || !inspectionResult) return '';
    return getMeasurementForDefectType(defectType || '', inspectionResult);
  }, [settings, defectType, inspectionResult, getMeasurementForDefectType]);

  return (
    <div className="absolute bottom-12 right-12 flex items-center gap-6">
      <span className="text-black text-2xl font-bold">歩出し</span>
      <div className={`${!inspectionResult ? 'bg-gray-200' : 'bg-white'} border-4 border-black px-8 py-4 rounded-lg shadow-lg`}>
        <span className="text-4xl font-bold">{inspectionResult ? measurementValue : ''}</span>
      </div>
      <span className="text-black text-2xl font-bold">mm</span>
    </div>
  );
};

export default MeasurementsDisplay;