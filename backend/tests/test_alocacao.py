"""Testes da API de alocação e dos critérios de aceite de
specs/motor-alocacao.md."""

from time import perf_counter

import pytest

from engine import Cenario, EquipeEntrada, SalaEntrada, otimizar


# --------------------------------------------------------------------------
# Endpoint de otimização sobre os dados de seed
# --------------------------------------------------------------------------
@pytest.fixture()
def resultado(client_com_seed):
    resposta = client_com_seed.post("/api/alocacoes/otimizar", json={})
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def test_otimizacao_aloca_todas_as_equipes_que_cabem(resultado):
    """11 das 12 equipes do seed têm sala compatível; a Operações Delta não."""
    assert resultado["governanca"]["equipes_alocadas"] == 11
    assert resultado["governanca"]["equipes_nao_alocadas"] == 1


def test_equipe_grande_demais_vira_alerta_e_nao_alocacao_forcada(resultado):
    """Critério central da spec: nunca forçar alocação para 'fechar' o número."""
    alertas = resultado["alertas"]
    assert len(alertas) == 1

    alerta = alertas[0]
    assert alerta["equipe_afetada"] == "Operações Delta"
    assert alerta["status"] == "ALERTA"
    assert alerta["restricao_nao_atendida"] == "capacidade mínima"
    assert "80" in alerta["causa"] and "92" in alerta["causa"]
    assert alerta["encaminhamento"]

    alocadas = {r["equipe"] for r in resultado["recomendacoes"]}
    assert "Operações Delta" not in alocadas


def test_concorrencia_por_sala_unica_e_resolvida_globalmente(resultado):
    """Suporte N1 só cabe na Sala 501, que é também a preferida do
    Desenvolvimento A. Um algoritmo guloso por prioridade deixaria uma das duas
    sem sala; o emparelhamento máximo acomoda ambas."""
    por_equipe = {r["equipe"]: r for r in resultado["recomendacoes"]}

    assert "Suporte N1" in por_equipe, "Suporte N1 ficou sem sala"
    assert "Desenvolvimento A" in por_equipe, "Desenvolvimento A ficou sem sala"
    assert por_equipe["Suporte N1"]["sala_sugerida"] == "Sala 501"


def test_nenhuma_recomendacao_excede_a_capacidade(resultado):
    for rec in resultado["recomendacoes"]:
        assert rec["pessoas"] <= rec["capacidade"], rec


def test_todas_as_recomendacoes_tem_explicabilidade_completa(resultado):
    campos = {
        "sala",
        "equipe",
        "capacidade_sala",
        "tamanho_equipe",
        "ocupacao_prevista",
        "recursos_atendidos",
        "restricao_andar_atendida",
        "alternativas_avaliadas",
        "justificativa",
    }
    for rec in resultado["recomendacoes"]:
        exp = rec["explicabilidade"]
        assert campos.issubset(exp.keys()), f"faltam campos em {rec['equipe']}"
        assert exp["justificativa"].strip()
        assert exp["alternativas_avaliadas"] >= 1


def test_comparativo_antes_depois_mostra_ganho_real(resultado):
    """Critério de aceite do dashboard: números reais, não mockados."""
    antes = resultado["comparativo"]["antes"]
    depois = resultado["comparativo"]["depois"]

    assert antes["ocupacao_media_percentual"] > 0, "estado inicial não foi carregado"
    assert depois["ocupacao_media_percentual"] > antes["ocupacao_media_percentual"]
    assert depois["assentos_ociosos"] < antes["assentos_ociosos"]


def test_execucao_fica_registrada_na_governanca(client_com_seed):
    client_com_seed.post("/api/alocacoes/otimizar", json={"usuario": "coordenadora-ana"})

    execucoes = client_com_seed.get("/api/alocacoes/execucoes").json()
    assert len(execucoes) == 1

    registro = execucoes[0]
    assert registro["usuario"] == "coordenadora-ana"
    assert registro["algoritmo"] == "allocation-engine-v1"
    assert registro["equipes_analisadas"] == 12
    assert registro["salas_analisadas"] == 18
    assert registro["duracao_ms"] > 0
    # Os pesos vigentes ficam gravados junto: a decisão pode ser reinterpretada
    # depois mesmo que a função de score mude.
    assert registro["pesos"]["ocupacao"] > 0


def test_detalhe_da_execucao_traz_recomendacoes_e_alertas(client_com_seed):
    execucao_id = client_com_seed.post("/api/alocacoes/otimizar", json={}).json()[
        "governanca"
    ]["execucao_id"]
    assert execucao_id is not None

    detalhe = client_com_seed.get(f"/api/alocacoes/execucoes/{execucao_id}").json()
    assert len(detalhe["recomendacoes"]) == 11
    assert len(detalhe["alertas"]) == 1
    assert detalhe["recomendacoes"][0]["explicabilidade"]["justificativa"]
    assert detalhe["comparativo"]["antes"]["ocupacao_media_percentual"] > 0


def test_execucoes_sucessivas_acumulam_historico(client_com_seed):
    for _ in range(3):
        client_com_seed.post("/api/alocacoes/otimizar", json={})
    assert len(client_com_seed.get("/api/alocacoes/execucoes").json()) == 3


def test_execucao_inexistente_retorna_404(client_com_seed):
    assert client_com_seed.get("/api/alocacoes/execucoes/999").status_code == 404


def test_otimizar_sem_dados_nao_quebra(client):
    """Banco vazio: resultado vazio e coerente, não erro 500."""
    resposta = client.post("/api/alocacoes/otimizar", json={})
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["recomendacoes"] == []
    assert corpo["alertas"] == []
    assert corpo["governanca"]["equipes_analisadas"] == 0


# --------------------------------------------------------------------------
# Desempenho — teto definido na spec
# --------------------------------------------------------------------------
def test_otimizacao_de_grande_porte_fica_abaixo_de_5_segundos():
    """A spec pede um teto de tempo para a demonstração. 100 equipes e 120
    salas é bem acima do prédio real de 9 andares do enunciado."""
    salas = tuple(
        SalaEntrada(
            id=i + 1,
            identificacao=f"Sala {i + 1}",
            andar=(i % 9) + 1,
            capacidade=10 + (i % 12) * 8,
            recursos=frozenset({"wifi"} if i % 2 else {"wifi", "projetor"}),
            acessibilidade=i % 3 == 0,
        )
        for i in range(120)
    )
    equipes = tuple(
        EquipeEntrada(
            id=i + 1,
            nome=f"Equipe {i + 1}",
            setor_id=(i % 8) + 1,
            quantidade_funcionarios=5 + (i % 20) * 4,
            requisitos_especiais=frozenset({"wifi"}),
            prioridade=("baixa", "media", "alta", "critica")[i % 4],
        )
        for i in range(100)
    )

    inicio = perf_counter()
    resultado = otimizar(Cenario(salas=salas, equipes=equipes, restricoes=()))
    decorrido = perf_counter() - inicio

    assert decorrido < 5.0, (
        f"A otimização levou {decorrido:.2f}s, acima do teto de 5s definido na spec."
    )
    assert resultado.governanca.equipes_alocadas > 0
