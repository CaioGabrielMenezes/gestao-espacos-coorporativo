import { useCallback, useState } from 'react'
import { api } from '../../api'
import {
  CampoCheckbox,
  CampoListaTexto,
  CampoMultiSelect,
  CampoNumero,
  CampoSelect,
  CampoTexto,
} from '../../componentes/Campo'
import { AcoesLinha, PainelCrud, useRecurso } from '../../componentes/PainelCrud'

const PRIORIDADES = [
  { valor: 'baixa', rotulo: 'Baixa' },
  { valor: 'media', rotulo: 'Média' },
  { valor: 'alta', rotulo: 'Alta' },
  { valor: 'critica', rotulo: 'Crítica' },
]

const ANDARES = Array.from({ length: 9 }, (_, i) => ({
  valor: i + 1,
  rotulo: `Andar ${i + 1}`,
}))

const NOVA = {
  nome: '',
  setor_id: null,
  quantidade_funcionarios: null,
  horario_necessario: '08:00-18:00',
  requisitos_especiais: [],
  preferencia_andar: null,
  necessita_acessibilidade: false,
  proximidade_desejada: [],
  prioridade: 'media',
  sala_atual_id: null,
}

// Equipes, setores e salas chegam juntos: os dois últimos alimentam os
// seletores do formulário, e pedi-los em paralelo evita três esperas em fila.
const carregarTudo = async () => {
  const [equipes, setores, salas] = await Promise.all([
    api.equipes(),
    api.setores(),
    api.salas(),
  ])
  return { equipes, setores, salas }
}

export default function Equipes() {
  const { dados, erro, carregando, recarregar, setErro } = useRecurso(
    useCallback(carregarTudo, [])
  )
  const [form, setForm] = useState(null)
  const [salvando, setSalvando] = useState(false)

  const equipes = dados?.equipes
  const setores = dados?.setores ?? []
  const salas = dados?.salas ?? []

  const campo = (nome) => (valor) => setForm((f) => ({ ...f, [nome]: valor }))

  const nomeDoSetor = (id) => setores.find((s) => s.id === id)?.nome ?? '—'
  const nomeDaSala = (id) =>
    salas.find((s) => s.id === id)?.identificacao ?? 'sem sala'

  const salvar = useCallback(
    async (evento) => {
      evento.preventDefault()
      setSalvando(true)
      setErro(null)
      try {
        const { id, setor_id: setorId, ...dadosSemSetor } = form
        if (id) {
          // Na edição o setor vai no corpo, e é assim que se move uma equipe
          // de setor. Na criação ele vai na rota.
          await api.atualizarEquipe(id, { ...dadosSemSetor, setor_id: setorId })
        } else {
          await api.criarEquipe(setorId, dadosSemSetor)
        }
        setForm(null)
        await recarregar()
      } catch (e) {
        setErro(e.message)
      } finally {
        setSalvando(false)
      }
    },
    [form, recarregar, setErro]
  )

  const excluir = useCallback(
    async (equipe) => {
      setErro(null)
      try {
        await api.removerEquipe(equipe.id)
        await recarregar()
      } catch (e) {
        setErro(e.message)
      }
    },
    [recarregar, setErro]
  )

  const semSetor = setores.length === 0

  return (
    <PainelCrud
      titulo="Equipes"
      descricao="Grupos que precisam de sala; a entrada principal do motor"
      itens={equipes}
      carregando={carregando}
      erro={erro}
      aoRecarregar={recarregar}
      rotuloNovo="Nova equipe"
      formularioAberto={form !== null}
      aoAbrirNovo={() => setForm(NOVA)}
      aoFechar={() => setForm(null)}
      vazio="Nenhuma equipe cadastrada."
      formulario={
        form && (
          <form onSubmit={salvar} aria-label="Formulário de equipe">
            {semSetor && (
              <p className="aviso" role="alert">
                Cadastre um setor antes: nenhuma equipe pode existir sem setor.
              </p>
            )}
            <div className="grade-campos">
              <CampoTexto
                rotulo="Nome"
                valor={form.nome}
                aoMudar={campo('nome')}
                obrigatorio
              />
              <CampoSelect
                rotulo="Setor"
                valor={form.setor_id}
                aoMudar={campo('setor_id')}
                opcoes={setores.map((s) => ({ valor: s.id, rotulo: s.nome }))}
                obrigatorio
                vazio="Escolha um setor"
              />
              <CampoNumero
                rotulo="Funcionários"
                valor={form.quantidade_funcionarios}
                aoMudar={campo('quantidade_funcionarios')}
                min={1}
                obrigatorio
                dica="Tamanho da equipe. Determina a capacidade mínima da sala."
              />
              <CampoTexto
                rotulo="Horário necessário"
                valor={form.horario_necessario}
                aoMudar={campo('horario_necessario')}
                dica="Ex: 08:00-18:00"
              />
              <CampoSelect
                rotulo="Prioridade"
                valor={form.prioridade}
                aoMudar={campo('prioridade')}
                opcoes={PRIORIDADES}
              />
              <CampoSelect
                rotulo="Preferência de andar"
                valor={form.preferencia_andar}
                aoMudar={campo('preferencia_andar')}
                opcoes={ANDARES}
                vazio="Sem preferência"
                dica="Preferência, não exigência: o motor pondera, não obriga."
              />
              <CampoSelect
                rotulo="Sala atual"
                valor={form.sala_atual_id}
                aoMudar={campo('sala_atual_id')}
                opcoes={salas.map((s) => ({
                  valor: s.id,
                  rotulo: `${s.identificacao} (${s.capacidade} lugares)`,
                }))}
                vazio="Sem sala hoje"
                dica="Onde a equipe está hoje. Alimenta o antes/depois."
              />
              <CampoListaTexto
                rotulo="Requisitos especiais"
                valores={form.requisitos_especiais}
                aoMudar={campo('requisitos_especiais')}
                dica="Exigência dura: a sala precisa ter todos. Ex: projetor, wifi"
              />
              <CampoCheckbox
                rotulo="Necessita acessibilidade"
                valor={form.necessita_acessibilidade}
                aoMudar={campo('necessita_acessibilidade')}
              />
              <CampoMultiSelect
                rotulo="Proximidade desejada"
                valores={form.proximidade_desejada}
                aoMudar={campo('proximidade_desejada')}
                opcoes={(equipes ?? [])
                  .filter((e) => e.id !== form.id)
                  .map((e) => ({ valor: e.id, rotulo: e.nome }))}
              />
            </div>
            <button
              type="submit"
              className="primario"
              disabled={salvando || semSetor}
            >
              {salvando ? 'Salvando…' : form.id ? 'Salvar alterações' : 'Criar equipe'}
            </button>
          </form>
        )
      }
    >
      <table className="tabela">
        <thead>
          <tr>
            <th scope="col">Equipe</th>
            <th scope="col">Setor</th>
            <th scope="col">Pessoas</th>
            <th scope="col">Prioridade</th>
            <th scope="col">Requisitos</th>
            <th scope="col">Sala atual</th>
            <th scope="col">Ações</th>
          </tr>
        </thead>
        <tbody>
          {(equipes ?? []).map((equipe) => (
            <tr key={equipe.id}>
              <th scope="row">{equipe.nome}</th>
              <td>{nomeDoSetor(equipe.setor_id)}</td>
              <td>{equipe.quantidade_funcionarios}</td>
              <td>{equipe.prioridade}</td>
              <td>{equipe.requisitos_especiais.join(', ') || '—'}</td>
              <td>{equipe.sala_atual_id ? nomeDaSala(equipe.sala_atual_id) : '—'}</td>
              <td>
                <AcoesLinha
                  aoEditar={() => setForm(equipe)}
                  aoExcluir={() => excluir(equipe)}
                  confirmacao={
                    `Excluir a equipe ${equipe.nome}?\n\n` +
                    'As restrições ligadas a ela são removidas junto.'
                  }
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </PainelCrud>
  )
}
