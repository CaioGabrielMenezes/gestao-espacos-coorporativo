import { useCallback, useState } from 'react'
import { api } from '../../api'
import {
  CampoListaTexto,
  CampoMultiSelect,
  CampoNumero,
  CampoSelect,
  CampoTexto,
} from '../../componentes/Campo'
import { AcoesLinha, PainelCrud, useRecurso } from '../../componentes/PainelCrud'

/**
 * Cadastro de restrições.
 *
 * O formulário se monta a partir de GET /api/restricoes/tipos: o backend diz
 * qual é o alvo de cada tipo e quais campos o `parametro` exige, e a tela só
 * renderiza. Nenhuma das 8 regras está escrita aqui — se estivesse, esta cópia
 * e a do backend divergiriam na primeira mudança.
 */

const ANDARES = Array.from({ length: 9 }, (_, i) => ({
  valor: i + 1,
  rotulo: `Andar ${i + 1}`,
}))

const carregarTudo = async () => {
  const [restricoes, tipos, equipes, setores, salas] = await Promise.all([
    api.restricoes(),
    api.tiposRestricao(),
    api.equipes(),
    api.setores(),
    api.salas(),
  ])
  return { restricoes, tipos, equipes, setores, salas }
}

export default function Restricoes() {
  const { dados, erro, carregando, recarregar, setErro } = useRecurso(
    useCallback(carregarTudo, [])
  )
  const [form, setForm] = useState(null)
  const [salvando, setSalvando] = useState(false)

  const restricoes = dados?.restricoes
  const tipos = dados?.tipos ?? []
  const equipes = dados?.equipes ?? []
  const setores = dados?.setores ?? []
  const salas = dados?.salas ?? []

  const info = tipos.find((t) => t.tipo === form?.tipo)

  const opcoesDoAlvo = {
    equipe: equipes.map((e) => ({ valor: e.id, rotulo: e.nome })),
    setor: setores.map((s) => ({ valor: s.id, rotulo: s.nome })),
    sala: salas.map((s) => ({ valor: s.id, rotulo: s.identificacao })),
  }

  function abrirNovo() {
    const primeiro = tipos[0]
    setForm({ tipo: primeiro?.tipo ?? '', alvoId: null, parametro: {}, descricao: '' })
  }

  function trocarTipo(tipo) {
    // Alvo e parâmetro pertencem ao tipo anterior e não têm sentido no novo:
    // manter resíduo produziria um envio inválido que o usuário não veria.
    setForm({ tipo, alvoId: null, parametro: {}, descricao: form.descricao })
  }

  const setParametro = (nome) => (valor) =>
    setForm((f) => ({ ...f, parametro: { ...f.parametro, [nome]: valor } }))

  const salvar = useCallback(
    async (evento) => {
      evento.preventDefault()
      setSalvando(true)
      setErro(null)
      try {
        const alvo = tipos.find((t) => t.tipo === form.tipo)?.alvo
        await api.criarRestricao({
          tipo: form.tipo,
          [`${alvo}_id`]: form.alvoId,
          parametro: form.parametro,
          descricao: form.descricao || null,
        })
        setForm(null)
        await recarregar()
      } catch (e) {
        setErro(e.message)
      } finally {
        setSalvando(false)
      }
    },
    [form, tipos, recarregar, setErro]
  )

  const excluir = useCallback(
    async (restricao) => {
      setErro(null)
      try {
        await api.removerRestricao(restricao.id)
        await recarregar()
      } catch (e) {
        setErro(e.message)
      }
    },
    [recarregar, setErro]
  )

  function renderizarCampo(campo) {
    const valor = form.parametro[campo.nome]
    switch (campo.tipo) {
      case 'inteiro':
        return (
          <CampoNumero
            key={campo.nome}
            rotulo={campo.rotulo}
            valor={valor ?? null}
            aoMudar={setParametro(campo.nome)}
            obrigatorio
          />
        )
      case 'lista_andares':
        return (
          <CampoMultiSelect
            key={campo.nome}
            rotulo={campo.rotulo}
            valores={valor ?? []}
            aoMudar={setParametro(campo.nome)}
            opcoes={ANDARES}
          />
        )
      case 'lista_texto':
        return (
          <CampoListaTexto
            key={campo.nome}
            rotulo={campo.rotulo}
            valores={valor ?? []}
            aoMudar={setParametro(campo.nome)}
          />
        )
      case 'lista_equipes':
        return (
          <CampoMultiSelect
            key={campo.nome}
            rotulo={campo.rotulo}
            valores={valor ?? []}
            aoMudar={setParametro(campo.nome)}
            opcoes={opcoesDoAlvo.equipe}
          />
        )
      case 'lista_setores':
        return (
          <CampoMultiSelect
            key={campo.nome}
            rotulo={campo.rotulo}
            valores={valor ?? []}
            aoMudar={setParametro(campo.nome)}
            opcoes={opcoesDoAlvo.setor}
          />
        )
      case 'setor':
        return (
          <CampoSelect
            key={campo.nome}
            rotulo={campo.rotulo}
            valor={valor ?? null}
            aoMudar={setParametro(campo.nome)}
            opcoes={opcoesDoAlvo.setor}
            obrigatorio
            vazio="Escolha um setor"
          />
        )
      default:
        // Tipo de campo que o backend passou a devolver e a tela ainda não
        // sabe desenhar. Avisar é melhor do que sumir com o campo.
        return (
          <p key={campo.nome} className="aviso">
            Campo "{campo.rotulo}" ({campo.tipo}) ainda não tem editor nesta tela.
          </p>
        )
    }
  }

  const rotuloDoTipo = (tipo) => tipos.find((t) => t.tipo === tipo)?.rotulo ?? tipo

  function descreverAlvo(restricao) {
    if (restricao.equipe_id)
      return `Equipe: ${equipes.find((e) => e.id === restricao.equipe_id)?.nome ?? restricao.equipe_id}`
    if (restricao.setor_id)
      return `Setor: ${setores.find((s) => s.id === restricao.setor_id)?.nome ?? restricao.setor_id}`
    if (restricao.sala_id)
      return `Sala: ${salas.find((s) => s.id === restricao.sala_id)?.identificacao ?? restricao.sala_id}`
    return '—'
  }

  return (
    <PainelCrud
      titulo="Restrições"
      descricao="Regras que o motor precisa respeitar ao alocar"
      itens={restricoes}
      carregando={carregando}
      erro={erro}
      aoRecarregar={recarregar}
      rotuloNovo="Nova restrição"
      formularioAberto={form !== null}
      aoAbrirNovo={abrirNovo}
      aoFechar={() => setForm(null)}
      vazio="Nenhuma restrição cadastrada. O motor otimiza só por capacidade e ocupação."
      formulario={
        form && (
          <form onSubmit={salvar} aria-label="Formulário de restrição">
            <div className="grade-campos">
              <CampoSelect
                rotulo="Tipo"
                valor={form.tipo}
                aoMudar={trocarTipo}
                opcoes={tipos.map((t) => ({ valor: t.tipo, rotulo: t.rotulo }))}
                obrigatorio
                vazio="Escolha um tipo"
              />
              {info && (
                <CampoSelect
                  rotulo={`Aplicar a (${info.alvo})`}
                  valor={form.alvoId}
                  aoMudar={(v) => setForm((f) => ({ ...f, alvoId: v }))}
                  opcoes={opcoesDoAlvo[info.alvo] ?? []}
                  obrigatorio
                  vazio={`Escolha ${info.alvo === 'sala' ? 'uma sala' : `um ${info.alvo}`}`}
                />
              )}
              {info?.campos.map(renderizarCampo)}
              <CampoTexto
                rotulo="Descrição"
                valor={form.descricao}
                aoMudar={(v) => setForm((f) => ({ ...f, descricao: v }))}
                dica="Por que esta restrição existe. Aparece na auditoria."
              />
            </div>
            <button type="submit" className="primario" disabled={salvando}>
              {salvando ? 'Salvando…' : 'Criar restrição'}
            </button>
          </form>
        )
      }
    >
      <table className="tabela">
        <thead>
          <tr>
            <th scope="col">Tipo</th>
            <th scope="col">Alvo</th>
            <th scope="col">Parâmetro</th>
            <th scope="col">Descrição</th>
            <th scope="col">Ações</th>
          </tr>
        </thead>
        <tbody>
          {(restricoes ?? []).map((restricao) => (
            <tr key={restricao.id}>
              <th scope="row">{rotuloDoTipo(restricao.tipo)}</th>
              <td>{descreverAlvo(restricao)}</td>
              <td>
                <code>{JSON.stringify(restricao.parametro)}</code>
              </td>
              <td>{restricao.descricao || '—'}</td>
              <td>
                {/* Sem edição de propósito: mudar o tipo muda o alvo e o
                    formato do parâmetro, o que é outra restrição, não a mesma
                    alterada. O backend também só expõe criar e remover. */}
                <AcoesLinha
                  aoExcluir={() => excluir(restricao)}
                  confirmacao={
                    `Excluir esta restrição (${rotuloDoTipo(restricao.tipo)})?\n\n` +
                    'A próxima otimização deixa de considerá-la.'
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
