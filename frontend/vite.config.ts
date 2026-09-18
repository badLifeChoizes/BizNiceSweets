import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  base: '/',
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.ts'],
    // Vitest's 5s default is not enough for the form-filling suites on a loaded
    // machine: `userEvent` yields between keystrokes, and a dialog with three
    // Radix Selects plus a tag input can drift past 5s under parallel backend
    // test runs while passing comfortably on an idle box. A gate that depends
    // on host load is not a gate, so the budget is raised rather than the tests
    // being made shallower. Found at the v5.0 Phase 1 verify fix loop, where a
    // baseline run with all FLAN work stashed already failed four tests this way.
    testTimeout: 15000,
  },
  server: {
    host: true,
    port: 5173,
    watch: {
      // Enable polling for Windows/WSL2 volume mounts where inotify is unavailable
      usePolling: !!process.env.VITE_USE_POLLING,
    },
    proxy: {
      // Business APIs live under /api/v1/* on the backend
      '/api': 'http://api:8000',
      // Health probes are served at the root (/health/*), not under /api.
      // Forward them too so the dev server (5173) reaches the backend instead
      // of returning index.html via the SPA fallback.
      '/health': 'http://api:8000',
    },
  },
})
