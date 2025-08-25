import React from 'react';
import { InspectionDetailsImg } from '@/types/api';
import { defectLabelColors } from '@/utils/defectStatus';

interface DefectLabelProps {
  defect: InspectionDetailsImg;
  index: number;
}

// Defect type names mapping
const defectTypeNames: { [key: number]: string } = {
  0: '変色',      // Discoloration
  1: '穴',        // Hole
  2: '死に節',    // Dead knot
  3: '流れ節_死', // Tight knot dead
  4: '流れ節_生', // Tight knot live
  5: '生き節',    // Live knot
};

const DefectLabel: React.FC<DefectLabelProps> = ({ defect, index }) => {
  // Get color scheme for this defect type
  const colors = defectLabelColors[defect.error_type as keyof typeof defectLabelColors] || defectLabelColors[0];
  
  // Get defect type name
  const typeName = defectTypeNames[defect.error_type] || `Type ${defect.error_type}`;
  
  // Calculate size information from bounding box dimensions
  const getSizeInfo = () => {
    const width = Math.abs(defect.width - defect.x_position);
    const height = Math.abs(defect.height - defect.y_position);
    
    if (width > 0 && height > 0) {
      return `Size: ${Math.round(width)}×${Math.round(height)}px`;
    }
    
    return 'Size: Unknown';
  };
  
  return (
    <div
      className={`p-3 rounded-lg border-2 transition-all duration-200 hover:shadow-md ${colors.bg} ${colors.border} ${colors.text}`}
      role="listitem"
      aria-label={`Defect ${index + 1}: ${typeName}`}
    >
      <div className="flex flex-col space-y-1">
        {/* Defect Type */}
        <div className="font-semibold text-sm">
          {typeName}
        </div>
        
        {/* Size Information */}
        <div className="text-xs opacity-80">
          {getSizeInfo()}
        </div>
        
        {/* Additional Info if available */}
        {defect.error_type_name && defect.error_type_name !== typeName && (
          <div className="text-xs opacity-70 italic">
            {defect.error_type_name}
          </div>
        )}
      </div>
    </div>
  );
};

export default DefectLabel;