/**
 * Inspection Session Service
 * This service manages the inspection session state across browser tabs
 * to prevent multiple tabs from running inspections simultaneously.
 */

// Explicitly import types to ensure this file is treated as a module
import type { InspectionSession } from './inspection-session-service.types';

// Constants
const INSPECTION_SESSION_KEY = 'oin-wood-inspection-session';
const SESSION_PING_INTERVAL = 5000; // Check session every 5 seconds

// This import is no longer needed as we've moved it to the top
// import { InspectionSession } from './inspection-session-service.types';

/**
 * Generates a unique ID for the current tab
 */
const generateTabId = (): string => {
  return `tab-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
};

/**
 * Gets the current tab ID from sessionStorage
 * Creates and stores one if it doesn't exist
 */
const getOrCreateTabId = (): string => {
  let tabId = sessionStorage.getItem('oin-tab-id');
  if (!tabId) {
    tabId = generateTabId();
    sessionStorage.setItem('oin-tab-id', tabId);
  }
  return tabId;
};

/**
 * InspectionSessionService class for managing cross-tab inspection sessions
 */
export class InspectionSessionService {
  private tabId: string;
  private pingInterval: NodeJS.Timeout | null = null;
  private isActive: boolean = false;

  constructor() {
    try {
      this.tabId = getOrCreateTabId();
      
      // Setup event listener for storage changes
      window.addEventListener('storage', this.handleStorageChange);
      
      // Setup cleanup on tab close
      window.addEventListener('beforeunload', this.cleanupSession);
      
      // Check for and clear any stale sessions on initialization
      this.checkForStaleSessions();
    } catch (error) {
      console.error('Error initializing InspectionSessionService:', error);
      this.tabId = `tab-${Date.now()}`; // Fallback ID if getOrCreateTabId fails
    }
  }
  
  /**
   * Check for stale sessions and clean them up
   */
  private checkForStaleSessions(): void {
    const existingSession = this.getExistingSession();
    if (existingSession) {
      const isStale = Date.now() - existingSession.timestamp > 15000;
      if (isStale) {
        console.log('Cleaning up stale session during initialization', existingSession);
        localStorage.removeItem('oin-wood-inspection-session');
      }
    }
  }

  /**
   * Attempts to start a new inspection session
   * @returns Promise that resolves to true if session started successfully, false otherwise
   */
  public async startSession(): Promise<boolean> {
    try {
      // First check if we already have an active session in this tab
      if (this.isActive) {
        console.log('Session already active in this tab');
        this.saveSession(); // Refresh timestamp
        this.startPinging(); // Ensure pinging is active
        return true;
      }
      
      // Check if another tab already has an active session
      const existingSession = this.getExistingSession();
      
      if (existingSession && existingSession.isActive && existingSession.tabId !== this.tabId) {
        // Check if the existing session is still valid (not older than 15 seconds)
        const isStale = Date.now() - existingSession.timestamp > 15000;
        
        if (!isStale) {
          console.log('Another tab already has an active inspection session', existingSession);
          return false;
        }
        
        // If the session is stale, we can take over
        console.log('Taking over stale session', existingSession);
      }
      
      // Start our session
      this.isActive = true;
      this.saveSession();
      
      // Start pinging to keep session alive
      this.startPinging();
      
      return true;
    } catch (error) {
      console.error('Error starting session:', error);
      this.isActive = false;
      return false;
    }
  }
  
  /**
   * Stops the current inspection session
   */
  public stopSession(): void {
    try {
      console.log('Stopping inspection session');
      this.isActive = false;
      
      // Stop ping interval
      if (this.pingInterval) {
        clearInterval(this.pingInterval);
        this.pingInterval = null;
      }
      
      // Only clear if it's our session
      const existingSession = this.getExistingSession();
      if (existingSession && existingSession.tabId === this.tabId) {
        localStorage.removeItem(INSPECTION_SESSION_KEY);
        console.log('Session removed from localStorage');
      } else if (existingSession) {
        console.log('Not removing session as it belongs to another tab');
      } else {
        console.log('No active session found to stop');
      }
    } catch (error) {
      console.error('Error stopping session:', error);
    }
  }
  
  /**
   * Checks if an inspection session is already active in another tab
   * @returns boolean indicating if another tab has an active session
   */
  public isSessionActiveInAnotherTab(): boolean {
    try {
      // Always get fresh data directly from localStorage
      const sessionJson = localStorage.getItem(INSPECTION_SESSION_KEY);
      if (!sessionJson) {
        return false;
      }
      
      const existingSession = JSON.parse(sessionJson) as InspectionSession;
      
      // Check if session is from another tab and still active
      const isAnotherTab = existingSession.tabId !== this.tabId;
      const isStale = Date.now() - existingSession.timestamp > 15000;
      const isActive = existingSession.isActive === true;
      
      console.log('Session check:', { 
        isAnotherTab, 
        isActive, 
        isStale, 
        timeSinceUpdate: Math.floor((Date.now() - existingSession.timestamp) / 1000) + 's'
      });
      
      return isAnotherTab && isActive && !isStale;
    } catch (error) {
      console.error('Error checking for active sessions:', error);
      return false;
    }
  }
  
  /**
   * Checks if the current tab has an active session
   */
  public isCurrentSessionActive(): boolean {
    return this.isActive;
  }
  
  /**
   * Starts pinging to keep the session alive
   */
  private startPinging(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
    }
    
    this.pingInterval = setInterval(() => {
      if (this.isActive) {
        this.saveSession();
      } else if (this.pingInterval) {
        clearInterval(this.pingInterval);
        this.pingInterval = null;
      }
    }, SESSION_PING_INTERVAL);
  }
  
  /**
   * Saves the current session to localStorage
   */
  private saveSession(): void {
    if (!this.isActive) return;
    
    const session: InspectionSession = {
      tabId: this.tabId,
      timestamp: Date.now(),
      isActive: this.isActive
    };
    
    localStorage.setItem(INSPECTION_SESSION_KEY, JSON.stringify(session));
  }
  
  /**
   * Gets the existing session from localStorage
   */
  private getExistingSession(): InspectionSession | null {
    const sessionJson = localStorage.getItem(INSPECTION_SESSION_KEY);
    
    if (!sessionJson) {
      return null;
    }
    
    try {
      return JSON.parse(sessionJson) as InspectionSession;
    } catch (error) {
      console.error('Failed to parse inspection session', error);
      return null;
    }
  }
  
  /**
   * Handles storage changes from other tabs
   */
  private handleStorageChange = (event: StorageEvent): void => {
    if (event.key !== INSPECTION_SESSION_KEY) return;
    
    console.log('Storage change detected for inspection session');
    
    // If the session was cleared by another tab
    if (!event.newValue) {
      console.log('Session was cleared in another tab');
      // Our session was stopped by another tab
      if (this.isActive) {
        const existingSession = this.getExistingSession();
        // If there's no session or it's not ours, we should stop
        if (!existingSession || existingSession.tabId !== this.tabId) {
          console.log('Stopping our session as it was cleared elsewhere');
          this.isActive = false;
          if (this.pingInterval) {
            clearInterval(this.pingInterval);
            this.pingInterval = null;
          }
        }
      }
      return;
    }
    
    try {
      const newSession = JSON.parse(event.newValue) as InspectionSession;
      console.log('New session data received:', { 
        tabId: newSession.tabId, 
        ourTabId: this.tabId,
        isActive: newSession.isActive, 
        timestamp: new Date(newSession.timestamp).toISOString()
      });
      
      // If another tab claimed the session and our session is active
      if (newSession.tabId !== this.tabId && this.isActive) {
        // Newer session from another tab is taking over
        if (newSession.timestamp > Date.now() - 5000) {
          console.log('Another tab took over the session - stopping ours');
          this.isActive = false;
          if (this.pingInterval) {
            clearInterval(this.pingInterval);
            this.pingInterval = null;
          }
        } 
        // Our session is newer, reclaim it
        else if (this.isActive) {
          console.log('Our session is newer - reclaiming session');
          this.saveSession();
        }
      }
    } catch (error) {
      console.error('Failed to parse changed session', error);
    }
  };
  
  /**
   * Cleans up the session when the tab is closed
   */
  private cleanupSession = (): void => {
    try {
      if (!this.isActive) return;
      
      const existingSession = this.getExistingSession();
      
      // Only remove if it's our session
      if (existingSession && existingSession.tabId === this.tabId) {
        localStorage.removeItem(INSPECTION_SESSION_KEY);
        console.log('Session cleaned up on tab close');
      }
    } catch (error) {
      console.error('Error in cleanupSession:', error);
    }
  };
  
  /**
   * Disposes the service, cleaning up all listeners
   */
  public dispose(): void {
    this.stopSession();
    window.removeEventListener('storage', this.handleStorageChange);
    window.removeEventListener('beforeunload', this.cleanupSession);
  }
}

// Create singleton instance
const inspectionSessionService = new InspectionSessionService();
export default inspectionSessionService;
