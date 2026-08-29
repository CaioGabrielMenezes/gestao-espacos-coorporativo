"""Motor de alocação (ver specs/motor-alocacao.md).

Módulo puro: recebe dataclasses, devolve Pydantic, não conhece banco de dados
nem FastAPI. Toda a adaptação ORM -> Cenario vive em app/routers/alocacoes.py.
"""

from engine.indicadores import (
    Indicadores,
    MapaPredio,
    calcular_indicadores,
    montar_mapa,
)
from engine.modelos import Cenario, EquipeEntrada, RestricaoEntrada, SalaEntrada
from engine.otimizador import ALGORITMO, atribuicao_atual, otimizar
from engine.resultado import ResultadoAlocacao

__all__ = [
    "ALGORITMO",
    "Cenario",
    "EquipeEntrada",
    "Indicadores",
    "MapaPredio",
    "RestricaoEntrada",
    "ResultadoAlocacao",
    "SalaEntrada",
    "atribuicao_atual",
    "calcular_indicadores",
    "montar_mapa",
    "otimizar",
]
