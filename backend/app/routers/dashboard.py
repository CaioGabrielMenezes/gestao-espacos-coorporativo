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
from engine import Indicadores, atribuicao_atual, calcular_indicadores

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/indicadores", response_model=Indicadores)
def obter_indicadores(
    db: Session = Depends(get_db),
    execucao_id: int | None = Query(
        default=None,
        description=(
            "Sem este parâmetro, os números refletem o estado ATUAL do prédio "
            "(lido de sala_atual_id). Com ele, projetam o resultado da execução."
        ),
    ),
):
    cenario = montar_cenario(db)

    if execucao_id is None:
        return calcular_indicadores(
            cenario, atribuicao_atual(cenario), origem="estado_atual"
        )

    execucao = obter_ou_404(db, ExecucaoAlocacao, execucao_id, "Execução")
    return calcular_indicadores(
        cenario,
        _atribuicao_da_execucao(db, execucao.id),
        origem="execucao",
        execucao_id=execucao.id,
    )


@router.get("/indicadores/ultima-execucao", response_model=Indicadores)
def obter_indicadores_da_ultima_execucao(db: Session = Depends(get_db)):
    """Atalho usado pelo dashboard para alternar entre 'hoje' e 'proposto'
    sem que o frontend precise descobrir o id da última execução."""
    cenario = montar_cenario(db)
    ultima = db.scalar(
        select(ExecucaoAlocacao)
        .where(ExecucaoAlocacao.status == "concluida")
        .order_by(ExecucaoAlocacao.id.desc())
        .limit(1)
    )

    if ultima is None:
        # Sem execução ainda: devolve o estado atual em vez de 404, para o
        # dashboard renderizar normalmente numa base recém-populada.
        return calcular_indicadores(
            cenario, atribuicao_atual(cenario), origem="estado_atual"
        )

    return calcular_indicadores(
        cenario,
        _atribuicao_da_execucao(db, ultima.id),
        origem="execucao",
        execucao_id=ultima.id,
    )


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
