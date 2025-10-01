/**
 * Centralized Event Manager
 * 
 * This module provides a clean alternative to using the global window object
 * for inter-component communication. It uses a simple event emitter pattern
 * to manage custom events throughout the inspection system.
 */

type EventCallback = (data: any) => void;

class EventManager {
  private listeners: Map<string, Set<EventCallback>> = new Map();

  /**
   * Subscribe to an event
   */
  on(eventName: string, callback: EventCallback): () => void {
    if (!this.listeners.has(eventName)) {
      this.listeners.set(eventName, new Set());
    }
    
    this.listeners.get(eventName)!.add(callback);
    
    // Return unsubscribe function
    return () => {
      this.listeners.get(eventName)?.delete(callback);
    };
  }

  /**
   * Emit an event to all subscribers
   */
  emit(eventName: string, data?: any): void {
    const callbacks = this.listeners.get(eventName);
    if (callbacks) {
      callbacks.forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error(`Error in event listener for ${eventName}:`, error);
        }
      });
    }
  }

  /**
   * Remove all listeners for an event
   */
  off(eventName: string): void {
    this.listeners.delete(eventName);
  }

  /**
   * Remove all listeners
   */
  clear(): void {
    this.listeners.clear();
  }
}

// Create a singleton instance
export const eventManager = new EventManager();

// Event names as constants for type safety
export const EVENTS = {
  INSPECTION_DATA_UPDATE: 'inspectionDataUpdate',
  PRESENTATION_IMAGES_READY: 'presentationImagesReady',
  PRESENTATION_IMAGES_UPDATED: 'presentationImagesUpdated',
  INSPECTION_SAVED: 'inspectionSaved',
  INSPECTION_RESULTS_READY: 'inspectionResultsReady',
  INSPECTION_ERROR: 'inspectionError',
  INSPECTION_WARNING: 'inspectionWarning',
  INSPECTION_SUCCESS: 'inspectionSuccess',
} as const;

// Type-safe event data interfaces
export interface InspectionDataUpdateEvent {
  inspectionId: number;
  inspectionData: any;
}

export interface PresentationImagesReadyEvent {
  inspectionId: number;
  images: any[];
}

export interface PresentationImagesUpdatedEvent {
  inspectionId: number;
  images: any[];
}

export interface InspectionSavedEvent {
  inspectionId?: number;
  success: boolean;
  message?: string;
}

export interface InspectionResultsReadyEvent {
  inspectionId: number;
  results: any;
}

export interface InspectionErrorEvent {
  message: string;
  error?: Error;
}

export interface InspectionWarningEvent {
  message: string;
  details?: any;
}

export interface InspectionSuccessEvent {
  message: string;
  details?: any;
}
