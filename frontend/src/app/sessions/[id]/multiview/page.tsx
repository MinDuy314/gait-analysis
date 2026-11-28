'use client'

import React, { useState, useEffect, useCallback, use } from 'react'
import Link from 'next/link'
import { analysisApi, sessionsApi } from '@/lib/api'
import { useLanguage } from '@/context/LanguageContext'
import type { CameraView, MultiViewAssessment, MultiViewView, PoseModel } from '@/types/api'
import PoseModelSelect from '@/components/gait/PoseModelSelect'
import {
  ArrowLeft,
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  Info,
  Loader2,
  Play,
  Video,
  XCircle,
  ArrowRight,
} from 'lucide-react'

const VIEW_LABEL: Record<CameraView, { en: string; vi: string }> = {
  front: { en: 'Front view', vi: 'Góc phía trước' },
  side: { en: 'Side view', vi: 'Góc bên hông' },
  rear: { en: 'Rear view', vi: 'Góc phía sau' },
}

// Backend timestamps are naive UTC; mark them as UTC before formatting.
const toDate = (s?: string | null) => (s ? new Date(/[zZ]|[+-]\d\d:\d\d$/.test(s) ? s : `${s}Z`) : null)

// Extract the FastAPI error detail from an Axios-style error.
const errDetail = (err: unknown): string | undefined =>
  (err as { response?: { data?: { detail?: string } } } | null)?.response?.data?.detail

const fmt = (v: number | null | undefined, digits = 2) =>
  v === null || v === undefined || Number.isNaN(v) ? '—' : Number(v).toFixed(digits).replace(/\.?0+$/, '')

export default function MultiViewAssessmentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: sessionId } = use(params)
  const { locale } = useLanguage()
  const isVi = locale === 'vi'
  const t = (en: string, vi: string) => (isVi ? vi : en)

  const [data, setData] = useState<MultiViewAssessment | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState<string | null>(null)
  const [poseModel, setPoseModel] = useState<PoseModel>('yolo')
  const [actionError, setActionError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const mv = await sessionsApi.multiview(sessionId)
      setData(mv)
      setError(null)
      return mv
    } catch (err) {
      setError(errDetail(err) || t('Failed to load assessment.', 'Không thể tải đánh giá.'))
      return null
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId])

  useEffect(() => {
    load()
  }, [load])

  // Poll while any view is processing.
  const anyProcessing = !!data?.views.some((v) => v.status === 'processing')
  useEffect(() => {
    if (!anyProcessing) return
    const id = setInterval(load, 2000)
    return () => clearInterval(id)
  }, [anyProcessing, load])

  const analyse = async (views: MultiViewView[]) => {
    setActionError(null)
    for (const v of views) {
      if (!v.recording) continue
      setSubmitting(v.camera_view)
      try {
        // Each view is analysed separately with its own labelled camera view.
        await analysisApi.submit(sessionId, { recording_id: v.recording.id, camera_view: v.camera_view, pose_model: poseModel })
      } catch (err) {
        setActionError(errDetail(err) || t('Could not start analysis.', 'Không thể bắt đầu phân tích.'))
        break
      }
    }
    setSubmitting(null)
    await load()
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-slate-500 text-sm gap-2">
        <Loader2 className="w-4 h-4 animate-spin" /> {t('Loading…', 'Đang tải…')}
      </div>
    )
  }
  if (error || !data) {
    return (
      <div className="max-w-2xl mx-auto p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700 flex gap-2">
        <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" /> {error}
      </div>
    )
  }

  const pending = data.views.filter((v) => v.recording && (v.status === 'recorded' || v.status === 'failed'))
  const combinedLabel: Record<string, string> = {
    not_available: t('Not available – no view analysed yet', 'Chưa có – chưa phân tích góc nào'),
    processing: t('Processing', 'Đang xử lý'),
    partial: t('Partial – based on a subset of views', 'Một phần – dựa trên một số góc quay'),
    complete: t('Complete – all recorded views analysed', 'Hoàn tất – đã phân tích mọi góc đã ghi'),
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6 pb-12">
      <Link
        href={`/subjects/${data.subject_id}`}
        className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-teal-700 transition"
      >
        <ArrowLeft className="w-3.5 h-3.5" /> {t('Back to subject', 'Quay lại chi tiết đối tượng')}
      </Link>

      {/* Header */}
      <div className="bg-white rounded-2xl border border-slate-200 p-5 sm:p-6 shadow-xs flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div>
          <span className="text-xs font-semibold text-teal-700 uppercase tracking-wider">{t('Combined assessment', 'Đánh giá tổng hợp')}</span>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight mt-1">{t('Multi-view gait assessment', 'Đánh giá dáng đi đa góc quay')}</h1>
          <div className="text-xs text-slate-500 mt-1 flex flex-wrap gap-x-3 gap-y-1">
            <span>{t('Patient', 'Bệnh nhân')}: <strong className="text-slate-700">{data.subject_display_name || '—'}</strong></span>
            <span>{t('Session date', 'Ngày phiên')}: <strong className="text-slate-700">{toDate(data.session_created_at)?.toLocaleString(isVi ? 'vi-VN' : 'en-US') || '—'}</strong></span>
            <span className="font-mono text-[11px] text-slate-400">ID {sessionId.slice(0, 8)}</span>
          </div>
        </div>
        <div className="flex flex-wrap gap-2 shrink-0">
          <Link
            href={`/sessions/${sessionId}/record`}
            className="flex items-center gap-1.5 px-3.5 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-xl"
          >
            <Video className="w-4 h-4" /> {t('Record / retake views', 'Ghi / quay lại góc')}
          </Link>
          <button
            type="button"
            disabled={pending.length === 0 || submitting !== null}
            onClick={() => analyse(pending)}
            className="flex items-center gap-1.5 px-3.5 py-2 bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold rounded-xl disabled:opacity-50"
          >
            {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 fill-current" />}
            {t('Analyse pending views', 'Phân tích các góc chờ')} ({pending.length})
          </button>
        </div>
      </div>

      {pending.length > 0 && (
        <div className="bg-white rounded-2xl border border-slate-200 px-5 py-3 shadow-xs">
          <PoseModelSelect value={poseModel} onChange={setPoseModel} isVi={isVi} disabled={submitting !== null} />
        </div>
      )}

      {actionError && (
        <div className="p-3.5 bg-red-50 border border-red-200 rounded-xl flex items-start gap-2.5 text-xs text-red-700">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" /> {actionError}
        </div>
      )}

      {/* Recording completeness */}
      {data.missing_views.length > 0 && (
        <div className="p-3.5 bg-amber-50 border border-amber-200 rounded-xl flex items-start gap-2.5 text-xs text-amber-900">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>
            {t('Incomplete session. Missing views', 'Phiên chưa đầy đủ. Góc còn thiếu')}:{' '}
            <strong>{data.missing_views.map((v) => (isVi ? VIEW_LABEL[v].vi : VIEW_LABEL[v].en)).join(', ')}</strong>.{' '}
            {t('Metrics that need these views are shown as unavailable – not as normal.', 'Các chỉ số cần những góc này được hiển thị là không có dữ liệu – không phải bình thường.')}
          </span>
        </div>
      )}

      {/* Per-view cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {data.views.map((v) => (
          <ViewCard key={v.camera_view} v={v} isVi={isVi} sessionId={sessionId} submitting={submitting === v.camera_view} onAnalyse={() => analyse([v])} />
        ))}
      </div>

      {/* Combined measurements */}
      <div className="bg-white rounded-2xl border border-slate-200 p-5 sm:p-6 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <h2 className="text-base font-bold text-slate-900">{t('Combined measurements', 'Số đo tổng hợp')}</h2>
          <span className="text-xs font-semibold px-2.5 py-1 rounded-lg bg-slate-100 border border-slate-200 text-slate-700">
            {t('Status', 'Trạng thái')}: {combinedLabel[data.combined.status] || data.combined.status}
          </span>
        </div>

        {data.combined.measurements.length === 0 ? (
          <p className="text-xs text-slate-500">
            {t('No measurements yet. Analyse at least one recorded view.', 'Chưa có số đo. Hãy phân tích ít nhất một góc đã ghi.')}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-slate-500 border-b border-slate-200">
                  <th className="py-2 pr-3 font-semibold">{t('Metric', 'Chỉ số')}</th>
                  <th className="py-2 pr-3 font-semibold">{t('Value', 'Giá trị')}</th>
                  <th className="py-2 pr-3 font-semibold">{t('Source view', 'Góc nguồn')}</th>
                  <th className="py-2 pr-3 font-semibold">{t('Per view', 'Theo từng góc')}</th>
                  <th className="py-2 font-semibold">{t('Status', 'Trạng thái')}</th>
                </tr>
              </thead>
              <tbody>
                {data.combined.measurements.map((m) => (
                  <tr key={m.feature_name} className="border-b border-slate-100 align-top">
                    <td className="py-2 pr-3 font-medium text-slate-800">{m.feature_name.replace(/_/g, ' ')}</td>
                    <td className="py-2 pr-3 font-semibold text-slate-900 whitespace-nowrap">
                      {m.value !== null ? `${fmt(m.value)} ${m.unit}` : '—'}
                      {m.confidence !== null && <div className="text-[10px] font-normal text-slate-500">{t('confidence', 'độ tin cậy')} {fmt(m.confidence)}</div>}
                    </td>
                    <td className="py-2 pr-3 text-slate-700">{m.source_view ? (isVi ? VIEW_LABEL[m.source_view].vi : VIEW_LABEL[m.source_view].en) : '—'}</td>
                    <td className="py-2 pr-3 text-slate-600">
                      {m.per_view.map((p) => (
                        <div key={p.camera_view} className="whitespace-nowrap">
                          {p.camera_view}: {p.value !== null ? fmt(p.value) : '—'}
                          {!m.eligible_views.includes(p.camera_view) && <span className="text-slate-400"> ({t('view not suitable', 'góc không phù hợp')})</span>}
                        </div>
                      ))}
                    </td>
                    <td className="py-2">
                      <StatusBadge status={m.status} isVi={isVi} />
                      {m.note && <div className="text-[10px] text-slate-500 mt-1 max-w-[220px]">{m.note}</div>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {data.combined.not_combined.length > 0 && (
          <p className="text-[11px] text-slate-500">
            {t('Shown per view only (no validated cross-view mapping)', 'Chỉ hiển thị theo từng góc (chưa có quy tắc kết hợp)')}:{' '}
            {data.combined.not_combined.map((n) => n.feature_name.replace(/_/g, ' ')).join(', ')}
          </p>
        )}

        <div className="p-3.5 bg-sky-50 border border-sky-200 rounded-xl text-[11px] text-sky-900 space-y-1">
          <div className="font-semibold flex items-center gap-1.5"><Info className="w-3.5 h-3.5" /> {t('How views are combined', 'Cách kết hợp các góc quay')}</div>
          <ul className="list-disc list-inside space-y-0.5">
            {data.combined.limitations.map((l) => <li key={l}>{l}</li>)}
            <li>
              {t(
                'Values are 2D video estimates pending clinician review; they are not validated clinical measurements.',
                'Giá trị là ước tính từ video 2D, chờ bác sĩ xem xét; không phải số đo lâm sàng đã được kiểm chứng.'
              )}
            </li>
          </ul>
        </div>
      </div>
    </div>
  )
}

function StatusBadge({ status, isVi }: { status: string; isVi: boolean }) {
  const map: Record<string, { cls: string; icon: React.ReactNode; en: string; vi: string }> = {
    combined: { cls: 'bg-emerald-50 border-emerald-200 text-emerald-800', icon: <CheckCircle2 className="w-3 h-3" />, en: 'Single-view value', vi: 'Giá trị một góc' },
    conflicting: { cls: 'bg-red-50 border-red-200 text-red-800', icon: <XCircle className="w-3 h-3" />, en: 'Views disagree', vi: 'Các góc mâu thuẫn' },
    insufficient_data: { cls: 'bg-slate-50 border-slate-200 text-slate-600', icon: <CircleDashed className="w-3 h-3" />, en: 'Unavailable', vi: 'Không có dữ liệu' },
  }
  const s = map[status] || map.insufficient_data
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md border text-[11px] font-semibold ${s.cls}`}>
      {s.icon} {isVi ? s.vi : s.en}
    </span>
  )
}

function ViewCard({
  v,
  isVi,
  sessionId,
  submitting,
  onAnalyse,
}: {
  v: MultiViewView
  isVi: boolean
  sessionId: string
  submitting: boolean
  onAnalyse: () => void
}) {
  const t = (en: string, vi: string) => (isVi ? vi : en)
  const statusMeta: Record<string, { cls: string; en: string; vi: string }> = {
    missing: { cls: 'bg-slate-100 text-slate-600 border-slate-200', en: 'Missing', vi: 'Chưa ghi' },
    recorded: { cls: 'bg-sky-50 text-sky-800 border-sky-200', en: 'Recorded – not analysed', vi: 'Đã ghi – chưa phân tích' },
    processing: { cls: 'bg-amber-50 text-amber-800 border-amber-200', en: 'Processing', vi: 'Đang xử lý' },
    analysed: { cls: 'bg-emerald-50 text-emerald-800 border-emerald-200', en: 'Analysed', vi: 'Đã phân tích' },
    failed: { cls: 'bg-red-50 text-red-800 border-red-200', en: 'Analysis failed', vi: 'Phân tích thất bại' },
  }
  const sm = statusMeta[v.status]
  const shown = (v.assessment?.measurements || []).filter((m) => m.value !== null).slice(0, 6)

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-xs space-y-3 text-xs">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-bold text-slate-900">{isVi ? VIEW_LABEL[v.camera_view].vi : VIEW_LABEL[v.camera_view].en}</h3>
        <span className={`px-2 py-0.5 rounded-md border text-[11px] font-semibold ${sm.cls}`}>{isVi ? sm.vi : sm.en}</span>
      </div>
      {!v.selected && <div className="text-[11px] text-slate-500">{t('Not in the selected views (recording kept).', 'Không nằm trong các góc đã chọn (vẫn giữ bản ghi).')}</div>}

      {v.recording ? (
        <div className="text-slate-600 space-y-0.5">
          <div>{t('Recorded', 'Thời điểm')}: {toDate(v.recording.recorded_at || v.recording.created_at)?.toLocaleString(isVi ? 'vi-VN' : 'en-US')}</div>
          <div>{t('Source', 'Nguồn')}: {v.recording.recording_source || 'upload'}{v.retake_count > 0 && ` · ${t('retakes', 'quay lại')}: ${v.retake_count}`}</div>
          {v.recording.duration_seconds != null && <div>{t('Duration', 'Thời lượng')}: {fmt(v.recording.duration_seconds, 1)} s</div>}
          {v.recording.validation_status === 'failed' && v.recording.validation_message && (
            <div className="text-red-700">{v.recording.validation_message}</div>
          )}
        </div>
      ) : (
        <p className="text-slate-500">{t('No recording for this view.', 'Chưa có bản ghi cho góc này.')}</p>
      )}

      {v.status === 'processing' && v.job && (
        <div className="space-y-1">
          <div className="flex justify-between text-slate-600"><span>{v.job.current_stage?.replace(/_/g, ' ') || t('queued', 'đang chờ')}</span><span>{Math.round(v.job.progress_pct)}%</span></div>
          <div className="w-full h-1.5 bg-slate-200 rounded-full overflow-hidden">
            <div className="h-full bg-teal-600 transition-all" style={{ width: `${Math.min(99, v.job.progress_pct)}%` }} />
          </div>
        </div>
      )}
      {v.status === 'failed' && v.job?.error_message && <div className="text-red-700 break-words">{v.job.error_message}</div>}

      {v.assessment && (
        <div className="space-y-1.5">
          {v.assessment.view_mismatch && (
            <div className="p-2 rounded-lg bg-amber-50 border border-amber-200 text-amber-900 text-[11px]">
              {t('Detected view', 'Góc phát hiện')} “{v.assessment.analysed_camera_view}” {t('differs from the labelled view; excluded from combination.', 'khác góc đã gắn nhãn; không dùng để kết hợp.')}
            </div>
          )}
          <div className="text-slate-500">{t('Overall evidence', 'Mức bằng chứng')}: <strong className="text-slate-700">{v.assessment.overall_status?.replace(/_/g, ' ') || '—'}</strong></div>
          {shown.length > 0 ? (
            <ul className="divide-y divide-slate-100 border border-slate-100 rounded-lg">
              {shown.map((m) => (
                <li key={m.feature_name} className="px-2 py-1 flex justify-between gap-2">
                  <span className="text-slate-600 truncate">{m.feature_name.replace(/_/g, ' ')}</span>
                  <span className="font-semibold text-slate-800 whitespace-nowrap">{fmt(m.value)} {m.unit}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-slate-500">{t('No measurement could be extracted from this view.', 'Không trích xuất được số đo từ góc này.')}</p>
          )}
        </div>
      )}

      <div className="flex flex-wrap gap-2 pt-1">
        {v.recording && (v.status === 'recorded' || v.status === 'failed') && (
          <button
            type="button"
            onClick={onAnalyse}
            disabled={submitting}
            className="flex items-center gap-1 px-3 py-1.5 bg-teal-600 hover:bg-teal-700 text-white font-semibold rounded-lg disabled:opacity-50"
          >
            {submitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5 fill-current" />}
            {v.status === 'failed' ? t('Re-run analysis', 'Phân tích lại') : t('Analyse', 'Phân tích')}
          </button>
        )}
        {v.status === 'analysed' && v.recording && (
          <Link
            href={`/sessions/${sessionId}/results?recording_id=${v.recording.id}`}
            className="flex items-center gap-1 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold rounded-lg"
          >
            {t('Details & video', 'Chi tiết & video')} <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        )}
      </div>
    </div>
  )
}
