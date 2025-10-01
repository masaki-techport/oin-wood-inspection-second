import React from 'react';
import StandardHeader from '@/components/ui/StandardHeader';

interface CameraViewHeaderProps {
  title: string;
}

/**
 * Header component for the camera view screen
 */
const CameraViewHeader: React.FC<CameraViewHeaderProps> = ({ title }) => {
  return (
    <StandardHeader
      title={title}
      variant="primary"
      showLogo={true}
    />
  );
};

export default CameraViewHeader;