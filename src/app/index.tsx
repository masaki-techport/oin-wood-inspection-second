import React, { useMemo } from 'react';
import { AppProvider } from './main-provider';
import { RouterProvider } from 'react-router-dom';
import { createRouter } from './routes';
import { useQueryClient } from '@tanstack/react-query';

const AppRouter = () => {
  const queryClient = useQueryClient();

  const router = useMemo(() => createRouter(queryClient), [queryClient]);

  return <RouterProvider router={router} />;
};

const App = () => (
  <AppProvider>
    <AppRouter />
  </AppProvider>
);

export default App;
