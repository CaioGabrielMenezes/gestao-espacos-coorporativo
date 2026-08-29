"""Critérios de aceitação do sistema (seção 14 do enunciado).

Cada teste deste arquivo É um critério de aceitação. A lista vive aqui, e não
num documento à parte, por um motivo: critério escrito em prosa é promessa;
critério executável é evidência. Rodar

    pytest tests/test_criterios_aceitacao.py -v

imprime a lista inteira com o veredito de cada um, e serve como comprovação
direta na demonstração.

Os limiares são objetivos e estão declarados como constantes — nada de
"deve ser rápido" ou "deve ser bom".
"""

from time import perf_counter

import pytest

from engine import Cenario, EquipeEntrada, SalaEntrada, otimizar
from engine.restricoes import IndiceRestricoes, avaliar_veto

# Limiares definidos pela equipe -------------------------------------------
TETO_DEMONSTRACAO_S = 1.0  # dataset de demonstração (18 salas, 12 equipes)
TETO_GRANDE_PORTE_S = 5.0  # 120 salas, 100 equipes
MINIMO_EXPLICABILIDADE = 1.0  # 100% das recomendações
MINIMO_RASTREABILIDADE = 1.0  # 100% das equipes sem sala


@pytest.fixture()
def resultado(client_com_seed):
    resposta = client_com_seed.post("/api/alocacoes/otimizar", json={})
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


# --------------------------------------------------------------------------
# CA-01
# --------------------------------------------------------------------------
def test_ca01_nenhuma_sala_recebe_mais_pessoas_que_a_capacidade(resultado):
    """CA-01 — Nenhuma sala pode receber mais pessoas do que sua capacidade.

    Limiar: zero ocorrências. É a única regra do sistema que não admite
    exceção, nem sequer por intervenção manual do coordenador.
    """
    excedidas = [
        r for r in resultado["recomendacoes"] if r["pessoas"] > r["capacidade"]
    ]
    assert not excedidas, f"salas com excesso de pessoas: {excedidas}"


# --------------------------------------------------------------------------
# CA-02
# --------------------------------------------------------------------------
def test_ca02_nenhuma_restricao_dura_e_ignorada(client_com_seed, resultado):
    """CA-02 — Nenhuma restrição obrigatória (dura) pode ser violada.

    Limiar: zero violações. Verificado reavaliando cada recomendação já pronta
    contra o avaliador de restrições, de forma independente do caminho que o
    motor percorreu para chegar nela.

    Limitação conhecida, verificada por mutação: esta checagem usa a MESMA
    função `avaliar_veto` que o motor usa, então ela pega defeito no *uso* das
    restrições (o emparelhamento ignorar o filtro, a busca local roubar uma
    sala) mas não pega defeito *dentro* do próprio avaliador. Essa outra classe
    de defeito é coberta pelo CA-01, que compara números crus vindos da API sem
    passar por `avaliar_veto`, e pelos testes metamórficos.
    """
    from app.database import SessionLocal
    from app.routers.alocacoes import montar_cenario

    db = SessionLocal()
    try:
        cenario = montar_cenario(db)
    finally:
        db.close()

    indice = IndiceRestricoes(cenario.restricoes)
    salas = {s.id: s for s in cenario.salas}
    equipes = {e.id: e for e in cenario.equipes}

    violacoes = []
    for r in resultado["recomendacoes"]:
        veto = avaliar_veto(equipes[r["equipe_id"]], salas[r["sala_id"]], indice)
        if veto is not None:
            violacoes.append(f"{r['equipe']} em {r['sala_sugerida']}: {veto.detalhe}")

    assert not violacoes, "restrições duras violadas: " + "; ".join(violacoes)


# --------------------------------------------------------------------------
# CA-03
# --------------------------------------------------------------------------
def test_ca03_toda_recomendacao_tem_justificativa(resultado):
    """CA-03 — 100% das recomendações apresentam justificativa completa.

    Limiar: 100%. Uma recomendação sem justificativa é indistinguível de um
    palpite, e o sistema existe justamente para não produzir palpites.
    """
    recomendacoes = resultado["recomendacoes"]
    assert recomendacoes, "a execução de demonstração deveria produzir recomendações"

    completas = [
        r
        for r in recomendacoes
        if r["explicabilidade"]["justificativa"].strip()
        and r["explicabilidade"]["alternativas_avaliadas"] >= 1
        and r["explicabilidade"]["ocupacao_prevista"]
    ]
    taxa = len(completas) / len(recomendacoes)
    assert taxa >= MINIMO_EXPLICABILIDADE, (
        f"apenas {taxa:.0%} das recomendações têm explicabilidade completa"
    )


# --------------------------------------------------------------------------
# CA-04
# --------------------------------------------------------------------------
def test_ca04_toda_equipe_sem_sala_tem_motivo_registrado(resultado):
    """CA-04 — 100% das equipes não alocadas têm causa e encaminhamento.

    Limiar: 100%. Nenhuma equipe pode simplesmente desaparecer do resultado —
    esconder o problema é pior do que não resolvê-lo.
    """
    nao_alocadas = resultado["governanca"]["equipes_nao_alocadas"]
    alertas = resultado["alertas"]

    assert len(alertas) == nao_alocadas, (
        f"{nao_alocadas} equipes sem sala, mas {len(alertas)} alertas emitidos"
    )

    completos = [
        a
        for a in alertas
        if a["equipe_afetada"] and a["restricao_nao_atendida"] and a["causa"] and a["encaminhamento"]
    ]
    if alertas:
        taxa = len(completos) / len(alertas)
        assert taxa >= MINIMO_RASTREABILIDADE, (
            f"apenas {taxa:.0%} dos alertas estão completos"
        )


# --------------------------------------------------------------------------
# CA-05
# --------------------------------------------------------------------------
def test_ca05_otimizacao_reduz_ociosidade_sem_perder_equipes(resultado):
    """CA-05 — A proposta reduz a ociosidade e não aloca menos equipes que a
    situação inicial.

    Limiar: assentos ociosos estritamente menores E equipes alocadas maiores ou
    iguais. Reduzir ociosidade deixando equipes de fora não seria melhora.
    """
    antes = resultado["comparativo"]["antes"]
    depois = resultado["comparativo"]["depois"]

    assert depois["assentos_ociosos"] < antes["assentos_ociosos"], (
        f"ociosidade não caiu: {antes['assentos_ociosos']} → "
        f"{depois['assentos_ociosos']}"
    )
    assert depois["equipes_alocadas"] >= antes["equipes_alocadas"], (
        f"a otimização alocou menos equipes que o arranjo inicial: "
        f"{antes['equipes_alocadas']} → {depois['equipes_alocadas']}"
    )


# --------------------------------------------------------------------------
# CA-06
# --------------------------------------------------------------------------
def test_ca06_tempo_de_resposta_da_demonstracao(client_com_seed):
    """CA-06a — A otimização do dataset de demonstração responde em < 1s."""
    inicio = perf_counter()
    resposta = client_com_seed.post("/api/alocacoes/otimizar", json={})
    decorrido = perf_counter() - inicio

    assert resposta.status_code == 200
    assert decorrido < TETO_DEMONSTRACAO_S, (
        f"a otimização levou {decorrido:.2f}s, acima do teto de "
        f"{TETO_DEMONSTRACAO_S}s definido para a demonstração"
    )


def test_ca06_tempo_de_resposta_em_grande_porte():
    """CA-06b — Um prédio muito maior que o do enunciado responde em < 5s.

    100 equipes e 120 salas está bem acima das 12 equipes e 18 salas da
    demonstração: o critério é sobre escalabilidade, não sobre o caso feliz.
    """
    salas = tuple(
        SalaEntrada(
            id=i + 1,
            identificacao=f"Sala {i + 1}",
            andar=(i % 9) + 1,
            capacidade=10 + (i % 12) * 8,
            recursos=frozenset({"wifi"}),
        )
        for i in range(120)
    )
    equipes = tuple(
        EquipeEntrada(
            id=i + 1,
            nome=f"Equipe {i + 1}",
            setor_id=(i % 8) + 1,
            quantidade_funcionarios=5 + (i % 20) * 4,
            requisitos_especiais=frozenset({"wifi"}),
        )
        for i in range(100)
    )

    inicio = perf_counter()
    otimizar(Cenario(salas=salas, equipes=equipes, restricoes=()))
    decorrido = perf_counter() - inicio

    assert decorrido < TETO_GRANDE_PORTE_S, (
        f"a otimização de grande porte levou {decorrido:.2f}s, acima do teto de "
        f"{TETO_GRANDE_PORTE_S}s"
    )


# --------------------------------------------------------------------------
# CA-07
# --------------------------------------------------------------------------
def test_ca07_toda_execucao_deixa_registro_de_governanca(client_com_seed):
    """CA-07 — Toda execução gera registro persistido, com os campos que
    permitem responder quem, quando, com quais dados e com que resultado.

    Limiar: registro presente e com todos os campos preenchidos.
    """
    client_com_seed.post("/api/alocacoes/otimizar", json={"usuario": "avaliador"})
    execucoes = client_com_seed.get("/api/alocacoes/execucoes").json()

    assert execucoes, "a execução não deixou registro"
    registro = execucoes[0]

    obrigatorios = [
        "execucao_id",
        "timestamp",
        "usuario",
        "algoritmo",
        "equipes_analisadas",
        "salas_analisadas",
        "equipes_alocadas",
        "equipes_nao_alocadas",
        "restricoes_violadas",
        "ocupacao_prevista",
        "duracao_ms",
    ]
    faltando = [c for c in obrigatorios if registro.get(c) in (None, "")]
    assert not faltando, f"campos ausentes no registro de governança: {faltando}"
    assert registro["usuario"] == "avaliador"


# --------------------------------------------------------------------------
# CA-08
# --------------------------------------------------------------------------
def test_ca08_mesma_entrada_produz_mesmo_resultado(client_com_seed):
    """CA-08 — A mesma entrada produz sempre a mesma recomendação.

    Limiar: alocações idênticas. Um sistema que recomenda coisas diferentes
    para a mesma entrada não é auditável, e a explicabilidade perderia o
    sentido — não daria para reproduzir a decisão que foi justificada.
    """
    def alocacoes():
        corpo = client_com_seed.post("/api/alocacoes/otimizar", json={}).json()
        return sorted((r["equipe_id"], r["sala_id"]) for r in corpo["recomendacoes"])

    primeira, segunda = alocacoes(), alocacoes()
    assert primeira == segunda, (
        "duas execuções da mesma entrada produziram alocações diferentes"
    )
