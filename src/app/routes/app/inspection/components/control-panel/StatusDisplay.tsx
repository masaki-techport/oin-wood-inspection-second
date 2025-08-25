import React from 'react';
import { StatusDisplayProps } from '../../types';

/**
 * Component for displaying inspection status
 */
const StatusDisplay: React.FC<StatusDisplayProps> = ({ status }) => {
  return (
    <div className={`px-8 py-4 rounded border-2 text-xl font-bold min-w-[120px] text-center ${
      status === '待機中' ? 'bg-gray-100 border-gray-600 text-gray-800' : 
      status === '検査中' ? 'bg-blue-100 border-blue-600 text-blue-800' :
      status === '処理中' ? 'bg-green-100 border-green-600 text-green-800 animate-pulse' :
      status === '停止' ? 'bg-red-100 border-red-600 text-red-800' : 'bg-yellow-100 border-yellow-600 text-yellow-800'
    }`}>
      {status}
    </div>
  );
};

export default StatusDisplay;