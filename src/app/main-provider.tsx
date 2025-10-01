import React, { useEffect } from 'react';
import { ErrorBoundary } from 'react-error-boundary';
import { MainErrorFallback } from '@/components/errors/main';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from '@/lib/react-query';
import { Notifications } from '@/components/ui/notifications';

import { ThemeProvider } from '@emotion/react';
import { createTheme } from '@mui/material';
import { LocalizationProvider } from '@mui/x-date-pickers';
import { AdapterMoment } from '@mui/x-date-pickers/AdapterMoment';
import { useAppStore } from '@/stores';
import { setupBrowserNavigationHandlers } from '@/app/routes/app/inspection/utils/browser-navigation';

const theme = createTheme();

type Props = {
  children: React.ReactNode;
};

export const AppProvider = ({ children }: Props) => {
  const { blocking } = useAppStore();
  useEffect(() => {
    // Default beforeunload handler for unsaved changes
    // Only apply when not on inspection screen to prevent conflicts
    const handleDefaultBeforeUnload = (event: BeforeUnloadEvent) => {
      // Check if we're on the inspection screen
      const isInspectionScreen = window.location.pathname.includes('/inspection');
      
      if (blocking && !isInspectionScreen) {
        const message = '保存されていない変更があります。本当に移動しますか？';
        event.returnValue = message;
        return message;
      }
    };
    
    // Set up browser navigation handlers for inspection screen
    const cleanupNavigationHandlers = setupBrowserNavigationHandlers();
    
    // Add the default beforeunload handler
    window.addEventListener('beforeunload', handleDefaultBeforeUnload);
    
    return () => {
      // Clean up all event listeners
      window.removeEventListener('beforeunload', handleDefaultBeforeUnload);
      cleanupNavigationHandlers();
    };
  }, [blocking]);
  return (
    // TODO: ErrorBoundaryが上手く動作しない、要確認
    <ErrorBoundary FallbackComponent={MainErrorFallback}>
      <ThemeProvider theme={theme}>
        <QueryClientProvider client={queryClient}>
          <LocalizationProvider dateAdapter={AdapterMoment} adapterLocale="ja">
            <Notifications />
            {children}
          </LocalizationProvider>
        </QueryClientProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
};
