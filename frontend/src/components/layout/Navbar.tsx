'use client'

import React from 'react'
import Link from 'next/link'
import { useAuth } from '@/context/AuthContext'
import { useLanguage } from '@/context/LanguageContext'
import { Globe, User, LogOut, Building, ShieldCheck } from 'lucide-react'

export function Navbar() {
  const { user, organization, logout } = useAuth()
  const { locale, setLocale, t } = useLanguage()

  const toggleLocale = () => {
    setLocale(locale === 'vi' ? 'en' : 'vi')
  }

  const roleLabels: Record<string, string> = {
    administrator: locale === 'vi' ? 'Quản trị viên' : 'Administrator',
    professional: locale === 'vi' ? 'Bác sĩ / Chuyên gia' : 'Clinician',
    individual: locale === 'vi' ? 'Bệnh nhân' : 'Patient',
  }

  return (
    <header className="h-16 border-b border-slate-200 bg-white/95 backdrop-blur px-6 flex items-center justify-between sticky top-0 z-30 shadow-xs">
      <div className="flex items-center gap-3">
        <Link href="/dashboard" className="flex items-center gap-2 group">
          <div className="w-9 h-9 rounded-lg bg-teal-600 flex items-center justify-center text-white font-bold text-lg shadow-sm group-hover:bg-teal-700 transition">
            G
          </div>
          <div>
            <span className="font-semibold text-slate-900 tracking-tight text-base">Gait Analysis</span>
            <span className="text-xs text-teal-600 font-medium block">Biomechanics Platform</span>
          </div>
        </Link>

        {organization && (
          <div className="hidden md:flex items-center gap-1.5 ml-4 px-3 py-1 bg-slate-50 border border-slate-200 rounded-full text-xs text-slate-600 font-medium">
            <Building className="w-3.5 h-3.5 text-teal-600" />
            <span className="truncate max-w-[200px]">{organization}</span>
          </div>
        )}
      </div>

      <div className="flex items-center gap-3">
        {/* Language switch */}
        <button
          onClick={toggleLocale}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 text-xs font-medium text-slate-700 hover:bg-slate-50 transition"
          title="Switch Language"
        >
          <Globe className="w-3.5 h-3.5 text-teal-600" />
          <span>{locale === 'vi' ? 'Tiếng Việt' : 'English'}</span>
          <span className="text-[10px] text-slate-400 font-bold uppercase ml-0.5">({locale === 'vi' ? 'VI' : 'EN'})</span>
        </button>

        {user ? (
          <div className="flex items-center gap-3 pl-2 border-l border-slate-200">
            <div className="hidden sm:flex flex-col text-right">
              <span className="text-xs font-semibold text-slate-900">{user.username}</span>
              <span className="text-[11px] text-teal-700 flex items-center justify-end gap-1 font-medium">
                <ShieldCheck className="w-3 h-3 text-teal-600" />
                {roleLabels[user.role] || user.role}
              </span>
            </div>

            <div className="w-8 h-8 rounded-full bg-slate-100 border border-slate-300 flex items-center justify-center text-slate-700">
              <User className="w-4 h-4" />
            </div>

            <button
              onClick={logout}
              className="p-1.5 text-slate-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition"
              title={t('nav.logout')}
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <Link
              href="/login"
              className="px-3.5 py-1.5 text-xs font-medium text-slate-700 hover:text-teal-700 transition"
            >
              {t('nav.login')}
            </Link>
            <Link
              href="/register"
              className="px-3.5 py-1.5 text-xs font-medium bg-teal-600 text-white rounded-lg hover:bg-teal-700 transition shadow-xs"
            >
              {t('nav.register')}
            </Link>
          </div>
        )}
      </div>
    </header>
  )
}
