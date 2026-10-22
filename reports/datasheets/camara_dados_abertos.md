# Datasheet — Dados Abertos da Câmara dos Deputados (recorte do projeto)

## Motivação
Estudar temas legislativos e relações entre atores (deputados e partidos) com dados
oficiais, para um projeto de portfólio de ciência de dados.

## Composição
- **Deputados:** id, nome, partido, UF, legislatura.
- **Proposições:** tipo, número, ano e ementa (PL, PLP, PEC, MPV no período configurado).
- **Autoria:** vínculo proposição–autor (somente autores deputados são usados).
- **Votações/votos:** voto nominal (Sim, Não, Abstenção etc.) por deputado e votação.
- **Discursos:** sumário/transcrição, data e deputado.

## Coleta
API REST oficial `https://dadosabertos.camara.leg.br/api/v2`, sem autenticação, com
paginação, retry e *rate* moderado (`max_workers`). Cada snapshot é registrado em
`data/bronze/manifest.json` com data, parâmetros e SHA-256.

## Pré-processamento
Bronze → silver: tipagem, deduplicação, limpeza leve de texto e validação por schema
(`src/schemas/datasets.py`). Colunas de e-mail, foto e URIs são descartadas.

## Licença e uso
Dados abertos publicados pela Câmara dos Deputados; consulte os termos de uso do portal
de dados abertos. Os dados brutos **não** são redistribuídos neste repositório.

## Privacidade e LGPD
- Conteúdo de natureza pública, sobre agentes públicos no exercício do mandato. Base legal
  para o tratamento: dados tornados manifestamente públicos pelo titular/ente público
  (LGPD, art. 7º, §§ 3º e 4º), em atendimento à finalidade de pesquisa e transparência.
  _Revisar com assessoria jurídica antes de qualquer uso comercial._
- Minimização: e-mail e foto não são mantidos. Nomes de deputados aparecem apenas em
  rankings agregados de centralidade.
- Discursos podem mencionar terceiros (cidadãos, magistrados, vítimas); o projeto não
  publica textos de discursos nos relatórios, apenas tópicos agregados e a amostra de
  revisão local. Evite publicar trechos da amostra sem checar menções a particulares.
- Direito de exclusão: os dados são derivados de fonte pública e podem ser regenerados;
  remover um titular implica remover seus registros das camadas silver/gold e rodar o
  pipeline de novo.

## Limitações conhecidas
Votos nominais não representam todas as votações; datas de proposição aproximadas ao mês;
discursos podem ter transcrição ausente (usa-se o sumário).
