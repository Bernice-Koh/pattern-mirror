import { fileURLToPath } from 'node:url'
// defineConfig from vitest/config (not vite) so the `test` block is typed.
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  // Forward API calls to the backend so the browser sees one origin (no CORS in dev).
  // One entry per backend path the frontend calls; add the next as endpoints land.
  server: {
    proxy: {
      '/auth': 'http://localhost:8000',
      '/analyze': 'http://localhost:8000',
      '/documents': 'http://localhost:8000',
      '/flags': 'http://localhost:8000',
      '/patterns': 'http://localhost:8000',
      '/hr': 'http://localhost:8000',
      '/growth': 'http://localhost:8000',
      '/subjects': 'http://localhost:8000',
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    coverage: {
      provider: 'v8',
      // lcov feeds SonarCloud; text is the local terminal summary.
      reporter: ['text', 'lcov'],
      include: ['src/**/*.{ts,tsx}'],
      // Entry points, declarative route wiring (logic lives in lib/auth-guards), type-only
      // files, and the tests themselves aren't measured.
      exclude: [
        'src/main.tsx',
        'src/router.tsx',
        'src/**/*.d.ts',
        'src/test/**',
        'src/**/*.test.{ts,tsx}',
      ],
    },
  },
})
