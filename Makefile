# --- Configuração ----------------------------------------------------------
# 'src' vira raiz do path ao rodar o script
RUN := uv run python src/main.py

# PYTHONHASHSEED precisa ser exportado ANTES do interpretador iniciar: definido
# dentro do processo, não afeta a ordem de iteração de conjuntos já criada.
export PYTHONHASHSEED := 42

.DEFAULT_GOAL := help
.PHONY: help init venv install install-nlp install-all \
	update lock export \
	lint format typecheck security quality check \
	test smoke test-all coverage hooks pre-commit update-hooks release docs docs-serve docs-deploy profile clean cache jupyter notebook add remove tree \
	ingest preprocess topics networks evaluate pipeline train reproduce \
	clean-gold clean-silver clean-reports clean-outputs clean-notebooks

help:  ## Lista os alvos disponíveis
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

init:  ## Inicializa o projeto (instala dependências + hooks)
	$(MAKE) install
	$(MAKE) hooks

venv:  ## Cria o ambiente virtual (requer: uv)
	uv venv

install:  ## Instala o núcleo leve (ingestão, pré-processamento, redes) + todos os grupos de dev
	uv sync --all-groups

install-nlp:  ## Instala também a pilha de PLN (torch, sentence-transformers, BERTopic, gensim)
	uv sync --all-groups --extra nlp

install-all:  ## Instala tudo (todos os extras + dev)
	uv sync --all-extras --all-groups

update:  ## Atualiza todas as dependências e sincroniza
	uv lock --upgrade
	uv sync --all-groups

lock:  ## Gera/atualiza o uv.lock (commite o arquivo)
	uv lock

export:  ## Exporta requirements.txt para quem usa pip
	uv export --no-hashes -o requirements.txt

# --- Qualidade (espelha o CI) ----------------------------------------------
lint:  ## Verifica lint e formatação (ruff) sem alterar arquivos
	uv run ruff check src tests
	uv run ruff format --check src tests

format:  ## Corrige lint e formata o código (ruff)
	uv run ruff check --fix src tests
	uv run ruff format src tests

typecheck:  ## Type checking estático (basedPyright)
	uv run basedpyright

# PYSEC-2026-3447 e GHSA-xmj3-9gf7-h52w (setuptools 81.0.0): dependência transitiva do torch 2.11, que
# limita a versão; as correções (83.0.0 / 84.1.0) não é instalável. Reavaliar ao atualizar o torch.
security:  ## Análise de segurança (bandit + pip-audit)
	uv run bandit -c pyproject.toml -r src
	uv run pip-audit --ignore-vuln PYSEC-2026-3447 --ignore-vuln GHSA-xmj3-9gf7-h52w

quality:  ## Código morto, modernização, complexidade e docstrings (vulture, refurb, xenon, interrogate)
	uv run vulture
	uv run refurb src
	uv run xenon --max-absolute B --max-modules A --max-average A src
	uv run interrogate -v src

check: lint typecheck security quality test  ## Roda localmente tudo o que o CI roda

# --- Testes ----------------------------------------------------------------
test:  ## Roda os testes com cobertura (sem os lentos)
	uv run pytest -m "not slow" --cov-report=term-missing

smoke:  ## Roda apenas os smoke tests
	uv run pytest -m smoke -q --no-cov

test-all:  ## Roda a suíte completa, inclusive os testes lentos (requer: make install-nlp)
	uv run pytest

coverage:  ## Gera o relatório de cobertura em HTML
	uv run pytest -m "not slow" --cov-report=html
	@echo "Relatório disponível em htmlcov/index.html"

hooks:  ## Instala os hooks do pre-commit (pre-commit + commit-msg) e o baseline do detect-secrets
	uv run pre-commit install --hook-type pre-commit --hook-type commit-msg
	uv run detect-secrets scan > .secrets.baseline

pre-commit:  ## Roda todos os hooks do pre-commit em todos os arquivos
	uv run pre-commit run --all-files

update-hooks:  ## Atualiza os hooks do pre-commit
	uv run pre-commit autoupdate

release:  ## Cria uma nova release (versão + changelog + tag)
	uv run cz bump --changelog

# --- Pipeline ---------------------------------------------------------------
ingest:  ## Etapa 1: ingere a API da Câmara para data/bronze (idempotente; REFRESH=1 ignora o cache)
	$(RUN) ingest $(if $(REFRESH),--refresh,)

preprocess:  ## Etapa 2: bronze -> silver (limpeza + contratos de dados)
	$(RUN) preprocess

topics:  ## Etapa 3: embeddings + BERTopic + tópicos no tempo + coerência (requer: make install-nlp)
	$(RUN) topics

networks:  ## Etapa 4: redes de coautoria e de alinhamento de votos + centralidades
	$(RUN) networks

evaluate:  ## Etapa 5: amostra de revisão manual (e resumo, se já rotulada)
	$(RUN) evaluate

pipeline: ingest preprocess topics networks evaluate  ## Executa todas as etapas em sequência

train: topics  ## Alias do template: treina o modelo (BERTopic) sobre a silver

reproduce: install-nlp pipeline  ## Reproduz o estudo do zero (ambiente + pipeline)

# --- Limpeza de saídas do pipeline ------------------------------------------
clean-silver:  ## Remove a camada silver (derivada; a bronze nunca é apagada)
	rm -rf data/silver/*.parquet

clean-gold:  ## Remove os dados da camada gold (derivados; bronze nunca é apagado)
	rm -rf data/gold/*.parquet data/gold/*.npy data/gold/*.json

clean-reports:  ## Remove as figuras geradas (a amostra de revisão manual é preservada)
	rm -rf reports/figures/*.png reports/figures/*.svg

clean-outputs: clean-silver clean-gold clean-reports  ## Remove todas as saídas derivadas do pipeline

clean-notebooks:  ## Remove os outputs dos notebooks
	uv run nbstripout notebooks/*.ipynb

# --- Documentação ----------------------------------------------------------
docs:  ## Constrói a documentação (modo estrito)
	uv run mkdocs build --strict

docs-serve:  ## Servidor local da documentação
	uv run mkdocs serve

docs-deploy:  ## Publica a documentação no GitHub Pages
	uv run mkdocs gh-deploy --force

# --- Utilitários -----------------------------------------------------------
profile:  ## Profiling com scalene de uma etapa (ex.: make profile STAGE=preprocess)
	uv run scalene src/main.py $(or $(STAGE),preprocess)

clean:  ## Remove caches e artefatos temporários
	rm -rf .pytest_cache .ruff_cache .mypy_cache .hypothesis htmlcov coverage.xml site
	find . -type d -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} +

cache:  ## Limpa o cache do uv
	uv cache clean

# --- Jupyter ----------------------------------------------------------------
jupyter:  ## Abre o JupyterLab
	uv run jupyter lab

notebook:  ## Abre o Jupyter Notebook clássico
	uv run jupyter notebook

# --- Gerenciamento de pacotes -----------------------------------------------
add:  ## Adiciona uma dependência (make add PKG=nome)
	uv add $(PKG)

remove:  ## Remove uma dependência (make remove PKG=nome)
	uv remove $(PKG)

tree:  ## Mostra a árvore de dependências
	uv tree
