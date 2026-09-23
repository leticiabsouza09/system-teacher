import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Em dev, o React roda em localhost:5173 e o Django em localhost:8000 —
// o proxy evita configurar CORS só pra desenvolvimento local (produção
// serve os dois do mesmo domínio, via build + collectstatic do Django).
export default defineConfig({
  plugins: [react()],
  base: '/static/grid/',
  build: {
    outDir: '../static/grid',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
