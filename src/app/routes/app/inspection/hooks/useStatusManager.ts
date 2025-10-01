import { useState, useEffect, useCallback } from 'react';
import { SensorStatus } from '../types';

/**
 * Centralized status management hook
 * Provides single source of truth for system status
 */
export const useStatusManager = () => {
  const [status, setStatus] = useState('待機中');

  /**
   * Centralized status determination logic
   * Single source of truth for status calculation
   * Optimized for immediate response times with early returns
   */
  const determineStatus = useCallback((sensorStatus: SensorStatus | null): string => {
    console.log('🔍 determineStatus called with:', sensorStatus);
    
    // Early returns for immediate response
    if (!sensorStatus || !sensorStatus.active) {
      console.log('❌ No sensor status or not active, returning 待機中');
      return '待機中';
    }

    // Get current sensor state for more specific status determination
    const currentState = sensorStatus.sensors?.current_state || sensorStatus.current_state;
    const sensorA = sensorStatus.sensor_a || sensorStatus.sensors?.sensor_a;
    const sensorB = sensorStatus.sensor_b || sensorStatus.sensors?.sensor_b;

    // Check for return path states (A_ACTIVE → A_THEN_B → B_ONLY)
    if (currentState === 'A_ACTIVE' || currentState === 'A_THEN_B' || currentState === 'B_ONLY') {
      console.log(`🔄 Return path detected: ${currentState}, returning 検査中`);
      return '検査中';
    }

    // Check for forward path states (B_ACTIVE → B_THEN_A → A_ONLY)
    if (currentState === 'B_ACTIVE' || currentState === 'B_THEN_A' || currentState === 'A_ONLY') {
      if (sensorA || sensorB) {
        console.log(`🔄 Forward path with sensors active: ${currentState}, returning 処理中`);
        return '処理中';
      } else {
        console.log(`🔄 Forward path without sensors: ${currentState}, returning 検査中`);
        return '検査中';
      }
    }

    // Check sensors first (most common case for immediate response)
    if (sensorA || sensorB) {
      console.log('✅ Sensor A or B active, returning 処理中');
      return '処理中';
    }

    // Check processing states
    if (sensorStatus.processing_active || 
        sensorStatus.capture?.processing_active ||
        sensorStatus.inspection_data?.processing_active) {
      console.log('✅ Processing active, returning 処理中');
      return '処理中';
    }

    // Default to inspecting when active but no sensors/processing
    console.log('⚠️ Active but no sensors/processing, returning 検査中');
    return '検査中';
  }, []);

  /**
   * Update status based on sensor status
   * This is the only function that should update status
   * Optimized for immediate response with direct state update
   */
  const updateStatusFromSensor = useCallback((sensorStatus: SensorStatus | null) => {
    console.log('🔄 updateStatusFromSensor called with:', sensorStatus);
    const newStatus = determineStatus(sensorStatus);
    console.log('🔄 New status determined:', newStatus);
    
    // Immediate status update - use functional update to avoid dependency on current status
    setStatus(prevStatus => {
      if (newStatus !== prevStatus) {
        // Immediate feedback for processing state changes
        if (newStatus === '処理中') {
          console.log('⚡ Processing started - immediate status change');
        } else {
          console.log(`🔄 Status updated: ${prevStatus} → ${newStatus}`);
        }
        
        return newStatus;
      }
      console.log('🔄 Status unchanged:', prevStatus);
      return prevStatus;
    });
  }, [determineStatus]);

  /**
   * Force set status (for manual overrides)
   * Use sparingly - prefer updateStatusFromSensor
   * Optimized for immediate feedback
   */
  const setStatusDirect = useCallback((newStatus: string) => {
    setStatus(prevStatus => {
      if (newStatus !== prevStatus) {
        console.log(`🔄 Status set directly: ${prevStatus} → ${newStatus}`);
        return newStatus;
      }
      return prevStatus;
    });
  }, []);

  return {
    status,
    updateStatusFromSensor,
    setStatusDirect,
    determineStatus
  };
};
