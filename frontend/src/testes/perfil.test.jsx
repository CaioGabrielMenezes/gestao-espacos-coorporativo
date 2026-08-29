import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import App from '../App'
import {
  equipeFake,
  mockarFetch,
  renderizarComRotas,
  indicadoresFake,
  mapaFake,
  salaFake,
  setorFake,
} from './ajuda'

/**
 * Os dois níveis de decisão da seção 2 do enunciado.
 *
 * A separação é organizacional, não de segurança: sem autenticação, nada
 * impede chamadas diretas à API. O que se verifica aqui é que cada papel vê o
 * que lhe compete e que a governança registra quem agiu.
 */

const SETORES = [setorFake(), setorFake({ id: 2, nome: 'Operações' })]
const COORDENADOR_TEC = { tipo: 'setor', setorId: 1, nome: 'Tecnologia' }

const rotasBase = {
  '/api/setores': SETORES,
  '/api/salas': [salaFake()],
  '/api/equipes': [equipeFake()],
  '/api/restricoes/tipos': [],
  '/api/restricoes': [],
  '/api/dashboard/indicadores': indicadoresFake,
  '/api/dashboard/mapa': mapaFake,
  '/api/alocacoes/execucoes': [],
}

beforeEach(() => localStorage.clear())

describe('seletor de perfil', () => {
  it('começa como Coordenador Geral', async () => {
    mockarFetch(rotasBase)
    renderizarComRotas(<App />)
    expect(await screen.findByLabelText(/Atuando como/)).toHaveValue('geral')
  })

  it('lista os setores vindos da API como perfis possíveis', async () => {
    mockarFetch(rotasBase)
    renderizarComRotas(<App />)

    await waitFor(() =>
      expect(screen.getByRole('option', { name: /Tecnologia/ })).toBeInTheDocument()
    )
    expect(screen.getByRole('option', { name: /Operações/ })).toBeInTheDocument()
  })

  it('lembra o perfil escolhido entre sessões', async () => {
    mockarFetch(rotasBase)
    renderizarComRotas(<App />)

    const seletor = await screen.findByLabelText(/Atuando como/)
    await waitFor(() =>
      expect(screen.getByRole('option', { name: /Tecnologia/ })).toBeInTheDocument()
    )
    await userEvent.selectOptions(seletor, '1')

    expect(JSON.parse(localStorage.getItem('perfil-atual'))).toMatchObject({
      tipo: 'setor',
      nome: 'Tecnologia',
    })
  })

  it('funciona mesmo se a lista de setores falhar', async () => {
    // Sem setores, resta o Coordenador Geral — a aplicação não pode quebrar.
    mockarFetch({ ...rotasBase, '/api/setores': { status: 500, corpo: null } })
    renderizarComRotas(<App />)
    expect(await screen.findByLabelText(/Atuando como/)).toHaveValue('geral')
  })
})

describe('o que cada papel enxerga', () => {
  it('o Coordenador Geral tem acesso às recomendações', async () => {
    mockarFetch(rotasBase)
    renderizarComRotas(<App />)
    expect(await screen.findByRole('link', { name: 'Recomendações' })).toBeInTheDocument()
  })

  it('o Coordenador de Setor não executa a otimização global', async () => {
    // Pela seção 2, executar a otimização e decidir sobre as recomendações
    // compete ao Coordenador Geral.
    mockarFetch(rotasBase)
    renderizarComRotas(<App />, { perfil: COORDENADOR_TEC })

    await screen.findByLabelText(/Atuando como/)
    expect(screen.queryByRole('link', { name: 'Recomendações' })).not.toBeInTheDocument()
  })

  it('acessar recomendações pela URL redireciona quem não é o Geral', async () => {
    mockarFetch(rotasBase)
    renderizarComRotas(<App />, { rota: '/recomendacoes', perfil: COORDENADOR_TEC })

    // Cai no dashboard em vez de mostrar uma tela sem ação possível.
    expect(await screen.findByRole('heading', { name: /Ocupação do prédio/ })).toBeInTheDocument()
  })

  it('o Coordenador Geral administra salas e setores', async () => {
    mockarFetch(rotasBase)
    renderizarComRotas(<App />, { rota: '/cadastro/salas' })

    expect(await screen.findByRole('link', { name: 'Salas' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Setores' })).toBeInTheDocument()
  })

  it('o Coordenador de Setor informa apenas equipes e restrições', async () => {
    mockarFetch(rotasBase)
    renderizarComRotas(<App />, { rota: '/cadastro/equipes', perfil: COORDENADOR_TEC })

    expect(await screen.findByRole('link', { name: 'Equipes' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Restrições' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Salas' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Setores' })).not.toBeInTheDocument()
  })

  it('explica ao Coordenador de Setor por que ele não vê salas', async () => {
    mockarFetch(rotasBase)
    renderizarComRotas(<App />, { rota: '/cadastro/equipes', perfil: COORDENADOR_TEC })

    expect(
      await screen.findByText(/salas e setores são administrados pelo Coordenador/i)
    ).toBeInTheDocument()
  })
})
