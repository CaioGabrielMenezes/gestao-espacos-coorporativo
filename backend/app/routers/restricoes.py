"""CRUD de restrições (specs/cadastro.md, requisito 4).

Critério de aceite: as restrições ficam disponíveis para o allocation-engine
consultar por aqui — nada de regra hardcoded no motor.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.enums import TipoRestricao
from app.models import Equipe, Restricao, Sala, Setor
from app.schemas import RestricaoCreate, RestricaoRead
from app.utils import obter_ou_404

router = APIRouter(prefix="/api/restricoes", tags=["restricoes"])


@router.get("", response_model=list[RestricaoRead])
def listar_restricoes(
    db: Session = Depends(get_db),
    tipo: TipoRestricao | None = None,
    sala_id: int | None = None,
    equipe_id: int | None = None,
    setor_id: int | None = None,
):
    stmt = select(Restricao)
    if tipo is not None:
        stmt = stmt.where(Restricao.tipo == tipo)
    if sala_id is not None:
        stmt = stmt.where(Restricao.sala_id == sala_id)
    if equipe_id is not None:
        stmt = stmt.where(Restricao.equipe_id == equipe_id)
    if setor_id is not None:
        stmt = stmt.where(Restricao.setor_id == setor_id)
    return db.scalars(stmt.order_by(Restricao.id)).all()


@router.post("", response_model=RestricaoRead, status_code=status.HTTP_201_CREATED)
def criar_restricao(dados: RestricaoCreate, db: Session = Depends(get_db)):
    # O schema já garantiu que há exatamente um alvo e que ele é do tipo certo;
    # aqui confirmamos que a entidade apontada existe de fato.
    if dados.sala_id is not None:
        obter_ou_404(db, Sala, dados.sala_id, "Sala")
    elif dados.equipe_id is not None:
        obter_ou_404(db, Equipe, dados.equipe_id, "Equipe")
    else:
        obter_ou_404(db, Setor, dados.setor_id, "Setor")

    _validar_referencias_do_parametro(db, dados)

    restricao = Restricao(**dados.model_dump(mode="json"))
    db.add(restricao)
    db.commit()
    db.refresh(restricao)
    return restricao


@router.delete("/{restricao_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_restricao(restricao_id: int, db: Session = Depends(get_db)):
    restricao = obter_ou_404(db, Restricao, restricao_id, "Restrição")
    db.delete(restricao)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _validar_referencias_do_parametro(db: Session, dados: RestricaoCreate) -> None:
    """Alguns tipos carregam ids dentro de `parametro`. Sem esta checagem o
    motor receberia restrições apontando para entidades inexistentes."""
    p = dados.parametro

    if dados.tipo is TipoRestricao.sala_reservada_setor:
        obter_ou_404(db, Setor, p["setor_id"], "Setor")

    elif dados.tipo is TipoRestricao.proximidade_obrigatoria:
        for equipe_id in _lista_de_ids(p, "equipe_ids"):
            obter_ou_404(db, Equipe, equipe_id, "Equipe")

    elif dados.tipo is TipoRestricao.setores_nao_compartilham:
        for setor_id in _lista_de_ids(p, "setor_ids"):
            obter_ou_404(db, Setor, setor_id, "Setor")

    elif dados.tipo is TipoRestricao.andar_permitido:
        andares = _lista_de_ids(p, "andares")
        if not andares or any(not 1 <= a <= 9 for a in andares):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="'andares' deve conter ao menos um andar entre 1 e 9.",
            )


def _lista_de_ids(parametro: dict, chave: str) -> list[int]:
    valor = parametro.get(chave)
    if not isinstance(valor, list) or not all(isinstance(v, int) for v in valor):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"'{chave}' deve ser uma lista de inteiros.",
        )
    return valor
