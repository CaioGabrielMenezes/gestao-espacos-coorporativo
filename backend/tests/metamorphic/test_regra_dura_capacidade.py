"""Regra dura — Capacidade (specs/testes-motor.md).

Nenhuma recomendação pode alocar mais pessoas do que a capacidade da sala.
Esta é a única regra do sistema que não admite exceção nem ponderação: violá-la
significa recomendar algo fisicamente impossível.
"""

import pytest

from engine import otimizar
from tests.metamorphic.conftest import cenarios, descrever


@pytest.mark.parametrize("cenario", cenarios(), ids=lambda c: f"{len(c.equipes)}e")
def test_nenhuma_sala_recebe_mais_pessoas_que_a_capacidade(cenario):
    resultado = otimizar(cenario)

    for rec in resultado.recomendacoes:
        if rec.pessoas > rec.capacidade:
            pytest.fail(
                f"REGRA DURA DE CAPACIDADE VIOLADA: a equipe '{rec.equipe}' tem "
                f"{rec.pessoas} pessoas e foi alocada em {rec.sala_sugerida}, que "
                f"comporta {rec.capacidade}."
                f"{descrever(cenario)}"
            )


@pytest.mark.parametrize("cenario", cenarios(), ids=lambda c: f"{len(c.equipes)}e")
def test_nenhuma_sala_recebe_duas_equipes(cenario):
    """Corolário do modelo de ocupação exclusiva: uma sala, uma equipe."""
    resultado = otimizar(cenario)
    salas_usadas = [rec.sala_id for rec in resultado.recomendacoes]

    if len(salas_usadas) != len(set(salas_usadas)):
        repetidas = {s for s in salas_usadas if salas_usadas.count(s) > 1}
        pytest.fail(
            f"OCUPAÇÃO EXCLUSIVA VIOLADA: as salas {repetidas} receberam mais de "
            f"uma equipe na mesma execução.{descrever(cenario)}"
        )


@pytest.mark.parametrize("cenario", cenarios(), ids=lambda c: f"{len(c.equipes)}e")
def test_toda_equipe_nao_alocada_tem_alerta(cenario):
    """Critério de aceite da spec: nenhuma equipe fica 'sumida' do resultado."""
    resultado = otimizar(cenario)

    alocadas = {rec.equipe_id for rec in resultado.recomendacoes}
    alertadas = {alerta.equipe_id for alerta in resultado.alertas}
    todas = {e.id for e in cenario.equipes}

    sem_destino = todas - alocadas - alertadas
    if sem_destino:
        nomes = [e.nome for e in cenario.equipes if e.id in sem_destino]
        pytest.fail(
            f"RASTREABILIDADE VIOLADA: as equipes {nomes} não foram alocadas nem "
            f"geraram alerta — desapareceram do resultado.{descrever(cenario)}"
        )

    sobreposicao = alocadas & alertadas
    if sobreposicao:
        pytest.fail(
            f"INCONSISTÊNCIA: as equipes {sobreposicao} aparecem simultaneamente "
            f"como alocadas e como alerta.{descrever(cenario)}"
        )


@pytest.mark.parametrize("cenario", cenarios(), ids=lambda c: f"{len(c.equipes)}e")
def test_toda_recomendacao_tem_explicabilidade_completa(cenario):
    """Critério de aceite: 100% das recomendações explicam a decisão."""
    resultado = otimizar(cenario)

    for rec in resultado.recomendacoes:
        exp = rec.explicabilidade
        if not exp.justificativa.strip():
            pytest.fail(
                f"EXPLICABILIDADE INCOMPLETA: recomendação de '{rec.equipe}' sem "
                f"justificativa.{descrever(cenario)}"
            )
        if exp.alternativas_avaliadas < 1:
            pytest.fail(
                f"EXPLICABILIDADE INCOMPLETA: '{rec.equipe}' declara "
                f"{exp.alternativas_avaliadas} alternativas avaliadas, mas foi "
                f"alocada — deveria haver ao menos a sala escolhida."
                f"{descrever(cenario)}"
            )
