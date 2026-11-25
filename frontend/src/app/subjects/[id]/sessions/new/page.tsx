'use client'

import React, { useState, use } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { sessionsApi } from '@/lib/api'
import { useLanguage } from '@/context/LanguageContext'
import { ArrowLeft, ChevronDown, ChevronUp, Play, Layers, AlertCircle } from 'lucide-react'

export default function NewSessionPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const resolvedParams = use(params)
  const subjectId = resolvedParams.id
  const router = useRouter()
  const { t, locale } = useLanguage()

  // Primary short form fields
  const [cameraView, setCameraView] = useState<'front' | 'side'>('front')
  const [walkingSpeed, setWalkingSpeed] = useState<string>('')
  const [walkingSurface, setWalkingSurface] = useState<string>('ground')

  // Expandable advanced fields
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [height, setHeight] = useState<string>('')
  const [mass, setMass] = useState<string>('')
  const [slopeDeg, setSlopeDeg] = useState<string>('')
  const [walkingDirection, setWalkingDirection] = useState<string>('')
  const [footwear, setFootwear] = useState<string>('barefoot')
  const [notes, setNotes] = useState<string>('')

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSubmitting(true)
    setError(null)

    const payload: any = {
      camera_view: cameraView,
      walking_surface: walkingSurface || undefined,
    }

    if (walkingSpeed) payload.walking_speed_ms = parseFloat(walkingSpeed)
    if (height) payload.height_m = parseFloat(height)
    if (mass) payload.mass_kg = parseFloat(mass)
    if (slopeDeg) payload.slope_deg = parseFloat(slopeDeg)
    if (walkingDirection) payload.walking_direction = walkingDirection
    if (footwear) payload.footwear = footwear
    if (notes) payload.notes = notes

    try {
      const sess = await sessionsApi.create(subjectId, payload)
      // Navigate straight to upload step
      router.push(`/sessions/${sess.id}/upload`)
    } catch (err: any) {
      setError(err.response?.data?.detail || t('common.error'))
      setIsSubmitting(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <Link
        href={`/subjects/${subjectId}`}
        className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-teal-700 transition"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        <span>{locale === 'vi' ? 'Quay lại chi tiết đối tượng' : 'Back to subject'}</span>
      </Link>

      <div className="bg-white rounded-2xl border border-slate-200 p-6 sm:p-8 shadow-xs space-y-6">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <Layers className="w-5 h-5 text-teal-600" />
            <span>{locale === 'vi' ? 'Tạo phiên đánh giá mới' : 'Create New Assessment Session'}</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            {locale === 'vi'
              ? 'Nhập các thông số thực nghiệm cơ bản trước khi tải lên video đi bộ.'
              : 'Specify basic experimental parameters before uploading the walking recording.'}
          </p>
        </div>

        {error && (
          <div className="p-3.5 bg-red-50 border border-red-200 rounded-xl flex items-start gap-2.5 text-xs text-red-700">
            <AlertCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Default / Short Form Section */}
          <div className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-700 block">
                {t('sessions.cameraView')} *
              </label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => setCameraView('front')}
                  className={`p-3 rounded-xl border text-left transition ${
                    cameraView === 'front'
                      ? 'border-teal-600 bg-teal-50/70 text-teal-900 ring-1 ring-teal-600 font-semibold'
                      : 'border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  <div className="text-xs font-bold">{t('sessions.front')} (Front View)</div>
                  <div className="text-[11px] text-slate-500 mt-0.5">
                    {locale === 'vi'
                      ? 'Góc chính diện. Tối ưu cho đối xứng trái/phải, rộng bước, xoay thân.'
                      : 'Frontal view. Best for bilateral symmetry, step width, torso sway.'}
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => setCameraView('side')}
                  className={`p-3 rounded-xl border text-left transition ${
                    cameraView === 'side'
                      ? 'border-teal-600 bg-teal-50/70 text-teal-900 ring-1 ring-teal-600 font-semibold'
                      : 'border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  <div className="text-xs font-bold">{t('sessions.side')} (Side View)</div>
                  <div className="text-[11px] text-slate-500 mt-0.5">
                    {locale === 'vi'
                      ? 'Góc ngang (sagittal). Tối ưu cho góc gập gối (knee ROM), độ dài sải chân.'
                      : 'Sagittal view. Best for knee flexion ROM, stride length, limb clearance.'}
                  </div>
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-700 block">
                  {t('sessions.walkingSpeed')}
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0.1"
                  max="5.0"
                  value={walkingSpeed}
                  onChange={(e) => setWalkingSpeed(e.target.value)}
                  placeholder="e.g. 1.25"
                  className="w-full px-3.5 py-2 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:bg-white focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-600 transition"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-700 block">
                  {t('sessions.walkingSurface')}
                </label>
                <select
                  value={walkingSurface}
                  onChange={(e) => setWalkingSurface(e.target.value)}
                  className="w-full px-3.5 py-2 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:bg-white focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-600 transition"
                >
                  <option value="ground">{locale === 'vi' ? 'Sàn phẳng / Mặt đất' : 'Flat Ground / Floor'}</option>
                  <option value="treadmill">{locale === 'vi' ? 'Máy chạy bộ (Treadmill)' : 'Treadmill'}</option>
                  <option value="corridor">{locale === 'vi' ? 'Hành lang lâm sàng' : 'Clinical Corridor'}</option>
                </select>
              </div>
            </div>
          </div>

          {/* Expandable Advanced Section */}
          <div className="pt-2 border-t border-slate-100">
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="flex items-center justify-between w-full py-2 text-xs font-semibold text-teal-700 hover:text-teal-800 transition"
            >
              <span>{locale === 'vi' ? 'Thông tin nhân trắc học & nâng cao (Tùy chọn)' : 'Advanced Biomechanical Metadata (Optional)'}</span>
              {showAdvanced ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>

            {showAdvanced && (
              <div className="mt-3 space-y-4 p-4 bg-slate-50/70 border border-slate-200 rounded-xl text-xs">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="font-medium text-slate-700 block">{t('sessions.height')}</label>
                    <input
                      type="number"
                      step="0.01"
                      min="0.5"
                      max="2.5"
                      value={height}
                      onChange={(e) => setHeight(e.target.value)}
                      placeholder="e.g. 1.70"
                      className="w-full px-3 py-1.5 text-xs bg-white border border-slate-200 rounded-lg focus:outline-none focus:border-teal-600"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="font-medium text-slate-700 block">{t('sessions.mass')}</label>
                    <input
                      type="number"
                      step="0.1"
                      min="10"
                      max="300"
                      value={mass}
                      onChange={(e) => setMass(e.target.value)}
                      placeholder="e.g. 68.5"
                      className="w-full px-3 py-1.5 text-xs bg-white border border-slate-200 rounded-lg focus:outline-none focus:border-teal-600"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="font-medium text-slate-700 block">{locale === 'vi' ? 'Giày dép' : 'Footwear'}</label>
                    <select
                      value={footwear}
                      onChange={(e) => setFootwear(e.target.value)}
                      className="w-full px-3 py-1.5 text-xs bg-white border border-slate-200 rounded-lg focus:outline-none focus:border-teal-600"
                    >
                      <option value="barefoot">{locale === 'vi' ? 'Chân trần' : 'Barefoot'}</option>
                      <option value="running_shoes">{locale === 'vi' ? 'Giày thể thao' : 'Running Shoes'}</option>
                      <option value="orthotic">{locale === 'vi' ? 'Giày nẹp chỉnh hình' : 'Orthotic Shoes'}</option>
                    </select>
                  </div>

                  <div className="space-y-1.5">
                    <label className="font-medium text-slate-700 block">{locale === 'vi' ? 'Độ dốc (độ)' : 'Slope (degrees)'}</label>
                    <input
                      type="number"
                      step="0.1"
                      value={slopeDeg}
                      onChange={(e) => setSlopeDeg(e.target.value)}
                      placeholder="0.0"
                      className="w-full px-3 py-1.5 text-xs bg-white border border-slate-200 rounded-lg focus:outline-none focus:border-teal-600"
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="font-medium text-slate-700 block">{t('sessions.notes')}</label>
                  <textarea
                    rows={2}
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder={locale === 'vi' ? 'Ghi chú lâm sàng, triệu chứng, hoặc mục tiêu đánh giá...' : 'Clinical notes or experimental conditions...'}
                    className="w-full px-3 py-1.5 text-xs bg-white border border-slate-200 rounded-lg focus:outline-none focus:border-teal-600"
                  />
                </div>
              </div>
            )}
          </div>

          <div className="flex items-center justify-end gap-3 pt-4">
            <Link
              href={`/subjects/${subjectId}`}
              className="px-4 py-2.5 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-xl transition"
            >
              {t('common.cancel')}
            </Link>

            <button
              type="submit"
              disabled={isSubmitting}
              className="flex items-center gap-2 px-5 py-2.5 bg-teal-600 hover:bg-teal-700 text-white font-semibold text-xs rounded-xl shadow-xs transition disabled:opacity-50"
            >
              {isSubmitting ? (
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <>
                  <span>{locale === 'vi' ? 'Tiếp tục tải video' : 'Proceed to Upload'}</span>
                  <Play className="w-3.5 h-3.5 fill-current" />
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
