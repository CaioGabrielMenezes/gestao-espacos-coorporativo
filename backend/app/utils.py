"""Helpers compartilhados pelos routers."""

from contextlib import contextmanager

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import Base


def obter_ou_404(db: Session, modelo: type[Base], registro_id: int, rotulo: str):
    """Busca por id ou aborta com 404 com mensagem legível na UI."""
    obj = db.get(modelo, registro_id)
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{rotulo} de id {registro_id} não encontrado(a).",
        )
    return obj


@contextmanager
def traduzir_conflito(mensagem: str):
    """Converte violação de UNIQUE/CHECK do banco em 409 em vez de erro 500."""
    try:
        yield
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=mensagem
        ) from exc
