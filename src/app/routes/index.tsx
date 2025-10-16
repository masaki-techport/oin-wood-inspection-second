import React from 'react';
import { createBrowserRouter } from 'react-router-dom';
import { QueryClient } from '@tanstack/react-query';
import HomePage from './app/inspection';
import DatasetRegister from './app/dataset-register';

export const createRouter = (queryClient: QueryClient) =>
  createBrowserRouter([
    {
      path: '/',
      element: <HomePage />,
    },
    {
      path: '/dataset-register',
      element: <DatasetRegister />,
    },
    {
      path: '*',
      lazy: async () => {
        const { NotFoundRoute } = await import('./not-found');
        return { Component: NotFoundRoute };
      },
    },
  ]);
