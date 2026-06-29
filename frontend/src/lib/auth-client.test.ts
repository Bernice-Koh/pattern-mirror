import { describe, it, expect, afterEach, vi } from 'vitest'
import { login } from './auth-client'
import { clearStoredAuth } from './auth-token'
import type { LoginResponseBody } from './auth-contract'

const BODY: LoginResponseBody = {
  token: 'tok-1',
  user: {
    id: 'u1',
    legal_name: 'Alex Tan',
    initials: 'AT',
    email: 'alex.tan@example.com',
    role: 'manager',
  },
}

function mockFetch(response: Response) {
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue(response)
}

describe('login', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    clearStoredAuth()
  })

  it('POSTs email, password and expected_role, and maps the response to camelCase', async () => {
    const fetchSpy = mockFetch(
      new Response(JSON.stringify(BODY), { status: 200 }),
    )

    const result = await login({
      email: 'alex.tan@example.com',
      password: 'anything',
      expectedRole: 'manager',
    })

    expect(fetchSpy).toHaveBeenCalledWith(
      '/auth/login',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          email: 'alex.tan@example.com',
          password: 'anything',
          expected_role: 'manager',
        }),
      }),
    )
    expect(result).toEqual({
      token: 'tok-1',
      user: {
        id: 'u1',
        legalName: 'Alex Tan',
        initials: 'AT',
        email: 'alex.tan@example.com',
        role: 'manager',
      },
    })
  })

  it('throws LoginError carrying the status on a 401', async () => {
    mockFetch(new Response(null, { status: 401 }))

    await expect(
      login({ email: 'nobody@example.com', password: 'x', expectedRole: 'hr' }),
    ).rejects.toMatchObject({ name: 'LoginError', status: 401 })
  })
})
