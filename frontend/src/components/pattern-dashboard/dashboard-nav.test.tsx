import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import type { AuthContextValue } from '@/lib/use-auth'
import { useAuth } from '@/lib/use-auth'
import { DashboardNav } from './dashboard-nav'

vi.mock('@/lib/use-auth', () => ({ useAuth: vi.fn() }))
const useAuthMock = vi.mocked(useAuth)

const USER = {
  id: 'u1',
  legalName: 'David Koh',
  initials: 'DK',
  email: 'david@example.com',
  role: 'manager' as const,
}

function authValue(user: AuthContextValue['user']): AuthContextValue {
  return { user, login: vi.fn(), logout: vi.fn() }
}

beforeEach(() => {
  vi.clearAllMocks()
  useAuthMock.mockReturnValue(authValue(USER))
})

describe('DashboardNav', () => {
  it('shows the signed-in manager and their sub-views', () => {
    render(<DashboardNav active="documents" onSelect={vi.fn()} />)

    expect(screen.getByText('DK')).toBeInTheDocument()
    expect(screen.getByText('David Koh')).toBeInTheDocument()
    expect(screen.getByText('Manager')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'My documents' }),
    ).toBeInTheDocument()
  })

  it('reports the chosen view', () => {
    const onSelect = vi.fn()
    render(<DashboardNav active="documents" onSelect={onSelect} />)

    fireEvent.click(screen.getByRole('button', { name: 'Your patterns' }))

    expect(onSelect).toHaveBeenCalledWith('patterns')
  })

  it('renders without an identity before the user resolves', () => {
    useAuthMock.mockReturnValue(authValue(null))

    render(<DashboardNav active="documents" onSelect={vi.fn()} />)

    expect(
      screen.getByRole('button', { name: 'My documents' }),
    ).toBeInTheDocument()
  })
})
