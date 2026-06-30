import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { PatternDashboard } from './pattern-dashboard'

vi.mock('@/lib/use-auth', () => ({
  useAuth: () => ({
    user: {
      id: 'u1',
      legalName: 'David Koh',
      initials: 'DK',
      email: 'david@example.com',
      role: 'manager' as const,
    },
    login: vi.fn(),
    logout: vi.fn(),
  }),
}))

vi.mock('@/lib/documents-client', () => ({
  listDocuments: vi.fn().mockResolvedValue([]),
}))

vi.mock('@/lib/patterns-client', () => ({
  getPatterns: vi.fn().mockResolvedValue({
    writing_patterns: [],
    decision_patterns: [],
    adoption_trend: [],
    flag_volume_trend: [],
    category_improvements: [],
  }),
}))

vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => vi.fn(),
}))

function wrapper({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={new QueryClient()}>
      {children}
    </QueryClientProvider>
  )
}

describe('PatternDashboard', () => {
  it('opens on My Documents', () => {
    render(<PatternDashboard />, { wrapper })

    expect(
      screen.getByRole('heading', { name: 'My documents' }),
    ).toBeInTheDocument()
  })

  it('switches to the Your patterns view from the rail', () => {
    render(<PatternDashboard />, { wrapper })

    fireEvent.click(screen.getByRole('button', { name: 'Your patterns' }))

    expect(
      screen.getByRole('heading', { name: 'Your patterns' }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'My documents' })).toBeNull()
  })

  it('renders the static profile view', () => {
    render(<PatternDashboard />, { wrapper })

    fireEvent.click(screen.getByRole('button', { name: 'Profile' }))

    expect(screen.getByRole('heading', { name: 'Profile' })).toBeInTheDocument()
  })
})
