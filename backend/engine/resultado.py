"""Contratos de saída do motor (Pydantic).

Seguem literalmente os formatos de specs/motor-alocacao.md. Campos extras
foram acrescentados apenas de forma aditiva (score, criterios, ids), para o
frontend e o dashboard não precisarem recalcular nada.

Ficam no próprio motor, e não em app/schemas.py, para o pacote `engine`
continuar autocontido e testável sem subir a aplicação.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class Explicabilidade(BaseModel):
    """Por que esta sala, e não outra."""

    sala: str
    equipe: str
    capacidade_sala: int
    tamanho_equipe: int
    ocupacao_prevista: str = Field(examples=["92%"])
    recursos_atendidos: bool
    restricao_andar_atendida: bool
    alternativas_avaliadas: int = Field(
        description="Quantas salas eram viáveis para esta equipe, incluindo a escolhida"
    )
    justificativa: str
    score: float = Field(description="Qualidade da alocação, de 0 a 100")
    criterios: dict[str, float] = Field(
        description="Score decomposto por critério, com os pesos vigentes"
    )


class Recomendacao(BaseModel):
    equipe_id: int
    equipe: str
    pessoas: int
    sala_id: int
    sala_sugerida: str
    capacidade: int
    andar: int
    ocupacao_prevista: str
    ocupacao_percentual: float
    explicabilidade: Explicabilidade


class Alerta(BaseModel):
    """Equipe que não pôde ser alocada. Nunca é omitida do resultado."""

    status: str = "ALERTA"
    equipe_id: int
    equipe_afetada: str
    restricao_nao_atendida: str
    causa: str
    encaminhamento: str


class Metricas(BaseModel):
    equipes_alocadas: int
    equipes_sem_sala: int
    salas_ocupadas: int
    ocupacao_media: str
    ocupacao_media_percentual: float
    assentos_ociosos: int
    violacoes: int


class Comparativo(BaseModel):
    """Insumo direto da tela 'antes/depois' do dashboard."""

    antes: Metricas
    depois: Metricas


class RegistroGovernanca(BaseModel):
    execucao_id: int | None = None
    timestamp: datetime
    usuario: str
    algoritmo: str
    equipes_analisadas: int
    salas_analisadas: int
    equipes_alocadas: int
    equipes_nao_alocadas: int
    restricoes_violadas: int
    ocupacao_prevista: str
    duracao_ms: float
    pesos: dict[str, float] = Field(
        description="Pesos vigentes na execução, para reinterpretá-la depois"
    )


class ViolacaoRegistrada(BaseModel):
    tipo: str
    descricao: str
    equipes_envolvidas: list[int]


class ResultadoAlocacao(BaseModel):
    recomendacoes: list[Recomendacao]
    alertas: list[Alerta]
    violacoes: list[ViolacaoRegistrada]
    governanca: RegistroGovernanca
    comparativo: Comparativo
