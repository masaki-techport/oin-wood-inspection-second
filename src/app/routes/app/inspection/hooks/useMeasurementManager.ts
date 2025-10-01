import { useState, useEffect, useMemo } from 'react';
import { useInspectionSettings } from './useInspectionSettings';
import { useSensorData } from './useSensorData';

/**
 * Centralized measurement manager that provides a single source of truth
 * for measurement calculations based on inspection results and defect types.
 * 
 * This hook eliminates the data source conflicts by:
 * 1. Using only useSensorData for real-time inspection results
 * 2. Using only useInspectionSettings for measurement configuration
 * 3. Providing a single calculation function
 */
export const useMeasurementManager = () => {
  const { settings, getMeasurementForDefectType } = useInspectionSettings();
  const { batchResult, defectType: sensorDefectType } = useSensorData();
  
  // Single source of truth for inspection result and defect type
  const inspectionResult = batchResult || '';
  const defectType = sensorDefectType || '';
  
  // Calculate measurement value using centralized logic
  const measurementValue = useMemo(() => {
    if (!settings || !inspectionResult) return '';
    
    const value = getMeasurementForDefectType(defectType, inspectionResult);
    console.log(`📏 [MeasurementManager] Calculation: result="${inspectionResult}", defectType="${defectType}", value=${value}`);
    return value;
  }, [settings, defectType, inspectionResult, getMeasurementForDefectType]);
  
  // Determine if measurement should be displayed
  const shouldShowMeasurement = Boolean(inspectionResult);
  
  // Listen for clear events to reset measurement display
  useEffect(() => {
    const onClear = () => {
      console.log('🧹 useMeasurementManager: Clearing measurement display due to inspection:clear event');
    };
    window.addEventListener('inspection:clear', onClear);
    return () => window.removeEventListener('inspection:clear', onClear);
  }, []);
  
  return {
    measurementValue,
    inspectionResult,
    defectType,
    shouldShowMeasurement,
    isLoading: !settings
  };
};
