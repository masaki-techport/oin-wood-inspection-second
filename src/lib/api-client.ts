import Axios from 'axios';

import { useNotifications } from '@/components/ui/notifications';

// Ensure the API URL has the correct protocol
const getApiUrl = () => {
  const url = process.env.REACT_APP_API_URL || 'http://localhost:8000';
  // If URL doesn't start with http:// or https://, add http://
  if (!url.startsWith('http://') && !url.startsWith('https://')) {
    return `http://${url}`;
  }
  return url;
};

export const api = Axios.create({
  baseURL: getApiUrl(),
});

api.interceptors.response.use(
  (response) => {
    return response.data;
  },
  (error) => {
    if (!error.config?.suppressGlobalError) {
      const message = error.response?.data?.message || error.message;
      useNotifications.getState().addNotification({
        type: 'error',
        title: 'Error',
        message,
      });
    }

    if (error.response?.status === 401) {
      const searchParams = new URLSearchParams();
      const redirectTo = searchParams.get('redirectTo');
      window.location.href = `/auth/login?redirectTo=${redirectTo}`;
    }

    return Promise.reject(error);
  }
);

