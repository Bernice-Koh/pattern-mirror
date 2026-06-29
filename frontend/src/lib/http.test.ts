import { describe, it, expect, afterEach, vi } from 'vitest'
import { apiFetch } from './http'
import { clearStoredAuth, getStoredAuth, setStoredAuth } from './auth-token'
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

function mockFetch(response: Response) {
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue(response)
}

describe('apiFetch', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    clearStoredAuth()
  })

  it('omits Authorization when no token is stored', async () => {
    const fetchSpy = mockFetch(new Response(null, { status: 200 }))

    await apiFetch('/documents', {
      headers: { 'Content-Type': 'application/json' },
    })

    expect(fetchSpy).toHaveBeenCalledWith(
      '/documents',
      expect.objectContaining({
        headers: { 'Content-Type': 'application/json' },
      }),
    )
  })

  it('attaches the bearer token when one is stored', async () => {
    setStoredAuth(AUTH)
    const fetchSpy = mockFetch(new Response(null, { status: 200 }))

    await apiFetch('/documents', {
      headers: { 'Content-Type': 'application/json' },
    })

    expect(fetchSpy).toHaveBeenCalledWith(
      '/documents',
      expect.objectContaining({
        headers: {
          'Content-Type': 'application/json',
          Authorization: 'Bearer tok-1',
        },
      }),
    )
  })

  it('clears the stored session on a 401', async () => {
    setStoredAuth(AUTH)
    mockFetch(new Response(null, { status: 401 }))

    await apiFetch('/documents')

    expect(getStoredAuth()).toBeNull()
  })
})
