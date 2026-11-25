'use client'

import React, { useEffect, useState } from 'react'
import Link from 'next/link'
import { useAuth } from '@/context/AuthContext'
import { useLanguage } from '@/context/LanguageContext'
import { subjectsApi } from '@/lib/api'
import type { Subject } from '@/types/api'
import {
  Users,
  Activity,
  PlayCircle,
  FileText,
  Clock,
  ArrowRight,
  TrendingUp,
  ShieldCheck,
  CheckCircle2,
  AlertCircle
} from 'lucide-react'

export default function DashboardPage() {
  const { user } = useAuth()
  const { t, locale } = useLanguage()

  const [subjects, setSubjects] = useState<Subject[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    subjectsApi
      .list(0, 10)
      .then((res) => {
        setSubjects(res.items || [])
      })
      .catch((err) => {
        console.error('Failed to load dashboard subjects:', err)
      })
      .finally(() => {
        setLoading(false)
      })
  }, [])

  const isClinician = user?.role === 'professional' || user?.role === 'administrator'

  return (
    <div className="space-y-8">
      {/* Top Banner / Welcome */}
      <div className="bg-gradient-to-r from-teal-700 to-teal-900 rounded-2xl p-6 sm:p-8 text-white shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-teal-200 text-xs font-semibold uppercase tracking-wider">
            <ShieldCheck className="w-4 h-4 text-teal-300" />
            <span>
              {isClinician
                ? locale === 'vi'
                  ? 'Giao diện Bác sĩ / Nhà nghiên cứu'
                  : 'Clinician & Biomechanics Interface'
                : locale === 'vi'
                ? 'Giao diện Bệnh nhân'
                : 'Patient Dashboard'}
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">
            {locale === 'vi' ? 'Xin chào,' : 'Welcome back,'} {user?.username || 'User'}
          </h1>
          <p className="text-sm text-teal-100 max-w-xl leading-relaxed">
            {locale === 'vi'
              ? 'Hệ thống định lượng dáng đi bằng video thị giác máy tính YOLO. Độ chính xác cơ sinh học theo chu kỳ bước đi.'
              : 'Quantitative gait assessment using computer vision YOLO pose estimation. Track biomechanical parameters across gait cycles.'}
          </p>
        </div>

        <Link
          href="/subjects"
          className="shrink-0 flex items-center gap-2.5 px-5 py-3 bg-white text-teal-900 hover:bg-teal-50 font-semibold text-sm rounded-xl shadow-sm transition group"
        >
          <PlayCircle className="w-5 h-5 text-teal-600 group-hover:scale-105 transition-transform" />
          <span>{locale === 'vi' ? 'Bắt đầu đánh giá mới' : 'Start Assessment'}</span>
        </Link>
      </div>

      {/* Metrics Overview Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-teal-50 border border-teal-100 flex items-center justify-center text-teal-700 shrink-0">
            <Users className="w-6 h-6" />
          </div>
          <div>
            <div className="text-2xl font-bold text-slate-900">{loading ? '…' : subjects.length}</div>
            <div className="text-xs text-slate-500 font-medium">
              {locale === 'vi' ? 'Đối tượng / Bệnh nhân' : 'Total Subjects'}
            </div>
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-emerald-50 border border-emerald-100 flex items-center justify-center text-emerald-700 shrink-0">
            <Activity className="w-6 h-6" />
          </div>
          <div>
            <div className="text-2xl font-bold text-slate-900">YOLOv8</div>
            <div className="text-xs text-slate-500 font-medium">
              {locale === 'vi' ? 'Mô hình tư thế 2D' : 'Pose Estimation Model'}
            </div>
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-sky-50 border border-sky-100 flex items-center justify-center text-sky-700 shrink-0">
            <TrendingUp className="w-6 h-6" />
          </div>
          <div>
            <div className="text-2xl font-bold text-slate-900">100%</div>
            <div className="text-xs text-slate-500 font-medium">
              {locale === 'vi' ? 'Dữ liệu phân tích thực tế' : 'Verified Real Biomechanics'}
            </div>
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-700 shrink-0">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <div>
            <div className="text-2xl font-bold text-slate-900">COCO 17</div>
            <div className="text-xs text-slate-500 font-medium">
              {locale === 'vi' ? 'Khung xương chú thích video' : 'Video Annotated Skeleton'}
            </div>
          </div>
        </div>
      </div>

      {/* Main Content Sections */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Recent Subjects List (2 cols) */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <Users className="w-4 h-4 text-teal-600" />
              <span>{locale === 'vi' ? 'Danh sách đối tượng gần đây' : 'Recent Subjects'}</span>
            </h2>
            <Link
              href="/subjects"
              className="text-xs font-semibold text-teal-700 hover:text-teal-800 flex items-center gap-1"
            >
              <span>{locale === 'vi' ? 'Xem tất cả' : 'View all'}</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden divide-y divide-slate-100">
            {loading ? (
              <div className="p-8 text-center text-sm text-slate-400">
                <div className="w-6 h-6 border-2 border-teal-600 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
                <span>{t('common.loading')}</span>
              </div>
            ) : subjects.length === 0 ? (
              <div className="p-8 text-center space-y-3">
                <div className="w-12 h-12 bg-slate-100 rounded-full flex items-center justify-center text-slate-400 mx-auto">
                  <Users className="w-5 h-5" />
                </div>
                <div className="text-sm font-semibold text-slate-700">
                  {t('subjects.noSubjects')}
                </div>
                <Link
                  href="/subjects"
                  className="inline-flex items-center gap-1.5 px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white font-medium text-xs rounded-xl shadow-xs transition"
                >
                  <PlayCircle className="w-4 h-4" />
                  <span>{t('subjects.new')}</span>
                </Link>
              </div>
            ) : (
              subjects.map((sub) => (
                <Link
                  key={sub.id}
                  href={`/subjects/${sub.id}`}
                  className="p-4 sm:px-6 flex items-center justify-between hover:bg-slate-50/80 transition group"
                >
                  <div className="space-y-1">
                    <div className="font-semibold text-sm text-slate-900 group-hover:text-teal-700 transition">
                      {sub.display_name || (locale === 'vi' ? 'Chưa đặt tên' : 'Unnamed Subject')}
                    </div>
                    <div className="flex items-center gap-3 text-xs text-slate-400">
                      <span className="font-mono text-[11px] text-slate-400">ID: {sub.id.slice(0, 8)}...</span>
                      <span>•</span>
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {new Date(sub.created_at).toLocaleDateString(locale === 'vi' ? 'vi-VN' : 'en-US')}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 text-xs font-semibold text-teal-700">
                    <span>{locale === 'vi' ? 'Chi tiết' : 'Details'}</span>
                    <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
                  </div>
                </Link>
              ))
            )}
          </div>
        </div>

        {/* Quick Workflow Guide & Scientific Information (1 col) */}
        <div className="space-y-6">
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs space-y-4">
            <h3 className="font-bold text-sm text-slate-900 flex items-center gap-2">
              <Activity className="w-4 h-4 text-teal-600" />
              <span>{locale === 'vi' ? 'Quy trình chuẩn' : 'Standard Workflow'}</span>
            </h3>
            <ol className="space-y-3 text-xs text-slate-600">
              <li className="flex items-start gap-2.5">
                <span className="w-5 h-5 rounded-full bg-teal-100 text-teal-800 font-bold flex items-center justify-center shrink-0 text-[11px]">1</span>
                <span><strong>{locale === 'vi' ? 'Tạo đối tượng' : 'Create Subject'}:</strong> {locale === 'vi' ? 'Đăng ký hồ sơ bệnh nhân hoặc mã định danh.' : 'Register patient or subject profile.'}</span>
              </li>
              <li className="flex items-start gap-2.5">
                <span className="w-5 h-5 rounded-full bg-teal-100 text-teal-800 font-bold flex items-center justify-center shrink-0 text-[11px]">2</span>
                <span><strong>{locale === 'vi' ? 'Tạo phiên & Tải video' : 'Create Session & Upload'}:</strong> {locale === 'vi' ? 'Kéo thả video đi bộ (front hoặc side view).' : 'Drag & drop walking recording (front/side).'}</span>
              </li>
              <li className="flex items-start gap-2.5">
                <span className="w-5 h-5 rounded-full bg-teal-100 text-teal-800 font-bold flex items-center justify-center shrink-0 text-[11px]">3</span>
                <span><strong>{locale === 'vi' ? 'Xác nhận góc camera' : 'Confirm View'}:</strong> {locale === 'vi' ? 'Xác nhận góc quay trước khi phân tích.' : 'Verify camera angle for accurate kinematics.'}</span>
              </li>
              <li className="flex items-start gap-2.5">
                <span className="w-5 h-5 rounded-full bg-teal-100 text-teal-800 font-bold flex items-center justify-center shrink-0 text-[11px]">4</span>
                <span><strong>{locale === 'vi' ? 'Xem kết quả & Báo cáo' : 'Review & Report'}:</strong> {locale === 'vi' ? 'Video có chú thích xương, chỉ số nhịp bước và xuất báo cáo.' : 'Annotated video, cadence metrics, and report export.'}</span>
              </li>
            </ol>
          </div>

          <div className="bg-slate-50 border border-slate-200 rounded-2xl p-5 space-y-2 text-xs text-slate-600">
            <span className="font-semibold text-slate-800 block">
              {locale === 'vi' ? 'Hỗ trợ định dạng' : 'Supported Formats'}
            </span>
            <p className="text-[11px] text-slate-500 leading-relaxed">
              Video MP4, MOV, AVI (tối đa 200MB, 10–60 FPS). Góc nhìn tối ưu: máy ảnh đặt ngang tầm hông, đối tượng đi bộ tự nhiên toàn thân trong khung hình.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
