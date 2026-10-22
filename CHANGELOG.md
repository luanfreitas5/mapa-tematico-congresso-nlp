# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e versionamento
[SemVer](https://semver.org/lang/pt-BR/). Atualizado pelo `commitizen` a cada release.

## [Unreleased]

### Added
- Ingestão idempotente da API da Câmara (deputados, proposições, autores, votações, votos,
  discursos) com paginação, retry exponencial e snapshots Parquet na bronze com manifesto.
- Pré-processamento de textos em português e camada silver validada por contratos (pandera).
- Embeddings multilíngues, BERTopic (UMAP + HDBSCAN) e tópicos ao longo do tempo.
- Redes de coautoria e de alinhamento de votos por partido, com centralidades e comunidades.
- Avaliação: coerência com IC por bootstrap e amostra de revisão manual com IC de Wilson.
- CI (lint, tipos, segurança, complexidade, testes) e documentação MkDocs.
