'use client'

import React from 'react'
import Link from 'next/link'
import { useLanguage } from '@/context/LanguageContext'
import { FileText, ArrowRight, Layers } from 'lucide-react'

export default function GlobalReportsPage() {
  const { locale } = useLanguage()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
          <FileText className="w-6 h-6 text-teal-600" />
          <span>{locale === 'vi' ? 'Báo cáo Dáng đi' : 'Gait Reports'}</span>
        </h1>
        <p className="text-xs text-slate-500 mt-1">
          {locale === 'vi'
            ? 'Tổng hợp báo cáo định dạng chuẩn khoa học cho bệnh nhân và bác sĩ.'
            : 'Aggregated scientific reports for patient communication and clinical records.'}
        </p>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 p-8 shadow-xs text-center space-y-4">
        <div className="w-12 h-12 bg-teal-50 border border-teal-200 rounded-2xl flex items-center justify-center text-teal-600 mx-auto">
          <FileText className="w-6 h-6" />
        </div>
        <div className="space-y-1">
          <h3 className="text-base font-bold text-slate-900">
            {locale === 'vi' ? 'Tạo báo cáo từ phiên phân tích' : 'Generate Reports from Sessions'}
          </h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            {locale === 'vi'
              ? 'Mỗi phiên đánh giá sau khi hoàn tất sẽ có tùy chọn xuất Báo cáo Bệnh nhân hoặc Báo cáo Lâm sàng chuyên sâu.'
              : 'Every completed session results page includes generation options for Patient or Professional Clinical reports.'}
          </p>
        </div>

        <Link
          href="/subjects"
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-teal-600 hover:bg-teal-700 text-white font-semibold text-xs rounded-xl shadow-xs transition"
        >
          <span>{locale === 'vi' ? 'Đến danh sách đối tượng' : 'Go to Subjects'}</span>
          <ArrowRight className="w-4 h-4" />
        </Link>
      </div>
    </div>
  )
}
