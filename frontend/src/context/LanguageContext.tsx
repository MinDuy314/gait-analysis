'use client'

import React, { createContext, useContext, useEffect, useState } from 'react'
import en from '@/i18n/en.json'
import vi from '@/i18n/vi.json'

type Locale = 'en' | 'vi'

const translations: Record<Locale, any> = { en, vi }

interface LanguageContextType {
  locale: Locale
  setLocale: (l: Locale) => void
  t: (keyPath: string) => string
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined)

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>('vi') // Default to Vietnamese for local accessibility

  useEffect(() => {
    const saved = localStorage.getItem('app_locale') as Locale
    if (saved && (saved === 'en' || saved === 'vi')) {
      setLocaleState(saved)
    }
  }, [])

  const setLocale = (newLocale: Locale) => {
    setLocaleState(newLocale)
    localStorage.setItem('app_locale', newLocale)
  }

  const t = (keyPath: string): string => {
    const parts = keyPath.split('.')
    let current = translations[locale]
    for (const part of parts) {
      if (current && typeof current === 'object' && part in current) {
        current = current[part]
      } else {
        // Fallback to English
        let fallback = translations['en']
        for (const fPart of parts) {
          if (fallback && typeof fallback === 'object' && fPart in fallback) {
            fallback = fallback[fPart]
          } else {
            return keyPath
          }
        }
        return typeof fallback === 'string' ? fallback : keyPath
      }
    }
    return typeof current === 'string' ? current : keyPath
  }

  return (
    <LanguageContext.Provider value={{ locale, setLocale, t }}>
      {children}
    </LanguageContext.Provider>
  )
}

export function useLanguage() {
  const context = useContext(LanguageContext)
  if (!context) {
    throw new Error('useLanguage must be used within LanguageProvider')
  }
  return context
}
