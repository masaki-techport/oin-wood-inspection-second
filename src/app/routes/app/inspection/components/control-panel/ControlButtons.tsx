import React, { useState } from 'react';
import { ControlButtonsProps } from '../../types';

/**
 * Component for control buttons (start, stop, top)
 */
const ControlButtons: React.FC<ControlButtonsProps> = ({
  onStart,
  onStop,
  onTop,
  isActive
}) => {
  const [isStarting, setIsStarting] = useState(false);
  const [isStopping, setIsStopping] = useState(false);

  const handleStartClick = async () => {
    if (isStarting || isActive) return; // Prevent multiple clicks

    console.log('開始 button clicked, current sensorStatus.active:', isActive);
    setIsStarting(true);

    try {
      await onStart();
    } finally {
      setIsStarting(false);
    }
  };

  const handleStopClick = async () => {
    if (isStopping || !isActive || isStarting) return; // Prevent multiple clicks and prevent clicking while starting

    console.log('停止 button clicked, current sensorStatus.active:', isActive);
    setIsStopping(true);

    try {
      await onStop();
    } finally {
      setIsStopping(false);
    }
  };

  return (
    <>
      <button
        onClick={handleStartClick}
        disabled={isActive || isStarting}
        className={`px-12 py-4 rounded-lg text-xl font-bold border-2 shadow-lg min-w-[120px] ${isActive || isStarting
            ? 'bg-gray-400 text-gray-600 border-gray-500 cursor-not-allowed'
            : 'bg-blue-500 hover:bg-blue-600 text-white border-blue-700'
          }`}
      >
        {isStarting ? '開始中...' : '▶ 開始'}
      </button>

      <button
        onClick={handleStopClick}
        disabled={!isActive || isStopping || isStarting}
        className={`px-12 py-4 rounded-lg text-xl font-bold border-2 shadow-lg min-w-[120px] ${!isActive || isStopping || isStarting
            ? 'bg-gray-400 text-gray-600 border-gray-500 cursor-not-allowed'
            : 'bg-yellow-500 hover:bg-yellow-600 text-white border-yellow-700'
          }`}
      >
        {isStopping ? '停止中...' : '■ 停止'}
      </button>

      <button
        onClick={onTop}
        disabled={isActive}
        className={`px-12 py-4 rounded-lg text-xl font-bold border-2 shadow-lg min-w-[100px] ${isActive
            ? 'bg-gray-400 text-gray-600 border-gray-500 cursor-not-allowed'
            : 'bg-blue-800 hover:bg-blue-900 text-white border-blue-900'
          }`}
      >
        TOP
      </button>
    </>
  );
};

export default ControlButtons;