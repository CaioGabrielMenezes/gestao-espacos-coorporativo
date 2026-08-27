"""CRUD de setores e criação de equipes dentro de um setor
(specs/cadastro.md, requisitos 2 e 3)."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Equipe, Setor
from app.schemas import EquipeCreate, EquipeRead, SetorCreate, SetorRead, SetorUpdate
from app.utils import obter_ou_404, traduzir_conflito

router = APIRouter(prefix="/api/setores", tags=["setores"])

CONFLITO = "Já existe um setor com esse nome."


@router.get("", response_model=list[SetorRead])
def listar_setores(db: Session = Depends(get_db)):
    return db.scalars(select(Setor).order_by(Setor.nome)).all()


@router.post("", response_model=SetorRead, status_code=status.HTTP_201_CREATED)
def criar_setor(dados: SetorCreate, db: Session = Depends(get_db)):
    setor = Setor(**dados.model_dump())
    db.add(setor)
    with traduzir_conflito(CONFLITO):
        db.commit()
    db.refresh(setor)
    return setor


@router.get("/{setor_id}", response_model=SetorRead)
def detalhar_setor(setor_id: int, db: Session = Depends(get_db)):
    return obter_ou_404(db, Setor, setor_id, "Setor")


@router.put("/{setor_id}", response_model=SetorRead)
def editar_setor(setor_id: int, dados: SetorUpdate, db: Session = Depends(get_db)):
    setor = obter_ou_404(db, Setor, setor_id, "Setor")
    for campo, valor in dados.model_dump().items():
        setattr(setor, campo, valor)
    with traduzir_conflito(CONFLITO):
        db.commit()
    db.refresh(setor)
    return setor


@router.delete("/{setor_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_setor(setor_id: int, db: Session = Depends(get_db)):
    """Remove o setor e, em cascata, suas equipes — não existe equipe órfã."""
    setor = obter_ou_404(db, Setor, setor_id, "Setor")
    db.delete(setor)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------
# Equipes de um setor
# --------------------------------------------------------------------------
@router.get("/{setor_id}/equipes", response_model=list[EquipeRead])
def listar_equipes_do_setor(setor_id: int, db: Session = Depends(get_db)):
    obter_ou_404(db, Setor, setor_id, "Setor")
    stmt = select(Equipe).where(Equipe.setor_id == setor_id).order_by(Equipe.nome)
    return db.scalars(stmt).all()


@router.post(
    "/{setor_id}/equipes", response_model=EquipeRead, status_code=status.HTTP_201_CREATED
)
def criar_equipe(setor_id: int, dados: EquipeCreate, db: Session = Depends(get_db)):
    """O setor vem da rota: é impossível criar equipe sem setor válido (404 se
    o setor não existir) — critério de aceite da spec."""
    obter_ou_404(db, Setor, setor_id, "Setor")
    equipe = Equipe(setor_id=setor_id, **dados.model_dump(mode="json"))
    db.add(equipe)
    db.commit()
    db.refresh(equipe)
    return equipe
