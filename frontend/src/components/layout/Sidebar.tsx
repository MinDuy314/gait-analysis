'use client'

import React from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { useLanguage } from '@/context/LanguageContext'
import {
  LayoutDashboard,
  Users,
  Activity,
  LineChart,
  FileText,
  PlayCircle,
  Building2,
  Settings,
  HelpCircle
} from 'lucide-react'

export function Sidebar() {
  const pathname = usePathname()
  const { user } = useAuth()
  const { t, locale } = useLanguage()

  const navItems = [
    {
      label: t('nav.dashboard'),
      href: '/dashboard',
      icon: LayoutDashboard,
    },
    {
      label: t('nav.subjects'),
      href: '/subjects',
      icon: Users,
    },
    {
      label: locale === 'vi' ? 'Tiến độ' : 'Progress',
      href: '/progress',
      icon: LineChart,
    },
    {
      label: t('reports.title'),
      href: '/reports',
      icon: FileText,
    },
  ]

  if (user?.role === 'administrator' || user?.role === 'professional') {
    navItems.push({
      label: locale === 'vi' ? 'Tổ chức & Nhóm' : 'Organization',
      href: '/organization',
      icon: Building2,
    })
  }

  return (
    <aside className="w-64 border-r border-slate-200 bg-slate-50/70 p-4 flex flex-col justify-between shrink-0 min-h-[calc(100vh-4rem)]">
      <div className="space-y-6">
        {/* Prominent Action Button */}
        <div>
          <Link
            href="/subjects"
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-teal-600 hover:bg-teal-700 text-white font-medium text-sm rounded-xl shadow-sm transition group"
          >
            <PlayCircle className="w-4 h-4 text-white group-hover:scale-105 transition-transform" />
            <span>{locale === 'vi' ? 'Bắt đầu đánh giá mới' : 'Start New Assessment'}</span>
          </Link>
        </div>

        {/* Main Nav */}
        <nav className="space-y-1">
          <div className="px-3 pb-2 text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
            {locale === 'vi' ? 'Menu chính' : 'Main Menu'}
          </div>
          {navItems.map((item) => {
            const Icon = item.icon
            const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`)
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition ${
                  isActive
                    ? 'bg-teal-50 text-teal-800 border-l-4 border-teal-600 font-semibold shadow-xs'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100/80'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-teal-700' : 'text-slate-500'}`} />
                <span>{item.label}</span>
              </Link>
            )
          })}
        </nav>
      </div>

      {/* Footer / Disclaimer */}
      <div className="pt-4 border-t border-slate-200 space-y-3">
        <div className="p-3 bg-amber-50/80 border border-amber-200/60 rounded-xl text-amber-900 text-xs">
          <p className="font-semibold flex items-center gap-1.5 mb-1 text-amber-800">
            <HelpCircle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
            <span>{locale === 'vi' ? 'Lưu ý y khoa' : 'Clinical Disclaimer'}</span>
          </p>
          <p className="text-[11px] text-amber-700 leading-relaxed">
            {locale === 'vi'
              ? 'Phân tích video 2D hỗ trợ định lượng, không thay thế chẩn đoán chuyên khoa lâm sàng.'
              : '2D video analysis provides biomechanical estimates, not replacement for clinical diagnosis.'}
          </p>
        </div>

        <div className="text-[11px] text-slate-400 px-1 text-center">
          YOLO Pose Gait Engine • v1.0.0
        </div>
      </div>
    </aside>
  )
}
