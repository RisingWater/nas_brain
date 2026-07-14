import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api/admin': {
        target: 'http://localhost:9020',
        changeOrigin: true,
      },
      '/api/services': {
        target: 'http://localhost:9022',
        changeOrigin: true,
      },
      '/api/tools': {
        target: 'http://localhost:9031',
        changeOrigin: true,
      },
      '/api/speak': {
        target: 'http://localhost:9020',
        changeOrigin: true,
      },
      '/api/tts': {
        target: 'http://localhost:9020',
        changeOrigin: true,
      },
    },
  },
})
