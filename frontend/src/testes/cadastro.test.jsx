import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import Equipes from '../paginas/cadastro/Equipes'
import Restricoes from '../paginas/cadastro/Restricoes'
import Salas from '../paginas/cadastro/Salas'
import Setores from '../paginas/cadastro/Setores'
import {
  equipeFake,
  mockarFetch,
  mockarFetchQueFalha,
  renderizarComRotas,
  salaFake,
  setorFake,
  tiposRestricaoFake,
} from './ajuda'

describe('cadastro de salas', () => {
  it('lista as salas vindas da API', async () => {
    mockarFetch({ '/api/salas': [salaFake(), salaFake({ id: 2, identificacao: 'Sala 202' })] })
    renderizarComRotas(<Salas />)

    expect(await screen.findByText('Sala 101')).toBeInTheDocument()
    expect(screen.getByText('Sala 202')).toBeInTheDocument()
  })

  it('avisa quando não há sala nenhuma, em vez de mostrar tabela vazia', async () => {
    mockarFetch({ '/api/salas': [] })
    renderizarComRotas(<Salas />)
    expect(await screen.findByText(/Nenhuma sala cadastrada/)).toBeInTheDocument()
  })

  it('envia os dados digitados ao criar', async () => {
    const { chamadas } = mockarFetch({ '/api/salas': [] })
    renderizarComRotas(<Salas />)

    await userEvent.click(await screen.findByRole('button', { name: 'Nova sala' }))
    await userEvent.type(screen.getByLabelText(/Identificação/), 'Sala 999')
    await userEvent.type(screen.getByLabelText(/Capacidade/), '25')
    await userEvent.type(screen.getByLabelText(/Recursos/), 'projetor, wifi')
    await userEvent.click(screen.getByLabelText(/Sala acessível/))
    await userEvent.click(screen.getByRole('button', { name: 'Criar sala' }))

    await waitFor(() => {
      const post = chamadas.find((c) => c.metodo === 'POST')
      expect(post).toBeDefined()
      expect(JSON.parse(post.corpo)).toMatchObject({
        identificacao: 'Sala 999',
        capacidade: 25,
        recursos: ['projetor', 'wifi'],
        acessibilidade: true,
      })
    })
  })

  it('mostra o erro de validação do backend com o nome do campo', async () => {
    // O 422 do FastAPI vem como lista; a tela precisa dizer QUAL campo falhou,
    // senão o usuário fica sem saber o que corrigir.
    mockarFetch({
      '/api/salas': {
        status: 422,
        corpo: {
          detail: [
            { loc: ['body', 'capacidade'], msg: 'Input should be greater than 0' },
          ],
        },
      },
    })
    renderizarComRotas(<Salas />)

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    expect(screen.getByRole('alert')).toHaveTextContent(/capacidade/)
  })

  it('preenche o formulário ao editar uma sala existente', async () => {
    mockarFetch({ '/api/salas': [salaFake({ identificacao: 'Sala 707', capacidade: 44 })] })
    renderizarComRotas(<Salas />)

    await userEvent.click(await screen.findByRole('button', { name: 'Editar' }))
    expect(screen.getByLabelText(/Identificação/)).toHaveValue('Sala 707')
    expect(screen.getByLabelText(/Capacidade/)).toHaveValue(44)
    expect(screen.getByRole('button', { name: 'Salvar alterações' })).toBeInTheDocument()
  })

  it('trata backend fora do ar sem tela branca', async () => {
    mockarFetchQueFalha()
    renderizarComRotas(<Salas />)
    expect(await screen.findByRole('alert')).toHaveTextContent(/backend está rodando/)
  })
})

describe('cadastro de setores', () => {
  it('alerta sobre a exclusão em cascata antes de apagar', async () => {
    // Apagar setor apaga as equipes junto. A confirmação tem de dizer isso —
    // "tem certeza?" não informa nada.
    mockarFetch({ '/api/setores': [setorFake()] })
    renderizarComRotas(<Setores />)

    const confirmacoes = []
    vi.spyOn(window, 'confirm').mockImplementation((msg) => {
      confirmacoes.push(msg)
      return false
    })

    await userEvent.click(await screen.findByRole('button', { name: 'Excluir' }))
    expect(confirmacoes[0]).toMatch(/equipes deste setor serão excluídas/i)
  })

  it('não chama a API quando a confirmação é recusada', async () => {
    const { chamadas } = mockarFetch({ '/api/setores': [setorFake()] })
    renderizarComRotas(<Setores />)
    vi.spyOn(window, 'confirm').mockReturnValue(false)

    await userEvent.click(await screen.findByRole('button', { name: 'Excluir' }))
    expect(chamadas.some((c) => c.metodo === 'DELETE')).toBe(false)
  })
})

describe('cadastro de equipes', () => {
  const rotas = {
    '/api/equipes': [equipeFake()],
    '/api/setores': [setorFake(), setorFake({ id: 2, nome: 'Operações' })],
    '/api/salas': [salaFake()],
  }

  it('mostra o nome do setor, não o id', async () => {
    mockarFetch(rotas)
    renderizarComRotas(<Equipes />)
    expect(await screen.findByText('Tecnologia')).toBeInTheDocument()
  })

  it('cria a equipe pela rota do setor escolhido', async () => {
    const { chamadas } = mockarFetch(rotas)
    renderizarComRotas(<Equipes />)

    await userEvent.click(await screen.findByRole('button', { name: 'Nova equipe' }))
    await userEvent.type(screen.getByLabelText(/^Nome/), 'Squad Novo')
    await userEvent.selectOptions(screen.getByLabelText(/Setor/), 'Operações')
    await userEvent.type(screen.getByLabelText(/Funcionários/), '12')
    await userEvent.click(screen.getByRole('button', { name: 'Criar equipe' }))

    await waitFor(() => {
      const post = chamadas.find((c) => c.metodo === 'POST')
      // Setor 2 na rota é o que garante, no próprio contrato, que a equipe
      // nasce com setor.
      expect(post.caminho).toContain('/api/setores/2/equipes')
      expect(JSON.parse(post.corpo)).toMatchObject({
        nome: 'Squad Novo',
        quantidade_funcionarios: 12,
      })
    })
  })

  it('bloqueia a criação enquanto não existir setor', async () => {
    mockarFetch({ ...rotas, '/api/setores': [] })
    renderizarComRotas(<Equipes />)

    await userEvent.click(await screen.findByRole('button', { name: 'Nova equipe' }))
    expect(screen.getByRole('alert')).toHaveTextContent(/Cadastre um setor antes/)
    expect(screen.getByRole('button', { name: 'Criar equipe' })).toBeDisabled()
  })
})

describe('cadastro de restrições', () => {
  const rotas = {
    '/api/restricoes/tipos': tiposRestricaoFake,
    '/api/restricoes': [],
    '/api/equipes': [equipeFake()],
    '/api/setores': [setorFake()],
    '/api/salas': [salaFake()],
  }

  it('monta os campos a partir dos metadados do backend', async () => {
    // A tela não conhece as 8 regras: ela desenha o que a API descreve.
    mockarFetch(rotas)
    renderizarComRotas(<Restricoes />)

    await userEvent.click(await screen.findByRole('button', { name: 'Nova restrição' }))
    expect(screen.getByLabelText(/Capacidade mínima exigida/)).toBeInTheDocument()
  })

  it('troca alvo e campos quando o tipo muda', async () => {
    mockarFetch(rotas)
    renderizarComRotas(<Restricoes />)

    await userEvent.click(await screen.findByRole('button', { name: 'Nova restrição' }))
    // capacidade_minima aplica-se a equipe
    expect(screen.getByLabelText(/Aplicar a \(equipe\)/)).toBeInTheDocument()

    await userEvent.selectOptions(
      screen.getByLabelText(/^Tipo/),
      'Sala reservada a setor'
    )
    // sala_reservada_setor aplica-se a sala, e troca o campo do parâmetro
    expect(screen.getByLabelText(/Aplicar a \(sala\)/)).toBeInTheDocument()
    expect(screen.getByLabelText(/Setor com reserva/)).toBeInTheDocument()
    expect(screen.queryByLabelText(/Capacidade mínima exigida/)).not.toBeInTheDocument()
  })

  it('envia o alvo no campo certo conforme o tipo', async () => {
    const { chamadas } = mockarFetch(rotas)
    renderizarComRotas(<Restricoes />)

    await userEvent.click(await screen.findByRole('button', { name: 'Nova restrição' }))
    await userEvent.selectOptions(screen.getByLabelText(/Aplicar a \(equipe\)/), 'Desenvolvimento A')
    await userEvent.type(screen.getByLabelText(/Capacidade mínima exigida/), '30')
    await userEvent.click(screen.getByRole('button', { name: 'Criar restrição' }))

    await waitFor(() => {
      const post = chamadas.find((c) => c.metodo === 'POST')
      expect(JSON.parse(post.corpo)).toMatchObject({
        tipo: 'capacidade_minima',
        equipe_id: 1,
        parametro: { valor: 30 },
      })
    })
  })

  it('não oferece edição de restrição', async () => {
    // Mudar o tipo mudaria alvo e parâmetro: é outra restrição, não a mesma.
    mockarFetch({
      ...rotas,
      '/api/restricoes': [
        { id: 1, tipo: 'capacidade_minima', equipe_id: 1, parametro: { valor: 30 }, descricao: null },
      ],
    })
    renderizarComRotas(<Restricoes />)

    const linha = (await screen.findByText('Capacidade mínima')).closest('tr')
    expect(within(linha).getByRole('button', { name: 'Excluir' })).toBeInTheDocument()
    expect(within(linha).queryByRole('button', { name: 'Editar' })).not.toBeInTheDocument()
  })

  it('tipo sem editor conhecido avisa em vez de sumir com o campo', async () => {
    mockarFetch({
      ...rotas,
      '/api/restricoes/tipos': [
        {
          tipo: 'tipo_futuro',
          rotulo: 'Tipo futuro',
          alvo: 'equipe',
          campos: [{ nome: 'x', tipo: 'formato_desconhecido', rotulo: 'Campo novo' }],
        },
      ],
    })
    renderizarComRotas(<Restricoes />)

    await userEvent.click(await screen.findByRole('button', { name: 'Nova restrição' }))
    expect(screen.getByText(/ainda não tem editor nesta tela/)).toBeInTheDocument()
  })
})
