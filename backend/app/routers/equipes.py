"""Edição/remoção de equipes e listagem global.

A listagem global (`GET /api/equipes`) é uma adição ao contrato da spec:
o allocation-engine e o dashboard precisam de todas as equipes de uma vez,
sem iterar setor a setor.
"""

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Equipe, Setor
from app.schemas import EquipeRead, EquipeUpdate
from app.utils import obter_ou_404

router = APIRouter(prefix="/api/equipes", tags=["equipes"])


@router.get("", response_model=list[EquipeRead])
def listar_equipes(
    db: Session = Depends(get_db),
    setor_id: int | None = Query(default=None, description="Filtra por setor"),
):
    stmt = select(Equipe)
    if setor_id is not None:
        stmt = stmt.where(Equipe.setor_id == setor_id)
    return db.scalars(stmt.order_by(Equipe.setor_id, Equipe.nome)).all()


@router.get("/{equipe_id}", response_model=EquipeRead)
def detalhar_equipe(equipe_id: int, db: Session = Depends(get_db)):
    return obter_ou_404(db, Equipe, equipe_id, "Equipe")


@router.put("/{equipe_id}", response_model=EquipeRead)
def editar_equipe(equipe_id: int, dados: EquipeUpdate, db: Session = Depends(get_db)):
    equipe = obter_ou_404(db, Equipe, equipe_id, "Equipe")
    valores = dados.model_dump(mode="json")

    # setor_id é opcional no corpo: ausente mantém o setor atual; presente
    # move a equipe, desde que o setor de destino exista.
    novo_setor = valores.pop("setor_id", None)
    if novo_setor is not None:
        obter_ou_404(db, Setor, novo_setor, "Setor")
        equipe.setor_id = novo_setor

    for campo, valor in valores.items():
        setattr(equipe, campo, valor)
    db.commit()
    db.refresh(equipe)
    return equipe


@router.delete("/{equipe_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_equipe(equipe_id: int, db: Session = Depends(get_db)):
    equipe = obter_ou_404(db, Equipe, equipe_id, "Equipe")
    db.delete(equipe)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
