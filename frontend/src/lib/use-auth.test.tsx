import { describe, it, expect, vi } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useAuth } from './use-auth'

describe('useAuth', () => {
  it('throws when used outside an AuthProvider', () => {
    // React logs the thrown render error; silence it so the suite output stays clean.
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})

    expect(() => renderHook(() => useAuth())).toThrow(
      'useAuth must be used within an AuthProvider',
    )

    consoleError.mockRestore()
  })
})
