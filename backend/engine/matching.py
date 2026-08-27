"""Emparelhamento máximo em grafo bipartido (algoritmo de Kuhn).

Este é o núcleo da garantia de qualidade do motor. Duas propriedades que os
testes metamórficos verificam saem daqui como consequência matemática, não
como sorte de heurística:

- acrescentar uma sala acrescenta um vértice ao lado das salas, e o
  emparelhamento máximo de um grafo nunca diminui ao se acrescentar vértice;
- remover uma restrição dura só acrescenta arestas, e o emparelhamento máximo
  nunca diminui ao se acrescentar aresta.

Complexidade O(V*E) — irrelevante na escala deste problema (centenas de salas
e equipes) e amplamente dentro do teto de 5s definido na spec.
"""


def emparelhamento_maximo(
    adjacencia: dict[int, list[int]], ordem_equipes: list[int]
) -> dict[int, int]:
    """Retorna o mapa equipe_id -> sala_id de um emparelhamento máximo.

    `adjacencia` lista, para cada equipe, as salas viáveis já ordenadas por
    qualidade decrescente: assim, entre dois emparelhamentos de mesmo tamanho,
    o algoritmo tende a devolver o de melhor score. `ordem_equipes` fixa a
    ordem de processamento e torna o resultado determinístico.
    """
    sala_ocupada_por: dict[int, int] = {}

    for equipe_id in ordem_equipes:
        # `visitadas` é por equipe-raiz: cada tentativa de aumentar o
        # emparelhamento explora cada sala no máximo uma vez.
        _buscar_caminho_aumentante(equipe_id, adjacencia, sala_ocupada_por, set())

    return {equipe: sala for sala, equipe in sala_ocupada_por.items()}


def _buscar_caminho_aumentante(
    equipe_id: int,
    adjacencia: dict[int, list[int]],
    sala_ocupada_por: dict[int, int],
    visitadas: set[int],
) -> bool:
    """Tenta alocar `equipe_id`, realocando ocupantes se necessário.

    A profundidade de recursão é limitada pelo número de equipes, muito abaixo
    do limite padrão do Python nas escalas deste sistema.
    """
    for sala_id in adjacencia.get(equipe_id, ()):
        if sala_id in visitadas:
            continue
        visitadas.add(sala_id)

        ocupante = sala_ocupada_por.get(sala_id)
        if ocupante is None or _buscar_caminho_aumentante(
            ocupante, adjacencia, sala_ocupada_por, visitadas
        ):
            sala_ocupada_por[sala_id] = equipe_id
            return True

    return False
