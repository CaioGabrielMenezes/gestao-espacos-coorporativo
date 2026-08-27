"""Dados de teste do cadastro.

Uso:
    python -m app.seed            # popula se o banco estiver vazio
    python -m app.seed --reset    # apaga tudo e repopula

Atende ao critério de aceite da spec (9 andares, >= 15 salas, >= 10 equipes) e
prepara de propósito o cenário de exceção que o motor precisa demonstrar:
a maior sala do prédio comporta 80 pessoas e a equipe "Operações Delta" tem 92,
ou seja, ela não cabe em lugar nenhum e deve virar um ALERTA, nunca uma
alocação forçada (ver specs/motor-alocacao.md).
"""

import argparse

from sqlalchemy import select

from app.database import Base, SessionLocal, criar_tabelas, engine
from app.enums import Prioridade, TipoRestricao, TipoSala
from app.models import Equipe, Restricao, Sala, Setor

PADRAO_COMERCIAL = {
    "dias": ["seg", "ter", "qua", "qui", "sex"],
    "horario_inicio": "08:00",
    "horario_fim": "18:00",
}
MEIO_PERIODO = {
    "dias": ["seg", "ter", "qua", "qui", "sex"],
    "horario_inicio": "08:00",
    "horario_fim": "12:00",
}

# (identificacao, andar, capacidade, tipo, recursos, acessibilidade, disponibilidade)
SALAS = [
    ("Sala 101", 1, 80, TipoSala.auditorio, ["projetor", "som", "palco"], True, PADRAO_COMERCIAL),
    ("Sala 102", 1, 12, TipoSala.reuniao, ["tv", "wifi"], True, PADRAO_COMERCIAL),
    ("Sala 201", 2, 40, TipoSala.treinamento, ["projetor", "quadro"], False, PADRAO_COMERCIAL),
    ("Sala 202", 2, 24, TipoSala.colaborativo, ["wifi", "quadro"], False, PADRAO_COMERCIAL),
    ("Sala 301", 3, 30, TipoSala.laboratorio, ["bancada", "rede_isolada", "wifi"], False, PADRAO_COMERCIAL),
    ("Sala 302", 3, 8, TipoSala.reuniao, ["tv"], False, MEIO_PERIODO),
    ("Sala 401", 4, 45, TipoSala.projeto, ["quadro", "wifi"], False, PADRAO_COMERCIAL),
    ("Sala 402", 4, 6, TipoSala.reuniao, ["tv"], False, PADRAO_COMERCIAL),
    ("Sala 501", 5, 60, TipoSala.colaborativo, ["wifi", "quadro", "projetor"], True, PADRAO_COMERCIAL),
    ("Sala 502", 5, 35, TipoSala.treinamento, ["projetor"], False, PADRAO_COMERCIAL),
    # 601 e 602 são o segundo polo de laboratório do prédio: sem elas, a Sala
    # 301 seria a única com `rede_isolada` e três equipes disputariam uma vaga
    # só, gerando alertas que dizem mais sobre o fixture do que sobre o motor.
    ("Sala 601", 6, 24, TipoSala.laboratorio, ["bancada", "wifi", "rede_isolada"], False, PADRAO_COMERCIAL),
    ("Sala 602", 6, 50, TipoSala.projeto, ["quadro", "bancada"], False, PADRAO_COMERCIAL),
    ("Sala 701", 7, 50, TipoSala.projeto, ["projetor", "wifi", "quadro"], True, PADRAO_COMERCIAL),
    ("Sala 702", 7, 16, TipoSala.reuniao, ["tv", "wifi"], False, PADRAO_COMERCIAL),
    ("Sala 801", 8, 45, TipoSala.treinamento, ["projetor", "quadro"], False, PADRAO_COMERCIAL),
    ("Sala 802", 8, 28, TipoSala.colaborativo, ["wifi"], True, MEIO_PERIODO),
    ("Sala 901", 9, 70, TipoSala.auditorio, ["projetor", "som"], True, PADRAO_COMERCIAL),
    ("Sala 902", 9, 40, TipoSala.projeto, ["wifi", "quadro"], False, PADRAO_COMERCIAL),
]

# (nome, coordenador, total_funcionarios)
SETORES = [
    ("Tecnologia", "Ana Ribeiro", 180),
    ("Operações", "Bruno Tavares", 210),
    ("Comercial", "Carla Menezes", 95),
    ("Pesquisa", "Diego Alves", 60),
]

# A última coluna é a sala que a equipe ocupa HOJE — o lado "antes" da tela de
# comparação. O arranjo é deliberadamente ruim: ocupação média perto de 60%,
# equipes do mesmo setor espalhadas por andares distantes e os dois squads de
# desenvolvimento longe do andar 7 que ambos preferem. É esse desperdício que
# a otimização precisa mostrar que elimina.
#
# (setor, nome, qtd, horario, requisitos, pref_andar, acessibilidade, prioridade, sala_atual)
EQUIPES = [
    ("Tecnologia", "Desenvolvimento A", 42, "08:00-18:00", ["projetor", "wifi"], 7, False, Prioridade.alta, "Sala 901"),
    ("Tecnologia", "Desenvolvimento B", 38, "08:00-18:00", ["wifi", "quadro"], 7, False, Prioridade.media, "Sala 501"),
    ("Tecnologia", "Infraestrutura", 14, "08:00-18:00", ["rede_isolada"], None, False, Prioridade.media, "Sala 301"),
    ("Tecnologia", "QA", 9, "08:00-12:00", ["tv"], None, False, Prioridade.baixa, "Sala 201"),
    # Sem sala hoje: não existe sala no prédio que comporte 92 pessoas.
    ("Operações", "Operações Delta", 92, "08:00-18:00", [], None, False, Prioridade.critica, None),
    ("Operações", "Suporte N1", 55, "08:00-18:00", ["wifi"], None, False, Prioridade.alta, "Sala 101"),
    ("Operações", "Logística", 26, "08:00-18:00", [], None, True, Prioridade.media, "Sala 802"),
    ("Comercial", "Vendas Corporativas", 48, "08:00-18:00", ["projetor"], None, False, Prioridade.alta, "Sala 602"),
    ("Comercial", "Pré-vendas", 18, "08:00-18:00", [], None, False, Prioridade.media, "Sala 401"),
    ("Comercial", "Marketing", 12, "08:00-18:00", ["tv", "wifi"], None, False, Prioridade.baixa, "Sala 702"),
    ("Pesquisa", "Pesquisa Aplicada", 22, "08:00-18:00", ["bancada"], 3, False, Prioridade.alta, "Sala 502"),
    ("Pesquisa", "Data Lab", 4, "08:00-12:00", ["bancada", "rede_isolada"], None, False, Prioridade.media, "Sala 601"),
]


def _tem_dados(db) -> bool:
    return db.scalar(select(Sala).limit(1)) is not None


def povoar(reset: bool = False) -> dict[str, int]:
    if reset:
        Base.metadata.drop_all(bind=engine)
    criar_tabelas()

    db = SessionLocal()
    try:
        if _tem_dados(db):
            print("Banco já contém dados — nada a fazer. Use --reset para recriar.")
            return _contagens(db)

        salas = {}
        for ident, andar, cap, tipo, recursos, acess, disp in SALAS:
            sala = Sala(
                identificacao=ident,
                andar=andar,
                capacidade=cap,
                tipo=tipo,
                recursos=recursos,
                acessibilidade=acess,
                disponibilidade=disp,
            )
            db.add(sala)
            salas[ident] = sala

        setores = {}
        for nome, coordenador, total in SETORES:
            setor = Setor(nome=nome, coordenador=coordenador, total_funcionarios=total)
            db.add(setor)
            setores[nome] = setor

        equipes = {}
        for setor_nome, nome, qtd, horario, reqs, pref, acess, prio, sala_atual in EQUIPES:
            equipe = Equipe(
                setor=setores[setor_nome],
                nome=nome,
                quantidade_funcionarios=qtd,
                horario_necessario=horario,
                requisitos_especiais=reqs,
                preferencia_andar=pref,
                necessita_acessibilidade=acess,
                proximidade_desejada=[],
                prioridade=prio,
                sala_atual=salas[sala_atual] if sala_atual else None,
            )
            db.add(equipe)
            equipes[nome] = equipe

        # flush para que salas/setores/equipes ganhem id antes das restrições,
        # que precisam referenciá-los.
        db.flush()

        equipes["Desenvolvimento A"].proximidade_desejada = [
            equipes["Desenvolvimento B"].id
        ]

        sala_901 = db.scalar(select(Sala).where(Sala.identificacao == "Sala 901"))

        # Uma restrição de cada tipo, para o motor ter variedade real de entrada.
        restricoes = [
            Restricao(
                tipo=TipoRestricao.capacidade_minima,
                equipe_id=equipes["Desenvolvimento A"].id,
                parametro={"valor": 42},
                descricao="Equipe não pode ser dividida entre salas.",
            ),
            Restricao(
                tipo=TipoRestricao.andar_permitido,
                equipe_id=equipes["Pesquisa Aplicada"].id,
                parametro={"andares": [3, 6]},
                descricao="Precisa ficar nos andares com laboratório.",
            ),
            Restricao(
                tipo=TipoRestricao.acessibilidade_obrigatoria,
                equipe_id=equipes["Logística"].id,
                parametro={},
                descricao="Integrante com mobilidade reduzida.",
            ),
            Restricao(
                tipo=TipoRestricao.equipamento_obrigatorio,
                equipe_id=equipes["Data Lab"].id,
                parametro={"recursos": ["bancada", "rede_isolada"]},
                descricao="Trabalha com dados sensíveis em rede isolada.",
            ),
            Restricao(
                tipo=TipoRestricao.proximidade_obrigatoria,
                equipe_id=equipes["Desenvolvimento A"].id,
                parametro={"equipe_ids": [equipes["Desenvolvimento B"].id]},
                descricao="Squads que fazem cerimônias juntas.",
            ),
            Restricao(
                tipo=TipoRestricao.setores_nao_compartilham,
                setor_id=setores["Pesquisa"].id,
                parametro={"setor_ids": [setores["Comercial"].id]},
                descricao="Confidencialidade de projetos em pesquisa.",
            ),
            Restricao(
                tipo=TipoRestricao.sala_reservada_setor,
                sala_id=sala_901.id,
                parametro={"setor_id": setores["Operações"].id},
                descricao="Auditório reservado para Operações.",
            ),
            Restricao(
                tipo=TipoRestricao.prioridade_equipe,
                equipe_id=equipes["Operações Delta"].id,
                parametro={"nivel": 1},
                descricao="Equipe crítica: resolver primeiro.",
            ),
        ]
        db.add_all(restricoes)
        db.commit()
        return _contagens(db)
    finally:
        db.close()


def _contagens(db) -> dict[str, int]:
    return {
        "salas": len(db.scalars(select(Sala)).all()),
        "setores": len(db.scalars(select(Setor)).all()),
        "equipes": len(db.scalars(select(Equipe)).all()),
        "restricoes": len(db.scalars(select(Restricao)).all()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Popula o banco com dados de teste.")
    parser.add_argument(
        "--reset", action="store_true", help="Apaga as tabelas antes de popular."
    )
    args = parser.parse_args()

    contagens = povoar(reset=args.reset)
    print("Seed concluído:")
    for entidade, total in contagens.items():
        print(f"  {entidade:12} {total}")


if __name__ == "__main__":
    main()
