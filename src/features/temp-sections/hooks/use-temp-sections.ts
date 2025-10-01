/**
 * React hook for managing temporary sections with SSE and polling fallback
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { 
  TempSectionsHookState, 
  TempSectionsSSEEvent, 
  SectionCompletedEvent, 
  SaveSectionsEvent,
  TempSection 
} from '../../../types/temp-sections';
import { tempSectionsApi } from '../api/temp-sections-api';
import { TempSectionsSSEClient } from '../api/sse-client';
import { diffNewSections, IncrementalRevealQueue } from '../utils/incremental-reveal';
import { sortSectionsAlphabetically } from '../utils/ordering';

const POLLING_INTERVAL = 1000; // 1 seconds
const SSE_RECONNECT_INTERVAL = 1000; // 1 seconds

export function useTempSections(limit: number = -1, isProcessing?: boolean) {
  const [state, setState] = useState<TempSectionsHookState>({
    sections: [],
    stats: null,
    isLoading: true,
    error: null,
    isConnected: false,
    saveSections: null,
    isSaveStage: false
  });

  const sseClientRef = useRef<TempSectionsSSEClient | null>(null);
  const pollingTimerRef = useRef<NodeJS.Timeout | null>(null);
  const isPollingRef = useRef(false);
  const revealTimerRef = useRef<NodeJS.Timeout | null>(null);
  const revealQueueRef = useRef<IncrementalRevealQueue>(new IncrementalRevealQueue());
  const prevProcessingRef = useRef<boolean | undefined>(undefined);

  // Fetch data function
  const fetchData = useCallback(async () => {
    try {
      console.log('🔄 Fetching temp sections data...');
      const [sectionsResponse, statsResponse] = await Promise.all([
        tempSectionsApi.getTempSections(limit),
        tempSectionsApi.getTempSectionStats()
      ]);

      console.log('✅ Temp sections response:', sectionsResponse);
      console.log('✅ Temp sections stats:', statsResponse);

      console.log('✅ Setting temp sections state:', {
        sectionsCount: sectionsResponse.sections?.length || 0,
        sections: sectionsResponse.sections,
        stats: statsResponse.stats
      });

      // incremental reveal: enqueue brand-new sections, keep existing
      setState(prev => {
        const existing = prev.sections ?? [];
        const incoming = sectionsResponse.sections ?? [];
        const newcomers = diffNewSections(existing, incoming);
        if (newcomers.length > 0) {
          revealQueueRef.current.enqueue(newcomers);
          // start reveal loop if not running
          if (!revealTimerRef.current) {
            revealTimerRef.current = setInterval(() => {
              setState(curr => {
                const next = revealQueueRef.current.dequeue();
                if (!next) {
                  if (revealTimerRef.current) {
                    clearInterval(revealTimerRef.current);
                    revealTimerRef.current = null;
                  }
                  return curr;
                }
                // Check for duplicates before adding
                const existingIds = new Set(curr.sections.map(s => s.id));
                if (existingIds.has(next.id)) {
                  return curr; // Skip duplicate
                }
                // Insert and keep display strictly A,B,C... order
                const merged = [...curr.sections, next];
                const sortedSections = sortSectionsAlphabetically(merged);
                console.log(`🔄 Added section ${next.label}, current order: ${sortedSections.map(s => s.label).join(', ')}`);
                return {
                  ...curr,
                  sections: sortedSections,
                  isLoading: false,
                  error: null,
                  stats: statsResponse.stats
                };
              });
            }, 250); // reveal one every 250ms
          }
        }
        // keep already-known items as-is
        return { ...prev, isLoading: false, error: null, stats: statsResponse.stats };
      });
    } catch (error) {
      console.error('❌ Error fetching temp sections data:', error);
      
      setState(prev => ({
        ...prev,
        sections: [],
        stats: null,
        isLoading: false,
        error: error instanceof Error ? error.message : 'Failed to fetch temp sections'
      }));
    }
  }, [limit]);

  // Handle SSE events
  const handleSSEMessage = useCallback((event: TempSectionsSSEEvent) => {
    if ('error' in event) {
      setState(prev => ({
        ...prev,
        error: event.error,
        isConnected: false
      }));
      return;
    }

    switch (event.event) {
      case 'section_completed':
        setState(prev => {
          const existing = prev.sections ?? [];
          const incoming = event.data.sections ?? [];
          const newcomers = diffNewSections(existing, incoming);
          if (newcomers.length > 0) {
            revealQueueRef.current.enqueue(newcomers);
            if (!revealTimerRef.current) {
              revealTimerRef.current = setInterval(() => {
                setState(curr => {
                  const next = revealQueueRef.current.dequeue();
                  if (!next) {
                    if (revealTimerRef.current) {
                      clearInterval(revealTimerRef.current);
                      revealTimerRef.current = null;
                    }
                    return curr;
                  }
                  // Check for duplicates before adding
                  const existingIds = new Set(curr.sections.map(s => s.id));
                  if (existingIds.has(next.id)) {
                    return curr; // Skip duplicate
                  }
                  const merged = [...curr.sections, next];
                  const sortedSections = sortSectionsAlphabetically(merged);
                  console.log(`🔄 SSE: Added section ${next.label}, current order: ${sortedSections.map(s => s.label).join(', ')}`);
                  return { ...curr, sections: sortedSections, isConnected: true, error: null };
                });
              }, 250);
            }
          }
          return { ...prev, isConnected: true, error: null };
        });
        break;

      case 'save_sections':
        setState(prev => ({
          ...prev,
          saveSections: event.data.groups,
          isSaveStage: true,
          isConnected: true,
          error: null
        }));
        break;

      case 'heartbeat':
        setState(prev => ({
          ...prev,
          isConnected: true,
          error: null
        }));
        break;
    }
  }, []);

  // Start polling fallback
  const startPolling = useCallback(() => {
    if (isPollingRef.current) return;
    
    isPollingRef.current = true;
    pollingTimerRef.current = setInterval(() => {
      fetchData();
    }, POLLING_INTERVAL);
  }, [fetchData]);

  // Stop polling
  const stopPolling = useCallback(() => {
    if (pollingTimerRef.current) {
      clearInterval(pollingTimerRef.current);
      pollingTimerRef.current = null;
    }
    isPollingRef.current = false;
  }, []);

  // Start SSE connection
  const startSSE = useCallback(() => {
    if (sseClientRef.current) return;

    const sseUrl = tempSectionsApi.getSSEUrl();
    sseClientRef.current = new TempSectionsSSEClient({
      url: sseUrl,
      onMessage: handleSSEMessage,
      onOpen: () => {
        setState(prev => ({ ...prev, isConnected: true, error: null }));
        stopPolling(); // Stop polling when SSE is connected
      },
      onError: (error) => {
        console.error('SSE error:', error);
        setState(prev => ({ ...prev, isConnected: false }));
        startPolling(); // Start polling on SSE error
      },
      onClose: () => {
        setState(prev => ({ ...prev, isConnected: false }));
        startPolling(); // Start polling when SSE closes
      },
      reconnectInterval: SSE_RECONNECT_INTERVAL,
      maxReconnectAttempts: 10
    });

    sseClientRef.current.connect();
  }, [handleSSEMessage, stopPolling, startPolling]);

  // Stop SSE connection
  const stopSSE = useCallback(() => {
    if (sseClientRef.current) {
      sseClientRef.current.disconnect();
      sseClientRef.current = null;
    }
    if (revealTimerRef.current) {
      clearInterval(revealTimerRef.current);
      revealTimerRef.current = null;
    }
    revealQueueRef.current.clear();
  }, []);

  // Clear sections when processing starts (new inspection)
  useEffect(() => {
    // Only clear when processing transitions from false/undefined to true
    if (isProcessing && prevProcessingRef.current !== true) {
      console.log('🔄 Processing started - clearing previous sections');
      
      // Clear frontend state
      setState(prev => ({
        ...prev,
        sections: [],
        saveSections: null,
        isSaveStage: false,
        error: null
      }));
      revealQueueRef.current.clear();
      
      // Also reset backend to ensure clean state
      tempSectionsApi.resetTempSections().catch(error => {
        console.warn('Failed to reset backend temp sections:', error);
      });
    }
    // Update the previous processing state
    prevProcessingRef.current = isProcessing;
  }, [isProcessing]);

  // Initialize
  useEffect(() => {
    // Initial data fetch
    fetchData();

    // Try SSE first, fallback to polling
    startSSE();

    return () => {
      stopSSE();
      stopPolling();
      if (revealTimerRef.current) {
        clearInterval(revealTimerRef.current);
        revealTimerRef.current = null;
      }
      revealQueueRef.current.clear();
    };
  }, []); // Empty dependency array to run only once

  // Manual refresh
  const refresh = useCallback(() => {
    fetchData();
  }, [fetchData]);

  // Reset temp sections
  const reset = useCallback(async () => {
    try {
      await tempSectionsApi.resetTempSections();
      setState(prev => ({
        ...prev,
        sections: [],
        saveSections: null,
        isSaveStage: false,
        error: null
      }));
      refresh();
    } catch (error) {
      console.error('Error resetting temp sections:', error);
      setState(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Failed to reset'
      }));
    }
  }, [refresh]);

  // Clear save stage
  const clearSaveStage = useCallback(() => {
    setState(prev => ({
      ...prev,
      saveSections: null,
      isSaveStage: false
    }));
  }, []);

  return {
    ...state,
    refresh,
    reset,
    clearSaveStage
  };
}
