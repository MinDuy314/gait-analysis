'use client'

import React, { useEffect, useState, use } from 'react'
import Link from 'next/link'
import { reportsApi } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { useLanguage } from '@/context/LanguageContext'
import type { Report } from '@/types/api'
import {
  FileText,
  Download,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  AlertCircle,
  UserCheck,
  Stethoscope,
  Clock,
} from 'lucide-react'

export default function SessionReportsPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const resolvedParams = use(params)
  const sessionId = resolvedParams.id
  const { user } = useAuth()
  const { t, locale } = useLanguage()
  const isClinician = user?.role === 'professional' || user?.role === 'administrator'

  const [sessionReports, setSessionReports] = useState<Report[]>([])
  const [generatedReport, setGeneratedReport] = useState<Report | null>(null)
  const [isGenerating, setIsGenerating] = useState(false)
  const [isDownloading, setIsDownloading] = useState<'md' | 'html' | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [reportType, setReportType] = useState<'individual' | 'professional'>('individual')

  useEffect(() => {
    reportsApi
      .listForSession(sessionId)
      .then((list) => {
        if (Array.isArray(list)) {
          setSessionReports(list)
          if (list.length > 0) setGeneratedReport(list[0])
        }
      })
      .catch(() => null)
      .finally(() => setLoading(false))
  }, [sessionId])

  const handleGenerate = async (type: 'individual' | 'professional') => {
    setIsGenerating(true)
    setError(null)
    setReportType(type)
    try {
      const rep = await reportsApi.generate(sessionId, type)
      setGeneratedReport(rep)
      setSessionReports((prev) => [rep, ...prev])
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to generate report')
    } finally {
      setIsGenerating(false)
    }
  }

  const handleDownload = async (report: Report, format: 'md' | 'html') => {
    setIsDownloading(format)
    setError(null)
    try {
      const res = await reportsApi.download(report.id, format)
      const contentType = String(res.headers['content-type'] || '')
      if (contentType.includes('application/json') || (contentType.includes('text/html') && format !== 'html')) {
        setError(locale === 'vi' ? 'Không thể tải tệp báo cáo hợp lệ.' : 'Failed to download valid report file.')
        return
      }
      const mime = format === 'html' ? 'text/html;charset=utf-8' : 'text/markdown;charset=utf-8'
      const blob = new Blob([res.data], { type: mime })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${report.report_type}_report_${report.id}.${format}`
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
    } catch (err: any) {
      setError(err.response?.data?.detail || (locale === 'vi' ? 'Lỗi khi tải tệp báo cáo.' : 'Error downloading report file.'))
    } finally {
      setIsDownloading(null)
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <Link
        href={`/sessions/${sessionId}/results`}
        className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-teal-700 transition"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        <span>{locale === 'vi' ? 'Quay lại kết quả phân tích' : 'Back to results'}</span>
      </Link>

      <div className="bg-white rounded-2xl border border-slate-200 p-6 sm:p-8 shadow-xs space-y-6">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <FileText className="w-5 h-5 text-teal-600" />
            <span>{t('reports.title')}</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            {isClinician
              ? locale === 'vi'
                ? 'Tạo báo cáo Bệnh nhân hoặc Lâm sàng, sau đó xem chi tiết, thêm nhận xét, phê duyệt và xuất bản.'
                : 'Generate Patient or Clinical reports, then review, add clinician notes, approve, and publish.'
              : locale === 'vi'
              ? 'Xem và tải xuống các báo cáo tiến độ đã được bác sĩ xuất bản cho phiên này.'
              : 'View and download walking progress reports published by your clinician for this session.'}
          </p>
        </div>

        {error && (
          <div className="p-3.5 bg-red-50 border border-red-200 rounded-xl flex items-start gap-2.5 text-xs text-red-700">
            <AlertCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {/* Clinician Report Generation Cards */}
        {isClinician && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div
              onClick={() => !isGenerating && handleGenerate('individual')}
              className="p-5 rounded-2xl border border-slate-200 bg-white hover:border-teal-500 hover:bg-slate-50 cursor-pointer transition space-y-3"
            >
              <div className="w-10 h-10 rounded-xl bg-teal-50 text-teal-700 flex items-center justify-center">
                <UserCheck className="w-5 h-5" />
              </div>
              <div>
                <div className="font-bold text-sm text-slate-900">{t('reports.individual')}</div>
                <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                  {locale === 'vi'
                    ? 'Báo cáo ngôn ngữ dễ hiểu cho bệnh nhân: tiến độ, thành tựu và bước tiếp theo.'
                    : 'Plain-language patient summary covering progress, achievements, and clinician-approved next steps.'}
                </p>
              </div>
              <button
                disabled={isGenerating}
                className="w-full py-2 bg-teal-600 hover:bg-teal-700 text-white font-semibold text-xs rounded-xl shadow-xs transition"
              >
                {isGenerating && reportType === 'individual' ? t('reports.generating') : t('reports.generate')}
              </button>
            </div>

            <div
              onClick={() => !isGenerating && handleGenerate('professional')}
              className="p-5 rounded-2xl border border-slate-200 bg-white hover:border-teal-500 hover:bg-slate-50 cursor-pointer transition space-y-3"
            >
              <div className="w-10 h-10 rounded-xl bg-sky-50 text-sky-700 flex items-center justify-center">
                <Stethoscope className="w-5 h-5" />
              </div>
              <div>
                <div className="font-bold text-sm text-slate-900">{t('reports.professional')}</div>
                <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                  {locale === 'vi'
                    ? 'Báo cáo chuyên khoa với diễn giải lâm sàng, xu hướng theo thời gian và ghi chú bác sĩ.'
                    : 'Full clinical report with longitudinal interpretation, reliability flags, and approval controls.'}
                </p>
              </div>
              <button
                disabled={isGenerating}
                className="w-full py-2 bg-sky-600 hover:bg-sky-700 text-white font-semibold text-xs rounded-xl shadow-xs transition"
              >
                {isGenerating && reportType === 'professional' ? t('reports.generating') : t('reports.generate')}
              </button>
            </div>
          </div>
        )}

        {/* Active / Existing Session Reports */}
        {loading ? (
          <div className="p-6 text-center text-xs text-slate-400">Loading reports...</div>
        ) : sessionReports.length === 0 ? (
          <div className="p-6 bg-slate-50 rounded-2xl border border-slate-200 text-center space-y-2">
            <Clock className="w-6 h-6 text-slate-400 mx-auto" />
            <p className="text-xs text-slate-600">
              {isClinician
                ? 'No reports generated for this session yet. Select a report type above.'
                : 'No published report is available for this session yet.'}
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {sessionReports.map((rep) => (
              <div key={rep.id} className="p-5 bg-emerald-50/50 border border-emerald-200 rounded-2xl space-y-3">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div className="flex items-center gap-2 text-emerald-900 font-bold text-sm">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    <span>{rep.title || `${rep.report_type} report`}</span>
                    <span className="px-2 py-0.5 rounded-full text-[10px] bg-white border border-emerald-200 text-emerald-700 capitalize">
                      {rep.status}
                    </span>
                  </div>
                  <Link
                    href={`/reports/${rep.id}`}
                    className="inline-flex items-center gap-1 px-3 py-1.5 bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold rounded-lg"
                  >
                    <span>{isClinician ? 'Review / Edit / Publish' : 'Open Report'}</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </Link>
                </div>

                <div className="flex flex-wrap justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => handleDownload(rep, 'md')}
                    disabled={isDownloading !== null}
                    className="flex items-center gap-1.5 px-3.5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs rounded-xl transition disabled:opacity-50"
                  >
                    <Download className="w-3.5 h-3.5" />
                    <span>.MD</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDownload(rep, 'html')}
                    disabled={isDownloading !== null}
                    className="flex items-center gap-1.5 px-3.5 py-2 bg-sky-600 hover:bg-sky-700 text-white font-semibold text-xs rounded-xl transition disabled:opacity-50"
                  >
                    <Download className="w-3.5 h-3.5" />
                    <span>.HTML</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
