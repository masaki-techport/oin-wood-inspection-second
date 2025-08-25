import React from 'react';
import { InspectionHeaderProps } from '../types';

/**
 * Header component for the inspection screen
 */
const InspectionHeader: React.FC<InspectionHeaderProps> = ({ title }) => {
  return (
    <div className="bg-cyan-800 text-white text-3xl font-bold py-4 w-full text-left px-4">
      <h1>{title}</h1>
    </div>
  );
};

export default InspectionHeader;