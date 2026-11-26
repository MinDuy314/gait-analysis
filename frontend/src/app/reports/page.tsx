'use client'

import React, { useEffect, useState } from 'react'
import Link from 'next/link'
import { reportsApi } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { useLanguage } from '@/context/LanguageContext'
import type { Report } from '@/types/api'
import { FileText, ArrowRight, CheckCircle2, Clock, UserCheck, Stethoscope, AlertCircle } from 'lucide-react'

export default function GlobalReportsPage() {
  const { user } = useAuth()
  const { locale } = useLanguage()
  const isClinician = user?.role === 'professional' || user?.role === 'administrator'

  const [reports, setReports] = useState<Report[]>([])
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    reportsApi
      .list()
      .then((data) => setReports(Array.isArray(data) ? data : []))
      .catch((err) => setError(err.response?.data?.detail || 'Failed to load reports'))
      .finally(() => setLoading(false))
  }, [])

  const statusBadge = (st: string) => {
    switch (st) {
      case 'published':
        return <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">Published</span>
      case 'approved':
        return <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-sky-50 text-sky-700 border border-sky-200">Approved</span>
      case 'pending_review':
        return <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">Pending Review</span>
      default:
        return <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-slate-100 text-slate-600 border border-slate-200 capitalize">{st}</span>
    }
  }

  const filtered = statusFilter === 'all' ? reports : reports.filter((r) => r.status === statusFilter)

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
            <FileText className="w-6 h-6 text-teal-600" />
            <span>{locale === 'vi' ? 'Báo cáo Dáng đi' : 'Gait Rehabilitation Reports'}</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            {isClinician
              ? locale === 'vi'
                ? 'Quản lý, nhận xét, phê duyệt và xuất bản báo cáo lâm sàng / bệnh nhân.'
                : 'Review, annotate, approve, and publish clinical and patient rehabilitation reports.'
              : locale === 'vi'
              ? 'Xem các báo cáo tiến độ đi bộ đã được bác sĩ phê duyệt và xuất bản cho bạn.'
              : 'View walking progress reports reviewed and published by your clinician.'}
          </p>
        </div>

        {isClinician && (
          <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-xl border border-slate-200 text-xs font-semibold">
            {(['all', 'draft', 'approved', 'published'] as const).map((st) => (
              <button
                key={st}
                type="button"
                onClick={() => setStatusFilter(st)}
                className={`px-2.5 py-1 rounded-lg capitalize transition ${
                  statusFilter === st ? 'bg-white text-teal-800 shadow-xs' : 'text-slate-600'
                }`}
              >
                {st}
              </button>
            ))}
          </div>
        )}
      </div>

      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl flex items-center gap-2 text-xs text-rose-700">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {loading ? (
        <div className="p-12 text-center text-sm text-slate-400">
          <div className="w-6 h-6 border-2 border-teal-600 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
          <span>{locale === 'vi' ? 'Đang tải báo cáo...' : 'Loading reports...'}</span>
        </div>
      ) : filtered.length === 0 ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-10 shadow-xs text-center space-y-3">
          <Clock className="w-8 h-8 text-slate-300 mx-auto" />
          <div className="text-sm font-bold text-slate-800">
            {isClinician
              ? locale === 'vi' ? 'Chưa có báo cáo nào được tạo' : 'No reports found'
              : locale === 'vi' ? 'Chưa có báo cáo nào được bác sĩ xuất bản' : 'No published reports available yet'}
          </div>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            {isClinician
              ? locale === 'vi'
                ? 'Vào chi tiết đối tượng hoặc kết quả phiên để tạo báo cáo mới.'
                : 'Open any completed session to generate a clinical or patient report.'
              : locale === 'vi'
              ? 'Khi bác sĩ hoàn tất đánh giá và xuất bản báo cáo, báo cáo sẽ hiển thị tại đây.'
              : 'Once your clinician reviews and publishes your report, it will appear here.'}
          </p>
          <Link
            href="/subjects"
            className="inline-flex items-center gap-2 px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white font-semibold text-xs rounded-xl transition"
          >
            <span>{locale === 'vi' ? 'Đến danh sách đối tượng' : 'Go to Subjects'}</span>
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-xs divide-y divide-slate-100 overflow-hidden">
          {filtered.map((rep) => (
            <div key={rep.id} className="p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-slate-50/70 transition">
              <div className="space-y-1">
                <div className="flex items-center gap-2.5 flex-wrap">
                  {rep.report_type === 'professional' ? (
                    <Stethoscope className="w-4 h-4 text-sky-600" />
                  ) : (
                    <UserCheck className="w-4 h-4 text-teal-600" />
                  )}
                  <span className="font-bold text-sm text-slate-900">
                    {rep.title || (rep.report_type === 'professional' ? 'Clinical Gait Report' : 'Patient Progress Report')}
                  </span>
                  {statusBadge(rep.status)}
                </div>
                <div className="text-xs text-slate-500">
                  Generated: {new Date(rep.generated_at).toLocaleString(locale === 'vi' ? 'vi-VN' : 'en-US')}
                  {rep.approved_by && <span className="ml-3">• Approved by: <strong>{rep.approved_by}</strong></span>}
                </div>
              </div>

              <Link
                href={`/reports/${rep.id}`}
                className="inline-flex items-center gap-1.5 px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold rounded-xl transition shrink-0"
              >
                <span>{locale === 'vi' ? 'Mở báo cáo' : 'Open Report'}</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
