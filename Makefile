# --- Configuração ----------------------------------------------------------
# 'src' vira raiz do path ao rodar o script
RUN := uv run python src/main.py

# PYTHONHASHSEED precisa ser exportado ANTES do interpretador iniciar: definido
# dentro do processo, não afeta a ordem de iteração de conjuntos já criada.
export PYTHONHASHSEED := 42

.DEFAULT_GOAL := help
.PHONY: help init venv install install-nlp install-all \
	update lock export \
	lint typecheck security deadcode complexity docstrings modernize quality check \
	test smoke test-all coverage hooks pre-commit update-hooks release docs docs-serve docs-deploy profile clean cache jupyter notebook add remove tree \
	ingest preprocess topics networks evaluate pipeline reproduce \
	clean-gold clean-silver clean-reports clean-outputs clean-notebooks

help:  ## Lista os alvos disponíveis
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

init:  ## Inicializa o projeto (instala dependências + hooks)
	$(MAKE) install
	$(MAKE) hooks

venv:  ## Cria o ambiente virtual (requer: uv)
	uv venv

install:  ## Instala o núcleo leve (ingestão, pré-processamento, redes) + dev
	uv sync --dev

install-nlp:  ## Instala também a pilha de PLN (torch, sentence-transformers, BERTopic, gensim)
	uv sync --dev --extra nlp

install-all:  ## Instala tudo (todos os extras + dev)
	uv sync --all-extras --dev

update:  ## Atualiza todas as dependências e sincroniza
	uv lock --upgrade
	uv sync --all-groups

lock:  ## Gera/atualiza o uv.lock (commite o arquivo)
	uv lock

export:  ## Exporta requirements.txt para quem usa pip
	uv export --no-hashes -o requirements.txt

# --- Qualidade -------------------------------------------------------------
lint: ## Lint com ruff (Format + Check)
	uv run ruff format .
	uv run ruff check --fix .

typecheck:  ## Type checking estático (basedPyright)
	uv run basedpyright

# PYSEC-2026-3447 (setuptools 81.0.0): dependência transitiva do torch 2.11, que
# limita a versão; a correção (83.0.0) não é instalável. Reavaliar ao atualizar o torch.
security:  ## Análise de segurança (bandit + pip-audit)
	uv run bandit -r src -c pyproject.toml
	uv run pip-audit --ignore-vuln PYSEC-2026-3447

deadcode:  ## Detecta código morto (vulture)
	uv run vulture src

complexity:  ## Limites de complexidade (xenon)
	uv run xenon --max-absolute B --max-modules A --max-average A src

docstrings:  ## Cobertura de docstrings (interrogate)
	uv run interrogate -v src

modernize:  ## Detecta código redundante (refurb)
	uv run refurb src

quality: lint typecheck security deadcode complexity docstrings modernize   ## Roda toda a suíte de qualidade (espelha o CI)

check: quality test  ## Roda localmente tudo o que o CI roda (qualidade + testes)

# --- Testes ----------------------------------------------------------------
test:  ## Roda os testes com cobertura (sem os lentos)
	uv run pytest -m "not slow"

smoke:  ## Roda apenas os smoke tests
	uv run pytest -m smoke -q --no-cov

test-all:  ## Roda a suíte completa, inclusive os testes lentos (requer: make install-nlp)
	uv run pytest

coverage:  ## Gera o relatório de cobertura em HTML
	uv run pytest -m "not slow" --cov-report=html
	@echo "Relatório disponível em htmlcov/index.html"

hooks:  ## Instala os hooks do pre-commit
	uv run pre-commit install
	uv run pre-commit install --hook-type commit-msg
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
