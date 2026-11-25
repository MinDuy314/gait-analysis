'use client'

import React, { useState } from 'react'
import Link from 'next/link'
import { useLanguage } from '@/context/LanguageContext'
import {
  LineChart,
  ArrowRight,
  TrendingUp,
  Activity,
  Layers,
  HelpCircle,
  CheckCircle2
} from 'lucide-react'

export default function ProgressPage() {
  const { t, locale } = useLanguage()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
          <LineChart className="w-6 h-6 text-teal-600" />
          <span>{locale === 'vi' ? 'Tiến độ & So sánh Dáng đi' : 'Longitudinal Progress & Comparisons'}</span>
        </h1>
        <p className="text-xs text-slate-500 mt-1">
          {locale === 'vi'
            ? 'Theo dõi sự thay đổi cơ sinh học theo thời gian và đánh giá khả năng so sánh giữa các phiên.'
            : 'Track biomechanical changes over time and verify session-to-session comparability.'}
        </p>
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-2">
          <div className="text-xs font-semibold text-slate-500 uppercase">
            {locale === 'vi' ? 'Kiểm tra tính tương thích' : 'Comparability Check'}
          </div>
          <div className="text-base font-bold text-slate-900 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            <span>{locale === 'vi' ? 'Chuẩn hóa góc quay' : 'Standardized View'}</span>
          </div>
          <p className="text-[11px] text-slate-500 leading-relaxed">
            {locale === 'vi'
              ? 'Hệ thống tự động kiểm tra xem 2 phiên có cùng góc camera (Front/Side) và bề mặt đi bộ trước khi so sánh.'
              : 'Verifies matching camera angles and walking speed conditions before generating comparative delta.'}
          </p>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-2">
          <div className="text-xs font-semibold text-slate-500 uppercase">
            {locale === 'vi' ? 'Baseline Tham Chiếu' : 'Baseline Builder'}
          </div>
          <div className="text-base font-bold text-slate-900 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-teal-600" />
            <span>{locale === 'vi' ? 'Khởi tạo từ phiên đầu' : 'Initial Session Baseline'}</span>
          </div>
          <p className="text-[11px] text-slate-500 leading-relaxed">
            {locale === 'vi'
              ? 'Tự động tính toán đường cơ sở (Baseline) khi tích lũy đủ các phiên của cùng một đối tượng.'
              : 'Constructs empirical individual baselines as longitudinal sessions accumulate.'}
          </p>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-2">
          <div className="text-xs font-semibold text-slate-500 uppercase">
            {locale === 'vi' ? 'Xu hướng phục hồi' : 'Rehab Trend'}
          </div>
          <div className="text-base font-bold text-slate-900 flex items-center gap-2">
            <Activity className="w-4 h-4 text-sky-600" />
            <span>{locale === 'vi' ? 'Độ ổn định nhịp bước' : 'Cadence & Symmetry'}</span>
          </div>
          <p className="text-[11px] text-slate-500 leading-relaxed">
            {locale === 'vi'
              ? 'Phân tích biến thiên thời gian sải bước (stride time SD) để đánh giá mức độ ổn định thần kinh cơ.'
              : 'Monitors stride time variability and symmetry recovery over therapy cycles.'}
          </p>
        </div>
      </div>

      {/* Workflow Navigation Card */}
      <div className="bg-white rounded-2xl border border-slate-200 p-8 shadow-xs text-center space-y-4">
        <div className="w-12 h-12 bg-teal-50 border border-teal-200 rounded-2xl flex items-center justify-center text-teal-600 mx-auto">
          <Layers className="w-6 h-6" />
        </div>
        <div className="space-y-1">
          <h3 className="text-base font-bold text-slate-900">
            {locale === 'vi' ? 'Chọn đối tượng để xem tiến trình' : 'Select Subject to View Progress'}
          </h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            {locale === 'vi'
              ? 'Vào chi tiết đối tượng cụ thể để so sánh các phiên đánh giá dáng đi theo thời gian thực.'
              : 'Open any subject profile to compare consecutive gait sessions and review progress.'}
          </p>
        </div>

        <Link
          href="/subjects"
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-teal-600 hover:bg-teal-700 text-white font-semibold text-xs rounded-xl shadow-xs transition"
        >
          <span>{locale === 'vi' ? 'Xem danh sách đối tượng' : 'Go to Subjects'}</span>
          <ArrowRight className="w-4 h-4" />
        </Link>
      </div>
    </div>
  )
}
