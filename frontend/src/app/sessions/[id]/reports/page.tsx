'use client'

import React, { useState, use } from 'react'
import Link from 'next/link'
import { reportsApi } from '@/lib/api'
import { useLanguage } from '@/context/LanguageContext'
import type { Report } from '@/types/api'
import {
  FileText,
  Download,
  ArrowLeft,
  CheckCircle2,
  AlertCircle,
  FileCheck,
  UserCheck,
  Stethoscope
} from 'lucide-react'

export default function SessionReportsPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const resolvedParams = use(params)
  const sessionId = resolvedParams.id
  const { t, locale } = useLanguage()

  const [generatedReport, setGeneratedReport] = useState<Report | null>(null)
  const [isGenerating, setIsGenerating] = useState(false)
  const [isDownloading, setIsDownloading] = useState<'md' | 'html' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [reportType, setReportType] = useState<'individual' | 'professional'>('individual')

  const handleGenerate = async (type: 'individual' | 'professional') => {
    setIsGenerating(true)
    setError(null)
    setReportType(type)
    try {
      const rep = await reportsApi.generate(sessionId, type)
      setGeneratedReport(rep)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to generate report')
    } finally {
      setIsGenerating(false)
    }
  }

  const handleDownload = async (format: 'md' | 'html') => {
    if (!generatedReport) return
    setIsDownloading(format)
    setError(null)
    try {
      const res = await reportsApi.download(generatedReport.id, format)
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
      a.download = `${generatedReport.report_type}_report_${generatedReport.id}.${format}`
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
    <div className="max-w-2xl mx-auto space-y-6">
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
            {locale === 'vi'
              ? 'Tạo báo cáo định dạng Markdown chuẩn khoa học có thể tải về hoặc lưu trữ hồ sơ bệnh án.'
              : 'Generate structured Markdown reports for patient communication or clinical records.'}
          </p>
        </div>

        {error && (
          <div className="p-3.5 bg-red-50 border border-red-200 rounded-xl flex items-start gap-2.5 text-xs text-red-700">
            <AlertCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {/* Report Type Selector Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div
            onClick={() => handleGenerate('individual')}
            className="p-5 rounded-2xl border border-slate-200 bg-white hover:border-teal-500 hover:bg-slate-50 cursor-pointer transition space-y-3"
          >
            <div className="w-10 h-10 rounded-xl bg-teal-50 text-teal-700 flex items-center justify-center">
              <UserCheck className="w-5 h-5" />
            </div>
            <div>
              <div className="font-bold text-sm text-slate-900">{t('reports.individual')}</div>
              <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                {locale === 'vi'
                  ? 'Báo cáo thân thiện cho bệnh nhân với ngôn từ dễ hiểu, tóm tắt chỉ số cơ bản.'
                  : 'Patient-friendly language, key measurements summary, and actionable advice.'}
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
            onClick={() => handleGenerate('professional')}
            className="p-5 rounded-2xl border border-slate-200 bg-white hover:border-teal-500 hover:bg-slate-50 cursor-pointer transition space-y-3"
          >
            <div className="w-10 h-10 rounded-xl bg-sky-50 text-sky-700 flex items-center justify-center">
              <Stethoscope className="w-5 h-5" />
            </div>
            <div>
              <div className="font-bold text-sm text-slate-900">{t('reports.professional')}</div>
              <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                {locale === 'vi'
                  ? 'Báo cáo chuyên khoa lâm sàng với bảng số liệu chi tiết, độ tin cậy và hạn chế phương pháp.'
                  : 'Full kinematic data tables, biomechanical rules, confidence levels, and uncertainty sources.'}
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

        {/* Generated Report Ready Card */}
        {generatedReport && (
          <div className="p-5 bg-emerald-50/70 border border-emerald-200 rounded-2xl space-y-3 animate-in fade-in">
            <div className="flex items-center gap-2 text-emerald-800 font-bold text-sm">
              <CheckCircle2 className="w-5 h-5 text-emerald-600" />
              <span>{t('reports.generated')}</span>
            </div>
            <div className="text-xs text-emerald-700 space-y-1">
              <div><strong>Report ID:</strong> {generatedReport.id}</div>
              <div><strong>Type:</strong> {generatedReport.report_type}</div>
              <div><strong>Generated At:</strong> {new Date(generatedReport.generated_at).toLocaleString()}</div>
            </div>

            <div className="pt-2 flex flex-wrap justify-end gap-3">
              <button
                type="button"
                onClick={() => handleDownload('md')}
                disabled={isDownloading !== null}
                className="flex items-center gap-2 px-4 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs rounded-xl shadow-xs transition disabled:opacity-50"
              >
                <Download className={`w-4 h-4 ${isDownloading === 'md' ? 'animate-bounce' : ''}`} />
                <span>{locale === 'vi' ? 'Tải tệp Markdown (.md)' : 'Download Markdown (.md)'}</span>
              </button>
              <button
                type="button"
                onClick={() => handleDownload('html')}
                disabled={isDownloading !== null}
                className="flex items-center gap-2 px-4 py-2.5 bg-sky-600 hover:bg-sky-700 text-white font-semibold text-xs rounded-xl shadow-xs transition disabled:opacity-50"
              >
                <Download className={`w-4 h-4 ${isDownloading === 'html' ? 'animate-bounce' : ''}`} />
                <span>{locale === 'vi' ? 'Tải trang web HTML (.html)' : 'Download Web Report (.html)'}</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
