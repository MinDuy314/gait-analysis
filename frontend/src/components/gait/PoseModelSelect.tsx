'use client'

import React from 'react'
import type { PoseModel } from '@/types/api'

const OPTIONS: { value: PoseModel; en: string; vi: string; hintEn: string; hintVi: string }[] = [
  {
    value: 'yolo',
    en: 'YOLO (default)',
    vi: 'YOLO (mặc định)',
    hintEn: 'Robust body tracking; no heel/toe points, so gait events use the ankle as a proxy.',
    hintVi: 'Theo dõi cơ thể ổn định; không có điểm gót/ngón chân nên sự kiện bước dùng mắt cá thay thế.',
  },
  {
    value: 'mediapipe',
    en: 'MediaPipe (heel & toe)',
    vi: 'MediaPipe (gót & ngón chân)',
    hintEn: 'Tracks heel and toe for more precise contact/toe-off and heel rise. Single person only.',
    hintVi: 'Theo dõi gót và ngón chân để xác định tiếp đất/nhấc ngón chính xác hơn. Chỉ một người.',
  },
]

export default function PoseModelSelect({
  value,
  onChange,
  isVi,
  disabled,
}: {
  value: PoseModel
  onChange: (v: PoseModel) => void
  isVi: boolean
  disabled?: boolean
}) {
  const current = OPTIONS.find((o) => o.value === value) || OPTIONS[0]
  return (
    <div className="space-y-1">
      <label className="text-xs font-semibold text-slate-700 flex items-center gap-2">
        {isVi ? 'Mô hình ước tính tư thế' : 'Pose model'}
        <select
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value as PoseModel)}
          className="px-2.5 py-1.5 text-xs bg-white border border-slate-200 rounded-lg focus:outline-none focus:border-teal-600 disabled:opacity-50"
        >
          {OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{isVi ? o.vi : o.en}</option>
          ))}
        </select>
      </label>
      <p className="text-[11px] text-slate-500">{isVi ? current.hintVi : current.hintEn}</p>
    </div>
  )
}
