// useNavigationGuard.ts
import { useCallback } from 'react';
import { useNavigate as reactUseNavigate } from 'react-router-dom';
import { useAppStore } from '@/stores';

const useNavigate = () => {
  const navigate = reactUseNavigate();
  const { blocking, setBlocking } = useAppStore();

  const guardedNavigate = useCallback(
    (to: string) => {
      if (blocking) {
        const userConfirmed = window.confirm(
          '保存されていない変更があります。本当に移動しますか？',
        );
        if (!userConfirmed) {
          return;
        }
      }
      navigate(to);
      setBlocking(false);
    },
    [navigate, blocking, setBlocking],
  );

  return { navigate: guardedNavigate, blocking, setBlocking };
};

export default useNavigate;
