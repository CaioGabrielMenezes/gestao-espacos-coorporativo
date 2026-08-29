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

const TIPOS = [
  'reuniao',
  'treinamento',
  'auditorio',
  'laboratorio',
  'projeto',
  'colaborativo',
].map((t) => ({ valor: t, rotulo: t[0].toUpperCase() + t.slice(1) }))

const ANDARES = Array.from({ length: 9 }, (_, i) => ({
  valor: i + 1,
  rotulo: `Andar ${i + 1}`,
}))

const DIAS = ['seg', 'ter', 'qua', 'qui', 'sex', 'sab', 'dom'].map((d) => ({
  valor: d,
  rotulo: d,
}))

const DISPONIBILIDADE_PADRAO = {
  dias: ['seg', 'ter', 'qua', 'qui', 'sex'],
  horario_inicio: '08:00',
  horario_fim: '18:00',
}

const NOVA = {
  identificacao: '',
  andar: 1,
  capacidade: null,
  tipo: 'reuniao',
  recursos: [],
  acessibilidade: false,
  disponibilidade: DISPONIBILIDADE_PADRAO,
}

export default function Salas() {
  const { dados: salas, erro, carregando, recarregar, setErro } = useRecurso(api.salas)
  const [form, setForm] = useState(null)
  const [salvando, setSalvando] = useState(false)

  const campo = (nome) => (valor) => setForm((f) => ({ ...f, [nome]: valor }))

  // Salas antigas podem não ter disponibilidade preenchida; cair no padrão
  // evita que o formulário quebre ao editar um registro anterior.
  const disponibilidade = form?.disponibilidade ?? DISPONIBILIDADE_PADRAO
  const comporDisponibilidade = (chave) => (valor) =>
    setForm((f) => ({
      ...f,
      disponibilidade: { ...(f.disponibilidade ?? DISPONIBILIDADE_PADRAO), [chave]: valor },
    }))

  const salvar = useCallback(
    async (evento) => {
      evento.preventDefault()
      setSalvando(true)
      setErro(null)
      try {
        const { id, ...dados } = form
        if (id) await api.atualizarSala(id, dados)
        else await api.criarSala(dados)
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
    async (sala) => {
      setErro(null)
      try {
        await api.removerSala(sala.id)
        await recarregar()
      } catch (e) {
        setErro(e.message)
      }
    },
    [recarregar, setErro]
  )

  return (
    <PainelCrud
      titulo="Salas"
      descricao="Espaços do prédio disponíveis para alocação"
      itens={salas}
      carregando={carregando}
      erro={erro}
      aoRecarregar={recarregar}
      rotuloNovo="Nova sala"
      formularioAberto={form !== null}
      aoAbrirNovo={() => setForm(NOVA)}
      aoFechar={() => setForm(null)}
      vazio="Nenhuma sala cadastrada. O motor não tem onde alocar equipes."
      formulario={
        form && (
          <form onSubmit={salvar} aria-label="Formulário de sala">
            <div className="grade-campos">
              <CampoTexto
                rotulo="Identificação"
                valor={form.identificacao}
                aoMudar={campo('identificacao')}
                obrigatorio
                dica="Ex: Sala 704"
              />
              <CampoSelect
                rotulo="Andar"
                valor={form.andar}
                aoMudar={campo('andar')}
                opcoes={ANDARES}
                obrigatorio
              />
              <CampoNumero
                rotulo="Capacidade"
                valor={form.capacidade}
                aoMudar={campo('capacidade')}
                min={1}
                obrigatorio
                dica="Número de pessoas. Precisa ser maior que zero."
              />
              <CampoSelect
                rotulo="Tipo"
                valor={form.tipo}
                aoMudar={campo('tipo')}
                opcoes={TIPOS}
                obrigatorio
              />
              <CampoListaTexto
                rotulo="Recursos"
                valores={form.recursos}
                aoMudar={campo('recursos')}
                dica="Separe por vírgula. Ex: projetor, wifi, bancada"
              />
              <CampoCheckbox
                rotulo="Sala acessível"
                valor={form.acessibilidade}
                aoMudar={campo('acessibilidade')}
              />
              {/* A janela é restrição dura: uma sala que fecha ao meio-dia não
                  recebe equipe de período integral. */}
              <CampoTexto
                rotulo="Disponível a partir de"
                valor={disponibilidade.horario_inicio}
                aoMudar={comporDisponibilidade('horario_inicio')}
                dica="Formato HH:MM. A equipe só entra se a janela cobrir o horário dela."
              />
              <CampoTexto
                rotulo="Disponível até"
                valor={disponibilidade.horario_fim}
                aoMudar={comporDisponibilidade('horario_fim')}
                dica="Formato HH:MM"
              />
              <CampoMultiSelect
                rotulo="Dias disponíveis"
                valores={disponibilidade.dias}
                aoMudar={comporDisponibilidade('dias')}
                opcoes={DIAS}
              />
            </div>
            <button type="submit" className="primario" disabled={salvando}>
              {salvando ? 'Salvando…' : form.id ? 'Salvar alterações' : 'Criar sala'}
            </button>
          </form>
        )
      }
    >
      <table className="tabela">
        <thead>
          <tr>
            <th scope="col">Identificação</th>
            <th scope="col">Andar</th>
            <th scope="col">Capacidade</th>
            <th scope="col">Tipo</th>
            <th scope="col">Recursos</th>
            <th scope="col">Acessível</th>
            <th scope="col">Disponível</th>
            <th scope="col">Ações</th>
          </tr>
        </thead>
        <tbody>
          {(salas ?? []).map((sala) => (
            <tr key={sala.id}>
              <th scope="row">{sala.identificacao}</th>
              <td>{sala.andar}</td>
              <td>{sala.capacidade}</td>
              <td>{sala.tipo}</td>
              <td>{sala.recursos.join(', ') || '—'}</td>
              <td>{sala.acessibilidade ? 'Sim' : 'Não'}</td>
              <td>
                {sala.disponibilidade
                  ? `${sala.disponibilidade.horario_inicio}–${sala.disponibilidade.horario_fim}`
                  : '—'}
              </td>
              <td>
                <AcoesLinha
                  aoEditar={() => setForm(sala)}
                  aoExcluir={() => excluir(sala)}
                  confirmacao={
                    `Excluir ${sala.identificacao}?\n\n` +
                    'A sala deixa de existir para o motor. Equipes que a ocupam ' +
                    'hoje ficam sem sala atual, e as restrições ligadas a ela ' +
                    'são removidas junto.'
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
