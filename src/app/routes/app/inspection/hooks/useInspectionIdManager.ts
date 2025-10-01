import { useState, useCallback } from 'react';

/**
 * Centralized inspection ID management hook
 * Provides single source of truth for inspection ID across the application
 */
export const useInspectionIdManager = () => {
  const [inspectionId, setInspectionId] = useState<number | null>(null);

  /**
   * Set the current inspection ID
   * @param id - The inspection ID to set
   */
  const setCurrentInspectionId = useCallback((id: number | null) => {
    console.log(`🔍 Setting inspection ID: ${inspectionId} → ${id}`);
    setInspectionId(id);
    
    // Also update the global window object for backward compatibility
    (window as any).inspectionId = id;
  }, [inspectionId]);

  /**
   * Clear the current inspection ID
   */
  const clearInspectionId = useCallback(() => {
    console.log('🔍 Clearing inspection ID');
    setInspectionId(null);
    (window as any).inspectionId = null;
  }, []);

  /**
   * Get the current inspection ID
   * @returns The current inspection ID or null
   */
  const getCurrentInspectionId = useCallback(() => {
    return inspectionId;
  }, [inspectionId]);

  /**
   * Check if there is a current inspection ID
   * @returns True if there is a current inspection ID
   */
  const hasInspectionId = useCallback(() => {
    return inspectionId !== null;
  }, [inspectionId]);

  return {
    inspectionId,
    setCurrentInspectionId,
    clearInspectionId,
    getCurrentInspectionId,
    hasInspectionId
  };
};
