'use client'

import React, { useEffect, useState, use } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { jobsApi } from '@/lib/api'
import { useLanguage } from '@/context/LanguageContext'
import type { Job } from '@/types/api'
import {
  Activity,
  CheckCircle2,
  Clock,
  AlertTriangle,
  RotateCcw,
  ArrowRight,
  Code2,
  ChevronDown,
  ChevronUp
} from 'lucide-react'

export default function AnalysisProgressPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const resolvedParams = use(params)
  const sessionId = resolvedParams.id
  const searchParams = useSearchParams()
  const jobId = searchParams.get('job_id') || ''
  const recordingId = searchParams.get('recording_id') || ''

  const router = useRouter()
  const { t, locale } = useLanguage()

  const [job, setJob] = useState<Job | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showTechnical, setShowTechnical] = useState(false)
  const [isRetrying, setIsRetrying] = useState(false)

  // Polling loop
  useEffect(() => {
    if (!jobId) return

    let isMounted = true
    const interval = setInterval(async () => {
      try {
        const j = await jobsApi.get(jobId)
        if (!isMounted) return
        setJob(j)

        if (j.status === 'completed') {
          clearInterval(interval)
          // Finished successfully -> navigate to results
          setTimeout(() => {
            router.push(`/sessions/${sessionId}/results?recording_id=${recordingId}`)
          }, 1000)
        } else if (j.status === 'failed' || j.status === 'cancelled') {
          clearInterval(interval)
        }
      } catch (err: any) {
        if (!isMounted) return
        setError(err.response?.data?.detail || 'Failed to poll job status')
      }
    }, 1500)

    return () => {
      isMounted = false
      clearInterval(interval)
    }
  }, [jobId, sessionId, recordingId, router])

  const handleRetry = async () => {
    if (!jobId) return
    setIsRetrying(true)
    try {
      const newJob = await jobsApi.retry(jobId)
      setJob(newJob)
    } catch (err: any) {
      alert(err.response?.data?.detail || t('common.error'))
    } finally {
      setIsRetrying(false)
    }
  }

  const stages = [
    { id: 'validation', label: locale === 'vi' ? 'Kiểm tra tệp video' : 'Video Validation' },
    { id: 'pose_estimation', label: locale === 'vi' ? 'Trích xuất tư thế YOLO' : 'YOLO Pose Estimation' },
    { id: 'gait_events', label: locale === 'vi' ? 'Phát hiện sự kiện tiếp đất / nhấc gót' : 'Gait Event Detection' },
    { id: 'feature_extraction', label: locale === 'vi' ? 'Tính toán cơ sinh học' : 'Biomechanical Extraction' },
    { id: 'annotation', label: locale === 'vi' ? 'Vẽ khung xương & Xuất MP4' : 'Skeleton Annotation & MP4' },
  ]

  const isFailed = job?.status === 'failed'
  const isCompleted = job?.status === 'completed'
  const progressPct = job?.progress_pct ? Math.round(job.progress_pct * 100) : 10

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="bg-white rounded-2xl border border-slate-200 p-6 sm:p-8 shadow-xs space-y-6">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="w-6 h-6 rounded-full bg-teal-100 text-teal-800 font-bold flex items-center justify-center text-xs">
              4
            </span>
            <span className="text-xs font-semibold text-teal-700 uppercase tracking-wider">
              {locale === 'vi' ? 'Bước 4 / 4: Tiến trình xử lý' : 'Step 4 / 4: Analysis Execution'}
            </span>
          </div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <Activity className="w-5 h-5 text-teal-600 animate-pulse" />
            <span>{isCompleted ? t('analysis.completed') : t('analysis.running')}</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            {locale === 'vi'
              ? 'Đang phân tích chu kỳ bước đi và mã hóa video chú thích độ phân giải đầy đủ.'
              : 'Processing gait cycles and rendering annotated MP4 video.'}
          </p>
        </div>

        {/* Progress bar */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-700 font-semibold">
            <span>
              {job?.current_stage
                ? `${t('analysis.stage')}: ${job.current_stage}`
                : isCompleted
                ? t('analysis.completed')
                : locale === 'vi'
                ? 'Đang khởi chạy luồng công việc...'
                : 'Initializing pipeline...'}
            </span>
            <span>{isCompleted ? '100%' : `${progressPct}%`}</span>
          </div>
          <div className="w-full h-3 bg-slate-100 rounded-full overflow-hidden p-0.5 border border-slate-200">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                isFailed ? 'bg-red-500' : isCompleted ? 'bg-emerald-500' : 'bg-teal-600'
              }`}
              style={{ width: `${isCompleted ? 100 : progressPct}%` }}
            />
          </div>
        </div>

        {/* Visual Pipeline Stages */}
        <div className="space-y-3 pt-2">
          <span className="text-xs font-semibold text-slate-700 block">
            {locale === 'vi' ? 'Các giai đoạn thực tế của mô hình:' : 'Pipeline Execution Stages:'}
          </span>
          <div className="space-y-2">
            {stages.map((stg, idx) => {
              const isDone = isCompleted || progressPct > (idx + 1) * 20
              const isCurrent = !isCompleted && !isFailed && progressPct >= idx * 20 && progressPct <= (idx + 1) * 20

              return (
                <div
                  key={stg.id}
                  className={`p-3 rounded-xl border flex items-center justify-between transition text-xs ${
                    isDone
                      ? 'bg-emerald-50/50 border-emerald-200 text-emerald-900'
                      : isCurrent
                      ? 'bg-teal-50 border-teal-300 text-teal-900 font-semibold'
                      : 'bg-slate-50 border-slate-200 text-slate-400'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    {isDone ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                    ) : isCurrent ? (
                      <div className="w-4 h-4 border-2 border-teal-600 border-t-transparent rounded-full animate-spin shrink-0" />
                    ) : (
                      <Clock className="w-4 h-4 text-slate-400 shrink-0" />
                    )}
                    <span>{stg.label}</span>
                  </div>
                  <span className="text-[11px] font-mono">
                    {isDone
                      ? locale === 'vi' ? 'Hoàn tất' : 'Done'
                      : isCurrent
                      ? locale === 'vi' ? 'Đang chạy' : 'Processing'
                      : locale === 'vi' ? 'Chờ' : 'Pending'}
                  </span>
                </div>
              )
            })}
          </div>
        </div>

        {/* Error Handling */}
        {isFailed && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-xl space-y-3 text-xs text-red-700">
            <div className="flex items-start gap-2.5">
              <AlertTriangle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
              <div>
                <span className="font-bold block">{t('analysis.failed')}</span>
                <p className="mt-1">{job?.error_message || error || 'Pipeline encountered an unexpected error.'}</p>
              </div>
            </div>

            <button
              onClick={handleRetry}
              disabled={isRetrying}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-red-600 text-white rounded-lg font-semibold hover:bg-red-700 transition"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>{t('analysis.retry')}</span>
            </button>
          </div>
        )}

        {/* Expandable Technical Details */}
        <div className="pt-2 border-t border-slate-100">
          <button
            type="button"
            onClick={() => setShowTechnical(!showTechnical)}
            className="flex items-center justify-between w-full py-1 text-xs font-semibold text-slate-500 hover:text-slate-800 transition"
          >
            <span className="flex items-center gap-1.5">
              <Code2 className="w-3.5 h-3.5 text-teal-600" />
              <span>{locale === 'vi' ? 'Thông tin kỹ thuật nền tảng (Job Metadata)' : 'Technical Job Details'}</span>
            </span>
            {showTechnical ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>

          {showTechnical && (
            <div className="mt-3 p-3 bg-slate-900 text-slate-200 font-mono text-[11px] rounded-xl space-y-1 overflow-x-auto">
              <div>Job ID: {jobId}</div>
              <div>Status: {job?.status || 'loading'}</div>
              <div>Current Stage: {job?.current_stage || 'none'}</div>
              <div>Retry Count: {job?.retry_count || 0}</div>
              <div>Created At: {job?.created_at || 'unknown'}</div>
              <div>Pose Model: YOLOv8-pose (COCO 17 keypoints)</div>
            </div>
          )}
        </div>

        {/* Action Button if Completed */}
        {isCompleted && (
          <div className="pt-2 flex justify-end">
            <Link
              href={`/sessions/${sessionId}/results?recording_id=${recordingId}`}
              className="flex items-center gap-2 px-6 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs rounded-xl shadow-xs transition"
            >
              <span>{t('analysis.viewResults')}</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        )}
      </div>
    </div>
  )
}
