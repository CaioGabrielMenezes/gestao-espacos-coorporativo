"""Aplicação FastAPI — Sistema de Gestão e Otimização de Espaços Corporativos.

O /docs gerado aqui é a evidência de contrato usada na demonstração.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import criar_tabelas
from app.routers import alocacoes, equipes, restricoes, salas, setores


@asynccontextmanager
async def lifespan(app: FastAPI):
    criar_tabelas()
    yield


app = FastAPI(
    title="Gestão de Espaços Corporativos",
    description=(
        "Cadastro de salas, setores, equipes e restrições que alimentam o "
        "motor de alocação. Ver specs/cadastro.md."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(salas.router)
app.include_router(setores.router)
app.include_router(equipes.router)
app.include_router(restricoes.router)
app.include_router(alocacoes.router)


@app.get("/api/health", tags=["infra"])
def health():
    return {"status": "ok"}
