"""Testes do mapa do prédio e dos metadados de restrição."""

from app.enums import TipoRestricao
from app.schemas import CAMPOS_PARAMETRO, DESCRITOR_CAMPO


# --------------------------------------------------------------------------
# GET /api/restricoes/tipos
# --------------------------------------------------------------------------
def test_tipos_cobrem_todos_os_tipos_do_enum(client):
    """Se alguém acrescentar um tipo de restrição, ele aparece aqui sozinho —
    e o formulário do frontend passa a oferecê-lo sem nenhuma alteração de JS."""
    tipos = client.get("/api/restricoes/tipos").json()
    assert {t["tipo"] for t in tipos} == {t.value for t in TipoRestricao}


def test_todo_campo_exigido_tem_descritor():
    """Trava de consistência interna: um tipo novo com um parâmetro novo, mas
    sem descritor, quebraria a montagem do formulário em tempo de execução.
    Aqui isso falha no teste, antes de chegar na tela."""
    exigidos = {campo for campos in CAMPOS_PARAMETRO.values() for campo in campos}
    faltando = exigidos - set(DESCRITOR_CAMPO)
    assert not faltando, f"campos sem descritor de formulário: {faltando}"


def test_metadados_batem_com_a_validacao_real(client):
    """O endpoint promete um alvo e certos campos; a criação de restrição tem
    de aceitar exatamente isso. É o contrato que o formulário vai seguir."""
    tipos = {t["tipo"]: t for t in client.get("/api/restricoes/tipos").json()}

    info = tipos["andar_permitido"]
    assert info["alvo"] == "equipe"
    assert [c["nome"] for c in info["campos"]] == ["andares"]

    info = tipos["sala_reservada_setor"]
    assert info["alvo"] == "sala"
    assert [c["nome"] for c in info["campos"]] == ["setor_id"]

    info = tipos["acessibilidade_obrigatoria"]
    assert info["alvo"] == "equipe"
    assert info["campos"] == []


def test_todo_tipo_tem_rotulo_legivel(client):
    for t in client.get("/api/restricoes/tipos").json():
        assert t["rotulo"] and t["rotulo"] != t["tipo"]
        for campo in t["campos"]:
            assert campo["rotulo"] and campo["tipo"]


# --------------------------------------------------------------------------
# GET /api/dashboard/mapa
# --------------------------------------------------------------------------
def test_mapa_cobre_os_nove_andares(client_com_seed):
    mapa = client_com_seed.get("/api/dashboard/mapa").json()
    assert [a["andar"] for a in mapa["andares"]] == list(range(1, 10))
    assert mapa["origem"] == "estado_atual"


def test_mapa_lista_todas_as_salas_sem_repetir(client_com_seed):
    mapa = client_com_seed.get("/api/dashboard/mapa").json()
    ids = [s["sala_id"] for a in mapa["andares"] for s in a["salas"]]
    assert len(ids) == 18
    assert len(set(ids)) == 18


def test_sala_ocupada_mostra_a_equipe_e_a_vazia_nao(client_com_seed):
    mapa = client_com_seed.get("/api/dashboard/mapa").json()
    salas = [s for a in mapa["andares"] for s in a["salas"]]

    ocupadas = [s for s in salas if s["equipe"] is not None]
    vazias = [s for s in salas if s["equipe"] is None]
    assert ocupadas and vazias, "o seed deve ter salas ocupadas e vazias"

    for sala in ocupadas:
        assert sala["pessoas"] > 0
        assert sala["faixa"] != "vazia"
    for sala in vazias:
        assert sala["pessoas"] == 0
        assert sala["faixa"] == "vazia"


def test_pessoas_por_andar_reconciliam_com_as_salas(client_com_seed):
    """Se as parcelas não fecham com o total, o mapa mente."""
    mapa = client_com_seed.get("/api/dashboard/mapa").json()
    for andar in mapa["andares"]:
        assert andar["pessoas"] == sum(s["pessoas"] for s in andar["salas"])
        assert andar["capacidade"] == sum(s["capacidade"] for s in andar["salas"])


def test_mapa_reconcilia_com_os_indicadores(client_com_seed):
    """As duas telas mostram o mesmo prédio: os totais têm de bater."""
    mapa = client_com_seed.get("/api/dashboard/mapa").json()
    indicadores = client_com_seed.get("/api/dashboard/indicadores").json()

    pessoas_no_mapa = sum(a["pessoas"] for a in mapa["andares"])
    assert pessoas_no_mapa == indicadores["pessoas"]["funcionarios_alocados"]

    ocupadas_no_mapa = sum(
        1 for a in mapa["andares"] for s in a["salas"] if s["equipe"] is not None
    )
    assert ocupadas_no_mapa == indicadores["predio"]["salas_ocupadas"]


def test_mapa_de_execucao_difere_do_estado_atual(client_com_seed):
    execucao_id = client_com_seed.post("/api/alocacoes/otimizar", json={}).json()[
        "governanca"
    ]["execucao_id"]

    atual = client_com_seed.get("/api/dashboard/mapa").json()
    proposto = client_com_seed.get(
        f"/api/dashboard/mapa?execucao_id={execucao_id}"
    ).json()

    assert proposto["origem"] == "execucao"
    assert proposto["execucao_id"] == execucao_id

    def ocupacao(mapa):
        return {
            s["identificacao"]: s["equipe"]
            for a in mapa["andares"]
            for s in a["salas"]
        }

    assert ocupacao(atual) != ocupacao(proposto), (
        "a otimização deveria reorganizar o prédio em relação ao estado inicial"
    )


def test_mapa_da_ultima_execucao_sem_execucao_cai_no_estado_atual(client_com_seed):
    mapa = client_com_seed.get("/api/dashboard/mapa/ultima-execucao").json()
    assert mapa["origem"] == "estado_atual"


def test_mapa_da_ultima_execucao_usa_a_mais_recente(client_com_seed):
    client_com_seed.post("/api/alocacoes/otimizar", json={})
    segunda = client_com_seed.post("/api/alocacoes/otimizar", json={}).json()[
        "governanca"
    ]["execucao_id"]

    mapa = client_com_seed.get("/api/dashboard/mapa/ultima-execucao").json()
    assert mapa["execucao_id"] == segunda


def test_faixas_classificam_a_ocupacao(client_com_seed):
    execucao_id = client_com_seed.post("/api/alocacoes/otimizar", json={}).json()[
        "governanca"
    ]["execucao_id"]
    mapa = client_com_seed.get(f"/api/dashboard/mapa?execucao_id={execucao_id}").json()

    for sala in (s for a in mapa["andares"] for s in a["salas"]):
        ocupacao = sala["ocupacao_percentual"]
        if sala["equipe"] is None:
            esperada = "vazia"
        elif ocupacao < 50:
            esperada = "subutilizada"
        elif ocupacao < 85:
            esperada = "adequada"
        else:
            esperada = "cheia"
        assert sala["faixa"] == esperada, f"{sala['identificacao']} com {ocupacao}%"


def test_mapa_de_execucao_inexistente_retorna_404(client_com_seed):
    assert client_com_seed.get("/api/dashboard/mapa?execucao_id=999").status_code == 404


def test_mapa_sem_salas_nao_quebra(client):
    mapa = client.get("/api/dashboard/mapa").json()
    assert mapa["andares"] == []
