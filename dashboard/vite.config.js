import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ command }) => ({
  plugins: [react()],
  // @vercel/static-build serves output under /dashboard/ on Vercel.
  // Locally (dev/preview) serve from root.
  base: command === 'build' ? '/dashboard/' : '/',
  server: {
    proxy: {
      '/api':    { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/auth':   { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/stream': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/agent':  { target: 'http://127.0.0.1:8000', changeOrigin: true },
    }
  }
}))
