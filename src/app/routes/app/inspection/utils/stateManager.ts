/**
 * Centralized State Manager
 * 
 * This module provides a clean alternative to using global window variables
 * for storing shared state across the inspection system.
 */

interface GlobalState {
  inspectionId: number | null;
  sensorStatus: any | null;
  fetchInspectionResults: ((id: number) => void) | null;
  updateInspectionResultFromSensorStatus: ((status: any) => void) | null;
  loadLatestPresentationImages: (() => void) | null;
  clearPresentationImages: (() => void) | null;
  forceLoadLatestInspection: (() => void) | null;
  stopPollingPresentationImages: (() => void) | null;
  forceRefreshCurrentInspection: (() => void) | null;
}

class StateManager {
  private state: GlobalState = {
    inspectionId: null,
    sensorStatus: null,
    fetchInspectionResults: null,
    updateInspectionResultFromSensorStatus: null,
    loadLatestPresentationImages: null,
    clearPresentationImages: null,
    forceLoadLatestInspection: null,
    stopPollingPresentationImages: null,
    forceRefreshCurrentInspection: null,
  };

  private listeners: Map<keyof GlobalState, Set<() => void>> = new Map();

  /**
   * Get a state value
   */
  get<K extends keyof GlobalState>(key: K): GlobalState[K] {
    return this.state[key];
  }

  /**
   * Set a state value and notify listeners
   */
  set<K extends keyof GlobalState>(key: K, value: GlobalState[K]): void {
    this.state[key] = value;
    this.notifyListeners(key);
  }

  /**
   * Subscribe to state changes
   */
  subscribe<K extends keyof GlobalState>(key: K, callback: () => void): () => void {
    if (!this.listeners.has(key)) {
      this.listeners.set(key, new Set());
    }
    
    this.listeners.get(key)!.add(callback);
    
    // Return unsubscribe function
    return () => {
      this.listeners.get(key)?.delete(callback);
    };
  }

  /**
   * Notify listeners of state changes
   */
  private notifyListeners<K extends keyof GlobalState>(key: K): void {
    const callbacks = this.listeners.get(key);
    if (callbacks) {
      callbacks.forEach(callback => {
        try {
          callback();
        } catch (error) {
          console.error(`Error in state listener for ${key}:`, error);
        }
      });
    }
  }

  /**
   * Clear all state
   */
  clear(): void {
    this.state = {
      inspectionId: null,
      sensorStatus: null,
      fetchInspectionResults: null,
      updateInspectionResultFromSensorStatus: null,
      loadLatestPresentationImages: null,
      clearPresentationImages: null,
      forceLoadLatestInspection: null,
      stopPollingPresentationImages: null,
      forceRefreshCurrentInspection: null,
    };
    this.listeners.clear();
  }
}

// Create a singleton instance
export const stateManager = new StateManager();

// Helper functions for common operations
export const getInspectionId = (): number | null => stateManager.get('inspectionId');
export const setInspectionId = (id: number | null): void => stateManager.set('inspectionId', id);

export const getSensorStatus = (): any | null => stateManager.get('sensorStatus');
export const setSensorStatus = (status: any | null): void => stateManager.set('sensorStatus', status);

export const getFetchInspectionResults = (): ((id: number) => void) | null => 
  stateManager.get('fetchInspectionResults');
export const setFetchInspectionResults = (fn: ((id: number) => void) | null): void => 
  stateManager.set('fetchInspectionResults', fn);

export const getUpdateInspectionResultFromSensorStatus = (): ((status: any) => void) | null => 
  stateManager.get('updateInspectionResultFromSensorStatus');
export const setUpdateInspectionResultFromSensorStatus = (fn: ((status: any) => void) | null): void => 
  stateManager.set('updateInspectionResultFromSensorStatus', fn);

export const getLoadLatestPresentationImages = (): (() => void) | null => 
  stateManager.get('loadLatestPresentationImages');
export const setLoadLatestPresentationImages = (fn: (() => void) | null): void => 
  stateManager.set('loadLatestPresentationImages', fn);

export const getClearPresentationImages = (): (() => void) | null => 
  stateManager.get('clearPresentationImages');
export const setClearPresentationImages = (fn: (() => void) | null): void => 
  stateManager.set('clearPresentationImages', fn);

export const getForceLoadLatestInspection = (): (() => void) | null => 
  stateManager.get('forceLoadLatestInspection');
export const setForceLoadLatestInspection = (fn: (() => void) | null): void => 
  stateManager.set('forceLoadLatestInspection', fn);

export const getStopPollingPresentationImages = (): (() => void) | null => 
  stateManager.get('stopPollingPresentationImages');
export const setStopPollingPresentationImages = (fn: (() => void) | null): void => 
  stateManager.set('stopPollingPresentationImages', fn);

export const getForceRefreshCurrentInspection = (): (() => void) | null => 
  stateManager.get('forceRefreshCurrentInspection');
export const setForceRefreshCurrentInspection = (fn: (() => void) | null): void => 
  stateManager.set('forceRefreshCurrentInspection', fn);
