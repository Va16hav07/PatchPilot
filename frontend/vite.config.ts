import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendUrl = env.VITE_BACKEND_URL || 'http://51.4.96.62:8000'

  return {
    plugins: [
      react(),
      VitePWA({
        registerType: 'autoUpdate',
        manifest: {
          name: 'Thali — Indian meal nutrition',
          short_name: 'Thali',
          description: 'Track nutrition of Indian meals, katori by katori.',
          theme_color: '#1E6A48',
          background_color: '#F3F5F2', // splash screen; the app itself follows the theme
          display: 'standalone',
          start_url: '/',
          icons: [{ src: '/icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any maskable' }],
        },
        workbox: { navigateFallbackDenylist: [/^\/api\//] },
      }),
    ],
    server: {
      // Same-origin API in dev, so the session cookie just works.
      proxy: {
        '/api': {
          target: backendUrl,
          changeOrigin: true,
        },
      },
    },
  }
})
