/**
 * Utilidades dos testes de componente.
 *
 * O `fetch` é mockado por rota: cada teste declara só o que a tela sob teste
 * consome. Uma rota não declarada falha com mensagem explícita, em vez de
 * devolver `undefined` e quebrar longe da causa.
 */

import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'
import { ProvedorPerfil } from '../perfil'

/**
 * Renderiza com roteador e provedor de perfil.
 *
 * O provedor entra sempre porque as telas leem o perfil para saber o que
 * mostrar e para registrar quem agiu. Ele busca a lista de setores ao montar e
 * tolera falha, então testes que não declaram essa rota seguem funcionando.
 */
export function renderizarComRotas(elemento, { rota = '/', perfil } = {}) {
  if (perfil) localStorage.setItem('perfil-atual', JSON.stringify(perfil))
  else localStorage.removeItem('perfil-atual')

  return render(
    <MemoryRouter initialEntries={[rota]}>
      <ProvedorPerfil>{elemento}</ProvedorPerfil>
    </MemoryRouter>
  )
}

/**
 * Instala um `fetch` falso.
 *
 * `rotas` mapeia um trecho de caminho para a resposta. O valor pode ser os
 * dados diretamente, ou `{ status, corpo }` para simular erro.
 */
export function mockarFetch(rotas) {
  const chamadas = []

  const falso = vi.fn(async (url, opcoes = {}) => {
    const caminho = String(url)
    chamadas.push({ caminho, metodo: opcoes.method ?? 'GET', corpo: opcoes.body })

    // Mais longa primeiro: '/api/alocacoes/execucoes/3' contém
    // '/api/alocacoes/execucoes', e casar pela primeira declarada devolveria a
    // lista no lugar do detalhe.
    const chave = Object.keys(rotas)
      .sort((a, b) => b.length - a.length)
      .find((r) => caminho.includes(r))

    if (!chave) {
      throw new Error(
        `Teste não declarou resposta para ${opcoes.method ?? 'GET'} ${caminho}. ` +
          `Rotas declaradas: ${Object.keys(rotas).join(', ') || 'nenhuma'}`
      )
    }

    const definicao = rotas[chave]
    const status = definicao?.status ?? 200
    const corpo = definicao?.status ? definicao.corpo : definicao

    return {
      ok: status >= 200 && status < 300,
      status,
      json: async () => corpo,
    }
  })

  vi.stubGlobal('fetch', falso)
  return { chamadas, falso }
}

/** Simula backend fora do ar: `fetch` rejeita, como faz o navegador. */
export function mockarFetchQueFalha() {
  const falso = vi.fn(async () => {
    throw new TypeError('Failed to fetch')
  })
  vi.stubGlobal('fetch', falso)
  return falso
}

// ---------------------------------------------------------------- fixtures
export const salaFake = (over = {}) => ({
  id: 1,
  identificacao: 'Sala 101',
  andar: 1,
  capacidade: 40,
  tipo: 'reuniao',
  recursos: ['projetor'],
  acessibilidade: true,
  disponibilidade: { dias: ['seg'], horario_inicio: '08:00', horario_fim: '18:00' },
  ...over,
})

export const setorFake = (over = {}) => ({
  id: 1,
  nome: 'Tecnologia',
  coordenador: 'Ana',
  total_funcionarios: 50,
  ...over,
})

export const equipeFake = (over = {}) => ({
  id: 1,
  setor_id: 1,
  nome: 'Desenvolvimento A',
  quantidade_funcionarios: 30,
  horario_necessario: '08:00-18:00',
  requisitos_especiais: ['projetor'],
  preferencia_andar: null,
  necessita_acessibilidade: false,
  proximidade_desejada: [],
  prioridade: 'alta',
  sala_atual_id: null,
  ...over,
})

export const tiposRestricaoFake = [
  {
    tipo: 'capacidade_minima',
    rotulo: 'Capacidade mínima',
    alvo: 'equipe',
    campos: [{ nome: 'valor', tipo: 'inteiro', rotulo: 'Capacidade mínima exigida' }],
  },
  {
    tipo: 'andar_permitido',
    rotulo: 'Andar permitido',
    alvo: 'equipe',
    campos: [{ nome: 'andares', tipo: 'lista_andares', rotulo: 'Andares permitidos' }],
  },
  {
    tipo: 'sala_reservada_setor',
    rotulo: 'Sala reservada a setor',
    alvo: 'sala',
    campos: [{ nome: 'setor_id', tipo: 'setor', rotulo: 'Setor com reserva' }],
  },
  {
    tipo: 'acessibilidade_obrigatoria',
    rotulo: 'Acessibilidade obrigatória',
    alvo: 'equipe',
    campos: [],
  },
]

export const mapaFake = {
  origem: 'estado_atual',
  execucao_id: null,
  andares: [
    {
      andar: 1,
      capacidade: 60,
      pessoas: 30,
      ocupacao_percentual: 50.0,
      salas: [
        {
          sala_id: 1,
          identificacao: 'Sala 101',
          capacidade: 40,
          tipo: 'reuniao',
          acessibilidade: true,
          equipe_id: 1,
          equipe: 'Desenvolvimento A',
          pessoas: 30,
          ocupacao_percentual: 75.0,
          faixa: 'adequada',
        },
        {
          sala_id: 2,
          identificacao: 'Sala 102',
          capacidade: 20,
          tipo: 'reuniao',
          acessibilidade: false,
          equipe_id: null,
          equipe: null,
          pessoas: 0,
          ocupacao_percentual: 0.0,
          faixa: 'vazia',
        },
      ],
    },
  ],
}

export const indicadoresFake = {
  origem: 'estado_atual',
  execucao_id: null,
  predio: {
    total_salas: 2,
    salas_ocupadas: 1,
    salas_disponiveis: 1,
    capacidade_total: 60,
    capacidade_em_uso: 40,
    capacidade_disponivel: 20,
    assentos_ociosos: 10,
    ocupacao_predio_percentual: 50.0,
    utilizacao_salas_percentual: 50.0,
    aproveitamento_percentual: 75.0,
  },
  pessoas: {
    total_funcionarios: 30,
    funcionarios_alocados: 30,
    funcionarios_nao_alocados: 0,
  },
  equipes: { total: 1, alocadas: 1, nao_alocadas: 0, taxa_alocacao_percentual: 100.0 },
  restricoes_violadas: 0,
  por_andar: [
    {
      andar: 1,
      salas: 2,
      salas_ocupadas: 1,
      salas_disponiveis: 1,
      capacidade: 60,
      pessoas: 30,
      ocupacao_percentual: 50.0,
    },
  ],
}
