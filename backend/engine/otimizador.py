"""Orquestração da alocação.

Fluxo:
    1. filtra arestas viáveis pelas restrições duras
    2. emparelhamento máximo  -> maximiza o nº de equipes alocadas (ótimo)
    3. busca local            -> melhora a qualidade sem nunca reduzir o nº alocado
    4. monta recomendações, explicabilidade, alertas e governança

A separação entre os passos 2 e 3 é deliberada: o passo 2 é ótimo e
demonstrável, o passo 3 é heurístico. O motor é, portanto, **ótimo no número
de equipes alocadas e heurístico na qualidade da distribuição** — e é assim
que a limitação deve ser apresentada, sem exagerar a garantia.
"""

from collections import Counter
from datetime import datetime, timezone
from time import perf_counter

from engine.matching import emparelhamento_maximo
from engine.modelos import PESO_PRIORIDADE, Cenario, EquipeEntrada, SalaEntrada
from engine.restricoes import (
    IndiceRestricoes,
    avaliar_acoplamento,
    avaliar_veto,
)
from engine.resultado import (
    Alerta,
    Comparativo,
    Explicabilidade,
    Metricas,
    Recomendacao,
    RegistroGovernanca,
    ResultadoAlocacao,
    ViolacaoRegistrada,
)
from engine.scoring import (
    PESOS,
    andares_atuais,
    criterios_do_par,
    score_par,
    score_total,
)

ALGORITMO = "allocation-engine-v1"

MAX_PASSES_BUSCA_LOCAL = 30
MAX_TENTATIVAS_REPARO = 300

ENCAMINHAMENTOS = {
    "capacidade mínima": "dividir equipe em dois grupos ou liberar sala adicional",
    "andar permitido": (
        "rever a restrição de andar da equipe ou liberar sala nos andares permitidos"
    ),
    "acessibilidade obrigatória": (
        "adaptar uma sala compatível para acessibilidade ou rever a exigência"
    ),
    "equipamento obrigatório": (
        "instalar o equipamento faltante numa sala compatível ou rever o requisito"
    ),
    "sala reservada a setor": "rever a reserva da sala para o setor",
}


def otimizar(
    cenario: Cenario,
    usuario: str = "coordenador-geral",
    fixacoes: dict[int, int] | None = None,
) -> ResultadoAlocacao:
    """Executa uma otimização completa e devolve o resultado explicável.

    `fixacoes` mapeia equipe_id -> sala_id que devem ser preservados como
    estão. É o que sustenta a re-otimização depois de intervenção humana: as
    decisões que o coordenador já aceitou ou editou saem do grafo, e o motor
    reotimiza apenas o que sobrou. Sem fixações (o caso normal, e o usado
    pelos testes metamórficos) o comportamento é exatamente o de antes.
    """
    inicio = perf_counter()
    indice = IndiceRestricoes(cenario.restricoes)
    fixacoes = _fixacoes_validas(fixacoes, cenario)

    salas_por_id = {s.id: s for s in cenario.salas}
    equipes_por_id = {e.id: e for e in cenario.equipes}
    andares = andares_atuais(cenario)

    # Salas viáveis por equipe, ordenadas por qualidade decrescente. O
    # emparelhamento percorre nessa ordem, então entre soluções de mesmo
    # tamanho ele tende a escolher a de melhor score.
    viaveis: dict[int, list[SalaEntrada]] = {
        equipe.id: sorted(
            (s for s in cenario.salas if avaliar_veto(equipe, s, indice) is None),
            key=lambda s, e=equipe: (-score_par(e, s, andares.get(e.id)), s.id),
        )
        for equipe in cenario.equipes
    }
    viaveis_ids = {eid: {s.id for s in lista} for eid, lista in viaveis.items()}

    # Equipes e salas fixadas saem do problema: o emparelhamento roda só sobre
    # o que ainda está em aberto.
    salas_fixadas = set(fixacoes.values())
    livres = [e for e in cenario.equipes if e.id not in fixacoes]

    # Ordem determinística: prioridade, depois equipes maiores (mais difíceis
    # de acomodar), depois id como desempate final.
    ordem = sorted(
        (e.id for e in livres),
        key=lambda eid: (
            -PESO_PRIORIDADE.get(equipes_por_id[eid].prioridade, 2),
            -equipes_por_id[eid].quantidade_funcionarios,
            eid,
        ),
    )

    adjacencia = {
        e.id: [s.id for s in viaveis[e.id] if s.id not in salas_fixadas] for e in livres
    }
    atribuicao = emparelhamento_maximo(adjacencia, ordem)

    total_alocado_otimo = len(atribuicao)
    atribuicao = _busca_local(
        atribuicao, cenario, indice, viaveis, viaveis_ids, andares, salas_fixadas
    )
    assert len(atribuicao) == total_alocado_otimo, (
        "A busca local reduziu o número de equipes alocadas — invariante violada."
    )
    # As fixações voltam ao conjunto só depois da busca local, para que ela
    # jamais as mova.
    atribuicao.update(fixacoes)

    recomendacoes = _montar_recomendacoes(
        atribuicao, indice, viaveis, salas_por_id, equipes_por_id, andares
    )
    alertas = _montar_alertas(atribuicao, cenario, indice, viaveis)
    violacoes = [
        ViolacaoRegistrada(
            tipo=v.tipo, descricao=v.descricao, equipes_envolvidas=list(v.equipes_envolvidas)
        )
        for v in avaliar_acoplamento(atribuicao, cenario, indice)
    ]

    metricas_depois = _metricas(atribuicao, cenario, indice)
    metricas_antes = _metricas(atribuicao_atual(cenario), cenario, indice)
    duracao_ms = (perf_counter() - inicio) * 1000

    governanca = RegistroGovernanca(
        timestamp=datetime.now(timezone.utc),
        usuario=usuario,
        algoritmo=ALGORITMO,
        equipes_analisadas=len(cenario.equipes),
        salas_analisadas=len(cenario.salas),
        equipes_alocadas=len(atribuicao),
        equipes_nao_alocadas=len(cenario.equipes) - len(atribuicao),
        restricoes_violadas=len(violacoes),
        ocupacao_prevista=metricas_depois.ocupacao_media,
        duracao_ms=round(duracao_ms, 2),
        pesos=dict(PESOS),
    )

    return ResultadoAlocacao(
        recomendacoes=recomendacoes,
        alertas=alertas,
        violacoes=violacoes,
        governanca=governanca,
        comparativo=Comparativo(antes=metricas_antes, depois=metricas_depois),
    )


# --------------------------------------------------------------------------
# Busca local
# --------------------------------------------------------------------------
def _busca_local(
    atribuicao: dict[int, int],
    cenario: Cenario,
    indice: IndiceRestricoes,
    viaveis: dict[int, list[SalaEntrada]],
    viaveis_ids: dict[int, set[int]],
    andares: dict[int, int | None],
    salas_fixadas: set[int],
) -> dict[int, int]:
    """Melhora a qualidade mantendo o número de equipes alocadas.

    Só usa dois movimentos — mover para sala livre e trocar duas equipes de
    sala — e ambos preservam a cardinalidade por construção. É daí que vem a
    invariante verificada no `assert` do chamador.

    `salas_fixadas` são salas travadas por decisão humana: continuam listadas
    como viáveis para outras equipes, então precisam ser excluídas aqui
    explicitamente, senão a busca local as roubaria.
    """
    atribuicao = _melhorar_separavel(
        atribuicao, cenario, viaveis, viaveis_ids, andares, salas_fixadas
    )
    return _reparar_acoplamento(
        atribuicao, cenario, indice, viaveis, viaveis_ids, salas_fixadas
    )


def _melhorar_separavel(
    atribuicao: dict[int, int],
    cenario: Cenario,
    viaveis: dict[int, list[SalaEntrada]],
    viaveis_ids: dict[int, set[int]],
    andares: dict[int, int | None],
    salas_fixadas: set[int],
) -> dict[int, int]:
    """Fase A — otimiza a parte do score que depende só do par (equipe, sala).

    O ganho de cada movimento é calculado em O(1), o que permite varrer todos
    os candidatos a cada passe sem estourar o orçamento de tempo.
    """
    salas = {s.id: s for s in cenario.salas}
    equipes = {e.id: e for e in cenario.equipes}
    peso = {eid: PESO_PRIORIDADE.get(equipes[eid].prioridade, 2) for eid in atribuicao}

    for _ in range(MAX_PASSES_BUSCA_LOCAL):
        ocupante = {sala_id: eid for eid, sala_id in atribuicao.items()}
        melhor_ganho = 1e-9
        melhor_movimento: tuple[int, int] | None = None

        for eid in sorted(atribuicao):
            sala_atual = atribuicao[eid]
            base = score_par(equipes[eid], salas[sala_atual], andares.get(eid)) * peso[eid]

            for sala in viaveis[eid]:
                if sala.id == sala_atual or sala.id in salas_fixadas:
                    continue
                outro = ocupante.get(sala.id)

                if outro is None:
                    ganho = (
                        score_par(equipes[eid], sala, andares.get(eid)) * peso[eid] - base
                    )
                else:
                    # Troca só vale se a sala atual também servir para o outro.
                    if sala_atual not in viaveis_ids[outro]:
                        continue
                    base_outro = (
                        score_par(equipes[outro], salas[sala.id], andares.get(outro))
                        * peso[outro]
                    )
                    ganho = (
                        score_par(equipes[eid], sala, andares.get(eid)) * peso[eid]
                        + score_par(equipes[outro], salas[sala_atual], andares.get(outro))
                        * peso[outro]
                        - base
                        - base_outro
                    )

                if ganho > melhor_ganho:
                    melhor_ganho = ganho
                    melhor_movimento = (eid, sala.id)

        if melhor_movimento is None:
            break

        eid, destino = melhor_movimento
        origem = atribuicao[eid]
        deslocado = ocupante.get(destino)
        atribuicao[eid] = destino
        if deslocado is not None:
            atribuicao[deslocado] = origem

    return atribuicao


def _reparar_acoplamento(
    atribuicao: dict[int, int],
    cenario: Cenario,
    indice: IndiceRestricoes,
    viaveis: dict[int, list[SalaEntrada]],
    viaveis_ids: dict[int, set[int]],
    salas_fixadas: set[int],
) -> dict[int, int]:
    """Fase B — tenta desfazer violações de restrições de acoplamento.

    Aqui o score completo é avaliado (é ele que enxerga proximidade e
    violações), mas só para as equipes efetivamente envolvidas em alguma
    violação, o que mantém o custo baixo.
    """
    melhor_score = score_total(atribuicao, cenario, indice)
    tentativas = 0

    while tentativas < MAX_TENTATIVAS_REPARO:
        violacoes = avaliar_acoplamento(atribuicao, cenario, indice)
        if not violacoes:
            break

        envolvidas = sorted({eid for v in violacoes for eid in v.equipes_envolvidas})
        melhorou = False

        for eid in envolvidas:
            if eid not in atribuicao:
                continue
            origem = atribuicao[eid]
            ocupante = {sala_id: dono for dono, sala_id in atribuicao.items()}

            for sala in viaveis[eid]:
                if sala.id == origem or sala.id in salas_fixadas:
                    continue
                tentativas += 1

                candidata = dict(atribuicao)
                deslocado = ocupante.get(sala.id)
                if deslocado is not None:
                    if origem not in viaveis_ids[deslocado]:
                        continue
                    candidata[deslocado] = origem
                candidata[eid] = sala.id

                novo_score = score_total(candidata, cenario, indice)
                if novo_score > melhor_score + 1e-9:
                    atribuicao = candidata
                    melhor_score = novo_score
                    melhorou = True
                    break

            if melhorou:
                break

        if not melhorou:
            break

    return atribuicao


# --------------------------------------------------------------------------
# Montagem do resultado
# --------------------------------------------------------------------------
def _montar_recomendacoes(
    atribuicao: dict[int, int],
    indice: IndiceRestricoes,
    viaveis: dict[int, list[SalaEntrada]],
    salas_por_id: dict[int, SalaEntrada],
    equipes_por_id: dict[int, EquipeEntrada],
    andares: dict[int, int | None],
) -> list[Recomendacao]:
    recomendacoes = []

    for eid in sorted(atribuicao):
        equipe = equipes_por_id[eid]
        sala = salas_por_id[atribuicao[eid]]
        ocupacao = equipe.quantidade_funcionarios / sala.capacidade
        alternativas = viaveis[eid]

        explicabilidade = Explicabilidade(
            sala=sala.identificacao,
            equipe=equipe.nome,
            capacidade_sala=sala.capacidade,
            tamanho_equipe=equipe.quantidade_funcionarios,
            ocupacao_prevista=_percentual(ocupacao),
            recursos_atendidos=_recursos_atendidos(equipe, sala, indice),
            restricao_andar_atendida=_andar_atendido(equipe, sala, indice),
            alternativas_avaliadas=len(alternativas),
            justificativa=_justificar(equipe, sala, alternativas, atribuicao, equipes_por_id),
            score=round(score_par(equipe, sala, andares.get(eid)), 2),
            criterios=criterios_do_par(equipe, sala, andares.get(eid)),
        )

        recomendacoes.append(
            Recomendacao(
                equipe_id=equipe.id,
                equipe=equipe.nome,
                pessoas=equipe.quantidade_funcionarios,
                sala_id=sala.id,
                sala_sugerida=sala.identificacao,
                capacidade=sala.capacidade,
                andar=sala.andar,
                ocupacao_prevista=_percentual(ocupacao),
                ocupacao_percentual=round(ocupacao * 100, 1),
                explicabilidade=explicabilidade,
            )
        )

    return recomendacoes


def _justificar(
    equipe: EquipeEntrada,
    escolhida: SalaEntrada,
    alternativas: list[SalaEntrada],
    atribuicao: dict[int, int],
    equipes_por_id: dict[int, EquipeEntrada],
) -> str:
    if len(alternativas) == 1:
        return (
            f"{escolhida.identificacao} era a única sala compatível com todas as "
            f"restrições da equipe."
        )

    melhor = alternativas[0]
    ocupacao_escolhida = equipe.quantidade_funcionarios / escolhida.capacidade

    if melhor.id == escolhida.id:
        segunda = alternativas[1]
        ocupacao_segunda = equipe.quantidade_funcionarios / segunda.capacidade
        return (
            f"Melhor equilíbrio entre capacidade, localização e restrições dentre as "
            f"{len(alternativas)} alternativas avaliadas: "
            f"{_percentual(ocupacao_escolhida)} de ocupação, contra "
            f"{_percentual(ocupacao_segunda)} da segunda melhor opção "
            f"({segunda.identificacao})."
        )

    # A sala individualmente melhor foi para outra equipe. Isso não é um
    # defeito: o motor prioriza alocar o maior número de equipes, e ceder esta
    # sala foi o que permitiu acomodar a outra.
    dono_id = next((e for e, s in atribuicao.items() if s == melhor.id), None)
    dono = equipes_por_id[dono_id].nome if dono_id is not None else "outra equipe"
    return (
        f"Dentre as {len(alternativas)} alternativas avaliadas, {melhor.identificacao} "
        f"teria score individual maior, mas foi atribuída a '{dono}', que dispunha de "
        f"menos opções compatíveis. {escolhida.identificacao} é a melhor escolha "
        f"restante ({_percentual(ocupacao_escolhida)} de ocupação) e preserva o número "
        f"total de equipes alocadas."
    )


def _montar_alertas(
    atribuicao: dict[int, int],
    cenario: Cenario,
    indice: IndiceRestricoes,
    viaveis: dict[int, list[SalaEntrada]],
) -> list[Alerta]:
    """Toda equipe não alocada gera alerta — nenhuma some do resultado."""
    alertas = []

    for equipe in sorted(cenario.equipes, key=lambda e: e.id):
        if equipe.id in atribuicao:
            continue

        compativeis = viaveis[equipe.id]

        if compativeis:
            # Existiam salas compatíveis, mas a concorrência as consumiu.
            nomes = ", ".join(s.identificacao for s in compativeis[:3])
            alertas.append(
                Alerta(
                    equipe_id=equipe.id,
                    equipe_afetada=equipe.nome,
                    restricao_nao_atendida="disponibilidade de sala",
                    causa=(
                        f"As {len(compativeis)} salas compatíveis ({nomes}"
                        f"{'...' if len(compativeis) > 3 else ''}) foram ocupadas por "
                        f"equipes que não tinham outra opção viável."
                    ),
                    encaminhamento=(
                        "liberar uma das salas compatíveis, flexibilizar as restrições "
                        "desta equipe ou acrescentar sala equivalente"
                    ),
                )
            )
            continue

        # Nenhuma sala compatível: identifica a restrição que mais bloqueia.
        vetos = [avaliar_veto(equipe, s, indice) for s in cenario.salas]
        vetos = [v for v in vetos if v is not None]

        if not vetos:
            # Cenário sem sala nenhuma cadastrada.
            alertas.append(
                Alerta(
                    equipe_id=equipe.id,
                    equipe_afetada=equipe.nome,
                    restricao_nao_atendida="disponibilidade de sala",
                    causa="Não há salas cadastradas para avaliar.",
                    encaminhamento="cadastrar salas antes de otimizar",
                )
            )
            continue

        dominante = Counter(v.restricao for v in vetos).most_common(1)[0][0]

        if dominante == "capacidade mínima" and cenario.salas:
            maior = max(cenario.salas, key=lambda s: s.capacidade)
            causa = (
                f"Maior sala disponível comporta {maior.capacidade} pessoas; "
                f"equipe tem {equipe.quantidade_funcionarios}"
            )
        else:
            causa = next(v.detalhe for v in vetos if v.restricao == dominante)

        alertas.append(
            Alerta(
                equipe_id=equipe.id,
                equipe_afetada=equipe.nome,
                restricao_nao_atendida=dominante,
                causa=causa,
                encaminhamento=ENCAMINHAMENTOS.get(
                    dominante, "rever as restrições da equipe"
                ),
            )
        )

    return alertas


def _metricas(
    atribuicao: dict[int, int], cenario: Cenario, indice: IndiceRestricoes
) -> Metricas:
    salas = {s.id: s for s in cenario.salas}
    equipes = {e.id: e for e in cenario.equipes}

    salas_ocupadas = set(atribuicao.values())
    capacidade_usada = sum(salas[s].capacidade for s in salas_ocupadas)
    pessoas = sum(equipes[e].quantidade_funcionarios for e in atribuicao)
    ocupacao = pessoas / capacidade_usada if capacidade_usada else 0.0

    return Metricas(
        equipes_alocadas=len(atribuicao),
        equipes_sem_sala=len(cenario.equipes) - len(atribuicao),
        salas_ocupadas=len(salas_ocupadas),
        ocupacao_media=_percentual(ocupacao),
        ocupacao_media_percentual=round(ocupacao * 100, 1),
        assentos_ociosos=capacidade_usada - pessoas,
        violacoes=len(avaliar_acoplamento(atribuicao, cenario, indice)),
    )


def atribuicao_atual(cenario: Cenario) -> dict[int, int]:
    """Arranjo vigente antes da otimização, lido de `sala_atual_id`.

    É o lado "antes" da tela de comparação e a base dos indicadores do
    dashboard. Salas inexistentes são ignoradas.
    """
    validas = {s.id for s in cenario.salas}
    return {
        e.id: e.sala_atual_id
        for e in cenario.equipes
        if e.sala_atual_id is not None and e.sala_atual_id in validas
    }


def _fixacoes_validas(
    fixacoes: dict[int, int] | None, cenario: Cenario
) -> dict[int, int]:
    """Descarta fixações que apontam para equipe ou sala inexistente.

    Uma fixação pode ter sido gravada numa execução anterior e a entidade
    removida do cadastro depois. Ignorar em silêncio é melhor que estourar:
    a re-otimização segue, apenas sem aquela restrição humana.

    Se duas equipes forem fixadas na mesma sala, vence a de menor id — a
    ocupação exclusiva é inegociável.
    """
    if not fixacoes:
        return {}

    equipes = {e.id: e for e in cenario.equipes}
    salas = {s.id: s for s in cenario.salas}

    resultado: dict[int, int] = {}
    salas_usadas: set[int] = set()

    for equipe_id, sala_id in sorted(fixacoes.items()):
        if equipe_id not in equipes or sala_id not in salas:
            continue
        if sala_id in salas_usadas:
            continue
        # A regra dura de capacidade vale mesmo para decisão humana.
        if salas[sala_id].capacidade < equipes[equipe_id].quantidade_funcionarios:
            continue
        resultado[equipe_id] = sala_id
        salas_usadas.add(sala_id)

    return resultado


def _recursos_atendidos(
    equipe: EquipeEntrada, sala: SalaEntrada, indice: IndiceRestricoes
) -> bool:
    exigidos = set(equipe.requisitos_especiais)
    for r in indice.da_equipe(equipe.id, "equipamento_obrigatorio"):
        exigidos.update(r.parametro.get("recursos", []))
    return exigidos.issubset(set(sala.recursos))


def _andar_atendido(
    equipe: EquipeEntrada, sala: SalaEntrada, indice: IndiceRestricoes
) -> bool:
    for r in indice.da_equipe(equipe.id, "andar_permitido"):
        if sala.andar not in r.parametro.get("andares", []):
            return False
    if equipe.preferencia_andar is not None:
        return sala.andar == equipe.preferencia_andar
    return True


def _percentual(fracao: float) -> str:
    return f"{round(fracao * 100)}%"
