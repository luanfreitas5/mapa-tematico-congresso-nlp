# 🏛️ Mapa Temático do Congresso

[![CI](https://github.com/luanfreitas5/mapa-tematico-congresso-nlp/actions/workflows/ci.yml/badge.svg)](https://github.com/luanfreitas5/mapa-tematico-congresso-nlp/actions/workflows/ci.yml)
[![Tests](https://github.com/luanfreitas5/mapa-tematico-congresso-nlp/actions/workflows/tests.yml/badge.svg)](https://github.com/luanfreitas5/mapa-tematico-congresso-nlp/actions/workflows/tests.yml)
[![Docs](https://github.com/luanfreitas5/mapa-tematico-congresso-nlp/actions/workflows/docs.yml/badge.svg)](https://luanfreitas5.github.io/mapa-tematico-congresso-nlp/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Modelagem de tópicos e análise de redes com os **dados abertos da Câmara dos Deputados**.

## 🎯 Problema

A Câmara produz milhares de proposições, votações e discursos por ano. Sem uma visão
estruturada, é difícil responder quais temas dominam a agenda, como eles evoluem e como os
atores se relacionam.

## ❓ Pergunta

> Quais **temas** aparecem nas ementas das proposições e nos discursos da 57ª legislatura, como
> sua frequência **muda ao longo do tempo**, e quem são os atores **centrais** nas redes de
> **coautoria** (deputados) e de **alinhamento de votos** (partidos)?

## 📦 Dados

| Fonte (endpoint `api/v2`) | Uso | Camada |
|---|---|---|
| `/deputados` | cadastro (id, partido, UF) | bronze → silver |
| `/proposicoes` (+ `/{id}/autores`) | ementas (tópicos) e coautoria (rede) | bronze → silver |
| `/votacoes` (+ `/{id}/votos`) | votos nominais por partido (rede) | bronze → silver |
| `/deputados/{id}/discursos` | discursos (tópicos) | bronze → silver |

- Dados **públicos**, de agentes públicos, da API oficial; nenhum dado bruto é versionado no Git.
- O e-mail e a foto dos deputados são descartados na silver (minimização, LGPD). Ver o
  [datasheet](reports/datasheets/camara_dados_abertos.md).
- Período e tipos de proposição: [`configs/config.yaml`](configs/config.yaml) (padrão: 2023-02 a
  2025-12; PL, PLP, PEC, MPV).

## 🧱 Arquitetura

```text
API ─▶ bronze (snapshots + manifesto SHA-256) ─▶ silver (pandera) ─┬▶ embeddings ─▶ BERTopic ─▶ gold
                                                                    └▶ redes (NetworkX) ───────▶ gold
```

Detalhes e decisões em [`docs/arquitetura.md`](docs/arquitetura.md).

## 🔁 Como reproduzir

Pré-requisitos: [uv](https://docs.astral.sh/uv/) e Python 3.10+. GPU é opcional (o `pyproject.toml`
aponta o PyTorch para o índice CUDA 12.8; ajuste `[tool.uv.sources]` se usar CPU).

```bash
make install-nlp     # núcleo + pilha de PLN (torch, sentence-transformers, BERTopic, gensim)
make hooks           # pre-commit + baseline do detect-secrets
make pipeline        # ingest → preprocess → topics → networks → evaluate
```

Etapas individuais: `make ingest`, `make preprocess`, `make topics`, `make networks`,
`make evaluate`. Sem o extra de PLN, `make install` basta para ingestão, silver e redes.

- **Idempotência:** `make ingest` reaproveita snapshots existentes; `make ingest REFRESH=1` grava
  um novo snapshot datado (os antigos nunca são alterados).
- **Reprodutibilidade:** semente 42 em tudo, `PYTHONHASHSEED` exportado pelo Makefile, `uv.lock`
  commitado e hash SHA-256 de cada snapshot em `data/bronze/manifest.json`.
- **Testes e qualidade:** `make test` (cobertura ≥ 80%), `make check` (espelha o CI).

## 📊 Resultados

> ⚠️ Os resultados serão preenchidos após a primeira execução completa. Nenhum número é
> reportado antes disso.

- Coerência dos tópicos (c_v e c_npmi, média com IC 95% por bootstrap) e revisão manual
  (proporção de documentos coerentes com IC de Wilson): ver [`docs/avaliacao.md`](docs/avaliacao.md).
- Figuras em `reports/figures/` (tópicos no tempo, rankings de centralidade).

## ⚠️ Limitações

- **Ementas e discursos têm registros diferentes:** ementas são curtas e formulaicas; discursos
  são longos e truncados em 5000 caracteres. Os tópicos não são comparáveis diretamente.
- **Data das proposições aproximada ao mês** da consulta (a listagem da API não traz a data).
- **Votos nominais apenas:** votações simbólicas não têm voto individual; a rede de partidos
  reflete só as votações nominais, que não são uma amostra aleatória.
- **Rede de partidos é densa:** o alinhamento entre partidos é alto em geral; o limiar
  `min_edge_weight` influencia as centralidades e deve ser reportado.
- **Coautoria:** proposições com mais de 30 autores não geram arestas (evita cliques de
  bancada); a escolha afeta a rede.
- **BERTopic é sensível a hiperparâmetros** (UMAP/HDBSCAN); parte dos documentos cai no tópico
  de ruído (-1). A revisão manual tem um único revisor.
- Sem inferência causal: centralidade descreve estrutura, não influência.

## 🗂️ Estrutura

```text
configs/   YAML validados por Pydantic        src/      código (imports a partir de src/)
data/      bronze | silver | gold (fora do Git) tests/    pytest + hypothesis
notebooks/ exploração e relatório             docs/     MkDocs Material
reports/   figuras, revisão, datasheet, model card
```

## 📄 Licença

MIT — veja [LICENSE](LICENSE).
