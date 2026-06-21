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
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    coverage: {
      provider: 'v8',
      // lcov feeds SonarCloud; text is the local terminal summary.
      reporter: ['text', 'lcov'],
      include: ['src/**/*.{ts,tsx}'],
      // Entry points, type-only files, and the tests themselves aren't measured.
      exclude: [
        'src/main.tsx',
        'src/**/*.d.ts',
        'src/test/**',
        'src/**/*.test.{ts,tsx}',
      ],
    },
  },
})
