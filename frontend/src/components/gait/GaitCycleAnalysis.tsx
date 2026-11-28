'use client'

import React, { useEffect, useState } from 'react'
import { gaitCyclesApi } from '@/lib/api'
import type {
  GaitCycleAnalysisData,
  GaitCycleRecord,
  GaitMetricSummary,
  GaitSubPhase,
} from '@/types/api'
import { Activity, AlertTriangle, Info, Loader2 } from 'lucide-react'

type Side = 'left' | 'right'
const SIDES: Side[] = ['left', 'right']

const SIDE_COLOR: Record<Side, { stance: string; swing: string; text: string; marker: string }> = {
  left: { stance: 'bg-teal-600', swing: 'bg-teal-200', text: 'text-teal-800', marker: '#0d9488' },
  right: { stance: 'bg-indigo-600', swing: 'bg-indigo-200', text: 'text-indigo-800', marker: '#4f46e5' },
}

const SUBPHASE_LABEL: Record<string, { en: string; vi: string }> = {
  initial_contact: { en: 'Initial contact', vi: 'Tiếp đất ban đầu' },
  loading_response: { en: 'Loading response', vi: 'Đáp ứng tải' },
  midstance: { en: 'Midstance', vi: 'Giữa pha chống' },
  terminal_stance: { en: 'Terminal stance', vi: 'Cuối pha chống' },
  pre_swing: { en: 'Pre-swing', vi: 'Trước pha đu' },
  initial_swing: { en: 'Initial swing', vi: 'Đầu pha đu' },
  mid_swing: { en: 'Midswing', vi: 'Giữa pha đu' },
  terminal_swing: { en: 'Terminal swing', vi: 'Cuối pha đu' },
}

const SUBPHASE_SHADE: Record<string, string> = {
  loading_response: 'bg-slate-700',
  midstance: 'bg-slate-600',
  terminal_stance: 'bg-slate-500',
  pre_swing: 'bg-slate-400',
  initial_swing: 'bg-sky-300',
  mid_swing: 'bg-sky-200',
  terminal_swing: 'bg-sky-100',
}

const METRIC_LABEL: Record<string, { en: string; vi: string }> = {
  stance_time: { en: 'Stance time', vi: 'Thời gian pha chống' },
  swing_time: { en: 'Swing time', vi: 'Thời gian pha đu' },
  stance_pct: { en: 'Stance', vi: 'Pha chống' },
  swing_pct: { en: 'Swing', vi: 'Pha đu' },
  gait_cycle_duration: { en: 'Gait cycle duration', vi: 'Thời gian chu kỳ bước' },
  double_support_time: { en: 'Double-support time', vi: 'Thời gian chống hai chân' },
  double_support_pct: { en: 'Double support', vi: 'Chống hai chân' },
  stance_time_asymmetry: { en: 'Stance-time asymmetry', vi: 'Bất đối xứng thời gian chống' },
  swing_time_asymmetry: { en: 'Swing-time asymmetry', vi: 'Bất đối xứng thời gian đu' },
  stance_pct_asymmetry: { en: 'Stance-% asymmetry', vi: 'Bất đối xứng % pha chống' },
  cadence: { en: 'Cadence', vi: 'Nhịp bước' },
}

const fmt = (v: number | null | undefined, d = 2) =>
  v === null || v === undefined || Number.isNaN(v) ? '—' : Number(v).toFixed(d)

const errDetail = (err: unknown): string | undefined =>
  (err as { response?: { data?: { detail?: string } } } | null)?.response?.data?.detail

export default function GaitCycleAnalysisSection({ recordingId, isVi }: { recordingId: string; isVi: boolean }) {
  const t = (en: string, vi: string) => (isVi ? vi : en)
  const [data, setData] = useState<GaitCycleAnalysisData | null>(null)
  const [state, setState] = useState<'loading' | 'ready' | 'missing' | 'error'>('loading')
  const [error, setError] = useState<string | null>(null)
  const [cycleFilter, setCycleFilter] = useState<'all' | 'valid' | 'excluded'>('all')

  useEffect(() => {
    let mounted = true
    gaitCyclesApi
      .getForRecording(recordingId)
      .then((r) => {
        if (!mounted) return
        setData(r.analysis)
        setState('ready')
      })
      .catch((err) => {
        if (!mounted) return
        const status = (err as { response?: { status?: number } })?.response?.status
        if (status === 404) setState('missing')
        else {
          setError(errDetail(err) || t('Failed to load gait-cycle analysis.', 'Không thể tải phân tích chu kỳ bước.'))
          setState('error')
        }
      })
    return () => {
      mounted = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recordingId])

  const metric = (name: string, side: Side | null = null): GaitMetricSummary | undefined =>
    data?.phase_metrics.find((m) => m.name === name && m.side === side)

  return (
    <section className="bg-white rounded-2xl border border-slate-200 p-5 sm:p-6 shadow-xs space-y-5" aria-labelledby="gait-cycle-title">
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-2">
        <div>
          <h2 id="gait-cycle-title" className="text-base font-bold text-slate-900 flex items-center gap-2">
            <Activity className="w-4 h-4 text-teal-600" /> {t('Gait Cycle Analysis', 'Phân tích chu kỳ bước')}
          </h2>
          <p className="text-[11px] text-slate-500 mt-0.5">
            {t('Estimated from 2D video – not validated against force plates or instrumented walkways.',
              'Ước tính từ video 2D – chưa được kiểm chứng bằng bàn lực hoặc thảm đo chuyên dụng.')}
          </p>
        </div>
        {data && (
          <span className="text-[11px] font-mono text-slate-400 self-start">{data.method_version} · {data.camera_view} view</span>
        )}
      </div>

      {state === 'loading' && (
        <div className="flex items-center gap-2 text-xs text-slate-500"><Loader2 className="w-4 h-4 animate-spin" /> {t('Loading…', 'Đang tải…')}</div>
      )}
      {state === 'missing' && (
        <p className="text-xs text-slate-500">
          {t('No gait-cycle analysis for this recording yet. Recordings analysed before this feature need to be re-analysed.',
            'Chưa có phân tích chu kỳ bước cho bản ghi này. Các bản ghi phân tích trước đây cần được phân tích lại.')}
        </p>
      )}
      {state === 'error' && <p className="text-xs text-red-700">{error}</p>}

      {state === 'ready' && data && (
        <>
          {data.warnings.length > 0 && (
            <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-[11px] text-amber-900 space-y-1">
              {data.warnings.map((w) => (
                <div key={w} className="flex gap-1.5"><AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" /> {w}</div>
              ))}
            </div>
          )}

          {data.status === 'analysed' && (
            <>
              <QualityStrip data={data} isVi={isVi} />
              <BilateralBars metric={metric} isVi={isVi} />
              <MetricsTable data={data} metric={metric} isVi={isVi} />
              <EventTimeline data={data} isVi={isVi} />
              <SubPhaseBreakdown data={data} isVi={isVi} />
            </>
          )}

          {data.cycles.length > 0 && (
            <CycleTable cycles={data.cycles} filter={cycleFilter} setFilter={setCycleFilter} isVi={isVi} />
          )}

          <details className="text-[11px] text-slate-600">
            <summary className="cursor-pointer font-semibold text-slate-700 flex items-center gap-1.5">
              <Info className="w-3.5 h-3.5" /> {t('Method & data quality', 'Phương pháp & chất lượng dữ liệu')}
            </summary>
            <ul className="list-disc list-inside mt-2 space-y-1">
              <li>{data.method}.</li>
              <li>
                {t('Initial contact = heel furthest forward of the pelvis; toe-off = toe furthest behind the pelvis. Foot height is not used as proof of ground contact.',
                  'Tiếp đất = gót xa nhất về phía trước so với khung chậu; nhấc ngón = ngón chân xa nhất phía sau khung chậu. Độ cao bàn chân không được dùng làm bằng chứng tiếp đất.')}
              </li>
              <li>
                {t('Events below confidence', 'Sự kiện có độ tin cậy dưới')} {data.thresholds.min_event_confidence}{' '}
                {t('are flagged; cycles containing them, incomplete or implausible cycles are excluded from averages.',
                  'bị gắn cờ; chu kỳ chứa chúng, chu kỳ thiếu hoặc bất hợp lý bị loại khỏi giá trị trung bình.')}
              </li>
              <li>
                {t('Landmarks used', 'Điểm mốc sử dụng')}:{' '}
                {Object.entries(data.landmarks_used).map(([k, v]) => `${k.replace(/_/g, ' ')}: ${v}`).join('; ') || '—'}
              </li>
              {data.walking_direction && (
                <li>{t('Walking direction', 'Hướng đi')}: {data.walking_direction.replace(/_/g, ' ')} ({data.direction_source?.replace(/_/g, ' ')})</li>
              )}
            </ul>
          </details>
        </>
      )}
    </section>
  )
}

function StatusTag({ status, isVi }: { status: string; isVi: boolean }) {
  const map: Record<string, [string, string, string]> = {
    estimated: ['bg-sky-50 border-sky-200 text-sky-800', 'Estimated', 'Ước tính'],
    low_confidence: ['bg-amber-50 border-amber-200 text-amber-800', 'Low confidence', 'Độ tin cậy thấp'],
    unavailable: ['bg-slate-50 border-slate-200 text-slate-500', 'Unavailable', 'Không có'],
    valid: ['bg-emerald-50 border-emerald-200 text-emerald-800', 'Valid', 'Hợp lệ'],
    incomplete: ['bg-slate-100 border-slate-300 text-slate-600', 'Incomplete', 'Không đầy đủ'],
    implausible: ['bg-red-50 border-red-200 text-red-800', 'Implausible', 'Bất hợp lý'],
  }
  const [cls, en, vi] = map[status] || map.unavailable
  return <span className={`inline-block px-1.5 py-0.5 rounded border text-[10px] font-semibold ${cls}`}>{isVi ? vi : en}</span>
}

function QualityStrip({ data, isVi }: { data: GaitCycleAnalysisData; isVi: boolean }) {
  const t = (en: string, vi: string) => (isVi ? vi : en)
  const c = data.counts
  const items: [string, number | undefined][] = [
    [t('Valid cycles', 'Chu kỳ hợp lệ'), c.cycles_valid],
    [t('Low-confidence cycles', 'Chu kỳ độ tin cậy thấp'), c.cycles_low_confidence],
    [t('Incomplete', 'Không đầy đủ'), c.cycles_incomplete],
    [t('Implausible', 'Bất hợp lý'), c.cycles_implausible],
    [t('Low-confidence events', 'Sự kiện độ tin cậy thấp'), c.low_confidence_events],
  ]
  return (
    <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
      {items.map(([label, n]) => (
        <div key={label} className="p-2.5 rounded-lg border border-slate-200 bg-slate-50">
          <div className="text-[10px] text-slate-500">{label}</div>
          <div className="text-sm font-bold text-slate-900">{n ?? 0}</div>
        </div>
      ))}
    </div>
  )
}

function BilateralBars({ metric, isVi }: { metric: (n: string, s?: Side | null) => GaitMetricSummary | undefined; isVi: boolean }) {
  const t = (en: string, vi: string) => (isVi ? vi : en)
  return (
    <div className="space-y-2">
      <h3 className="text-xs font-bold text-slate-700">{t('Stance / swing – left vs right (% of gait cycle)', 'Pha chống / pha đu – trái và phải (% chu kỳ)')}</h3>
      {SIDES.map((side) => {
        const st = metric('stance_pct', side)
        const sw = metric('swing_pct', side)
        const ok = st?.value != null && sw?.value != null
        return (
          <div key={side} className="flex items-center gap-3 text-xs">
            <span className={`w-12 font-semibold capitalize ${SIDE_COLOR[side].text}`}>{isVi ? (side === 'left' ? 'Trái' : 'Phải') : side}</span>
            {ok ? (
              <div className="flex-1 flex h-6 rounded-md overflow-hidden border border-slate-200" role="img"
                aria-label={`${side}: stance ${fmt(st!.value, 1)}%, swing ${fmt(sw!.value, 1)}%`}>
                <div className={`${SIDE_COLOR[side].stance} text-white text-[10px] font-semibold flex items-center px-2`} style={{ width: `${st!.value}%` }}>
                  {t('Stance', 'Chống')} {fmt(st!.value, 1)}%
                </div>
                <div className={`${SIDE_COLOR[side].swing} text-slate-800 text-[10px] font-semibold flex items-center px-2`} style={{ width: `${sw!.value}%` }}>
                  {t('Swing', 'Đu')} {fmt(sw!.value, 1)}%
                </div>
              </div>
            ) : (
              <div className="flex-1 text-slate-500">{t('Unavailable – no valid cycles for this leg.', 'Không có – không có chu kỳ hợp lệ cho chân này.')}</div>
            )}
            {st && <StatusTag status={st.status} isVi={isVi} />}
          </div>
        )
      })}
    </div>
  )
}

function MetricsTable({
  data, metric, isVi,
}: { data: GaitCycleAnalysisData; metric: (n: string, s?: Side | null) => GaitMetricSummary | undefined; isVi: boolean }) {
  const t = (en: string, vi: string) => (isVi ? vi : en)
  const label = (n: string) => (isVi ? METRIC_LABEL[n]?.vi : METRIC_LABEL[n]?.en) || n
  const cell = (m?: GaitMetricSummary) =>
    !m || m.value == null ? <span className="text-slate-400">—</span> : (
      <span>
        <strong className="text-slate-900">{fmt(m.value, m.unit.startsWith('%') ? 1 : 3)}</strong>
        {m.sd != null && <span className="text-slate-500"> ± {fmt(m.sd, m.unit.startsWith('%') ? 1 : 3)}</span>}
        <span className="text-slate-400"> (n={m.n_cycles})</span>
      </span>
    )
  const bilateral = ['stance_time', 'swing_time', 'stance_pct', 'swing_pct']
  const asym: Record<string, string> = { stance_time: 'stance_time_asymmetry', swing_time: 'swing_time_asymmetry', stance_pct: 'stance_pct_asymmetry' }
  const single = ['gait_cycle_duration', 'double_support_time', 'double_support_pct']

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <div className="lg:col-span-2 overflow-x-auto">
        <table className="w-full text-xs">
          <caption className="text-left text-xs font-bold text-slate-700 mb-2">{t('Phase durations & percentages (mean ± SD)', 'Thời lượng & tỷ lệ pha (TB ± ĐLC)')}</caption>
          <thead>
            <tr className="text-left text-slate-500 border-b border-slate-200">
              <th className="py-1.5 pr-2 font-semibold">{t('Metric', 'Chỉ số')}</th>
              <th className="py-1.5 pr-2 font-semibold">{t('Left', 'Trái')}</th>
              <th className="py-1.5 pr-2 font-semibold">{t('Right', 'Phải')}</th>
              <th className="py-1.5 font-semibold">{t('Asymmetry (SI %)', 'Bất đối xứng (SI %)')}</th>
            </tr>
          </thead>
          <tbody>
            {bilateral.map((n) => {
              const l = metric(n, 'left')
              return (
                <tr key={n} className="border-b border-slate-100">
                  <td className="py-1.5 pr-2 text-slate-700">{label(n)} <span className="text-slate-400">({l?.unit})</span></td>
                  <td className="py-1.5 pr-2">{cell(l)}</td>
                  <td className="py-1.5 pr-2">{cell(metric(n, 'right'))}</td>
                  <td className="py-1.5">{asym[n] ? cell(metric(asym[n])) : <span className="text-slate-400">—</span>}</td>
                </tr>
              )
            })}
            {single.map((n) => {
              const m = metric(n)
              return (
                <tr key={n} className="border-b border-slate-100">
                  <td className="py-1.5 pr-2 text-slate-700">{label(n)} <span className="text-slate-400">({m?.unit})</span></td>
                  <td className="py-1.5 pr-2" colSpan={2}>{cell(m)}</td>
                  <td className="py-1.5">{m && m.value == null && m.note && <span className="text-[10px] text-slate-500">{m.note}</span>}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
        <p className="text-[10px] text-slate-500 mt-1">
          {t('SI = |L − R| / mean(L, R) × 100; 0 means symmetric. Averages use valid cycles only.',
            'SI = |T − P| / TB(T, P) × 100; 0 là đối xứng. Giá trị trung bình chỉ dùng chu kỳ hợp lệ.')}
        </p>
      </div>
      <div className="p-3 rounded-xl border border-slate-200 bg-slate-50 space-y-1 self-start">
        <div className="text-xs font-bold text-slate-700">{label('cadence')}</div>
        <div className="text-lg font-bold text-slate-900">{fmt(data.cadence?.value, 1)} <span className="text-xs font-normal text-slate-500">steps/min</span></div>
        {data.cadence && <StatusTag status={data.cadence.status} isVi={isVi} />}
        <p className="text-[10px] text-slate-500">{data.cadence?.note}</p>
        <p className="text-[10px] text-slate-500">{t('Reported separately from phase measurements.', 'Báo cáo riêng với các chỉ số pha.')}</p>
      </div>
    </div>
  )
}

function EventTimeline({ data, isVi }: { data: GaitCycleAnalysisData; isVi: boolean }) {
  const t = (en: string, vi: string) => (isVi ? vi : en)
  const total = Math.max(data.duration_s || 0, ...data.events.map((e) => e.timestamp_s), 0.001)
  const W = 1000, rowH = 34, padL = 60, H = rowH * 2 + 30
  const x = (s: number) => padL + (s / total) * (W - padL - 10)
  const ticks = Array.from({ length: Math.floor(total) + 1 }, (_, i) => i)

  return (
    <div className="space-y-1.5">
      <h3 className="text-xs font-bold text-slate-700">{t('Gait event timeline', 'Dòng thời gian sự kiện bước')}</h3>
      <div className="overflow-x-auto">
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full min-w-[560px]" role="img"
          aria-label={t('Timeline of initial contact and toe-off events for both legs', 'Dòng thời gian tiếp đất và nhấc ngón của hai chân')}>
          {SIDES.map((side, r) => {
            const y = 8 + r * rowH
            const cycles = data.cycles.filter((c) => c.side === side && c.toe_off_s != null && c.end_s != null)
            return (
              <g key={side}>
                <text x={0} y={y + 16} fontSize="12" fill="#475569">{isVi ? (side === 'left' ? 'Trái' : 'Phải') : side}</text>
                <rect x={padL} y={y + 6} width={W - padL - 10} height={14} fill="#f1f5f9" rx={3} />
                {cycles.map((c) => (
                  <g key={c.cycle_id} opacity={c.included_in_aggregate ? 1 : 0.35}>
                    <rect x={x(c.start_s)} y={y + 6} width={Math.max(0, x(c.toe_off_s!) - x(c.start_s))} height={14} fill={SIDE_COLOR[side].marker} />
                    <rect x={x(c.toe_off_s!)} y={y + 6} width={Math.max(0, x(c.end_s!) - x(c.toe_off_s!))} height={14} fill={SIDE_COLOR[side].marker} opacity={0.3} />
                  </g>
                ))}
                {data.events.filter((e) => e.side === side).map((e) => (
                  <g key={`${e.event_type}-${e.frame_index}`}>
                    <title>{`${e.event_type === 'initial_contact' ? 'IC' : 'TO'} ${e.timestamp_s.toFixed(3)} s · frame ${e.frame_index} · conf ${e.confidence.toFixed(2)}${e.low_confidence ? ' (low)' : ''}`}</title>
                    {e.event_type === 'initial_contact' ? (
                      <polygon points={`${x(e.timestamp_s)},${y + 4} ${x(e.timestamp_s) - 5},${y - 4} ${x(e.timestamp_s) + 5},${y - 4}`}
                        fill={e.low_confidence ? 'white' : '#0f172a'} stroke="#0f172a" strokeWidth={1.2} />
                    ) : (
                      <polygon points={`${x(e.timestamp_s)},${y + 22} ${x(e.timestamp_s) - 5},${y + 30} ${x(e.timestamp_s) + 5},${y + 30}`}
                        fill={e.low_confidence ? 'white' : '#b45309'} stroke="#b45309" strokeWidth={1.2} />
                    )}
                  </g>
                ))}
              </g>
            )
          })}
          {ticks.map((s) => (
            <g key={s}>
              <line x1={x(s)} x2={x(s)} y1={H - 22} y2={H - 18} stroke="#94a3b8" />
              <text x={x(s)} y={H - 6} fontSize="10" fill="#64748b" textAnchor="middle">{s}s</text>
            </g>
          ))}
        </svg>
      </div>
      <p className="text-[10px] text-slate-500">
        {t('▼ initial contact (above bar) · ▲ toe-off (below bar) · hollow marker = low confidence · solid = stance, light = swing · faded cycles are excluded from averages. Hover a marker for its timestamp.',
          '▼ tiếp đất (trên thanh) · ▲ nhấc ngón (dưới thanh) · ký hiệu rỗng = độ tin cậy thấp · đậm = pha chống, nhạt = pha đu · chu kỳ mờ bị loại khỏi trung bình. Di chuột để xem thời điểm.')}
      </p>
    </div>
  )
}

function SubPhaseBreakdown({ data, isVi }: { data: GaitCycleAnalysisData; isVi: boolean }) {
  const t = (en: string, vi: string) => (isVi ? vi : en)
  const label = (n: string) => (isVi ? SUBPHASE_LABEL[n]?.vi : SUBPHASE_LABEL[n]?.en) || n
  return (
    <div className="space-y-2">
      <h3 className="text-xs font-bold text-slate-700">{t('Eight-phase breakdown (mean % of gait cycle)', 'Tám giai đoạn bước (TB % chu kỳ)')}</h3>
      {SIDES.map((side) => {
        const rows: GaitSubPhase[] = data.subphase_summary?.[side] || []
        const segs = rows.filter((p) => p.name !== 'initial_contact' && p.available && p.start_pct != null && p.end_pct != null)
        const missing = rows.filter((p) => p.name !== 'initial_contact' && !p.available)
        return (
          <div key={side} className="space-y-1">
            <div className="flex items-center gap-3 text-xs">
              <span className={`w-12 font-semibold capitalize ${SIDE_COLOR[side].text}`}>{isVi ? (side === 'left' ? 'Trái' : 'Phải') : side}</span>
              <div className="flex-1 relative h-6 rounded-md bg-slate-100 border border-slate-200 overflow-hidden">
                {segs.map((p) => (
                  <div key={p.name} title={`${label(p.name)}: ${fmt(p.start_pct, 1)}–${fmt(p.end_pct, 1)}%`}
                    className={`absolute top-0 h-full ${SUBPHASE_SHADE[p.name]} border-r border-white`}
                    style={{ left: `${p.start_pct}%`, width: `${Math.max(0, p.end_pct! - p.start_pct!)}%` }} />
                ))}
              </div>
            </div>
            <div className="ml-[60px] grid grid-cols-2 sm:grid-cols-4 gap-x-3 gap-y-0.5 text-[10px] text-slate-600">
              {rows.filter((p) => p.name !== 'initial_contact').map((p) => (
                <div key={p.name} className="flex items-center gap-1">
                  <span className={`w-2.5 h-2.5 rounded-sm ${p.available ? SUBPHASE_SHADE[p.name] : 'bg-white border border-dashed border-slate-400'}`} />
                  <span>{label(p.name)}: {p.available ? `${fmt(p.start_pct, 0)}–${fmt(p.end_pct, 0)}%` : t('unavailable', 'không có')}</span>
                </div>
              ))}
            </div>
            {missing.length > 0 && (
              <p className="ml-[60px] text-[10px] text-amber-800">
                {t('Not classified', 'Không phân loại')}: {missing.map((p) => `${label(p.name)} – ${p.reason}`).join(' ')}
              </p>
            )}
          </div>
        )
      })}
    </div>
  )
}

function CycleTable({
  cycles, filter, setFilter, isVi,
}: { cycles: GaitCycleRecord[]; filter: 'all' | 'valid' | 'excluded'; setFilter: (f: 'all' | 'valid' | 'excluded') => void; isVi: boolean }) {
  const t = (en: string, vi: string) => (isVi ? vi : en)
  const shown = cycles.filter((c) => filter === 'all' || (filter === 'valid' ? c.included_in_aggregate : !c.included_in_aggregate))
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-xs font-bold text-slate-700">{t('Individual gait cycles', 'Từng chu kỳ bước')}</h3>
        <div className="flex gap-1 text-[11px]" role="group">
          {(['all', 'valid', 'excluded'] as const).map((f) => (
            <button key={f} type="button" aria-pressed={filter === f} onClick={() => setFilter(f)}
              className={`px-2 py-1 rounded-md border font-semibold ${filter === f ? 'border-teal-600 bg-teal-50 text-teal-900' : 'border-slate-200 text-slate-600 hover:bg-slate-50'}`}>
              {f === 'all' ? t('All', 'Tất cả') : f === 'valid' ? t('Used in averages', 'Dùng tính TB') : t('Excluded', 'Bị loại')}
            </button>
          ))}
        </div>
      </div>
      <div className="overflow-x-auto max-h-80 overflow-y-auto border border-slate-200 rounded-lg">
        <table className="w-full text-[11px]">
          <thead className="sticky top-0 bg-slate-50">
            <tr className="text-left text-slate-500">
              <th className="p-1.5 font-semibold">{t('Cycle', 'Chu kỳ')}</th>
              <th className="p-1.5 font-semibold">{t('Time (s)', 'Thời gian (s)')}</th>
              <th className="p-1.5 font-semibold">{t('Duration', 'Thời lượng')}</th>
              <th className="p-1.5 font-semibold">{t('Stance / swing (s)', 'Chống / đu (s)')}</th>
              <th className="p-1.5 font-semibold">{t('Stance %', '% chống')}</th>
              <th className="p-1.5 font-semibold">{t('Double support', 'Chống hai chân')}</th>
              <th className="p-1.5 font-semibold">{t('Min. conf.', 'Tin cậy tối thiểu')}</th>
              <th className="p-1.5 font-semibold">{t('Status', 'Trạng thái')}</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((c) => (
              <tr key={c.cycle_id} className="border-t border-slate-100 align-top">
                <td className={`p-1.5 font-semibold capitalize ${SIDE_COLOR[c.side].text}`}>{c.cycle_id.replace(/_/g, ' ')}</td>
                <td className="p-1.5 whitespace-nowrap">{fmt(c.start_s, 2)}–{fmt(c.end_s, 2)}</td>
                <td className="p-1.5">{fmt(c.duration_s, 3)}</td>
                <td className="p-1.5 whitespace-nowrap">{fmt(c.stance_s, 3)} / {fmt(c.swing_s, 3)}</td>
                <td className="p-1.5">{fmt(c.stance_pct, 1)}</td>
                <td className="p-1.5">{c.double_support_pct != null ? `${fmt(c.double_support_pct, 1)}%` : '—'}</td>
                <td className="p-1.5">{fmt(c.min_event_confidence, 2)}</td>
                <td className="p-1.5">
                  <StatusTag status={c.status} isVi={isVi} />
                  {c.reasons.length > 0 && <div className="text-[10px] text-slate-500 mt-0.5 max-w-[260px]">{c.reasons.join(' ')}</div>}
                </td>
              </tr>
            ))}
            {shown.length === 0 && (
              <tr><td colSpan={8} className="p-3 text-center text-slate-500">{t('No cycles in this filter.', 'Không có chu kỳ.')}</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
