"""Função de qualidade de uma alocação.

Os pesos ficam num dicionário à parte, de propósito: eles são o "porquê" das
recomendações e precisam ser inspecionáveis e ajustáveis sem caçar constantes
espalhadas pelo código. A API os expõe no registro de governança, de modo que
uma execução antiga possa ser reinterpretada com os pesos que valiam na época.
"""

from engine.modelos import PESO_PRIORIDADE, Cenario, EquipeEntrada, SalaEntrada
from engine.restricoes import IndiceRestricoes, avaliar_acoplamento

# Componentes do score individual de um par (equipe, sala). Somam 100.
PESOS: dict[str, float] = {
    # Maximizar ocupação == minimizar assentos ociosos. É o critério dominante:
    # uma equipe de 6 numa sala de 80 é tecnicamente válida e péssima.
    "ocupacao": 60.0,
    # Atender à preferência de andar declarada pela equipe.
    "preferencia_andar": 20.0,
    # Minimizar movimentação entre andares. Com peso 20 contra 60 da ocupação,
    # uma equipe só troca de andar se isso render ganho real de aproveitamento
    # — mudança física de equipe tem custo que a métrica sozinha não enxerga.
    "permanencia": 20.0,
}

# Penalidades e bônus aplicados ao score global, não ao par isolado.
PENALIDADE_VIOLACAO_ACOPLAMENTO = 40.0
BONUS_PROXIMIDADE_DESEJADA = 15.0


def andares_atuais(cenario: Cenario) -> dict[int, int | None]:
    """Andar que cada equipe ocupa hoje — insumo do critério de permanência."""
    andar_por_sala = {s.id: s.andar for s in cenario.salas}
    return {
        e.id: andar_por_sala.get(e.sala_atual_id) if e.sala_atual_id else None
        for e in cenario.equipes
    }


def score_par(
    equipe: EquipeEntrada, sala: SalaEntrada, andar_atual: int | None = None
) -> float:
    """Qualidade de alocar `equipe` em `sala`, de 0 a 100.

    Considera apenas o par — nada aqui depende de onde as outras equipes
    ficaram. É o número mostrado na explicabilidade da recomendação.
    """
    return sum(criterios_do_par(equipe, sala, andar_atual).values())


def criterios_do_par(
    equipe: EquipeEntrada, sala: SalaEntrada, andar_atual: int | None = None
) -> dict[str, float]:
    """Score decomposto por critério — vai inteiro para a explicabilidade,
    para a justificativa não ser um número mágico."""
    ocupacao = equipe.quantidade_funcionarios / sala.capacidade if sala.capacidade else 0

    if equipe.preferencia_andar is None:
        # Sem preferência declarada, ninguém é premiado nem punido: o critério
        # vale metade para todas as salas, mantendo a comparação justa.
        preferencia = 0.5
    else:
        preferencia = 1.0 if sala.andar == equipe.preferencia_andar else 0.0

    # A spec pede "minimizar movimentação ENTRE ANDARES": trocar de sala no
    # mesmo andar custa pouco, mudar de andar custa muito. Daí os três níveis.
    if equipe.sala_atual_id is None:
        permanencia = 0.5
    elif sala.id == equipe.sala_atual_id:
        permanencia = 1.0
    elif andar_atual is not None and sala.andar == andar_atual:
        permanencia = 0.6
    else:
        permanencia = 0.0

    return {
        "ocupacao": round(ocupacao * PESOS["ocupacao"], 2),
        "preferencia_andar": round(preferencia * PESOS["preferencia_andar"], 2),
        "permanencia": round(permanencia * PESOS["permanencia"], 2),
    }


def score_total(
    atribuicao: dict[int, int], cenario: Cenario, indice: IndiceRestricoes
) -> float:
    """Qualidade global de uma solução completa.

    É esta função que a busca local maximiza. Combina o score de cada par
    (ponderado pela prioridade da equipe) com os efeitos que só existem no
    conjunto: proximidade atendida e violações de acoplamento.
    """
    salas = {s.id: s for s in cenario.salas}
    equipes = {e.id: e for e in cenario.equipes}
    andares = andares_atuais(cenario)

    total = 0.0
    for equipe_id, sala_id in atribuicao.items():
        equipe = equipes[equipe_id]
        peso = PESO_PRIORIDADE.get(equipe.prioridade, 2)
        total += score_par(equipe, salas[sala_id], andares.get(equipe_id)) * peso

    # Bônus por proximidade desejada (preferência da equipe, não restrição).
    for equipe_id, sala_id in atribuicao.items():
        andar = salas[sala_id].andar
        for vizinho_id in equipes[equipe_id].proximidade_desejada:
            vizinho_sala = atribuicao.get(vizinho_id)
            if vizinho_sala is not None and salas[vizinho_sala].andar == andar:
                total += BONUS_PROXIMIDADE_DESEJADA

    total -= PENALIDADE_VIOLACAO_ACOPLAMENTO * len(
        avaliar_acoplamento(atribuicao, cenario, indice)
    )
    return total
