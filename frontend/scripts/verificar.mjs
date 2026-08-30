/**
 * Roda as três suítes do projeto em sequência, com um comando só.
 *
 * Existe porque verificar o sistema inteiro exigia três comandos em duas
 * pastas, com o caminho do Python mudando conforme o sistema operacional —
 * fácil de errar e fácil de esquecer uma das camadas.
 *
 * Para na primeira falha: se o backend quebrou, rodar o resto só atrasa a
 * notícia.
 */

import { spawnSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const raizFrontend = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const raizBackend = resolve(raizFrontend, '..', 'backend')

const ehWindows = process.platform === 'win32'
const python = join(raizBackend, '.venv', ehWindows ? 'Scripts/python.exe' : 'bin/python')

if (!existsSync(python)) {
  console.error(
    `\nAmbiente Python não encontrado em ${python}\n` +
      'Crie a venv antes:\n' +
      '  cd backend\n' +
      '  python -m venv .venv\n' +
      `  ${ehWindows ? '.venv\Scripts\python' : '.venv/bin/python'} -m pip install -r requirements.txt\n`
  )
  process.exit(1)
}

const etapas = [
  {
    nome: 'Backend (pytest)',
    comando: python,
    args: ['-m', 'pytest', '-q'],
    cwd: raizBackend,
  },
  {
    nome: 'Frontend (vitest)',
    comando: 'npm',
    args: ['test'],
    cwd: raizFrontend,
  },
  {
    nome: 'End-to-end (Playwright)',
    comando: 'npx',
    args: ['playwright', 'test'],
    cwd: raizFrontend,
  },
]

for (const etapa of etapas) {
  console.log(`\n\x1b[1m━━ ${etapa.nome} ━━\x1b[0m\n`)

  const resultado = spawnSync(etapa.comando, etapa.args, {
    cwd: etapa.cwd,
    stdio: 'inherit',
    // Sem isto o npm/npx não resolve no Windows, onde são arquivos .cmd.
    shell: ehWindows,
  })

  if (resultado.status !== 0) {
    console.error(`\n\x1b[31m✗ ${etapa.nome} falhou. Parando por aqui.\x1b[0m\n`)
    process.exit(resultado.status ?? 1)
  }
}

console.log('\n\x1b[32m✓ Backend, frontend e end-to-end: tudo verde.\x1b[0m\n')
