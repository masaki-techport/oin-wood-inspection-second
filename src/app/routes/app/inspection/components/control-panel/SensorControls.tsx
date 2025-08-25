import React from 'react';
import { SensorControlsProps } from '../../types';

/**
 * Component for sensor controls (only visible in debug mode)
 */
const SensorControls: React.FC<SensorControlsProps> = ({
  isActive,
  isSimulationMode,
  onTriggerTest,
  onToggleSensorA,
  onToggleSensorB,
  sensorAActive,
  sensorBActive
}) => {
  if (!isActive || !isSimulationMode) {
    return null;
  }

  return (
    <div className="mt-4 p-4 bg-red-50 rounded-lg border-2 border-red-200">
      <div className="flex items-center justify-center gap-4">
        <button
          onClick={onToggleSensorA}
          className={`px-6 py-3 rounded-lg text-sm font-medium border-2 transition-colors ${
            sensorAActive
              ? 'bg-red-500 text-white border-red-600 hover:bg-red-600'
              : 'bg-gray-200 text-gray-700 border-gray-400 hover:bg-gray-300'
          }`}
        >
          センサーA: {sensorAActive ? 'ON' : 'OFF'}
        </button>
        
        <button
          onClick={onToggleSensorB}
          className={`px-6 py-3 rounded-lg text-sm font-medium border-2 transition-colors ${
            sensorBActive
              ? 'bg-red-500 text-white border-red-600 hover:bg-red-600'
              : 'bg-gray-200 text-gray-700 border-gray-400 hover:bg-gray-300'
          }`}
        >
          センサーB: {sensorBActive ? 'ON' : 'OFF'}
        </button>
      </div>
    </div>
  );
};

export default SensorControls;