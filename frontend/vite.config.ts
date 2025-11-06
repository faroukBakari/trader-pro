import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), vueDevTools()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@clients': fileURLToPath(new URL('./src/clients_generated', import.meta.url)),
      '@public': fileURLToPath(new URL('./public', import.meta.url)),
      '@debug': fileURLToPath(new URL('./debug_data', import.meta.url)),
    },
  },
  server: {
    port: parseInt(process.env.FRONTEND_PORT || '5173'),
    proxy: {
      '/api/': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
        ws: true, // Enable WebSocket proxying
      },
    },
  },
})
