"""Infraestrutura dos testes metamórficos (specs/testes-motor.md).

Por que testes metamórficos: não existe "resposta certa" conhecida para uma
alocação ótima de 9 andares, então não dá para comparar a saída do motor com
um gabarito. O que dá para afirmar são *relações* entre execuções — se eu
acrescento uma sala, o resultado não pode piorar. É isso que se testa aqui.

Cada propriedade é verificada sobre dezenas de cenários gerados com semente
fixa: determinístico o bastante para o CI, variado o bastante para não ser um
único caso escolhido a dedo. O motor não depende de banco, então a suíte
inteira roda em milissegundos.
"""

import random

from engine.modelos import Cenario, EquipeEntrada, RestricaoEntrada, SalaEntrada

RECURSOS = ("projetor", "wifi", "quadro", "tv", "bancada", "rede_isolada", "som")
PRIORIDADES = ("baixa", "media", "alta", "critica")
TIPOS_SALA = ("reuniao", "treinamento", "auditorio", "laboratorio", "projeto")

SEMENTE_PADRAO = 42
QUANTIDADE_PADRAO = 30


def gerar_cenario(rnd: random.Random, indice: int) -> Cenario:
    """Um cenário sintético plausível: salas, equipes e restrições variadas."""
    n_salas = rnd.randint(4, 14)
    n_equipes = rnd.randint(4, 14)

    salas = tuple(
        SalaEntrada(
            id=i + 1,
            identificacao=f"S{indice}-{i + 1}",
            andar=rnd.randint(1, 9),
            capacidade=rnd.randint(5, 60),
            tipo=rnd.choice(TIPOS_SALA),
            recursos=frozenset(rnd.sample(RECURSOS, rnd.randint(0, 3))),
            acessibilidade=rnd.random() < 0.4,
        )
        for i in range(n_salas)
    )

    equipes = tuple(
        EquipeEntrada(
            id=i + 1,
            nome=f"Equipe {i + 1}",
            setor_id=rnd.randint(1, 3),
            quantidade_funcionarios=rnd.randint(3, 55),
            requisitos_especiais=frozenset(rnd.sample(RECURSOS, rnd.randint(0, 2))),
            preferencia_andar=rnd.choice([None, rnd.randint(1, 9)]),
            necessita_acessibilidade=rnd.random() < 0.25,
            proximidade_desejada=(),
            prioridade=rnd.choice(PRIORIDADES),
            sala_atual_id=rnd.choice([None, rnd.randint(1, n_salas)]),
        )
        for i in range(n_equipes)
    )

    restricoes = _gerar_restricoes(rnd, salas, equipes)
    return Cenario(salas=salas, equipes=equipes, restricoes=restricoes)


def _gerar_restricoes(
    rnd: random.Random,
    salas: tuple[SalaEntrada, ...],
    equipes: tuple[EquipeEntrada, ...],
) -> tuple[RestricaoEntrada, ...]:
    restricoes: list[RestricaoEntrada] = []
    proximo_id = 1

    for _ in range(rnd.randint(0, 5)):
        tipo = rnd.choice(
            [
                "capacidade_minima",
                "andar_permitido",
                "acessibilidade_obrigatoria",
                "equipamento_obrigatorio",
                "sala_reservada_setor",
                "setores_nao_compartilham",
            ]
        )

        if tipo == "sala_reservada_setor":
            restricao = RestricaoEntrada(
                id=proximo_id,
                tipo=tipo,
                sala_id=rnd.choice(salas).id,
                parametro={"setor_id": rnd.randint(1, 3)},
            )
        elif tipo == "setores_nao_compartilham":
            restricao = RestricaoEntrada(
                id=proximo_id,
                tipo=tipo,
                setor_id=1,
                parametro={"setor_ids": [2]},
            )
        else:
            parametros = {
                "capacidade_minima": {"valor": rnd.randint(5, 40)},
                "andar_permitido": {"andares": rnd.sample(range(1, 10), rnd.randint(1, 4))},
                "acessibilidade_obrigatoria": {},
                "equipamento_obrigatorio": {"recursos": [rnd.choice(RECURSOS)]},
            }
            restricao = RestricaoEntrada(
                id=proximo_id,
                tipo=tipo,
                equipe_id=rnd.choice(equipes).id,
                parametro=parametros[tipo],
            )

        restricoes.append(restricao)
        proximo_id += 1

    return tuple(restricoes)


def cenarios(
    quantidade: int = QUANTIDADE_PADRAO, semente: int = SEMENTE_PADRAO
) -> list[Cenario]:
    """Lote determinístico de cenários — mesma semente, mesmos cenários."""
    rnd = random.Random(semente)
    return [gerar_cenario(rnd, i) for i in range(quantidade)]


def descrever(cenario: Cenario) -> str:
    """Resumo legível do cenário, para a mensagem de falha apontar o caso."""
    salas = ", ".join(
        f"{s.identificacao}(cap={s.capacidade},andar={s.andar})" for s in cenario.salas
    )
    equipes = ", ".join(
        f"{e.nome}({e.quantidade_funcionarios}p,{e.prioridade})" for e in cenario.equipes
    )
    restricoes = ", ".join(f"{r.tipo}={r.parametro}" for r in cenario.restricoes) or "nenhuma"
    return (
        f"\n  SALAS      : {salas}"
        f"\n  EQUIPES    : {equipes}"
        f"\n  RESTRIÇÕES : {restricoes}"
    )
