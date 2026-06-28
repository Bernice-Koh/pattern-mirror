import type { ReactNode } from 'react'
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { recordInteraction } from '@/lib/interaction-client'
import { useFlagInteractions } from './use-flag-interactions'

vi.mock('@/lib/interaction-client', () => ({
  recordInteraction: vi.fn(),
}))

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { mutations: { retry: false } },
  })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

describe('useFlagInteractions', () => {
  beforeEach(() => {
    vi.mocked(recordInteraction).mockReset()
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('optimistically marks a flag dismissed and sends the interaction', async () => {
    vi.mocked(recordInteraction).mockResolvedValue({
      id: 'i-1',
      flag_id: 'flag-1',
      kind: 'dismiss',
      dismissed: true,
    })
    const { result } = renderHook(() => useFlagInteractions(), { wrapper })

    act(() => result.current.dismiss('flag-1'))

    expect(result.current.resolutions.get('flag-1')).toBe('dismissed')
    await waitFor(() =>
      expect(recordInteraction).toHaveBeenCalledWith('flag-1', {
        kind: 'dismiss',
        accepted_alternative: undefined,
      }),
    )
  })

  it('records the taken alternative on accept', async () => {
    vi.mocked(recordInteraction).mockResolvedValue({
      id: 'i-1',
      flag_id: 'flag-1',
      kind: 'accept',
      dismissed: false,
    })
    const { result } = renderHook(() => useFlagInteractions(), { wrapper })

    act(() => result.current.accept('flag-1', 'recent graduate'))

    expect(result.current.resolutions.get('flag-1')).toBe('accepted')
    await waitFor(() =>
      expect(recordInteraction).toHaveBeenCalledWith('flag-1', {
        kind: 'accept',
        accepted_alternative: 'recent graduate',
      }),
    )
  })

  it('rolls back the optimistic resolution when the request fails', async () => {
    vi.mocked(recordInteraction).mockRejectedValue(new Error('boom'))
    const { result } = renderHook(() => useFlagInteractions(), { wrapper })

    act(() => result.current.dismiss('flag-1'))
    expect(result.current.resolutions.get('flag-1')).toBe('dismissed')

    await waitFor(() =>
      expect(result.current.resolutions.has('flag-1')).toBe(false),
    )
  })
})
