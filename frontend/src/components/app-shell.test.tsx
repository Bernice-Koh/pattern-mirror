import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { AuthProvider } from '@/lib/auth-context'
import { clearStoredAuth, getStoredAuth, setStoredAuth } from '@/lib/auth-token'
import type { StoredAuth } from '@/lib/auth-token'
import { AppShell } from './app-shell'

const { navigate, routerState } = vi.hoisted(() => ({
  navigate: vi.fn(),
  routerState: { pathname: '/jd-studio' },
}))

vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => navigate,
  useRouterState: ({ select }: { select: (state: unknown) => unknown }) =>
    select({ location: { pathname: routerState.pathname } }),
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
    routerState.pathname = '/jd-studio'
  })

  it('keeps a surface label on its sub-pages', () => {
    routerState.pathname = '/hr-portal/dictionary-review'
    setStoredAuth(AUTH)
    renderShell()

    expect(screen.getByText(/HR Portal/)).toBeInTheDocument()
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
