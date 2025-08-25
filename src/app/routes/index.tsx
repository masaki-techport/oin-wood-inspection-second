import React from 'react';
import { createBrowserRouter } from 'react-router-dom';
import { QueryClient } from '@tanstack/react-query';
import HomePage from './app/home';
import CameraPage from './app/camera/CameraPage';
import { InspectionScreen } from './app/inspection';
import InferencePage from './app/inference';
// import ShootingScreen from './app/shooting'; // Commented out - file doesn't exist
import SettingScreen from './app/inspection/setting';
import InspectionHistoryScreen from './app/inspection/inspection-history';
import CameraViewScreen from './app/camera-view';

export const createRouter = (queryClient: QueryClient) =>
  createBrowserRouter([
    {
      path: '/',
      element: <HomePage />,
    },
    {
      path: '/camera',
      element: <CameraPage  />,
    },
    {
      path: '/inspection',
      element: <InspectionScreen />,
    },
    {
      path: '/inference',
      element: <InferencePage />,
    },
    // {
    //   path: '/shooting',
    //   element: <ShootingScreen />,
    // },
    {
      path: '/setting',
      element: <SettingScreen />,
    },
    {
      path: '/inspection-history',
      element: <InspectionHistoryScreen />,
    },
    {
      path: '/camera-view',
      element: <CameraViewScreen />,
    },
    {
      path: '*',
      lazy: async () => {
        const { NotFoundRoute } = await import('./not-found');
        return { Component: NotFoundRoute };
      },
    },
  ]);
