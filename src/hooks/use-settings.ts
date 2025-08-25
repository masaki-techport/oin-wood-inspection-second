import { useState, useEffect } from 'react';

interface SettingsResponse {
  [section: string]: {
    [key: string]: string;
  };
}

interface SettingValue {
  section: string;
  key: string;
  value: string | null;
  exists: boolean;
  error?: string;
}

/**
 * Hook to fetch application settings from the API
 */
export const useSettings = () => {
  const [settings, setSettings] = useState<SettingsResponse>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const response = await fetch('/api/settings');
        if (response.ok) {
          const data = await response.json();
          setSettings(data);
        } else {
          setError('Failed to fetch settings');
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    fetchSettings();
  }, []);

  return { settings, loading, error };
};

/**
 * Hook to fetch a specific setting value
 */
export const useSetting = (section: string, key: string) => {
  const [setting, setSetting] = useState<SettingValue | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchSetting = async () => {
      try {
        const response = await fetch(`/api/settings/${section}/${key}`);
        if (response.ok) {
          const data = await response.json();
          setSetting(data);
        } else {
          setError('Failed to fetch setting');
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    fetchSetting();
  }, [section, key]);

  return { setting, loading, error };
};

/**
 * Hook to check if debug mode is enabled
 */
export const useDebugMode = () => {
  const { setting, loading, error } = useSetting('DEBUG', 'debug_mode');
  
  const isDebugMode = setting?.exists && setting.value === '1';
  
  return { isDebugMode, loading, error };
};