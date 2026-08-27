"""Teste metamórfico 4 — Estabilidade (specs/testes-motor.md).

Relação: rodar a mesma entrada duas vezes deve produzir o mesmo resultado.

O motor é inteiramente determinístico — não há sorteio, nem estrutura de dados
com ordem indefinida na tomada de decisão. Este teste é o que impede que uma
mudança futura introduza não-determinismo sem ninguém perceber: um sistema que
recomenda coisas diferentes para a mesma entrada não é auditável, e a
explicabilidade perde o sentido.
"""

import pytest

from engine import otimizar
from tests.metamorphic.conftest import cenarios, descrever


def _assinatura(resultado) -> list[tuple[int, int]]:
    """Alocação completa, em ordem estável: (equipe, sala)."""
    return sorted((rec.equipe_id, rec.sala_id) for rec in resultado.recomendacoes)


@pytest.mark.parametrize("cenario", cenarios(), ids=lambda c: f"{len(c.equipes)}e")
def test_mesma_entrada_produz_mesma_alocacao(cenario):
    primeira = otimizar(cenario)
    segunda = otimizar(cenario)

    if _assinatura(primeira) != _assinatura(segunda):
        diferencas = set(_assinatura(primeira)) ^ set(_assinatura(segunda))
        pytest.fail(
            "PROPRIEDADE METAMÓRFICA 4 VIOLADA (estabilidade): duas execuções da "
            f"mesma entrada produziram alocações diferentes. Pares divergentes "
            f"(equipe, sala): {sorted(diferencas)}.{descrever(cenario)}"
        )


@pytest.mark.parametrize("cenario", cenarios(), ids=lambda c: f"{len(c.equipes)}e")
def test_mesma_entrada_produz_mesmos_alertas_e_metricas(cenario):
    primeira = otimizar(cenario)
    segunda = otimizar(cenario)

    alertas_a = sorted((a.equipe_id, a.restricao_nao_atendida) for a in primeira.alertas)
    alertas_b = sorted((a.equipe_id, a.restricao_nao_atendida) for a in segunda.alertas)

    if alertas_a != alertas_b:
        pytest.fail(
            "PROPRIEDADE METAMÓRFICA 4 VIOLADA (estabilidade): os alertas mudaram "
            f"entre duas execuções idênticas: {alertas_a} contra {alertas_b}."
            f"{descrever(cenario)}"
        )

    if primeira.comparativo.depois != segunda.comparativo.depois:
        pytest.fail(
            "PROPRIEDADE METAMÓRFICA 4 VIOLADA (estabilidade): as métricas "
            f"mudaram entre duas execuções idênticas: "
            f"{primeira.comparativo.depois} contra {segunda.comparativo.depois}."
            f"{descrever(cenario)}"
        )


@pytest.mark.parametrize("cenario", cenarios(quantidade=10, semente=99))
def test_explicabilidade_tambem_e_estavel(cenario):
    """A justificativa mostrada ao coordenador não pode variar entre execuções
    idênticas — é ela que sustenta a decisão perante terceiros."""
    primeira = otimizar(cenario)
    segunda = otimizar(cenario)

    justificativas_a = {r.equipe_id: r.explicabilidade.justificativa for r in primeira.recomendacoes}
    justificativas_b = {r.equipe_id: r.explicabilidade.justificativa for r in segunda.recomendacoes}

    if justificativas_a != justificativas_b:
        divergentes = [
            eid for eid in justificativas_a if justificativas_a[eid] != justificativas_b.get(eid)
        ]
        pytest.fail(
            "PROPRIEDADE METAMÓRFICA 4 VIOLADA (estabilidade): a justificativa "
            f"das equipes {divergentes} mudou entre duas execuções idênticas."
            f"{descrever(cenario)}"
        )
