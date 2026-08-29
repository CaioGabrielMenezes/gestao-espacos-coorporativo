"""Indicadores executivos do prédio (specs/dashboard.md).

Módulo puro, como o resto do `engine`: recebe um `Cenario` e uma atribuição
equipe -> sala, devolve Pydantic. Não conhece banco.

A distinção entre as três taxas abaixo não é preciosismo — elas respondem a
perguntas diferentes e confundi-las num número só é o erro mais comum num
painel de ocupação:

- `ocupacao_predio`  : quanto do prédio inteiro está de fato sendo usado.
- `utilizacao_salas` : quantas salas estão em uso, independente de quão cheias.
- `aproveitamento`   : quão bem as salas EM USO estão preenchidas.

Um prédio com uma única sala lotada tem aproveitamento 100% e ocupação
pífia. Só as três juntas contam a história.
"""

from pydantic import BaseModel, Field

from engine.modelos import Cenario
from engine.restricoes import IndiceRestricoes, avaliar_acoplamento


class IndicadoresAndar(BaseModel):
    andar: int
    salas: int
    salas_ocupadas: int
    salas_disponiveis: int
    capacidade: int
    pessoas: int
    ocupacao_percentual: float


class IndicadoresPredio(BaseModel):
    total_salas: int
    salas_ocupadas: int
    salas_disponiveis: int
    capacidade_total: int
    capacidade_em_uso: int = Field(
        description="Soma da capacidade das salas ocupadas (não das pessoas)"
    )
    capacidade_disponivel: int
    assentos_ociosos: int = Field(
        description="Lugares vagos dentro das salas ocupadas"
    )
    ocupacao_predio_percentual: float
    utilizacao_salas_percentual: float
    aproveitamento_percentual: float


class IndicadoresPessoas(BaseModel):
    total_funcionarios: int
    funcionarios_alocados: int
    funcionarios_nao_alocados: int


class IndicadoresEquipes(BaseModel):
    total: int
    alocadas: int
    nao_alocadas: int
    taxa_alocacao_percentual: float


class Indicadores(BaseModel):
    origem: str = Field(
        description="'estado_atual' ou 'execucao' — de onde vieram estes números"
    )
    execucao_id: int | None = None
    predio: IndicadoresPredio
    pessoas: IndicadoresPessoas
    equipes: IndicadoresEquipes
    restricoes_violadas: int
    por_andar: list[IndicadoresAndar]


def calcular_indicadores(
    cenario: Cenario,
    atribuicao: dict[int, int],
    origem: str = "estado_atual",
    execucao_id: int | None = None,
) -> Indicadores:
    """Fotografia do prédio sob uma dada atribuição de equipes a salas."""
    salas = {s.id: s for s in cenario.salas}
    equipes = {e.id: e for e in cenario.equipes}
    indice = IndiceRestricoes(cenario.restricoes)

    ocupadas = set(atribuicao.values())
    capacidade_total = sum(s.capacidade for s in cenario.salas)
    capacidade_em_uso = sum(salas[s].capacidade for s in ocupadas)
    pessoas_alocadas = sum(equipes[e].quantidade_funcionarios for e in atribuicao)
    total_funcionarios = sum(e.quantidade_funcionarios for e in cenario.equipes)

    predio = IndicadoresPredio(
        total_salas=len(cenario.salas),
        salas_ocupadas=len(ocupadas),
        salas_disponiveis=len(cenario.salas) - len(ocupadas),
        capacidade_total=capacidade_total,
        capacidade_em_uso=capacidade_em_uso,
        capacidade_disponivel=capacidade_total - capacidade_em_uso,
        assentos_ociosos=capacidade_em_uso - pessoas_alocadas,
        ocupacao_predio_percentual=_pct(pessoas_alocadas, capacidade_total),
        utilizacao_salas_percentual=_pct(len(ocupadas), len(cenario.salas)),
        aproveitamento_percentual=_pct(pessoas_alocadas, capacidade_em_uso),
    )

    pessoas = IndicadoresPessoas(
        total_funcionarios=total_funcionarios,
        funcionarios_alocados=pessoas_alocadas,
        funcionarios_nao_alocados=total_funcionarios - pessoas_alocadas,
    )

    equipes_info = IndicadoresEquipes(
        total=len(cenario.equipes),
        alocadas=len(atribuicao),
        nao_alocadas=len(cenario.equipes) - len(atribuicao),
        taxa_alocacao_percentual=_pct(len(atribuicao), len(cenario.equipes)),
    )

    return Indicadores(
        origem=origem,
        execucao_id=execucao_id,
        predio=predio,
        pessoas=pessoas,
        equipes=equipes_info,
        restricoes_violadas=len(avaliar_acoplamento(atribuicao, cenario, indice)),
        por_andar=_por_andar(cenario, atribuicao),
    )


class SalaNoMapa(BaseModel):
    sala_id: int
    identificacao: str
    capacidade: int
    tipo: str
    acessibilidade: bool
    equipe_id: int | None = None
    equipe: str | None = None
    pessoas: int = 0
    ocupacao_percentual: float = 0.0
    # Faixa textual da ocupação. Existe para a tela não depender só de cor:
    # quem não distingue as cores, ou vê num projetor ruim, lê a faixa.
    faixa: str


class AndarNoMapa(BaseModel):
    andar: int
    salas: list[SalaNoMapa]
    capacidade: int
    pessoas: int
    ocupacao_percentual: float


class MapaPredio(BaseModel):
    origem: str
    execucao_id: int | None = None
    andares: list[AndarNoMapa]


def montar_mapa(
    cenario: Cenario,
    atribuicao: dict[int, int],
    origem: str = "estado_atual",
    execucao_id: int | None = None,
) -> MapaPredio:
    """Planta do prédio: andares, salas e quem ocupa cada uma."""
    equipes = {e.id: e for e in cenario.equipes}
    ocupante_por_sala = {sala_id: eid for eid, sala_id in atribuicao.items()}

    andares = []
    for andar in sorted({s.andar for s in cenario.salas}):
        do_andar = sorted(
            (s for s in cenario.salas if s.andar == andar),
            key=lambda s: s.identificacao,
        )

        salas_mapa = []
        for sala in do_andar:
            equipe_id = ocupante_por_sala.get(sala.id)
            equipe = equipes.get(equipe_id) if equipe_id is not None else None
            pessoas = equipe.quantidade_funcionarios if equipe else 0
            ocupacao = _pct(pessoas, sala.capacidade)

            salas_mapa.append(
                SalaNoMapa(
                    sala_id=sala.id,
                    identificacao=sala.identificacao,
                    capacidade=sala.capacidade,
                    tipo=sala.tipo,
                    acessibilidade=sala.acessibilidade,
                    equipe_id=equipe_id,
                    equipe=equipe.nome if equipe else None,
                    pessoas=pessoas,
                    ocupacao_percentual=ocupacao,
                    faixa=_faixa(equipe is not None, ocupacao),
                )
            )

        capacidade = sum(s.capacidade for s in do_andar)
        pessoas_andar = sum(s.pessoas for s in salas_mapa)
        andares.append(
            AndarNoMapa(
                andar=andar,
                salas=salas_mapa,
                capacidade=capacidade,
                pessoas=pessoas_andar,
                ocupacao_percentual=_pct(pessoas_andar, capacidade),
            )
        )

    return MapaPredio(origem=origem, execucao_id=execucao_id, andares=andares)


def _faixa(ocupada: bool, ocupacao: float) -> str:
    """Faixa de ocupação de uma sala.

    'subutilizada' é a faixa que importa para o coordenador: a sala está em
    uso, então não aparece como disponível, mas está desperdiçando espaço.
    """
    if not ocupada:
        return "vazia"
    if ocupacao < 50:
        return "subutilizada"
    if ocupacao < 85:
        return "adequada"
    return "cheia"


def _por_andar(cenario: Cenario, atribuicao: dict[int, int]) -> list[IndicadoresAndar]:
    """Um registro por andar que tenha ao menos uma sala cadastrada.

    Andares sem sala nenhuma são omitidos em vez de aparecerem zerados: uma
    linha "andar 4: 0%" sugere um andar vazio quando na verdade ele não existe
    no cadastro.
    """
    equipes = {e.id: e for e in cenario.equipes}

    pessoas_por_sala = {
        sala_id: equipes[equipe_id].quantidade_funcionarios
        for equipe_id, sala_id in atribuicao.items()
    }
    ocupadas = set(atribuicao.values())

    resultado = []
    for andar in sorted({s.andar for s in cenario.salas}):
        do_andar = [s for s in cenario.salas if s.andar == andar]
        ocupadas_no_andar = [s for s in do_andar if s.id in ocupadas]
        capacidade = sum(s.capacidade for s in do_andar)
        pessoas = sum(pessoas_por_sala.get(s.id, 0) for s in do_andar)

        resultado.append(
            IndicadoresAndar(
                andar=andar,
                salas=len(do_andar),
                salas_ocupadas=len(ocupadas_no_andar),
                salas_disponiveis=len(do_andar) - len(ocupadas_no_andar),
                capacidade=capacidade,
                pessoas=pessoas,
                # Sobre a capacidade TOTAL do andar, não só das salas em uso:
                # é a leitura útil para decidir onde há espaço sobrando.
                ocupacao_percentual=_pct(pessoas, capacidade),
            )
        )

    return resultado


def _pct(parte: int, total: int) -> float:
    return round(parte / total * 100, 1) if total else 0.0
