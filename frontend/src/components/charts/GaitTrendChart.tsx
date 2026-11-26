'use client'

import React from 'react'
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from 'recharts'
import type { MetricSeriesPoint } from '@/types/api'

interface GaitTrendChartProps {
  title: string
  unit: string
  series: MetricSeriesPoint[]
  baselineValue?: number | null
  color?: string
  locale?: string
  subtitle?: string
}

export function GaitTrendChart({
  title,
  unit,
  series,
  baselineValue,
  color = '#0d9488',
  locale = 'en',
  subtitle,
}: GaitTrendChartProps) {
  const chartData = series.map((pt, i) => ({
    idx: i + 1,
    dateLabel: pt.date ? new Date(pt.date).toLocaleDateString(locale === 'vi' ? 'vi-VN' : 'en-US', { month: 'short', day: 'numeric' }) : `#${i + 1}`,
    fullDate: pt.date ? new Date(pt.date).toLocaleString(locale === 'vi' ? 'vi-VN' : 'en-US') : '',
    value: pt.status === 'valid' ? pt.value : null,
    lowConfValue: pt.status === 'low_confidence' ? pt.value : null,
    status: pt.status,
    record_type: pt.record_type,
    reason: pt.reason,
    is_baseline: pt.is_baseline,
    is_latest: pt.is_latest,
  }))

  const hasValidPoints = chartData.some((d) => d.value !== null || d.lowConfValue !== null)
  const excludedPoints = chartData.filter((d) => d.value === null)

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs space-y-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-bold text-slate-900">{title}</h3>
          <p className="text-[11px] text-slate-500">
            {locale === 'vi' ? `Đơn vị: ${unit}` : `Unit: ${unit}`}
            {baselineValue !== null && baselineValue !== undefined && (
              <span className="ml-2 text-teal-700 font-semibold">
                • {locale === 'vi' ? 'Mốc đầu' : 'Baseline'}: {baselineValue} {unit}
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-3 text-[11px] text-slate-500">
          <span className="inline-flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />
            {locale === 'vi' ? 'Hợp lệ' : 'Valid'}
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-400" />
            {locale === 'vi' ? 'Độ tin cậy thấp' : 'Low confidence'}
          </span>
        </div>
      </div>

      {!hasValidPoints ? (
        <div className="h-52 rounded-xl bg-slate-50 border border-dashed border-slate-200 flex items-center justify-center p-6 text-center text-xs text-slate-500">
          {locale === 'vi'
            ? `Chưa có dữ liệu hợp lệ cho ${title.toLowerCase()}. Các giá trị không khả dụng không được vẽ giả định.`
            : `No valid ${title.toLowerCase()} measurements available yet. Unavailable data is never fabricated.`}
        </div>
      ) : (
        <div className="h-56 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 10, right: 16, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="dateLabel" tick={{ fontSize: 11, fill: '#64748b' }} />
              <YAxis tick={{ fontSize: 11, fill: '#64748b' }} width={45} domain={['auto', 'auto']} />
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload || payload.length === 0) return null
                  const d = payload[0].payload
                  const shownVal = d.value ?? d.lowConfValue
                  return (
                    <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-md text-xs space-y-1 max-w-xs">
                      <div className="font-bold text-slate-900">
                        {d.fullDate || d.dateLabel}
                        {d.is_baseline && <span className="ml-1.5 text-[10px] px-1.5 py-0.5 rounded bg-teal-50 text-teal-700">Baseline</span>}
                        {d.is_latest && <span className="ml-1.5 text-[10px] px-1.5 py-0.5 rounded bg-sky-50 text-sky-700">Latest</span>}
                      </div>
                      <div className="text-slate-600 capitalize">
                        {d.record_type === 'clinical_assessment' ? 'Clinical Assessment' : 'Rehab Session'}
                      </div>
                      <div className="font-semibold text-slate-900">
                        {shownVal !== null && shownVal !== undefined ? `${shownVal} ${unit}` : 'Unavailable'}
                      </div>
                      <div className="text-[11px] text-slate-500 capitalize">Status: {String(d.status).replace('_', ' ')}</div>
                      {d.reason && <div className="text-[11px] text-amber-700">{d.reason}</div>}
                    </div>
                  )
                }}
              />
              {baselineValue !== null && baselineValue !== undefined && (
                <ReferenceLine y={baselineValue} stroke="#94a3b8" strokeDasharray="4 4" />
              )}
              <Line
                type="monotone"
                dataKey="value"
                name={title}
                stroke={color}
                strokeWidth={2.5}
                connectNulls={false}
                dot={(props: any) => {
                  const { cx, cy, payload } = props
                  if (cx == null || cy == null || payload?.value == null) return <g key={props.key} />
                  const isAssessment = payload.record_type === 'clinical_assessment'
                  return (
                    <circle
                      key={props.key}
                      cx={cx}
                      cy={cy}
                      r={payload.is_latest || payload.is_baseline ? 5.5 : 4}
                      fill={isAssessment ? '#0284c7' : color}
                      stroke="#ffffff"
                      strokeWidth={1.5}
                    />
                  )
                }}
              />
              <Line
                type="monotone"
                dataKey="lowConfValue"
                name="Low Confidence"
                stroke="#f59e0b"
                strokeWidth={0}
                dot={{ r: 4.5, fill: '#f59e0b', stroke: '#ffffff', strokeWidth: 1.5 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {excludedPoints.length > 0 && (
        <div className="text-[11px] text-amber-700 bg-amber-50/70 border border-amber-200/70 rounded-lg px-3 py-1.5">
          {locale === 'vi'
            ? `${excludedPoints.length} phiên có dữ liệu thiếu/độ tin cậy thấp không được tính vào xu hướng chính.`
            : `${excludedPoints.length} session(s) had unavailable or low-confidence values and are excluded from primary trend calculations.`}
        </div>
      )}

      {subtitle && <p className="text-xs text-slate-600 leading-relaxed pt-1">{subtitle}</p>}
    </div>
  )
}
