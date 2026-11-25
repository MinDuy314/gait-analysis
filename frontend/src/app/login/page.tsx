'use client'

import React, { useState } from 'react'
import Link from 'next/link'
import { useAuth } from '@/context/AuthContext'
import { useLanguage } from '@/context/LanguageContext'
import {
  Activity,
  Lock,
  User,
  AlertCircle,
  ArrowRight,
  Eye,
  EyeOff,
  Stethoscope,
  UserCheck,
  ShieldCheck
} from 'lucide-react'

export default function LoginPage() {
  const { login } = useAuth()
  const { t, locale } = useLanguage()

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
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

  // Pre-fill demo credentials
  const fillCredentials = (u: string, p: string) => {
    setUsername(u)
    setPassword(p)
    setError(null)
  }

  return (
    <div className="min-h-[calc(100vh-8rem)] flex items-center justify-center py-8 px-4 sm:px-6">
      <div className="w-full max-w-md space-y-6">
        {/* Main Login Card */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200/90 p-8 sm:p-9 space-y-6">
          {/* Header & Logo */}
          <div className="text-center space-y-3">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-teal-600 text-white shadow-sm ring-4 ring-teal-50">
              <Activity className="w-6 h-6 stroke-[2.2]" />
            </div>
            <div className="space-y-1">
              <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
                {t('auth.welcomeBack')}
              </h1>
              <p className="text-xs text-slate-500 max-w-xs mx-auto leading-relaxed">
                {t('auth.welcomeSubtitle')}
              </p>
            </div>
          </div>

          {/* Error Banner */}
          {error && (
            <div className="p-3.5 bg-red-50 border border-red-200 rounded-xl flex items-start gap-2.5 text-xs text-red-700 animate-in fade-in">
              <AlertCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
              <span className="leading-snug">{error}</span>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-700 block">
                {t('auth.username')}
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                  <User className="w-4 h-4" />
                </div>
                <input
                  type="text"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="dr_smith"
                  autoComplete="username"
                  className="w-full pl-10 pr-3.5 py-2.5 text-sm bg-slate-50 border border-slate-200 rounded-xl text-slate-900 placeholder:text-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-600 transition"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-700 block">
                {t('auth.password')}
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                  <Lock className="w-4 h-4" />
                </div>
                <input
                  type={showPassword ? 'text' : 'password'}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  autoComplete="current-password"
                  className="w-full pl-10 pr-10 py-2.5 text-sm bg-slate-50 border border-slate-200 rounded-xl text-slate-900 placeholder:text-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-600 transition"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-slate-600 transition"
                  title={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full mt-2 py-2.5 px-4 bg-teal-600 hover:bg-teal-700 active:bg-teal-800 text-white font-semibold text-sm rounded-xl shadow-xs transition flex items-center justify-center gap-2 disabled:opacity-50"
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

          {/* Footer Register Link */}
          <div className="pt-4 border-t border-slate-100 flex items-center justify-between text-xs text-slate-600">
            <span>{t('auth.noAccount')}</span>
            <Link
              href="/register"
              className="font-semibold text-teal-600 hover:text-teal-700 hover:underline transition"
            >
              {t('auth.registerButton')}
            </Link>
          </div>
        </div>

        {/* Demo Accounts Card - Clearly Separated */}
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs space-y-3">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-700">
            <ShieldCheck className="w-4 h-4 text-teal-600" />
            <span>
              {locale === 'vi' ? 'Tài khoản mẫu dùng thử (One-click fill):' : 'Configured Demo Credentials (One-click fill):'}
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            <button
              type="button"
              onClick={() => fillCredentials('dr_smith', 'Clinician@123')}
              className="p-3 text-left rounded-xl border border-slate-200 bg-slate-50/70 hover:bg-teal-50/60 hover:border-teal-300 transition group"
            >
              <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800 group-hover:text-teal-800">
                <Stethoscope className="w-3.5 h-3.5 text-teal-600" />
                <span>Dr. Smith</span>
              </div>
              <div className="text-[11px] text-slate-500 font-mono mt-0.5">
                dr_smith • Clinician
              </div>
            </button>

            <button
              type="button"
              onClick={() => fillCredentials('patient_john', 'Patient@123')}
              className="p-3 text-left rounded-xl border border-slate-200 bg-slate-50/70 hover:bg-teal-50/60 hover:border-teal-300 transition group"
            >
              <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800 group-hover:text-teal-800">
                <UserCheck className="w-3.5 h-3.5 text-teal-600" />
                <span>John Doe</span>
              </div>
              <div className="text-[11px] text-slate-500 font-mono mt-0.5">
                patient_john • Patient
              </div>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
