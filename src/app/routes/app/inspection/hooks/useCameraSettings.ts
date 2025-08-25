import { useState, useEffect } from 'react';
import { shouldShowCameraSettings } from '@/utils/settingsReader';

/**
 * Hook for managing camera UI visibility based on settings.ini
 * This controls only the UI components (camera selector dropdown and camera preview)
 * Camera functionality for inspections remains active regardless of this setting
 * @returns Camera UI visibility state
 */
export const useCameraSettings = () => {
    const [showCameraUI, setShowCameraUI] = useState(false);

    // Check camera UI visibility on component mount
    useEffect(() => {
        const checkCameraSettings = async () => {
            try {
                const shouldShow = await shouldShowCameraSettings();
                console.log('Camera UI visibility from settings.ini:', shouldShow);
                setShowCameraUI(shouldShow);
            } catch (error) {
                console.error('Failed to check camera UI visibility:', error);
                // Default to false to ensure camera UI is hidden if there's an error
                setShowCameraUI(false);
            }
        };
        checkCameraSettings();
    }, []);

    return {
        showCameraUI
    };
};