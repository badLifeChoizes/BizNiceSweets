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
      '/api': 'http://api:8000',
    },
  },
})
