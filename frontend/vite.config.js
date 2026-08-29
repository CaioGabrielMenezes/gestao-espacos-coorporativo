import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/testes/preparo.js',
    // Os testes E2E do Playwright vivem em /e2e e têm runner próprio; sem esta
    // exclusão o Vitest tentaria executá-los e falharia na importação.
    exclude: ['node_modules/**', 'e2e/**', 'dist/**'],
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{js,jsx}'],
      exclude: ['src/main.jsx', 'src/testes/**'],
    },
  },
})
