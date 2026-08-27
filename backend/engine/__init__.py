"""Motor de alocação (ver specs/motor-alocacao.md).

Módulo puro: recebe dataclasses, devolve Pydantic, não conhece banco de dados
nem FastAPI. Toda a adaptação ORM -> Cenario vive em app/routers/alocacoes.py.
"""

from engine.modelos import Cenario, EquipeEntrada, RestricaoEntrada, SalaEntrada
from engine.otimizador import ALGORITMO, otimizar
from engine.resultado import ResultadoAlocacao

__all__ = [
    "ALGORITMO",
    "Cenario",
    "EquipeEntrada",
    "RestricaoEntrada",
    "ResultadoAlocacao",
    "SalaEntrada",
    "otimizar",
]
