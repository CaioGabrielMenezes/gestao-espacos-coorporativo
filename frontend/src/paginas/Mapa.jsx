import { useCallback, useEffect, useState } from 'react'
import { api, ultimaExecucaoId } from '../api'
import { Carregando, Erro, Vazio } from '../componentes/Estado'

/**
 * Planta do prédio.
 *
 * A cor comunica a faixa de ocupação, mas nunca sozinha: cada sala mostra o
 * percentual escrito e a faixa por extenso. Depender só de cor tornaria a tela
 * inútil para quem não as distingue, e ilegível num projetor ruim — que é
 * exatamente onde ela vai ser mostrada.
 */

const LEGENDA = [
  { faixa: 'vazia', rotulo: 'Vazia', ajuda: 'Nenhuma equipe alocada' },
  { faixa: 'subutilizada', rotulo: 'Subutilizada', ajuda: 'Menos de 50% ocupada' },
  { faixa: 'adequada', rotulo: 'Adequada', ajuda: 'Entre 50% e 85%' },
  { faixa: 'cheia', rotulo: 'Cheia', ajuda: '85% ou mais' },
]

export default function Mapa() {
  const [mapa, setMapa] = useState(null)
  const [verProposto, setVerProposto] = useState(false)
  const [temExecucao, setTemExecucao] = useState(false)
  const [erro, setErro] = useState(null)
  const [carregando, setCarregando] = useState(true)

  const carregar = useCallback(async () => {
    setCarregando(true)
    setErro(null)
    try {
      const id = await ultimaExecucaoId()
      setTemExecucao(Boolean(id))
      setMapa(verProposto && id ? await api.mapa(id) : await api.mapa())
    } catch (e) {
      setErro(e.message)
    } finally {
      setCarregando(false)
    }
  }, [verProposto])

  useEffect(() => {
    carregar()
  }, [carregar])

  if (carregando) return <Carregando />
  if (erro) return <Erro mensagem={erro} aoTentarNovamente={carregar} />
  if (!mapa?.andares.length) {
    return <Vazio>Nenhuma sala cadastrada — não há prédio para desenhar.</Vazio>
  }

  return (
    <section>
      <header className="cabecalho-secao">
        <div>
          <h2>Mapa do prédio</h2>
          <p className="subtitulo">
            {mapa.origem === 'execucao'
              ? `Distribuição proposta pela execução #${mapa.execucao_id}`
              : 'Ocupação atual, como está hoje no cadastro'}
          </p>
        </div>
        {temExecucao && (
          <div className="alternador" role="group" aria-label="Origem dos dados">
            <button
              type="button"
              className={!verProposto ? 'ativo' : ''}
              onClick={() => setVerProposto(false)}
            >
              Hoje
            </button>
            <button
              type="button"
              className={verProposto ? 'ativo' : ''}
              onClick={() => setVerProposto(true)}
            >
              Proposto
            </button>
          </div>
        )}
      </header>

      <ul className="legenda">
        {LEGENDA.map((item) => (
          <li key={item.faixa}>
            <span className={`amostra amostra--${item.faixa}`} aria-hidden="true" />
            <strong>{item.rotulo}</strong>
            <small>{item.ajuda}</small>
          </li>
        ))}
      </ul>

      <div className="mapa">
        {/* Andares de cima para baixo, como se olha um prédio de fora. */}
        {[...mapa.andares].reverse().map((andar) => (
          <section key={andar.andar} className="mapa__andar">
            <header className="mapa__rotulo-andar">
              <strong>Andar {andar.andar}</strong>
              <small>
                {andar.pessoas}/{andar.capacidade} lugares ·{' '}
                {andar.ocupacao_percentual}%
              </small>
            </header>

            <div className="mapa__salas">
              {andar.salas.map((sala) => (
                <article
                  key={sala.sala_id}
                  className={`sala sala--${sala.faixa}`}
                  aria-label={
                    `${sala.identificacao}, ${sala.faixa}, ` +
                    (sala.equipe
                      ? `${sala.equipe}, ${sala.pessoas} de ${sala.capacidade} lugares`
                      : `vazia, ${sala.capacidade} lugares`)
                  }
                >
                  <header>
                    <strong>{sala.identificacao}</strong>
                    {sala.acessibilidade && (
                      <span title="Sala acessível" aria-label="acessível">
                        ♿
                      </span>
                    )}
                  </header>

                  <p className="sala__equipe">{sala.equipe ?? 'Livre'}</p>

                  <footer>
                    <span className="sala__numeros">
                      {sala.pessoas}/{sala.capacidade}
                    </span>
                    <span className="sala__percentual">
                      {sala.ocupacao_percentual}%
                    </span>
                  </footer>
                </article>
              ))}
            </div>
          </section>
        ))}
      </div>
    </section>
  )
}
