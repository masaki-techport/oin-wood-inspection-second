/**
 * API client for temporary sections
 */

import { api } from '../../../lib/api-client';
import { 
  TempSectionsResponse, 
  TempSectionsStatsResponse, 
  TempSectionStats 
} from '../../../types/temp-sections';

// Use relative path; api baseURL already handles '/api' prefix in dev
const TEMP_SECTIONS_BASE_URL = '/temp-sections';

export const tempSectionsApi = {
  /**
   * Get recent temporary sections
   */
  async getTempSections(limit: number = -1): Promise<TempSectionsResponse> {
    const response = await api.get(`${TEMP_SECTIONS_BASE_URL}?limit=${limit}`);
    return response as unknown as TempSectionsResponse; // API interceptor already extracts response.data
  },

  /**
   * Get temp section statistics
   */
  async getTempSectionStats(): Promise<TempSectionsStatsResponse> {
    const response = await api.get(`${TEMP_SECTIONS_BASE_URL}/stats`);
    return response as unknown as TempSectionsStatsResponse; // API interceptor already extracts response.data
  },

  /**
   * Reset temp sections (for testing/debugging)
   */
  async resetTempSections(): Promise<{ message: string }> {
    const response = await api.post(`${TEMP_SECTIONS_BASE_URL}/reset`);
    return response as unknown as { message: string }; // API interceptor already extracts response.data
  },

  /**
   * Get SSE URL for live updates
   */
  getSSEUrl(): string {
    // Return a relative URL to avoid double '/api' when baseURL already includes it
    return `${TEMP_SECTIONS_BASE_URL}/live`;
  }
};
