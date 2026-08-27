"""Teste metamórfico 2 — Remoção de restrição (specs/testes-motor.md).

Relação: remover uma restrição não pode reduzir o espaço de soluções — a nova
execução não deve alocar menos equipes por causa disso.

Remover uma restrição dura só acrescenta arestas ao grafo de viabilidade, e o
emparelhamento máximo é monótono em relação a isso. O teste existe para
garantir que nenhuma camada acima (busca local, montagem do resultado) quebre
essa monotonicidade.
"""

import pytest

from engine import otimizar
from tests.metamorphic.conftest import cenarios, descrever

# Cenários com pelo menos uma restrição — nos demais o teste não tem o que remover.
CENARIOS_COM_RESTRICAO = [c for c in cenarios() if c.restricoes]


@pytest.mark.parametrize("cenario", CENARIOS_COM_RESTRICAO)
def test_remover_uma_restricao_nunca_reduz_equipes_alocadas(cenario):
    antes = otimizar(cenario)

    for restricao in cenario.restricoes:
        relaxado = cenario.sem_restricao(restricao.id)
        depois = otimizar(relaxado)

        if depois.governanca.equipes_alocadas < antes.governanca.equipes_alocadas:
            pytest.fail(
                "PROPRIEDADE METAMÓRFICA 2 VIOLADA (remoção de restrição): "
                f"remover a restrição '{restricao.tipo}' "
                f"(parâmetro {restricao.parametro}) reduziu as equipes alocadas de "
                f"{antes.governanca.equipes_alocadas} para "
                f"{depois.governanca.equipes_alocadas}. Relaxar uma exigência só "
                f"pode ampliar o espaço de soluções.{descrever(cenario)}"
            )


@pytest.mark.parametrize("cenario", CENARIOS_COM_RESTRICAO)
def test_remover_todas_as_restricoes_maximiza_alocacao(cenario):
    """Sem restrição alguma, o resultado é o teto: nenhuma execução restrita
    pode superá-lo."""
    antes = otimizar(cenario)

    sem_restricoes = cenario
    for restricao in cenario.restricoes:
        sem_restricoes = sem_restricoes.sem_restricao(restricao.id)
    teto = otimizar(sem_restricoes)

    if teto.governanca.equipes_alocadas < antes.governanca.equipes_alocadas:
        pytest.fail(
            "PROPRIEDADE METAMÓRFICA 2 VIOLADA (remoção de restrição): o cenário "
            f"sem nenhuma restrição alocou {teto.governanca.equipes_alocadas} "
            f"equipes, menos que as {antes.governanca.equipes_alocadas} do cenário "
            f"restrito.{descrever(cenario)}"
        )
