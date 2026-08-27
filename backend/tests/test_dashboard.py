"""Testes dos indicadores executivos (specs/dashboard.md)."""

import pytest


@pytest.fixture()
def indicadores(client_com_seed):
    resposta = client_com_seed.get("/api/dashboard/indicadores")
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def test_traz_todos_os_indicadores_exigidos_pela_spec(indicadores):
    predio = indicadores["predio"]
    for campo in (
        "total_salas",
        "salas_ocupadas",
        "salas_disponiveis",
        "capacidade_total",
        "capacidade_disponivel",
        "ocupacao_predio_percentual",
        "utilizacao_salas_percentual",
    ):
        assert campo in predio, f"falta o indicador '{campo}'"

    assert "funcionarios_alocados" in indicadores["pessoas"]
    assert "funcionarios_nao_alocados" in indicadores["pessoas"]
    assert "nao_alocadas" in indicadores["equipes"]
    assert "restricoes_violadas" in indicadores


def test_estado_atual_reflete_o_arranjo_inicial_do_seed(indicadores):
    """O seed deixa 11 equipes posicionadas e a Operações Delta sem sala."""
    assert indicadores["origem"] == "estado_atual"
    assert indicadores["predio"]["total_salas"] == 18
    assert indicadores["equipes"]["total"] == 12
    assert indicadores["equipes"]["alocadas"] == 11
    assert indicadores["equipes"]["nao_alocadas"] == 1


def test_as_tres_taxas_medem_coisas_diferentes(indicadores):
    """Ocupação do prédio, utilização das salas e aproveitamento não podem ser
    o mesmo número — confundi-las é o erro clássico de um painel de ocupação."""
    predio = indicadores["predio"]
    ocupacao = predio["ocupacao_predio_percentual"]
    utilizacao = predio["utilizacao_salas_percentual"]
    aproveitamento = predio["aproveitamento_percentual"]

    assert len({ocupacao, utilizacao, aproveitamento}) == 3, (
        f"as três taxas colapsaram no mesmo valor: {ocupacao}, {utilizacao}, "
        f"{aproveitamento}"
    )
    # O aproveitamento das salas em uso é sempre >= à ocupação do prédio,
    # porque ignora as salas vazias.
    assert aproveitamento >= ocupacao


def test_soma_dos_andares_reconcilia_com_o_total(indicadores):
    """Se as parcelas por andar não fecham com o total, o painel mente."""
    por_andar = indicadores["por_andar"]

    assert sum(a["salas"] for a in por_andar) == indicadores["predio"]["total_salas"]
    assert (
        sum(a["capacidade"] for a in por_andar)
        == indicadores["predio"]["capacidade_total"]
    )
    assert (
        sum(a["pessoas"] for a in por_andar)
        == indicadores["pessoas"]["funcionarios_alocados"]
    )
    assert (
        sum(a["salas_ocupadas"] for a in por_andar)
        == indicadores["predio"]["salas_ocupadas"]
    )


def test_cobre_os_nove_andares(indicadores):
    andares = [a["andar"] for a in indicadores["por_andar"]]
    assert andares == list(range(1, 10))


def test_capacidade_disponivel_e_o_complemento_da_em_uso(indicadores):
    predio = indicadores["predio"]
    assert (
        predio["capacidade_em_uso"] + predio["capacidade_disponivel"]
        == predio["capacidade_total"]
    )
    assert predio["salas_ocupadas"] + predio["salas_disponiveis"] == predio["total_salas"]


def test_funcionarios_nao_alocados_batem_com_a_equipe_sem_sala(indicadores):
    """A Operações Delta tem 92 pessoas e não cabe em nenhuma sala."""
    assert indicadores["pessoas"]["funcionarios_nao_alocados"] == 92


def test_projecao_de_execucao_difere_do_estado_atual(client_com_seed):
    atual = client_com_seed.get("/api/dashboard/indicadores").json()
    execucao_id = client_com_seed.post("/api/alocacoes/otimizar", json={}).json()[
        "governanca"
    ]["execucao_id"]

    projetado = client_com_seed.get(
        "/api/dashboard/indicadores", params={"execucao_id": execucao_id}
    ).json()

    assert projetado["origem"] == "execucao"
    assert projetado["execucao_id"] == execucao_id
    # A otimização tem de melhorar o aproveitamento; se não melhorasse, não
    # haveria razão para existir.
    assert (
        projetado["predio"]["aproveitamento_percentual"]
        > atual["predio"]["aproveitamento_percentual"]
    )
    assert (
        projetado["predio"]["assentos_ociosos"] < atual["predio"]["assentos_ociosos"]
    )


def test_atalho_da_ultima_execucao(client_com_seed):
    client_com_seed.post("/api/alocacoes/otimizar", json={})
    resposta = client_com_seed.get("/api/dashboard/indicadores/ultima-execucao")
    assert resposta.status_code == 200
    assert resposta.json()["origem"] == "execucao"


def test_atalho_sem_nenhuma_execucao_cai_no_estado_atual(client_com_seed):
    """Base recém-populada: o dashboard renderiza em vez de dar 404."""
    resposta = client_com_seed.get("/api/dashboard/indicadores/ultima-execucao")
    assert resposta.status_code == 200
    assert resposta.json()["origem"] == "estado_atual"


def test_execucao_inexistente_retorna_404(client_com_seed):
    resposta = client_com_seed.get(
        "/api/dashboard/indicadores", params={"execucao_id": 999}
    )
    assert resposta.status_code == 404


def test_banco_vazio_nao_quebra(client):
    resposta = client.get("/api/dashboard/indicadores")
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["predio"]["total_salas"] == 0
    assert corpo["predio"]["ocupacao_predio_percentual"] == 0.0
    assert corpo["por_andar"] == []
