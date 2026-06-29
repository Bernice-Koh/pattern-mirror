import { describe, it, expect, afterEach, vi } from 'vitest'
import {
  HOME,
  indexRedirect,
  redirectIfAuthenticated,
  requireRole,
} from './auth-guards'
import { clearStoredAuth, setStoredAuth } from './auth-token'
import type { StoredAuth } from './auth-token'
import type { UserRole } from './auth-contract'

// redirect() throws in the app; here we only need its target, so stub it to return its argument.
vi.mock('@tanstack/react-router', () => ({
  redirect: (options: { to: string }) => options,
}))

function authAs(role: UserRole): StoredAuth {
  return {
    token: 't',
    user: { id: 'u', legalName: 'N', initials: 'N', email: 'e', role },
  }
}

function thrownBy(guard: () => void): { to: string } | null {
  try {
    guard()
    return null
  } catch (target) {
    return target as { to: string }
  }
}

describe('auth guards', () => {
  afterEach(() => {
    clearStoredAuth()
  })

  it('sends an anonymous manager visitor to /login', () => {
    expect(thrownBy(requireRole('manager'))).toEqual({ to: '/login' })
  })

  it('sends an anonymous HR visitor to /hr-login', () => {
    expect(thrownBy(requireRole('hr'))).toEqual({ to: '/hr-login' })
  })

  it('sends a mismatched role to their own home', () => {
    setStoredAuth(authAs('hr'))
    expect(thrownBy(requireRole('manager'))).toEqual({ to: HOME.hr })
  })

  it('lets a matching role through', () => {
    setStoredAuth(authAs('manager'))
    expect(thrownBy(requireRole('manager'))).toBeNull()
  })

  it('lets an anonymous visitor reach a login screen', () => {
    expect(thrownBy(redirectIfAuthenticated)).toBeNull()
  })

  it('skips a signed-in user away from a login screen', () => {
    setStoredAuth(authAs('hr'))
    expect(thrownBy(redirectIfAuthenticated)).toEqual({ to: '/hr-portal' })
  })

  it('routes the index to /login when anonymous', () => {
    expect(thrownBy(indexRedirect)).toEqual({ to: '/login' })
  })

  it('routes the index to the user home when signed in', () => {
    setStoredAuth(authAs('manager'))
    expect(thrownBy(indexRedirect)).toEqual({ to: '/jd-studio' })
  })
})
