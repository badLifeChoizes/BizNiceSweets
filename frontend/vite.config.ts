import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  base: '/',
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
