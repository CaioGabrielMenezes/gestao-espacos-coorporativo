"""Teste metamórfico 1 — Expansão de capacidade (specs/testes-motor.md).

Relação: acrescentar uma sala nova ao conjunto, sem alterar mais nada, não
pode diminuir a quantidade de equipes alocadas.

É a propriedade que pega o erro mais traiçoeiro de um otimizador: melhorar a
entrada e piorar a saída. Heurísticas gulosas violam isso com facilidade —
uma sala a mais muda as escolhas iniciais e cascateia num resultado pior.
"""

import pytest

from engine import otimizar
from engine.modelos import SalaEntrada
from tests.metamorphic.conftest import cenarios, descrever


def _sala_extra(cenario, capacidade: int, andar: int = 1) -> SalaEntrada:
    novo_id = max((s.id for s in cenario.salas), default=0) + 1
    return SalaEntrada(
        id=novo_id,
        identificacao=f"Sala extra {novo_id}",
        andar=andar,
        capacidade=capacidade,
        tipo="projeto",
        # Recursos abundantes e acessível: a sala nova não deve restringir nada.
        recursos=frozenset(
            {"projetor", "wifi", "quadro", "tv", "bancada", "rede_isolada", "som"}
        ),
        acessibilidade=True,
    )


@pytest.mark.parametrize("cenario", cenarios(), ids=lambda c: f"{len(c.equipes)}e")
def test_acrescentar_sala_nunca_reduz_equipes_alocadas(cenario):
    antes = otimizar(cenario)

    # Uma sala grande o bastante para caber qualquer equipe do cenário.
    maior_equipe = max(e.quantidade_funcionarios for e in cenario.equipes)
    ampliado = cenario.com_sala(_sala_extra(cenario, capacidade=maior_equipe + 10))
    depois = otimizar(ampliado)

    if depois.governanca.equipes_alocadas < antes.governanca.equipes_alocadas:
        pytest.fail(
            "PROPRIEDADE METAMÓRFICA 1 VIOLADA (expansão de capacidade): "
            f"acrescentar uma sala reduziu as equipes alocadas de "
            f"{antes.governanca.equipes_alocadas} para "
            f"{depois.governanca.equipes_alocadas}. Acrescentar recurso jamais "
            f"pode piorar o resultado.{descrever(cenario)}"
        )


@pytest.mark.parametrize("cenario", cenarios(), ids=lambda c: f"{len(c.equipes)}e")
def test_acrescentar_sala_pequena_tambem_nunca_reduz(cenario):
    """Variante: a sala nova pode ser inútil, mas nunca prejudicial."""
    antes = otimizar(cenario)
    ampliado = cenario.com_sala(_sala_extra(cenario, capacidade=1))
    depois = otimizar(ampliado)

    if depois.governanca.equipes_alocadas < antes.governanca.equipes_alocadas:
        pytest.fail(
            "PROPRIEDADE METAMÓRFICA 1 VIOLADA (expansão de capacidade): "
            f"acrescentar uma sala de capacidade 1 — inútil para qualquer equipe — "
            f"reduziu as alocações de {antes.governanca.equipes_alocadas} para "
            f"{depois.governanca.equipes_alocadas}.{descrever(cenario)}"
        )


@pytest.mark.parametrize("cenario", cenarios(quantidade=15, semente=7))
def test_acrescentar_varias_salas_e_monotono(cenario):
    """A propriedade tem de valer a cada passo, não só no primeiro."""
    atual = cenario
    alocadas = otimizar(atual).governanca.equipes_alocadas

    for passo in range(3):
        atual = atual.com_sala(_sala_extra(atual, capacidade=30 + passo * 10))
        novo_total = otimizar(atual).governanca.equipes_alocadas

        if novo_total < alocadas:
            pytest.fail(
                "PROPRIEDADE METAMÓRFICA 1 VIOLADA (expansão de capacidade): "
                f"no passo {passo + 1} de expansão, as alocações caíram de "
                f"{alocadas} para {novo_total}.{descrever(cenario)}"
            )
        alocadas = novo_total
