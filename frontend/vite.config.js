import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/auth':  { target: 'http://localhost:8000', changeOrigin: true },
      '/admin': { target: 'http://localhost:8000', changeOrigin: true },
      '/culle': { target: 'http://localhost:8000', changeOrigin: true },
      '/export': { target: 'http://localhost:8000', changeOrigin: true },
      '/impostazioni': { target: 'http://localhost:8000', changeOrigin: true },
      '/license': { target: 'http://localhost:8000', changeOrigin: true },
      '/messages': { target: 'http://localhost:8000', changeOrigin: true },
      '/support': { target: 'http://localhost:8000', changeOrigin: true },
      '/utenti': { target: 'http://localhost:8000', changeOrigin: true },
      '/tank': { target: 'http://localhost:8000', changeOrigin: true },
      '/health': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})
