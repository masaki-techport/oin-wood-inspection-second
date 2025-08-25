import { CameraType } from '../inspection/types';

// Camera View Component Props Types
export interface CameraViewHeaderProps {
  title: string;
}

export interface MainCameraDisplayProps {
  image: string | null;
  isConnected: boolean | null;
  selectedCameraType: CameraType;
  droppedFrame: boolean;
}