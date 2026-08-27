"""Fixtures dos testes de cadastro.

Cada teste roda contra um SQLite temporário próprio: a DATABASE_URL é
definida antes de qualquer import de `app`, então o engine do módulo
app.database já nasce apontando para o arquivo descartável.
"""

import os
import tempfile
from pathlib import Path

import pytest

_tmp_dir = tempfile.mkdtemp(prefix="cadastro-testes-")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_tmp_dir) / 'teste.db'}"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import povoar  # noqa: E402


@pytest.fixture()
def client():
    """Banco limpo e vazio a cada teste."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def client_com_seed():
    """Banco carregado com os dados de seed."""
    povoar(reset=True)
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def setor_id(client):
    resposta = client.post(
        "/api/setores",
        json={"nome": "Tecnologia", "coordenador": "Ana", "total_funcionarios": 30},
    )
    assert resposta.status_code == 201
    return resposta.json()["id"]


def nova_sala(**overrides) -> dict:
    base = {
        "identificacao": "Sala 704",
        "andar": 7,
        "capacidade": 45,
        "tipo": "projeto",
        "recursos": ["projetor"],
        "acessibilidade": False,
    }
    base.update(overrides)
    return base


def nova_equipe(**overrides) -> dict:
    base = {
        "nome": "Desenvolvimento A",
        "quantidade_funcionarios": 42,
        "horario_necessario": "08:00-18:00",
        "requisitos_especiais": ["projetor"],
        "prioridade": "alta",
    }
    base.update(overrides)
    return base
