/** Client for POST /auth/login: exchanges email + role for a signed token and the user to
 *  cache. The password is sent but cosmetic; an unknown email or role mismatch returns 401. */

import { apiFetch } from '@/lib/http'
import type { LoginRequest, LoginResponseBody } from '@/lib/auth-contract'
import type { StoredAuth } from '@/lib/auth-token'

/** A non-OK response from /auth/login. Status 401 means wrong credentials. */
export class LoginError extends Error {
  readonly status: number

  constructor(status: number) {
    super(`Login failed with status ${status}`)
    this.name = 'LoginError'
    this.status = status
  }
}

/** Log in and return the token + camelCase user to store. Throws LoginError on failure. */
export async function login(request: LoginRequest): Promise<StoredAuth> {
  const response = await apiFetch('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email: request.email,
      password: request.password,
      expected_role: request.expectedRole,
    }),
  })
  if (!response.ok) throw new LoginError(response.status)

  const body = (await response.json()) as LoginResponseBody
  return {
    token: body.token,
    user: {
      id: body.user.id,
      legalName: body.user.legal_name,
      initials: body.user.initials,
      email: body.user.email,
      role: body.user.role,
    },
  }
}
