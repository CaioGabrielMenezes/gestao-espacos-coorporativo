# Sistema Inteligente de Gestão e Otimização de Espaços Corporativos

Protótipo full stack que recebe salas de um prédio de 9 andares, setores,
equipes e restrições, e recomenda automaticamente a melhor distribuição de
espaços — com justificativa para cada decisão, tratamento explícito dos casos
sem solução e registro de auditoria de toda execução.

Trabalho da disciplina de **Qualidade e Testes de Sistemas Baseados em IA**
(ISTQB CT-AI).

| | |
|---|---|
| **Backend** | Python 3.14 · FastAPI · SQLAlchemy · SQLite |
| **Frontend** | React 19 · Vite · React Router |
| **Testes** | 489 no backend (pytest) · 46 de componente (Vitest) · 12 end-to-end (Playwright) |
| **API** | 34 endpoints, documentados em `/docs` |

---

## Como rodar

Precisa de **Python 3.12+** e **Node 20+**.

### Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Linux/macOS: .venv/bin/python
.venv/Scripts/python -m app.seed --reset
.venv/Scripts/python -m uvicorn app.main:app --reload
```

API em <http://127.0.0.1:8000> · documentação interativa em **`/docs`**.

### Frontend

Em outro terminal, com o backend rodando:

```bash
cd frontend
npm install
npm run dev
```

Abre em <http://localhost:5173>.

### Testes

```bash
# backend — inclui os testes metamórficos
cd backend && .venv/Scripts/python -m pytest

# só os metamórficos
.venv/Scripts/python -m pytest tests/metamorphic -v

# frontend — componentes e telas
cd frontend && npm test

# end-to-end — sobe backend e frontend sozinho, com banco descartável
npm run e2e
```

---

## Arquitetura

```
frontend (React)  →  backend (FastAPI)  →  engine (módulo Python puro)
                                        ↘  SQLite (backend/espacos.db)
```

O motor de alocação vive em `backend/engine/` e é **puro**: recebe dataclasses,
devolve modelos Pydantic e não importa SQLAlchemy nem FastAPI. Quem traduz o
ORM para a entrada do motor é `app/routers/alocacoes.py`.

Essa fronteira não é enfeite. É ela que permite aos testes metamórficos rodarem
sobre centenas de cenários sintéticos **sem subir banco**, em menos de um
segundo — condição prática para que sejam úteis num pipeline de CI.

---

## O motor de alocação

### Algoritmo

**Emparelhamento máximo bipartido (algoritmo de Kuhn), seguido de busca local.**

1. As restrições duras filtram as arestas do grafo equipe × sala.
2. O emparelhamento máximo encontra a maior quantidade possível de equipes
   alocadas.
3. A busca local melhora a qualidade da distribuição, com uma invariante
   explícita: **nunca reduz o número de equipes alocadas**.

### O que ele garante — e o que não garante

O motor é **ótimo no número de equipes alocadas** e **heurístico na qualidade
da distribuição**. Essa distinção é deliberada e está declarada no código.

A escolha do algoritmo não foi estética. Duas das propriedades verificadas pelos
testes metamórficos valem **por construção** com emparelhamento máximo:

- acrescentar uma sala acrescenta um vértice ao grafo, e o emparelhamento
  máximo nunca diminui ao se acrescentar vértice;
- remover uma restrição dura apenas acrescenta arestas, e o emparelhamento
  máximo nunca diminui ao se acrescentar aresta.

Uma heurística gulosa não teria essa garantia — e o teste de mutação descrito
mais abaixo demonstra isso na prática.

### Duas classes de restrição

| Classe | Comportamento | Tipos |
|---|---|---|
| **Duras** | Filtram arestas. **Nunca** são violadas. | capacidade, capacidade mínima, andar permitido, acessibilidade, equipamento, sala reservada a setor, **janela de horário** |
| **De acoplamento** | Dependem de onde as *outras* equipes ficaram. Entram como penalidade na busca local; violações remanescentes são contadas na governança. | setores que não compartilham área, proximidade obrigatória |

Um emparelhamento bipartido não consegue expressar restrições de acoplamento
como filtro de aresta — daí a separação. O campo `restricoes_violadas` do
registro de governança existe exatamente para tornar isso visível em vez de
escondê-lo.

**Conflito de horário** entra como restrição dura: a janela de disponibilidade
da sala precisa cobrir a faixa que a equipe exige. Uma sala que fecha ao
meio-dia não abriga uma equipe de período integral — não é questão de
preferência. Nos dados de exemplo isso é visível: a equipe de Logística não
pode ocupar a Sala 802, que só abre até as 12h.

Os *dias* da semana são cadastrados na sala mas não restringem a alocação,
porque as equipes declaram apenas faixa de horário, não dias — não haveria com
o que comparar.

### Explicabilidade

Toda recomendação carrega uma estrutura de explicação, nunca apenas
"Equipe X → Sala Y":

```json
{
  "sala": "Sala 701",
  "equipe": "Desenvolvimento A",
  "capacidade_sala": 50,
  "tamanho_equipe": 42,
  "ocupacao_prevista": "84%",
  "recursos_atendidos": true,
  "restricao_andar_atendida": true,
  "alternativas_avaliadas": 2,
  "justificativa": "Melhor equilíbrio entre capacidade, localização e restrições dentre as 2 alternativas avaliadas: 84% de ocupação, contra 70% da segunda melhor opção (Sala 501).",
  "score": 70.4,
  "criterios": { "ocupacao": 50.4, "preferencia_andar": 20.0, "permanencia": 0.0 }
}
```

A justificativa é gerada comparando com a **segunda melhor alternativa real**.
Quando a sala individualmente melhor foi para outra equipe, o texto diz isso e
explica que ceder a sala foi o que permitiu acomodar a outra — a decisão global
fica auditável, não só a local.

Na interface, a explicação está a **um clique** da lista de recomendações.

### Tratamento de exceção

Nenhuma equipe some do resultado. Quando não há sala compatível, o motor emite
um alerta em vez de forçar uma alocação inválida:

```json
{
  "status": "ALERTA",
  "equipe_afetada": "Operações Delta",
  "restricao_nao_atendida": "capacidade mínima",
  "causa": "Maior sala disponível comporta 80 pessoas; equipe tem 92",
  "encaminhamento": "dividir equipe em dois grupos ou liberar sala adicional"
}
```

Os alertas distinguem dois casos que a especificação tratava como um só:
**não existe sala compatível** (restrição insatisfazível) e **existiam salas
compatíveis, mas todas foram ocupadas** por equipes sem outra opção. O
encaminhamento sugerido é diferente em cada caso.

### Governança e intervenção humana

Toda execução grava um registro persistido: quem disparou, quando, qual
algoritmo, quantas salas e equipes foram analisadas, quantas foram alocadas,
restrições violadas, duração e **os pesos vigentes no momento** — para que uma
decisão antiga possa ser reinterpretada mesmo depois de a função de score ser
recalibrada. Execuções que falham também ficam registradas, com `status=falha`.

O coordenador pode aceitar, rejeitar, editar manualmente e re-otimizar. Cada
ação grava uma linha de auditoria com o de/para. A re-otimização **preserva** as
alocações aceitas e editadas.

Na edição manual, a capacidade é inegociável e devolve 422 — é impossibilidade
física, não questão de julgamento. As demais restrições duras são permitidas e
registradas como avisos: o coordenador pode saber algo que o cadastro não sabe
(o projetor chega semana que vem), e bloquear tornaria a intervenção humana
decorativa. O que não se abre mão é do registro.

---

## Critérios de aceitação

Oito critérios objetivos definem quando uma recomendação pode ser considerada
aceitável. Cada um tem limiar declarado e **um teste automatizado que o
verifica** — critério em prosa é promessa, critério executável é evidência.

```bash
cd backend && .venv/Scripts/python -m pytest tests/test_criterios_aceitacao.py -v
```

O comando acima imprime a lista com o veredito de cada critério.

| # | Critério | Limiar | Teste |
|---|---|---|---|
| **CA-01** | Nenhuma sala recebe mais pessoas que sua capacidade | zero ocorrências | `test_ca01_...` |
| **CA-02** | Nenhuma restrição obrigatória é violada | zero violações | `test_ca02_...` |
| **CA-03** | Toda recomendação apresenta justificativa completa | 100% | `test_ca03_...` |
| **CA-04** | Toda equipe sem sala tem causa e encaminhamento | 100% | `test_ca04_...` |
| **CA-05** | A proposta reduz a ociosidade sem alocar menos equipes | ociosos ↓ **e** alocadas ≥ | `test_ca05_...` |
| **CA-06** | Tempo de resposta | < 1 s na demonstração · < 5 s em 100×120 | `test_ca06_...` |
| **CA-07** | Toda execução deixa registro de governança completo | todos os campos preenchidos | `test_ca07_...` |
| **CA-08** | A mesma entrada produz a mesma recomendação | alocações idênticas | `test_ca08_...` |

Todos vivem em
[`backend/tests/test_criterios_aceitacao.py`](backend/tests/test_criterios_aceitacao.py),
um teste por critério.

Dois deles merecem justificativa. **CA-05** exige as duas condições juntas de
propósito: reduzir a ociosidade deixando equipes de fora não seria melhora,
seria maquiagem do indicador. **CA-08** parece técnico, mas é o que sustenta a
auditoria — um sistema que recomenda coisas diferentes para a mesma entrada
torna impossível reproduzir a decisão que foi justificada.

### Por que testes metamórficos

Não existe gabarito conhecido para a alocação ótima de um prédio de 9 andares.
Não dá para comparar a saída do motor com uma resposta certa, porque essa
resposta não existe de antemão.

O que dá para afirmar são **relações entre execuções**: se eu acrescento uma
sala, o resultado não pode piorar. É isso que se testa.

Cada propriedade é verificada sobre **~30 cenários sintéticos gerados com
semente fixa** — determinístico para o CI, variado o bastante para não ser um
único caso escolhido a dedo. São 392 verificações no total.

| Propriedade | Relação verificada |
|---|---|
| **Regra dura** | Nenhuma recomendação aloca mais pessoas que a capacidade da sala |
| **MR1** | Acrescentar uma sala nunca reduz o número de equipes alocadas |
| **MR2** | Remover uma restrição nunca reduz o número de equipes alocadas |
| **MR3** | Equipes idênticas exceto pelo nome não alteram a qualidade global |
| **MR4** | A mesma entrada produz sempre o mesmo resultado |

Cobrem-se também a rastreabilidade (toda equipe não alocada tem alerta), a
completude da explicabilidade e um teto de desempenho (100 equipes × 120 salas
em menos de 5s).

As mensagens de falha nomeiam a propriedade violada e imprimem o cenário — não
apenas "assert failed".

### Verificação por mutação

Testes que passam mas nunca falham não provam nada. Dois defeitos foram
injetados de propósito para confirmar que a suíte os detecta:

| Mutante | Resultado |
|---|---|
| Regra de capacidade afrouxada (`capacidade * 2`) | 29 falhas na regra dura |
| Kuhn rebaixado para algoritmo guloso | Detectado pelo **MR2** — exatamente a propriedade que se previa que um guloso violaria |
| Emparelhamento ignorando o filtro de restrições | Detectado: 7 dos 9 critérios de aceitação acusaram |
| Regra de capacidade desligada por completo | Detectado pelo **CA-01**, isoladamente (1 falha, 8 aprovações) |

O segundo é a validação empírica da escolha de algoritmo. A mensagem de falha
apontou os números concretos (7 → 6 equipes alocadas), a restrição responsável e
o cenário completo. Todos os mutantes foram revertidos.

O quarto mutante revelou uma **limitação real do CA-02**, que está documentada
no próprio teste: como ele reavalia as recomendações usando a mesma função de
restrições que o motor usa, ele detecta defeito no *uso* das restrições, mas não
detecta defeito *dentro* do avaliador. Essa classe de falha é coberta pelo
CA-01, que compara números crus da API sem passar por aquela função. Descobrir
isso foi o objetivo do exercício de mutação — e é a razão de ele não ser
opcional.

### Testes de frontend

Duas camadas com propósitos distintos:

- **Vitest + Testing Library** (43): componentes e telas com a API mockada.
  Rápidos, sem infraestrutura.
- **Playwright** (12): o fluxo real contra o backend de verdade, com SQLite
  descartável. É a única camada que pega **quebra de contrato** entre as duas
  pontas — um teste com mock segue verde enquanto a tela quebra.

### Integração contínua

`.github/workflows/ci.yml` roda a cada push e pull request: suíte do backend
(com os metamórficos destacados na saída), testes e build do frontend, e o E2E
com os dois servidores de pé.

---

## Interface

| Tela | O que mostra |
|---|---|
| **Dashboard** | Indicadores do prédio, alternando entre situação atual e proposta |
| **Mapa** | Planta dos 9 andares, salas coloridas por faixa de ocupação |
| **Recomendações** | Lista, explicabilidade a um clique e ações de intervenção |
| **Antes e depois** | Comparação direta, com os números da própria execução |
| **Monitoramento** | Saúde do motor e histórico de governança |
| **Cadastro** | CRUD de salas, setores, equipes e restrições |

Três decisões de interface que valem menção:

**Nenhum número é calculado no cliente.** Tudo vem da API, para a tela não
poder discordar do registro de governança.

**A cor nunca é o único portador de informação.** No mapa, cada sala traz o
percentual escrito, a faixa por extenso e um rótulo acessível completo — uma
tela que só comunica por cor é inútil em projetor ruim.

**O formulário de restrições se monta a partir do backend.**
`GET /api/restricoes/tipos` informa o alvo e os campos de cada um dos 8 tipos.
Nenhuma dessas regras está duplicada em JavaScript, e por isso não há como as
duas versões divergirem.

Três indicadores de ocupação são deliberadamente separados, porque respondem a
perguntas diferentes e colapsá-los num número só é o erro mais comum num painel
de ocupação:

| Indicador | Fórmula |
|---|---|
| Ocupação do prédio | pessoas ÷ capacidade de **todas** as salas |
| Utilização das salas | salas em uso ÷ total de salas |
| Aproveitamento | pessoas ÷ capacidade das salas **em uso** |

---

## Limitações conhecidas

Declaradas de propósito — a disciplina cobra transparência sobre elas.

**O motor não é ótimo na qualidade da distribuição.** É ótimo apenas no número
de equipes alocadas. A busca local é heurística e pode parar num ótimo local.

**Uma equipe por sala** (ocupação exclusiva). Como consequência,
`setores_nao_compartilham` é interpretada como "não podem ficar no mesmo andar":
no modelo exclusivo, compartilhar sala já é impossível.

**Sobre os dados de exemplo, resta 1 violação de acoplamento — e ela é
insatisfazível.** Desenvolvimento A e B têm proximidade obrigatória entre si,
mas ambos só cabem na Sala 701, no andar 7. Atender é fisicamente impossível. O
motor reporta em vez de esconder; um zero fabricado seria pior.

**A ocupação não chega a 100%.** O motor maximiza primeiro o número de equipes
alocadas e só depois a qualidade, nessa ordem, porque é o que o requisito pede.
Ele aceita conscientemente uma sala mal aproveitada se a alternativa for deixar
uma equipe sem sala.

**Equipes resistem a migrar por ganhos pequenos.** O critério de permanência
(peso 20 contra 60 da ocupação) faz uma equipe só trocar de andar se o ganho for
real — é a exigência de minimizar movimentação. Os pesos estão em
`engine/scoring.py` e são gravados em cada execução.

**Sem autenticação**, por estar fora do escopo do enunciado. O campo `usuario`
da governança é informado pelo cliente.

**Não usa Machine Learning**, por decisão registrada: o problema é de otimização
com restrições, e ML traria custo de dados, treino e avaliação sem ganho —
além de tornar a explicabilidade mais difícil, que é justamente o requisito
central.

---

## Dados de exemplo

O seed (`python -m app.seed --reset`) cria 18 salas nos 9 andares, 4 setores,
12 equipes e 8 restrições — uma de cada tipo.

Dois detalhes são intencionais:

- A equipe **Operações Delta** tem 92 pessoas e a maior sala comporta 80. É o
  insumo da demonstração de tratamento de exceção.
- O arranjo inicial das equipes é deliberadamente ruim (~60% de ocupação), para
  que o ganho da otimização seja real e mensurável na tela de comparação.

Resultado esperado: **11 das 12 equipes alocadas em ~1 ms**, 1 alerta e 1
violação de acoplamento insatisfazível.

Um caso vale observar na demonstração: Suporte N1 (55 pessoas, exige wifi) só
cabe na Sala 501, que é também a melhor opção do Desenvolvimento A. Um algoritmo
guloso por prioridade daria a 501 ao Desenvolvimento A e deixaria o Suporte N1
sem sala. O emparelhamento máximo acomoda os dois.
