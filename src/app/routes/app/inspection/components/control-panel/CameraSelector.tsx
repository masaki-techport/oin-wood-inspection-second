import React from 'react';
import { CameraSelectorProps, CameraType } from '../../types';

/**
 * Component for selecting camera type
 */
const CameraSelector: React.FC<CameraSelectorProps> = ({ 
  selectedCameraType, 
  onCameraTypeChange,
  disabled
}) => {
  return (
    <div className="flex flex-col items-start">
      <label htmlFor="camera-select" className="text-sm font-medium text-gray-700 mb-1">
        カメラタイプ:
      </label>
      <select
        id="camera-select"
        value={selectedCameraType}
        onChange={(e) => onCameraTypeChange(e.target.value as CameraType)}
        className="border border-gray-300 rounded-md px-3 py-2 bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent min-w-[140px]"
        disabled={disabled}
      >
        <option value="webcam">Web Camera</option>
        <option value="basler">Basler Camera</option>
        <option value="usb">USB Camera</option>
      </select>
    </div>
  );
};

export default CameraSelector;