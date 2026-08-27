"""Enumerações compartilhadas entre ORM, schemas e (futuramente) o motor."""

from enum import Enum


class TipoSala(str, Enum):
    reuniao = "reuniao"
    treinamento = "treinamento"
    auditorio = "auditorio"
    laboratorio = "laboratorio"
    projeto = "projeto"
    colaborativo = "colaborativo"


class Prioridade(str, Enum):
    baixa = "baixa"
    media = "media"
    alta = "alta"
    critica = "critica"


class TipoRestricao(str, Enum):
    capacidade_minima = "capacidade_minima"
    andar_permitido = "andar_permitido"
    acessibilidade_obrigatoria = "acessibilidade_obrigatoria"
    equipamento_obrigatorio = "equipamento_obrigatorio"
    proximidade_obrigatoria = "proximidade_obrigatoria"
    setores_nao_compartilham = "setores_nao_compartilham"
    sala_reservada_setor = "sala_reservada_setor"
    prioridade_equipe = "prioridade_equipe"


class AlvoRestricao(str, Enum):
    sala = "sala"
    equipe = "equipe"
    setor = "setor"


# Qual entidade cada tipo de restrição referencia. Usado pela validação em
# schemas.py para rejeitar restrição apontada para o alvo errado.
ALVO_POR_TIPO: dict[TipoRestricao, AlvoRestricao] = {
    TipoRestricao.capacidade_minima: AlvoRestricao.equipe,
    TipoRestricao.andar_permitido: AlvoRestricao.equipe,
    TipoRestricao.acessibilidade_obrigatoria: AlvoRestricao.equipe,
    TipoRestricao.equipamento_obrigatorio: AlvoRestricao.equipe,
    TipoRestricao.proximidade_obrigatoria: AlvoRestricao.equipe,
    TipoRestricao.setores_nao_compartilham: AlvoRestricao.setor,
    TipoRestricao.sala_reservada_setor: AlvoRestricao.sala,
    TipoRestricao.prioridade_equipe: AlvoRestricao.equipe,
}
