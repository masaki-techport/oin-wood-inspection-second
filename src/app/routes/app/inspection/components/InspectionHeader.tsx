import React from 'react';
import { InspectionHeaderProps } from '../types';
import StandardHeader from '@/components/ui/StandardHeader';

/**
 * Header component for the inspection screen
 */
const InspectionHeader: React.FC<InspectionHeaderProps> = ({ title }) => {
  return (
    <StandardHeader
      title={title}
      variant="primary"
      showLogo={true}
    />
  );
};

export default InspectionHeader;