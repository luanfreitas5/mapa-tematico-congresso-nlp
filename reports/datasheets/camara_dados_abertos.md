# Datasheet — Dados Abertos da Câmara dos Deputados (57ª legislatura, recorte do projeto)

## 1. Motivação
- Por que foi criado? Para qual tarefa? Estudar temas legislativos (modelagem de tópicos) e relações entre atores (redes de coautoria e de alinhamento de votos) com dados oficiais. O recorte foi montado para este projeto de portfólio; a fonte original existe para transparência pública.
- Quem criou e quem financiou? Fonte: Câmara dos Deputados (dados abertos oficiais). Recorte e pipeline: Luan Freitas, sem financiamento.

## 2. Composição
- O que cada instância representa? Varia por tabela: deputado, proposição, vínculo proposição–autor, voto nominal individual em uma votação, discurso.
- Número de instâncias e período coberto (snapshot de 2026-10-22; período 2023-02-01 a 2025-12-31, 57ª legislatura):

| Tabela | Registros brutos | Após silver |
|---|---|---|
| Deputados | 882 | — |
| Proposições (PT, PL, PLP, PEC, MPV) | 17.505 | 17.482 |
| Autores (vínculos) | 32.387 | — |
| Votações | 34.489 | — |
| Votos nominais | 415.061 | — |
| Discursos | 44.528 | 44.269 |

- Campos, tipos e contrato: [`src/schemas/datasets.py`](../../src/schemas/datasets.py) (pandera, validado na entrada e na saída da silver).
- Rótulo: não há (aprendizado não supervisionado). Não existe verdade de referência para os tópicos.
- Dados ausentes (taxa por coluna): nas tabelas silver de proposições e discursos, 0% de nulos em todas as colunas (após descartar registros sem texto ou abaixo do mínimo de tokens). `TODO(owner): taxa de ausência por coluna nas tabelas bronze`.
- Campos sensíveis / PII e tratamento: nomes, partido e UF de agentes públicos (dados públicos). E-mail, foto e URIs são descartados na silver. Discursos podem citar terceiros (cidadãos, magistrados, vítimas) em texto livre; não são publicados nos relatórios.
- É amostra de uma população maior? Como amostrado? Não é amostra aleatória: recorte por legislatura, período e tipos de proposição. Votos nominais cobrem apenas votações nominais (votações simbólicas não têm voto individual).

## 3. Processo de coleta
- Fonte(s) e sistema(s) de origem: API REST oficial `https://dadosabertos.camara.leg.br/api/v2` (`/deputados`, `/proposicoes` e `/{id}/autores`, `/votacoes` e `/{id}/votos`, `/deputados/{id}/discursos`), sem autenticação.
- Período e frequência de coleta: coleta única em 2026-10-22; novos snapshots datados sob demanda (`make ingest REFRESH=1`). Paginação de 100, retry com backoff e `max_workers=8`.
- Consentimento / aviso aos titulares: não se aplica — dados publicados pela própria Câmara sobre agentes públicos no exercício do mandato.

## 4. Pré-processamento
- Limpeza, filtragem e linhas removidas por regra: tipagem, deduplicação, limpeza leve de texto; ementas com menos de 5 tokens e discursos com menos de 30 tokens são descartados (23 ementas e 259 discursos a menos que o bruto); discursos truncados em 5000 caracteres. A data das proposições é aproximada ao mês da consulta.
- Anonimização / pseudonimização: não há pseudonimização (dados públicos); minimização por descarte de e-mail e foto.
- Hash SHA-256 dos dados brutos (`data/bronze/manifest.json`, snapshot 2026-10-22):
  - deputados `e7972c1738b678058830d0cfadb5b8bad89b0cb1270ef4016e8383f785751b87`
  - proposições `a563e526a5ef22a87897ba3964d362e08efe864bbe0f2085919e15ebe9642961`
  - autores `446a225b6c4dfeab244a8b4e7ec6178a7e22c1da6b654eb517c9f4bced8b62d2`
  - votações `fea62be1a6b4a79978285bfe5f8ce8bb557b0b5cbff3107f0c89fd790f9cd93a`
  - votos `194d4149cb8328b5d036f3fafa7fd182896da8bfc66e2a1307a6622865385367`
  - discursos `d74c12e27a9ffefd570e926ace09638a4cbef3b2857ffab8449c9c75865ac0cf`

## 5. Usos
- Usos pretendidos: modelagem de tópicos, séries temporais de temas e análise de redes de coautoria e de alinhamento partidário em votações nominais; pesquisa, jornalismo de dados e portfólio.
- Usos desaconselhados: avaliar ou rotular indivíduos; inferir posição política de um parlamentar a partir de um discurso; generalizar o alinhamento de votos para votações simbólicas; publicar trechos de discursos sem checar menções a particulares; inferência causal.
- Riscos de viés conhecidos: ementas formulaicas (datas comemorativas, Código Penal) dominam a frequência; votações nominais não são amostra aleatória; discursos truncados; transcrição ausente (usa-se o sumário); partidos grandes pesam mais nos tópicos.

## 6. Distribuição
- Licença e restrições: dados abertos publicados pela Câmara dos Deputados; `TODO(owner): confirmar e citar a licença/termos exatos do portal de dados abertos`. Os dados brutos **não** são redistribuídos neste repositório.
- Onde está armazenado (DVC remote, bucket): somente local, em `data/bronze/`, `data/silver/` e `data/gold/` (fora do Git); regeneráveis pelo pipeline. Sem DVC remote configurado.

## 7. Manutenção
- Responsável: Luan Freitas — luan.mgf@gmail.com
- Frequência de atualização: sob demanda (novo snapshot datado; os anteriores nunca são alterados).
- Como atender pedidos de exclusão de titulares: os dados derivam de fonte pública e são regeneráveis; para remover um titular, excluir seus registros da silver/gold e reexecutar o pipeline (`make clean-outputs pipeline`). A bronze é imutável por projeto — remover o snapshot afetado e reingerir.

## 8. LGPD
- Base legal (art. 7 / art. 11): dados tornados manifestamente públicos, sobre agentes públicos no exercício do mandato (LGPD, art. 7º, §§ 3º e 4º), para pesquisa e transparência. _Revisar com assessoria jurídica antes de qualquer uso comercial._
- Prazo de retenção: enquanto o projeto existir; dados regeneráveis a qualquer momento. `TODO(owner): definir prazo formal`.
- Relatório de impacto (RIPD) necessário? Não — dados públicos de agentes públicos, sem dados sensíveis (art. 11) tratados; nomes aparecem apenas em rankings agregados de centralidade. Reavaliar se houver publicação de textos de discursos.
