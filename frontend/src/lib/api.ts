import api from '@/lib/api-client'
import type {
  TokenResponse, User, Subject, Session, Recording,
  Job, Assessment, Report, Paginated, AnalysisRequest
} from '@/types/api'

// ─── Auth ─────────────────────────────────────────────────────────────────
export const authApi = {
  register: (body: { username: string; email?: string; password: string; role: string }) =>
    api.post<TokenResponse>('/api/v1/auth/register', body).then(r => r.data),
  login: (username: string, password: string) =>
    api.post<TokenResponse>('/api/v1/auth/login', { username, password }).then(r => r.data),
  me: () => api.get<User>('/api/v1/auth/me').then(r => r.data),
  logout: () => api.post('/api/v1/auth/logout').then(r => r.data),
}

// ─── Subjects ─────────────────────────────────────────────────────────────
export const subjectsApi = {
  list: (skip = 0, limit = 50) =>
    api.get<Paginated<Subject>>('/api/v1/subjects', { params: { skip, limit } }).then(r => r.data),
  get: (id: string) => api.get<Subject>(`/api/v1/subjects/${id}`).then(r => r.data),
  create: (display_name?: string) =>
    api.post<Subject>('/api/v1/subjects', { display_name }).then(r => r.data),
  update: (id: string, display_name: string) =>
    api.patch<Subject>(`/api/v1/subjects/${id}`, { display_name }).then(r => r.data),
  delete: (id: string) => api.delete(`/api/v1/subjects/${id}`),
}

// ─── Sessions ─────────────────────────────────────────────────────────────
export const sessionsApi = {
  list: (subject_id: string, skip = 0, limit = 50) =>
    api.get<Paginated<Session>>(`/api/v1/subjects/${subject_id}/sessions`, { params: { skip, limit } }).then(r => r.data),
  get: (id: string) => api.get<Session>(`/api/v1/sessions/${id}`).then(r => r.data),
  create: (subject_id: string, body: Partial<Session>) =>
    api.post<Session>(`/api/v1/subjects/${subject_id}/sessions`, body).then(r => r.data),
}

// ─── Recordings ───────────────────────────────────────────────────────────
export const recordingsApi = {
  list: (session_id: string) =>
    api.get<Paginated<Recording>>(`/api/v1/sessions/${session_id}/recordings`).then(r => r.data),
  get: (id: string) => api.get<Recording>(`/api/v1/recordings/${id}`).then(r => r.data),
  upload: (session_id: string, file: File, onProgress?: (pct: number) => void) => {
    const form = new FormData()
    form.append('file', file)
    return api.post<Recording>(`/api/v1/sessions/${session_id}/recordings`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (onProgress && e.total) onProgress(Math.round((e.loaded * 100) / e.total))
      },
    }).then(r => r.data)
  },
  annotatedVideoUrl: (id: string) => `${process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'}/api/v1/recordings/${id}/annotated-video`,
}

// ─── Analysis ─────────────────────────────────────────────────────────────
export const analysisApi = {
  submit: (session_id: string, body: AnalysisRequest) =>
    api.post<Job>(`/api/v1/sessions/${session_id}/analysis`, body).then(r => r.data),
}

// ─── Jobs ─────────────────────────────────────────────────────────────────
export const jobsApi = {
  get: (id: string) => api.get<Job>(`/api/v1/jobs/${id}`).then(r => r.data),
  retry: (id: string) => api.post<Job>(`/api/v1/jobs/${id}/retry`).then(r => r.data),
  cancel: (id: string) => api.post(`/api/v1/jobs/${id}/cancel`).then(r => r.data),
}

// ─── Assessments ──────────────────────────────────────────────────────────
export const assessmentsApi = {
  get: (session_id: string) =>
    api.get<Assessment>(`/api/v1/sessions/${session_id}/assessment`).then(r => r.data),
}

// ─── Reports ──────────────────────────────────────────────────────────────
export const reportsApi = {
  generate: (session_id: string, report_type: 'individual' | 'professional') =>
    api.post<Report>(`/api/v1/sessions/${session_id}/reports`, { report_type }).then(r => r.data),
  get: (id: string) => api.get<Report>(`/api/v1/reports/${id}`).then(r => r.data),
  downloadUrl: (id: string) => `${process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'}/api/v1/reports/${id}/download`,
}

// ─── Progress ─────────────────────────────────────────────────────────────
export const progressApi = {
  get: (session_id: string) =>
    api.get(`/api/v1/sessions/${session_id}/progress`).then(r => r.data),
}
