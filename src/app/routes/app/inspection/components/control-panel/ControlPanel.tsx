import React from 'react';
import { ControlPanelProps } from '../../types';
import CameraSelector from './CameraSelector';
import AIThresholdInput from './AIThresholdInput';
import StatusDisplay from './StatusDisplay';
import ControlButtons from './ControlButtons';
import SensorControls from './SensorControls';

/**
 * Control panel component that contains all control elements
 */
const ControlPanel: React.FC<ControlPanelProps> = ({
  selectedCameraType,
  onCameraTypeChange,
  aiThreshold,
  setAiThreshold,
  status,
  onStart,
  onStop,
  onTop,
  isActive,
  debugMode,
  isSimulationMode,
  showCameraSettings,
  onTriggerTest,
  onToggleSensorA,
  onToggleSensorB,
  sensorAActive,
  sensorBActive
}) => {
  return (
    <div className="bg-white p-6 border-b-2 border-gray-300">
      <div className="flex items-center justify-center gap-8">
        {/* Camera Type Dropdown - Only show when showCameraSettings is true */}
        {showCameraSettings && (
          <CameraSelector 
            selectedCameraType={selectedCameraType} 
            onCameraTypeChange={onCameraTypeChange}
            disabled={isActive}
          />
        )}

        {/* AI Threshold Input */}
        <AIThresholdInput 
          aiThreshold={aiThreshold} 
          setAiThreshold={setAiThreshold}
          disabled={isActive}
        />
        
        {/* Status Display */}
        <StatusDisplay status={status} />
        
        {/* Control Buttons */}
        <ControlButtons 
          onStart={onStart} 
          onStop={onStop} 
          onTop={onTop} 
          isActive={isActive} 
        />
        
        {/* Test button in debug mode */}
        {debugMode && isSimulationMode && isActive && onTriggerTest && (
          <button 
            onClick={onTriggerTest}
            className="bg-orange-500 hover:bg-orange-600 text-white px-8 py-4 rounded-lg text-lg font-bold border-2 border-orange-700 shadow-lg"
          >
            🧪 テスト実行
          </button>
        )}
      </div>

      {/* Sensor Controls - Only in debug mode */}
      {debugMode && onToggleSensorA && onToggleSensorB && (
        <SensorControls 
          isActive={isActive}
          isSimulationMode={isSimulationMode}
          onTriggerTest={onTriggerTest || (() => {})}
          onToggleSensorA={onToggleSensorA}
          onToggleSensorB={onToggleSensorB}
          sensorAActive={sensorAActive || false}
          sensorBActive={sensorBActive || false}
        />
      )}
    </div>
  );
};

export default ControlPanel;