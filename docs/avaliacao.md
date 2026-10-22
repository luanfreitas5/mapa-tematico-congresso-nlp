# Avaliação dos tópicos

A avaliação combina uma métrica automática e uma revisão manual de amostra. Os **resultados
abaixo devem ser preenchidos após executar o pipeline**; este documento não traz números
inventados.

## 1. Coerência automática

`make topics` grava `data/gold/coherence_<corpus>.parquet` com, para cada métrica
(`c_v`, `c_npmi`), a média sobre os tópicos e o IC 95% por bootstrap (reamostragem dos
tópicos). O tópico -1 (ruído do HDBSCAN) é excluído.

| Corpus | Métrica | Média | IC 95% | Nº de tópicos |
|---|---|---|---|---|
| Ementas | c_v | _pendente_ | _pendente_ | _pendente_ |
| Ementas | c_npmi | _pendente_ | _pendente_ | _pendente_ |
| Discursos | c_v | _pendente_ | _pendente_ | _pendente_ |
| Discursos | c_npmi | _pendente_ | _pendente_ | _pendente_ |

Parâmetros e semente: `configs/model_params.yaml` e `configs/config.yaml` (`random_seed`).

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

### Padrões de erro observados

_Preencher após a revisão: tópicos que agregam temas distintos, tópicos dominados por
expressões formulaicas, documentos curtos mal classificados etc._

## Limitações da avaliação

- Um único revisor: sem concordância entre avaliadores (recomenda-se um segundo revisor em
  uma subamostra para calcular o kappa de Cohen).
- O tamanho da amostra por tópico é pequeno; os ICs são largos por tópico.
- Coerência automática correlaciona apenas parcialmente com o julgamento humano.
