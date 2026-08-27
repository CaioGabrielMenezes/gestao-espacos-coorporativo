import { useCallback, useEffect, useState } from 'react'
import { api, ultimaExecucaoId } from '../api'
import { Carregando, Erro, Vazio } from '../componentes/Estado'

/**
 * Lista de recomendações com explicabilidade e intervenção humana.
 *
 * Critério de aceite da spec: a explicação tem de estar a UM clique da lista.
 * Por isso a linha expande no lugar, sem navegação — e os botões de decisão
 * ficam junto da explicação, não antes dela: aceitar algo sem ver o porquê é
 * exatamente o que a explicabilidade existe para evitar.
 */

const ROTULO_STATUS = {
  sugerida: 'Sugerida',
  aceita: 'Aceita',
  rejeitada: 'Rejeitada',
  editada: 'Editada à mão',
}

function Explicabilidade({ dados }) {
  return (
    <div className="explicacao">
      <p className="explicacao__justificativa">{dados.justificativa}</p>

      <dl className="explicacao__grade">
        <div>
          <dt>Capacidade da sala</dt>
          <dd>{dados.capacidade_sala} lugares</dd>
        </div>
        <div>
          <dt>Tamanho da equipe</dt>
          <dd>{dados.tamanho_equipe} pessoas</dd>
        </div>
        <div>
          <dt>Ocupação prevista</dt>
          <dd>{dados.ocupacao_prevista}</dd>
        </div>
        <div>
          <dt>Alternativas avaliadas</dt>
          <dd>{dados.alternativas_avaliadas}</dd>
        </div>
        <div>
          <dt>Recursos atendidos</dt>
          <dd>{dados.recursos_atendidos ? 'sim' : 'não'}</dd>
        </div>
        <div>
          <dt>Restrição de andar</dt>
          <dd>{dados.restricao_andar_atendida ? 'atendida' : 'não atendida'}</dd>
        </div>
      </dl>

      <div className="explicacao__criterios">
        <span className="explicacao__score">Score {dados.score} / 100</span>
        {Object.entries(dados.criterios || {}).map(([nome, valor]) => (
          <span key={nome} className="etiqueta">
            {nome.replace('_', ' ')}: {valor}
          </span>
        ))}
      </div>
    </div>
  )
}

export default function Recomendacoes() {
  const [execucao, setExecucao] = useState(null)
  const [salas, setSalas] = useState([])
  const [expandida, setExpandida] = useState(null)
  const [erro, setErro] = useState(null)
  const [aviso, setAviso] = useState(null)
  const [carregando, setCarregando] = useState(true)
  const [ocupado, setOcupado] = useState(false)

  const carregar = useCallback(async () => {
    setCarregando(true)
    setErro(null)
    try {
      const [id, listaSalas] = await Promise.all([ultimaExecucaoId(), api.salas()])
      setSalas(listaSalas)
      setExecucao(id ? await api.execucao(id) : null)
    } catch (e) {
      setErro(e.message)
    } finally {
      setCarregando(false)
    }
  }, [])

  useEffect(() => {
    carregar()
  }, [carregar])

  async function executar(acao) {
    setOcupado(true)
    setAviso(null)
    setErro(null)
    try {
      await acao()
      await carregar()
    } catch (e) {
      // Erro de uma ação não pode apagar a lista já carregada: mostramos o
      // problema e mantemos a tela utilizável.
      setAviso(e.message)
    } finally {
      setOcupado(false)
    }
  }

  const otimizar = () => executar(() => api.otimizar())
  const reotimizar = () =>
    executar(() => api.reotimizar(execucao.governanca.execucao_id))

  if (carregando) return <Carregando />
  if (erro) return <Erro mensagem={erro} aoTentarNovamente={carregar} />

  if (!execucao) {
    return (
      <section>
        <header className="cabecalho-secao">
          <h2>Recomendações</h2>
        </header>
        <Vazio>Nenhuma otimização executada ainda.</Vazio>
        <button type="button" className="primario" onClick={otimizar} disabled={ocupado}>
          {ocupado ? 'Otimizando…' : 'Gerar alocação otimizada'}
        </button>
      </section>
    )
  }

  const { governanca, recomendacoes, alertas } = execucao
  const salasOcupadas = new Set(
    recomendacoes.filter((r) => r.status !== 'rejeitada').map((r) => r.sala_id)
  )

  return (
    <section>
      <header className="cabecalho-secao">
        <div>
          <h2>Recomendações</h2>
          <p className="subtitulo">
            Execução #{governanca.execucao_id} · {governanca.equipes_alocadas} de{' '}
            {governanca.equipes_analisadas} equipes alocadas · {governanca.duracao_ms}
            {' ms'}
          </p>
        </div>
        <div className="acoes">
          <button type="button" onClick={otimizar} disabled={ocupado}>
            Nova otimização
          </button>
          <button type="button" className="primario" onClick={reotimizar} disabled={ocupado}>
            Re-otimizar mantendo decisões
          </button>
        </div>
      </header>

      {aviso && <p className="aviso aviso--erro">{aviso}</p>}

      {alertas.length > 0 && (
        <div className="alertas">
          <h3>Equipes sem sala ({alertas.length})</h3>
          {alertas.map((a) => (
            <div key={a.equipe_id} className="alerta">
              <strong>{a.equipe_afetada}</strong>
              <span className="etiqueta etiqueta--alerta">
                {a.restricao_nao_atendida}
              </span>
              <p>{a.causa}</p>
              <p className="alerta__encaminhamento">
                Encaminhamento sugerido: {a.encaminhamento}
              </p>
            </div>
          ))}
        </div>
      )}

      <h3>Alocações propostas ({recomendacoes.length})</h3>
      <ul className="lista-recomendacoes">
        {recomendacoes.map((r) => {
          const aberta = expandida === r.id
          return (
            <li key={r.id} className={`recomendacao recomendacao--${r.status}`}>
              <button
                type="button"
                className="recomendacao__linha"
                aria-expanded={aberta}
                onClick={() => setExpandida(aberta ? null : r.id)}
              >
                <span className="recomendacao__equipe">{r.equipe}</span>
                <span className="recomendacao__sala">
                  {r.sala_sugerida} · andar {r.andar}
                </span>
                <span className="recomendacao__ocupacao">
                  {r.pessoas}/{r.capacidade} · {r.ocupacao_percentual}%
                </span>
                <span className={`etiqueta etiqueta--${r.status}`}>
                  {ROTULO_STATUS[r.status] || r.status}
                </span>
                <span aria-hidden="true">{aberta ? '▲' : '▼'}</span>
              </button>

              {aberta && (
                <div className="recomendacao__detalhe">
                  <Explicabilidade dados={r.explicabilidade} />

                  <div className="acoes-intervencao">
                    <button
                      type="button"
                      onClick={() => executar(() => api.aceitar(r.id))}
                      disabled={ocupado || r.status === 'aceita'}
                    >
                      Aceitar
                    </button>
                    <button
                      type="button"
                      onClick={() => executar(() => api.rejeitar(r.id))}
                      disabled={ocupado || r.status === 'rejeitada'}
                    >
                      Rejeitar
                    </button>
                    <label className="editar">
                      Mover para:
                      <select
                        defaultValue=""
                        disabled={ocupado}
                        onChange={(evento) => {
                          const salaId = Number(evento.target.value)
                          if (salaId) executar(() => api.editar(r.id, salaId))
                        }}
                      >
                        <option value="">escolha uma sala…</option>
                        {salas
                          .filter(
                            (s) =>
                              s.capacidade >= r.pessoas &&
                              (!salasOcupadas.has(s.id) || s.id === r.sala_id)
                          )
                          .map((s) => (
                            <option key={s.id} value={s.id}>
                              {s.identificacao} · andar {s.andar} · {s.capacidade}{' '}
                              lugares
                            </option>
                          ))}
                      </select>
                    </label>
                  </div>
                </div>
              )}
            </li>
          )
        })}
      </ul>
    </section>
  )
}
