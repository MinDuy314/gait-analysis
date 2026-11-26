import type { Metadata } from 'next'
import './globals.css'
import { Providers } from './providers'
import { AppLayout } from '@/components/layout/AppLayout'
import { SpeedInsights } from '@vercel/speed-insights/next'

export const metadata: Metadata = {
  title: 'Gait Analysis Platform | Hệ Thống Phân Tích Dáng Đi',
  description: 'Evidence-based biomechanical gait analysis with YOLO pose estimation & video annotation.',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="vi" className="h-full">
      <body className="h-full antialiased text-slate-800 bg-slate-50">
        <Providers>
          <AppLayout>{children}</AppLayout>
        </Providers>
        <SpeedInsights />
      </body>
    </html>
  )
}
