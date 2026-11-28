'use client'

import React, { useEffect, useState, use } from 'react'
import { useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { assessmentsApi, recordingsApi, sessionsApi, jobsApi } from '@/lib/api'
import api from '@/lib/api-client'
import { useAuth } from '@/context/AuthContext'
import { useLanguage } from '@/context/LanguageContext'
import type { Assessment, Session, Recording, FeatureInterpretation, Job } from '@/types/api'
import GaitCycleAnalysisSection from '@/components/gait/GaitCycleAnalysis'
import {
  Video,
  Activity,
  FileText,
  TrendingUp,
  AlertCircle,
  CheckCircle2,
  HelpCircle,
  Download,
  ArrowLeft,
  ChevronDown,
  ChevronUp,
  ShieldAlert,
  Info,
  Maximize2,
  RotateCcw
} from 'lucide-react'

export default function SessionResultsPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const resolvedParams = use(params)
  const sessionId = resolvedParams.id
  const searchParams = useSearchParams()
  const recordingId = searchParams.get('recording_id') || ''

  const { user } = useAuth()
  const { t, locale } = useLanguage()
  const isClinician = user?.role === 'professional' || user?.role === 'administrator'

  const [assessment, setAssessment] = useState<Assessment | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [recordings, setRecordings] = useState<Recording[]>([])
  const [activeRecordingId, setActiveRecordingId] = useState<string>(recordingId)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Audience view mode: 'patient' vs 'professional'
  const [viewMode, setViewMode] = useState<'patient' | 'professional'>('patient')
  const [expandedFeatures, setExpandedFeatures] = useState<Record<string, boolean>>({})

  // Authenticated Video Stream State
  const [videoBlobUrl, setVideoBlobUrl] = useState<string | null>(null)
  const [videoLoading, setVideoLoading] = useState(false)
  const [videoError, setVideoError] = useState<string | null>(null)

  // Real-time Job Progress State
  const [job, setJob] = useState<Job | null>(null)
  const [isRetryingJob, setIsRetryingJob] = useState(false)

  // Polling for Analysis Job status while running or pending
  useEffect(() => {
    let isMounted = true

    const pollJob = async () => {
      try {
        const j = await jobsApi.getBySession(sessionId, recordingId || undefined)
        if (!isMounted) return null
        setJob(j)

        if (j.recording_id && !recordingId) {
          setActiveRecordingId(j.recording_id)
        }

        if (j.status === 'completed') {
          assessmentsApi.get(sessionId, recordingId || undefined).then((ass) => isMounted && ass && setAssessment(ass)).catch(() => null)
          recordingsApi.list(sessionId).then((recs) => {
            if (isMounted && Array.isArray(recs)) {
              setRecordings(recs)
              if (j.recording_id) {
                setActiveRecordingId(j.recording_id)
              } else {
                const comp = recs.find((r) => r.annotation_status === 'completed')
                if (comp) setActiveRecordingId(comp.id)
              }
            }
          }).catch(() => null)
        }
        return j
      } catch {
        return null
      }
    }

    pollJob()

    const interval = setInterval(async () => {
      const current = await pollJob()
      if (current && (current.status === 'completed' || current.status === 'failed' || current.status === 'cancelled')) {
        clearInterval(interval)
      }
    }, 1500)

    return () => {
      isMounted = false
      clearInterval(interval)
    }
  }, [sessionId, recordingId])

  const handleRetryJob = async () => {
    if (!job?.id) return
    setIsRetryingJob(true)
    try {
      const refreshed = await jobsApi.retry(job.id)
      setJob(refreshed)
    } catch (err: any) {
      alert(err.response?.data?.detail || t('common.error'))
    } finally {
      setIsRetryingJob(false)
    }
  }

  const getStageLabel = (stage?: string): string => {
    if (!stage) return locale === 'vi' ? 'Đang chuẩn bị...' : 'Preparing pipeline...'
    switch (stage) {
      case 'validate_recording':
        return locale === 'vi' ? 'Kiểm tra tệp video' : 'Validating video'
      case 'extract_frames':
        return locale === 'vi' ? 'Trích xuất khung hình' : 'Extracting frames'
      case 'estimate_pose':
        return locale === 'vi' ? 'Xử lý khung hình' : 'Processing frames'
      case 'detect_view':
        return locale === 'vi' ? 'Nhận diện góc quay' : 'Detecting camera view'
      case 'detect_events':
        return locale === 'vi' ? 'Phát hiện sự kiện dáng đi' : 'Detecting gait events'
      case 'segment_cycles':
        return locale === 'vi' ? 'Phân đoạn chu kỳ bước' : 'Segmenting gait cycles'
      case 'extract_features':
        return locale === 'vi' ? 'Tính toán đặc trưng cơ sinh học' : 'Extracting biomechanical features'
      case 'quality_control':
        return locale === 'vi' ? 'Kiểm định chất lượng' : 'Quality control'
      case 'assess':
        return locale === 'vi' ? 'Đánh giá dáng đi' : 'Running gait assessment'
      case 'generate_reports':
        return locale === 'vi' ? 'Tạo báo cáo kết quả' : 'Generating reports'
      case 'annotate_recording':
        return locale === 'vi' ? 'Vẽ khung xương & xuất video MP4' : 'Rendering annotated MP4 video'
      case 'finalize':
        return locale === 'vi' ? 'Hoàn tất phân tích' : 'Finalizing analysis'
      case 'queued_retry':
        return locale === 'vi' ? 'Đang xếp hàng chạy lại...' : 'Queued for retry...'
      default:
        return stage.replace(/_/g, ' ')
    }
  }

  const isJobRunning = job?.status === 'running' || job?.status === 'queued'
  const isJobFailed = job?.status === 'failed' || job?.status === 'cancelled'
  const isJobCompleted = job?.status === 'completed'

  // Overall job progress (0..99% while running, 100% ONLY when completed)
  const overallPct = isJobCompleted
    ? 100
    : Math.min(99, Math.max(0, Math.round(job?.progress_pct ?? 0)))

  // Separate frame-processing percentage: (processed_frames / total_frames) * 100
  const hasFrameCounts = !!(job?.total_frames && job.total_frames > 0)
  const safeProcessedFrames = hasFrameCounts
    ? Math.min(job?.processed_frames || 0, job!.total_frames!)
    : 0
  const framePct = hasFrameCounts
    ? Math.min(100, Math.max(0, Math.round((safeProcessedFrames / job!.total_frames!) * 100)))
    : 0

  useEffect(() => {
    Promise.all([
      assessmentsApi.get(sessionId, recordingId || undefined).catch(() => null),
      sessionsApi.get(sessionId).catch(() => null),
      recordingsApi.list(sessionId).catch(() => [] as Recording[]),
    ])
      .then(([ass, sess, recList]) => {
        if (ass) setAssessment(ass)
        if (sess) setSession(sess)
        if (Array.isArray(recList)) {
          setRecordings(recList)
          if (!recordingId && recList.length > 0) {
            const comp = recList.find((r) => r.annotation_status === 'completed')
            setActiveRecordingId((prev) => prev || (comp ? comp.id : recList[recList.length - 1].id))
          }
        }
      })
      .catch((err) => {
        setError(err.message || 'Failed to load assessment data')
      })
      .finally(() => setLoading(false))
  }, [sessionId, recordingId])

  const toggleExpand = (featureName: string) => {
    setExpandedFeatures((prev) => ({ ...prev, [featureName]: !prev[featureName] }))
  }

  const activeRec = recordings.find((r) => r.id === activeRecordingId)

  useEffect(() => {
    let isCancelled = false
    let currentBlobUrl: string | null = null

    if (!activeRecordingId || activeRec?.annotation_status !== 'completed') {
      setVideoBlobUrl(null)
      setVideoLoading(false)
      if (activeRec?.annotation_status === 'failed') {
        setVideoError(locale === 'vi' ? 'Quá trình tạo video chú thích đã thất bại.' : 'Annotated video generation failed.')
      } else {
        setVideoError(null)
      }
      return
    }

    setVideoLoading(true)
    setVideoError(null)

    api
      .get(`/api/v1/recordings/${activeRecordingId}/annotated-video`, {
        responseType: 'blob',
      })
      .then((res) => {
        if (isCancelled) return
        const contentType = String(res.headers['content-type'] || res.data?.type || '')
        if (contentType.includes('text/html') || contentType.includes('application/json') || !res.data || res.data.size === 0) {
          setVideoError(locale === 'vi' ? 'Tệp video không hợp lệ hoặc bị trống.' : 'Invalid or empty video response.')
          setVideoLoading(false)
          return
        }
        const blob = new Blob([res.data], { type: 'video/mp4' })
        currentBlobUrl = window.URL.createObjectURL(blob)
        setVideoBlobUrl(currentBlobUrl)
        setVideoLoading(false)
      })
      .catch(async (err) => {
        if (isCancelled) return
        setVideoLoading(false)
        if (err.response?.status === 403) {
          setVideoError(locale === 'vi' ? 'Không có quyền truy cập video này.' : 'Unauthorized to view this video.')
        } else if (err.response?.status === 404) {
          setVideoError(locale === 'vi' ? 'Không tìm thấy video đã phân tích trên máy chủ.' : 'Annotated video file not found on server.')
        } else if (err.response?.status === 409) {
          setVideoError(locale === 'vi' ? 'Video chú thích chưa hoàn tất.' : 'Annotated video is not ready yet.')
        } else {
          setVideoError(locale === 'vi' ? 'Lỗi khi tải video.' : 'Error loading video.')
        }
      })

    return () => {
      isCancelled = true
      if (currentBlobUrl) {
        window.URL.revokeObjectURL(currentBlobUrl)
      }
    }
  }, [activeRecordingId, activeRec?.annotation_status, locale])

  const handleDownloadMp4 = async () => {
    if (!activeRecordingId) return
    try {
      let downloadUrl = videoBlobUrl
      let shouldRevoke = false
      if (!downloadUrl) {
        const res = await api.get(`/api/v1/recordings/${activeRecordingId}/annotated-video`, {
          responseType: 'blob',
        })
        const contentType = String(res.headers['content-type'] || res.data?.type || '')
        if (contentType.includes('text/html') || contentType.includes('application/json') || !res.data || res.data.size === 0) {
          setVideoError(locale === 'vi' ? 'Không thể tải video MP4 hợp lệ.' : 'Failed to download valid MP4 video.')
          return
        }
        const blob = new Blob([res.data], { type: 'video/mp4' })
        downloadUrl = window.URL.createObjectURL(blob)
        shouldRevoke = true
      }
      const a = document.createElement('a')
      a.href = downloadUrl
      a.download = `annotated_${activeRecordingId}.mp4`
      document.body.appendChild(a)
      a.click()
      a.remove()
      if (shouldRevoke && downloadUrl) {
        window.URL.revokeObjectURL(downloadUrl)
      }
    } catch (err: any) {
      let detail = locale === 'vi' ? 'Không thể tải video MP4.' : 'Failed to download MP4 video.'
      if (err.response?.data instanceof Blob) {
        try {
          const text = await err.response.data.text()
          const parsed = JSON.parse(text)
          if (parsed?.detail) detail = parsed.detail
        } catch {}
      }
      setVideoError(detail)
    }
  }

  if (loading) {
    return (
      <div className="p-16 text-center text-sm text-slate-400">
        <div className="w-8 h-8 border-3 border-teal-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
        <span>{t('common.loading')}</span>
      </div>
    )
  }

  const features: FeatureInterpretation[] = assessment?.data?.feature_interpretations || []

  const GAIT_CATEGORIES: { key: string; en: string; vi: string }[] = [
    { key: 'temporal', en: 'Temporal Gait Parameters', vi: 'Thông số Thời gian (Temporal)' },
    { key: 'spatial', en: 'Spatial Gait Parameters', vi: 'Thông số Không gian (Spatial)' },
    { key: 'kinematic', en: 'Joint Kinematics (ROM)', vi: 'Động học Khớp (Kinematic)' },
    { key: 'symmetry', en: 'Bilateral Symmetry', vi: 'Đối xứng Hai bên (Symmetry)' },
    { key: 'postural', en: 'Postural Control', vi: 'Kiểm soát Tư thế (Postural)' },
  ]

  const inferCategory = (name: string): string => {
    const n = name.toLowerCase()
    if (n.includes('cadence') || n.includes('step_time') || n.includes('stride_time') || n.includes('stance') || n.includes('swing')) return 'temporal'
    if (n.includes('step_length') || n.includes('stride_length') || n.includes('speed')) return 'spatial'
    if (n.includes('symmetry') || n.includes('asymmetry') || n.includes('bilateral')) return 'symmetry'
    if (n.includes('trunk') || n.includes('pelvi') || n.includes('lean') || n.includes('tilt')) return 'postural'
    return 'kinematic'
  }

  const grouped: Record<string, FeatureInterpretation[]> = assessment?.data?.grouped_measurements
    ? assessment.data.grouped_measurements
    : features.reduce((acc, f) => {
        const cat = f.category || inferCategory(f.feature_name)
        if (!acc[cat]) acc[cat] = []
        acc[cat].push(f)
        return acc
      }, {} as Record<string, FeatureInterpretation[]>)

  const statusBadge = (st: string) => {
    switch (st) {
      case 'supported':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 className="w-3 h-3" />
            {t('results.supported')}
          </span>
        )
      case 'limited_evidence':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
            <AlertCircle className="w-3 h-3" />
            {t('results.limited_evidence')}
          </span>
        )
      case 'insufficient_data':
      case 'not_assessable':
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-slate-100 text-slate-600 border border-slate-200">
            <HelpCircle className="w-3 h-3" />
            {st === 'insufficient_data' ? t('results.insufficient_data') : t('results.not_assessable')}
          </span>
        )
    }
  }

  return (
    <div className="space-y-8">
      {/* Top Navigation */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <Link
            href={session ? `/subjects/${session.subject_id}` : '/subjects'}
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-teal-700 transition mb-1"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>{locale === 'vi' ? 'Quay lại chi tiết phiên' : 'Back to subject'}</span>
          </Link>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
            <Activity className="w-6 h-6 text-teal-600" />
            <span>{t('results.title')}</span>
          </h1>
          <div className="text-xs text-slate-500">
            {session?.camera_view && (
              <span className="font-semibold text-teal-800 capitalize mr-2">
                [{session.camera_view} View]
              </span>
            )}
            <span>ID: {sessionId}</span>
          </div>
        </div>

        {/* Audience Mode Switcher (Clinicians/Admins only) */}
        {isClinician && (
          <div className="flex items-center gap-2 bg-slate-100 p-1 rounded-xl self-start sm:self-auto border border-slate-200">
            <button
              onClick={() => setViewMode('patient')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                viewMode === 'patient'
                  ? 'bg-white text-teal-900 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              {locale === 'vi' ? 'Dành cho Bệnh nhân' : 'Patient View'}
            </button>
            <button
              onClick={() => setViewMode('professional')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                viewMode === 'professional'
                  ? 'bg-white text-teal-900 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              {locale === 'vi' ? 'Chuyên gia / Lâm sàng' : 'Clinician View'}
            </button>
          </div>
        )}
      </div>

      {/* Main Grid: Video Player + Key Summary */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Col (7 cols): Large Video Player */}
        <div className="lg:col-span-7 space-y-4">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
            <div className="p-4 border-b border-slate-100 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Video className="w-4 h-4 text-teal-600" />
                <span className="font-bold text-sm text-slate-900">{t('results.annotatedVideo')}</span>
              </div>
              <span className="text-[11px] px-2 py-0.5 rounded-md bg-teal-50 text-teal-700 font-semibold border border-teal-200">
                YOLO COCO 17
              </span>
            </div>

            {/* Video Player Container */}
            <div className="bg-black aspect-video relative flex items-center justify-center">
              {isJobRunning ? (
                <div className="w-full max-w-md px-6 py-8 text-center text-slate-200 space-y-4">
                  <div className="w-8 h-8 border-3 border-teal-400 border-t-transparent rounded-full animate-spin mx-auto" />
                  
                  <div className="space-y-1">
                    <p className="text-sm font-semibold text-white">
                      {getStageLabel(job?.current_stage)}
                    </p>
                    <p className="text-[11px] text-slate-400">
                      {locale === 'vi' ? 'Tiến độ tổng thể' : 'Overall pipeline progress'}: <span className="font-mono text-teal-300 font-semibold">{overallPct}%</span>
                    </p>
                  </div>

                  {/* Overall Pipeline Progress Bar */}
                  <div className="space-y-1">
                    <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden border border-slate-700">
                      <div
                        className="h-full bg-teal-500 rounded-full transition-all duration-300"
                        style={{ width: `${overallPct}%` }}
                      />
                    </div>
                    <div className="flex justify-between text-[11px] font-mono text-slate-400">
                      <span>{job?.current_stage ? job.current_stage.replace(/_/g, ' ') : 'processing'}</span>
                      <span className="font-semibold text-teal-400">{overallPct}%</span>
                    </div>
                  </div>

                  {/* Frame-Processing Progress (Distinct from Overall Progress) */}
                  {hasFrameCounts && (
                    <div className="pt-2 border-t border-slate-800 space-y-1">
                      <div className="flex justify-between text-[11px] font-mono text-slate-300">
                        <span>{locale === 'vi' ? 'Khung hình YOLO' : 'Frame processing'}</span>
                        <span className="text-sky-300 font-semibold">
                          {safeProcessedFrames} / {job?.total_frames} {locale === 'vi' ? 'khung hình' : 'frames'} ({framePct}%)
                        </span>
                      </div>
                      <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-sky-500 rounded-full transition-all duration-300"
                          style={{ width: `${framePct}%` }}
                        />
                      </div>
                    </div>
                  )}
                </div>
              ) : isJobFailed ? (
                <div className="p-8 text-center text-rose-300 space-y-3 max-w-md">
                  <AlertCircle className="w-8 h-8 mx-auto text-rose-400" />
                  <div className="space-y-1">
                    <p className="text-sm font-bold text-white">
                      {locale === 'vi' ? 'Phân tích video thất bại' : 'Video Analysis Failed'}
                    </p>
                    <p className="text-xs text-rose-300 break-words">
                      {job?.error_message || error || (locale === 'vi' ? 'Đã xảy ra lỗi trong quá trình xử lý.' : 'An error occurred during processing.')}
                    </p>
                  </div>
                  {job?.id && (
                    <button
                      type="button"
                      onClick={handleRetryJob}
                      disabled={isRetryingJob}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-rose-600/80 hover:bg-rose-600 text-white text-xs font-semibold rounded-lg transition disabled:opacity-50"
                    >
                      <RotateCcw className={`w-3.5 h-3.5 ${isRetryingJob ? 'animate-spin' : ''}`} />
                      <span>{locale === 'vi' ? 'Thử lại phân tích' : 'Retry Analysis'}</span>
                    </button>
                  )}
                </div>
              ) : videoLoading ? (
                <div className="p-8 text-center text-slate-300 space-y-2">
                  <div className="w-6 h-6 border-2 border-teal-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
                  <p className="text-xs">{locale === 'vi' ? 'Đang tải video...' : 'Loading video...'}</p>
                </div>
              ) : videoError ? (
                <div className="p-8 text-center text-rose-300 space-y-2">
                  <AlertCircle className="w-6 h-6 mx-auto text-rose-400" />
                  <p className="text-xs">{videoError}</p>
                </div>
              ) : videoBlobUrl ? (
                <video
                  controls
                  playsInline
                  className="w-full h-full object-contain"
                  src={videoBlobUrl}
                  onError={() =>
                    setVideoError(
                      locale === 'vi'
                        ? 'Trình duyệt không thể giải mã video MP4 này. Hãy thử tải tệp MP4 xuống.'
                        : 'Browser could not decode this MP4 video stream. Try downloading the MP4 file.'
                    )
                  }
                >
                  <p className="text-white text-xs p-4">
                    {t('results.noAnnotation')}
                  </p>
                </video>
              ) : (
                <div className="p-8 text-center text-slate-400 space-y-2">
                  <Video className="w-8 h-8 mx-auto" />
                  <p className="text-xs">{t('results.noAnnotation')}</p>
                </div>
              )}
            </div>

            <div className="p-4 bg-slate-50/70 border-t border-slate-100 text-xs text-slate-600 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span
                  className={`w-2 h-2 rounded-full ${
                    isJobRunning
                      ? 'bg-amber-500 animate-pulse'
                      : isJobFailed || videoError
                      ? 'bg-rose-500'
                      : activeRec?.annotation_status === 'completed' && videoBlobUrl
                      ? 'bg-emerald-500'
                      : 'bg-slate-400'
                  }`}
                />
                <span>
                  {isJobRunning
                    ? `${getStageLabel(job?.current_stage)} (${overallPct}%)`
                    : isJobFailed
                    ? locale === 'vi' ? 'Phân tích thất bại' : 'Analysis failed'
                    : videoError
                    ? videoError
                    : activeRec?.annotation_status === 'completed'
                    ? locale === 'vi' ? 'Video đã vẽ khung xương hoàn tất (100%)' : 'Annotated video ready (100%)'
                    : locale === 'vi' ? 'Video chú thích chưa sẵn sàng' : 'Annotated video not ready'}
                </span>
              </div>
              <button
                type="button"
                onClick={handleDownloadMp4}
                disabled={!activeRecordingId || activeRec?.annotation_status !== 'completed'}
                className="text-teal-700 font-semibold hover:underline flex items-center gap-1 text-[11px] disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <Download className="w-3.5 h-3.5" />
                <span>{locale === 'vi' ? 'Tải video MP4' : 'Download MP4'}</span>
              </button>
            </div>
          </div>

          {/* Quick Action Buttons */}
          <div className="flex flex-wrap gap-3">
            <Link
              href={`/sessions/${sessionId}/reports`}
              className="flex items-center gap-2 px-4 py-2.5 bg-teal-600 hover:bg-teal-700 text-white font-semibold text-xs rounded-xl shadow-xs transition"
            >
              <FileText className="w-4 h-4" />
              <span>{locale === 'vi' ? 'Tạo Báo cáo Bệnh nhân / Lâm sàng' : 'Generate Reports'}</span>
            </Link>

            <Link
              href={session ? `/progress?subject_id=${session.subject_id}` : '/progress'}
              className="flex items-center gap-2 px-4 py-2.5 bg-white border border-slate-200 hover:border-teal-500 text-slate-700 font-semibold text-xs rounded-xl shadow-xs transition"
            >
              <TrendingUp className="w-4 h-4 text-teal-600" />
              <span>{locale === 'vi' ? 'So sánh với phiên trước' : 'Compare Progress'}</span>
            </Link>
          </div>
        </div>

        {/* Right Col (5 cols): Overall Status & Biomechanical Metrics */}
        <div className="lg:col-span-5 space-y-6">
          {/* Overall Assessment Status Card */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs space-y-3">
            <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              {t('results.overallStatus')}
            </div>
            <div className="flex items-center justify-between">
              <div className="text-lg font-bold text-slate-900">
                {assessment?.overall_status === 'supported'
                  ? locale === 'vi' ? 'Có cơ sở phân tích đầy đủ' : 'Adequately Supported'
                  : locale === 'vi' ? 'Dữ liệu hạn chế' : 'Limited Evidence'}
              </div>
              {statusBadge(assessment?.overall_status || 'supported')}
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              {viewMode === 'patient'
                ? locale === 'vi'
                  ? 'Video của bạn có chất lượng tốt, trích xuất được tư thế khung xương và các mốc thời gian bước đi rõ ràng.'
                  : 'Your walking video provided clear pose landmarks and consistent step event detection.'
                : locale === 'vi'
                ? 'Mô hình phát hiện chu kỳ bước đi với độ tin cậy thỏa mãn các quy tắc cơ sinh học theo chuẩn tham chiếu.'
                : 'Pipeline detected gait cycles satisfying biomechanical rule validation against reference boundaries.'}
            </p>
          </div>

          {/* Metric Cards List */}
          <div className="space-y-3">
            <h3 className="text-sm font-bold text-slate-900 flex items-center justify-between">
              <span>{t('results.metrics')}</span>
              <span className="text-xs font-normal text-slate-400">
                {features.length} {locale === 'vi' ? 'chỉ số được ghi nhận' : 'features evaluated'}
              </span>
            </h3>

            {features.length === 0 ? (
              <div className="p-6 bg-white rounded-2xl border border-slate-200 text-center text-xs text-slate-500">
                {locale === 'vi'
                  ? 'Chưa có chỉ số dáng đi nào được tính toán cho phiên này.'
                  : 'No gait metrics currently computed for this session.'}
              </div>
            ) : (
              GAIT_CATEGORIES.map((cat) => {
                const catFeatures = grouped[cat.key] || []
                if (catFeatures.length === 0) return null
                return (
                  <div key={cat.key} className="space-y-2.5 pt-2">
                    <div className="text-xs font-bold text-teal-800 uppercase tracking-wider px-1">
                      {locale === 'vi' ? cat.vi : cat.en}
                    </div>
                    {catFeatures.map((feat) => {
                      const isExpanded = !!expandedFeatures[feat.feature_name]
                      const hasValue = feat.value !== null && feat.value !== undefined

                return (
                  <div
                    key={feat.feature_name}
                    className="bg-white rounded-2xl border border-slate-200 p-4 shadow-xs space-y-3 transition"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                          {feat.feature_name.replace(/_/g, ' ')}
                        </div>
                        <div className="text-xl font-bold text-slate-900 mt-0.5">
                          {hasValue ? (
                            <span>
                              {feat.value?.toFixed(1)}{' '}
                              <span className="text-xs font-medium text-slate-500">{feat.unit}</span>
                            </span>
                          ) : (
                            <span className="text-sm text-slate-400 italic">
                              {locale === 'vi' ? 'Không khả dụng' : 'Not available'}
                            </span>
                          )}
                        </div>
                      </div>

                      {statusBadge(feat.status)}
                    </div>

                    {/* Interpretation text */}
                    <p className="text-xs text-slate-600 leading-relaxed">
                      {feat.interpretation_text}
                    </p>

                    {/* Expandable technical details */}
                    {viewMode === 'professional' && (
                      <div className="pt-2 border-t border-slate-100">
                        <button
                          type="button"
                          onClick={() => toggleExpand(feat.feature_name)}
                          className="flex items-center justify-between w-full text-[11px] font-semibold text-teal-700 hover:text-teal-800"
                        >
                          <span>{locale === 'vi' ? 'Chi tiết cơ sinh học & độ tin cậy' : 'Biomechanical & Uncertainty Details'}</span>
                          {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                        </button>

                        {isExpanded && (
                          <div className="mt-2.5 p-3 bg-slate-50 rounded-xl space-y-2 text-[11px] text-slate-600">
                            <div className="flex justify-between">
                              <span className="font-semibold text-slate-700">Confidence:</span>
                              <span className="font-mono">{Math.round((feat.confidence || 0) * 100)}%</span>
                            </div>
                            {feat.rule_name && (
                              <div className="flex justify-between">
                                <span className="font-semibold text-slate-700">Rule:</span>
                                <span className="font-mono text-slate-500">{feat.rule_name}</span>
                              </div>
                            )}
                            {feat.limitations && feat.limitations.length > 0 && (
                              <div className="space-y-1">
                                <span className="font-semibold text-slate-700 block">Limitations:</span>
                                <ul className="list-disc list-inside text-slate-500">
                                  {feat.limitations.map((lim, i) => (
                                    <li key={i}>{lim}</li>
                                  ))}
                                </ul>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                      </div>
                    )
                  })}
                </div>
              )
            })
            )}
          </div>
        </div>
      </div>

      {/* Gait Cycle Analysis (Feature 02) – clinician view only */}
      {isClinician && viewMode === 'professional' && activeRecordingId && (
        <GaitCycleAnalysisSection key={activeRecordingId} recordingId={activeRecordingId} isVi={locale === 'vi'} />
      )}

      {/* Scientific & Clinical Disclaimer Box */}
      <div className="p-5 bg-amber-50/70 border border-amber-200/80 rounded-2xl text-xs text-amber-900 space-y-2">
        <div className="flex items-center gap-2 font-bold text-amber-800">
          <ShieldAlert className="w-4 h-4 text-amber-600" />
          <span>{locale === 'vi' ? 'Tuyên bố trách nhiệm khoa học & y tế:' : 'Scientific & Medical Disclaimer:'}</span>
        </div>
        <ul className="list-disc list-inside text-amber-800 space-y-1 leading-relaxed text-[11px]">
          <li>
            {locale === 'vi'
              ? 'Các chỉ số được trích xuất từ camera đơn kính (monocular 2D) có giới hạn phép chiếu hình học và sai số ước tính.'
              : 'Estimates derived from monocular 2D video are subject to projection limitations and pose noise.'}
          </li>
          <li>
            {locale === 'vi'
              ? 'Hệ thống không thay thế hệ thống đo đạc động lực học 3D có hiệu chuẩn chuyên dụng (3D Motion Capture).'
              : 'Monocular estimation is not an equivalent replacement for laboratory-calibrated 3D motion capture systems.'}
          </li>
          <li>
            {locale === 'vi'
              ? 'Kết quả mang tính chất hỗ trợ định lượng theo dõi tiến trình, không được dùng làm căn cứ chẩn đoán bệnh lý duy nhất.'
              : 'Results are quantitative observational aids and do not constitute a definitive medical diagnosis.'}
          </li>
        </ul>
      </div>
    </div>
  )
}
