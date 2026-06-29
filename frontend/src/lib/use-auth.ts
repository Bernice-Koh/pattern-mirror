/** The auth context and its hook, kept apart from the provider component so each file has a
 *  single export kind (fast-refresh friendly). */

import { createContext, useContext } from 'react'
import type { AuthUser, LoginRequest } from '@/lib/auth-contract'

export interface AuthContextValue {
  user: AuthUser | null
  login: (request: LoginRequest) => Promise<AuthUser>
  logout: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (context === null) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
