"""Testes da intervenção humana (specs/motor-alocacao.md).

O que se verifica aqui não é só "o botão funciona", mas que toda decisão
humana deixa rastro auditável e que a re-otimização a respeita.
"""

import pytest


@pytest.fixture()
def execucao(client_com_seed):
    resultado = client_com_seed.post("/api/alocacoes/otimizar", json={}).json()
    return resultado["governanca"]["execucao_id"]


@pytest.fixture()
def alocacoes(client_com_seed, execucao):
    return client_com_seed.get(f"/api/alocacoes/execucoes/{execucao}").json()[
        "recomendacoes"
    ]


def _por_equipe(alocacoes, nome):
    return next(a for a in alocacoes if a["equipe"] == nome)


# --------------------------------------------------------------------------
# Aceitar e rejeitar
# --------------------------------------------------------------------------
def test_aceitar_muda_status_e_registra_intervencao(client_com_seed, execucao, alocacoes):
    alvo = alocacoes[0]
    resposta = client_com_seed.post(
        f"/api/alocacoes/{alvo['id']}/aceitar",
        json={"usuario": "ana", "justificativa": "conferido com o setor"},
    )
    assert resposta.status_code == 200, resposta.text

    intervencao = resposta.json()
    assert intervencao["acao"] == "aceitar"
    assert intervencao["usuario"] == "ana"
    assert intervencao["justificativa"] == "conferido com o setor"
    assert intervencao["detalhe"]["para"]["status"] == "aceita"

    detalhe = client_com_seed.get(f"/api/alocacoes/execucoes/{execucao}").json()
    assert _por_equipe(detalhe["recomendacoes"], alvo["equipe"])["status"] == "aceita"


def test_rejeitar_muda_status_e_registra_intervencao(client_com_seed, execucao, alocacoes):
    alvo = alocacoes[0]
    resposta = client_com_seed.post(f"/api/alocacoes/{alvo['id']}/rejeitar", json={})
    assert resposta.status_code == 200
    assert resposta.json()["acao"] == "rejeitar"

    detalhe = client_com_seed.get(f"/api/alocacoes/execucoes/{execucao}").json()
    assert _por_equipe(detalhe["recomendacoes"], alvo["equipe"])["status"] == "rejeitada"


def test_alocacao_inexistente_retorna_404(client_com_seed):
    assert client_com_seed.post("/api/alocacoes/999/aceitar", json={}).status_code == 404


# --------------------------------------------------------------------------
# Edição manual
# --------------------------------------------------------------------------
def test_editar_move_a_equipe_e_recalcula_ocupacao(client_com_seed, alocacoes):
    salas = client_com_seed.get("/api/salas").json()
    alvo = _por_equipe(alocacoes, "Marketing")  # 12 pessoas
    ocupadas = {a["sala_id"] for a in alocacoes}
    destino = next(
        s for s in salas if s["id"] not in ocupadas and s["capacidade"] >= 12
    )

    resposta = client_com_seed.put(
        f"/api/alocacoes/{alvo['id']}", json={"sala_id": destino["id"]}
    )
    assert resposta.status_code == 200, resposta.text

    detalhe = resposta.json()["detalhe"]
    assert detalhe["de"]["sala_id"] == alvo["sala_id"]
    assert detalhe["para"]["sala_id"] == destino["id"]
    assert detalhe["para"]["ocupacao_percentual"] == round(12 / destino["capacidade"] * 100, 1)


def test_editar_para_sala_pequena_demais_e_bloqueado(client_com_seed, alocacoes):
    """Capacidade é impossibilidade física: nem a decisão humana passa por cima."""
    salas = client_com_seed.get("/api/salas").json()
    alvo = _por_equipe(alocacoes, "Suporte N1")  # 55 pessoas
    pequena = next(s for s in salas if s["capacidade"] < 55)

    resposta = client_com_seed.put(
        f"/api/alocacoes/{alvo['id']}", json={"sala_id": pequena["id"]}
    )
    assert resposta.status_code == 422, resposta.text
    assert "capacidade" in resposta.json()["detail"].lower()


def test_editar_para_sala_ja_ocupada_e_bloqueado(client_com_seed, alocacoes):
    alvo = _por_equipe(alocacoes, "Marketing")
    outra = next(a for a in alocacoes if a["id"] != alvo["id"] and a["capacidade"] >= 12)

    resposta = client_com_seed.put(
        f"/api/alocacoes/{alvo['id']}", json={"sala_id": outra["sala_id"]}
    )
    assert resposta.status_code == 409, resposta.text


def test_editar_ferindo_restricao_nao_critica_passa_mas_registra_aviso(
    client_com_seed, alocacoes
):
    """A Pesquisa Aplicada só pode ficar nos andares 3 e 6. Mandá-la para
    outro andar é permitido — o coordenador pode saber algo que o cadastro
    não sabe — mas fica registrado."""
    salas = client_com_seed.get("/api/salas").json()
    alvo = _por_equipe(alocacoes, "Pesquisa Aplicada")  # 22 pessoas
    ocupadas = {a["sala_id"] for a in alocacoes}
    fora_do_andar = next(
        s
        for s in salas
        if s["id"] not in ocupadas and s["capacidade"] >= 22 and s["andar"] not in (3, 6)
    )

    resposta = client_com_seed.put(
        f"/api/alocacoes/{alvo['id']}", json={"sala_id": fora_do_andar["id"]}
    )
    assert resposta.status_code == 200, resposta.text

    avisos = resposta.json()["detalhe"]["avisos"]
    assert avisos, "a violação de andar deveria ter sido registrada como aviso"
    assert "andar" in avisos[0].lower()


# --------------------------------------------------------------------------
# Re-otimização
# --------------------------------------------------------------------------
def test_reotimizar_preserva_alocacao_aceita(client_com_seed, execucao, alocacoes):
    """Critério de aceite da spec: re-otimizar depois de intervenção manual
    não pode jogar fora o que o coordenador já decidiu."""
    alvo = _por_equipe(alocacoes, "Marketing")
    client_com_seed.post(f"/api/alocacoes/{alvo['id']}/aceitar", json={})

    nova = client_com_seed.post(f"/api/alocacoes/execucoes/{execucao}/reotimizar", json={})
    assert nova.status_code == 200, nova.text

    recomendacao = next(
        r for r in nova.json()["recomendacoes"] if r["equipe"] == "Marketing"
    )
    assert recomendacao["sala_id"] == alvo["sala_id"], (
        "a alocação aceita foi movida pela re-otimização"
    )


def test_reotimizar_preserva_edicao_manual(client_com_seed, execucao, alocacoes):
    salas = client_com_seed.get("/api/salas").json()
    alvo = _por_equipe(alocacoes, "Marketing")
    ocupadas = {a["sala_id"] for a in alocacoes}
    destino = next(s for s in salas if s["id"] not in ocupadas and s["capacidade"] >= 12)

    client_com_seed.put(f"/api/alocacoes/{alvo['id']}", json={"sala_id": destino["id"]})
    nova = client_com_seed.post(f"/api/alocacoes/execucoes/{execucao}/reotimizar", json={})

    recomendacao = next(
        r for r in nova.json()["recomendacoes"] if r["equipe"] == "Marketing"
    )
    assert recomendacao["sala_id"] == destino["id"]


def test_reotimizar_sem_intervencao_alguma_equivale_a_otimizar(client_com_seed, execucao):
    nova = client_com_seed.post(f"/api/alocacoes/execucoes/{execucao}/reotimizar", json={})
    assert nova.status_code == 200
    assert nova.json()["governanca"]["equipes_alocadas"] == 11


def test_recomendacao_rejeitada_sai_dos_indicadores(client_com_seed, execucao, alocacoes):
    antes = client_com_seed.get(
        "/api/dashboard/indicadores", params={"execucao_id": execucao}
    ).json()

    alvo = alocacoes[0]
    client_com_seed.post(f"/api/alocacoes/{alvo['id']}/rejeitar", json={})

    depois = client_com_seed.get(
        "/api/dashboard/indicadores", params={"execucao_id": execucao}
    ).json()
    assert depois["equipes"]["alocadas"] == antes["equipes"]["alocadas"] - 1


# --------------------------------------------------------------------------
# Trilha de auditoria
# --------------------------------------------------------------------------
def test_intervencoes_ficam_listadas_na_execucao(client_com_seed, execucao, alocacoes):
    client_com_seed.post(f"/api/alocacoes/{alocacoes[0]['id']}/aceitar", json={})
    client_com_seed.post(f"/api/alocacoes/{alocacoes[1]['id']}/rejeitar", json={})

    listadas = client_com_seed.get(
        f"/api/alocacoes/execucoes/{execucao}/intervencoes"
    ).json()
    assert [i["acao"] for i in listadas] == ["aceitar", "rejeitar"]
    assert all(i["timestamp"] for i in listadas)
    assert all(i["detalhe"]["equipe"] for i in listadas)


def test_contador_alimenta_a_area_de_monitoramento(client_com_seed, execucao, alocacoes):
    client_com_seed.post(f"/api/alocacoes/{alocacoes[0]['id']}/aceitar", json={})
    client_com_seed.post(f"/api/alocacoes/{alocacoes[1]['id']}/aceitar", json={})
    client_com_seed.post(f"/api/alocacoes/{alocacoes[2]['id']}/rejeitar", json={})

    total = client_com_seed.get("/api/alocacoes/intervencoes/total").json()
    assert total["total"] == 3
    assert total["por_acao"] == {"aceitar": 2, "rejeitar": 1}
    assert total["execucoes_com_erro"] == 0
