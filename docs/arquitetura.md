# Arquitetura

## Fluxo de dados (medalhão)

```text
API dadosabertos.camara.leg.br/api/v2
        │  ingestion (httpx + tenacity, paginação por links.next)
        ▼
data/bronze/<fonte>/<rótulo>__<AAAA-MM-DD>.parquet   (imutável) + manifest.json (SHA-256)
        │  preprocessing (limpeza, tipagem, dedup) + schemas (pandera)
        ▼
data/silver/{deputies,propositions,authors,votes,speeches}.parquet
        │                                   │
        │ embeddings + topics               │ networks
        ▼                                   ▼
data/gold/doc_topics_*, topics_*,     data/gold/network_*_nodes|edges
topics_over_time_*, coherence_*
        │
        ▼
reports/figures, reports/review (revisão manual)
```

## Decisões

| Decisão | Motivo |
|---|---|
| Núcleo leve + extra `nlp` | CI, ingestão e redes não precisam de torch (gigabytes); `uv sync --extra nlp` habilita tópicos. |
| Bronze com snapshots datados | Rastreabilidade: nada é sobrescrito; o cache é por `(fonte, rótulo)`, tornando a ingestão idempotente. |
| Proposições consultadas mês a mês | A listagem da API não traz a data de apresentação; a janela da consulta define o mês (`period`). |
| Textos limpos de forma leve | O encoder de sentenças usa frases; stopwords só entram no c-TF-IDF (rótulos dos tópicos). |
| Embeddings em cache com hash | Recalcular só se o modelo ou os textos mudarem. |
| Coerência com IC por bootstrap | Reportar média com incerteza, não só o ponto. |
| Rede de votos por posição do partido | Votos nominais são agregados pela maioria do partido em cada votação. |

## Pacotes (`src/`)

`config` · `constants` · `exceptions` · `schemas` · `storage` · `ingestion` · `preprocessing` ·
`embeddings` · `topics` · `networks` · `evaluation` · `visualization` · `pipelines` · `utils`.
Imports absolutos a partir de `src/` (sem prefixo `src.`).
