// Define interfaces for streaming data types

export interface StreamingBatch {
  batch_id: string;
  batch_size: number;
  results: StreamingResult[];
}

export interface DetectionResult {
  class_name: string;
  confidence: number;
  area?: number;
  bounding_box?: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
}

export interface StreamingResult {
  file_index: number;
  filename: string;
  status: 'processing' | 'completed' | 'error';
  progress?: number;
  result?: {
    detected_defects: string[];
    confidence_scores: Record<string, number>;
    overall_confidence: number | boolean;
    processing_time_ms: number;
    file_size: number;
    mock?: boolean;
  };
  error?: string;
  timestamp: number;
}

export interface AnalysisResponse {
  result: boolean;
  error?: string;
  data?: {
    batches: StreamingBatch[];
    total_files: number;
  };
}

export interface ProgressiveAnalysisData {
  analysis_complete?: boolean;
  progress?: number;
  detections?: DetectionResult[];
  confidence_above_threshold?: boolean;
  threshold_value?: number;
  processing_time_ms?: number;
  error?: string;
}

export interface SensorStatusData {
  sensor_a: boolean;
  sensor_b: boolean;
  direction: 'left_to_right' | 'right_to_left' | 'none';
  timestamp: number;
}