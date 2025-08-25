/**
 * Utility functions to read settings from settings.ini
 */

// Cache for settings to avoid repeated API calls
let settingsCache: Record<string, Record<string, string>> | null = null;

/**
 * Fetches settings from the backend API
 * @returns {Promise<Record<string, Record<string, string>>>} Settings object
 */
export const fetchSettings = async (): Promise<Record<string, Record<string, string>>> => {
  try {
    // If we have cached settings, return them
    if (settingsCache) {
      console.log('Using cached settings:', settingsCache);
      return settingsCache;
    }

    console.log('Fetching settings from /api/settings...');

    // Fetch settings from the backend API
    const response = await fetch('/api/settings');

    console.log('Response status:', response.status);
    console.log('Response headers:', Object.fromEntries(response.headers.entries()));

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Response error text:', errorText);
      throw new Error(`Failed to fetch settings: ${response.status} ${response.statusText}`);
    }

    const responseText = await response.text();
    console.log('Raw response text:', responseText.substring(0, 200) + '...');

    let settings;
    try {
      settings = JSON.parse(responseText);
    } catch (parseError) {
      console.error('JSON parse error:', parseError);
      console.error('Response was not valid JSON:', responseText);
      throw new Error(`Invalid JSON response: ${parseError}`);
    }

    console.log('Parsed settings:', settings);

    // Cache the settings
    settingsCache = settings;

    return settings;
  } catch (error) {
    console.error('Error fetching settings:', error);
    // Return empty settings object if there's an error
    return {};
  }
};

/**
 * Force refresh the settings cache
 * @returns {Promise<Record<string, Record<string, string>>>} Updated settings object
 */
export const refreshSettings = async (): Promise<Record<string, Record<string, string>>> => {
  try {
    // Clear the cache
    settingsCache = null;

    // Fetch fresh settings
    return await fetchSettings();
  } catch (error) {
    console.error('Error refreshing settings:', error);
    return {};
  }
};

/**
 * Reads the debug_mode setting from settings.ini
 * @returns {Promise<boolean>} True if debug_mode is enabled, false otherwise
 */
export const isDebugModeEnabled = async (): Promise<boolean> => {
  try {
    // Try to get settings from the backend
    const settings = await fetchSettings();

    // Check if DEBUG section and debug_mode key exist
    if (settings && settings.DEBUG && settings.DEBUG.debug_mode) {
      return settings.DEBUG.debug_mode === '1';
    }

    // Fallback to environment variable if API fails
    const debugMode = process.env.REACT_APP_DEBUG_MODE === '1';
    return debugMode;
  } catch (error) {
    console.error('Error reading debug_mode setting:', error);
    return false;
  }
};

/**
 * Checks if the debug panel button should be shown
 * This function ensures the debug panel button is hidden when debug_mode is disabled
 * @returns {Promise<boolean>} True if the debug panel button should be shown, false otherwise
 */
export const shouldShowDebugPanelButton = async (): Promise<boolean> => {
  try {
    // First check if debug mode is enabled
    const debugModeEnabled = await isDebugModeEnabled();
    if (!debugModeEnabled) {
      return false;
    }

    // If debug mode is enabled, check if show_debug_panel is explicitly set
    const settings = await fetchSettings();

    // Prioritize the specific show_debug_panel setting if available
    if (settings && settings.DEBUG && settings.DEBUG.show_debug_panel !== undefined) {
      return settings.DEBUG.show_debug_panel === '1';
    }
    
    // Fall back to show_debug_windows if show_debug_panel is not specified
    if (settings && settings.DEBUG && settings.DEBUG.show_debug_windows) {
      return settings.DEBUG.show_debug_windows === '1';
    }

    // If neither setting is specified, default to showing the button when debug_mode is enabled
    return debugModeEnabled;
  } catch (error) {
    console.error('Error checking if debug panel button should be shown:', error);
    return false;
  }
};

/**
 * Synchronous version that returns the current cached value or a default
 * @returns {boolean} True if debug_mode is enabled, false otherwise
 */
export const isDebugModeEnabledSync = (): boolean => {
  try {
    // Check if we have cached settings
    if (settingsCache && settingsCache.DEBUG && settingsCache.DEBUG.debug_mode) {
      return settingsCache.DEBUG.debug_mode === '1';
    }

    // Fallback to environment variable if cache is not available
    return process.env.REACT_APP_DEBUG_MODE === '1';
  } catch (error) {
    console.error('Error reading cached debug_mode setting:', error);
    return false;
  }
};

/**
 * Synchronous version that checks if the debug panel button should be shown
 * This function ensures the debug panel button is hidden when debug_mode is disabled
 * @returns {boolean} True if the debug panel button should be shown, false otherwise
 */
export const shouldShowDebugPanelButtonSync = (): boolean => {
  try {
    // First check if debug mode is enabled
    const debugModeEnabled = isDebugModeEnabledSync();
    if (!debugModeEnabled) {
      return false;
    }

    // If debug mode is enabled, check if show_debug_panel is explicitly set
    if (settingsCache && settingsCache.DEBUG && settingsCache.DEBUG.show_debug_panel !== undefined) {
      return settingsCache.DEBUG.show_debug_panel === '1';
    }
    
    // Fall back to show_debug_windows if show_debug_panel is not specified
    if (settingsCache && settingsCache.DEBUG && settingsCache.DEBUG.show_debug_windows !== undefined) {
      return settingsCache.DEBUG.show_debug_windows === '1';
    }

    // If neither setting is specified, default to showing the button when debug_mode is enabled
    return debugModeEnabled;
  } catch (error) {
    console.error('Error checking if debug panel button should be shown (sync):', error);
    return false;
  }
};

/**
 * Checks if camera settings should be shown based on debug_mode and show_camera_setting
 * @returns {Promise<boolean>} True if camera settings should be shown, false otherwise
 */
export const shouldShowCameraSettings = async (): Promise<boolean> => {
  try {
    // First check if debug mode is enabled
    const debugModeEnabled = await isDebugModeEnabled();
    if (!debugModeEnabled) {
      return false;
    }

    // If debug mode is enabled, check show_camera_setting
    const settings = await fetchSettings();
    if (settings && settings.DEBUG && settings.DEBUG.show_camera_setting !== undefined) {
      return settings.DEBUG.show_camera_setting === '1';
    }

    // Default to false if show_camera_setting is not specified
    return false;
  } catch (error) {
    console.error('Error checking if camera settings should be shown:', error);
    return false;
  }
};

/**
 * Synchronous version that checks if camera settings should be shown
 * @returns {boolean} True if camera settings should be shown, false otherwise
 */
export const shouldShowCameraSettingsSync = (): boolean => {
  try {
    // First check if debug mode is enabled
    const debugModeEnabled = isDebugModeEnabledSync();
    if (!debugModeEnabled) {
      return false;
    }

    // If debug mode is enabled, check show_camera_setting
    if (settingsCache && settingsCache.DEBUG && settingsCache.DEBUG.show_camera_setting !== undefined) {
      return settingsCache.DEBUG.show_camera_setting === '1';
    }

    // Default to false if show_camera_setting is not specified
    return false;
  } catch (error) {
    console.error('Error checking if camera settings should be shown (sync):', error);
    return false;
  }
};

/**
 * Reads a specific setting from settings.ini
 * @param {string} section The section in the settings.ini file
 * @param {string} key The key to read
 * @param {any} defaultValue The default value to return if the setting is not found
 * @returns {Promise<any>} The value of the setting or the default value
 */
export const getSetting = async (section: string, key: string, defaultValue: any): Promise<any> => {
  try {
    // Try to get settings from the backend
    const settings = await fetchSettings();

    // Check if section and key exist
    if (settings && settings[section] && settings[section][key] !== undefined) {
      return settings[section][key];
    }

    // Fallback to environment variable if API fails
    const envKey = `REACT_APP_${section.toUpperCase()}_${key.toUpperCase()}`;
    const value = process.env[envKey];
    return value !== undefined ? value : defaultValue;
  } catch (error) {
    console.error(`Error reading setting ${section}.${key}:`, error);
    return defaultValue;
  }
};

/**
 * Synchronous version that returns the current cached value or a default
 * @param {string} section The section in the settings.ini file
 * @param {string} key The key to read
 * @param {any} defaultValue The default value to return if the setting is not found
 * @returns {any} The value of the setting or the default value
 */
export const getSettingSync = (section: string, key: string, defaultValue: any): any => {
  try {
    // Check if we have cached settings
    if (settingsCache && settingsCache[section] && settingsCache[section][key] !== undefined) {
      return settingsCache[section][key];
    }

    // Fallback to environment variable if cache is not available
    const envKey = `REACT_APP_${section.toUpperCase()}_${key.toUpperCase()}`;
    const value = process.env[envKey];
    return value !== undefined ? value : defaultValue;
  } catch (error) {
    console.error(`Error reading cached setting ${section}.${key}:`, error);
    return defaultValue;
  }
};