"""Endpoints do motor de alocação (specs/motor-alocacao.md).

Este módulo é a fronteira entre o banco e o motor: ele traduz ORM -> Cenario,
chama `engine.otimizar` e persiste o registro de governança. Nenhuma regra de
otimização vive aqui.
"""

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    AlertaAlocacao,
    AlocacaoRecomendada,
    Equipe,
    ExecucaoAlocacao,
    Restricao,
    Sala,
)
from app.utils import obter_ou_404
from engine import Cenario, EquipeEntrada, RestricaoEntrada, SalaEntrada, otimizar
from engine.resultado import RegistroGovernanca, ResultadoAlocacao

router = APIRouter(prefix="/api/alocacoes", tags=["alocacao"])


class PedidoOtimizacao(BaseModel):
    usuario: str = Field(
        default="coordenador-geral",
        description="Quem disparou a execução — registrado na governança",
    )


class ExecucaoDetalhada(BaseModel):
    """Uma execução recuperada do histórico, com tudo que ela produziu."""

    governanca: RegistroGovernanca
    recomendacoes: list[dict]
    alertas: list[dict]
    comparativo: dict


@router.post("/otimizar", response_model=ResultadoAlocacao)
def gerar_alocacao_otimizada(
    pedido: PedidoOtimizacao | None = None, db: Session = Depends(get_db)
):
    """Ação principal: GERAR ALOCAÇÃO OTIMIZADA.

    Lê o estado atual do cadastro, roda o motor e persiste a execução.
    """
    pedido = pedido or PedidoOtimizacao()
    cenario = montar_cenario(db)
    resultado = otimizar(cenario, usuario=pedido.usuario)
    execucao = _persistir(db, resultado)
    resultado.governanca.execucao_id = execucao.id
    return resultado


@router.get("/execucoes", response_model=list[RegistroGovernanca])
def listar_execucoes(
    db: Session = Depends(get_db),
    limite: int = Query(default=20, ge=1, le=200),
):
    """Histórico de governança — consumido pela área de monitoramento."""
    stmt = select(ExecucaoAlocacao).order_by(ExecucaoAlocacao.id.desc()).limit(limite)
    return [_para_governanca(e) for e in db.scalars(stmt).all()]


@router.get("/execucoes/{execucao_id}", response_model=ExecucaoDetalhada)
def detalhar_execucao(execucao_id: int, db: Session = Depends(get_db)):
    execucao = obter_ou_404(db, ExecucaoAlocacao, execucao_id, "Execução")
    return ExecucaoDetalhada(
        governanca=_para_governanca(execucao),
        recomendacoes=[
            {
                "equipe_id": a.equipe_id,
                "equipe": a.equipe_nome,
                "pessoas": a.pessoas,
                "sala_id": a.sala_id,
                "sala_sugerida": a.sala_identificacao,
                "capacidade": a.capacidade,
                "andar": a.andar,
                "ocupacao_percentual": a.ocupacao_percentual,
                "status": a.status,
                "explicabilidade": a.explicabilidade,
            }
            for a in execucao.alocacoes
        ],
        alertas=[
            {
                "status": "ALERTA",
                "equipe_id": al.equipe_id,
                "equipe_afetada": al.equipe_afetada,
                "restricao_nao_atendida": al.restricao_nao_atendida,
                "causa": al.causa,
                "encaminhamento": al.encaminhamento,
            }
            for al in execucao.alertas
        ],
        comparativo=execucao.comparativo,
    )


# --------------------------------------------------------------------------
# Adaptação ORM -> motor
# --------------------------------------------------------------------------
def montar_cenario(db: Session) -> Cenario:
    """Converte o estado do banco na entrada do motor.

    As coleções viram tuplas/frozensets porque as dataclasses do motor são
    imutáveis — o cenário de uma execução não muda no meio do caminho.
    """
    salas = tuple(
        SalaEntrada(
            id=s.id,
            identificacao=s.identificacao,
            andar=s.andar,
            capacidade=s.capacidade,
            tipo=s.tipo.value,
            recursos=frozenset(s.recursos or ()),
            acessibilidade=s.acessibilidade,
        )
        for s in db.scalars(select(Sala).order_by(Sala.id)).all()
    )

    equipes = tuple(
        EquipeEntrada(
            id=e.id,
            nome=e.nome,
            setor_id=e.setor_id,
            quantidade_funcionarios=e.quantidade_funcionarios,
            requisitos_especiais=frozenset(e.requisitos_especiais or ()),
            preferencia_andar=e.preferencia_andar,
            necessita_acessibilidade=e.necessita_acessibilidade,
            proximidade_desejada=tuple(e.proximidade_desejada or ()),
            prioridade=e.prioridade.value,
            sala_atual_id=e.sala_atual_id,
        )
        for e in db.scalars(select(Equipe).order_by(Equipe.id)).all()
    )

    restricoes = tuple(
        RestricaoEntrada(
            id=r.id,
            tipo=r.tipo.value,
            sala_id=r.sala_id,
            equipe_id=r.equipe_id,
            setor_id=r.setor_id,
            parametro=dict(r.parametro or {}),
            descricao=r.descricao,
        )
        for r in db.scalars(select(Restricao).order_by(Restricao.id)).all()
    )

    return Cenario(salas=salas, equipes=equipes, restricoes=restricoes)


def _persistir(db: Session, resultado: ResultadoAlocacao) -> ExecucaoAlocacao:
    g = resultado.governanca
    execucao = ExecucaoAlocacao(
        timestamp=g.timestamp.replace(tzinfo=None),
        usuario=g.usuario,
        algoritmo=g.algoritmo,
        equipes_analisadas=g.equipes_analisadas,
        salas_analisadas=g.salas_analisadas,
        equipes_alocadas=g.equipes_alocadas,
        equipes_nao_alocadas=g.equipes_nao_alocadas,
        restricoes_violadas=g.restricoes_violadas,
        ocupacao_prevista=g.ocupacao_prevista,
        duracao_ms=g.duracao_ms,
        pesos=g.pesos,
        comparativo=resultado.comparativo.model_dump(),
    )
    db.add(execucao)

    for rec in resultado.recomendacoes:
        execucao.alocacoes.append(
            AlocacaoRecomendada(
                equipe_id=rec.equipe_id,
                sala_id=rec.sala_id,
                equipe_nome=rec.equipe,
                sala_identificacao=rec.sala_sugerida,
                pessoas=rec.pessoas,
                capacidade=rec.capacidade,
                andar=rec.andar,
                ocupacao_percentual=rec.ocupacao_percentual,
                explicabilidade=rec.explicabilidade.model_dump(),
            )
        )

    for alerta in resultado.alertas:
        execucao.alertas.append(
            AlertaAlocacao(
                equipe_id=alerta.equipe_id,
                equipe_afetada=alerta.equipe_afetada,
                restricao_nao_atendida=alerta.restricao_nao_atendida,
                causa=alerta.causa,
                encaminhamento=alerta.encaminhamento,
            )
        )

    db.commit()
    db.refresh(execucao)
    return execucao


def _para_governanca(execucao: ExecucaoAlocacao) -> RegistroGovernanca:
    return RegistroGovernanca(
        execucao_id=execucao.id,
        timestamp=execucao.timestamp,
        usuario=execucao.usuario,
        algoritmo=execucao.algoritmo,
        equipes_analisadas=execucao.equipes_analisadas,
        salas_analisadas=execucao.salas_analisadas,
        equipes_alocadas=execucao.equipes_alocadas,
        equipes_nao_alocadas=execucao.equipes_nao_alocadas,
        restricoes_violadas=execucao.restricoes_violadas,
        ocupacao_prevista=execucao.ocupacao_prevista,
        duracao_ms=execucao.duracao_ms,
        pesos=execucao.pesos or {},
    )
