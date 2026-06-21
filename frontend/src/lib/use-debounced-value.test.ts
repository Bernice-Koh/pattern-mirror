import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useDebouncedValue } from './use-debounced-value'

describe('useDebouncedValue', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns the initial value immediately', () => {
    const { result } = renderHook(() => useDebouncedValue('a', 200))
    expect(result.current).toBe('a')
  })

  it('settles on the latest value only after the delay elapses', () => {
    const { result, rerender } = renderHook(
      ({ v }) => useDebouncedValue(v, 200),
      {
        initialProps: { v: 'a' },
      },
    )

    rerender({ v: 'b' })
    expect(result.current).toBe('a')

    act(() => {
      vi.advanceTimersByTime(200)
    })
    expect(result.current).toBe('b')
  })

  it('resets the timer when the value changes again mid-delay', () => {
    const { result, rerender } = renderHook(
      ({ v }) => useDebouncedValue(v, 200),
      {
        initialProps: { v: 'a' },
      },
    )

    rerender({ v: 'b' })
    act(() => {
      vi.advanceTimersByTime(150)
    })
    rerender({ v: 'c' })
    act(() => {
      vi.advanceTimersByTime(150)
    })
    expect(result.current).toBe('a')

    act(() => {
      vi.advanceTimersByTime(50)
    })
    expect(result.current).toBe('c')
  })
})
