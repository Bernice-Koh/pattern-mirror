import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { AuthProvider } from '@/lib/auth-context'
import { LoginError } from '@/lib/auth-client'
import { clearStoredAuth } from '@/lib/auth-token'
import { LoginScreen } from './login-screen'

const { navigate, loginMock } = vi.hoisted(() => ({
  navigate: vi.fn(),
  loginMock: vi.fn(),
}))

vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => navigate,
  Link: ({ to, children }: { to: string; children: ReactNode }) => (
    <a href={to}>{children}</a>
  ),
}))

vi.mock('@/lib/auth-client', async () => {
  const actual =
    await vi.importActual<typeof import('@/lib/auth-client')>(
      '@/lib/auth-client',
    )
  return { ...actual, login: loginMock }
})

function renderScreen() {
  render(
    <AuthProvider>
      <LoginScreen
        role="manager"
        portalLabel="Manager Portal"
        home="/jd-studio"
        crossLink={{
          to: '/hr-login',
          label: 'Access HR Portal',
          blurb: 'use the HR login',
        }}
      />
    </AuthProvider>,
  )
}

function submitCredentials(email: string) {
  fireEvent.change(screen.getByLabelText('Username'), {
    target: { value: email },
  })
  fireEvent.change(screen.getByLabelText('Password'), {
    target: { value: 'anything' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Log in' }))
}

describe('LoginScreen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    clearStoredAuth()
  })

  it('logs in with the screen role and navigates home on success', async () => {
    loginMock.mockResolvedValue({
      token: 't',
      user: {
        id: 'u',
        legalName: 'Alex Tan',
        initials: 'AT',
        email: 'a@x',
        role: 'manager',
      },
    })
    renderScreen()

    submitCredentials('alex.tan@example.com')

    await waitFor(() => {
      expect(loginMock).toHaveBeenCalledWith({
        email: 'alex.tan@example.com',
        password: 'anything',
        expectedRole: 'manager',
      })
      expect(navigate).toHaveBeenCalledWith({ to: '/jd-studio' })
    })
  })

  it('shows an error and does not navigate on wrong credentials', async () => {
    loginMock.mockRejectedValue(new LoginError(401))
    renderScreen()

    submitCredentials('nobody@example.com')

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Wrong credentials.',
    )
    expect(navigate).not.toHaveBeenCalled()
  })
})
