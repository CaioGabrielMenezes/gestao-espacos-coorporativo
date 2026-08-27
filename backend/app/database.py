"""Configuração do banco (SQLite local).

Decisão registrada no CLAUDE.md: o protótipo usa SQLite em arquivo, sem
dependência de serviço externo. O caminho pode ser sobrescrito por
DATABASE_URL — os testes usam isso para rodar contra um banco temporário.
"""

import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "espacos.db"

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")

engine = create_engine(
    DATABASE_URL,
    # check_same_thread só se aplica a SQLite; o TestClient do FastAPI roda
    # as requisições em outra thread que não a que criou a conexão.
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)


@event.listens_for(engine, "connect")
def _habilitar_foreign_keys(dbapi_connection, connection_record):
    """SQLite ignora FKs por padrão — sem isso, o ON DELETE CASCADE de
    equipes/restrições não roda e sobram registros órfãos."""
    if DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def criar_tabelas() -> None:
    from app import models  # noqa: F401  (registra os mapeamentos antes do create_all)

    Base.metadata.create_all(bind=engine)
