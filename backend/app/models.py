"""Modelos ORM do cadastro (specs/cadastro.md).

Campos de lista/objeto usam o tipo JSON do SQLAlchemy: funciona em SQLite e
continua válido caso o projeto volte a um Postgres.
"""

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import Prioridade, TipoRestricao, TipoSala


class Sala(Base):
    __tablename__ = "salas"
    __table_args__ = (
        CheckConstraint("capacidade > 0", name="ck_sala_capacidade_positiva"),
        CheckConstraint("andar BETWEEN 1 AND 9", name="ck_sala_andar_valido"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    identificacao: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    andar: Mapped[int] = mapped_column(Integer, nullable=False)
    capacidade: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo: Mapped[TipoSala] = mapped_column(SAEnum(TipoSala), nullable=False)
    recursos: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    acessibilidade: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # {"dias": ["seg", ...], "horario_inicio": "08:00", "horario_fim": "18:00"}
    disponibilidade: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    restricoes: Mapped[list["Restricao"]] = relationship(
        back_populates="sala", cascade="all, delete-orphan"
    )


class Setor(Base):
    __tablename__ = "setores"
    __table_args__ = (
        CheckConstraint("total_funcionarios >= 0", name="ck_setor_total_nao_negativo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    coordenador: Mapped[str] = mapped_column(String(120), nullable=False)
    total_funcionarios: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    equipes: Mapped[list["Equipe"]] = relationship(
        back_populates="setor", cascade="all, delete-orphan"
    )
    restricoes: Mapped[list["Restricao"]] = relationship(
        back_populates="setor", cascade="all, delete-orphan"
    )


class Equipe(Base):
    __tablename__ = "equipes"
    __table_args__ = (
        CheckConstraint(
            "quantidade_funcionarios > 0", name="ck_equipe_quantidade_positiva"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # NOT NULL + FK: garante o critério de aceite "não é possível cadastrar
    # equipe sem setor associado" também no nível do banco, não só no schema.
    setor_id: Mapped[int] = mapped_column(
        ForeignKey("setores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    quantidade_funcionarios: Mapped[int] = mapped_column(Integer, nullable=False)
    # Onde a equipe está HOJE, antes de qualquer otimização. É o lado "antes"
    # da tela de comparação do dashboard e alimenta o critério de minimizar
    # movimentação entre andares.
    sala_atual_id: Mapped[int | None] = mapped_column(
        ForeignKey("salas.id", ondelete="SET NULL"), nullable=True
    )
    horario_necessario: Mapped[str] = mapped_column(String(40), nullable=False)
    requisitos_especiais: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    preferencia_andar: Mapped[int | None] = mapped_column(Integer, nullable=True)
    necessita_acessibilidade: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    # ids de outras equipes com quem esta deve ficar próxima
    proximidade_desejada: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    prioridade: Mapped[Prioridade] = mapped_column(
        SAEnum(Prioridade), nullable=False, default=Prioridade.media
    )

    setor: Mapped["Setor"] = relationship(back_populates="equipes")
    sala_atual: Mapped["Sala | None"] = relationship()
    restricoes: Mapped[list["Restricao"]] = relationship(
        back_populates="equipe", cascade="all, delete-orphan"
    )


class Restricao(Base):
    __tablename__ = "restricoes"
    __table_args__ = (
        # Exatamente um alvo preenchido. A spec fala em "sala_id ou equipe_id";
        # setor_id foi acrescentado para comportar `setores_nao_compartilham`.
        CheckConstraint(
            "(CASE WHEN sala_id IS NOT NULL THEN 1 ELSE 0 END) + "
            "(CASE WHEN equipe_id IS NOT NULL THEN 1 ELSE 0 END) + "
            "(CASE WHEN setor_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_restricao_alvo_unico",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tipo: Mapped[TipoRestricao] = mapped_column(SAEnum(TipoRestricao), nullable=False)
    sala_id: Mapped[int | None] = mapped_column(
        ForeignKey("salas.id", ondelete="CASCADE"), nullable=True, index=True
    )
    equipe_id: Mapped[int | None] = mapped_column(
        ForeignKey("equipes.id", ondelete="CASCADE"), nullable=True, index=True
    )
    setor_id: Mapped[int | None] = mapped_column(
        ForeignKey("setores.id", ondelete="CASCADE"), nullable=True, index=True
    )
    parametro: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    descricao: Mapped[str | None] = mapped_column(String(240), nullable=True)

    sala: Mapped["Sala | None"] = relationship(back_populates="restricoes")
    equipe: Mapped["Equipe | None"] = relationship(back_populates="restricoes")
    setor: Mapped["Setor | None"] = relationship(back_populates="restricoes")


# --------------------------------------------------------------------------
# Governança das execuções do motor (specs/motor-alocacao.md)
# --------------------------------------------------------------------------
class ExecucaoAlocacao(Base):
    """Registro imutável de uma execução do motor.

    É a resposta à pergunta "como sabemos que é confiável?": toda otimização
    deixa rastro de quem rodou, com qual algoritmo, sobre quantos dados e com
    que resultado.
    """

    __tablename__ = "execucoes_alocacao"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    usuario: Mapped[str] = mapped_column(String(120), nullable=False)
    algoritmo: Mapped[str] = mapped_column(String(80), nullable=False)
    equipes_analisadas: Mapped[int] = mapped_column(Integer, nullable=False)
    salas_analisadas: Mapped[int] = mapped_column(Integer, nullable=False)
    equipes_alocadas: Mapped[int] = mapped_column(Integer, nullable=False)
    equipes_nao_alocadas: Mapped[int] = mapped_column(Integer, nullable=False)
    restricoes_violadas: Mapped[int] = mapped_column(Integer, nullable=False)
    ocupacao_prevista: Mapped[str] = mapped_column(String(10), nullable=False)
    duracao_ms: Mapped[float] = mapped_column(Float, nullable=False)
    # Pesos vigentes na execução: permite reinterpretar uma decisão antiga
    # mesmo depois de a função de score ter sido recalibrada.
    pesos: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    comparativo: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    alocacoes: Mapped[list["AlocacaoRecomendada"]] = relationship(
        back_populates="execucao", cascade="all, delete-orphan"
    )
    alertas: Mapped[list["AlertaAlocacao"]] = relationship(
        back_populates="execucao", cascade="all, delete-orphan"
    )


class AlocacaoRecomendada(Base):
    __tablename__ = "alocacoes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    execucao_id: Mapped[int] = mapped_column(
        ForeignKey("execucoes_alocacao.id", ondelete="CASCADE"), nullable=False, index=True
    )
    equipe_id: Mapped[int] = mapped_column(Integer, nullable=False)
    sala_id: Mapped[int] = mapped_column(Integer, nullable=False)
    equipe_nome: Mapped[str] = mapped_column(String(120), nullable=False)
    sala_identificacao: Mapped[str] = mapped_column(String(80), nullable=False)
    pessoas: Mapped[int] = mapped_column(Integer, nullable=False)
    capacidade: Mapped[int] = mapped_column(Integer, nullable=False)
    andar: Mapped[int] = mapped_column(Integer, nullable=False)
    ocupacao_percentual: Mapped[float] = mapped_column(Float, nullable=False)
    explicabilidade: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Preparado para a rodada de intervenção humana (aceitar/rejeitar/editar).
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="sugerida")

    execucao: Mapped["ExecucaoAlocacao"] = relationship(back_populates="alocacoes")


class AlertaAlocacao(Base):
    __tablename__ = "alertas_alocacao"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    execucao_id: Mapped[int] = mapped_column(
        ForeignKey("execucoes_alocacao.id", ondelete="CASCADE"), nullable=False, index=True
    )
    equipe_id: Mapped[int] = mapped_column(Integer, nullable=False)
    equipe_afetada: Mapped[str] = mapped_column(String(120), nullable=False)
    restricao_nao_atendida: Mapped[str] = mapped_column(String(120), nullable=False)
    causa: Mapped[str] = mapped_column(String(400), nullable=False)
    encaminhamento: Mapped[str] = mapped_column(String(400), nullable=False)

    execucao: Mapped["ExecucaoAlocacao"] = relationship(back_populates="alertas")
