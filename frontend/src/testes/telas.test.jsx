import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import BarraOcupacao from '../componentes/BarraOcupacao'
import Comparacao from '../paginas/Comparacao'
import Mapa from '../paginas/Mapa'
import Recomendacoes from '../paginas/Recomendacoes'
import {
  mapaFake,
  mockarFetch,
  mockarFetchQueFalha,
  renderizarComRotas,
  salaFake,
} from './ajuda'

describe('mapa do prédio', () => {
  it('desenha as salas com equipe e percentual escritos', async () => {
    // A cor sozinha não pode ser o único portador da informação: o percentual
    // precisa estar em texto.
    mockarFetch({ '/api/alocacoes/execucoes': [], '/api/dashboard/mapa': mapaFake })
    renderizarComRotas(<Mapa />)

    expect(await screen.findByText('Sala 101')).toBeInTheDocument()
    expect(screen.getByText('Desenvolvimento A')).toBeInTheDocument()
    expect(screen.getByText('75%')).toBeInTheDocument()
    expect(screen.getByText('30/40')).toBeInTheDocument()
  })

  it('marca sala sem equipe como livre', async () => {
    mockarFetch({ '/api/alocacoes/execucoes': [], '/api/dashboard/mapa': mapaFake })
    renderizarComRotas(<Mapa />)
    expect(await screen.findByText('Livre')).toBeInTheDocument()
  })

  it('descreve cada sala para leitor de tela', async () => {
    mockarFetch({ '/api/alocacoes/execucoes': [], '/api/dashboard/mapa': mapaFake })
    renderizarComRotas(<Mapa />)

    expect(
      await screen.findByLabelText(/Sala 101, adequada, Desenvolvimento A/)
    ).toBeInTheDocument()
  })

  it('esconde o alternador quando não há execução para comparar', async () => {
    mockarFetch({ '/api/alocacoes/execucoes': [], '/api/dashboard/mapa': mapaFake })
    renderizarComRotas(<Mapa />)

    await screen.findByText('Sala 101')
    expect(screen.queryByRole('button', { name: 'Proposto' })).not.toBeInTheDocument()
  })

  it('alterna para a distribuição proposta', async () => {
    const { chamadas } = mockarFetch({
      '/api/alocacoes/execucoes': [{ execucao_id: 5 }],
      '/api/dashboard/mapa': { ...mapaFake, origem: 'execucao', execucao_id: 5 },
    })
    renderizarComRotas(<Mapa />)

    await userEvent.click(await screen.findByRole('button', { name: 'Proposto' }))
    await waitFor(() =>
      expect(
        chamadas.some((c) => c.caminho.includes('/api/dashboard/mapa?execucao_id=5'))
      ).toBe(true)
    )
  })

  it('avisa quando não há sala cadastrada', async () => {
    mockarFetch({
      '/api/alocacoes/execucoes': [],
      '/api/dashboard/mapa': { origem: 'estado_atual', execucao_id: null, andares: [] },
    })
    renderizarComRotas(<Mapa />)
    expect(await screen.findByText(/Nenhuma sala cadastrada/)).toBeInTheDocument()
  })

  it('trata backend fora do ar', async () => {
    mockarFetchQueFalha()
    renderizarComRotas(<Mapa />)
    expect(await screen.findByRole('alert')).toHaveTextContent(/backend está rodando/)
  })
})

describe('recomendações', () => {
  const execucao = {
    governanca: {
      execucao_id: 3,
      equipes_alocadas: 1,
      equipes_nao_alocadas: 1,
      restricoes_violadas: 0,
      ocupacao_prevista: '75%',
      algoritmo: 'allocation-engine-v1',
      duracao_ms: 1.2,
      timestamp: '2026-08-29T12:00:00',
      usuario: 'coordenador-geral',
      equipes_analisadas: 2,
      salas_analisadas: 2,
      pesos: {},
    },
    recomendacoes: [
      {
        id: 10,
        equipe_id: 1,
        equipe: 'Desenvolvimento A',
        pessoas: 30,
        sala_id: 1,
        sala_sugerida: 'Sala 101',
        capacidade: 40,
        andar: 1,
        ocupacao_percentual: 75,
        status: 'sugerida',
        explicabilidade: {
          sala: 'Sala 101',
          equipe: 'Desenvolvimento A',
          capacidade_sala: 40,
          tamanho_equipe: 30,
          ocupacao_prevista: '75%',
          recursos_atendidos: true,
          restricao_andar_atendida: true,
          alternativas_avaliadas: 3,
          justificativa: 'Melhor equilíbrio entre as 3 alternativas avaliadas.',
          score: 70,
          criterios: { ocupacao: 45, preferencia_andar: 10, permanencia: 15 },
        },
      },
    ],
    alertas: [
      {
        status: 'ALERTA',
        equipe_id: 2,
        equipe_afetada: 'Operações Delta',
        restricao_nao_atendida: 'capacidade mínima',
        causa: 'Maior sala disponível comporta 40 pessoas; equipe tem 92',
        encaminhamento: 'dividir equipe em dois grupos',
      },
    ],
    comparativo: {},
    intervencoes: [],
  }

  const rotas = {
    '/api/alocacoes/execucoes': [{ execucao_id: 3 }],
    '/api/alocacoes/execucoes/3': execucao,
    '/api/salas': [salaFake()],
  }

  it('revela a explicabilidade em um clique na linha', async () => {
    // Critério de aceite da spec: a explicação fica a 1 clique da lista.
    mockarFetch(rotas)
    renderizarComRotas(<Recomendacoes />)

    const linha = await screen.findByText('Desenvolvimento A')
    expect(screen.queryByText(/Melhor equilíbrio/)).not.toBeInTheDocument()

    await userEvent.click(linha)
    expect(await screen.findByText(/Melhor equilíbrio/)).toBeInTheDocument()
    // O número de alternativas avaliadas é parte da explicabilidade exigida
    // pela spec; sem ele a justificativa vira afirmação sem lastro.
    const termo = screen.getByText('Alternativas avaliadas')
    expect(termo.nextElementSibling).toHaveTextContent('3')
  })

  it('mostra o alerta da equipe que não coube, com causa e encaminhamento', async () => {
    mockarFetch(rotas)
    renderizarComRotas(<Recomendacoes />)

    expect(await screen.findByText('Operações Delta')).toBeInTheDocument()
    expect(screen.getByText(/comporta 40 pessoas; equipe tem 92/)).toBeInTheDocument()
    expect(screen.getByText(/dividir equipe em dois grupos/)).toBeInTheDocument()
  })

  it('aceita uma recomendação pelo id da alocação', async () => {
    const { chamadas } = mockarFetch(rotas)
    renderizarComRotas(<Recomendacoes />)

    await userEvent.click(await screen.findByText('Desenvolvimento A'))
    await userEvent.click(screen.getByRole('button', { name: /Aceitar/ }))

    await waitFor(() =>
      expect(
        chamadas.some((c) => c.caminho.includes('/api/alocacoes/10/aceitar'))
      ).toBe(true)
    )
  })
})

describe('comparação antes e depois', () => {
  it('pede uma otimização quando ainda não houve nenhuma', async () => {
    mockarFetch({ '/api/alocacoes/execucoes': [] })
    renderizarComRotas(<Comparacao />)
    expect(await screen.findByText(/Ainda não há execução para comparar/)).toBeInTheDocument()
  })

  it('marca como melhora a queda de assentos ociosos', async () => {
    mockarFetch({
      '/api/alocacoes/execucoes': [{ execucao_id: 1 }],
      '/api/alocacoes/execucoes/1': {
        comparativo: {
          antes: {
            ocupacao_media_percentual: 60,
            assentos_ociosos: 190,
            equipes_alocadas: 11,
            equipes_sem_sala: 1,
            salas_ocupadas: 11,
            violacoes: 2,
          },
          depois: {
            ocupacao_media_percentual: 70,
            assentos_ociosos: 126,
            equipes_alocadas: 11,
            equipes_sem_sala: 1,
            salas_ocupadas: 11,
            violacoes: 1,
          },
        },
      },
    })
    renderizarComRotas(<Comparacao />)

    // Menos assentos ociosos é melhora, ainda que o número tenha caído.
    const celula = (await screen.findByText('-64')).closest('td')
    expect(celula).toHaveClass('delta--melhorou')
  })
})

describe('BarraOcupacao', () => {
  it('expõe o valor para tecnologia assistiva, não só visualmente', () => {
    renderizarComRotas(<BarraOcupacao percentual={42} rotulo="Andar 3" />)
    const barra = screen.getByRole('meter', { name: /Andar 3/ })
    expect(barra).toHaveAttribute('aria-valuenow', '42')
    expect(screen.getByText('42%')).toBeInTheDocument()
  })

  it('limita a largura em 100% mesmo com percentual acima', () => {
    // Superlotação existe nos dados; a barra não pode vazar do trilho.
    const { container } = renderizarComRotas(
      <BarraOcupacao percentual={130} rotulo="Andar 9" />
    )
    const preenchimento = container.querySelector('.barra__preenchimento')
    expect(preenchimento).toHaveStyle({ width: '100%' })
  })
})
