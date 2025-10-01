/**
 * Data Consistency Monitor
 * 
 * This module monitors data consistency across all data sources
 * and provides real-time alerts for inconsistencies.
 */

import { eventManager, EVENTS } from './eventManager';
import { dataValidator, ValidationResult } from './dataValidator';

export interface ConsistencyCheck {
  id: string;
  timestamp: number;
  dataSource: string;
  status: 'consistent' | 'inconsistent' | 'warning';
  details: string;
  resolved: boolean;
}

export interface DataSourceSnapshot {
  inspectionId: number | null;
  inspectionResult: string;
  defectType: string;
  measurements: string;
  presentationImages: any[];
  sensorStatus: any;
  timestamp: number;
  source: string;
}

class DataConsistencyMonitor {
  private checks: ConsistencyCheck[] = [];
  private snapshots: Map<string, DataSourceSnapshot> = new Map();
  private isMonitoring = false;
  private checkInterval: NodeJS.Timeout | null = null;
  private maxChecks = 1000;

  /**
   * Start monitoring data consistency
   */
  startMonitoring(intervalMs: number = 5000): void {
    if (this.isMonitoring) {
      console.warn('Data consistency monitoring is already active');
      return;
    }

    this.isMonitoring = true;
    console.log('Starting data consistency monitoring...');

    this.checkInterval = setInterval(() => {
      this.performConsistencyCheck();
    }, intervalMs);

    // Listen for data updates
    eventManager.on(EVENTS.INSPECTION_DATA_UPDATE, (data) => {
      this.updateSnapshot('inspection-data', data);
    });

    eventManager.on(EVENTS.PRESENTATION_IMAGES_UPDATED, (data) => {
      this.updateSnapshot('presentation-images', data);
    });
  }

  /**
   * Stop monitoring data consistency
   */
  stopMonitoring(): void {
    if (!this.isMonitoring) {
      return;
    }

    this.isMonitoring = false;
    console.log('Stopping data consistency monitoring...');

    if (this.checkInterval) {
      clearInterval(this.checkInterval);
      this.checkInterval = null;
    }
  }

  /**
   * Update data source snapshot
   */
  updateSnapshot(source: string, data: any): void {
    const snapshot: DataSourceSnapshot = {
      inspectionId: data.inspectionId || data.inspection_id || null,
      inspectionResult: data.inspectionResult || data.results || '',
      defectType: data.defectType || '',
      measurements: data.measurements || '',
      presentationImages: data.presentationImages || data.images || [],
      sensorStatus: data.sensorStatus || null,
      timestamp: Date.now(),
      source
    };

    this.snapshots.set(source, snapshot);
  }

  /**
   * Perform consistency check across all data sources
   */
  private performConsistencyCheck(): void {
    const checkId = `check_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    const timestamp = Date.now();

    try {
      // Get all snapshots
      const snapshots = Array.from(this.snapshots.values());
      
      if (snapshots.length < 2) {
        // Not enough data sources to compare
        return;
      }

      // Check for inconsistencies
      const inconsistencies = this.findInconsistencies(snapshots);
      
      if (inconsistencies.length > 0) {
        const check: ConsistencyCheck = {
          id: checkId,
          timestamp,
          dataSource: 'multiple',
          status: 'inconsistent',
          details: `Found ${inconsistencies.length} inconsistencies`,
          resolved: false
        };

        this.addCheck(check);
        this.emitInconsistencyAlert(inconsistencies);
      } else {
        // All data sources are consistent
        const check: ConsistencyCheck = {
          id: checkId,
          timestamp,
          dataSource: 'multiple',
          status: 'consistent',
          details: 'All data sources are consistent',
          resolved: true
        };

        this.addCheck(check);
      }

      // Validate each snapshot
      snapshots.forEach(snapshot => {
        const validationResult = dataValidator.validateInspectionData({
          inspectionId: snapshot.inspectionId || 0,
          inspectionResult: snapshot.inspectionResult,
          defectType: snapshot.defectType,
          measurements: snapshot.measurements,
          presentationImages: snapshot.presentationImages,
          sensorStatus: snapshot.sensorStatus,
          timestamp: snapshot.timestamp
        });

        if (!validationResult.isValid) {
          const check: ConsistencyCheck = {
            id: `${checkId}_${snapshot.source}`,
            timestamp,
            dataSource: snapshot.source,
            status: 'inconsistent',
            details: `Validation failed: ${validationResult.errors.map(e => e.message).join(', ')}`,
            resolved: false
          };

          this.addCheck(check);
        }
      });

    } catch (error) {
      console.error('Error during consistency check:', error);
      
      const check: ConsistencyCheck = {
        id: checkId,
        timestamp,
        dataSource: 'monitor',
        status: 'inconsistent',
        details: `Consistency check failed: ${error}`,
        resolved: false
      };

      this.addCheck(check);
    }
  }

  /**
   * Find inconsistencies between data sources
   */
  private findInconsistencies(snapshots: DataSourceSnapshot[]): string[] {
    const inconsistencies: string[] = [];
    const primary = snapshots[0];

    for (let i = 1; i < snapshots.length; i++) {
      const current = snapshots[i];

      // Check inspection ID consistency
      if (primary.inspectionId !== current.inspectionId) {
        inconsistencies.push(
          `Inspection ID mismatch: ${primary.source}(${primary.inspectionId}) vs ${current.source}(${current.inspectionId})`
        );
      }

      // Check inspection result consistency
      if (primary.inspectionResult !== current.inspectionResult) {
        inconsistencies.push(
          `Inspection result mismatch: ${primary.source}(${primary.inspectionResult}) vs ${current.source}(${current.inspectionResult})`
        );
      }

      // Check defect type consistency
      if (primary.defectType !== current.defectType) {
        inconsistencies.push(
          `Defect type mismatch: ${primary.source}(${primary.defectType}) vs ${current.source}(${current.defectType})`
        );
      }

      // Check measurements consistency
      if (primary.measurements !== current.measurements) {
        inconsistencies.push(
          `Measurements mismatch: ${primary.source}(${primary.measurements}) vs ${current.source}(${current.measurements})`
        );
      }

      // Check presentation images count consistency
      if (primary.presentationImages.length !== current.presentationImages.length) {
        inconsistencies.push(
          `Presentation images count mismatch: ${primary.source}(${primary.presentationImages.length}) vs ${current.source}(${current.presentationImages.length})`
        );
      }
    }

    return inconsistencies;
  }

  /**
   * Add consistency check to history
   */
  private addCheck(check: ConsistencyCheck): void {
    this.checks.push(check);
    
    // Keep only recent checks
    if (this.checks.length > this.maxChecks) {
      this.checks.shift();
    }
  }

  /**
   * Emit inconsistency alert
   */
  private emitInconsistencyAlert(inconsistencies: string[]): void {
    eventManager.emit(EVENTS.INSPECTION_WARNING, {
      message: `Data inconsistency detected: ${inconsistencies.join(', ')}`,
      details: inconsistencies
    });

    console.warn('Data inconsistency detected:', inconsistencies);
  }

  /**
   * Get consistency check history
   */
  getChecks(): ConsistencyCheck[] {
    return [...this.checks];
  }

  /**
   * Get unresolved checks
   */
  getUnresolvedChecks(): ConsistencyCheck[] {
    return this.checks.filter(check => !check.resolved);
  }

  /**
   * Mark check as resolved
   */
  resolveCheck(checkId: string): void {
    const check = this.checks.find(c => c.id === checkId);
    if (check) {
      check.resolved = true;
    }
  }

  /**
   * Get consistency statistics
   */
  getConsistencyStats(): {
    totalChecks: number;
    consistentChecks: number;
    inconsistentChecks: number;
    warningChecks: number;
    unresolvedChecks: number;
    consistencyRate: number;
  } {
    const total = this.checks.length;
    const consistent = this.checks.filter(c => c.status === 'consistent').length;
    const inconsistent = this.checks.filter(c => c.status === 'inconsistent').length;
    const warning = this.checks.filter(c => c.status === 'warning').length;
    const unresolved = this.checks.filter(c => !c.resolved).length;

    return {
      totalChecks: total,
      consistentChecks: consistent,
      inconsistentChecks: inconsistent,
      warningChecks: warning,
      unresolvedChecks: unresolved,
      consistencyRate: total > 0 ? consistent / total : 0
    };
  }

  /**
   * Clear all checks
   */
  clearChecks(): void {
    this.checks = [];
  }
}

// Create singleton instance
export const dataConsistencyMonitor = new DataConsistencyMonitor();

/**
 * Hook for using data consistency monitoring in React components
 */
export const useDataConsistencyMonitoring = () => {
  const startMonitoring = (intervalMs?: number) => {
    dataConsistencyMonitor.startMonitoring(intervalMs);
  };

  const stopMonitoring = () => {
    dataConsistencyMonitor.stopMonitoring();
  };

  const getChecks = () => {
    return dataConsistencyMonitor.getChecks();
  };

  const getUnresolvedChecks = () => {
    return dataConsistencyMonitor.getUnresolvedChecks();
  };

  const resolveCheck = (checkId: string) => {
    dataConsistencyMonitor.resolveCheck(checkId);
  };

  const getConsistencyStats = () => {
    return dataConsistencyMonitor.getConsistencyStats();
  };

  const clearChecks = () => {
    dataConsistencyMonitor.clearChecks();
  };

  return {
    startMonitoring,
    stopMonitoring,
    getChecks,
    getUnresolvedChecks,
    resolveCheck,
    getConsistencyStats,
    clearChecks
  };
};
