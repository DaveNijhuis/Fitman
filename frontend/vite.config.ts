import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

/**
 * Where the dev server forwards /api.
 *
 * The default suits `npm run dev` on the host, where the backend publishes
 * port 8000. In the dev compose stack the frontend runs in its own container,
 * so localhost resolves to the frontend itself and every request 502s — that
 * stack sets VITE_API_PROXY_TARGET to the backend service name instead (#274).
 */
const apiProxyTarget = process.env.VITE_API_PROXY_TARGET ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3000,
    proxy: {
      '/api': apiProxyTarget,
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.ts'],
  },
})
