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

export type ReportWorkflowStatus = 'draft' | 'pending_review' | 'approved' | 'published' | 'generated'

export interface ReportRevision {
  timestamp: string
  actor: string
  action: string
  status: string
}

export interface Report {
  id: string
  report_type: 'individual' | 'professional' | string
  title?: string | null
  subject_id: string
  session_id: string
  assessment_id?: string | null
  status: ReportWorkflowStatus
  clinician_notes?: string | null
  rehabilitation_priorities?: string[] | null
  recommendations?: string | null
  report_data?: Record<string, any> | null
  approved_by?: string | null
  approved_at?: string | null
  published_at?: string | null
  revision_history?: ReportRevision[] | null
  generated_at: string
  updated_at?: string | null
}

export type ReliabilityStatus = 'valid' | 'low_confidence' | 'invalid' | 'unavailable' | 'pending'
export type TrendStatus = 'improved' | 'unchanged' | 'declined' | 'insufficient_data'

export interface MetricSeriesPoint {
  session_id: string
  date: string
  record_type: 'session' | 'clinical_assessment'
  value: number | null
  status: ReliabilityStatus
  confidence?: number | null
  reason?: string | null
  is_baseline: boolean
  is_latest: boolean
}

export interface MetricSummary {
  metric: string
  label: string
  unit: string
  baseline_value: number | null
  baseline_date: string | null
  latest_value: number | null
  latest_date: string | null
  previous_value: number | null
  absolute_change: number | null
  percentage_change: number | null
  change_vs_previous: number | null
  percentage_change_vs_previous: number | null
  trend: TrendStatus
  trend_explanation: string
  valid_count: number
  excluded_count: number
  series: MetricSeriesPoint[]
}

export interface TimelineMetricValue {
  value: number | null
  unit: string
  status: ReliabilityStatus
  confidence?: number | null
  reason?: string | null
}

export interface TimelineItem {
  index: number
  session_id: string
  assessment_id?: string | null
  approval_status?: string | null
  record_type: 'session' | 'clinical_assessment'
  date: string
  camera_view?: string | null
  calibration_status?: string | null
  analysis_status: string
  quality_status: ReliabilityStatus
  recording_count: number
  recording_ids: string[]
  notes?: string | null
  walking_speed: TimelineMetricValue
  cadence: TimelineMetricValue
}

export interface LongitudinalProgress {
  subject_id: string
  subject_name?: string | null
  total_sessions: number
  valid_sessions_count: number
  unavailable_or_unreliable_count: number
  quality_counts: Record<ReliabilityStatus, number>
  period_start: string | null
  period_end: string | null
  walking_speed: MetricSummary
  cadence: MetricSummary
  timeline: TimelineItem[]
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
