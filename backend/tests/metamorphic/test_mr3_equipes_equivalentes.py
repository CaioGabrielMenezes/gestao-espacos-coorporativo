"""Teste metamórfico 3 — Equipes equivalentes (specs/testes-motor.md).

Relação: duas equipes com requisitos idênticos, diferindo só no nome, não
devem produzir diferença relevante na qualidade global da solução.

É a propriedade que detecta o motor "prendendo" em algo que não deveria
importar — o nome da equipe, a ordem em que ela chegou no cadastro, o id que o
banco sorteou. Um sistema que decide com base nisso é injusto de forma
invisível: duas equipes iguais recebendo tratamento diferente.
"""

from dataclasses import replace

import pytest

from engine import otimizar
from engine.modelos import Cenario
from tests.metamorphic.conftest import cenarios, descrever


def _com_clone(cenario: Cenario) -> tuple[Cenario, int, int]:
    """Acrescenta uma cópia da primeira equipe, idêntica exceto id e nome."""
    original = cenario.equipes[0]
    novo_id = max(e.id for e in cenario.equipes) + 1
    clone = replace(original, id=novo_id, nome=f"{original.nome} (equivalente)")
    return replace(cenario, equipes=cenario.equipes + (clone,)), original.id, novo_id


def _trocar_nomes(cenario: Cenario, id_a: int, id_b: int) -> Cenario:
    nomes = {e.id: e.nome for e in cenario.equipes}
    equipes = tuple(
        replace(e, nome=nomes[id_b])
        if e.id == id_a
        else replace(e, nome=nomes[id_a])
        if e.id == id_b
        else e
        for e in cenario.equipes
    )
    return replace(cenario, equipes=equipes)


def _qualidade(resultado) -> tuple:
    """A "qualidade global" comparada pela propriedade."""
    return (
        resultado.governanca.equipes_alocadas,
        resultado.comparativo.depois.ocupacao_media_percentual,
        resultado.comparativo.depois.assentos_ociosos,
        resultado.governanca.restricoes_violadas,
    )


@pytest.mark.parametrize("cenario", cenarios(), ids=lambda c: f"{len(c.equipes)}e")
def test_trocar_nomes_de_equipes_equivalentes_nao_muda_a_qualidade(cenario):
    base, id_a, id_b = _com_clone(cenario)

    original = otimizar(base)
    trocado = otimizar(_trocar_nomes(base, id_a, id_b))

    if _qualidade(original) != _qualidade(trocado):
        pytest.fail(
            "PROPRIEDADE METAMÓRFICA 3 VIOLADA (equipes equivalentes): trocar o "
            f"nome de duas equipes idênticas mudou a qualidade global de "
            f"{_qualidade(original)} para {_qualidade(trocado)} "
            f"(alocadas, ocupação %, assentos ociosos, violações). O nome da "
            f"equipe não pode influenciar a decisão.{descrever(cenario)}"
        )


@pytest.mark.parametrize("cenario", cenarios(), ids=lambda c: f"{len(c.equipes)}e")
def test_equipes_equivalentes_recebem_salas_de_mesma_qualidade(cenario):
    """Se as duas equivalentes forem alocadas, nenhuma pode ser privilegiada:
    o par de salas atribuído tem de ser o mesmo, não importa qual ficou com qual."""
    base, id_a, id_b = _com_clone(cenario)

    original = otimizar(base)
    trocado = otimizar(_trocar_nomes(base, id_a, id_b))

    def salas_do_par(resultado):
        return sorted(
            rec.sala_id for rec in resultado.recomendacoes if rec.equipe_id in (id_a, id_b)
        )

    if salas_do_par(original) != salas_do_par(trocado):
        pytest.fail(
            "PROPRIEDADE METAMÓRFICA 3 VIOLADA (equipes equivalentes): o par de "
            f"equipes idênticas recebeu as salas {salas_do_par(original)} numa "
            f"execução e {salas_do_par(trocado)} na outra, mudando apenas os nomes."
            f"{descrever(cenario)}"
        )


@pytest.mark.parametrize("cenario", cenarios(quantidade=15, semente=11))
def test_ordem_de_cadastro_nao_altera_a_qualidade(cenario):
    """Companheiro da propriedade: a ordem em que as equipes aparecem na
    entrada não pode mudar o resultado global."""
    original = otimizar(cenario)
    invertido = otimizar(replace(cenario, equipes=tuple(reversed(cenario.equipes))))

    if _qualidade(original) != _qualidade(invertido):
        pytest.fail(
            "PROPRIEDADE METAMÓRFICA 3 VIOLADA (equipes equivalentes): inverter a "
            f"ordem de cadastro das equipes mudou a qualidade global de "
            f"{_qualidade(original)} para {_qualidade(invertido)}. A ordem de "
            f"entrada não é informação de negócio.{descrever(cenario)}"
        )
