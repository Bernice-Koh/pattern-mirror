/** The session token and cached user in localStorage, so a refresh keeps the user signed in.
 *  The role here is a routing hint for the guards; the server still verifies the token. */

import type { AuthUser } from '@/lib/auth-contract'

const STORAGE_KEY = 'pm.auth'

export interface StoredAuth {
  token: string
  user: AuthUser
}

export function getStoredAuth(): StoredAuth | null {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as StoredAuth
  } catch {
    return null
  }
}

export function setStoredAuth(auth: StoredAuth): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(auth))
}

export function clearStoredAuth(): void {
  localStorage.removeItem(STORAGE_KEY)
}

export function getToken(): string | null {
  return getStoredAuth()?.token ?? null
}
