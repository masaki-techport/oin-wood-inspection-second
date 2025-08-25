import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import { useNotifications } from '@/components/ui/notifications';

interface MeasurementsConfig {
  no_defect: number;
  small_knot: number;
  large_knot: number;
  hole: number;
  discoloration: number;
  [key: string]: number;
}

interface UIConfig {
  textbox: {
    default_color: string;
    active_color: string;
  };
}

interface InspectionSettings {
  default_measurement: number;
  measurements: MeasurementsConfig;
  ui: UIConfig;
}

interface InspectionSettingsResponse {
  result: boolean;
  message: string;
  data: InspectionSettings;
}

export const useInspectionSettings = () => {
  const { addNotification } = useNotifications();
  const [settings, setSettings] = useState<InspectionSettings | null>(null);

  // Default settings in case API fails
  const defaultSettings: InspectionSettings = {
    default_measurement: 45,
    measurements: {
      no_defect: 45,
      small_knot: 45,
      large_knot: 45,
      hole: 45,
      discoloration: 45
    },
    ui: {
      textbox: {
        default_color: "lightgray",
        active_color: "white"
      }
    }
  };

  // Fetch inspection settings from the API
  const { data, isLoading, error } = useQuery<any>({
    queryKey: ['inspectionSettings'],
    queryFn: async () => {
      try {
        const response = await api.get('/inspections/settings');
        // The api client already returns response.data through the interceptor
        return response;
      } catch (err) {
        console.error('Failed to fetch inspection settings:', err);
        throw err;
      }
    },
    retry: 2,
  });

  useEffect(() => {
    if (data && 'result' in data && data.result && data.data) {
      setSettings(data.data);
      console.log('Successfully loaded inspection settings');
    } else if (error) {
      console.error('Error fetching inspection settings:', error);
      // Set default settings when API fails
      setSettings(defaultSettings);
      
      addNotification({
        type: 'warning',
        title: '設定取得エラー',
        message: '検査設定を取得できませんでした。デフォルト値を使用します。'
      });
    }
  }, [data, error, addNotification, defaultSettings]);

  // Get measurement value based on defect type
  const getMeasurementForDefectType = (defectType: string, inspectionResult: string): string => {
    if (!settings) {
      return String(defaultSettings.default_measurement); // Default fallback if settings not loaded
    }

    // Map inspection result to measurement config key
    let measurementKey = 'default_measurement';
    
    if (inspectionResult === '無欠点') {
      measurementKey = 'no_defect';
    } else if (inspectionResult === 'こぶし') {
      measurementKey = 'small_knot';
    } else if (inspectionResult === '節あり') {
      measurementKey = 'large_knot';
    }
    
    // Check specific defect types
    if (defectType.includes('穴')) {
      measurementKey = 'hole';
    }
    if (defectType.includes('変色')) {
      measurementKey = 'discoloration';
    }

    // Get the measurement value from settings
    const measurementValue = settings.measurements[measurementKey] || settings.default_measurement;
    return String(measurementValue);
  };

  return {
    settings,
    isLoading,
    getMeasurementForDefectType
  };
};