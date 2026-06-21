// Extends vitest's `expect` with jest-dom matchers (toBeInTheDocument, etc.) and
// unmounts React trees between tests. Runs once before the suite (see vite.config.ts).
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'

// With vitest globals off, Testing Library can't auto-register cleanup, so do it here.
afterEach(() => {
  cleanup()
})
