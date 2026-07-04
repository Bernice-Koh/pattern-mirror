import type { ReactNode } from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import type { AuthUser } from '@/lib/auth-contract'
import { useAuth } from '@/lib/use-auth'
import { SurfaceNav } from './surface-nav'

// Link renders its render-prop child with a fixed active state; routing itself is not under test.
vi.mock('@tanstack/react-router', () => ({
  Link: ({
    children,
  }: {
    children: (state: { isActive: boolean }) => ReactNode
  }) => children({ isActive: false }),
}))
vi.mock('@/lib/use-auth', () => ({ useAuth: vi.fn() }))

function asUser(role: AuthUser['role']): AuthUser {
  return {
    id: 'u1',
    legalName: 'Test',
    initials: 'T',
    email: 't@example.test',
    role,
  }
}

function setUser(user: AuthUser | null) {
  vi.mocked(useAuth).mockReturnValue({
    user,
    login: vi.fn(),
    logout: vi.fn(),
  })
}

describe('SurfaceNav', () => {
  beforeEach(() => vi.mocked(useAuth).mockReset())

  it('shows a manager only their four surfaces, never HR Portal', () => {
    setUser(asUser('manager'))
    render(<SurfaceNav />)

    for (const label of [
      'JD Studio',
      'Feedback Checkpoint',
      'Pattern Dashboard',
      'Promotion Writeup',
    ]) {
      expect(screen.getByText(label)).toBeInTheDocument()
    }
    expect(screen.queryByText('HR Portal')).not.toBeInTheDocument()
  })

  it('shows HR only the HR Portal, never the manager surfaces', () => {
    setUser(asUser('hr'))
    render(<SurfaceNav />)

    expect(screen.getByText('HR Portal')).toBeInTheDocument()
    expect(screen.queryByText('JD Studio')).not.toBeInTheDocument()
    expect(screen.queryByText('Pattern Dashboard')).not.toBeInTheDocument()
  })

  it('renders no surfaces until a user resolves', () => {
    setUser(null)
    render(<SurfaceNav />)

    expect(screen.queryByText('JD Studio')).not.toBeInTheDocument()
    expect(screen.queryByText('HR Portal')).not.toBeInTheDocument()
  })
})
