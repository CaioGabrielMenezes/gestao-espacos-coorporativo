"""Indicadores executivos do prédio (specs/dashboard.md).

O cálculo em si vive em `engine/indicadores.py`. Aqui só se decide QUAL
atribuição alimenta os números: o estado atual do prédio ou a projeção de uma
execução do motor.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AlocacaoRecomendada, ExecucaoAlocacao
from app.routers.alocacoes import montar_cenario
from app.utils import obter_ou_404
from engine import (
    Indicadores,
    MapaPredio,
    atribuicao_atual,
    calcular_indicadores,
    montar_mapa,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

DESCRICAO_EXECUCAO_ID = (
    "Sem este parâmetro, os números refletem o estado ATUAL do prédio "
    "(lido de sala_atual_id). Com ele, projetam o resultado da execução."
)


@router.get("/indicadores", response_model=Indicadores)
def obter_indicadores(
    db: Session = Depends(get_db),
    execucao_id: int | None = Query(default=None, description=DESCRICAO_EXECUCAO_ID),
):
    cenario, atribuicao, origem, eid = _resolver(db, execucao_id)
    return calcular_indicadores(cenario, atribuicao, origem=origem, execucao_id=eid)


@router.get("/mapa", response_model=MapaPredio)
def obter_mapa(
    db: Session = Depends(get_db),
    execucao_id: int | None = Query(default=None, description=DESCRICAO_EXECUCAO_ID),
):
    """Planta do prédio: andares, salas e a equipe que ocupa cada uma."""
    cenario, atribuicao, origem, eid = _resolver(db, execucao_id)
    return montar_mapa(cenario, atribuicao, origem=origem, execucao_id=eid)


@router.get("/mapa/ultima-execucao", response_model=MapaPredio)
def obter_mapa_da_ultima_execucao(db: Session = Depends(get_db)):
    ultima = _ultima_execucao_concluida(db)
    return obter_mapa(db=db, execucao_id=ultima.id if ultima else None)


def _resolver(
    db: Session, execucao_id: int | None
) -> tuple[object, dict[int, int], str, int | None]:
    """Decide qual atribuição alimenta os números.

    Compartilhado por indicadores e mapa: as duas telas mostram o mesmo prédio
    sob a mesma ótica, e duplicar essa escolha deixaria uma poder discordar da
    outra.
    """
    cenario = montar_cenario(db)

    if execucao_id is None:
        return cenario, atribuicao_atual(cenario), "estado_atual", None

    execucao = obter_ou_404(db, ExecucaoAlocacao, execucao_id, "Execução")
    return cenario, _atribuicao_da_execucao(db, execucao.id), "execucao", execucao.id


def _ultima_execucao_concluida(db: Session) -> ExecucaoAlocacao | None:
    return db.scalar(
        select(ExecucaoAlocacao)
        .where(ExecucaoAlocacao.status == "concluida")
        .order_by(ExecucaoAlocacao.id.desc())
        .limit(1)
    )


@router.get("/indicadores/ultima-execucao", response_model=Indicadores)
def obter_indicadores_da_ultima_execucao(db: Session = Depends(get_db)):
    """Atalho usado pelo dashboard para alternar entre 'hoje' e 'proposto'
    sem que o frontend precise descobrir o id da última execução.

    Sem execução ainda, devolve o estado atual em vez de 404, para o dashboard
    renderizar normalmente numa base recém-populada.
    """
    ultima = _ultima_execucao_concluida(db)
    return obter_indicadores(db=db, execucao_id=ultima.id if ultima else None)


def _atribuicao_da_execucao(db: Session, execucao_id: int) -> dict[int, int]:
    """Alocações de uma execução, exceto as rejeitadas pelo coordenador.

    Uma recomendação rejeitada não representa ocupação real e não deve entrar
    nos indicadores.
    """
    stmt = select(AlocacaoRecomendada).where(
        AlocacaoRecomendada.execucao_id == execucao_id,
        AlocacaoRecomendada.status != "rejeitada",
    )
    return {a.equipe_id: a.sala_id for a in db.scalars(stmt).all()}
