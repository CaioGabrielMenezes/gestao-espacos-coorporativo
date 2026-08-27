import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import Card from '../componentes/Card'
import { Carregando, Erro, Vazio } from '../componentes/Estado'

/**
 * Monitoramento do motor (specs/dashboard.md).
 *
 * Responde à pergunta da demonstração: "como sabemos que é confiável?".
 * Todos os números aqui vêm do registro de governança persistido — inclusive
 * a contagem de erros, que só é honesta porque execuções que falham também
 * ficam gravadas.
 */
export default function Monitoramento() {
  const [execucoes, setExecucoes] = useState([])
  const [totais, setTotais] = useState(null)
  const [erro, setErro] = useState(null)
  const [carregando, setCarregando] = useState(true)

  const carregar = useCallback(async () => {
    setCarregando(true)
    setErro(null)
    try {
      const [lista, contagens] = await Promise.all([
        api.execucoes(),
        api.totaisIntervencao(),
      ])
      setExecucoes(lista)
      setTotais(contagens)
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
  if (!execucoes.length) {
    return <Vazio>Nenhuma execução registrada ainda.</Vazio>
  }

  const ultima = execucoes[0]
  const taxa = ultima.equipes_analisadas
    ? Math.round((ultima.equipes_alocadas / ultima.equipes_analisadas) * 100)
    : 0

  return (
    <section>
      <header className="cabecalho-secao">
        <div>
          <h2>Monitoramento do motor</h2>
          <p className="subtitulo">
            Última execução: #{ultima.execucao_id} por {ultima.usuario} ·{' '}
            {new Date(ultima.timestamp).toLocaleString('pt-BR')}
          </p>
        </div>
        <button type="button" onClick={carregar}>
          Atualizar
        </button>
      </header>

      <div className="grade-cards">
        <Card
          rotulo="Tempo da última otimização"
          valor={ultima.duracao_ms}
          unidade=" ms"
          destaque
        />
        <Card rotulo="Taxa de alocação" valor={taxa} unidade="%" />
        <Card rotulo="Ocupação prevista" valor={ultima.ocupacao_prevista} />
        <Card
          rotulo="Restrições violadas"
          valor={ultima.restricoes_violadas}
          destaque={ultima.restricoes_violadas > 0}
        />
        <Card
          rotulo="Intervenções manuais"
          valor={totais?.total ?? 0}
          nota={
            totais && Object.keys(totais.por_acao).length
              ? Object.entries(totais.por_acao)
                  .map(([acao, n]) => `${acao}: ${n}`)
                  .join(' · ')
              : 'nenhuma até agora'
          }
        />
        <Card
          rotulo="Execuções com erro"
          valor={totais?.execucoes_com_erro ?? 0}
          destaque={(totais?.execucoes_com_erro ?? 0) > 0}
        />
        <Card rotulo="Algoritmo" valor={ultima.algoritmo} />
        <Card rotulo="Execuções registradas" valor={execucoes.length} />
      </div>

      <h3>Pesos vigentes na última execução</h3>
      <p className="subtitulo">
        Gravados junto com a execução: uma decisão antiga continua
        interpretável mesmo depois de a função de score ser recalibrada.
      </p>
      <div className="etiquetas">
        {Object.entries(ultima.pesos || {}).map(([nome, valor]) => (
          <span key={nome} className="etiqueta">
            {nome.replace('_', ' ')}: {valor}
          </span>
        ))}
      </div>

      <h3>Histórico de execuções</h3>
      <table className="tabela">
        <thead>
          <tr>
            <th scope="col">#</th>
            <th scope="col">Quando</th>
            <th scope="col">Usuário</th>
            <th scope="col">Alocadas</th>
            <th scope="col">Sem sala</th>
            <th scope="col">Violações</th>
            <th scope="col">Ocupação</th>
            <th scope="col">Tempo</th>
          </tr>
        </thead>
        <tbody>
          {execucoes.map((e) => (
            <tr key={e.execucao_id}>
              <td>{e.execucao_id}</td>
              <td>{new Date(e.timestamp).toLocaleString('pt-BR')}</td>
              <td>{e.usuario}</td>
              <td>{e.equipes_alocadas}</td>
              <td>{e.equipes_nao_alocadas}</td>
              <td>{e.restricoes_violadas}</td>
              <td>{e.ocupacao_prevista}</td>
              <td>{e.duracao_ms} ms</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
