'use client'

import React, { useState, useEffect, use } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { sessionsApi, analysisApi, recordingsApi } from '@/lib/api'
import { useLanguage } from '@/context/LanguageContext'
import PoseModelSelect from '@/components/gait/PoseModelSelect'
import type { PoseModel } from '@/types/api'
import {
  Camera,
  Play,
  ArrowLeft,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Eye,
  Info
} from 'lucide-react'

export default function ConfirmViewPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const resolvedParams = use(params)
  const sessionId = resolvedParams.id
  const searchParams = useSearchParams()
  const recordingId = searchParams.get('recording_id') || ''

  const router = useRouter()
  const { t, locale } = useLanguage()

  const [cameraView, setCameraView] = useState<'front' | 'side'>('front')
  const [poseModel, setPoseModel] = useState<PoseModel>('yolo')
  const [resolvedRecId, setResolvedRecId] = useState<string>(recordingId)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Fetch session and fallback recording if missing from query params
  useEffect(() => {
    sessionsApi
      .get(sessionId)
      .then((sess) => {
        if (sess.camera_view === 'side' || sess.camera_view === 'front') {
          setCameraView(sess.camera_view as 'front' | 'side')
        }
      })
      .catch((err) => console.error(err))

    if (!recordingId) {
      recordingsApi
        .list(sessionId)
        .then((recs) => {
          if (recs.length > 0) {
            setResolvedRecId(recs[recs.length - 1].id)
          }
        })
        .catch(() => null)
    }
  }, [sessionId, recordingId])

  const handleStartAnalysis = async () => {
    setIsSubmitting(true)
    setError(null)

    try {
      const targetRecId = resolvedRecId || recordingId || undefined
      const job = await analysisApi.submit(sessionId, {
        recording_id: targetRecId,
        camera_view: cameraView,
        pose_model: poseModel,
      })

      // Redirect to progress polling page
      router.push(`/sessions/${sessionId}/analysis?job_id=${job.id}&recording_id=${targetRecId || ''}`)
    } catch (err: any) {
      setError(err.response?.data?.detail || t('common.error'))
      setIsSubmitting(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <Link
        href={`/sessions/${sessionId}/upload`}
        className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-teal-700 transition"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        <span>{locale === 'vi' ? 'Quay lại bước tải video' : 'Back to upload'}</span>
      </Link>

      <div className="bg-white rounded-2xl border border-slate-200 p-6 sm:p-8 shadow-xs space-y-6">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="w-6 h-6 rounded-full bg-teal-100 text-teal-800 font-bold flex items-center justify-center text-xs">
              3
            </span>
            <span className="text-xs font-semibold text-teal-700 uppercase tracking-wider">
              {locale === 'vi' ? 'Bước 3 / 4: Xác nhận góc camera' : 'Step 3 / 4: Camera View Confirmation'}
            </span>
          </div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">
            {t('upload.viewConfirm')}
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            {locale === 'vi'
              ? 'Xác nhận góc máy quay video để thuật toán áp dụng đúng mô hình cơ sinh học tương ứng.'
              : 'Confirm the camera view angle so the engine applies the appropriate biomechanical model.'}
          </p>
        </div>

        {error && (
          <div className="p-3.5 bg-red-50 border border-red-200 rounded-xl flex items-start gap-2.5 text-xs text-red-700">
            <AlertCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {/* View selection cards */}
        <div className="space-y-4">
          <label className="text-xs font-semibold text-slate-700 block">
            {locale === 'vi' ? 'Chọn góc camera thực tế:' : 'Confirm Video Camera View:'}
          </label>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div
              onClick={() => setCameraView('front')}
              className={`p-5 rounded-2xl border cursor-pointer transition relative flex flex-col justify-between ${
                cameraView === 'front'
                  ? 'border-teal-600 bg-teal-50/60 ring-2 ring-teal-600/20 shadow-xs'
                  : 'border-slate-200 bg-white hover:bg-slate-50'
              }`}
            >
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-sm text-slate-900 flex items-center gap-2">
                    <Camera className="w-4 h-4 text-teal-600" />
                    <span>{t('sessions.front')} (Frontal)</span>
                  </span>
                  {cameraView === 'front' && (
                    <CheckCircle2 className="w-4 h-4 text-teal-600" />
                  )}
                </div>
                <p className="text-xs text-slate-600 leading-relaxed">
                  {locale === 'vi'
                    ? 'Máy quay đối diện trực diện hướng đi tới hoặc đi lùi.'
                    : 'Camera faces subject walking directly towards or away.'}
                </p>
                <div className="pt-2 border-t border-slate-100 text-[11px] text-teal-800 space-y-1">
                  <div className="font-semibold">{locale === 'vi' ? 'Các chỉ số hỗ trợ:' : 'Supported metrics:'}</div>
                  <ul className="list-disc list-inside text-slate-600">
                    <li>{locale === 'vi' ? 'Nhịp bước (Cadence)' : 'Cadence (steps/min)'}</li>
                    <li>{locale === 'vi' ? 'Đối xứng sải chân trái/phải' : 'Bilateral symmetry'}</li>
                    <li>{locale === 'vi' ? 'Độ lệch trục thân trên' : 'Trunk/pelvic sway'}</li>
                  </ul>
                </div>
              </div>
            </div>

            <div
              onClick={() => setCameraView('side')}
              className={`p-5 rounded-2xl border cursor-pointer transition relative flex flex-col justify-between ${
                cameraView === 'side'
                  ? 'border-teal-600 bg-teal-50/60 ring-2 ring-teal-600/20 shadow-xs'
                  : 'border-slate-200 bg-white hover:bg-slate-50'
              }`}
            >
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-sm text-slate-900 flex items-center gap-2">
                    <Camera className="w-4 h-4 text-teal-600" />
                    <span>{t('sessions.side')} (Sagittal)</span>
                  </span>
                  {cameraView === 'side' && (
                    <CheckCircle2 className="w-4 h-4 text-teal-600" />
                  )}
                </div>
                <p className="text-xs text-slate-600 leading-relaxed">
                  {locale === 'vi'
                    ? 'Máy quay đặt bên hông vuông góc với hướng đi bộ.'
                    : 'Camera placed perpendicular to walking corridor.'}
                </p>
                <div className="pt-2 border-t border-slate-100 text-[11px] text-teal-800 space-y-1">
                  <div className="font-semibold">{locale === 'vi' ? 'Các chỉ số hỗ trợ:' : 'Supported metrics:'}</div>
                  <ul className="list-disc list-inside text-slate-600">
                    <li>{locale === 'vi' ? 'Góc gập duỗi khớp gối (Knee ROM)' : 'Knee flexion ROM'}</li>
                    <li>{locale === 'vi' ? 'Thời gian chạm đất (Stance/Swing)' : 'Stance / swing phase duration'}</li>
                    <li>{locale === 'vi' ? 'Chiều dài sải bước (Stride length)' : 'Stride length'}</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </div>

        <PoseModelSelect value={poseModel} onChange={setPoseModel} isVi={locale === 'vi'} disabled={isSubmitting} />

        {/* Scientific Limitation Disclaimer */}
        <div className="p-4 bg-amber-50/70 border border-amber-200/60 rounded-xl text-xs text-amber-900 flex items-start gap-3">
          <Info className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
          <div className="leading-relaxed space-y-1">
            <span className="font-semibold block">
              {locale === 'vi' ? 'Nguyên lý cơ sinh học quan trọng:' : 'Biomechanical Projection Principle:'}
            </span>
            <p className="text-[11px] text-amber-800">
              {locale === 'vi'
                ? 'Camera góc trước (Front) không thể đo chính xác góc gập gối mặt phẳng đứng dọc (sagittal). Các chỉ số không đủ điều kiện sẽ được đánh dấu rõ ràng là insufficient_data thay vì gán giá trị 0.'
                : 'Front-view video cannot reliably capture sagittal knee flexion. Unavailable parameters will be explicitly reported as insufficient_data rather than zero.'}
            </p>
          </div>
        </div>

        {/* Submit */}
        <div className="flex items-center justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={handleStartAnalysis}
            disabled={isSubmitting}
            className="flex items-center gap-2 px-6 py-2.5 bg-teal-600 hover:bg-teal-700 text-white font-semibold text-xs rounded-xl shadow-xs transition disabled:opacity-50"
          >
            {isSubmitting ? (
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : (
              <>
                <Play className="w-4 h-4 fill-current" />
                <span>{locale === 'vi' ? 'Bắt đầu phân tích YOLO' : 'Start YOLO Analysis'}</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
