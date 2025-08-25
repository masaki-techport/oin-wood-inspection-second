// Type definitions for DebugPanel component

// Define response and result types for API calls
export interface WorkflowResponse {
  result: boolean;
  message?: string;
  data?: {
    inspection_id: number;
    analysis_results?: Array<{
      results?: string;
      inspection_details?: Array<any>;
    }>;
    presentation_results?: {
      presentation_images?: Array<{
        group_name?: string;
        image_path?: string;
      }>;
    };
  };
}

// Helper function to convert headers to object (compatible with older TypeScript targets)
export const headersToObject = (headers: Headers): Record<string, string> => {
  const result: Record<string, string> = {};
  headers.forEach((value, key) => {
    result[key] = value;
  });
  return result;
};

// Define FileWithPath type for TypeScript
export type FileWithPath = File & {
  webkitRelativePath: string;
};