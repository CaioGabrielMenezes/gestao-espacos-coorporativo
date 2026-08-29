import { defineConfig, devices } from '@playwright/test'

/**
 * Configuração do E2E.
 *
 * O Playwright sobe backend e frontend sozinho. O backend usa um SQLite
 * descartável (`DATABASE_URL` própria) e é sempre semeado antes: o teste não
 * pode depender do estado do banco de desenvolvimento, nem sujá-lo.
 *
 * Estes testes são a única camada que exercita front e back juntos — é aqui
 * que uma quebra de contrato entre os dois aparece, e não nos testes de
 * componente, que usam a API mockada.
 */

const BANCO = 'sqlite:///./e2e.db'
// No Windows o comando roda via cmd.exe, que não aceita barra normal no
// caminho do executável — daí as contrabarras.
const PYTHON =
  process.platform === 'win32' ? '.venv\\Scripts\\python.exe' : '.venv/bin/python'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  // Um worker só: os testes compartilham um backend e um banco, e rodar em
  // paralelo faria um teste ver a otimização disparada por outro.
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['html'], ['list']] : 'list',
  timeout: 30_000,

  use: {
    baseURL: 'http://localhost:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },

  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],

  webServer: [
    {
      command: `${PYTHON} -m app.seed --reset && ${PYTHON} -m uvicorn app.main:app --port 8001`,
      cwd: '../backend',
      env: { DATABASE_URL: BANCO },
      url: 'http://127.0.0.1:8001/api/health',
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: 'npm run dev -- --port 5173',
      env: { VITE_API_URL: 'http://127.0.0.1:8001' },
      url: 'http://localhost:5173',
      // Nunca reaproveitar: um `npm run dev` já aberto aponta para a porta
      // 8000 (banco de desenvolvimento), e os testes rodariam contra o banco
      // errado sem nenhum sinal de que isso aconteceu.
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
})
