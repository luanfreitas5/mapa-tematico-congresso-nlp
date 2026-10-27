# Model Card — BERTopic sobre ementas e discursos da Câmara v0.1.0

**Status:** DRAFT
**Bloqueios pendentes:**
- Revisão manual sem rótulos (§8) — bloqueia afirmar que os tópicos são interpretáveis/"coerentes" para humanos.
- Sem linha de base (LDA/NMF) (§5, §8) — bloqueia afirmar que as coerências 0,739 / 0,666 são boas.
- Sem análise por fatias de tipo de proposição e ano (§8) — bloqueia uso em recortes por tipo ou período.
- Sem análise de sensibilidade a UMAP/HDBSCAN (§10) — bloqueia uso dos tópicos como medida estável entre re-execuções com outros hiperparâmetros.
- Defeito de acentuação nos termos dos tópicos (§10) — bloqueia publicação dos rótulos de tópico.

## 1. Detalhes do modelo
- **Responsável / contato:** Luan Freitas — luan.mgf@gmail.com
- **Data:** 2026-10-22 (primeira execução completa, snapshot da API)
- **Algoritmo:** BERTopic (embeddings `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` → UMAP → HDBSCAN → c-TF-IDF com stopwords em português); não supervisionado. Um modelo por corpus (ementas e discursos). Hiperparâmetros em [`configs/model_params.yaml`](../../configs/model_params.yaml): UMAP `n_neighbors=15`, `n_components=5`, `cosine`; HDBSCAN `min_cluster_size=30`, `min_samples=10`, `eom`; n-gramas (1, 2), `min_df=5`.
- **Rastreabilidade:** Git SHA `TODO(owner): SHA do commit que gerou os resultados (a execução foi feita com alterações não commitadas)` · MLflow run `N/A (o projeto não usa MLflow; os artefatos ficam em data/gold/)` · hash dos dados: SHA-256 por snapshot em `data/bronze/manifest.json` (ex.: proposições `a563e526…2961`, discursos `d74c12e2…c0cf`)
- **Licença:** MIT (código). Dados: ver [datasheet](../datasheets/camara_dados_abertos.md).
- **Semente:** 42 (`PYTHONHASHSEED` exportado pelo Makefile).

## 2. Uso pretendido
- **Uso primário:** exploração temática de textos legislativos (quais assuntos dominam as ementas e os discursos e como a frequência varia no tempo).
- **Usuários pretendidos:** pesquisadores, jornalistas de dados e analistas de políticas públicas.
- **Humano no circuito:** sim — os tópicos são hipóteses de leitura a serem validadas por um revisor humano (amostras em `reports/review/`).

## 3. Usos fora do escopo
- Classificar, rotular ou ranquear deputados e partidos a partir dos tópicos; qualquer decisão sobre pessoas.
- Tratar o tópico de um discurso como juízo de valor ou posição política do parlamentar.
- Inferência causal (centralidade e frequência de tópicos descrevem estrutura, não influência).
- Uso em outras legislaturas, casas legislativas ou idiomas: não validado.

## 4. Fatores
- **Grupos relevantes:** corpus (ementas × discursos); tipo de proposição (PT, PL, PLP, PEC, MPV); ano; partido (risco indireto). Não há atributo individual na saída.
- **Ambientes:** 57ª legislatura (2023-02 a 2025-12), texto em português do Brasil; ementas curtas e formulaicas, discursos longos (truncados em 5000 caracteres).

## 5. Métricas
- **Métrica principal:** coerência de tópicos `c_v` (e `c_npmi` como secundária), com IC 95% por bootstrap (2000 reamostragens) sobre os tópicos, excluindo o ruído (-1). Justificativa: não há rótulo de referência; a coerência é uma proxy automática de interpretabilidade, a ser complementada pela revisão manual. Custo de erro: um tópico incoerente induz leitura errada do tema; por isso a taxa de documentos no ruído também é reportada.
- **Limiar de decisão:** não se aplica (modelo não supervisionado; HDBSCAN atribui ruído conforme `min_cluster_size`).
- **Calibração:** não se aplica.
- **Linha de base:** `TODO(owner): LDA/NMF com o mesmo número de tópicos e mesmas métricas`. Sem ela, os valores abaixo não têm referência.

## 6. Dados de avaliação
Avaliação **in-sample**: a coerência é calculada sobre o próprio corpus de treino (não há conjunto separado, pois o modelo é não supervisionado). Snapshot de 2026-10-22, 17.482 ementas e 44.269 discursos após o pré-processamento. Sem validação externa.

## 7. Dados de treino
Ementas de proposições (PT, PL, PLP, PEC, MPV) e discursos da 57ª legislatura. Ver [datasheet](../datasheets/camara_dados_abertos.md).

## 8. Análise quantitativa
| Recorte | n | Tópicos | No ruído (-1) | c_v (IC 95%) | c_npmi (IC 95%) | Baseline |
|---|---|---|---|---|---|---|
| Ementas (geral) | 17.482 | 122 | 25,3% | 0,739 [0,702; 0,774] | 0,164 [0,135; 0,192] | TODO(owner): LDA/NMF |
| Discursos (geral) | 44.269 | 125 | 54,1% | 0,666 [0,639; 0,693] | 0,047 [0,022; 0,072] | TODO(owner): LDA/NMF |
| Por tipo de proposição (PT/PL/PLP/PEC/MPV) | — | — | TODO(owner) | TODO(owner) | TODO(owner) | — |
| Por ano | — | — | TODO(owner) | TODO(owner) | TODO(owner) | — |
| Revisão manual (% coerente, IC de Wilson) | — | — | — | TODO(owner): rotular `is_coherent` em `reports/review/` | — | — |

Leitura: os discursos têm mais que o dobro da proporção de documentos no ruído e coerência menor — são a fatia pior coberta. Os IC são sobre tópicos, não sobre documentos.

## 9. Considerações éticas e fairness
- **Atributos sensíveis auditados:** nenhum diretamente (não há predição por indivíduo). Risco indireto por partido.
- **Disparidades encontradas:** `TODO(owner): distribuição de tópicos por partido não auditada`. Tópicos dominados por partidos grandes ou por assuntos formulaicos podem sub-representar temas de minorias parlamentares.
- **Mitigação aplicada:** nenhuma.
- **Base legal LGPD:** dados tornados manifestamente públicos, sobre agentes públicos no exercício do mandato (LGPD, art. 7º, §§ 3º e 4º). Discursos podem citar terceiros; textos de discursos não são publicados nos relatórios, apenas tópicos agregados.

## 10. Limitações, riscos e monitoramento
- **Limitações conhecidas:**
  - Sensível a UMAP/HDBSCAN; documentos curtos geram tópicos instáveis; sensibilidade **não avaliada**.
  - Embeddings multilíngues não específicos do jargão jurídico-legislativo.
  - **Termos sem acento** (`cdigo`, `educao`, `providncias`): o vetorizador do c-TF-IDF descarta caracteres acentuados, o que pode afetar stopwords e coerência medida — defeito a corrigir.
  - 54,1% dos discursos caem no ruído; há tópicos quase duplicados (violência contra a mulher, educação, saúde).
  - Revisão manual com um único revisor (ainda sem rótulos).
- **Mudanças de distribuição previstas:** início e fim de legislatura e recessos alteram o volume mensal; data das proposições é aproximada ao mês da consulta; o modelo reflete somente 2023-02 a 2025-12.
- **Monitoramento:** não há serviço em produção. Reexecutar o pipeline a cada novo snapshot e comparar `c_v`, taxa de ruído e tamanho dos maiores tópicos com os valores desta versão.
- **Critério de retreino / descontinuação:** retreinar a cada novo snapshot ou mudança de hiperparâmetros; descontinuar esta versão quando a correção da acentuação for aplicada (as coerências mudam e não serão comparáveis).
