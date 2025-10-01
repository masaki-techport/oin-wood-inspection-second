import { useState, useEffect, useCallback } from 'react';
import useNavigate from '@/hooks/use-navigate';
import { SensorStatus, NavigationAction, UseBrowserNavigationReturn } from '../types';

export type InspectionStatus = '待機中' | '検査中' | '処理中' | '停止';

interface UseBrowserNavigationProps {
  status: string;
  sensorStatus: SensorStatus;
  stopInspection?: () => Promise<void>;
}

/**
 * Hook to handle browser navigation interactions based on inspection status
 */
export const useBrowserNavigation = ({
  status,
  sensorStatus,
  stopInspection
}: UseBrowserNavigationProps): UseBrowserNavigationReturn => {
  const { navigate } = useNavigate();
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [navigationAction, setNavigationAction] = useState<NavigationAction | null>(null);
  const [dialogContent, setDialogContent] = useState({
    title: '',
    content: ''
  });
  
  // Note: We only show custom dialog for back button navigation, not for close actions

  // Helper to determine if the inspection is active
  const isInspectionActive = useCallback(() => {
    // Check both the status string and the sensor's active state to be sure
    return (status === '検査中' || status === '処理中' || sensorStatus.active);
  }, [status, sensorStatus.active]);

  // Handle various navigation actions
  const handleNavigationAction = useCallback((action: NavigationAction) => {
    if (!isInspectionActive()) {
      // Before inspection starts or after it's stopped
      if (action === 'back') {
        // Go directly to TOP screen without confirmation
        navigate('/');
      } else if (action === 'close') {
        // Close the application
        window.close();
      } else if (action === 'refresh') {
        // Refresh the page
        window.location.reload();
      }
    } else {
      // Inspection is active (検査中 or 処理中) - show confirmation dialog
      setNavigationAction(action);
      
      if (action === 'back') {
        setDialogContent({
          title: '確認',
          content: '検査を終了してTOP画面に戻ります\nよろしいでしょうか。'
        });
      } else if (action === 'close') {
        setDialogContent({
          title: '確認',
          content: '検査を終了して、アプリを終了します\nよろしいでしょうか。'
        });
      } else if (action === 'refresh') {
        setDialogContent({
          title: '確認',
          content: '検査を終了して、画面を更新します\nよろしいでしょうか。'
        });
      }
      
      setShowConfirmDialog(true);
    }
  }, [isInspectionActive, navigate]);

  // Handle the confirmation from the dialog
  const handleConfirm = useCallback(async () => {
    // Hide dialog first
    setShowConfirmDialog(false);
    
    if (!navigationAction) return;

    // Stop inspection process first if it's active
    if (isInspectionActive() && stopInspection) {
      try {
        console.log('Stopping inspection before navigation...');
        await stopInspection();
        
        // Give a small delay to ensure inspection is fully stopped
        await new Promise(resolve => setTimeout(resolve, 300));
      } catch (error) {
        console.error('Error stopping inspection:', error);
      }
    }

    // Perform action after inspection is stopped
    if (navigationAction === 'back') {
      navigate('/');
    } else if (navigationAction === 'close') {
      window.close();
    } else if (navigationAction === 'refresh') {
      window.location.reload();
    }
    
    setNavigationAction(null);
  }, [navigationAction, isInspectionActive, stopInspection, navigate]);

  // Handle dialog close without confirming
  const handleDialogClose = useCallback(() => {
    setShowConfirmDialog(false);
    setNavigationAction(null);
  }, []);

  // Set up browser event listeners for back, close and refresh
  useEffect(() => {
    // Back button (popstate event)
    const handlePopState = (event: PopStateEvent) => {
      event.preventDefault();
      handleNavigationAction('back');
    };

    // Before unload (close or refresh) - prevent browser's default warning
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      if (isInspectionActive()) {
        // Prevent the browser's default warning dialog
        event.preventDefault();
        event.returnValue = '';
        
        // Note: We don't show custom dialog here because the user might cancel
        // The custom dialog should only show for back button navigation
        return '';
      }
      return undefined;
    };

    // Handle actual page unload - stop inspection when user confirms leaving
    const handlePageUnload = () => {
      if (isInspectionActive()) {
        console.log('Stopping inspection before page unload...');
        // Use sendBeacon for reliable API call during page unload
        try {
          // Send a beacon to stop the inspection
          navigator.sendBeacon('/api/sensor-inspection/stop', '');
        } catch (error) {
          console.error('Error sending stop beacon:', error);
        }
      }
    };

    // Handle page hide - more reliable than unload
    const handlePageHide = () => {
      if (isInspectionActive()) {
        console.log('Stopping inspection before page hide...');
        try {
          navigator.sendBeacon('/api/sensor-inspection/stop', '');
        } catch (error) {
          console.error('Error sending stop beacon on page hide:', error);
        }
      }
    };

    // Note: We don't override window.close to avoid showing custom dialog
    // The custom dialog should only show for back button navigation

    // Add event listeners
    window.addEventListener('popstate', handlePopState);
    window.addEventListener('beforeunload', handleBeforeUnload);
    window.addEventListener('unload', handlePageUnload);
    window.addEventListener('pagehide', handlePageHide);

    return () => {
      // Clean up event listeners
      window.removeEventListener('popstate', handlePopState);
      window.removeEventListener('beforeunload', handleBeforeUnload);
      window.removeEventListener('unload', handlePageUnload);
      window.removeEventListener('pagehide', handlePageHide);
    };
  }, [handleNavigationAction, isInspectionActive, stopInspection]);

  // Note: No need to track navigation handling since we only show dialog for back button

  return {
    showConfirmDialog,
    confirmDialogProps: {
      title: dialogContent.title,
      content: dialogContent.content,
      onConfirm: handleConfirm,
      onClose: handleDialogClose
    },
    handleNavigationAction
  };
};

export default useBrowserNavigation;
