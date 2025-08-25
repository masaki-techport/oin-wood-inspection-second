import { useState, useEffect, useRef } from 'react';
import { useNotifications } from '@/components/ui/notifications';
import { api } from '@/lib/api-client';
import { SensorStatus, UseSensorMonitoringReturn, CameraType } from '../types';
import { dispatchSaveEvent } from '../utils';

/**
 * Hook for monitoring and controlling sensors
 * @param selectedCameraType - Currently selected camera type
 * @returns Sensor monitoring state and functions
 */
export const useSensorMonitoring = (selectedCameraType: CameraType): UseSensorMonitoringReturn => {
  const [aiThreshold, setAiThreshold] = useState(50);
  const [isUpdatingThreshold, setIsUpdatingThreshold] = useState(false);
  const [sensorStatus, setSensorStatus] = useState<SensorStatus>({
    active: false,
    sensor_a: false,
    sensor_b: false,
    current_state: 'IDLE',
    simulation_mode: false,
    sensors: {
      sensor_a: false,
      sensor_b: false,
      current_state: 'IDLE',
      last_result: null
    },
    capture_status: {
      status: '待機中',
      last_save_message: '',
      total_saves: 0,
      total_discards: 0,
      buffer_status: {
        is_recording: false,
        buffer_size: 0,
        max_buffer_size: 600
      }
    },
    inspection_data: null,
    inspection_results: null,
    inspection_results_loading: false,
    inspection_results_error: null
  });

  const sensorStatusRef = useRef<NodeJS.Timeout | null>(null);
  const lastSaveMessageRef = useRef<string>('');
  const lastInspectionIdRef = useRef<number | null>(null);

  const { addNotification } = useNotifications();

  // Function to fetch inspection results from backend with retry mechanism
  const fetchInspectionResults = async (inspectionId: number, retryCount = 0) => {
    try {
      console.log(`Fetching inspection results for inspection ID: ${inspectionId}`);

      // Set loading state
      setSensorStatus(prev => ({
        ...prev,
        inspection_results: null,
        inspection_results_loading: true,
        inspection_results_error: null
      }));

      // Add timeout to prevent hanging requests
      const timeoutPromise = new Promise((_, reject) =>
        setTimeout(() => reject(new Error('Request timeout')), 10000)
      );

      // Use the endpoint that fetches from inspection_results table
      const apiPromise = api.get(`/api/sensor-inspection/inspection-result/${inspectionId}`);
      const data = await Promise.race([apiPromise, timeoutPromise]) as any;

      if (data.status === 'success' && data.data) {
        console.log('Successfully fetched inspection results:', data.data);
        setSensorStatus(prev => ({
          ...prev,
          inspection_results: data.data,
          inspection_results_loading: false,
          inspection_results_error: null
        }));
      } else {
        console.log('No inspection results found for inspection ID:', inspectionId);
        // Handle missing results gracefully without showing error notification
        setSensorStatus(prev => ({
          ...prev,
          inspection_results: null,
          inspection_results_loading: false,
          inspection_results_error: null
        }));
      }
    } catch (err: any) {
      console.error('Failed to fetch inspection results:', err);

      // Determine error type and message
      let errorMessage = '詳細検査結果の取得に失敗しました';
      let shouldShowNotification = false;

      if (err.message === 'Request timeout') {
        // Timeout errors should be reported
        errorMessage = 'リクエストがタイムアウトしました。詳細検査結果を取得できません';
        shouldShowNotification = true;
      } else if (err.response?.status === 404) {
        // 404 errors are expected for inspections without detailed results
        errorMessage = '詳細検査結果が見つかりません';
        console.log('Inspection results not found (404) - handling gracefully');
      } else if (err.response?.status >= 500) {
        // Server errors should be reported to user
        errorMessage = 'サーバーエラーが発生しました。詳細検査結果を取得できません';
        shouldShowNotification = true;
      } else if (err.code === 'NETWORK_ERROR' || !err.response) {
        // Network errors should be reported
        errorMessage = 'ネットワークエラーが発生しました。詳細検査結果を取得できません';
        shouldShowNotification = true;
      }

      // Update state with error information
      setSensorStatus(prev => ({
        ...prev,
        inspection_results: null,
        inspection_results_loading: false,
        inspection_results_error: errorMessage
      }));

      // Retry logic for network errors and timeouts
      if ((err.message === 'Request timeout' || err.code === 'NETWORK_ERROR' || !err.response) && retryCount < 2) {
        console.log(`Retrying inspection results fetch (attempt ${retryCount + 1}/3) for ID: ${inspectionId}`);

        // Exponential backoff: 1s, 2s, 4s
        const delay = Math.pow(2, retryCount) * 1000;
        setTimeout(() => {
          fetchInspectionResults(inspectionId, retryCount + 1);
        }, delay);
        return;
      }

      // Show notification only for serious errors that user should know about
      if (shouldShowNotification) {
        addNotification({
          type: 'error',
          title: '詳細検査結果エラー',
          message: errorMessage
        });
      }
    }
  };

  // Function to update AI threshold on backend
  const updateAiThresholdOnBackend = async (newThreshold: number) => {
    if (isUpdatingThreshold) return; // Prevent concurrent updates

    setIsUpdatingThreshold(true);
    try {
      console.log(`Updating AI threshold on backend to ${newThreshold}%`);
      const response = await api.post('/api/sensor-inspection/set-ai-threshold', {
        ai_threshold: newThreshold
      }) as any;

      if (response.status === 'success') {
        console.log(`Successfully updated AI threshold to ${newThreshold}%`);
        addNotification({
          type: 'success',
          title: 'AI閾値更新',
          message: `AI閾値を${newThreshold}%に設定しました`
        });
      }
    } catch (err: any) {
      console.error('Failed to update AI threshold on backend:', err);
      const message = err.response?.data?.error || 'AI閾値の更新に失敗しました';
      addNotification({
        type: 'error',
        title: 'AI閾値更新エラー',
        message
      });
    } finally {
      setIsUpdatingThreshold(false);
    }
  };

  // Enhanced setAiThreshold that also updates the backend
  const setAiThresholdWithBackend = (newThreshold: number) => {
    setAiThreshold(newThreshold);
    // Only update backend if sensor monitoring is active
    if (sensorStatus.active) {
      updateAiThresholdOnBackend(newThreshold);
    }
  };

  // Function to get the display name for camera types
  const getCameraLabel = (type: CameraType) => {
    switch (type) {
      case 'basler':
        return 'Basler Camera';
      case 'webcam':
        return 'Web Camera';
      case 'usb':
        return 'USB Camera';
    }
  };

  // Using throttle/debounce pattern to prevent concurrent calls
let pollInProgress = false;
let pollRequested = false;

const pollSensorStatus = async () => {
    // Skip if a poll is already in progress
    if (pollInProgress) {
      pollRequested = true;
      return;
    }
    
    pollInProgress = true;
    try {
      const data = await api.get('/api/sensor-inspection/status') as any;

      // Debug logging
      // console.log('Polling sensor status:', {
      //   active: data.active,
      //   sensors: data.sensors,
      //   inspection_data: data.inspection_data,
      //   timestamp: new Date().toLocaleTimeString()
      // });

      // Enhanced debug logging for inspection data - only log when new inspection data received
      if (data.inspection_data && (!lastInspectionIdRef.current || 
          lastInspectionIdRef.current !== data.inspection_data.inspection_id)) {
        console.log('🔍 New inspection data received:', data.inspection_data.inspection_id);
        console.log('🔍 Confidence above threshold:', data.inspection_data.confidence_above_threshold);
        console.log('🔍 Inspection details count:', data.inspection_data.inspection_details?.length || 0);
        console.log('🔍 Presentation images count:', data.inspection_data.presentation_images?.length || 0);
        console.log('🔍 Presentation ready:', data.inspection_data.presentation_ready);
      }

      if (data.active) {
        // Update AI threshold if provided by the backend
        if (data.ai_threshold !== undefined && data.ai_threshold !== aiThreshold) {
          console.log(`Updating AI threshold from backend: ${data.ai_threshold}% (was ${aiThreshold}%)`);
          setAiThreshold(data.ai_threshold);
        }

        // Check if we're in the "just started inspection" state
        if (data.inspection_just_started) {
          console.log('Backend reports inspection just started - clearing frontend state');
          // Force clear any outdated results
          if ((window as any).clearInspectionResults) {
            console.log('Clearing previous inspection results due to just_started flag');
            (window as any).clearInspectionResults();
          }
        }

        // Handle notifications before state update
        const newCaptureStatus = data.capture;
        const shouldShowNotification = newCaptureStatus.last_save_message &&
          newCaptureStatus.last_save_message !== lastSaveMessageRef.current;

        if (shouldShowNotification) {
          lastSaveMessageRef.current = newCaptureStatus.last_save_message;

          // Check if this is a proper save result (pass_L_to_R) by examining last_result
          const isValidSaveResult = data.sensors && data.sensors.last_result === 'pass_L_to_R';
          const isSuccess = newCaptureStatus.last_save_message.includes('保存');

          // Don't capture current image when save is triggered
          // Just process the inspection data to update the inspection result display
          if (isSuccess && isValidSaveResult) {
            // Use the inspection ID if available in the data
            const inspectionId = data.inspection_data?.inspection_id || null;

            // Store the inspection ID for future reference
            lastInspectionIdRef.current = inspectionId;

            // Dispatch an event to trigger image loading
            dispatchSaveEvent(inspectionId);

            // Automatically fetch inspection results when successful save occurs
            if (inspectionId) {
              console.log(`Triggering automatic fetch of inspection results for ID: ${inspectionId}`);
              fetchInspectionResults(inspectionId);
            }
          }

          addNotification({
            type: isSuccess ? 'success' : 'info',
            title: isSuccess ? '画像保存' : '画像破棄',
            message: newCaptureStatus.last_save_message
          });
        }

        // Check if backend camera type matches UI selection
        if (data.camera_type && data.camera_type !== selectedCameraType) {
          const cameraTypeMap: Record<string, CameraType> = {
            'basler': 'basler',
            'basler_legacy': 'basler',
            'webcam': 'webcam',
            'usb': 'usb',
            'dummy': 'webcam'
          };

          console.log(`Backend camera type (${data.camera_type}) differs from UI selection (${selectedCameraType}), keeping UI selection`);
        }

        // Update sensor status
        // Check if relevant state has actually changed before updating
      const hasChanges = (prev: any) => {
        if (prev.sensor_a !== data.sensors.sensor_a ||
            prev.sensor_b !== data.sensors.sensor_b ||
            prev.current_state !== data.sensors.current_state ||
            prev.simulation_mode !== data.simulation_mode ||
            prev.sensors.sensor_a !== data.sensors.sensor_a ||
            prev.sensors.sensor_b !== data.sensors.sensor_b ||
            prev.sensors.current_state !== data.sensors.current_state ||
            prev.sensors.last_result !== data.sensors.last_result ||
            JSON.stringify(prev.capture_status) !== JSON.stringify(newCaptureStatus) ||
            (data.inspection_data && (!prev.inspection_data || 
              prev.inspection_data.inspection_id !== data.inspection_data.inspection_id)) ||
            (data.inspection_results && (!prev.inspection_results ||
              prev.inspection_results.inspection_id !== data.inspection_results.inspection_id))) {
          return true;
        }
        return false;
      };

      setSensorStatus(prev => {
        // Only update state if something has actually changed
        if (!hasChanges(prev)) {
          return prev;
        }
        
        return {
          ...prev,
          active: true,  // Ensure active stays true
          sensor_a: data.sensors.sensor_a,
          sensor_b: data.sensors.sensor_b,
          current_state: data.sensors.current_state,
          simulation_mode: data.simulation_mode,
          sensors: {
            sensor_a: data.sensors.sensor_a,
            sensor_b: data.sensors.sensor_b,
            current_state: data.sensors.current_state,
            last_result: data.sensors.last_result
          },
          capture_status: newCaptureStatus,
          inspection_data: data.inspection_data || prev.inspection_data,
          inspection_results: data.inspection_results || prev.inspection_results,
          inspection_results_loading: prev.inspection_results_loading,
          inspection_results_error: prev.inspection_results_error
        };
      });

      } else {
        console.log('Sensor monitoring not active, stopping polling');
        // Sensor monitoring stopped
        setSensorStatus(prev => ({ ...prev, active: false }));
        if (sensorStatusRef.current) {
          clearInterval(sensorStatusRef.current);
          sensorStatusRef.current = null;
        }
      }
    } catch (err: any) {
      console.error('Sensor status polling failed:', err);

      // Handle different types of polling errors
      if (err.response?.status >= 500) {
        // Server error - show notification but continue polling
        console.warn('Server error during polling, continuing...');
      } else if (err.code === 'NETWORK_ERROR' || !err.response) {
        // Network error - log but don't show notification to avoid spam
        console.warn('Network error during polling, continuing...');
      }

      // Don't stop polling on error - keep trying
      // Only show error notification if polling fails consistently (not implemented to avoid spam)
    } finally {
      // Mark poll as complete
      pollInProgress = false;
      
      // If another poll was requested while this one was running, run it now
      if (pollRequested) {
        pollRequested = false;
        setTimeout(pollSensorStatus, 50); // Small delay to prevent CPU spiking
      }
    }
  };

  const triggerTestSequence = async () => {
    try {
      const response = await api.post('/api/sensor-inspection/trigger-test') as any;
      addNotification({
        type: 'info',
        title: 'テストシーケンス',
        message: response.message
      });
    } catch (err: any) {
      const message = err.response?.data?.error || 'テストシーケンスの実行に失敗しました';
      addNotification({
        type: 'error',
        title: 'エラー',
        message
      });
    }
  };

  const toggleSensorA = async () => {
    try {
      const response = await api.post('/api/sensor-inspection/toggle-sensor-a') as any;
      addNotification({
        type: 'info',
        title: 'センサーA',
        message: response.message
      });
    } catch (err: any) {
      const message = err.response?.data?.error || 'センサーAの切り替えに失敗しました';
      addNotification({
        type: 'error',
        title: 'エラー',
        message
      });
    }
  };

  const toggleSensorB = async () => {
    try {
      const response = await api.post('/api/sensor-inspection/toggle-sensor-b') as any;
      addNotification({
        type: 'info',
        title: 'センサーB',
        message: response.message
      });
    } catch (err: any) {
      const message = err.response?.data?.error || 'センサーBの切り替えに失敗しました';
      addNotification({
        type: 'error',
        title: 'エラー',
        message
      });
    }
  };

  const handleStart = async () => {
    console.log('handleStart called');

    // Check if AI threshold is within valid range
    if (aiThreshold < 10 || aiThreshold > 100) {
      addNotification({
        type: 'warning',
        title: 'AI閾値が範囲外です',
        message: 'AI閾値は10から100の間で設定してください'
      });
      return; // Don't proceed with starting
    }

    // Reset inspection-related state
    lastInspectionIdRef.current = null; // Reset the last inspection ID
    lastSaveMessageRef.current = ''; // Reset the last save message

    // Immediately update UI state
    setSensorStatus(prev => {
      console.log('Setting sensorStatus.active to true');
      return {
        ...prev,
        active: true,
        inspection_data: null, // Clear any previous inspection data
        inspection_results: null, // Clear any previous inspection results
        inspection_results_loading: false, // Reset loading state
        inspection_results_error: null, // Clear any previous errors
        capture_status: {
          ...prev.capture_status,
          last_save_message: '',
          total_saves: 0,
          total_discards: 0
        }
      };
    });

    // Start sensor monitoring with the CURRENTLY SELECTED camera type
    try {
      console.log(`Starting sensor inspection with camera type: ${selectedCameraType}, AI threshold: ${aiThreshold}`);
      const response = await api.post('/api/sensor-inspection/start', {
        camera_type: selectedCameraType,  // Use the currently selected camera type
        ai_threshold: aiThreshold         // Pass the AI threshold to the backend
      });

      if ((response as any).status === 'started') {
        // Check if camera is connected
        const cameraConnected = (response as any).camera_connected === true;
        const simulationMode = (response as any).simulation_mode === true;
        const returnedCameraType = (response as any).camera_type;

        // Verify that the backend is using the same camera type we requested
        if (returnedCameraType && returnedCameraType !== selectedCameraType) {
          console.warn(`Backend returned different camera type: ${returnedCameraType}, expected: ${selectedCameraType}`);
          // Don't change the UI selection - keep what the user selected
          addNotification({
            type: 'warning',
            title: 'カメラタイプ不一致',
            message: `選択されたカメラ (${getCameraLabel(selectedCameraType)}) と実際のカメラ (${returnedCameraType}) が異なります`
          });
        }

        // Update simulation mode status
        setSensorStatus(prev => ({
          ...prev,
          active: true,
          simulation_mode: simulationMode
        }));

        // Start polling sensor status more frequently
        sensorStatusRef.current = setInterval(pollSensorStatus, 1000);  // Reduced from 500ms to 1000ms for fewer API calls

        // Show appropriate notification based on camera connection status
        if (cameraConnected) {
          addNotification({
            type: 'success',
            title: 'センサー監視開始',
            message: `${getCameraLabel(selectedCameraType)}でセンサーによる自動検査を開始しました`
          });
        } else {
          // Check if camera is in use by another application
          const cameraInUse = (response as any).camera_in_use === true;

          if (cameraInUse) {
            addNotification({
              type: 'warning',
              title: 'カメラ使用中',
              message: `${getCameraLabel(selectedCameraType)}が他のアプリケーションで使用中のため、シミュレーションモードで開始しました。他のアプリケーションを閉じて再試行してください。`
            });
          } else {
            // Camera not connected, but system started in simulation mode
            addNotification({
              type: 'warning',
              title: 'カメラ未接続',
              message: `${getCameraLabel(selectedCameraType)}が接続されていないため、シミュレーションモードで開始しました`
            });
          }
        }
      } else {
        // API call succeeded but returned unexpected status
        setSensorStatus(prev => ({ ...prev, active: false }));
        addNotification({
          type: 'error',
          title: 'センサー監視エラー',
          message: 'センサー監視の開始に失敗しました'
        });
      }
    } catch (err: any) {
      // API call failed - reset UI state
      setSensorStatus(prev => ({ ...prev, active: false }));

      const message = err.response?.data?.error || 'センサー監視の開始に失敗しました';
      addNotification({
        type: 'error',
        title: 'センサー監視エラー',
        message
      });
    }
  };

  const handleStop = async () => {
    console.log('handleStop called');

    // First stop the backend API to prevent race conditions
    try {
      console.log('Stopping sensor monitoring via API');

      // Set timeout for API call
      const stopPromise = api.post('/api/sensor-inspection/stop');
      const timeoutPromise = new Promise((_, reject) =>
        setTimeout(() => reject(new Error('Request timeout')), 5000)
      );

      await Promise.race([stopPromise, timeoutPromise]);

      console.log('API stop request completed successfully');
    } catch (err: any) {
      const message = err.message === 'Request timeout'
        ? 'API応答がタイムアウトしましたが、監視を強制停止しました'
        : err.response?.data?.error || 'センサー監視の停止に失敗しましたが、強制停止しました';

      console.error('Error stopping via API, proceeding with UI stop:', err);
      addNotification({
        type: 'warning',
        title: '強制停止',
        message
      });
    }

    // Now update the UI state - this happens whether API call succeeds or fails
    console.log('Updating UI state to stopped');
    setSensorStatus(prev => {
      console.log('Setting sensorStatus.active to false');
      return {
        ...prev,
        active: false,
        sensor_a: false,
        sensor_b: false,
        current_state: 'IDLE',
        // Keep inspection_data to maintain the current view
      };
    });

    // Stop polling immediately
    if (sensorStatusRef.current) {
      clearInterval(sensorStatusRef.current);
      sensorStatusRef.current = null;
    }

    // Don't clear presentation images or inspection results - we want to keep showing them
    // DO NOT reset the inspection result

    // Add success notification
    addNotification({
      type: 'info',
      title: 'センサー監視停止',
      message: 'センサー監視を停止しました'
    });
  };

  // Expose fetchInspectionResults globally for retry functionality
  useEffect(() => {
    (window as any).fetchInspectionResults = fetchInspectionResults;

    return () => {
      delete (window as any).fetchInspectionResults;
    };
  }, []);

  // Cleanup function
  useEffect(() => {
    return () => {
      if (sensorStatusRef.current) {
        clearInterval(sensorStatusRef.current);
        sensorStatusRef.current = null;
      }
    };
  }, []);

  return {
    sensorStatus,
    aiThreshold,
    setAiThreshold: setAiThresholdWithBackend,
    handleStart,
    handleStop,
    triggerTestSequence,
    toggleSensorA,
    toggleSensorB,
    fetchInspectionResults
  };
};