'use client'

import React, { useEffect, useState } from 'react'
import Link from 'next/link'
import { subjectsApi } from '@/lib/api'
import { useLanguage } from '@/context/LanguageContext'
import type { Subject } from '@/types/api'
import { Users, Plus, Search, Clock, Trash2, ArrowRight, UserPlus, X } from 'lucide-react'

export default function SubjectsPage() {
  const { t, locale } = useLanguage()
  const [subjects, setSubjects] = useState<Subject[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [displayName, setDisplayName] = useState('')
  const [isCreating, setIsCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadSubjects = () => {
    setLoading(true)
    subjectsApi
      .list(0, 50)
      .then((res) => setSubjects(res.items || []))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadSubjects()
  }, [])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsCreating(true)
    setError(null)
    try {
      await subjectsApi.create(displayName.trim() || undefined)
      setDisplayName('')
      setShowModal(false)
      loadSubjects()
    } catch (err: any) {
      setError(err.response?.data?.detail || t('common.error'))
    } finally {
      setIsCreating(false)
    }
  }

  const handleDelete = async (id: string, name?: string) => {
    if (!confirm(t('subjects.confirmDelete'))) return
    try {
      await subjectsApi.delete(id)
      setSubjects((prev) => prev.filter((s) => s.id !== id))
    } catch (err) {
      alert(t('common.error'))
    }
  }

  const filtered = subjects.filter((s) =>
    (s.display_name || s.id).toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
            <Users className="w-6 h-6 text-teal-600" />
            <span>{t('subjects.title')}</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            {locale === 'vi'
              ? 'Quản lý danh sách bệnh nhân và đối tượng theo dõi dáng đi'
              : 'Manage patient cohort and gait tracking profiles'}
          </p>
        </div>

        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-2 px-4 py-2.5 bg-teal-600 hover:bg-teal-700 text-white font-semibold text-xs rounded-xl shadow-xs transition"
        >
          <UserPlus className="w-4 h-4" />
          <span>{t('subjects.new')}</span>
        </button>
      </div>

      {/* Search and Filters */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={locale === 'vi' ? 'Tìm theo tên hoặc ID...' : 'Search by name or ID...'}
            className="w-full pl-9 pr-3 py-2 text-xs bg-white border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-600 transition"
          />
        </div>
      </div>

      {/* Subjects Grid / List */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden divide-y divide-slate-100">
        {loading ? (
          <div className="p-12 text-center text-sm text-slate-400">
            <div className="w-6 h-6 border-2 border-teal-600 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
            <span>{t('common.loading')}</span>
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-12 text-center space-y-3">
            <Users className="w-8 h-8 text-slate-300 mx-auto" />
            <div className="text-sm font-semibold text-slate-700">{t('subjects.noSubjects')}</div>
            <button
              onClick={() => setShowModal(true)}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white font-medium text-xs rounded-xl shadow-xs transition"
            >
              <Plus className="w-4 h-4" />
              <span>{t('subjects.new')}</span>
            </button>
          </div>
        ) : (
          filtered.map((sub) => (
            <div
              key={sub.id}
              className="p-4 sm:px-6 flex items-center justify-between hover:bg-slate-50/70 transition"
            >
              <Link href={`/subjects/${sub.id}`} className="flex-1 space-y-1">
                <div className="font-semibold text-sm text-slate-900 hover:text-teal-700 transition">
                  {sub.display_name || (locale === 'vi' ? 'Đối tượng chưa đặt tên' : 'Unnamed Subject')}
                </div>
                <div className="flex items-center gap-3 text-xs text-slate-400">
                  <span className="font-mono text-[11px] text-slate-400">ID: {sub.id}</span>
                  <span>•</span>
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {new Date(sub.created_at).toLocaleDateString(locale === 'vi' ? 'vi-VN' : 'en-US')}
                  </span>
                </div>
              </Link>

              <div className="flex items-center gap-3">
                <Link
                  href={`/subjects/${sub.id}`}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 hover:bg-teal-50 hover:text-teal-700 text-slate-700 text-xs font-semibold rounded-lg transition"
                >
                  <span>{locale === 'vi' ? 'Xem phiên' : 'Sessions'}</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>

                <button
                  onClick={() => handleDelete(sub.id, sub.display_name)}
                  className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition"
                  title={t('subjects.delete')}
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Create Subject Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl border border-slate-200 space-y-5 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-slate-900">{t('subjects.new')}</h3>
              <button
                onClick={() => setShowModal(false)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {error && (
              <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-xl">
                {error}
              </div>
            )}

            <form onSubmit={handleCreate} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-700 block">
                  {t('subjects.name')}
                </label>
                <input
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder={t('subjects.namePlaceholder')}
                  autoFocus
                  className="w-full px-3.5 py-2 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:bg-white focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-600 transition"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-xl transition"
                >
                  {t('common.cancel')}
                </button>
                <button
                  type="submit"
                  disabled={isCreating}
                  className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white font-semibold text-xs rounded-xl shadow-xs transition disabled:opacity-50"
                >
                  {isCreating ? t('common.loading') : t('common.save')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
