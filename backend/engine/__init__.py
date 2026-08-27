"""Motor de alocação (ver specs/motor-alocacao.md).

Módulo puro: recebe dataclasses, devolve Pydantic, não conhece banco de dados
nem FastAPI. Toda a adaptação ORM -> Cenario vive em app/routers/alocacoes.py.
"""

from engine.indicadores import Indicadores, calcular_indicadores
from engine.modelos import Cenario, EquipeEntrada, RestricaoEntrada, SalaEntrada
from engine.otimizador import ALGORITMO, atribuicao_atual, otimizar
from engine.resultado import ResultadoAlocacao

__all__ = [
    "ALGORITMO",
    "Cenario",
    "EquipeEntrada",
    "Indicadores",
    "RestricaoEntrada",
    "ResultadoAlocacao",
    "SalaEntrada",
    "atribuicao_atual",
    "calcular_indicadores",
    "otimizar",
]
