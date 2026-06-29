import { describe, it, expect, afterEach } from 'vitest'
import {
  clearStoredAuth,
  getStoredAuth,
  getToken,
  setStoredAuth,
} from './auth-token'
import type { StoredAuth } from './auth-token'

const AUTH: StoredAuth = {
  token: 'tok-1',
  user: {
    id: 'u1',
    legalName: 'Alex Tan',
    initials: 'AT',
    email: 'alex.tan@example.com',
    role: 'manager',
  },
}

describe('auth-token', () => {
  afterEach(() => {
    clearStoredAuth()
  })

  it('round-trips stored auth and exposes the token', () => {
    setStoredAuth(AUTH)

    expect(getStoredAuth()).toEqual(AUTH)
    expect(getToken()).toBe('tok-1')
  })

  it('returns null when nothing is stored', () => {
    expect(getStoredAuth()).toBeNull()
    expect(getToken()).toBeNull()
  })

  it('returns null when the stored value is malformed', () => {
    localStorage.setItem('pm.auth', '{not valid json')

    expect(getStoredAuth()).toBeNull()
  })
})
