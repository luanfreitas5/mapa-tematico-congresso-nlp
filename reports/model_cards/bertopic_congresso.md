# Model Card — BERTopic sobre ementas e discursos

## Descrição
Pipeline de modelagem de tópicos: embeddings `paraphrase-multilingual-MiniLM-L12-v2`
(configurável) → UMAP → HDBSCAN → c-TF-IDF com stopwords em português. Não supervisionado.

## Uso pretendido
Exploração temática de textos legislativos, apoio a pesquisa e jornalismo de dados.

## Fora de escopo
Classificar ou rotular deputados/partidos, decisões sobre pessoas, inferência causal ou
qualquer uso que trate o tópico como juízo de valor sobre o parlamentar.

## Dados
Ementas de PL/PLP/PEC/MPV e discursos da 57ª legislatura (ver o datasheet em
`reports/datasheets/`). Hiperparâmetros: `configs/model_params.yaml`; semente 42.

## Avaliação
Coerência (c_v, c_npmi) com IC 95% por bootstrap e revisão manual estratificada por tópico
com IC de Wilson — ver `docs/avaliacao.md`.

Primeira execução (snapshot da API de 2026-10-22, semente 42):

| Corpus | Documentos | Tópicos | No ruído (-1) | c_v (IC 95%) | c_npmi (IC 95%) |
|---|---|---|---|---|---|
| Ementas | 17.482 | 122 | 25,3% | 0,739 [0,702; 0,774] | 0,164 [0,135; 0,192] |
| Discursos | 44.269 | 125 | 54,1% | 0,666 [0,639; 0,693] | 0,047 [0,022; 0,072] |

IC por bootstrap sobre os tópicos, excluindo o -1. **Pendentes:** revisão manual (amostras
geradas, ainda sem rótulos), comparação com linha de base (LDA/NMF) e análise de
sensibilidade a UMAP/HDBSCAN. Sem linha de base, não se pode dizer se esses valores são bons.

## Avaliação por fatias (parcial)
Disponível apenas por corpus (tabela acima): os discursos têm o dobro da proporção de
documentos no ruído (54,1% contra 25,3%) e coerência menor, ou seja, são a fatia pior coberta.
**Pendente:** proporção no tópico -1 e coerência manual por tipo de proposição (PL, PLP, PEC,
MPV) e por ano.

## Vieses e justiça
Não há saída por indivíduo. Risco indireto: tópicos dominados por partidos grandes ou por
assuntos formulaicos podem sub-representar temas de minorias parlamentares. Auditar a
distribuição de tópicos por partido antes de interpretar diferenças.

## Limitações
Sensível a UMAP/HDBSCAN; documentos curtos geram tópicos instáveis; modelo de embeddings
multilíngue não é específico para o jargão jurídico-legislativo; um único revisor manual.

Observados na primeira execução: os termos dos tópicos saem sem acentos (`cdigo`, `educao`),
indicando que o vetorizador do c-TF-IDF descarta caracteres acentuados, o que pode afetar
stopwords e coerência (defeito a corrigir); 54% dos discursos caem no ruído; há tópicos
quase duplicados nos discursos (violência contra a mulher, educação, saúde).
