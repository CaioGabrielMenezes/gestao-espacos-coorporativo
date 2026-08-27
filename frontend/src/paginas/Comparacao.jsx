import { useCallback, useEffect, useState } from 'react'
import { api, ultimaExecucaoId } from '../api'
import { Carregando, Erro, Vazio } from '../componentes/Estado'

/**
 * Tela "antes vs depois" (specs/dashboard.md).
 *
 * Os números vêm do bloco `comparativo` que o motor grava em cada execução —
 * nada é calculado aqui, para a tela não poder discordar da governança.
 */

const LINHAS = [
  {
    chave: 'ocupacao_media_percentual',
    rotulo: 'Ocupação média',
    sufixo: '%',
    melhorQuando: 'maior',
  },
  { chave: 'assentos_ociosos', rotulo: 'Assentos ociosos', melhorQuando: 'menor' },
  { chave: 'equipes_alocadas', rotulo: 'Equipes alocadas', melhorQuando: 'maior' },
  { chave: 'equipes_sem_sala', rotulo: 'Equipes sem sala', melhorQuando: 'menor' },
  { chave: 'salas_ocupadas', rotulo: 'Salas ocupadas', melhorQuando: 'neutro' },
  { chave: 'violacoes', rotulo: 'Restrições violadas', melhorQuando: 'menor' },
]

function avaliar(linha, antes, depois) {
  if (linha.melhorQuando === 'neutro' || antes === depois) return 'igual'
  const subiu = depois > antes
  const bom = linha.melhorQuando === 'maior' ? subiu : !subiu
  return bom ? 'melhorou' : 'piorou'
}

function formatarDelta(linha, antes, depois) {
  const delta = Number((depois - antes).toFixed(1))
  if (delta === 0) return '—'
  return `${delta > 0 ? '+' : ''}${delta}${linha.sufixo || ''}`
}

export default function Comparacao() {
  const [comparativo, setComparativo] = useState(null)
  const [execucaoId, setExecucaoId] = useState(null)
  const [erro, setErro] = useState(null)
  const [carregando, setCarregando] = useState(true)

  const carregar = useCallback(async () => {
    setCarregando(true)
    setErro(null)
    try {
      const id = await ultimaExecucaoId()
      setExecucaoId(id)
      if (id) {
        const detalhe = await api.execucao(id)
        setComparativo(detalhe.comparativo)
      }
    } catch (e) {
      setErro(e.message)
    } finally {
      setCarregando(false)
    }
  }, [])

  useEffect(() => {
    carregar()
  }, [carregar])

  if (carregando) return <Carregando />
  if (erro) return <Erro mensagem={erro} aoTentarNovamente={carregar} />
  if (!execucaoId || !comparativo?.antes) {
    return (
      <Vazio>
        Ainda não há execução para comparar. Rode uma otimização na aba
        Recomendações.
      </Vazio>
    )
  }

  const { antes, depois } = comparativo

  return (
    <section>
      <header className="cabecalho-secao">
        <div>
          <h2>Antes e depois</h2>
          <p className="subtitulo">
            Situação atual do prédio contra a proposta da execução #{execucaoId}
          </p>
        </div>
      </header>

      <table className="tabela">
        <thead>
          <tr>
            <th scope="col">Indicador</th>
            <th scope="col">Antes</th>
            <th scope="col">Depois</th>
            <th scope="col">Diferença</th>
          </tr>
        </thead>
        <tbody>
          {LINHAS.map((linha) => {
            const valorAntes = antes[linha.chave]
            const valorDepois = depois[linha.chave]
            const situacao = avaliar(linha, valorAntes, valorDepois)
            return (
              <tr key={linha.chave}>
                <th scope="row">{linha.rotulo}</th>
                <td>
                  {valorAntes}
                  {linha.sufixo}
                </td>
                <td>
                  {valorDepois}
                  {linha.sufixo}
                </td>
                <td className={`delta delta--${situacao}`}>
                  {formatarDelta(linha, valorAntes, valorDepois)}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>

      <p className="rodape-nota">
        "Antes" é a ocupação registrada no cadastro de cada equipe. "Depois" é o
        que o motor recomendou nesta execução — ainda não aplicado ao cadastro.
      </p>
    </section>
  )
}
