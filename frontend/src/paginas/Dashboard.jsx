import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import BarraOcupacao from '../componentes/BarraOcupacao'
import Card from '../componentes/Card'
import { Carregando, Erro } from '../componentes/Estado'

/**
 * Dashboard executivo (specs/dashboard.md).
 *
 * O seletor "hoje / proposto" existe porque os dois números respondem a
 * perguntas diferentes: como o prédio está, e como ficaria se a recomendação
 * do motor fosse aceita. Misturá-los num painel só engana quem decide.
 */
export default function Dashboard() {
  const [visao, setVisao] = useState('atual')
  const [dados, setDados] = useState(null)
  const [erro, setErro] = useState(null)
  const [carregando, setCarregando] = useState(true)

  const carregar = useCallback(async () => {
    setCarregando(true)
    setErro(null)
    try {
      setDados(
        visao === 'atual'
          ? await api.indicadores()
          : await api.indicadoresUltimaExecucao()
      )
    } catch (e) {
      setErro(e.message)
    } finally {
      setCarregando(false)
    }
  }, [visao])

  useEffect(() => {
    carregar()
  }, [carregar])

  if (carregando) return <Carregando />
  if (erro) return <Erro mensagem={erro} aoTentarNovamente={carregar} />
  if (!dados) return null

  const { predio, pessoas, equipes, por_andar: porAndar } = dados
  const semExecucao = visao === 'proposto' && dados.origem === 'estado_atual'

  return (
    <section>
      <header className="cabecalho-secao">
        <div>
          <h2>Ocupação do prédio</h2>
          <p className="subtitulo">
            {dados.origem === 'execucao'
              ? `Projeção da execução #${dados.execucao_id}`
              : 'Situação atual, antes de qualquer otimização'}
          </p>
        </div>
        <div className="alternador" role="group" aria-label="Visão dos dados">
          <button
            type="button"
            className={visao === 'atual' ? 'ativo' : ''}
            onClick={() => setVisao('atual')}
          >
            Hoje
          </button>
          <button
            type="button"
            className={visao === 'proposto' ? 'ativo' : ''}
            onClick={() => setVisao('proposto')}
          >
            Proposto
          </button>
        </div>
      </header>

      {semExecucao && (
        <p className="aviso">
          Nenhuma otimização foi executada ainda — mostrando a situação atual.
          Rode uma otimização na aba <strong>Recomendações</strong>.
        </p>
      )}

      <div className="grade-cards">
        <Card
          rotulo="Ocupação do prédio"
          valor={predio.ocupacao_predio_percentual}
          unidade="%"
          nota="pessoas ÷ capacidade total"
          destaque
        />
        <Card
          rotulo="Utilização das salas"
          valor={predio.utilizacao_salas_percentual}
          unidade="%"
          nota={`${predio.salas_ocupadas} de ${predio.total_salas} salas em uso`}
        />
        <Card
          rotulo="Aproveitamento"
          valor={predio.aproveitamento_percentual}
          unidade="%"
          nota="preenchimento das salas em uso"
        />
        <Card
          rotulo="Assentos ociosos"
          valor={predio.assentos_ociosos}
          nota="lugares vagos nas salas ocupadas"
        />
        <Card
          rotulo="Capacidade disponível"
          valor={predio.capacidade_disponivel}
          nota={`de ${predio.capacidade_total} lugares no prédio`}
        />
        <Card rotulo="Salas disponíveis" valor={predio.salas_disponiveis} />
        <Card
          rotulo="Funcionários alocados"
          valor={pessoas.funcionarios_alocados}
          nota={`de ${pessoas.total_funcionarios} no total`}
        />
        <Card
          rotulo="Funcionários sem sala"
          valor={pessoas.funcionarios_nao_alocados}
          destaque={pessoas.funcionarios_nao_alocados > 0}
        />
        <Card
          rotulo="Equipes sem sala"
          valor={equipes.nao_alocadas}
          nota={`${equipes.alocadas} de ${equipes.total} alocadas`}
          destaque={equipes.nao_alocadas > 0}
        />
        <Card
          rotulo="Restrições violadas"
          valor={dados.restricoes_violadas}
          destaque={dados.restricoes_violadas > 0}
        />
      </div>

      <h3>Ocupação por andar</h3>
      <div className="lista-andares">
        {porAndar.map((a) => (
          <BarraOcupacao
            key={a.andar}
            rotulo={`Andar ${a.andar}`}
            percentual={a.ocupacao_percentual}
            detalhe={
              `${a.pessoas} pessoas · ${a.salas_ocupadas}/${a.salas} salas em uso · ` +
              `${a.capacidade} lugares`
            }
          />
        ))}
      </div>
    </section>
  )
}
