/**
 * Types for inspection session service
 */
// Explicitly ensure this file is treated as a module

export interface InspectionSession {
  tabId: string;
  timestamp: number;
  isActive: boolean;
}
