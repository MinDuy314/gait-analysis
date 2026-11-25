'use client'

import React, { useState } from 'react'
import Link from 'next/link'
import { useAuth } from '@/context/AuthContext'
import { useLanguage } from '@/context/LanguageContext'
import { Activity, Lock, User, AlertCircle, ArrowRight } from 'lucide-react'

export default function LoginPage() {
  const { login } = useAuth()
  const { t, locale } = useLanguage()

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      await login(username, password)
    } catch (err: any) {
      if (err.response?.status === 401) {
        setError(t('auth.invalidCredentials'))
      } else {
        setError(err.response?.data?.detail || t('common.error'))
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  // Quick fill helper for testing/evaluating
  const fillCredentials = (u: string, p: string) => {
    setUsername(u)
    setPassword(p)
  }

  return (
    <div className="max-w-md mx-auto py-12 px-4 sm:px-6">
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200/80 p-8 space-y-6">
        <div className="text-center space-y-2">
          <div className="w-12 h-12 bg-teal-50 border border-teal-200 rounded-xl mx-auto flex items-center justify-center text-teal-600 shadow-xs">
            <Activity className="w-6 h-6" />
          </div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">
            {t('auth.loginTitle')}
          </h1>
          <p className="text-xs text-slate-500">
            {locale === 'vi'
              ? 'Nền tảng phân tích chuyển động & dáng đi chuẩn lâm sàng'
              : 'Clinical-grade gait & biomechanical movement analysis platform'}
          </p>
        </div>

        {error && (
          <div className="p-3.5 bg-red-50 border border-red-200 rounded-xl flex items-start gap-2.5 text-xs text-red-700">
            <AlertCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-700 block">
              {t('auth.username')}
            </label>
            <div className="relative">
              <User className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="clinician_duy"
                className="w-full pl-9 pr-3 py-2 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:bg-white focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-600 transition"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-700 block">
              {t('auth.password')}
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full pl-9 pr-3 py-2 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:bg-white focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-600 transition"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full py-2.5 px-4 bg-teal-600 hover:bg-teal-700 text-white font-semibold text-sm rounded-xl shadow-xs transition flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {isSubmitting ? (
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : (
              <>
                <span>{t('auth.loginButton')}</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </form>

        <div className="pt-4 border-t border-slate-100 flex items-center justify-between text-xs text-slate-600">
          <span>{t('auth.noAccount')}</span>
          <Link href="/register" className="font-semibold text-teal-600 hover:text-teal-700">
            {t('auth.registerButton')}
          </Link>
        </div>

        {/* Demo Account Presets */}
        <div className="p-3 bg-slate-50 border border-slate-200/60 rounded-xl space-y-2">
          <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">
            {locale === 'vi' ? 'Tài khoản mẫu thử nghiệm:' : 'Demo / Quick Test Credentials:'}
          </span>
          <div className="flex flex-wrap gap-1.5">
            <button
              type="button"
              onClick={() => fillCredentials('dr_smith', 'Clinician@123')}
              className="text-[11px] px-2.5 py-1 bg-white border border-slate-200 rounded-lg text-slate-700 hover:border-teal-500 transition"
            >
              Dr. Smith (Clinician)
            </button>
            <button
              type="button"
              onClick={() => fillCredentials('patient_john', 'Patient@123')}
              className="text-[11px] px-2.5 py-1 bg-white border border-slate-200 rounded-lg text-slate-700 hover:border-teal-500 transition"
            >
              John (Patient)
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
