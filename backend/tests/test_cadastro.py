"""Testes dos critérios de aceite de specs/cadastro.md."""

from tests.conftest import nova_equipe, nova_sala


# --------------------------------------------------------------------------
# Critério: não é possível cadastrar sala com capacidade <= 0
# --------------------------------------------------------------------------
def test_sala_com_capacidade_zero_e_rejeitada(client):
    resposta = client.post("/api/salas", json=nova_sala(capacidade=0))
    assert resposta.status_code == 422, resposta.text


def test_sala_com_capacidade_negativa_e_rejeitada(client):
    resposta = client.post("/api/salas", json=nova_sala(capacidade=-5))
    assert resposta.status_code == 422, resposta.text


def test_sala_fora_dos_nove_andares_e_rejeitada(client):
    assert client.post("/api/salas", json=nova_sala(andar=0)).status_code == 422
    assert client.post("/api/salas", json=nova_sala(andar=10)).status_code == 422


def test_identificacao_de_sala_e_unica(client):
    assert client.post("/api/salas", json=nova_sala()).status_code == 201
    duplicada = client.post("/api/salas", json=nova_sala(capacidade=20))
    assert duplicada.status_code == 409, duplicada.text


def test_ciclo_completo_da_sala(client):
    criada = client.post("/api/salas", json=nova_sala()).json()
    sala_id = criada["id"]

    assert client.get(f"/api/salas/{sala_id}").json()["capacidade"] == 45

    editada = client.put(f"/api/salas/{sala_id}", json=nova_sala(capacidade=60))
    assert editada.status_code == 200
    assert editada.json()["capacidade"] == 60

    assert client.delete(f"/api/salas/{sala_id}").status_code == 204
    assert client.get(f"/api/salas/{sala_id}").status_code == 404


# --------------------------------------------------------------------------
# Critério: não é possível cadastrar equipe sem setor associado
# --------------------------------------------------------------------------
def test_equipe_em_setor_inexistente_retorna_404(client):
    resposta = client.post("/api/setores/999/equipes", json=nova_equipe())
    assert resposta.status_code == 404, resposta.text


def test_equipe_criada_sempre_tem_setor(client, setor_id):
    resposta = client.post(f"/api/setores/{setor_id}/equipes", json=nova_equipe())
    assert resposta.status_code == 201, resposta.text
    assert resposta.json()["setor_id"] == setor_id


def test_equipe_com_zero_funcionarios_e_rejeitada(client, setor_id):
    resposta = client.post(
        f"/api/setores/{setor_id}/equipes", json=nova_equipe(quantidade_funcionarios=0)
    )
    assert resposta.status_code == 422, resposta.text


def test_mover_equipe_para_setor_inexistente_retorna_404(client, setor_id):
    equipe = client.post(f"/api/setores/{setor_id}/equipes", json=nova_equipe()).json()
    resposta = client.put(
        f"/api/equipes/{equipe['id']}", json=nova_equipe(setor_id=999)
    )
    assert resposta.status_code == 404, resposta.text


def test_remover_setor_remove_equipes_em_cascata(client, setor_id):
    client.post(f"/api/setores/{setor_id}/equipes", json=nova_equipe())
    assert client.delete(f"/api/setores/{setor_id}").status_code == 204
    # Nenhuma equipe órfã sobrevive à remoção do setor.
    assert client.get("/api/equipes").json() == []


# --------------------------------------------------------------------------
# Critério: restrições ficam disponíveis para o allocation-engine via API
# --------------------------------------------------------------------------
def test_restricao_e_recuperada_com_parametro_integro(client, setor_id):
    equipe = client.post(f"/api/setores/{setor_id}/equipes", json=nova_equipe()).json()

    criada = client.post(
        "/api/restricoes",
        json={
            "tipo": "andar_permitido",
            "equipe_id": equipe["id"],
            "parametro": {"andares": [3, 6]},
        },
    )
    assert criada.status_code == 201, criada.text

    listadas = client.get("/api/restricoes", params={"tipo": "andar_permitido"}).json()
    assert len(listadas) == 1
    assert listadas[0]["parametro"] == {"andares": [3, 6]}
    assert listadas[0]["equipe_id"] == equipe["id"]


def test_restricao_com_alvo_do_tipo_errado_e_rejeitada(client):
    sala = client.post("/api/salas", json=nova_sala()).json()
    # acessibilidade_obrigatoria se aplica a equipe, não a sala.
    resposta = client.post(
        "/api/restricoes",
        json={"tipo": "acessibilidade_obrigatoria", "sala_id": sala["id"]},
    )
    assert resposta.status_code == 422, resposta.text


def test_restricao_sem_alvo_e_rejeitada(client):
    resposta = client.post(
        "/api/restricoes", json={"tipo": "capacidade_minima", "parametro": {"valor": 10}}
    )
    assert resposta.status_code == 422, resposta.text


def test_restricao_sem_parametro_obrigatorio_e_rejeitada(client, setor_id):
    equipe = client.post(f"/api/setores/{setor_id}/equipes", json=nova_equipe()).json()
    resposta = client.post(
        "/api/restricoes",
        json={"tipo": "capacidade_minima", "equipe_id": equipe["id"], "parametro": {}},
    )
    assert resposta.status_code == 422, resposta.text


def test_restricao_apontando_para_equipe_inexistente_retorna_404(client):
    resposta = client.post(
        "/api/restricoes",
        json={
            "tipo": "capacidade_minima",
            "equipe_id": 999,
            "parametro": {"valor": 10},
        },
    )
    assert resposta.status_code == 404, resposta.text


# --------------------------------------------------------------------------
# Critério: seed cobre 9 andares, >= 15 salas e >= 10 equipes
# --------------------------------------------------------------------------
def test_seed_cobre_os_nove_andares(client_com_seed):
    salas = client_com_seed.get("/api/salas").json()
    assert len(salas) >= 15
    assert {sala["andar"] for sala in salas} == set(range(1, 10))


def test_seed_tem_equipes_de_tamanhos_variados(client_com_seed):
    equipes = client_com_seed.get("/api/equipes").json()
    assert len(equipes) >= 10
    tamanhos = [e["quantidade_funcionarios"] for e in equipes]
    assert min(tamanhos) < 10 and max(tamanhos) > 50


def test_seed_prepara_equipe_que_nao_cabe_em_nenhuma_sala(client_com_seed):
    """Cenário exigido por specs/motor-alocacao.md: o motor precisa ter um caso
    real de exceção para tratar, em vez de forçar uma alocação inválida."""
    maior_sala = max(s["capacidade"] for s in client_com_seed.get("/api/salas").json())
    equipes = client_com_seed.get("/api/equipes").json()
    sem_sala = [e for e in equipes if e["quantidade_funcionarios"] > maior_sala]
    assert sem_sala, "seed deveria conter ao menos uma equipe maior que a maior sala"


def test_seed_cobre_todos_os_tipos_de_restricao(client_com_seed):
    restricoes = client_com_seed.get("/api/restricoes").json()
    assert len({r["tipo"] for r in restricoes}) == 8


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}
