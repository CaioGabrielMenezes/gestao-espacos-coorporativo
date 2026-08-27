"""Aplicação FastAPI — Sistema de Gestão e Otimização de Espaços Corporativos.

O /docs gerado aqui é a evidência de contrato usada na demonstração.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import criar_tabelas
from app.routers import alocacoes, dashboard, equipes, restricoes, salas, setores


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
    # Qualquer porta de localhost, e não só a 5173: quando essa porta está
    # ocupada o Vite sobe na 5174 sem avisar, e um CORS fixo faria a aplicação
    # falhar em silêncio bem na hora da demonstração. O protótipo roda só
    # localmente, então liberar as portas locais não amplia superfície real.
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1|\[::1\]):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(salas.router)
app.include_router(setores.router)
app.include_router(equipes.router)
app.include_router(restricoes.router)
app.include_router(alocacoes.router)
app.include_router(dashboard.router)


@app.get("/api/health", tags=["infra"])
def health():
    return {"status": "ok"}
