'use client'

import React, { useState, useCallback, use } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useDropzone } from 'react-dropzone'
import { recordingsApi, sessionsApi } from '@/lib/api'
import { useLanguage } from '@/context/LanguageContext'
import {
  UploadCloud,
  FileVideo,
  CheckCircle2,
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  ShieldAlert,
  X
} from 'lucide-react'

export default function SessionUploadPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const resolvedParams = use(params)
  const sessionId = resolvedParams.id
  const router = useRouter()
  const { t, locale } = useLanguage()

  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploadProgress, setUploadProgress] = useState<number>(0)
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      const file = acceptedFiles[0]
      // Max 200MB check
      if (file.size > 200 * 1024 * 1024) {
        setError(locale === 'vi' ? 'Tệp video vượt quá giới hạn 200MB' : 'Video file exceeds 200MB limit')
        return
      }
      setSelectedFile(file)
      setError(null)
    }
  }, [locale])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'video/*': ['.mp4', '.mov', '.avi', '.webm'],
    },
    maxFiles: 1,
    disabled: isUploading,
  })

  const handleUpload = async () => {
    if (!selectedFile) return
    setIsUploading(true)
    setError(null)

    try {
      const rec = await recordingsApi.upload(sessionId, selectedFile, (pct) => {
        setUploadProgress(pct)
      })

      // Upload completed -> proceed to confirm camera view
      router.push(`/sessions/${sessionId}/confirm-view?recording_id=${rec.id}`)
    } catch (err: any) {
      setError(err.response?.data?.detail || t('upload.error'))
      setIsUploading(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <Link
        href="/subjects"
        className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-teal-700 transition"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        <span>{locale === 'vi' ? 'Hủy và quay lại' : 'Cancel & return'}</span>
      </Link>

      <div className="bg-white rounded-2xl border border-slate-200 p-6 sm:p-8 shadow-xs space-y-6">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="w-6 h-6 rounded-full bg-teal-100 text-teal-800 font-bold flex items-center justify-center text-xs">
              2
            </span>
            <span className="text-xs font-semibold text-teal-700 uppercase tracking-wider">
              {locale === 'vi' ? 'Bước 2 / 4: Tải lên video' : 'Step 2 / 4: Video Upload'}
            </span>
          </div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">
            {t('upload.title')}
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            {locale === 'vi'
              ? 'Tải lên video người đi bộ tự nhiên để trích xuất khung xương và đo lường thông số dáng đi.'
              : 'Upload walking recording for skeleton extraction and biomechanical measurement.'}
          </p>
        </div>

        {error && (
          <div className="p-3.5 bg-red-50 border border-red-200 rounded-xl flex items-start gap-2.5 text-xs text-red-700">
            <AlertCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {/* Dropzone Container */}
        {!selectedFile ? (
          <div
            {...getRootProps()}
            className={`border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition flex flex-col items-center justify-center gap-4 ${
              isDragActive
                ? 'border-teal-500 bg-teal-50/50 scale-[1.01]'
                : 'border-slate-300 hover:border-teal-500 hover:bg-slate-50/70 bg-slate-50/40'
            }`}
          >
            <input {...getInputProps()} />
            <div className="w-14 h-14 rounded-2xl bg-teal-50 border border-teal-100 flex items-center justify-center text-teal-600 shadow-xs">
              <UploadCloud className="w-7 h-7" />
            </div>

            <div className="space-y-1">
              <div className="text-sm font-semibold text-slate-800">
                {isDragActive
                  ? locale === 'vi'
                    ? 'Thả video vào đây...'
                    : 'Drop video here...'
                  : t('upload.dropzone')}
              </div>
              <div className="text-xs text-slate-500">{t('upload.accepted')} (Tối đa 200MB)</div>
            </div>

            <button
              type="button"
              className="px-4 py-2 bg-white border border-slate-200 text-slate-700 text-xs font-semibold rounded-xl shadow-xs hover:border-teal-600 hover:text-teal-700 transition"
            >
              {locale === 'vi' ? 'Chọn tệp từ máy tính' : 'Browse Local Files'}
            </button>
          </div>
        ) : (
          <div className="bg-slate-50 rounded-2xl border border-slate-200 p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-teal-100 text-teal-700 flex items-center justify-center">
                  <FileVideo className="w-5 h-5" />
                </div>
                <div>
                  <div className="font-semibold text-sm text-slate-900 truncate max-w-xs sm:max-w-md">
                    {selectedFile.name}
                  </div>
                  <div className="text-xs text-slate-500">
                    {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB • {selectedFile.type || 'video'}
                  </div>
                </div>
              </div>

              {!isUploading && (
                <button
                  type="button"
                  onClick={() => setSelectedFile(null)}
                  className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>

            {/* Progress bar */}
            {isUploading && (
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-xs text-slate-600 font-semibold">
                  <span>{t('upload.uploading')}</span>
                  <span>{uploadProgress}%</span>
                </div>
                <div className="w-full h-2 bg-slate-200 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-teal-600 transition-all duration-300"
                    style={{ width: `${uploadProgress}%` }}
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {/* Security & Validation Notice */}
        <div className="p-4 bg-sky-50/70 border border-sky-200/60 rounded-xl text-sky-900 text-xs flex items-start gap-3">
          <ShieldAlert className="w-4 h-4 text-sky-600 shrink-0 mt-0.5" />
          <div className="space-y-1 leading-relaxed">
            <span className="font-semibold block">
              {locale === 'vi' ? 'Bảo mật & Quyền riêng tư dữ liệu:' : 'Privacy & Security Standard:'}
            </span>
            <p className="text-[11px] text-sky-800">
              {locale === 'vi'
                ? 'Video được lưu trữ riêng biệt trong không gian phiên bảo mật. Không công khai ra bên ngoài.'
                : 'Recordings are strictly isolated in protected session storage and never exposed publicly.'}
            </p>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={handleUpload}
            disabled={!selectedFile || isUploading}
            className="flex items-center gap-2 px-6 py-2.5 bg-teal-600 hover:bg-teal-700 text-white font-semibold text-xs rounded-xl shadow-xs transition disabled:opacity-50"
          >
            {isUploading ? (
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : (
              <>
                <span>{locale === 'vi' ? 'Tải lên & Tiếp tục' : 'Upload & Proceed'}</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
