import { describe, expect, it } from 'vitest'
import { api, formatarErro, ultimaExecucaoId } from '../api'
import { mockarFetch, mockarFetchQueFalha } from './ajuda'

describe('formatarErro', () => {
  it('usa o detail quando ele já é uma frase', () => {
    expect(formatarErro({ detail: 'Sala 101 já existe.' }, 409, '/x')).toBe(
      'Sala 101 já existe.'
    )
  })

  it('nomeia o campo reprovado na validação do FastAPI', () => {
    // Este é o caso que antes virava um inútil "Erro 422": a validação do
    // Pydantic devolve lista de objetos, não string.
    const corpo = {
      detail: [
        {
          type: 'greater_than',
          loc: ['body', 'capacidade'],
          msg: 'Input should be greater than 0',
        },
      ],
    }
    expect(formatarErro(corpo, 422, '/api/salas')).toBe(
      'capacidade: Input should be greater than 0'
    )
  })

  it('junta múltiplos campos reprovados numa frase só', () => {
    const corpo = {
      detail: [
        { loc: ['body', 'capacidade'], msg: 'obrigatório' },
        { loc: ['body', 'andar'], msg: 'fora do intervalo' },
      ],
    }
    expect(formatarErro(corpo, 422, '/x')).toBe(
      'capacidade: obrigatório · andar: fora do intervalo'
    )
  })

  it('sobrevive a erro sem campo identificável', () => {
    const corpo = { detail: [{ loc: ['body'], msg: 'corpo inválido' }] }
    expect(formatarErro(corpo, 422, '/x')).toBe('corpo inválido')
  })

  it('cai num texto genérico quando não há detail', () => {
    expect(formatarErro(null, 500, '/api/salas')).toBe('Erro 500 ao chamar /api/salas')
  })
})

describe('cliente da API', () => {
  it('explica o que fazer quando o backend está fora do ar', async () => {
    mockarFetchQueFalha()
    // A mensagem precisa dizer como resolver, não só que falhou: numa
    // demonstração, o backend derrubado é o cenário mais provável.
    await expect(api.salas()).rejects.toThrow(/backend está rodando/)
  })

  it('devolve null em 204 sem tentar ler corpo', async () => {
    mockarFetch({ '/api/salas/1': { status: 204, corpo: null } })
    await expect(api.removerSala(1)).resolves.toBeNull()
  })

  it('envia o método e o corpo corretos ao criar sala', async () => {
    const { chamadas } = mockarFetch({ '/api/salas': { id: 9 } })
    await api.criarSala({ identificacao: 'Sala 999', capacidade: 10 })

    expect(chamadas[0].metodo).toBe('POST')
    expect(JSON.parse(chamadas[0].corpo)).toEqual({
      identificacao: 'Sala 999',
      capacidade: 10,
    })
  })

  it('cria equipe pela rota do setor, que é o que impede equipe órfã', async () => {
    const { chamadas } = mockarFetch({ '/api/setores/3/equipes': { id: 5 } })
    await api.criarEquipe(3, { nome: 'Nova' })
    expect(chamadas[0].caminho).toContain('/api/setores/3/equipes')
  })

  it('monta a query de execução no mapa e nos indicadores', async () => {
    const { chamadas } = mockarFetch({ '/api/dashboard': {} })
    await api.mapa(7)
    await api.indicadores(7)
    expect(chamadas[0].caminho).toContain('/api/dashboard/mapa?execucao_id=7')
    expect(chamadas[1].caminho).toContain('/api/dashboard/indicadores?execucao_id=7')
  })

  it('omite a query quando não há execução', async () => {
    const { chamadas } = mockarFetch({ '/api/dashboard': {} })
    await api.mapa()
    expect(chamadas[0].caminho).not.toContain('?')
  })
})

describe('ultimaExecucaoId', () => {
  it('devolve null quando nunca houve execução', async () => {
    mockarFetch({ '/api/alocacoes/execucoes': [] })
    await expect(ultimaExecucaoId()).resolves.toBeNull()
  })

  it('devolve a primeira da lista, que a API ordena da mais recente', async () => {
    mockarFetch({
      '/api/alocacoes/execucoes': [{ execucao_id: 12 }, { execucao_id: 11 }],
    })
    await expect(ultimaExecucaoId()).resolves.toBe(12)
  })
})
