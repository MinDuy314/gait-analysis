'use client'

import React, { createContext, useContext, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { authApi } from '@/lib/api'
import type { User } from '@/types/api'

interface AuthContextType {
  user: User | null
  token: string | null
  organization: string | null
  setOrganization: (org: string | null) => void
  isLoading: boolean
  login: (username: string, password: string) => Promise<void>
  register: (data: { username: string; email?: string; password: string; role: string; organization?: string }) => Promise<void>
  logout: () => void
  hasRole: (roles: string[]) => boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [organization, setOrganizationState] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const router = useRouter()

  useEffect(() => {
    const savedToken = localStorage.getItem('access_token')
    const savedUser = localStorage.getItem('user_data')
    const savedOrg = localStorage.getItem('active_org')

    if (savedToken && savedUser) {
      try {
        setToken(savedToken)
        setUser(JSON.parse(savedUser))
        setOrganizationState(savedOrg || null)
      } catch {
        localStorage.removeItem('access_token')
        localStorage.removeItem('user_data')
        localStorage.removeItem('active_org')
      }
    }
    setIsLoading(false)
  }, [])

  const setOrganization = (org: string | null) => {
    setOrganizationState(org)
    if (org) {
      localStorage.setItem('active_org', org)
    } else {
      localStorage.removeItem('active_org')
    }
  }

  const login = async (username: string, password: string) => {
    const res = await authApi.login(username, password)
    localStorage.setItem('access_token', res.access_token)
    setToken(res.access_token)

    // Fetch user profile
    const profile = await authApi.me()
    setUser(profile)
    localStorage.setItem('user_data', JSON.stringify(profile))

    // Default org from username or role if organization account
    if (profile.role === 'administrator') {
      const defaultOrg = 'National Biomechanics & Rehab Center'
      setOrganization(defaultOrg)
    }

    router.push('/dashboard')
  }

  const register = async (data: { username: string; email?: string; password: string; role: string; organization?: string }) => {
    const res = await authApi.register({
      username: data.username,
      email: data.email,
      password: data.password,
      role: data.role,
    })
    localStorage.setItem('access_token', res.access_token)
    setToken(res.access_token)

    if (data.organization) {
      setOrganization(data.organization)
    }

    const profile = await authApi.me()
    setUser(profile)
    localStorage.setItem('user_data', JSON.stringify(profile))

    router.push('/dashboard')
  }

  const logout = () => {
    try {
      authApi.logout()
    } catch {
      // ignore network errors on logout
    }
    localStorage.removeItem('access_token')
    localStorage.removeItem('user_data')
    localStorage.removeItem('active_org')
    setToken(null)
    setUser(null)
    setOrganizationState(null)
    router.push('/login')
  }

  const hasRole = (roles: string[]) => {
    if (!user) return false
    return roles.includes(user.role)
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        organization,
        setOrganization,
        isLoading,
        login,
        register,
        logout,
        hasRole,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
