"""Conflito de horário entre a janela da sala e a faixa exigida pela equipe.

O enunciado lista "conflitos de horário" entre os problemas a resolver e
"conflitos" entre o que a função de otimização deve minimizar. A janela é
tratada como restrição dura: uma sala que fecha ao meio-dia não abriga uma
equipe que trabalha até as 18h — não é questão de preferência.
"""

import pytest

from engine import Cenario, EquipeEntrada, SalaEntrada, otimizar
from engine.restricoes import IndiceRestricoes, avaliar_veto, faixa_horaria


# --------------------------------------------------------------------------
# Interpretação da faixa
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("08:00-18:00", ("08:00", "18:00")),
        (" 09:30 - 17:45 ", ("09:30", "17:45")),
        ("", None),
        ("integral", None),
        ("8-18", None),
        ("08:00", None),
    ],
)
def test_faixa_horaria_interpreta_ou_desiste(entrada, esperado):
    """Formato irreconhecível devolve None: horário mal preenchido deixa de
    restringir, em vez de impedir a alocação por um erro de digitação."""
    assert faixa_horaria(entrada) == esperado


# --------------------------------------------------------------------------
# Restrição dura
# --------------------------------------------------------------------------
def _cenario(horario_equipe, inicio_sala, fim_sala):
    sala = SalaEntrada(
        id=1,
        identificacao="Sala 1",
        andar=1,
        capacidade=20,
        horario_inicio=inicio_sala,
        horario_fim=fim_sala,
    )
    equipe = EquipeEntrada(
        id=1,
        nome="Equipe",
        setor_id=1,
        quantidade_funcionarios=10,
        horario_necessario=horario_equipe,
    )
    return Cenario(salas=(sala,), equipes=(equipe,), restricoes=())


def _veto(cenario):
    return avaliar_veto(
        cenario.equipes[0], cenario.salas[0], IndiceRestricoes(cenario.restricoes)
    )


def test_sala_que_fecha_antes_e_vetada():
    veto = _veto(_cenario("08:00-18:00", "08:00", "12:00"))
    assert veto is not None
    assert veto.restricao == "disponibilidade de horário"
    assert "12:00" in veto.detalhe and "18:00" in veto.detalhe


def test_sala_que_abre_depois_e_vetada():
    veto = _veto(_cenario("07:00-12:00", "08:00", "18:00"))
    assert veto is not None
    assert veto.restricao == "disponibilidade de horário"


def test_janela_que_cobre_exatamente_e_aceita():
    """Limite inclusivo: a sala aberta das 8 às 12 serve a quem precisa das
    8 às 12."""
    assert _veto(_cenario("08:00-12:00", "08:00", "12:00")) is None


def test_janela_mais_ampla_e_aceita():
    assert _veto(_cenario("09:00-17:00", "08:00", "18:00")) is None


def test_equipe_sem_horario_declarado_nao_e_restringida():
    """Cenário que não declara horário não deve ganhar uma restrição que
    ninguém pediu — é o que mantém os testes metamórficos intactos."""
    assert _veto(_cenario("", "08:00", "12:00")) is None


def test_horario_mal_formatado_nao_impede_alocacao():
    assert _veto(_cenario("manhã", "08:00", "12:00")) is None


# --------------------------------------------------------------------------
# Efeito no resultado
# --------------------------------------------------------------------------
def test_equipe_sem_sala_no_horario_vira_alerta_e_nao_alocacao_forcada():
    cenario = _cenario("08:00-18:00", "08:00", "12:00")
    resultado = otimizar(cenario)

    assert resultado.recomendacoes == []
    assert len(resultado.alertas) == 1

    alerta = resultado.alertas[0]
    assert alerta.restricao_nao_atendida == "disponibilidade de horário"
    assert "ampliar a janela" in alerta.encaminhamento


def test_motor_escolhe_a_sala_compativel_no_horario():
    """Entre duas salas idênticas, a única diferença é a janela — e ela decide."""
    cedo = SalaEntrada(
        id=1,
        identificacao="Meio período",
        andar=1,
        capacidade=20,
        horario_inicio="08:00",
        horario_fim="12:00",
    )
    integral = SalaEntrada(
        id=2,
        identificacao="Integral",
        andar=1,
        capacidade=20,
        horario_inicio="08:00",
        horario_fim="18:00",
    )
    equipe = EquipeEntrada(
        id=1,
        nome="Equipe",
        setor_id=1,
        quantidade_funcionarios=18,
        horario_necessario="08:00-18:00",
    )

    resultado = otimizar(Cenario(salas=(cedo, integral), equipes=(equipe,)))
    assert resultado.recomendacoes[0].sala_sugerida == "Integral"


# --------------------------------------------------------------------------
# Dados de demonstração
# --------------------------------------------------------------------------
def test_seed_respeita_a_janela_das_salas_de_meio_periodo(client_com_seed):
    """Sobre os dados de exemplo, nenhuma equipe de período integral pode cair
    numa sala que fecha ao meio-dia."""
    resultado = client_com_seed.post("/api/alocacoes/otimizar", json={}).json()

    salas = {s["identificacao"]: s for s in client_com_seed.get("/api/salas").json()}
    equipes = {e["nome"]: e for e in client_com_seed.get("/api/equipes").json()}

    for rec in resultado["recomendacoes"]:
        sala = salas[rec["sala_sugerida"]]
        equipe = equipes[rec["equipe"]]
        faixa = faixa_horaria(equipe["horario_necessario"])
        if faixa is None:
            continue
        inicio, fim = faixa
        assert sala["disponibilidade"]["horario_inicio"] <= inicio
        assert sala["disponibilidade"]["horario_fim"] >= fim, (
            f"{rec['equipe']} ({equipe['horario_necessario']}) foi alocada em "
            f"{sala['identificacao']}, que fecha às "
            f"{sala['disponibilidade']['horario_fim']}"
        )


def test_alteracao_de_disponibilidade_muda_a_alocacao(client_com_seed):
    """Prova que a janela é entrada real do motor: encolher a disponibilidade
    de uma sala tira dela a equipe que a ocupava."""
    primeira = client_com_seed.post("/api/alocacoes/otimizar", json={}).json()
    escolhida = primeira["recomendacoes"][0]

    sala = client_com_seed.get(f"/api/salas/{escolhida['sala_id']}").json()
    sala["disponibilidade"] = {
        "dias": ["seg"],
        "horario_inicio": "22:00",
        "horario_fim": "23:00",
    }
    assert client_com_seed.put(f"/api/salas/{sala['id']}", json=sala).status_code == 200

    segunda = client_com_seed.post("/api/alocacoes/otimizar", json={}).json()
    nova = next(
        (r for r in segunda["recomendacoes"] if r["equipe_id"] == escolhida["equipe_id"]),
        None,
    )
    if nova is not None:
        assert nova["sala_id"] != escolhida["sala_id"], (
            "a equipe continuou numa sala que agora só abre das 22h às 23h"
        )
