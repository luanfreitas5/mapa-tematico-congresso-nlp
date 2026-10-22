# Avaliação dos tópicos

A avaliação combina uma métrica automática e uma revisão manual de amostra. A coerência
automática abaixo vem da primeira execução completa (snapshot da API de 2026-10-22, semente 42).
A **revisão manual ainda não foi feita**; este documento não traz números inventados.

## 1. Coerência automática

`make topics` grava `data/gold/coherence_<corpus>.parquet` com, para cada métrica
(`c_v`, `c_npmi`), a média sobre os tópicos e o IC 95% por bootstrap (reamostragem dos
tópicos). O tópico -1 (ruído do HDBSCAN) é excluído.

| Corpus | Métrica | Média | IC 95% | Nº de tópicos |
|---|---|---|---|---|
| Ementas | c_v | 0,739 | [0,702; 0,774] | 120 |
| Ementas | c_npmi | 0,164 | [0,135; 0,192] | 120 |
| Discursos | c_v | 0,666 | [0,639; 0,693] | 125 |
| Discursos | c_npmi | 0,047 | [0,022; 0,072] | 125 |

Parâmetros e semente: `configs/model_params.yaml` e `configs/config.yaml` (`random_seed`).

**Cobertura.** O modelo de ementas produz 122 tópicos e deixa 25,3% dos documentos (4.426 de
17.482) no tópico -1. O de discursos produz 125 tópicos e deixa 54,1% (23.933 de 44.269) no
ruído. A coerência é calculada só sobre os tópicos, então não mede essa perda de cobertura:
reporte as duas coisas juntas.

**Leitura.** As ementas são mais coerentes que os discursos em ambas as métricas e os ICs não
se sobrepõem. O c_npmi dos discursos (0,047) é próximo de zero, com o IC inferior em 0,022,
o que indica associação fraca entre as palavras de topo. Não há linha de base (LDA ou NMF)
nem modelo alternativo para comparar, portanto não se pode afirmar que esses valores sejam
bons ou ruins em termos relativos.

**Ressalva técnica.** Os termos dos tópicos saem sem acentos (`cdigo penal`, `educao`).
O vetorizador provavelmente descarta caracteres acentuados, o que pode afetar as stopwords
e a coerência medida. Corrigir e reexecutar antes de tratar estes números como definitivos.

> Observação: o `n_topics` da tabela (120 e 125) é o usado no cálculo da coerência, e o do
> parágrafo acima (122) conta os tópicos presentes em `doc_topics_propositions.parquet`; a
> diferença nas ementas ainda não foi investigada.

## 2. Revisão manual

`make evaluate` cria `reports/review/review_sample_<corpus>.csv` com até 5 documentos por
tópico (até 20 maiores tópicos), sorteados com semente fixa. O arquivo **nunca é
sobrescrito**, para preservar os rótulos.

Protocolo:

1. Para cada linha, leia o texto e o rótulo do tópico (`topic_name`).
2. Preencha `is_coherent`: `1` se o documento trata do tema do tópico; `0` caso contrário.
3. Use `notes` para erros recorrentes (ex.: tópico misturando saúde e previdência).
4. Rode `make evaluate` de novo: gera `review_summary_<corpus>.csv` com a proporção de
   documentos coerentes e o IC de Wilson, no total e por tópico.

### Registro da revisão

| Data | Corpus | Revisor | n | Coerentes | Proporção (IC 95%) |
|---|---|---|---|---|---|
| _pendente_ | | | | | |

As amostras já foram geradas (`reports/review/review_sample_propositions.csv` e
`review_sample_speeches.csv`), mas `is_coherent` ainda está vazio.

### Padrões de erro observados

_Preencher após a revisão: tópicos que agregam temas distintos, tópicos dominados por
expressões formulaicas, documentos curtos mal classificados etc._

Indícios a verificar na revisão, vistos apenas nos rótulos e **não confirmados**: pares de
tópicos quase duplicados nos discursos (violência contra a mulher, educação, saúde) e o
tópico -1 dominado por termos genéricos (`sr`, `ns`, `brasil`).

## Limitações da avaliação

- Um único revisor: sem concordância entre avaliadores (recomenda-se um segundo revisor em
  uma subamostra para calcular o kappa de Cohen).
- O tamanho da amostra por tópico é pequeno; os ICs são largos por tópico.
- Coerência automática correlaciona apenas parcialmente com o julgamento humano.
