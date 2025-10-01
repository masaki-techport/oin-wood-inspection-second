/**
 * Types for temporary sections feature
 */

export interface TempSection {
  id: string;
  label: string;
  status: 'building' | 'completed' | 'saved';
  imageIndices: number[];
  representativeImage?: string;
  summaryColor: 'red' | 'yellow' | 'green' | 'gray';
  createdAt: number;
  completedAt?: number;
}

export interface TempSectionStats {
  totalSections: number;
  completedSections: number;
  savedSections: number;
  buildingSections: number;
  currentSectionSize: number;
  sectionCounter: number;
}

export interface TempSectionsResponse {
  sections: TempSection[];
  count: number;
  timestamp: number;
}

export interface TempSectionsStatsResponse {
  stats: TempSectionStats;
  timestamp: number;
}

export interface SaveSectionGroup {
  label: string;
  imageNumbers: number[];
  count: number;
}

export interface SaveSectionsEvent {
  event: 'save_sections';
  data: {
    groups: SaveSectionGroup[];
    totalImages: number;
    imageRange: string;
    timestamp: number;
  };
}

export interface SectionCompletedEvent {
  event: 'section_completed';
  data: {
    sections: TempSection[];
    count: number;
  };
}

export interface HeartbeatEvent {
  event: 'heartbeat';
  timestamp: number;
}

export interface ErrorEvent {
  error: string;
}

export type TempSectionsSSEEvent = 
  | SectionCompletedEvent 
  | SaveSectionsEvent 
  | HeartbeatEvent 
  | ErrorEvent;

export interface TempSectionsHookState {
  sections: TempSection[];
  stats: TempSectionStats | null;
  isLoading: boolean;
  error: string | null;
  isConnected: boolean;
  saveSections: SaveSectionGroup[] | null;
  isSaveStage: boolean;
}
