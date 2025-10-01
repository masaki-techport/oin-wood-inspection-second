import { useState, useEffect, useRef } from 'react';
import { api } from '@/lib/api-client';
import { SensorStatus, InspectionData, InspectionDetail } from '../types';
import { createStandardPollingManager } from '../utils/pollingManager';
import { determineInspectionResult, determineDefectType } from '../utils/colorManager';
import { dispatchSaveEvent } from '../utils';

/**
 * Custom hook to fetch and process sensor data for batch image processing
 * Provides unified logic for determining defect types and display results
 * @returns Processed batch inspection data and defect information
 */
export const useSensorData = () => {
  const [sensorStatus, setSensorStatus] = useState<SensorStatus | null>(null);
  const [batchResult, setBatchResult] = useState<string | null>(null);
  const [defectType, setDefectType] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [hasData, setHasData] = useState<boolean>(false);
  const [dbResultLoaded, setDbResultLoaded] = useState<boolean>(false);

  /**
   * Fetch sensor status data from the API
   */
  const fetchSensorStatus = async () => {
    setIsLoading(true);
    try {
      console.log('🔄 Fetching sensor status...');
      const data = await api.get('/sensor-inspection/status', {
        timeout: 8000, // Increased timeout for sensor polling
        suppressGlobalError: true // Suppress automatic error notifications for polling
      }) as any;
      
      console.log('✅ Sensor status received:', data);
      // Mirror core values globally for components that read window directly
      try {
        (window as any).sensorStatus = data;
        const imgs = Array.isArray((data as any)?.presentation_images)
          ? (data as any).presentation_images
          : undefined;
        if (imgs) (window as any).presentationImages = imgs;
        const cid = (data as any)?.inspection_data?.inspection_id || (data as any)?.inspection_results?.inspection_id;
        if (cid) (window as any).inspectionId = cid;
      } catch (_) {}
      console.log('✅ Sensor status active:', data?.active);
      console.log('✅ Sensor status sensors:', data?.sensors);
      console.log('✅ Sensor status capture:', data?.capture);
      // Always update sensor status, regardless of active state
      setSensorStatus(data);
      
      if (data && (data.active || data.inspection_results || data.inspection_data)) {
        // If backend indicates a new circle/processing, immediately clear any cached UI state
        const lastResult = (data?.sensors as any)?.last_result as string | undefined;
        const nonForwardResult = lastResult && lastResult !== 'pass_L_to_R';
        const isProcessing = Boolean(
          data?.capture?.status === '処理中' ||
          data?.sensors?.clear_requested === true ||
          data?.capture?.processing_active === true ||
          data?.processing_active === true ||
          nonForwardResult
        );
        if (isProcessing) {
          // Clear local derived states to avoid showing previous inspection results
          setBatchResult(null);
          setDefectType(null);
          setDbResultLoaded(false);
        }
        // Always prefer fresh inspection_results data from database over cached inspection_data
        if (!isProcessing && data.inspection_results) {
          console.log('Using fresh inspection_results data from database:', data.inspection_results);
          // Use this fresh data instead of processing from cached inspection_data
          const resultData = data.inspection_results;
          
          // Check for knot defects
          const hasAnyKnot = resultData.knot || resultData.dead_knot || resultData.live_knot || resultData.tight_knot;
          
          // Check for hole and discoloration
          const hasHole = resultData.hole;
          const hasDiscoloration = resultData.discoloration;
          
          // Get the length value
          const knotLength = resultData.length || 0;
          console.log(`🔍 DEBUG useSensorData RAW: resultData.length=${resultData.length}, knotLength=${knotLength}`);
          
          // Use centralized logic for determining inspection result and defect type
          const knotStatus = determineInspectionResult(hasAnyKnot, knotLength, hasHole, hasDiscoloration);
          const defectTypeResult = determineDefectType(hasHole, hasDiscoloration);
          
          // Update state with results
          setBatchResult(knotStatus);
          setDefectType(defectTypeResult);
          setDbResultLoaded(true);
          
          console.log(`Using inspection_results: hasAnyKnot=${hasAnyKnot}, knotLength=${knotLength}, hasHole=${hasHole}, hasDiscoloration=${hasDiscoloration}, result="${knotStatus}", defectType="${defectTypeResult}"`);
        } else if (!isProcessing) {
          // Fall back to processing inspection_data
          processBatchData(data.inspection_data);
        }
      }
    } catch (error) {
      console.error('Error fetching sensor status:', error);
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Process inspection details to determine defect types and display results
   * @param details The inspection details to analyze
   * @returns An object containing information about detected defects
   */
  const analyzeDefects = (details: InspectionDetail[]) => {
    // Find the knot with the largest length (most severe)
    let maxKnotLength = 0;
    
    // Check for different defect types
    let hasAnyKnot = false;
    let hasHole = false;
    let hasDiscoloration = false;
    
    details.forEach(detail => {
      // Error types 2-5 are various knot types
      const isKnot = detail.error_type >= 2 && detail.error_type <= 5;
      if (isKnot) {
        hasAnyKnot = true;
        if (detail.length > maxKnotLength) {
          maxKnotLength = detail.length;
        }
      }
      
      // Check for holes (error_type = 1)
      if (detail.error_type === 1) {
        hasHole = true;
      }
      
      // Check for discoloration (error_type = 0)
      if (detail.error_type === 0) {
        hasDiscoloration = true;
      }
    });
    
    // Use centralized logic for determining inspection result and defect type
    const knotStatus = determineInspectionResult(hasAnyKnot, maxKnotLength, hasHole, hasDiscoloration);
    const defectTypeResult = determineDefectType(hasHole, hasDiscoloration);
    
    return { 
      knotStatus, 
      defectType: defectTypeResult, 
      hasAnyKnot, 
      hasHole, 
      hasDiscoloration, 
      maxKnotLength 
    };
  };

  /**
   * Process batch data according to rules
   * @param inspectionData The inspection data to process
   */
  const processBatchData = (inspectionData: InspectionData | null) => {
    if (!inspectionData || !inspectionData.inspection_details || inspectionData.inspection_details.length === 0) {
      // Only set hasData to false if we've never had data before
      if (!hasData) {
        setHasData(false);
      }
      return;
    }

    // We have data now
    setHasData(true);

    const details = inspectionData.inspection_details;
    const { knotStatus, defectType: detectedDefectType, hasAnyKnot, hasHole, hasDiscoloration, maxKnotLength } = analyzeDefects(details);
    
    // Update state with the analysis results
    setBatchResult(knotStatus);
    setDefectType(detectedDefectType);

    console.log(`Batch processing: maxKnotLength=${maxKnotLength}, hasAnyKnot=${hasAnyKnot}, hasHole=${hasHole}, hasDiscoloration=${hasDiscoloration}, result="${knotStatus}", defectType="${detectedDefectType}"`);
  };

  // Set up polling for sensor status data
  const sensorStatusPollRef = useRef<NodeJS.Timeout | null>(null);
  
  // Add debounce mechanism to prevent rapid UI changes
  const lastResultRef = useRef<string | null>(null);
  const lastDefectTypeRef = useRef<string | null>(null);
  const resultStableCountRef = useRef<number>(0);
  const STABILITY_THRESHOLD = 2; // Number of consecutive identical results before updating UI

  // Add a ref to track when sensor was stopped to continue polling briefly for final results
  const sensorStoppedAtRef = useRef<number | null>(null);
  const STOP_GRACE_PERIOD = 10000; // Continue polling for 10 seconds after stop

  useEffect(() => {
    console.log('🚀 useSensorData useEffect started');
    // Initial fetch
    fetchSensorStatus();
    
    // Create standardized polling manager
    const pollingManager = createStandardPollingManager(
      async () => {
        console.log('🔄 Polling sensor status...');
        await fetchSensorStatus();
        
        // Check if sensor was just stopped and start grace period
        if (sensorStatus && !sensorStatus.active && sensorStoppedAtRef.current === null) {
          sensorStoppedAtRef.current = Date.now();
          console.log('🔍 Sensor stopped, continuing polling for final results...');
        }
        
        // Stop polling after grace period if sensor is inactive
        if (sensorStoppedAtRef.current && (Date.now() - sensorStoppedAtRef.current > STOP_GRACE_PERIOD)) {
          console.log('🔍 Grace period ended, stopping useSensorData polling');
          pollingManager.stop();
          return;
        }
        
        // Debounce logic to prevent flickering between classifications
        // But always update immediately for important results (節あり or 無欠点)
        const isLargeKnot = batchResult === '節あり';
        const isNoDefect = batchResult === '無欠点';
        
        // Always update immediately for these critical states
        if (isLargeKnot || isNoDefect) {
          resultStableCountRef.current = STABILITY_THRESHOLD;
          lastResultRef.current = batchResult;
          lastDefectTypeRef.current = defectType;
          console.log(`Priority result (${batchResult}) detected - updating immediately`);
        } else if (batchResult === lastResultRef.current && defectType === lastDefectTypeRef.current) {
          resultStableCountRef.current++;
          console.log(`Result "${batchResult}" stable for ${resultStableCountRef.current} polls`);
        } else {
          // Reset counter when result changes
          resultStableCountRef.current = 0;
          lastResultRef.current = batchResult;
          lastDefectTypeRef.current = defectType;
          console.log(`New result detected: "${batchResult}", defectType: "${defectType}", waiting for stability...`);
        }
      },
      (error) => {
        console.error('Error polling sensor status:', error);
      }
    );

    // Start polling
    pollingManager.start();

    // Cleanup function
    return () => {
      pollingManager.destroy();
    };
  }, [batchResult, defectType, sensorStatus]);

  // Listen for global clear event so all hook instances reset in sync
  useEffect(() => {
    const onClear = () => {
      console.log('🧹 useSensorData: Clearing cached data due to inspection:clear event');
      setBatchResult(null);
      setDefectType(null);
      setHasData(false);
      setDbResultLoaded(false);
      setSensorStatus(null);
    };
    window.addEventListener('inspection:clear', onClear);
    return () => window.removeEventListener('inspection:clear', onClear);
  }, []);

  /**
   * Fetch inspection result directly from database for a specific inspection ID
   * Maps database fields to UI display logic according to the following rules:
   * - If any knot with length > 10mm is detected, display "節あり"
   * - If any knot with length ≤ 10mm is detected, display "こぶし"
   * - If no knot is detected, display "無欠点"
   * - If hole is detected, include "穴発生" in defect type
   * - If discoloration is detected, include "変色発生" in defect type
   * - If both hole and discoloration are detected, include "穴●変色発生" in defect type
   * @param inspectionId The inspection ID to fetch results for
   * @returns The inspection result data from the database
   */
  const fetchInspectionResult = async (inspectionId: number) => {
    if (!inspectionId) return null;

    setIsLoading(true);
    try {
      // Endpoint is at /inspections/result without the /api prefix
      const response = await api.get(`/inspections/result`, { 
        params: { inspection_id: inspectionId },
        timeout: 8000,
        suppressGlobalError: true // Suppress automatic error notifications for inspection result fetching
      });
      console.log('Fetched inspection result from database:', response);
      if (response?.data) {
        // Process the database result
        const resultData = response.data;
        
        // Directly use the results from the inspection_results table
        // Check for knot defects (types 2-5)
        const hasAnyKnot = resultData.knot || resultData.dead_knot || resultData.live_knot || resultData.tight_knot;
        
        // Check for hole and discoloration
        const hasHole = resultData.hole;
        const hasDiscoloration = resultData.discoloration;
        
        // Get the length value from the database
        // The t_inspection_result table has a single length field for all defect types
        const knotLength = resultData.length || 0;
        
        // Determine knot status based on knot presence and length
        let knotStatus = '無欠点';
        if (hasAnyKnot) {
          knotStatus = knotLength > 10 ? '節あり' : 'こぶし';
        }
        
        // Determine defect type based on hole and discoloration
        let defectTypeResult = '';
        if (hasHole && hasDiscoloration) {
          defectTypeResult = '穴●変色発生';
        } else if (hasHole) {
          defectTypeResult = '穴発生';
        } else if (hasDiscoloration) {
          defectTypeResult = '変色発生';
        }
        
        // Update state with the analysis results
        setBatchResult(knotStatus);
        setDefectType(defectTypeResult);
        setDbResultLoaded(true);
        
        console.log(`🔍 DEBUG useSensorData: hasAnyKnot=${hasAnyKnot}, knotLength=${knotLength}, hasHole=${hasHole}, hasDiscoloration=${hasDiscoloration}, result="${knotStatus}", defectType="${defectTypeResult}"`);
        
        // Trigger presentation images loading via the event system
        // This ensures that presentation images and result display are synchronized
        console.log(`Dispatching event to load presentation images for inspection ID: ${inspectionId}`);
        dispatchSaveEvent(inspectionId);
        
        return resultData;
      }
    } catch (error) {
      console.error('Error fetching inspection result:', error);
      // In case of error, don't update the batch result
      // This will allow the component to fall back to other data sources
    } finally {
      setIsLoading(false);
    }
    return null;
  };

  // Expose fetchInspectionResult globally for stop handler to use
  useEffect(() => {
    (window as any).fetchInspectionResultFromSensorData = fetchInspectionResult;
    // Also expose a clear function so other hooks can reset sensor-derived UI state
    (window as any).clearSensorData = () => {
      setBatchResult(null);
      setDefectType(null);
      setHasData(false);
      setDbResultLoaded(false);
    };
    
    return () => {
      delete (window as any).fetchInspectionResultFromSensorData;
      delete (window as any).clearSensorData;
    };
  }, []);

  return {
    sensorStatus,
    batchResult,
    defectType,
    isLoading,
    hasData,
    dbResultLoaded,
    inspectionDetails: sensorStatus?.inspection_data?.inspection_details || [],
    fetchInspectionResult
  };
};