/**
 * Cliente da API.
 *
 * Toda chamada passa por `requisitar`, que transforma erro de rede e erro HTTP
 * na mesma coisa: uma Error com mensagem legível. As telas tratam um caso só.
 */

const BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

async function requisitar(caminho, opcoes = {}) {
  let resposta
  try {
    resposta = await fetch(`${BASE}${caminho}`, {
      headers: { 'Content-Type': 'application/json' },
      ...opcoes,
    })
  } catch {
    // Backend fora do ar é o cenário mais provável numa demonstração;
    // a mensagem precisa dizer o que fazer, não só que falhou.
    throw new Error(
      `Não foi possível falar com o servidor em ${BASE}. ` +
        'Confira se o backend está rodando (uvicorn app.main:app).'
    )
  }

  if (resposta.status === 204) return null

  const corpo = await resposta.json().catch(() => null)

  if (!resposta.ok) {
    const detalhe = corpo?.detail
    throw new Error(
      typeof detalhe === 'string'
        ? detalhe
        : `Erro ${resposta.status} ao chamar ${caminho}`
    )
  }

  return corpo
}

export const api = {
  indicadores: (execucaoId) =>
    requisitar(
      execucaoId
        ? `/api/dashboard/indicadores?execucao_id=${execucaoId}`
        : '/api/dashboard/indicadores'
    ),
  indicadoresUltimaExecucao: () =>
    requisitar('/api/dashboard/indicadores/ultima-execucao'),

  otimizar: (usuario = 'coordenador-geral') =>
    requisitar('/api/alocacoes/otimizar', {
      method: 'POST',
      body: JSON.stringify({ usuario }),
    }),
  reotimizar: (execucaoId, usuario = 'coordenador-geral') =>
    requisitar(`/api/alocacoes/execucoes/${execucaoId}/reotimizar`, {
      method: 'POST',
      body: JSON.stringify({ usuario }),
    }),

  execucoes: () => requisitar('/api/alocacoes/execucoes'),
  execucao: (id) => requisitar(`/api/alocacoes/execucoes/${id}`),
  totaisIntervencao: () => requisitar('/api/alocacoes/intervencoes/total'),

  aceitar: (alocacaoId, justificativa) =>
    requisitar(`/api/alocacoes/${alocacaoId}/aceitar`, {
      method: 'POST',
      body: JSON.stringify({ justificativa }),
    }),
  rejeitar: (alocacaoId, justificativa) =>
    requisitar(`/api/alocacoes/${alocacaoId}/rejeitar`, {
      method: 'POST',
      body: JSON.stringify({ justificativa }),
    }),
  editar: (alocacaoId, salaId, justificativa) =>
    requisitar(`/api/alocacoes/${alocacaoId}`, {
      method: 'PUT',
      body: JSON.stringify({ sala_id: salaId, justificativa }),
    }),

  salas: () => requisitar('/api/salas'),
}

/** Id da execução mais recente, ou null se ainda não houve nenhuma. */
export async function ultimaExecucaoId() {
  const execucoes = await api.execucoes()
  const concluidas = execucoes.filter((e) => e.execucao_id != null)
  return concluidas.length ? concluidas[0].execucao_id : null
}
