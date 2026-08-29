import { useCallback, useState } from 'react'
import { api } from '../../api'
import { CampoNumero, CampoTexto } from '../../componentes/Campo'
import { AcoesLinha, PainelCrud, useRecurso } from '../../componentes/PainelCrud'

const NOVO = { nome: '', coordenador: '', total_funcionarios: 0 }

export default function Setores() {
  const {
    dados: setores,
    erro,
    carregando,
    recarregar,
    setErro,
  } = useRecurso(api.setores)
  const [form, setForm] = useState(null)
  const [salvando, setSalvando] = useState(false)

  const campo = (nome) => (valor) => setForm((f) => ({ ...f, [nome]: valor }))

  const salvar = useCallback(
    async (evento) => {
      evento.preventDefault()
      setSalvando(true)
      setErro(null)
      try {
        const { id, ...dados } = form
        if (id) await api.atualizarSetor(id, dados)
        else await api.criarSetor(dados)
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
    async (setor) => {
      setErro(null)
      try {
        await api.removerSetor(setor.id)
        await recarregar()
      } catch (e) {
        setErro(e.message)
      }
    },
    [recarregar, setErro]
  )

  return (
    <PainelCrud
      titulo="Setores"
      descricao="Áreas da empresa; cada equipe pertence a um setor"
      itens={setores}
      carregando={carregando}
      erro={erro}
      aoRecarregar={recarregar}
      rotuloNovo="Novo setor"
      formularioAberto={form !== null}
      aoAbrirNovo={() => setForm(NOVO)}
      aoFechar={() => setForm(null)}
      vazio="Nenhum setor cadastrado. Equipes precisam de um setor para existir."
      formulario={
        form && (
          <form onSubmit={salvar} aria-label="Formulário de setor">
            <div className="grade-campos">
              <CampoTexto
                rotulo="Nome"
                valor={form.nome}
                aoMudar={campo('nome')}
                obrigatorio
              />
              <CampoTexto
                rotulo="Coordenador"
                valor={form.coordenador}
                aoMudar={campo('coordenador')}
                obrigatorio
              />
              <CampoNumero
                rotulo="Total de funcionários"
                valor={form.total_funcionarios}
                aoMudar={campo('total_funcionarios')}
                min={0}
                dica="Tamanho do setor inteiro, não da equipe"
              />
            </div>
            <button type="submit" className="primario" disabled={salvando}>
              {salvando ? 'Salvando…' : form.id ? 'Salvar alterações' : 'Criar setor'}
            </button>
          </form>
        )
      }
    >
      <table className="tabela">
        <thead>
          <tr>
            <th scope="col">Nome</th>
            <th scope="col">Coordenador</th>
            <th scope="col">Funcionários</th>
            <th scope="col">Ações</th>
          </tr>
        </thead>
        <tbody>
          {(setores ?? []).map((setor) => (
            <tr key={setor.id}>
              <th scope="row">{setor.nome}</th>
              <td>{setor.coordenador}</td>
              <td>{setor.total_funcionarios}</td>
              <td>
                <AcoesLinha
                  aoEditar={() => setForm(setor)}
                  aoExcluir={() => excluir(setor)}
                  confirmacao={
                    `Excluir o setor ${setor.nome}?\n\n` +
                    'ATENÇÃO: todas as equipes deste setor serão excluídas ' +
                    'junto, em cascata. Isso não pode ser desfeito.'
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
