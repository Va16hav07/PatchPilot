import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
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
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})
