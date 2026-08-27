"""Contratos de dados da API (Pydantic v2).

Conforme o CLAUDE.md, é aqui que backend, allocation-engine e frontend
concordam no formato. O /docs do FastAPI é gerado a partir destes modelos.

Convenção de edição: PUT recebe o corpo completo (substituição), então os
schemas *Update herdam dos *Create.
"""

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.enums import ALVO_POR_TIPO, AlvoRestricao, Prioridade, TipoRestricao, TipoSala

Andar = Annotated[int, Field(ge=1, le=9, description="Andar do prédio, de 1 a 9")]


# --------------------------------------------------------------------------
# Sala
# --------------------------------------------------------------------------
class Disponibilidade(BaseModel):
    dias: list[str] = Field(default_factory=lambda: ["seg", "ter", "qua", "qui", "sex"])
    horario_inicio: str = "08:00"
    horario_fim: str = "18:00"


class SalaBase(BaseModel):
    identificacao: str = Field(min_length=1, max_length=80, examples=["Sala 704"])
    andar: Andar
    capacidade: int = Field(gt=0, description="Deve ser maior que zero")
    tipo: TipoSala
    recursos: list[str] = Field(default_factory=list, examples=[["projetor", "wifi"]])
    acessibilidade: bool = False
    disponibilidade: Disponibilidade = Field(default_factory=Disponibilidade)


class SalaCreate(SalaBase):
    pass


class SalaUpdate(SalaBase):
    pass


class SalaRead(SalaBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


# --------------------------------------------------------------------------
# Setor
# --------------------------------------------------------------------------
class SetorBase(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    coordenador: str = Field(min_length=1, max_length=120)
    total_funcionarios: int = Field(ge=0, default=0)


class SetorCreate(SetorBase):
    pass


class SetorUpdate(SetorBase):
    pass


class SetorRead(SetorBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


# --------------------------------------------------------------------------
# Equipe
# --------------------------------------------------------------------------
class EquipeBase(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    quantidade_funcionarios: int = Field(gt=0, description="Tamanho da equipe")
    sala_atual_id: int | None = Field(
        default=None,
        description="Sala que a equipe ocupa hoje, antes de qualquer otimização",
    )
    horario_necessario: str = Field(default="08:00-18:00", max_length=40)
    requisitos_especiais: list[str] = Field(
        default_factory=list, examples=[["projetor", "bancada"]]
    )
    preferencia_andar: Andar | None = None
    necessita_acessibilidade: bool = False
    proximidade_desejada: list[int] = Field(
        default_factory=list, description="ids de equipes com quem deve ficar próxima"
    )
    prioridade: Prioridade = Prioridade.media


class EquipeCreate(EquipeBase):
    """O setor vem da rota (/api/setores/{setor_id}/equipes), não do corpo."""


class EquipeUpdate(EquipeBase):
    setor_id: int | None = Field(
        default=None, description="Informe para mover a equipe de setor"
    )


class EquipeRead(EquipeBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    setor_id: int


# --------------------------------------------------------------------------
# Restrição
# --------------------------------------------------------------------------

# Chaves obrigatórias de `parametro` por tipo de restrição.
CAMPOS_PARAMETRO: dict[TipoRestricao, tuple[str, ...]] = {
    TipoRestricao.capacidade_minima: ("valor",),
    TipoRestricao.andar_permitido: ("andares",),
    TipoRestricao.acessibilidade_obrigatoria: (),
    TipoRestricao.equipamento_obrigatorio: ("recursos",),
    TipoRestricao.proximidade_obrigatoria: ("equipe_ids",),
    TipoRestricao.setores_nao_compartilham: ("setor_ids",),
    TipoRestricao.sala_reservada_setor: ("setor_id",),
    TipoRestricao.prioridade_equipe: ("nivel",),
}


class RestricaoBase(BaseModel):
    tipo: TipoRestricao
    sala_id: int | None = None
    equipe_id: int | None = None
    setor_id: int | None = None
    parametro: dict[str, Any] = Field(default_factory=dict)
    descricao: str | None = Field(default=None, max_length=240)

    @model_validator(mode="after")
    def _validar_alvo_e_parametro(self):
        alvos = {
            AlvoRestricao.sala: self.sala_id,
            AlvoRestricao.equipe: self.equipe_id,
            AlvoRestricao.setor: self.setor_id,
        }
        preenchidos = [nome for nome, valor in alvos.items() if valor is not None]

        if len(preenchidos) != 1:
            raise ValueError(
                "Informe exatamente um alvo entre sala_id, equipe_id e setor_id "
                f"(recebidos: {len(preenchidos)})."
            )

        esperado = ALVO_POR_TIPO[self.tipo]
        if preenchidos[0] != esperado:
            raise ValueError(
                f"A restrição '{self.tipo.value}' se aplica a {esperado.value}, "
                f"mas foi informado {preenchidos[0].value}_id."
            )

        faltando = [c for c in CAMPOS_PARAMETRO[self.tipo] if c not in self.parametro]
        if faltando:
            raise ValueError(
                f"'parametro' da restrição '{self.tipo.value}' exige as chaves: "
                f"{', '.join(faltando)}."
            )
        return self


class RestricaoCreate(RestricaoBase):
    pass


class RestricaoRead(RestricaoBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
