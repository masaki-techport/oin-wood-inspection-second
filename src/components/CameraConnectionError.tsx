/**
 * Camera Connection Error Component
 * Shows error popups when camera connection fails
 */

import React from 'react';
import './CameraConnectionError.css';

interface CameraConnectionErrorProps {
  isVisible: boolean;
  cameraType: string;
  errorMessage: string;
  onClose: () => void;
  onRetry?: () => void;
  onSwitchCamera?: (cameraType: 'basler' | 'webcam') => void;
}

const CameraConnectionError: React.FC<CameraConnectionErrorProps> = ({
  isVisible,
  cameraType,
  errorMessage,
  onClose,
  onRetry,
  onSwitchCamera
}) => {
  if (!isVisible) return null;

  const getErrorTitle = () => {
    switch (cameraType) {
      case 'basler':
        return 'Basler Camera Connection Failed';
      case 'webcam':
        return 'Webcam Connection Failed';
      default:
        return 'Camera Connection Failed';
    }
  };

  const getErrorIcon = () => {
    return (
      <div className="error-icon">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="12" cy="12" r="10" stroke="#dc3545" strokeWidth="2" fill="#fff"/>
          <path d="M15 9l-6 6M9 9l6 6" stroke="#dc3545" strokeWidth="2" strokeLinecap="round"/>
        </svg>
      </div>
    );
  };

  const getSuggestions = () => {
    if (cameraType === 'basler') {
      return [
        'Ensure the Basler camera is properly connected via USB/GigE',
        'Check that the camera drivers are installed',
        'Verify no other application is using the camera',
        'Try switching to webcam for testing purposes'
      ];
    } else if (cameraType === 'webcam') {
      return [
        'Check that your webcam is properly connected',
        'Ensure no other application is using the webcam',
        'Verify webcam permissions are granted',
        'Try switching to a different camera if available'
      ];
    }
    return ['Check camera connection and try again'];
  };

  return (
    <div className="camera-error-overlay">
      <div className="camera-error-modal">
        <div className="camera-error-header">
          {getErrorIcon()}
          <h2>{getErrorTitle()}</h2>
          <button className="close-button" onClick={onClose}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          </button>
        </div>

        <div className="camera-error-content">
          <div className="error-message">
            <strong>Error Details:</strong>
            <p>{errorMessage}</p>
          </div>

          <div className="error-suggestions">
            <strong>Troubleshooting Steps:</strong>
            <ul>
              {getSuggestions().map((suggestion, index) => (
                <li key={index}>{suggestion}</li>
              ))}
            </ul>
          </div>
        </div>

        <div className="camera-error-actions">
          {onRetry && (
            <button className="retry-button" onClick={onRetry}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M1 4v6h6M23 20v-6h-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              Retry Connection
            </button>
          )}

          {onSwitchCamera && cameraType === 'basler' && (
            <button className="switch-button" onClick={() => onSwitchCamera('webcam')}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2v11z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                <circle cx="12" cy="13" r="4" stroke="currentColor" strokeWidth="2"/>
              </svg>
              Switch to Webcam
            </button>
          )}

          {onSwitchCamera && cameraType === 'webcam' && (
            <button className="switch-button" onClick={() => onSwitchCamera('basler')}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="2" y="3" width="20" height="14" rx="2" ry="2" stroke="currentColor" strokeWidth="2"/>
                <line x1="8" y1="21" x2="16" y2="21" stroke="currentColor" strokeWidth="2"/>
                <line x1="12" y1="17" x2="12" y2="21" stroke="currentColor" strokeWidth="2"/>
              </svg>
              Switch to Basler Camera
            </button>
          )}

          <button className="close-button-text" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default CameraConnectionError;
