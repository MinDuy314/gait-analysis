'use client'

import React, { useEffect, useState, Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { subjectsApi, progressApi } from '@/lib/api'
import { useLanguage } from '@/context/LanguageContext'
import { GaitTrendChart } from '@/components/charts/GaitTrendChart'
import type { Subject, LongitudinalProgress, MetricSummary, ReliabilityStatus, TrendStatus } from '@/types/api'
import {
  LineChart as LineChartIcon,
  TrendingUp,
  TrendingDown,
  Minus,
  AlertCircle,
  CheckCircle2,
  Clock,
  Calendar,
  ArrowRight,
  HelpCircle,
} from 'lucide-react'

function ProgressContent() {
  const searchParams = useSearchParams()
  const initialSubjectId = searchParams.get('subject_id') || ''
  const { locale } = useLanguage()

  const [subjects, setSubjects] = useState<Subject[]>([])
  const [selectedSubjectId, setSelectedSubjectId] = useState<string>(initialSubjectId)
  const [progress, setProgress] = useState<LongitudinalProgress | null>(null)
  const [dateRange, setDateRange] = useState<'all' | '30d' | '90d'>('all')
  const [loadingSubjects, setLoadingSubjects] = useState(true)
  const [loadingProgress, setLoadingProgress] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    subjectsApi
      .list(0, 100)
      .then((res) => {
        const list = res.items || []
        setSubjects(list)
        if (!initialSubjectId && list.length > 0) {
          setSelectedSubjectId(list[0].id)
        }
      })
      .catch((err) => setError(err.response?.data?.detail || 'Failed to load subjects'))
      .finally(() => setLoadingSubjects(false))
  }, [initialSubjectId])

  useEffect(() => {
    if (!selectedSubjectId) return
    setLoadingProgress(true)
    setError(null)
    progressApi
      .longitudinal(selectedSubjectId)
      .then((data) => setProgress(data))
      .catch((err) => setError(err.response?.data?.detail || 'Failed to load longitudinal progress'))
      .finally(() => setLoadingProgress(false))
  }, [selectedSubjectId])

  const trendBadge = (trend: TrendStatus) => {
    switch (trend) {
      case 'improved':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <TrendingUp className="w-3 h-3" />
            {locale === 'vi' ? 'Cải thiện' : 'Improved'}
          </span>
        )
      case 'declined':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-rose-50 text-rose-700 border border-rose-200">
            <TrendingDown className="w-3 h-3" />
            {locale === 'vi' ? 'Giảm' : 'Declined'}
          </span>
        )
      case 'unchanged':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-sky-50 text-sky-700 border border-sky-200">
            <Minus className="w-3 h-3" />
            {locale === 'vi' ? 'Ổn định' : 'Unchanged'}
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-slate-100 text-slate-600 border border-slate-200">
            <HelpCircle className="w-3 h-3" />
            {locale === 'vi' ? 'Chưa đủ dữ liệu' : 'Insufficient data'}
          </span>
        )
    }
  }

  const qualityBadge = (q: ReliabilityStatus) => {
    switch (q) {
      case 'valid':
        return <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">Valid</span>
      case 'low_confidence':
        return <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">Low Confidence</span>
      case 'invalid':
        return <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-50 text-rose-700 border border-rose-200">Invalid</span>
      case 'pending':
        return <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-sky-50 text-sky-700 border border-sky-200">Pending</span>
      default:
        return <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-100 text-slate-600 border border-slate-200">Unavailable</span>
    }
  }

  const filterByDate = <T extends { date: string | null }>(items: T[]): T[] => {
    if (dateRange === 'all') return items
    const days = dateRange === '30d' ? 30 : 90
    const cutoff = Date.now() - days * 86400 * 1000
    return items.filter((item) => (item.date ? new Date(item.date).getTime() >= cutoff : true))
  }

  const renderSummaryCard = (m: MetricSummary, decimals: number) => (
    <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div className="text-xs font-bold text-slate-500 uppercase tracking-wider">{m.label} ({m.unit})</div>
        {trendBadge(m.trend)}
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-1">
        <div>
          <div className="text-[11px] text-slate-400">{locale === 'vi' ? 'Mốc đầu (Baseline)' : 'Baseline'}</div>
          <div className="text-lg font-bold text-slate-900">
            {m.baseline_value !== null ? `${m.baseline_value.toFixed(decimals)}` : 'N/A'}
          </div>
        </div>
        <div>
          <div className="text-[11px] text-slate-400">{locale === 'vi' ? 'Mới nhất' : 'Latest'}</div>
          <div className="text-lg font-bold text-teal-700">
            {m.latest_value !== null ? `${m.latest_value.toFixed(decimals)}` : 'N/A'}
          </div>
        </div>
        <div>
          <div className="text-[11px] text-slate-400">{locale === 'vi' ? 'Thay đổi' : 'Total Change'}</div>
          <div className="text-base font-bold text-slate-900">
            {m.absolute_change !== null ? `${m.absolute_change >= 0 ? '+' : ''}${m.absolute_change.toFixed(decimals)}` : 'N/A'}
          </div>
          {m.change_vs_previous !== null && (
            <div className="text-[10px] text-slate-500">
              vs prev: {m.change_vs_previous >= 0 ? '+' : ''}{m.change_vs_previous.toFixed(decimals)}
            </div>
          )}
        </div>
        <div>
          <div className="text-[11px] text-slate-400">{locale === 'vi' ? '% Thay đổi' : '% Change'}</div>
          <div className="text-base font-bold text-slate-900">
            {m.percentage_change !== null ? `${m.percentage_change >= 0 ? '+' : ''}${m.percentage_change.toFixed(1)}%` : 'N/A'}
          </div>
          <div className="text-[10px] text-slate-500">{m.valid_count} valid</div>
        </div>
      </div>

      <p className="text-xs text-slate-600 bg-slate-50 rounded-xl px-3 py-2 border border-slate-100">
        {m.trend_explanation}
      </p>
    </div>
  )

  const filteredTimeline = progress ? filterByDate(progress.timeline) : []
  const filteredWsSeries = progress ? filterByDate(progress.walking_speed.series) : []
  const filteredCadSeries = progress ? filterByDate(progress.cadence.series) : []

  return (
    <div className="space-y-6">
      {/* Header + Controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
            <LineChartIcon className="w-6 h-6 text-teal-600" />
            <span>{locale === 'vi' ? 'Theo dõi Tiến độ Phục hồi Dáng đi' : 'Longitudinal Rehabilitation Progress'}</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            {locale === 'vi'
              ? 'So sánh tốc độ đi bộ và nhịp bước qua các phiên thực tế đã được kiểm định chất lượng.'
              : 'Track walking speed and cadence across rehabilitation sessions and clinical assessments.'}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {subjects.length > 0 && (
            <select
              value={selectedSubjectId}
              onChange={(e) => setSelectedSubjectId(e.target.value)}
              className="px-3 py-2 bg-white border border-slate-200 rounded-xl text-xs font-semibold text-slate-800 shadow-xs"
            >
              {subjects.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.display_name || s.id.slice(0, 8)}
                </option>
              ))}
            </select>
          )}

          <div className="flex items-center bg-slate-100 p-1 rounded-xl border border-slate-200 text-xs font-semibold">
            {(['all', '30d', '90d'] as const).map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => setDateRange(r)}
                className={`px-2.5 py-1 rounded-lg transition ${dateRange === r ? 'bg-white text-teal-800 shadow-xs' : 'text-slate-600'}`}
              >
                {r === 'all' ? (locale === 'vi' ? 'Tất cả' : 'All') : r}
              </button>
            ))}
          </div>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl flex items-center gap-2 text-xs text-rose-700">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {loadingSubjects || loadingProgress ? (
        <div className="p-16 text-center text-sm text-slate-400">
          <div className="w-7 h-7 border-2 border-teal-600 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
          <span>{locale === 'vi' ? 'Đang tải dữ liệu lịch sử...' : 'Loading longitudinal history...'}</span>
        </div>
      ) : !progress || progress.total_sessions === 0 ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-10 text-center space-y-3">
          <Clock className="w-8 h-8 text-slate-300 mx-auto" />
          <div className="text-sm font-bold text-slate-800">
            {locale === 'vi' ? 'Chưa có phiên phân tích nào cho đối tượng này' : 'No rehabilitation sessions recorded yet'}
          </div>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            {locale === 'vi'
              ? 'Hãy tạo phiên mới và tải video đi bộ để bắt đầu theo dõi tiến độ theo thời gian.'
              : 'Create a session and upload a walking video to begin tracking longitudinal gait progress.'}
          </p>
          <Link
            href={selectedSubjectId ? `/subjects/${selectedSubjectId}` : '/subjects'}
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-teal-600 text-white text-xs font-semibold rounded-xl"
          >
            <span>{locale === 'vi' ? 'Mở hồ sơ đối tượng' : 'Open Subject Profile'}</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      ) : (
        <>
          {/* Period & Quality Overview Strip */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-xs">
              <div className="text-[11px] text-slate-500 font-semibold uppercase">{locale === 'vi' ? 'Tổng số phiên' : 'Total Sessions'}</div>
              <div className="text-2xl font-bold text-slate-900 mt-1">{progress.total_sessions}</div>
            </div>
            <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-xs">
              <div className="text-[11px] text-emerald-700 font-semibold uppercase">{locale === 'vi' ? 'Phiên hợp lệ' : 'Valid Sessions'}</div>
              <div className="text-2xl font-bold text-emerald-700 mt-1">{progress.valid_sessions_count}</div>
            </div>
            <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-xs">
              <div className="text-[11px] text-amber-700 font-semibold uppercase">{locale === 'vi' ? 'Thiếu / Độ tin cậy thấp' : 'Excluded / Unavailable'}</div>
              <div className="text-2xl font-bold text-amber-700 mt-1">{progress.unavailable_or_unreliable_count}</div>
            </div>
            <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-xs">
              <div className="text-[11px] text-slate-500 font-semibold uppercase">{locale === 'vi' ? 'Khoảng thời gian' : 'Assessment Period'}</div>
              <div className="text-xs font-semibold text-slate-800 mt-2">
                {progress.period_start ? new Date(progress.period_start).toLocaleDateString() : '—'} → {progress.period_end ? new Date(progress.period_end).toLocaleDateString() : '—'}
              </div>
            </div>
          </div>

          {/* Priority Metric Summary Cards */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {renderSummaryCard(progress.walking_speed, 2)}
            {renderSummaryCard(progress.cadence, 1)}
          </div>

          {/* Separate Time-Series Trend Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <GaitTrendChart
              title={locale === 'vi' ? 'Xu hướng Tốc độ đi bộ' : 'Walking Speed Over Time'}
              unit="m/s"
              series={filteredWsSeries}
              baselineValue={progress.walking_speed.baseline_value}
              color="#0d9488"
              locale={locale}
            />
            <GaitTrendChart
              title={locale === 'vi' ? 'Xu hướng Nhịp bước (Cadence)' : 'Cadence Over Time'}
              unit="steps/min"
              series={filteredCadSeries}
              baselineValue={progress.cadence.baseline_value}
              color="#0284c7"
              locale={locale}
            />
          </div>

          {/* Chronological Rehabilitation Timeline */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
            <div className="p-5 border-b border-slate-100 flex items-center justify-between">
              <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <Calendar className="w-4 h-4 text-teal-600" />
                <span>{locale === 'vi' ? 'Dòng thời gian Phục hồi' : 'Chronological Rehabilitation Timeline'}</span>
              </h2>
              <span className="text-xs text-slate-400">{filteredTimeline.length} entries</span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase text-[11px]">
                    <th className="py-3 px-4">Date</th>
                    <th className="py-3 px-4">Type</th>
                    <th className="py-3 px-4">Walking Speed</th>
                    <th className="py-3 px-4">Cadence</th>
                    <th className="py-3 px-4">Quality</th>
                    <th className="py-3 px-4">Analysis</th>
                    <th className="py-3 px-4 text-right">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {[...filteredTimeline].reverse().map((item, idx) => (
                    <tr key={item.session_id} className="hover:bg-slate-50/70">
                      <td className="py-3 px-4 font-medium text-slate-900">
                        {item.date ? new Date(item.date).toLocaleDateString(locale === 'vi' ? 'vi-VN' : 'en-US') : '—'}
                        {idx === 0 && (
                          <span className="ml-2 px-1.5 py-0.5 rounded bg-teal-50 text-teal-700 text-[10px] font-bold">Latest</span>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        <span className="capitalize text-slate-700 font-medium">
                          {item.record_type === 'clinical_assessment' ? 'Clinical Assessment' : 'Rehab Session'}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-mono">
                        {item.walking_speed.value !== null ? (
                          <span className="font-semibold text-slate-900">{item.walking_speed.value.toFixed(2)} m/s</span>
                        ) : (
                          <span className="text-slate-400 italic" title={item.walking_speed.reason || ''}>Unavailable</span>
                        )}
                      </td>
                      <td className="py-3 px-4 font-mono">
                        {item.cadence.value !== null ? (
                          <span className="font-semibold text-slate-900">{item.cadence.value.toFixed(1)} steps/min</span>
                        ) : (
                          <span className="text-slate-400 italic" title={item.cadence.reason || ''}>Unavailable</span>
                        )}
                      </td>
                      <td className="py-3 px-4">{qualityBadge(item.quality_status)}</td>
                      <td className="py-3 px-4 capitalize text-slate-600">{item.analysis_status}</td>
                      <td className="py-3 px-4 text-right">
                        <Link
                          href={`/sessions/${item.session_id}/results`}
                          className="text-teal-700 font-semibold hover:underline inline-flex items-center gap-1"
                        >
                          <span>View</span>
                          <ArrowRight className="w-3 h-3" />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

export default function ProgressPage() {
  return (
    <Suspense fallback={<div className="p-12 text-center text-sm text-slate-400">Loading...</div>}>
      <ProgressContent />
    </Suspense>
  )
}
