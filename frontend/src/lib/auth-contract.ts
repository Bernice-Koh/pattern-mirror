/** Types for the mock-auth boundary: the login request, the backend response shape, and the
 *  camelCase user the app caches. Mock only — the password is cosmetic. */

export type UserRole = 'manager' | 'hr'

/** The signed-in user, as stored client-side and shown in the chrome. */
export interface AuthUser {
  id: string
  legalName: string
  initials: string
  email: string
  role: UserRole
}

/** A login attempt; `expectedRole` is the portal the screen is for. */
export interface LoginRequest {
  email: string
  password: string
  expectedRole: UserRole
}

/** The raw POST /auth/login response (snake_case, as the backend serialises it). */
export interface LoginResponseBody {
  token: string
  user: {
    id: string
    legal_name: string
    initials: string
    email: string
    role: UserRole
  }
}
