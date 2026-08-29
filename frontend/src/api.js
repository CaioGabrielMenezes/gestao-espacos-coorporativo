/**
 * Cliente da API.
 *
 * Toda chamada passa por `requisitar`, que transforma erro de rede e erro HTTP
 * na mesma coisa: uma Error com mensagem legível. As telas tratam um caso só.
 */

const BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

/**
 * Traduz o corpo de erro do FastAPI em uma frase única.
 *
 * O 422 de validação não vem como string: vem uma lista de objetos, um por
 * campo reprovado. Tratar isso como string produzia "Erro 422" e escondia
 * justamente a informação de que o usuário precisa para corrigir o formulário.
 */
export function formatarErro(corpo, status, caminho) {
  const detalhe = corpo?.detail

  if (typeof detalhe === 'string') return detalhe

  if (Array.isArray(detalhe) && detalhe.length) {
    return detalhe
      .map((item) => {
        // loc costuma ser ["body", "capacidade"]; o campo é o último trecho
        // textual. Em erro do corpo inteiro não há campo, e aí só a msg serve.
        const campo = Array.isArray(item.loc)
          ? item.loc.filter((p) => typeof p === 'string' && p !== 'body').pop()
          : null
        const msg = item.msg || 'valor inválido'
        return campo ? `${campo}: ${msg}` : msg
      })
      .join(' · ')
  }

  return `Erro ${status} ao chamar ${caminho}`
}

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
    throw new Error(formatarErro(corpo, resposta.status, caminho))
  }

  return corpo
}

/** Açúcar para não repetir JSON.stringify em toda mutação. */
const enviar = (dados) => ({ body: JSON.stringify(dados) })

export const api = {
  // ---- Dashboard e mapa -------------------------------------------------
  indicadores: (execucaoId) =>
    requisitar(
      execucaoId
        ? `/api/dashboard/indicadores?execucao_id=${execucaoId}`
        : '/api/dashboard/indicadores'
    ),
  indicadoresUltimaExecucao: () =>
    requisitar('/api/dashboard/indicadores/ultima-execucao'),
  mapa: (execucaoId) =>
    requisitar(
      execucaoId
        ? `/api/dashboard/mapa?execucao_id=${execucaoId}`
        : '/api/dashboard/mapa'
    ),
  mapaUltimaExecucao: () => requisitar('/api/dashboard/mapa/ultima-execucao'),

  // ---- Motor ------------------------------------------------------------
  otimizar: (usuario = 'coordenador-geral') =>
    requisitar('/api/alocacoes/otimizar', { method: 'POST', ...enviar({ usuario }) }),
  reotimizar: (execucaoId, usuario = 'coordenador-geral') =>
    requisitar(`/api/alocacoes/execucoes/${execucaoId}/reotimizar`, {
      method: 'POST',
      ...enviar({ usuario }),
    }),

  execucoes: () => requisitar('/api/alocacoes/execucoes'),
  execucao: (id) => requisitar(`/api/alocacoes/execucoes/${id}`),
  totaisIntervencao: () => requisitar('/api/alocacoes/intervencoes/total'),

  aceitar: (alocacaoId, justificativa, usuario) =>
    requisitar(`/api/alocacoes/${alocacaoId}/aceitar`, {
      method: 'POST',
      ...enviar({ justificativa, usuario }),
    }),
  rejeitar: (alocacaoId, justificativa, usuario) =>
    requisitar(`/api/alocacoes/${alocacaoId}/rejeitar`, {
      method: 'POST',
      ...enviar({ justificativa, usuario }),
    }),
  editar: (alocacaoId, salaId, justificativa, usuario) =>
    requisitar(`/api/alocacoes/${alocacaoId}`, {
      method: 'PUT',
      ...enviar({ sala_id: salaId, justificativa, usuario }),
    }),

  // ---- Cadastro ---------------------------------------------------------
  salas: () => requisitar('/api/salas'),
  criarSala: (dados) => requisitar('/api/salas', { method: 'POST', ...enviar(dados) }),
  atualizarSala: (id, dados) =>
    requisitar(`/api/salas/${id}`, { method: 'PUT', ...enviar(dados) }),
  removerSala: (id) => requisitar(`/api/salas/${id}`, { method: 'DELETE' }),

  setores: () => requisitar('/api/setores'),
  criarSetor: (dados) =>
    requisitar('/api/setores', { method: 'POST', ...enviar(dados) }),
  atualizarSetor: (id, dados) =>
    requisitar(`/api/setores/${id}`, { method: 'PUT', ...enviar(dados) }),
  removerSetor: (id) => requisitar(`/api/setores/${id}`, { method: 'DELETE' }),

  equipes: () => requisitar('/api/equipes'),
  // A equipe nasce dentro de um setor: é a rota que garante que nenhuma
  // equipe exista sem setor associado.
  criarEquipe: (setorId, dados) =>
    requisitar(`/api/setores/${setorId}/equipes`, { method: 'POST', ...enviar(dados) }),
  atualizarEquipe: (id, dados) =>
    requisitar(`/api/equipes/${id}`, { method: 'PUT', ...enviar(dados) }),
  removerEquipe: (id) => requisitar(`/api/equipes/${id}`, { method: 'DELETE' }),

  restricoes: () => requisitar('/api/restricoes'),
  tiposRestricao: () => requisitar('/api/restricoes/tipos'),
  criarRestricao: (dados) =>
    requisitar('/api/restricoes', { method: 'POST', ...enviar(dados) }),
  removerRestricao: (id) => requisitar(`/api/restricoes/${id}`, { method: 'DELETE' }),
}

/** Id da execução mais recente, ou null se ainda não houve nenhuma. */
export async function ultimaExecucaoId() {
  const execucoes = await api.execucoes()
  const concluidas = execucoes.filter((e) => e.execucao_id != null)
  return concluidas.length ? concluidas[0].execucao_id : null
}
