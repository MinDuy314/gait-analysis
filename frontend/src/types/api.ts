// API types matching backend schemas exactly

export interface User {
  id: string
  username: string
  email?: string
  role: 'individual' | 'professional' | 'administrator'
  is_active: boolean
  created_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user_id: string
  username: string
  role: string
}

export interface Subject {
  id: string
  display_name?: string
  created_at: string
}

export interface Session {
  id: string
  subject_id: string
  camera_view?: string
  walking_speed_ms?: number
  walking_surface?: string
  height_m?: number
  mass_kg?: number
  created_at: string
  notes?: string
  slope_deg?: number
  walking_direction?: string
  footwear?: string
  calibration_status?: string
}

export interface Recording {
  id: string
  session_id: string
  server_filename: string
  file_size_bytes?: number
  validation_status: 'pending' | 'passed' | 'failed'
  annotated_video_path?: string
  annotation_status?: 'pending' | 'running' | 'completed' | 'failed'
  created_at: string
}

export type JobStatus = 'queued' | 'running' | 'completed' | 'partially_completed' | 'failed' | 'cancelled'

export interface Job {
  id: string
  session_id: string
  subject_id: string
  recording_id?: string
  status: JobStatus
  current_stage?: string
  progress_pct: number
  processed_frames?: number
  total_frames?: number
  error_message?: string
  retry_count: number
  created_at: string
  started_at?: string
  completed_at?: string
}

export interface FeatureInterpretation {
  feature_name: string
  category?: string
  value?: number | null
  unit: string
  status: 'supported' | 'limited_evidence' | 'insufficient_data' | 'not_assessable'
  rule_name?: string
  interpretation_text: string
  evidence_sources: string[]
  confidence: number
  limitations: string[]
}

export interface Assessment {
  assessment_id: string
  session_id: string
  overall_status: string
  data: {
    feature_interpretations: FeatureInterpretation[]
    grouped_measurements?: Record<string, FeatureInterpretation[]>
    reference_comparisons?: unknown[]
    bilateral_results?: unknown[]
    global_limitations?: string[]
  }
  created_at: string
}

export interface Report {
  id: string
  report_type: string
  subject_id: string
  session_id: string
  status: string
  generated_at: string
}

export interface Paginated<T> {
  items: T[]
  total: number
  skip: number
  limit: number
}

export interface AnalysisRequest {
  recording_id?: string
  camera_view: 'front' | 'side'
  pose_model: 'yolo'
}
