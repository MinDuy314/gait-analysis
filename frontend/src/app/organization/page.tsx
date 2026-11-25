'use client'

import React from 'react'
import Link from 'next/link'
import { useAuth } from '@/context/AuthContext'
import { useLanguage } from '@/context/LanguageContext'
import { Building2, Users, ShieldCheck, Mail, Plus, ArrowRight } from 'lucide-react'

export default function OrganizationPage() {
  const { user, organization, setOrganization } = useAuth()
  const { locale } = useLanguage()

  const members = [
    { name: user?.username || 'Dr. Duy', role: user?.role || 'administrator', email: user?.email || 'admin@clinic.org' },
    { name: 'Dr. Sarah Smith', role: 'professional', email: 'sarah.smith@biomech.org' },
    { name: 'Nguyen Van A (Patient)', role: 'individual', email: 'patient.a@example.com' },
  ]

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
            <Building2 className="w-6 h-6 text-teal-600" />
            <span>{locale === 'vi' ? 'Quản lý Tổ chức & Phòng khám' : 'Organization & Clinic Management'}</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            {locale === 'vi'
              ? 'Phân quyền ranh giới dữ liệu bệnh nhân và quản lý thành viên chuyên môn.'
              : 'RBAC boundaries, clinician assignments, and patient data privacy scopes.'}
          </p>
        </div>

        <button
          onClick={() => {
            const orgName = prompt(locale === 'vi' ? 'Tên phòng khám / tổ chức:' : 'Organization Name:', organization || '')
            if (orgName) setOrganization(orgName)
          }}
          className="flex items-center gap-2 px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white font-semibold text-xs rounded-xl shadow-xs transition"
        >
          <Plus className="w-4 h-4" />
          <span>{locale === 'vi' ? 'Đổi đơn vị' : 'Update Organization'}</span>
        </button>
      </div>

      {/* Organization Header */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs flex items-center justify-between">
        <div className="space-y-1">
          <span className="text-[11px] font-semibold text-teal-700 uppercase tracking-wider block">
            {locale === 'vi' ? 'Đơn vị hiện hành' : 'Active Organization'}
          </span>
          <div className="text-xl font-bold text-slate-900">
            {organization || (locale === 'vi' ? 'Phòng khám Cơ sinh học & Phục hồi' : 'National Biomechanics Center')}
          </div>
          <div className="text-xs text-slate-500">
            RBAC Domain Isolation: <span className="font-mono text-teal-700 font-semibold">Strict Patient Data Boundary</span>
          </div>
        </div>

        <div className="w-12 h-12 rounded-2xl bg-teal-50 border border-teal-200 flex items-center justify-center text-teal-700 font-bold text-lg">
          ORG
        </div>
      </div>

      {/* Members List */}
      <div className="space-y-3">
        <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
          <Users className="w-4 h-4 text-teal-600" />
          <span>{locale === 'vi' ? 'Thành viên được cấp quyền truy cập' : 'Authorized Team Members'}</span>
        </h2>

        <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden divide-y divide-slate-100">
          {members.map((m, idx) => (
            <div key={idx} className="p-4 sm:px-6 flex items-center justify-between hover:bg-slate-50 transition text-xs">
              <div className="space-y-1">
                <div className="font-semibold text-slate-900 text-sm">{m.name}</div>
                <div className="text-slate-400 flex items-center gap-2">
                  <Mail className="w-3.5 h-3.5" />
                  <span>{m.email}</span>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <span className="px-2.5 py-1 rounded-full bg-slate-100 text-slate-700 font-semibold text-[11px] capitalize">
                  {m.role}
                </span>
                <span className="text-emerald-600 font-medium text-[11px] flex items-center gap-1">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  Active
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
