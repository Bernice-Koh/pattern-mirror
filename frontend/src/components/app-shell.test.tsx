import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { AuthProvider } from '@/lib/auth-context'
import { clearStoredAuth, getStoredAuth, setStoredAuth } from '@/lib/auth-token'
import type { StoredAuth } from '@/lib/auth-token'
import { AppShell } from './app-shell'

const { navigate } = vi.hoisted(() => ({ navigate: vi.fn() }))

vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => navigate,
  useRouterState: ({ select }: { select: (state: unknown) => unknown }) =>
    select({ location: { pathname: '/jd-studio' } }),
  Outlet: () => null,
}))

vi.mock('@/components/surface-nav', () => ({ SurfaceNav: () => null }))

const AUTH: StoredAuth = {
  token: 't',
  user: {
    id: 'u',
    legalName: 'Alex Tan',
    initials: 'AT',
    email: 'alex.tan@example.com',
    role: 'manager',
  },
}

function renderShell() {
  render(
    <AuthProvider>
      <AppShell />
    </AuthProvider>,
  )
}

describe('AppShell', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    clearStoredAuth()
  })

  it('shows the signed-in user initials', () => {
    setStoredAuth(AUTH)
    renderShell()

    expect(screen.getByText('AT')).toBeInTheDocument()
  })

  it('logs out and navigates to /login', async () => {
    setStoredAuth(AUTH)
    renderShell()

    fireEvent.click(screen.getByTitle('Log out'))

    await waitFor(() => {
      expect(navigate).toHaveBeenCalledWith({ to: '/login' })
      expect(getStoredAuth()).toBeNull()
    })
  })
})
