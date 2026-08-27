"""CRUD de salas — Coordenador Geral (specs/cadastro.md, requisito 1)."""

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.enums import TipoSala
from app.models import Sala
from app.schemas import SalaCreate, SalaRead, SalaUpdate
from app.utils import obter_ou_404, traduzir_conflito

router = APIRouter(prefix="/api/salas", tags=["salas"])

CONFLITO = "Já existe uma sala com essa identificação."


@router.get("", response_model=list[SalaRead])
def listar_salas(
    db: Session = Depends(get_db),
    andar: int | None = Query(default=None, ge=1, le=9),
    tipo: TipoSala | None = None,
    acessibilidade: bool | None = None,
):
    stmt = select(Sala)
    if andar is not None:
        stmt = stmt.where(Sala.andar == andar)
    if tipo is not None:
        stmt = stmt.where(Sala.tipo == tipo)
    if acessibilidade is not None:
        stmt = stmt.where(Sala.acessibilidade == acessibilidade)
    return db.scalars(stmt.order_by(Sala.andar, Sala.identificacao)).all()


@router.post("", response_model=SalaRead, status_code=status.HTTP_201_CREATED)
def criar_sala(dados: SalaCreate, db: Session = Depends(get_db)):
    sala = Sala(**dados.model_dump(mode="json"))
    db.add(sala)
    with traduzir_conflito(CONFLITO):
        db.commit()
    db.refresh(sala)
    return sala


@router.get("/{sala_id}", response_model=SalaRead)
def detalhar_sala(sala_id: int, db: Session = Depends(get_db)):
    return obter_ou_404(db, Sala, sala_id, "Sala")


@router.put("/{sala_id}", response_model=SalaRead)
def editar_sala(sala_id: int, dados: SalaUpdate, db: Session = Depends(get_db)):
    sala = obter_ou_404(db, Sala, sala_id, "Sala")
    for campo, valor in dados.model_dump(mode="json").items():
        setattr(sala, campo, valor)
    with traduzir_conflito(CONFLITO):
        db.commit()
    db.refresh(sala)
    return sala


@router.delete("/{sala_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_sala(sala_id: int, db: Session = Depends(get_db)):
    sala = obter_ou_404(db, Sala, sala_id, "Sala")
    db.delete(sala)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
