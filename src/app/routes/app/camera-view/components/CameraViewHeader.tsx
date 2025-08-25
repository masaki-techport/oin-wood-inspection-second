import React from 'react';

interface CameraViewHeaderProps {
  title: string;
}

/**
 * Header component for the camera view screen
 */
const CameraViewHeader: React.FC<CameraViewHeaderProps> = ({ title }) => {
  return (
    <div className="bg-cyan-800 text-white text-3xl font-bold py-4 w-full text-left px-4">
      <h1>{title}</h1>
    </div>
  );
};

export default CameraViewHeader;