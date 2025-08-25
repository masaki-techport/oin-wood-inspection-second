// Camera View Component Props Types

export interface CameraViewHeaderProps {
  title: string;
  onNavigateHome: () => void;
}

// Re-export camera types from inspection for consistency
export type { CameraType } from '@/app/routes/app/inspection/types';