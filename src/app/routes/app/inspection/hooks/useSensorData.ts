import { useState, useEffect, useRef } from 'react';
import { api } from '@/lib/api-client';
import { SensorStatus, InspectionData, InspectionDetail } from '../types';
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
      const data = await api.get('/api/sensor-inspection/status') as any;
      if (data && data.active) {
        setSensorStatus(data);
        
        // Always prefer fresh inspection_results data from database over cached inspection_data
        if (data.inspection_results) {
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
          
          // Determine knot status based on presence and length
          let knotStatus = '無欠点';
          if (hasAnyKnot) {
            knotStatus = knotLength > 10 ? '節あり' : 'こぶし';
          }
          
          // Determine defect type
          let defectTypeResult = '';
          if (hasHole && hasDiscoloration) {
            defectTypeResult = '穴●変色発生';
          } else if (hasHole) {
            defectTypeResult = '穴発生';
          } else if (hasDiscoloration) {
            defectTypeResult = '変色発生';
          }
          
          // Update state with results
          setBatchResult(knotStatus);
          setDefectType(defectTypeResult);
          setDbResultLoaded(true);
          
          console.log(`Using inspection_results: hasAnyKnot=${hasAnyKnot}, knotLength=${knotLength}, hasHole=${hasHole}, hasDiscoloration=${hasDiscoloration}, result="${knotStatus}", defectType="${defectTypeResult}"`);
        } else {
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
    
    // Determine knot status based on the largest knot length
    let knotStatus = '無欠点'; // Default: no defect
    if (hasAnyKnot) {
      knotStatus = maxKnotLength > 10 ? '節あり' : 'こぶし';
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

  useEffect(() => {
    // Initial fetch
    fetchSensorStatus();
    
    // Set up polling interval
    sensorStatusPollRef.current = setInterval(fetchSensorStatus, 1000); // Poll every 1 second
    
    // Cleanup function
    return () => {
      if (sensorStatusPollRef.current) {
        clearInterval(sensorStatusPollRef.current);
        sensorStatusPollRef.current = null;
      }
    };
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
      const response = await api.get(`/inspections/result`, { params: { inspection_id: inspectionId } });
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
        
        console.log(`Database result: hasAnyKnot=${hasAnyKnot}, knotLength=${knotLength}, hasHole=${hasHole}, hasDiscoloration=${hasDiscoloration}, result="${knotStatus}", defectType="${defectTypeResult}"`);
        
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