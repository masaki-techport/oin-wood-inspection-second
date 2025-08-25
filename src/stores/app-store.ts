import { create } from 'zustand';

interface AppState {
  blocking: boolean;
  setBlocking: (blocking: boolean) => void;
}

export const useAppStore = create<AppState>((set) => ({
  blocking: false,
  setBlocking: (blocking: boolean) => set({ blocking }),
}));
