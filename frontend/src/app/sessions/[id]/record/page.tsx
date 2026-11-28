'use client'

import React, { useState, useRef, useEffect, useCallback, use } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { recordingsApi, sessionsApi } from '@/lib/api'
import { useLanguage } from '@/context/LanguageContext'
import type { CameraView, MultiViewAssessment, MultiViewView } from '@/types/api'
import {
  Camera,
  Square,
  RotateCcw,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Sun,
  Loader2,
  Upload,
  Save,
  CircleDashed,
} from 'lucide-react'

const ALL_VIEWS: CameraView[] = ['front', 'side', 'rear']

const VIEW_INFO: Record<CameraView, { en: string; vi: string; instrEn: string[]; instrVi: string[] }> = {
  front: {
    en: 'Front view',
    vi: 'Góc phía trước',
    instrEn: [
      'Place the camera at hip height, 4–5 m in front of the walking path.',
      'Start at the far end and walk naturally straight toward the camera.',
      'Keep your whole body, head to feet, inside the guide.',
    ],
    instrVi: [
      'Đặt camera ngang hông, cách đường đi 4–5 m ở phía trước.',
      'Bắt đầu ở đầu xa và đi tự nhiên thẳng về phía camera.',
      'Giữ toàn thân, từ đầu đến chân, nằm trong khung hướng dẫn.',
    ],
  },
  side: {
    en: 'Side view',
    vi: 'Góc bên hông',
    instrEn: [
      'Place the camera at hip height, 3–4 m to the side of the walking path, perpendicular to it.',
      'Walk naturally across the frame from one side to the other.',
      'Walk at least 3–4 steps fully inside the frame.',
    ],
    instrVi: [
      'Đặt camera ngang hông, cách đường đi 3–4 m về một bên, vuông góc với hướng đi.',
      'Đi tự nhiên ngang qua khung hình từ bên này sang bên kia.',
      'Đi ít nhất 3–4 bước hoàn toàn trong khung hình.',
    ],
  },
  rear: {
    en: 'Rear view',
    vi: 'Góc phía sau',
    instrEn: [
      'Place the camera at hip height behind the start of the walking path.',
      'Start close to the camera and walk naturally straight away from it.',
      'Keep your whole body, head to feet, inside the guide.',
    ],
    instrVi: [
      'Đặt camera ngang hông, phía sau điểm bắt đầu của đường đi.',
      'Bắt đầu gần camera và đi tự nhiên thẳng ra xa.',
      'Giữ toàn thân, từ đầu đến chân, nằm trong khung hướng dẫn.',
    ],
  },
}

// Mean frame luminance (0–255) thresholds for the lighting quality check.
const LUMA_TOO_DARK = 50
const LUMA_TOO_BRIGHT = 215
const MIN_RECORD_SECONDS = 3

// Backend timestamps are naive UTC; mark them as UTC before formatting.
const toDate = (s?: string | null) => (s ? new Date(/[zZ]|[+-]\d\d:\d\d$/.test(s) ? s : `${s}Z`) : null)

// Extract the FastAPI error detail from an Axios-style error.
const errDetail = (err: unknown): string | undefined =>
  (err as { response?: { data?: { detail?: string } } } | null)?.response?.data?.detail

interface DraftRecording {
  view: CameraView
  source: 'webcam' | 'upload'
  blob: Blob
  url: string
  fileName: string
  mimeType: string
  durationSec: number | null
  recordedAt: string
  luminance: number | null
  resolution: string | null
}

function pickRecorderMime(): { mime: string; ext: string } {
  if (typeof MediaRecorder === 'undefined') return { mime: '', ext: 'webm' }
  const candidates: [string, string][] = [
    ['video/mp4', 'mp4'],
    ['video/webm;codecs=vp9', 'webm'],
    ['video/webm;codecs=vp8', 'webm'],
    ['video/webm', 'webm'],
  ]
  for (const [mime, ext] of candidates) {
    if (MediaRecorder.isTypeSupported(mime)) return { mime, ext }
  }
  return { mime: '', ext: 'webm' }
}

export default function MultiViewRecordPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: sessionId } = use(params)
  const router = useRouter()
  const { locale } = useLanguage()
  const isVi = locale === 'vi'

  const [summary, setSummary] = useState<MultiViewAssessment | null>(null)
  const [selectedViews, setSelectedViews] = useState<CameraView[]>([])
  const [activeView, setActiveView] = useState<CameraView>('front')
  const [loadError, setLoadError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const videoRef = useRef<HTMLVideoElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const startTimeRef = useRef<number>(0)
  const lumaRef = useRef<number | null>(null)

  const [cameraStatus, setCameraStatus] = useState<'idle' | 'requesting' | 'ready' | 'denied' | 'unsupported' | 'error'>('idle')
  const [cameraError, setCameraError] = useState<string | null>(null)
  const [luminance, setLuminance] = useState<number | null>(null)
  const [resolution, setResolution] = useState<{ w: number; h: number } | null>(null)

  const [countdown, setCountdown] = useState<number | null>(null)
  const [isRecording, setIsRecording] = useState(false)
  const [elapsed, setElapsed] = useState(0)

  const [drafts, setDrafts] = useState<Partial<Record<CameraView, DraftRecording>>>({})
  const [saving, setSaving] = useState<CameraView | null>(null)
  const [uploadPct, setUploadPct] = useState(0)
  const [actionError, setActionError] = useState<string | null>(null)
  const [viewsSaving, setViewsSaving] = useState(false)

  const t = (en: string, vi: string) => (isVi ? vi : en)

  // ── Load session state (supports resuming an incomplete session) ──────────
  const refresh = useCallback(async () => {
    const mv = await sessionsApi.multiview(sessionId)
    setSummary(mv)
    return mv
  }, [sessionId])

  useEffect(() => {
    let mounted = true
    refresh()
      .then((mv) => {
        if (!mounted) return
        const views = mv.selected_views?.length ? mv.selected_views : (['front', 'side', 'rear'] as CameraView[])
        setSelectedViews(views)
        const firstMissing = views.find((v) => mv.missing_views.includes(v))
        setActiveView(firstMissing || views[0])
      })
      .catch((err) => mounted && setLoadError(errDetail(err) || t('Failed to load session.', 'Không thể tải phiên.')))
      .finally(() => mounted && setLoading(false))
    return () => {
      mounted = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refresh])

  const viewState = (v: CameraView): MultiViewView | undefined => summary?.views.find((x) => x.camera_view === v)
  const isSaved = (v: CameraView) => !!viewState(v)?.recording

  // ── Camera ────────────────────────────────────────────────────────────────
  const stopStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((tr) => tr.stop())
    streamRef.current = null
  }, [])

  const startCamera = useCallback(async () => {
    if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
      setCameraStatus('unsupported')
      setCameraError(t('This browser does not support camera access. Use the file upload option instead.',
        'Trình duyệt không hỗ trợ camera. Vui lòng dùng tùy chọn tải tệp.'))
      return
    }
    stopStream()
    setCameraStatus('requesting')
    setCameraError(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false,
      })
      streamRef.current = stream
      if (videoRef.current) videoRef.current.srcObject = stream
      setCameraStatus('ready')
    } catch (err) {
      const name = (err as DOMException | null)?.name
      if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
        setCameraStatus('denied')
        setCameraError(t('Camera permission was denied. Allow camera access in your browser settings, or upload a file instead.',
          'Quyền truy cập camera bị từ chối. Hãy cho phép trong cài đặt trình duyệt hoặc tải tệp lên.'))
      } else {
        setCameraStatus('error')
        setCameraError((err as Error | null)?.message || t('Unable to start the camera.', 'Không thể khởi động camera.'))
      }
    }
  }, [stopStream, isVi]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => () => stopStream(), [stopStream])

  // Re-attach the stream when the preview element re-mounts (e.g. after reviewing a draft).
  useEffect(() => {
    if (cameraStatus === 'ready' && videoRef.current && streamRef.current && videoRef.current.srcObject !== streamRef.current) {
      videoRef.current.srcObject = streamRef.current
    }
  })

  // Lighting & resolution check from real preview frames.
  useEffect(() => {
    if (cameraStatus !== 'ready') return
    const id = setInterval(() => {
      const video = videoRef.current
      const canvas = canvasRef.current
      if (!video || !canvas || video.readyState < 2) return
      setResolution({ w: video.videoWidth, h: video.videoHeight })
      canvas.width = 160
      canvas.height = 90
      const ctx = canvas.getContext('2d', { willReadFrequently: true })
      if (!ctx) return
      ctx.drawImage(video, 0, 0, 160, 90)
      const data = ctx.getImageData(0, 0, 160, 90).data
      let total = 0
      for (let i = 0; i < data.length; i += 4) total += 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2]
      const mean = Math.round(total / (data.length / 4))
      lumaRef.current = mean
      setLuminance(mean)
    }, 800)
    return () => clearInterval(id)
  }, [cameraStatus])

  // Recording timer
  useEffect(() => {
    if (!isRecording) return
    const id = setInterval(() => setElapsed((s) => s + 1), 1000)
    return () => clearInterval(id)
  }, [isRecording])

  // Warn before leaving with unsaved drafts.
  const hasUnsavedDrafts = Object.keys(drafts).length > 0
  useEffect(() => {
    if (!hasUnsavedDrafts) return
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [hasUnsavedDrafts])

  // Revoke object URLs on unmount.
  const draftsRef = useRef(drafts)
  useEffect(() => {
    draftsRef.current = drafts
  }, [drafts])
  useEffect(() => () => Object.values(draftsRef.current).forEach((d) => d && URL.revokeObjectURL(d.url)), [])

  const lightingState: 'ok' | 'dark' | 'bright' | 'unknown' =
    luminance === null ? 'unknown' : luminance < LUMA_TOO_DARK ? 'dark' : luminance > LUMA_TOO_BRIGHT ? 'bright' : 'ok'
  const resolutionOk = !!resolution && resolution.w >= 640 && resolution.h >= 360

  const discardDraft = (v: CameraView) => {
    setDrafts((prev) => {
      const d = prev[v]
      if (d) URL.revokeObjectURL(d.url)
      const next = { ...prev }
      delete next[v]
      return next
    })
  }

  const startRecording = () => {
    if (!streamRef.current || isRecording || countdown !== null) return
    setActionError(null)
    const view = activeView
    let n = 3
    setCountdown(n)
    const cd = setInterval(() => {
      n -= 1
      if (n <= 0) {
        clearInterval(cd)
        setCountdown(null)
        beginRecorder(view)
      } else {
        setCountdown(n)
      }
    }, 1000)
  }

  const beginRecorder = (view: CameraView) => {
    if (!streamRef.current) return
    const { mime, ext } = pickRecorderMime()
    let recorder: MediaRecorder
    try {
      recorder = mime ? new MediaRecorder(streamRef.current, { mimeType: mime }) : new MediaRecorder(streamRef.current)
    } catch {
      setActionError(t('Video recording is not supported in this browser. Upload a file instead.',
        'Trình duyệt không hỗ trợ ghi video. Vui lòng tải tệp lên.'))
      return
    }
    chunksRef.current = []
    recorderRef.current = recorder
    const recordedAt = new Date().toISOString()
    const lumaAtStart = lumaRef.current
    const res = videoRef.current ? `${videoRef.current.videoWidth}x${videoRef.current.videoHeight}` : null
    recorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) chunksRef.current.push(e.data)
    }
    recorder.onstop = () => {
      const type = (recorder.mimeType || mime || 'video/webm').split(';')[0]
      const blob = new Blob(chunksRef.current, { type })
      const durationSec = Math.round(((Date.now() - startTimeRef.current) / 1000) * 10) / 10
      setIsRecording(false)
      setElapsed(0)
      discardDraft(view)
      setDrafts((prev) => ({
        ...prev,
        [view]: {
          view,
          source: 'webcam',
          blob,
          url: URL.createObjectURL(blob),
          fileName: `${view}_view_${recordedAt.replace(/[:.]/g, '-')}.${type.includes('mp4') ? 'mp4' : ext}`,
          mimeType: type,
          durationSec,
          recordedAt,
          luminance: lumaAtStart,
          resolution: res,
        },
      }))
    }
    startTimeRef.current = Date.now()
    recorder.start(250)
    setElapsed(0)
    setIsRecording(true)
  }

  const stopRecording = () => {
    if (recorderRef.current && recorderRef.current.state !== 'inactive') recorderRef.current.stop()
  }

  const onFileChosen = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    if (file.size > 200 * 1024 * 1024) {
      setActionError(t('Video file exceeds the 200 MB limit.', 'Tệp video vượt quá giới hạn 200MB.'))
      return
    }
    const view = activeView
    discardDraft(view)
    setDrafts((prev) => ({
      ...prev,
      [view]: {
        view,
        source: 'upload',
        blob: file,
        url: URL.createObjectURL(file),
        fileName: file.name,
        mimeType: file.type || 'video/mp4',
        durationSec: null,
        recordedAt: new Date(file.lastModified || Date.now()).toISOString(),
        luminance: null,
        resolution: null,
      },
    }))
  }

  // Save reviewed draft to the session. A second save for the same view is a retake:
  // the backend keeps the earlier recording but marks it superseded.
  const saveDraft = async (v: CameraView) => {
    const d = drafts[v]
    if (!d || saving) return
    setSaving(v)
    setUploadPct(0)
    setActionError(null)
    try {
      const file = new File([d.blob], d.fileName, { type: d.mimeType })
      await recordingsApi.upload(sessionId, file, setUploadPct, {
        camera_view: v,
        recording_source: d.source,
        recorded_at: d.recordedAt,
        recording_metadata: {
          client_duration_seconds: d.durationSec,
          mime_type: d.mimeType,
          capture_resolution: d.resolution,
          mean_luminance_at_start: d.luminance,
          lighting_check: d.luminance === null ? 'not_checked'
            : d.luminance < LUMA_TOO_DARK ? 'too_dark' : d.luminance > LUMA_TOO_BRIGHT ? 'too_bright' : 'ok',
        },
      })
      discardDraft(v)
      const mv = await refresh()
      const nextMissing = selectedViews.find((x) => x !== v && mv.missing_views.includes(x))
      if (nextMissing) setActiveView(nextMissing)
    } catch (err) {
      setActionError(errDetail(err) || t('Saving the recording failed. Please try again.', 'Lưu bản ghi thất bại. Vui lòng thử lại.'))
    } finally {
      setSaving(null)
    }
  }

  const toggleView = async (v: CameraView) => {
    if (viewsSaving) return
    const next = selectedViews.includes(v)
      ? selectedViews.filter((x) => x !== v)
      : ALL_VIEWS.filter((x) => x === v || selectedViews.includes(x))
    if (next.length === 0) return
    setViewsSaving(true)
    setActionError(null)
    try {
      const s = await sessionsApi.updateViews(sessionId, next)
      setSelectedViews((s.selected_views as CameraView[]) || next)
      if (!next.includes(activeView)) setActiveView(next[0])
      await refresh()
    } catch (err) {
      setActionError(errDetail(err) || t('Could not update views.', 'Không thể cập nhật góc quay.'))
    } finally {
      setViewsSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-slate-500 text-sm gap-2">
        <Loader2 className="w-4 h-4 animate-spin" /> {t('Loading session…', 'Đang tải phiên…')}
      </div>
    )
  }
  if (loadError || !summary) {
    return (
      <div className="max-w-2xl mx-auto p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700 flex gap-2">
        <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" /> {loadError}
      </div>
    )
  }

  const draft = drafts[activeView]
  const active = viewState(activeView)
  const info = VIEW_INFO[activeView]
  const savedCount = selectedViews.filter(isSaved).length
  const missing = selectedViews.filter((v) => !isSaved(v))
  const busy = isRecording || countdown !== null || saving !== null

  return (
    <div className="max-w-5xl mx-auto space-y-6 pb-12">
      <Link
        href={`/subjects/${summary.subject_id}`}
        className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-teal-700 transition"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        <span>{t('Back to subject', 'Quay lại chi tiết đối tượng')}</span>
      </Link>

      {/* Session header */}
      <div className="bg-white rounded-2xl border border-slate-200 p-5 sm:p-6 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
          <div>
            <span className="text-xs font-semibold text-teal-700 uppercase tracking-wider">
              {t('Multi-view gait assessment', 'Đánh giá dáng đi đa góc quay')}
            </span>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight mt-1">
              {t('Record camera views', 'Ghi hình các góc quay')}
            </h1>
            <div className="text-xs text-slate-500 mt-1 flex flex-wrap gap-x-3 gap-y-1">
              <span>{t('Patient', 'Bệnh nhân')}: <strong className="text-slate-700">{summary.subject_display_name || '—'}</strong></span>
              <span>
                {t('Session date', 'Ngày phiên')}:{' '}
                <strong className="text-slate-700">
                  {toDate(summary.session_created_at)?.toLocaleString(isVi ? 'vi-VN' : 'en-US') || '—'}
                </strong>
              </span>
              <span className="font-mono text-[11px] text-slate-400">ID {sessionId.slice(0, 8)}</span>
            </div>
          </div>
          <div className="text-xs font-semibold px-3 py-1.5 rounded-lg border bg-slate-50 border-slate-200 text-slate-700 self-start">
            {t('Recorded', 'Đã ghi')}: {savedCount} / {selectedViews.length}
          </div>
        </div>

        {/* View selection */}
        <div className="space-y-1.5">
          <div className="text-xs font-semibold text-slate-700">{t('Views to record in this session', 'Các góc quay trong phiên này')}</div>
          <div className="flex flex-wrap gap-2">
            {ALL_VIEWS.map((v) => {
              const on = selectedViews.includes(v)
              return (
                <button
                  key={v}
                  type="button"
                  aria-pressed={on}
                  disabled={viewsSaving || busy || (on && selectedViews.length === 1)}
                  onClick={() => toggleView(v)}
                  className={`px-3 py-1.5 rounded-lg border text-xs font-semibold transition disabled:opacity-50 ${
                    on ? 'border-teal-600 bg-teal-50 text-teal-900' : 'border-slate-200 bg-white text-slate-500 hover:bg-slate-50'
                  }`}
                >
                  {on ? '✓ ' : '+ '}
                  {isVi ? VIEW_INFO[v].vi : VIEW_INFO[v].en}
                </button>
              )
            })}
          </div>
        </div>

        {/* View tabs with status */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2" role="tablist">
          {selectedViews.map((v) => {
            const saved = isSaved(v)
            const hasDraft = !!drafts[v]
            const st = viewState(v)
            return (
              <button
                key={v}
                role="tab"
                aria-selected={activeView === v}
                disabled={busy}
                onClick={() => setActiveView(v)}
                className={`p-3 rounded-xl border text-left transition disabled:opacity-60 ${
                  activeView === v ? 'border-teal-600 ring-1 ring-teal-600 bg-teal-50/50' : 'border-slate-200 hover:bg-slate-50'
                }`}
              >
                <div className="text-sm font-bold text-slate-900">{isVi ? VIEW_INFO[v].vi : VIEW_INFO[v].en}</div>
                <div className="mt-1 text-[11px] font-semibold flex items-center gap-1">
                  {hasDraft ? (
                    <span className="text-amber-700 flex items-center gap-1"><AlertTriangle className="w-3 h-3" />{t('Recorded – review & save', 'Đã quay – xem lại & lưu')}</span>
                  ) : saved ? (
                    <span className="text-emerald-700 flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3" />
                      {t('Saved', 'Đã lưu')}{st && st.retake_count > 0 ? ` · ${t('retaken', 'đã quay lại')} ×${st.retake_count}` : ''}
                    </span>
                  ) : (
                    <span className="text-slate-500 flex items-center gap-1"><CircleDashed className="w-3 h-3" />{t('Missing', 'Chưa ghi')}</span>
                  )}
                </div>
              </button>
            )
          })}
        </div>
      </div>

      {actionError && (
        <div className="p-3.5 bg-red-50 border border-red-200 rounded-xl flex items-start gap-2.5 text-xs text-red-700">
          <AlertCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
          <span>{actionError}</span>
        </div>
      )}

      {/* Active view workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-200 p-5 shadow-xs space-y-4">
          <div className="relative aspect-video bg-slate-900 rounded-xl overflow-hidden">
            {draft ? (
              <video key={draft.url} src={draft.url} controls playsInline className="w-full h-full object-contain bg-black" />
            ) : (
              <>
                <video ref={videoRef} autoPlay muted playsInline className="w-full h-full object-contain" />
                {cameraStatus === 'ready' && (
                  // Full-body framing guide: keep head and feet between the markers.
                  <div className="pointer-events-none absolute inset-0 flex items-center justify-center" aria-hidden="true">
                    <div className="h-[88%] aspect-[1/2.2] border-2 border-dashed border-teal-300/80 rounded-[40%_40%_12%_12%] relative">
                      <span className="absolute -top-5 left-1/2 -translate-x-1/2 text-[10px] font-semibold text-teal-200 whitespace-nowrap">{t('Head', 'Đầu')}</span>
                      <span className="absolute -bottom-5 left-1/2 -translate-x-1/2 text-[10px] font-semibold text-teal-200 whitespace-nowrap">{t('Feet', 'Chân')}</span>
                    </div>
                  </div>
                )}
                {cameraStatus !== 'ready' && (
                  <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-slate-300 text-xs p-6 text-center">
                    <Camera className="w-8 h-8" />
                    {cameraError ? <span className="text-red-300 max-w-sm">{cameraError}</span> : <span>{t('Camera preview is off', 'Chưa bật xem trước camera')}</span>}
                    <button
                      type="button"
                      onClick={startCamera}
                      disabled={cameraStatus === 'requesting'}
                      className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg font-semibold disabled:opacity-50"
                    >
                      {cameraStatus === 'requesting' ? t('Requesting camera…', 'Đang mở camera…') : t('Start camera', 'Bật camera')}
                    </button>
                  </div>
                )}
                {countdown !== null && (
                  <div className="absolute inset-0 flex items-center justify-center bg-black/40 text-white text-6xl font-bold" aria-live="assertive">
                    {countdown}
                  </div>
                )}
                {isRecording && (
                  <div className="absolute top-3 left-3 px-2.5 py-1 rounded-md bg-red-600 text-white text-xs font-bold flex items-center gap-1.5" aria-live="polite">
                    <span className="w-2 h-2 rounded-full bg-white animate-pulse" /> REC {elapsed}s
                  </div>
                )}
              </>
            )}
            <canvas ref={canvasRef} className="hidden" />
          </div>

          {/* Quality checks */}
          {!draft && cameraStatus === 'ready' && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
              <div className={`p-2.5 rounded-lg border flex items-center gap-2 ${lightingState === 'ok' ? 'bg-emerald-50 border-emerald-200 text-emerald-800' : 'bg-amber-50 border-amber-200 text-amber-800'}`}>
                <Sun className="w-4 h-4 shrink-0" />
                <span>
                  {lightingState === 'ok' && t('Lighting OK', 'Ánh sáng tốt')}
                  {lightingState === 'dark' && t('Too dark – add light or face a window', 'Quá tối – hãy tăng ánh sáng')}
                  {lightingState === 'bright' && t('Too bright – avoid backlight', 'Quá sáng – tránh ngược sáng')}
                  {lightingState === 'unknown' && t('Checking lighting…', 'Đang kiểm tra ánh sáng…')}
                  {luminance !== null && <span className="opacity-70"> ({t('brightness', 'độ sáng')} {luminance}/255)</span>}
                </span>
              </div>
              <div className={`p-2.5 rounded-lg border flex items-center gap-2 ${resolutionOk ? 'bg-emerald-50 border-emerald-200 text-emerald-800' : 'bg-amber-50 border-amber-200 text-amber-800'}`}>
                <Camera className="w-4 h-4 shrink-0" />
                <span>
                  {resolution ? `${resolution.w}×${resolution.h}` : '—'}{' '}
                  {resolutionOk ? t('resolution OK', 'độ phân giải tốt') : t('low resolution (min 640×360)', 'độ phân giải thấp (tối thiểu 640×360)')}
                </span>
              </div>
            </div>
          )}

          {/* Controls */}
          <div className="flex flex-wrap items-center gap-2">
            {draft ? (
              <>
                <button
                  type="button"
                  onClick={() => saveDraft(activeView)}
                  disabled={saving !== null}
                  className="flex items-center gap-2 px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold rounded-xl disabled:opacity-50"
                >
                  {saving === activeView ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                  {saving === activeView
                    ? `${t('Saving', 'Đang lưu')} ${uploadPct}%`
                    : isSaved(activeView) ? t('Replace saved recording', 'Thay thế bản ghi đã lưu') : t('Save to session', 'Lưu vào phiên')}
                </button>
                <button
                  type="button"
                  onClick={() => discardDraft(activeView)}
                  disabled={saving !== null}
                  className="flex items-center gap-2 px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-xl disabled:opacity-50"
                >
                  <RotateCcw className="w-4 h-4" /> {t('Discard & retake', 'Hủy & quay lại')}
                </button>
                <span className="text-[11px] text-slate-500">
                  {draft.durationSec !== null && `${draft.durationSec}s · `}
                  {draft.source === 'webcam' ? t('Webcam recording – review before saving', 'Bản quay webcam – xem lại trước khi lưu') : draft.fileName}
                </span>
              </>
            ) : isRecording ? (
              <button
                type="button"
                onClick={stopRecording}
                disabled={elapsed < MIN_RECORD_SECONDS}
                className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-xs font-semibold rounded-xl disabled:opacity-50"
              >
                <Square className="w-4 h-4 fill-current" />
                {elapsed < MIN_RECORD_SECONDS ? t(`Recording… (min ${MIN_RECORD_SECONDS}s)`, `Đang quay… (tối thiểu ${MIN_RECORD_SECONDS}s)`) : t('Stop recording', 'Dừng quay')}
              </button>
            ) : (
              <>
                <button
                  type="button"
                  onClick={startRecording}
                  disabled={cameraStatus !== 'ready' || countdown !== null}
                  className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-xs font-semibold rounded-xl disabled:opacity-50"
                >
                  <span className="w-2.5 h-2.5 rounded-full bg-white" />
                  {isSaved(activeView) ? t('Retake this view', 'Quay lại góc này') : t('Start recording', 'Bắt đầu quay')}
                </button>
                <label className="flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 hover:border-teal-600 text-slate-700 text-xs font-semibold rounded-xl cursor-pointer">
                  <Upload className="w-4 h-4" /> {t('Upload a file instead', 'Tải tệp lên')}
                  <input type="file" accept="video/mp4,video/quicktime,video/x-msvideo,video/webm,.mp4,.mov,.avi,.webm" className="sr-only" onChange={onFileChosen} />
                </label>
              </>
            )}
          </div>
        </div>

        {/* Instructions & saved state */}
        <div className="space-y-4">
          <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs space-y-2">
            <h2 className="text-sm font-bold text-slate-900">{isVi ? info.vi : info.en}: {t('instructions', 'hướng dẫn')}</h2>
            <ol className="list-decimal list-inside text-xs text-slate-600 space-y-1.5">
              {(isVi ? info.instrVi : info.instrEn).map((line) => <li key={line}>{line}</li>)}
              <li>{t('Wear fitted clothing; make sure nobody else is in the frame.', 'Mặc trang phục gọn; không có người khác trong khung hình.')}</li>
            </ol>
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs space-y-2 text-xs">
            <h2 className="text-sm font-bold text-slate-900">{t('Saved recording', 'Bản ghi đã lưu')}</h2>
            {active?.recording ? (
              <dl className="grid grid-cols-2 gap-x-2 gap-y-1 text-slate-600">
                <dt>{t('Source', 'Nguồn')}</dt><dd className="font-medium text-slate-800">{active.recording.recording_source}</dd>
                <dt>{t('Recorded at', 'Thời điểm')}</dt>
                <dd className="font-medium text-slate-800">
                  {toDate(active.recording.recorded_at)?.toLocaleString(isVi ? 'vi-VN' : 'en-US') || '—'}
                </dd>
                <dt>{t('Duration', 'Thời lượng')}</dt>
                <dd className="font-medium text-slate-800">
                  {active.recording.duration_seconds != null
                    ? `${active.recording.duration_seconds}s`
                    : typeof active.recording.recording_metadata?.client_duration_seconds === 'number'
                      ? `~${active.recording.recording_metadata.client_duration_seconds}s (${t('browser estimate', 'ước tính trình duyệt')})`
                      : t('measured after processing', 'đo sau khi xử lý')}
                </dd>
                <dt>{t('Retakes', 'Số lần quay lại')}</dt><dd className="font-medium text-slate-800">{active.retake_count}</dd>
              </dl>
            ) : (
              <p className="text-slate-500">{t('Nothing saved for this view yet.', 'Chưa có bản ghi cho góc này.')}</p>
            )}
          </div>
        </div>
      </div>

      {/* Footer: missing views + navigation */}
      <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="text-xs">
          {missing.length > 0 ? (
            <span className="text-amber-800 flex items-start gap-1.5">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              {t('Missing views', 'Góc quay còn thiếu')}: {missing.map((v) => (isVi ? VIEW_INFO[v].vi : VIEW_INFO[v].en)).join(', ')}.{' '}
              {t('Your saved views are kept; you can continue later.', 'Các góc đã lưu được giữ lại; bạn có thể tiếp tục sau.')}
            </span>
          ) : (
            <span className="text-emerald-800 flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4" /> {t('All selected views are recorded.', 'Đã ghi đủ các góc quay đã chọn.')}
            </span>
          )}
          {hasUnsavedDrafts && (
            <div className="text-red-700 mt-1">{t('You have unsaved recordings. Save or discard them before leaving.', 'Bạn có bản quay chưa lưu. Hãy lưu hoặc hủy trước khi rời đi.')}</div>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            disabled={busy || hasUnsavedDrafts}
            onClick={() => router.push(`/subjects/${summary.subject_id}`)}
            className="px-4 py-2.5 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-xl disabled:opacity-50"
          >
            {t('Save & finish later', 'Lưu & tiếp tục sau')}
          </button>
          <button
            type="button"
            disabled={busy || hasUnsavedDrafts || savedCount === 0}
            onClick={() => router.push(`/sessions/${sessionId}/multiview`)}
            className="flex items-center gap-2 px-5 py-2.5 bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold rounded-xl disabled:opacity-50"
          >
            {t('Review & analyse', 'Xem lại & phân tích')} <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
