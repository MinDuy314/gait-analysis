'use client'

import React, { useEffect, useState, use } from 'react'
import Link from 'next/link'
import { subjectsApi, sessionsApi } from '@/lib/api'
import { useLanguage } from '@/context/LanguageContext'
import type { Subject, Session } from '@/types/api'
import {
  Users,
  Calendar,
  PlayCircle,
  Plus,
  ArrowLeft,
  ArrowRight,
  Clock,
  Video,
  Activity,
  Layers
} from 'lucide-react'

export default function SubjectDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const resolvedParams = use(params)
  const id = resolvedParams.id
  const { t, locale } = useLanguage()

  const [subject, setSubject] = useState<Subject | null>(null)
  const [sessions, setSessions] = useState<Session[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([subjectsApi.get(id), sessionsApi.list(id)])
      .then(([sub, sessList]) => {
        setSubject(sub)
        setSessions(sessList.items || [])
      })
      .catch((err) => console.error(err))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) {
    return (
      <div className="p-12 text-center text-sm text-slate-400">
        <div className="w-6 h-6 border-2 border-teal-600 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
        <span>{t('common.loading')}</span>
      </div>
    )
  }

  if (!subject) {
    return (
      <div className="p-8 text-center space-y-4">
        <div className="text-slate-600 text-sm">Subject not found.</div>
        <Link href="/subjects" className="text-teal-600 text-xs font-semibold underline">
          Back to subjects
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Back button */}
      <Link
        href="/subjects"
        className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-teal-700 transition"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        <span>{locale === 'vi' ? 'Quay lại danh sách đối tượng' : 'Back to subjects'}</span>
      </Link>

      {/* Subject Header Card */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-0.5 rounded-full bg-teal-50 border border-teal-200 text-teal-800 text-[11px] font-semibold">
              {locale === 'vi' ? 'Hồ sơ đối tượng' : 'Subject Profile'}
            </span>
            <span className="text-xs text-slate-400 font-mono">ID: {subject.id}</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            {subject.display_name || (locale === 'vi' ? 'Chưa đặt tên' : 'Unnamed Subject')}
          </h1>
          <div className="text-xs text-slate-500 flex items-center gap-2">
            <Calendar className="w-3.5 h-3.5 text-slate-400" />
            <span>
              {locale === 'vi' ? 'Ngày khởi tạo:' : 'Created:'}{' '}
              {new Date(subject.created_at).toLocaleDateString(locale === 'vi' ? 'vi-VN' : 'en-US')}
            </span>
          </div>
        </div>

        <div className="flex flex-wrap gap-2.5">
          <Link
            href={`/progress?subject_id=${subject.id}`}
            className="flex items-center gap-2 px-4 py-2.5 bg-white border border-slate-200 hover:border-teal-500 text-slate-700 font-semibold text-xs rounded-xl shadow-xs transition"
          >
            <Activity className="w-4 h-4 text-teal-600" />
            <span>{locale === 'vi' ? 'Xem Tiến độ Dài hạn' : 'Longitudinal Progress'}</span>
          </Link>
          <Link
            href={`/subjects/${subject.id}/sessions/new`}
            className="flex items-center gap-2 px-4 py-2.5 bg-teal-600 hover:bg-teal-700 text-white font-semibold text-xs rounded-xl shadow-xs transition"
          >
            <Plus className="w-4 h-4" />
            <span>{locale === 'vi' ? 'Thêm phiên đánh giá mới' : 'New Assessment Session'}</span>
          </Link>
        </div>
      </div>

      {/* Sessions History List */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <Layers className="w-4 h-4 text-teal-600" />
            <span>{locale === 'vi' ? 'Lịch sử các phiên dáng đi' : 'Assessment Sessions'}</span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 font-semibold">
              {sessions.length}
            </span>
          </h2>
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden divide-y divide-slate-100">
          {sessions.length === 0 ? (
            <div className="p-12 text-center space-y-3">
              <Activity className="w-8 h-8 text-slate-300 mx-auto" />
              <div className="text-sm font-semibold text-slate-700">{t('sessions.noSessions')}</div>
              <p className="text-xs text-slate-500 max-w-sm mx-auto">
                {locale === 'vi'
                  ? 'Bắt đầu bằng cách tạo phiên đánh giá và tải lên video đi bộ của bệnh nhân.'
                  : 'Start by creating a session and uploading the walking recording.'}
              </p>
              <Link
                href={`/subjects/${subject.id}/sessions/new`}
                className="inline-flex items-center gap-1.5 px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white font-medium text-xs rounded-xl shadow-xs transition"
              >
                <Plus className="w-4 h-4" />
                <span>{locale === 'vi' ? 'Tạo phiên đầu tiên' : 'Create First Session'}</span>
              </Link>
            </div>
          ) : (
            sessions.map((sess, idx) => (
              <div
                key={sess.id}
                className="p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-slate-50/70 transition"
              >
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2.5">
                    <span className="font-semibold text-sm text-slate-900">
                      {locale === 'vi' ? `Phiên #${sessions.length - idx}` : `Session #${sessions.length - idx}`}
                    </span>
                    {sess.camera_view && (
                      <span className="px-2 py-0.5 rounded-md bg-teal-50 border border-teal-200 text-teal-800 text-[11px] font-medium capitalize">
                        {sess.camera_view} view
                      </span>
                    )}
                  </div>

                  <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3 text-slate-400" />
                      {new Date(sess.created_at).toLocaleString(locale === 'vi' ? 'vi-VN' : 'en-US')}
                    </span>
                    {sess.walking_speed_ms && (
                      <>
                        <span>•</span>
                        <span>{sess.walking_speed_ms} m/s</span>
                      </>
                    )}
                    {sess.walking_surface && (
                      <>
                        <span>•</span>
                        <span>{sess.walking_surface}</span>
                      </>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2 self-end sm:self-auto">
                  <Link
                    href={`/sessions/${sess.id}/upload`}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg transition"
                  >
                    <Video className="w-3.5 h-3.5 text-slate-600" />
                    <span>{locale === 'vi' ? 'Tải video' : 'Upload Video'}</span>
                  </Link>

                  <Link
                    href={`/sessions/${sess.id}/results`}
                    className="flex items-center gap-1.5 px-3.5 py-1.5 bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold rounded-lg transition shadow-xs"
                  >
                    <span>{locale === 'vi' ? 'Kết quả & Video' : 'Results & Video'}</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </Link>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
