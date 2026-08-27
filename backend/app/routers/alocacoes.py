"""Endpoints do motor de alocação (specs/motor-alocacao.md).

Este módulo é a fronteira entre o banco e o motor: ele traduz ORM -> Cenario,
chama `engine.otimizar` e persiste o registro de governança. Nenhuma regra de
otimização vive aqui.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    AlertaAlocacao,
    AlocacaoRecomendada,
    Equipe,
    ExecucaoAlocacao,
    IntervencaoManual,
    Restricao,
    Sala,
)
from app.utils import obter_ou_404
from engine import Cenario, EquipeEntrada, RestricaoEntrada, SalaEntrada, otimizar
from engine.restricoes import IndiceRestricoes, avaliar_veto
from engine.resultado import RegistroGovernanca, ResultadoAlocacao

router = APIRouter(prefix="/api/alocacoes", tags=["alocacao"])

# Status de uma alocação que representam decisão humana e que, por isso, a
# re-otimização deve preservar.
STATUS_FIXADOS = ("aceita", "editada")


class PedidoOtimizacao(BaseModel):
    usuario: str = Field(
        default="coordenador-geral",
        description="Quem disparou a execução — registrado na governança",
    )


class PedidoIntervencao(BaseModel):
    usuario: str = Field(default="coordenador-geral")
    justificativa: str | None = Field(default=None, max_length=400)


class EdicaoManual(PedidoIntervencao):
    sala_id: int = Field(description="Nova sala para a equipe")


class IntervencaoRead(BaseModel):
    id: int
    execucao_id: int
    alocacao_id: int | None
    acao: str
    usuario: str
    timestamp: datetime
    justificativa: str | None
    detalhe: dict


class ExecucaoDetalhada(BaseModel):
    """Uma execução recuperada do histórico, com tudo que ela produziu."""

    governanca: RegistroGovernanca
    recomendacoes: list[dict]
    alertas: list[dict]
    comparativo: dict
    intervencoes: list[IntervencaoRead]


@router.post("/otimizar", response_model=ResultadoAlocacao)
def gerar_alocacao_otimizada(
    pedido: PedidoOtimizacao | None = None, db: Session = Depends(get_db)
):
    """Ação principal: GERAR ALOCAÇÃO OTIMIZADA.

    Lê o estado atual do cadastro, roda o motor e persiste a execução.
    """
    pedido = pedido or PedidoOtimizacao()
    return _executar(db, usuario=pedido.usuario)


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
                # O id da linha de alocação é o que os endpoints de
                # intervenção usam como endereço — sem ele, a UI não tem
                # como aceitar, rejeitar ou editar nada.
                "id": a.id,
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
        intervencoes=[IntervencaoRead(**_intervencao_dict(i)) for i in execucao.intervencoes],
    )


# --------------------------------------------------------------------------
# Intervenção humana (specs/motor-alocacao.md)
# --------------------------------------------------------------------------
@router.post("/{alocacao_id}/aceitar", response_model=IntervencaoRead)
def aceitar_recomendacao(
    alocacao_id: int,
    pedido: PedidoIntervencao | None = None,
    db: Session = Depends(get_db),
):
    return _mudar_status(db, alocacao_id, "aceita", "aceitar", pedido)


@router.post("/{alocacao_id}/rejeitar", response_model=IntervencaoRead)
def rejeitar_recomendacao(
    alocacao_id: int,
    pedido: PedidoIntervencao | None = None,
    db: Session = Depends(get_db),
):
    return _mudar_status(db, alocacao_id, "rejeitada", "rejeitar", pedido)


@router.put("/{alocacao_id}", response_model=IntervencaoRead)
def editar_alocacao_manualmente(
    alocacao_id: int, pedido: EdicaoManual, db: Session = Depends(get_db)
):
    """Move a equipe para outra sala por decisão do coordenador.

    Capacidade é inegociável: sala menor que a equipe devolve 422, porque é
    impossibilidade física, não questão de julgamento. As demais restrições
    duras são permitidas e registradas como `avisos` — o coordenador pode
    saber algo que o cadastro não sabe (o projetor chega semana que vem), e
    bloquear isso tornaria a intervenção humana decorativa. O que não se
    abre mão é do rastro.
    """
    alocacao = obter_ou_404(db, AlocacaoRecomendada, alocacao_id, "Alocação")
    sala = obter_ou_404(db, Sala, pedido.sala_id, "Sala")
    equipe = obter_ou_404(db, Equipe, alocacao.equipe_id, "Equipe")

    if sala.capacidade < equipe.quantidade_funcionarios:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"{sala.identificacao} comporta {sala.capacidade} pessoas e a equipe "
                f"'{equipe.nome}' tem {equipe.quantidade_funcionarios}. A regra de "
                f"capacidade não admite exceção, nem por decisão manual."
            ),
        )

    ocupante = db.scalar(
        select(AlocacaoRecomendada).where(
            AlocacaoRecomendada.execucao_id == alocacao.execucao_id,
            AlocacaoRecomendada.sala_id == sala.id,
            AlocacaoRecomendada.id != alocacao.id,
            AlocacaoRecomendada.status != "rejeitada",
        )
    )
    if ocupante is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"{sala.identificacao} já está ocupada por '{ocupante.equipe_nome}' "
                f"nesta execução. Cada sala recebe uma equipe."
            ),
        )

    anterior = {
        "sala_id": alocacao.sala_id,
        "sala": alocacao.sala_identificacao,
        "andar": alocacao.andar,
        "capacidade": alocacao.capacidade,
        "ocupacao_percentual": alocacao.ocupacao_percentual,
    }

    alocacao.sala_id = sala.id
    alocacao.sala_identificacao = sala.identificacao
    alocacao.andar = sala.andar
    alocacao.capacidade = sala.capacidade
    alocacao.ocupacao_percentual = round(
        equipe.quantidade_funcionarios / sala.capacidade * 100, 1
    )
    alocacao.status = "editada"

    intervencao = _registrar_intervencao(
        db,
        alocacao=alocacao,
        acao="editar",
        pedido=pedido,
        detalhe={
            "de": anterior,
            "para": {
                "sala_id": sala.id,
                "sala": sala.identificacao,
                "andar": sala.andar,
                "capacidade": sala.capacidade,
                "ocupacao_percentual": alocacao.ocupacao_percentual,
            },
            "avisos": _avisos_da_edicao(db, equipe, sala),
        },
    )
    db.commit()
    db.refresh(intervencao)
    return IntervencaoRead(**_intervencao_dict(intervencao))


@router.post("/execucoes/{execucao_id}/reotimizar", response_model=ResultadoAlocacao)
def reotimizar(
    execucao_id: int,
    pedido: PedidoOtimizacao | None = None,
    db: Session = Depends(get_db),
):
    """Nova otimização preservando o que o coordenador já decidiu.

    As alocações aceitas ou editadas viram fixações: saem do grafo e o motor
    reotimiza apenas o restante. É o que dá sentido prático à intervenção —
    sem isso, re-otimizar jogaria fora todo o trabalho manual.
    """
    pedido = pedido or PedidoOtimizacao()
    execucao = obter_ou_404(db, ExecucaoAlocacao, execucao_id, "Execução")

    stmt = select(AlocacaoRecomendada).where(
        AlocacaoRecomendada.execucao_id == execucao.id,
        AlocacaoRecomendada.status.in_(STATUS_FIXADOS),
    )
    fixacoes = {a.equipe_id: a.sala_id for a in db.scalars(stmt).all()}

    return _executar(db, usuario=pedido.usuario, fixacoes=fixacoes)


@router.get("/execucoes/{execucao_id}/intervencoes", response_model=list[IntervencaoRead])
def listar_intervencoes(execucao_id: int, db: Session = Depends(get_db)):
    obter_ou_404(db, ExecucaoAlocacao, execucao_id, "Execução")
    stmt = (
        select(IntervencaoManual)
        .where(IntervencaoManual.execucao_id == execucao_id)
        .order_by(IntervencaoManual.id)
    )
    return [IntervencaoRead(**_intervencao_dict(i)) for i in db.scalars(stmt).all()]


@router.get("/intervencoes/total")
def contar_intervencoes(db: Session = Depends(get_db)):
    """Contador usado pela área de monitoramento do dashboard."""
    total = db.scalar(select(func.count()).select_from(IntervencaoManual)) or 0
    por_acao = dict(
        db.execute(
            select(IntervencaoManual.acao, func.count()).group_by(IntervencaoManual.acao)
        ).all()
    )
    erros = (
        db.scalar(
            select(func.count())
            .select_from(ExecucaoAlocacao)
            .where(ExecucaoAlocacao.status == "falha")
        )
        or 0
    )
    return {"total": total, "por_acao": por_acao, "execucoes_com_erro": erros}


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


def _executar(
    db: Session, usuario: str, fixacoes: dict[int, int] | None = None
) -> ResultadoAlocacao:
    """Roda o motor e persiste a execução — inclusive quando ela falha.

    Registrar a falha é o que torna o card 'erros ocorridos' do monitoramento
    um número real. Uma exceção engolida silenciosamente seria pior do que o
    erro em si: o painel diria que está tudo bem.
    """
    cenario = montar_cenario(db)
    try:
        resultado = otimizar(cenario, usuario=usuario, fixacoes=fixacoes)
    except Exception as exc:
        db.rollback()
        _persistir_falha(db, cenario, usuario, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"A otimização falhou e foi registrada na governança: {exc}",
        ) from exc

    execucao = _persistir(db, resultado)
    resultado.governanca.execucao_id = execucao.id
    return resultado


def _persistir_falha(
    db: Session, cenario: Cenario, usuario: str, exc: Exception
) -> None:
    db.add(
        ExecucaoAlocacao(
            timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
            usuario=usuario,
            algoritmo="allocation-engine-v1",
            equipes_analisadas=len(cenario.equipes),
            salas_analisadas=len(cenario.salas),
            equipes_alocadas=0,
            equipes_nao_alocadas=len(cenario.equipes),
            restricoes_violadas=0,
            ocupacao_prevista="0%",
            duracao_ms=0.0,
            pesos={},
            comparativo={},
            status="falha",
            erro=f"{type(exc).__name__}: {exc}"[:500],
        )
    )
    db.commit()


def _mudar_status(
    db: Session,
    alocacao_id: int,
    novo_status: str,
    acao: str,
    pedido: PedidoIntervencao | None,
) -> IntervencaoRead:
    alocacao = obter_ou_404(db, AlocacaoRecomendada, alocacao_id, "Alocação")
    anterior = alocacao.status
    alocacao.status = novo_status

    intervencao = _registrar_intervencao(
        db,
        alocacao=alocacao,
        acao=acao,
        pedido=pedido or PedidoIntervencao(),
        detalhe={"de": {"status": anterior}, "para": {"status": novo_status}},
    )
    db.commit()
    db.refresh(intervencao)
    return IntervencaoRead(**_intervencao_dict(intervencao))


def _registrar_intervencao(
    db: Session,
    alocacao: AlocacaoRecomendada,
    acao: str,
    pedido: PedidoIntervencao,
    detalhe: dict,
) -> IntervencaoManual:
    intervencao = IntervencaoManual(
        execucao_id=alocacao.execucao_id,
        alocacao_id=alocacao.id,
        acao=acao,
        usuario=pedido.usuario,
        timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
        justificativa=pedido.justificativa,
        detalhe={"equipe": alocacao.equipe_nome, **detalhe},
    )
    db.add(intervencao)
    return intervencao


def _avisos_da_edicao(db: Session, equipe: Equipe, sala: Sala) -> list[str]:
    """Restrições duras que a escolha manual desrespeita.

    Não bloqueiam a edição — apenas ficam registradas, para que a decisão
    humana seja auditável junto com o que ela custou.
    """
    cenario = montar_cenario(db)
    entrada_equipe = next((e for e in cenario.equipes if e.id == equipe.id), None)
    entrada_sala = next((s for s in cenario.salas if s.id == sala.id), None)
    if entrada_equipe is None or entrada_sala is None:
        return []

    veto = avaliar_veto(entrada_equipe, entrada_sala, IndiceRestricoes(cenario.restricoes))
    return [] if veto is None else [f"{veto.restricao}: {veto.detalhe}"]


def _intervencao_dict(intervencao: IntervencaoManual) -> dict:
    return {
        "id": intervencao.id,
        "execucao_id": intervencao.execucao_id,
        "alocacao_id": intervencao.alocacao_id,
        "acao": intervencao.acao,
        "usuario": intervencao.usuario,
        "timestamp": intervencao.timestamp,
        "justificativa": intervencao.justificativa,
        "detalhe": intervencao.detalhe or {},
    }


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
