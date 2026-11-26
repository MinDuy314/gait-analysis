'use client'

import React, { useEffect, useState, use } from 'react'
import Link from 'next/link'
import { reportsApi, progressApi } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { useLanguage } from '@/context/LanguageContext'
import { GaitTrendChart } from '@/components/charts/GaitTrendChart'
import type { Report, LongitudinalProgress } from '@/types/api'
import {
  ArrowLeft,
  CheckCircle2,
  Download,
  FileText,
  Save,
  Send,
  ShieldCheck,
  AlertCircle,
  Stethoscope,
  UserCheck,
  History,
} from 'lucide-react'

export default function ReportDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = use(params)
  const { user } = useAuth()
  const { locale } = useLanguage()
  const isClinician = user?.role === 'professional' || user?.role === 'administrator'

  const [report, setReport] = useState<Report | null>(null)
  const [longitudinal, setLongitudinal] = useState<LongitudinalProgress | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionMsg, setActionMsg] = useState<string | null>(null)

  // Clinician editable fields
  const [notes, setNotes] = useState('')
  const [prioritiesText, setPrioritiesText] = useState('')
  const [recommendations, setRecommendations] = useState('')
  const [saving, setSaving] = useState(false)
  const [downloading, setDownloading] = useState<'md' | 'html' | null>(null)

  useEffect(() => {
    reportsApi
      .get(id)
      .then((rep) => {
        setReport(rep)
        setNotes(rep.clinician_notes || '')
        setPrioritiesText((rep.rehabilitation_priorities || []).join('\n'))
        setRecommendations(rep.recommendations || '')
        return progressApi.longitudinal(rep.subject_id).catch(() => null)
      })
      .then((prog) => {
        if (prog) setLongitudinal(prog)
      })
      .catch((err) => setError(err.response?.data?.detail || 'Failed to load report'))
      .finally(() => setLoading(false))
  }, [id])

  const handleSaveNotes = async () => {
    if (!report) return
    setSaving(true)
    setActionMsg(null)
    setError(null)
    try {
      const priorities = prioritiesText
        .split('\n')
        .map((s) => s.trim())
        .filter(Boolean)
      const updated = await reportsApi.update(report.id, {
        clinician_notes: notes,
        rehabilitation_priorities: priorities,
        recommendations,
      })
      setReport(updated)
      setActionMsg(locale === 'vi' ? 'Đã lưu ghi chú lâm sàng.' : 'Clinician notes and recommendations saved.')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save report')
    } finally {
      setSaving(false)
    }
  }

  const handleApprove = async () => {
    if (!report) return
    setSaving(true)
    setActionMsg(null)
    setError(null)
    try {
      const priorities = prioritiesText
        .split('\n')
        .map((s) => s.trim())
        .filter(Boolean)
      await reportsApi.update(report.id, {
        clinician_notes: notes,
        rehabilitation_priorities: priorities,
        recommendations,
      })
      const approved = await reportsApi.approve(report.id)
      setReport(approved)
      setActionMsg(locale === 'vi' ? 'Báo cáo đã được phê duyệt.' : 'Report approved.')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to approve report')
    } finally {
      setSaving(false)
    }
  }

  const handlePublish = async () => {
    if (!report) return
    setSaving(true)
    setActionMsg(null)
    setError(null)
    try {
      const priorities = prioritiesText
        .split('\n')
        .map((s) => s.trim())
        .filter(Boolean)
      await reportsApi.update(report.id, {
        clinician_notes: notes,
        rehabilitation_priorities: priorities,
        recommendations,
      })
      const published = await reportsApi.publish(report.id)
      setReport(published)
      setActionMsg(
        locale === 'vi'
          ? 'Báo cáo đã được xuất bản. Bệnh nhân có thể xem ngay bây giờ.'
          : 'Report published. Patient can now view this report.'
      )
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to publish report')
    } finally {
      setSaving(false)
    }
  }

  const handleDownload = async (format: 'md' | 'html') => {
    if (!report) return
    setDownloading(format)
    try {
      const res = await reportsApi.download(report.id, format)
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
      setError(err.response?.data?.detail || 'Download failed')
    } finally {
      setDownloading(null)
    }
  }

  if (loading) {
    return (
      <div className="p-16 text-center text-sm text-slate-400">
        <div className="w-7 h-7 border-2 border-teal-600 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
        <span>Loading report...</span>
      </div>
    )
  }

  if (error && !report) {
    return (
      <div className="max-w-xl mx-auto p-8 bg-white rounded-2xl border border-rose-200 text-center space-y-4">
        <AlertCircle className="w-8 h-8 text-rose-500 mx-auto" />
        <div className="text-sm font-bold text-slate-900">{error}</div>
        <Link href="/reports" className="inline-block text-xs font-semibold text-teal-700 underline">
          Back to Reports
        </Link>
      </div>
    )
  }

  if (!report) return null

  const rd = report.report_data || {}
  const isClinical = report.report_type === 'professional'

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Top Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <Link
            href="/reports"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-teal-700"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>{locale === 'vi' ? 'Danh sách báo cáo' : 'Back to Reports'}</span>
          </Link>
          <div className="flex items-center gap-2.5 flex-wrap">
            {isClinical ? <Stethoscope className="w-5 h-5 text-sky-600" /> : <UserCheck className="w-5 h-5 text-teal-600" />}
            <h1 className="text-xl font-bold text-slate-900">
              {report.title || (isClinical ? 'Clinical Gait Rehabilitation Report' : 'Your Walking Progress Report')}
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-teal-50 text-teal-800 border border-teal-200 capitalize">
              {report.status.replace('_', ' ')}
            </span>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => handleDownload('md')}
            disabled={downloading !== null}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-white border border-slate-200 hover:border-teal-500 text-slate-700 text-xs font-semibold rounded-xl"
          >
            <Download className="w-3.5 h-3.5" />
            <span>.MD</span>
          </button>
          <button
            type="button"
            onClick={() => handleDownload('html')}
            disabled={downloading !== null}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-white border border-slate-200 hover:border-teal-500 text-slate-700 text-xs font-semibold rounded-xl"
          >
            <Download className="w-3.5 h-3.5" />
            <span>.HTML</span>
          </button>
        </div>
      </div>

      {actionMsg && (
        <div className="p-3.5 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center gap-2 text-xs text-emerald-800 font-semibold">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{actionMsg}</span>
        </div>
      )}
      {error && (
        <div className="p-3.5 bg-rose-50 border border-rose-200 rounded-xl flex items-center gap-2 text-xs text-rose-700">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* ================= CLINICAL REPORT VIEW ================= */}
      {isClinical ? (
        <div className="space-y-6">
          {/* 1. Patient & Assessment Info */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
            <div>
              <div className="text-slate-400">Subject ID</div>
              <div className="font-mono font-semibold text-slate-900 mt-0.5">{rd.patient_info?.subject_id || report.subject_id}</div>
            </div>
            <div>
              <div className="text-slate-400">Comparison Period</div>
              <div className="font-semibold text-slate-900 mt-0.5">{rd.patient_info?.comparison_period || 'Single session'}</div>
            </div>
            <div>
              <div className="text-slate-400">Clinician</div>
              <div className="font-semibold text-slate-900 mt-0.5">{rd.patient_info?.clinician || report.approved_by || 'Pending'}</div>
            </div>
            <div>
              <div className="text-slate-400">Camera / Calibration</div>
              <div className="font-semibold text-slate-900 mt-0.5 capitalize">
                {rd.patient_info?.camera_view || '—'} / {rd.patient_info?.calibration_status || 'uncalibrated'}
              </div>
            </div>
          </div>

          {/* 2. Measurement Summary & 3. Clinical Interpretation */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {(['walking_speed', 'cadence'] as const).map((mk) => {
              const m = rd.measurement_summary?.[mk] || longitudinal?.[mk]
              const interp = rd.clinical_interpretation?.[mk]
              return (
                <div key={mk} className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs space-y-3">
                  <div className="flex items-center justify-between">
                    <h2 className="text-sm font-bold text-slate-900">{m?.label || mk}</h2>
                    <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-slate-100 text-slate-700 capitalize">
                      {String(m?.trend || 'insufficient_data').replace('_', ' ')}
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-xs bg-slate-50 p-3 rounded-xl">
                    <div>
                      <div className="text-slate-400">Baseline</div>
                      <div className="font-bold text-slate-900">{m?.baseline_value ?? 'N/A'} {m?.unit}</div>
                    </div>
                    <div>
                      <div className="text-slate-400">Latest</div>
                      <div className="font-bold text-teal-700">{m?.latest_value ?? 'N/A'} {m?.unit}</div>
                    </div>
                    <div>
                      <div className="text-slate-400">Change</div>
                      <div className="font-bold text-slate-900">
                        {m?.absolute_change != null ? `${m.absolute_change >= 0 ? '+' : ''}${m.absolute_change} (${m.percentage_change}%)` : 'N/A'}
                      </div>
                    </div>
                  </div>
                  {interp && (
                    <div className="text-xs text-slate-600 space-y-1.5 leading-relaxed">
                      <p><strong>Meaning:</strong> {interp.what_it_represents}</p>
                      <p><strong>Current Indication:</strong> {interp.current_indication}</p>
                      <p><strong>Longitudinal Evaluation:</strong> {interp.change_over_time}</p>
                    </div>
                  )}
                </div>
              )
            })}
          </div>

          {/* 4. Longitudinal Charts */}
          {longitudinal && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <GaitTrendChart
                title="Walking Speed Longitudinal Trend"
                unit="m/s"
                series={longitudinal.walking_speed.series}
                baselineValue={longitudinal.walking_speed.baseline_value}
                color="#0d9488"
                locale={locale}
              />
              <GaitTrendChart
                title="Cadence Longitudinal Trend"
                unit="steps/min"
                series={longitudinal.cadence.series}
                baselineValue={longitudinal.cadence.baseline_value}
                color="#0284c7"
                locale={locale}
              />
            </div>
          )}

          {/* 5. Clinical Considerations */}
          <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs space-y-2">
            <h2 className="text-sm font-bold text-slate-900">Clinical Considerations</h2>
            <ul className="list-disc pl-5 text-xs text-slate-700 space-y-1">
              {(rd.clinical_considerations || []).map((c: string, i: number) => (
                <li key={i}>{c}</li>
              ))}
            </ul>
          </div>
        </div>
      ) : (
        /* ================= PATIENT-FRIENDLY REPORT VIEW ================= */
        <div className="space-y-6">
          {/* 1. Simple Overall Progress Statement */}
          <div className="bg-gradient-to-r from-teal-600 to-teal-800 text-white rounded-2xl p-6 shadow-xs space-y-2">
            <div className="text-xs font-semibold uppercase tracking-wider text-teal-100">
              {locale === 'vi' ? 'Tôi có đang tiến bộ không?' : 'Am I Making Progress?'}
            </div>
            <p className="text-lg font-bold leading-snug">
              {rd.overall_summary || 'Your walking summary is ready for review.'}
            </p>
            <div className="text-xs text-teal-100">
              Comparison period: {rd.comparison_period || 'Current session'}
            </div>
          </div>

          {/* 2. Achievements & 3. Areas to Improve */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white rounded-2xl border border-emerald-200 p-5 shadow-xs space-y-3">
              <h2 className="text-sm font-bold text-emerald-900 flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span>{locale === 'vi' ? 'Những điểm bạn đã cải thiện' : 'What You Have Improved (Achievements)'}</span>
              </h2>
              <ul className="space-y-2 text-xs text-slate-700">
                {(rd.achievements || []).map((a: string, i: number) => (
                  <li key={i} className="p-2.5 bg-emerald-50/60 rounded-xl border border-emerald-100">{a}</li>
                ))}
              </ul>
            </div>

            <div className="bg-white rounded-2xl border border-amber-200 p-5 shadow-xs space-y-3">
              <h2 className="text-sm font-bold text-amber-900 flex items-center gap-2">
                <FileText className="w-4 h-4 text-amber-600" />
                <span>{locale === 'vi' ? 'Điểm cần tiếp tục rèn luyện' : 'What to Continue Working On'}</span>
              </h2>
              <ul className="space-y-2 text-xs text-slate-700">
                {(rd.areas_to_improve || []).map((area: string, i: number) => (
                  <li key={i} className="p-2.5 bg-amber-50/60 rounded-xl border border-amber-100">{area}</li>
                ))}
              </ul>
            </div>
          </div>

          {/* 4. Patient-Friendly Charts */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <GaitTrendChart
              title={locale === 'vi' ? 'Tốc độ đi bộ của bạn' : 'Your Walking Speed Over Time'}
              unit="m/s"
              series={rd.charts?.walking_speed?.series || longitudinal?.walking_speed.series || []}
              baselineValue={rd.charts?.walking_speed?.baseline_value ?? longitudinal?.walking_speed.baseline_value}
              color="#0d9488"
              locale={locale}
              subtitle={rd.charts?.walking_speed?.explanation}
            />
            <GaitTrendChart
              title={locale === 'vi' ? 'Nhịp bước của bạn' : 'Your Step Rhythm (Cadence) Over Time'}
              unit="steps/min"
              series={rd.charts?.cadence?.series || longitudinal?.cadence.series || []}
              baselineValue={rd.charts?.cadence?.baseline_value ?? longitudinal?.cadence.baseline_value}
              color="#0284c7"
              locale={locale}
              subtitle={rd.charts?.cadence?.explanation}
            />
          </div>

          {/* 5. Clinician-Approved Next Steps */}
          <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs space-y-2">
            <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-teal-600" />
              <span>{locale === 'vi' ? 'Bước tiếp theo được bác sĩ phê duyệt' : 'Next Steps Approved by Your Clinician'}</span>
            </h2>
            {(rd.clinician_approved_next_steps || []).length > 0 ? (
              <ul className="list-disc pl-5 text-xs text-slate-700 space-y-1">
                {rd.clinician_approved_next_steps.map((s: string, i: number) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-slate-500">
                Your clinician has not added specific follow-up instructions yet.
              </p>
            )}
          </div>
        </div>
      )}

      {/* ================= CLINICIAN NOTES & APPROVAL WORKFLOW ================= */}
      {isClinician && (
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-900">Clinician Notes, Approval & Publication</h2>
            {report.approved_by && (
              <span className="text-xs text-emerald-700 font-semibold">
                Approved by {report.approved_by}
              </span>
            )}
          </div>

          <div className="space-y-3 text-xs">
            <div>
              <label className="font-semibold text-slate-700 block mb-1">Clinical Observations & Interpretation Notes</label>
              <textarea
                rows={3}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Add clinical observations, gait pattern context, or session comparability notes..."
                className="w-full rounded-xl border border-slate-200 p-3 text-xs focus:outline-none focus:border-teal-500"
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="font-semibold text-slate-700 block mb-1">Rehabilitation Priorities (one per line)</label>
                <textarea
                  rows={3}
                  value={prioritiesText}
                  onChange={(e) => setPrioritiesText(e.target.value)}
                  placeholder="e.g. Maintain steady cadence during 10m walk&#10;Build single-leg stance endurance"
                  className="w-full rounded-xl border border-slate-200 p-3 text-xs focus:outline-none focus:border-teal-500"
                />
              </div>
              <div>
                <label className="font-semibold text-slate-700 block mb-1">Follow-up Recommendations</label>
                <textarea
                  rows={3}
                  value={recommendations}
                  onChange={(e) => setRecommendations(e.target.value)}
                  placeholder="e.g. Repeat standardized side-view capture in 2 weeks."
                  className="w-full rounded-xl border border-slate-200 p-3 text-xs focus:outline-none focus:border-teal-500"
                />
              </div>
            </div>
          </div>

          <div className="flex flex-wrap justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={handleSaveNotes}
              disabled={saving}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-semibold rounded-xl transition disabled:opacity-50"
            >
              <Save className="w-3.5 h-3.5" />
              <span>Save Draft</span>
            </button>
            <button
              type="button"
              onClick={handleApprove}
              disabled={saving}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-sky-600 hover:bg-sky-700 text-white text-xs font-semibold rounded-xl transition disabled:opacity-50"
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Approve</span>
            </button>
            <button
              type="button"
              onClick={handlePublish}
              disabled={saving}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-xl transition disabled:opacity-50"
            >
              <Send className="w-3.5 h-3.5" />
              <span>Publish</span>
            </button>
          </div>

          {/* Revision History */}
          {(report.revision_history || []).length > 0 && (
            <div className="pt-4 border-t border-slate-100 space-y-2">
              <div className="text-xs font-bold text-slate-600 flex items-center gap-1.5">
                <History className="w-3.5 h-3.5" />
                <span>Revision & Approval History</span>
              </div>
              <div className="space-y-1 text-[11px] text-slate-500">
                {report.revision_history!.map((rev, idx) => (
                  <div key={idx}>
                    {new Date(rev.timestamp).toLocaleString()} — <strong>{rev.actor}</strong> {rev.action} ({rev.status})
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
