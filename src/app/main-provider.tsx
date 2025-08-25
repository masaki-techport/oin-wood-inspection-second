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

const theme = createTheme();

type Props = {
  children: React.ReactNode;
};

export const AppProvider = ({ children }: Props) => {
  const { blocking } = useAppStore();
  useEffect(() => {
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      if (blocking) {
        const message = '保存されていない変更があります。本当に移動しますか？';
        event.returnValue = message;
        return message;
      }
    };
    // TODO: ブラウザのバックボタン押下イベントについては、
    // 遷移イベントをキャンセルできないため、保存するかの確認に変更
    // const handlePopState = (event: PopStateEvent) => {
    //   if (blocking) {
    //     const userConfirmed = window.confirm(
    //       '保存されていない変更があります。本当に移動しますか？',
    //     );
    //     if (!userConfirmed) {
    //       window.history.go(1);
    //     }
    //   }
    // };
    // window.addEventListener('popstate', handlePopState);
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => {
      // window.removeEventListener('popstate', handlePopState);
      window.removeEventListener('beforeunload', handleBeforeUnload);
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
