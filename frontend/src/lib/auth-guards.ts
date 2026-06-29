/** Route-guard logic for the router, kept here so it is unit-testable without standing up the
 *  whole route tree. Each guard throws a redirect (TanStack's beforeLoad contract) or returns. */

import { redirect } from '@tanstack/react-router'
import { getStoredAuth } from '@/lib/auth-token'
import type { UserRole } from '@/lib/auth-contract'

export const HOME: Record<UserRole, '/jd-studio' | '/hr-portal'> = {
  manager: '/jd-studio',
  hr: '/hr-portal',
}

/** Guard a role's surfaces: anonymous → that role's login; wrong role → their own home. */
export function requireRole(role: UserRole) {
  return () => {
    const auth = getStoredAuth()
    if (auth === null) {
      throw redirect({ to: role === 'hr' ? '/hr-login' : '/login' })
    }
    if (auth.user.role !== role) {
      throw redirect({ to: HOME[auth.user.role] })
    }
  }
}

/** On a login screen while already signed in: skip straight to the user's home. */
export function redirectIfAuthenticated() {
  const auth = getStoredAuth()
  if (auth !== null) {
    throw redirect({ to: HOME[auth.user.role] })
  }
}

/** Index route: send to the user's home, or to login when anonymous. */
export function indexRedirect(): never {
  const auth = getStoredAuth()
  throw redirect({ to: auth === null ? '/login' : HOME[auth.user.role] })
}
