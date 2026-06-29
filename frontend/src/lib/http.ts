/** Single fetch wrapper for authenticated API calls: attaches the bearer token and clears the
 *  stored session on a 401 so the route guards bounce the user back to login. Every client
 *  (documents, analyze, stream, interactions) goes through here so the header lives in one place. */

import { API_BASE_URL } from '@/lib/api'
import { clearStoredAuth, getToken } from '@/lib/auth-token'

export async function apiFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const token = getToken()
  // Plain-object merge (callers pass plain header objects), so an unauthenticated request is
  // byte-identical to a bare fetch.
  const headers: Record<string, string> = {
    ...(init.headers as Record<string, string> | undefined),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers })
  if (response.status === 401) clearStoredAuth()
  return response
}
