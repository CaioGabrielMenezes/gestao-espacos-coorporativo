"""Avaliação de restrições.

Duas classes, conforme decidido no plano:

- **Duras**: dependem só do par (equipe, sala). Filtram arestas do grafo e
  NUNCA são violadas. Uma alocação que fira qualquer uma delas é impossível
  de o motor produzir, por construção.
- **De acoplamento**: dependem de onde as *outras* equipes ficaram, então não
  cabem no grafo bipartido. Entram como penalidade na busca local e as
  violações que sobrarem são contadas em `restricoes_violadas`.
"""

from dataclasses import dataclass

from engine.modelos import Cenario, EquipeEntrada, RestricaoEntrada, SalaEntrada


@dataclass(frozen=True)
class Veto:
    """Motivo pelo qual uma equipe não pode ocupar uma sala."""

    restricao: str  # nome legível, usado no campo `restricao_nao_atendida` do alerta
    detalhe: str


class IndiceRestricoes:
    """Agrupa as restrições por alvo para consulta em tempo constante."""

    def __init__(self, restricoes: tuple[RestricaoEntrada, ...]):
        self.todas = restricoes
        self.por_equipe: dict[int, list[RestricaoEntrada]] = {}
        self.por_sala: dict[int, list[RestricaoEntrada]] = {}
        self.por_setor: dict[int, list[RestricaoEntrada]] = {}

        for r in restricoes:
            if r.equipe_id is not None:
                self.por_equipe.setdefault(r.equipe_id, []).append(r)
            elif r.sala_id is not None:
                self.por_sala.setdefault(r.sala_id, []).append(r)
            elif r.setor_id is not None:
                self.por_setor.setdefault(r.setor_id, []).append(r)

    def da_equipe(self, equipe_id: int, tipo: str) -> list[RestricaoEntrada]:
        return [r for r in self.por_equipe.get(equipe_id, []) if r.tipo == tipo]

    def da_sala(self, sala_id: int, tipo: str) -> list[RestricaoEntrada]:
        return [r for r in self.por_sala.get(sala_id, []) if r.tipo == tipo]


# --------------------------------------------------------------------------
# Restrições duras
# --------------------------------------------------------------------------
def avaliar_veto(
    equipe: EquipeEntrada, sala: SalaEntrada, indice: IndiceRestricoes
) -> Veto | None:
    """Retorna o primeiro veto encontrado, ou None se a alocação é viável.

    A ordem importa: a capacidade é verificada primeiro porque é o motivo mais
    frequente e o mais informativo na mensagem de alerta.
    """
    # Regra dura absoluta da spec: nunca alocar equipe em sala menor que ela.
    if sala.capacidade < equipe.quantidade_funcionarios:
        return Veto(
            "capacidade mínima",
            f"{sala.identificacao} comporta {sala.capacidade} pessoas; "
            f"a equipe tem {equipe.quantidade_funcionarios}",
        )

    for r in indice.da_equipe(equipe.id, "capacidade_minima"):
        minimo = r.parametro.get("valor", 0)
        if sala.capacidade < minimo:
            return Veto(
                "capacidade mínima",
                f"{sala.identificacao} tem capacidade {sala.capacidade}, "
                f"abaixo do mínimo exigido de {minimo}",
            )

    for r in indice.da_equipe(equipe.id, "andar_permitido"):
        andares = r.parametro.get("andares", [])
        if sala.andar not in andares:
            return Veto(
                "andar permitido",
                f"{sala.identificacao} fica no andar {sala.andar}; "
                f"a equipe só pode ocupar os andares {andares}",
            )

    exige_acessibilidade = equipe.necessita_acessibilidade or bool(
        indice.da_equipe(equipe.id, "acessibilidade_obrigatoria")
    )
    if exige_acessibilidade and not sala.acessibilidade:
        return Veto(
            "acessibilidade obrigatória",
            f"{sala.identificacao} não é acessível",
        )

    exigidos = set(equipe.requisitos_especiais)
    for r in indice.da_equipe(equipe.id, "equipamento_obrigatorio"):
        exigidos.update(r.parametro.get("recursos", []))
    faltando = exigidos - set(sala.recursos)
    if faltando:
        return Veto(
            "equipamento obrigatório",
            f"{sala.identificacao} não possui: {', '.join(sorted(faltando))}",
        )

    for r in indice.da_sala(sala.id, "sala_reservada_setor"):
        reservada_para = r.parametro.get("setor_id")
        if reservada_para is not None and equipe.setor_id != reservada_para:
            return Veto(
                "sala reservada a setor",
                f"{sala.identificacao} é reservada ao setor {reservada_para}",
            )

    return None


def salas_viaveis(
    equipe: EquipeEntrada, cenario: Cenario, indice: IndiceRestricoes
) -> list[SalaEntrada]:
    """Todas as salas que a equipe poderia ocupar, ignorando concorrência."""
    return [s for s in cenario.salas if avaliar_veto(equipe, s, indice) is None]


def vetos_da_equipe(
    equipe: EquipeEntrada, cenario: Cenario, indice: IndiceRestricoes
) -> list[Veto]:
    """Vetos de todas as salas — base para explicar por que uma equipe não coube."""
    vetos = [avaliar_veto(equipe, s, indice) for s in cenario.salas]
    return [v for v in vetos if v is not None]


# --------------------------------------------------------------------------
# Restrições de acoplamento
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Violacao:
    tipo: str
    descricao: str
    equipes_envolvidas: tuple[int, ...]


def avaliar_acoplamento(
    atribuicao: dict[int, int],
    cenario: Cenario,
    indice: IndiceRestricoes,
) -> list[Violacao]:
    """Violações de restrições que dependem do conjunto todo.

    `atribuicao` mapeia equipe_id -> sala_id. A busca local chama esta função
    muitas vezes, então o agrupamento por (andar, setor) é feito uma vez só —
    o custo fica linear no número de equipes, e não quadrático.
    """
    salas = {s.id: s for s in cenario.salas}
    equipes = {e.id: e for e in cenario.equipes}
    violacoes: list[Violacao] = []

    # (andar, setor_id) -> equipes ali alocadas
    por_andar_setor: dict[tuple[int, int], list[EquipeEntrada]] = {}
    andares_ocupados: set[int] = set()
    for equipe_id, sala_id in atribuicao.items():
        equipe = equipes[equipe_id]
        andar = salas[sala_id].andar
        andares_ocupados.add(andar)
        por_andar_setor.setdefault((andar, equipe.setor_id), []).append(equipe)

    def andar_de(equipe_id: int) -> int | None:
        sala_id = atribuicao.get(equipe_id)
        return salas[sala_id].andar if sala_id is not None else None

    # Setores que não podem compartilhar área: interpretado como "não podem
    # ocupar o mesmo andar" (ver plano — no modelo de uma equipe por sala,
    # compartilhar sala é impossível, então a restrição só faz sentido no andar).
    # Conta-se uma violação por andar conflitante, não por par de equipes.
    for r in indice.todas:
        if r.tipo != "setores_nao_compartilham" or r.setor_id is None:
            continue
        for setor_proibido in r.parametro.get("setor_ids", []):
            for andar in sorted(andares_ocupados):
                grupo_a = por_andar_setor.get((andar, r.setor_id))
                grupo_b = por_andar_setor.get((andar, setor_proibido))
                if grupo_a and grupo_b:
                    violacoes.append(
                        Violacao(
                            "setores_nao_compartilham",
                            f"Os setores {r.setor_id} e {setor_proibido} não podem "
                            f"compartilhar área, mas ambos ficaram no andar {andar} "
                            f"('{grupo_a[0].nome}' e '{grupo_b[0].nome}')",
                            (grupo_a[0].id, grupo_b[0].id),
                        )
                    )

    # Proximidade obrigatória: mesmo andar das equipes indicadas.
    for r in indice.todas:
        if r.tipo != "proximidade_obrigatoria" or r.equipe_id is None:
            continue
        if r.equipe_id not in atribuicao:
            continue
        andar_origem = andar_de(r.equipe_id)
        for alvo_id in r.parametro.get("equipe_ids", []):
            if alvo_id not in atribuicao:
                continue
            if andar_de(alvo_id) != andar_origem:
                violacoes.append(
                    Violacao(
                        "proximidade_obrigatoria",
                        f"'{equipes[r.equipe_id].nome}' (andar {andar_origem}) e "
                        f"'{equipes[alvo_id].nome}' (andar {andar_de(alvo_id)}) "
                        f"deveriam ficar próximas",
                        (r.equipe_id, alvo_id),
                    )
                )

    return violacoes
