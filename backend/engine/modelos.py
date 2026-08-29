"""Estruturas de entrada do motor.

Propositalmente dataclasses puras, sem SQLAlchemy: o motor não conhece banco.
Quem adapta ORM -> Cenario é o router (app/routers/alocacoes.py). É isso que
permite aos testes metamórficos montar dezenas de cenários sintéticos sem
subir banco nenhum.
"""

from dataclasses import dataclass, field, replace


@dataclass(frozen=True)
class SalaEntrada:
    id: int
    identificacao: str
    andar: int
    capacidade: int
    tipo: str = "reuniao"
    recursos: frozenset[str] = frozenset()
    acessibilidade: bool = False
    # Janela em que a sala pode ser usada, no formato "HH:MM". O padrão é
    # permissivo de propósito: um cenário que não declara disponibilidade não
    # deve ganhar uma restrição que ninguém pediu.
    horario_inicio: str = "00:00"
    horario_fim: str = "23:59"


@dataclass(frozen=True)
class EquipeEntrada:
    id: int
    nome: str
    setor_id: int
    quantidade_funcionarios: int
    requisitos_especiais: frozenset[str] = frozenset()
    preferencia_andar: int | None = None
    necessita_acessibilidade: bool = False
    proximidade_desejada: tuple[int, ...] = ()
    prioridade: str = "media"
    sala_atual_id: int | None = None
    # Faixa que a equipe precisa ocupar, no formato "HH:MM-HH:MM". Vazio
    # significa "sem exigência de horário".
    horario_necessario: str = ""


@dataclass(frozen=True)
class RestricaoEntrada:
    id: int
    tipo: str
    sala_id: int | None = None
    equipe_id: int | None = None
    setor_id: int | None = None
    parametro: dict = field(default_factory=dict)
    descricao: str | None = None


@dataclass(frozen=True)
class Cenario:
    """Entrada completa de uma execução do motor."""

    salas: tuple[SalaEntrada, ...] = ()
    equipes: tuple[EquipeEntrada, ...] = ()
    restricoes: tuple[RestricaoEntrada, ...] = ()

    def com_sala(self, sala: SalaEntrada) -> "Cenario":
        """Novo cenário com uma sala a mais — usado pelo teste metamórfico 1."""
        return replace(self, salas=self.salas + (sala,))

    def sem_restricao(self, restricao_id: int) -> "Cenario":
        """Novo cenário sem uma restrição — usado pelo teste metamórfico 2."""
        return replace(
            self,
            restricoes=tuple(r for r in self.restricoes if r.id != restricao_id),
        )


# Peso de cada nível de prioridade no desempate entre equipes.
PESO_PRIORIDADE: dict[str, int] = {
    "critica": 4,
    "alta": 3,
    "media": 2,
    "baixa": 1,
}
