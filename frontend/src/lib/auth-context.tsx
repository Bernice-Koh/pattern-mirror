/** AuthProvider: holds the cached user and wires login/logout into localStorage. The route
 *  guards read the token straight from localStorage; this drives the chrome that re-renders on
 *  sign-in and sign-out. The context and `useAuth` hook live in `use-auth.ts`. */

import { useState, type ReactNode } from 'react'
import { login as requestLogin } from '@/lib/auth-client'
import {
  clearStoredAuth,
  getStoredAuth,
  setStoredAuth,
  type StoredAuth,
} from '@/lib/auth-token'
import { AuthContext } from '@/lib/use-auth'
import type { AuthUser, LoginRequest } from '@/lib/auth-contract'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [auth, setAuth] = useState<StoredAuth | null>(() => getStoredAuth())

  const login = async (request: LoginRequest): Promise<AuthUser> => {
    const next = await requestLogin(request)
    setStoredAuth(next)
    setAuth(next)
    return next.user
  }

  const logout = (): void => {
    clearStoredAuth()
    setAuth(null)
  }

  return (
    <AuthContext.Provider value={{ user: auth?.user ?? null, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}
