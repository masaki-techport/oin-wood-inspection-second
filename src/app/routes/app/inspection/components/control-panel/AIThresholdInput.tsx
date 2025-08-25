import React, { useState } from 'react';
import { AIThresholdInputProps } from '../../types';

/**
 * Component for AI threshold input
 */
const AIThresholdInput: React.FC<AIThresholdInputProps> = ({ 
  aiThreshold, 
  setAiThreshold,
  disabled 
}) => {
  const [error, setError] = useState<string | null>(null);
  return (
    <div className="flex flex-col items-start">
      <label htmlFor="ai-threshold" className="text-sm font-medium text-gray-700 mb-1">
        AI閾値:
      </label>
      <div className="flex items-center gap-2">
        <input
          id="ai-threshold"
          type="text"
          inputMode="numeric"
          value={aiThreshold}
          onChange={(e) => {
            const value = e.target.value;
            const numValue = parseInt(value);
            
            if (value === "") {
              setAiThreshold(10);
              setError(null);
              return;
            }
            
            if (isNaN(numValue)) {
              return;
            }
            
            if (numValue > 100) {
              setError("100より小さい数値を入力してください");
            } else if (numValue < 10) {
              setError("10より大きい数値を入力してください");
            } else {
              setError(null);
            }
            
            setAiThreshold(numValue);
          }}
          onBlur={(e) => {
            // Only check and show error, don't auto-correct
            if (aiThreshold > 100) {
              setError("100より小さい数値を入力してください");
            } else if (aiThreshold < 10) {
              setError("10より大きい数値を入力してください");
            } else {
              setError(null);
            }
          }}
          className="border border-gray-300 rounded-md px-3 py-2 bg-white text-gray-900 w-24 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          disabled={disabled}
        />
      </div>
      {error && (
        <p className="text-red-500 text-xs mt-1">{error}</p>
      )}
    </div>
  );
};

export default AIThresholdInput;