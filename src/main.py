"""Ponto de entrada: orquestra as etapas do pipeline.

Uso::

    uv run python src/main.py ingest --sources deputies propositions
    uv run python src/main.py preprocess
    uv run python src/main.py topics --corpus propositions
    uv run python src/main.py networks
    uv run python src/main.py evaluate --corpus propositions
    uv run python src/main.py all
"""

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

# `src/` é a raiz de importação; garante o path ao rodar `python src/main.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.environment import seed_everything
from config.logging import configure_logging
from config.paths import CONFIGS_DIR
from config.settings import Settings, load_settings
from ingestion.runner import SOURCE_ORDER
from pipelines import workflow

logger = logging.getLogger(__name__)

STAGES = ("ingest", "preprocess", "topics", "networks", "evaluate", "all")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Interpreta os argumentos de linha de comando.

    Parameters
    ----------
    argv : Sequence[str], optional
        Argumentos; por padrão, ``sys.argv[1:]``.

    Returns
    -------
    argparse.Namespace
        Argumentos validados.

    Examples
    --------
    >>> parse_args(["ingest", "--sources", "deputies"]).sources
    ['deputies']
    """
    parser = argparse.ArgumentParser(description="Mapa temático do Congresso (PLN + redes)")
    parser.add_argument("stage", choices=STAGES, help="Etapa a executar")
    parser.add_argument("--config-dir", type=Path, default=CONFIGS_DIR, help="Pasta dos YAML")
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=SOURCE_ORDER,
        default=list(SOURCE_ORDER),
        help="Fontes da ingestão",
    )
    parser.add_argument(
        "--corpus",
        nargs="+",
        choices=workflow.CORPORA,
        default=list(workflow.CORPORA),
        help="Corpora de texto para tópicos/avaliação",
    )
    parser.add_argument("--refresh", action="store_true", help="Ignora o cache bronze")
    return parser.parse_args(argv)


def _run_stage(stage: str, settings: Settings, args: argparse.Namespace) -> None:
    """Executa uma única etapa do pipeline (por corpus, quando aplicável)."""
    if stage == "ingest":
        workflow.run_ingest(settings, args.sources, args.refresh)
    elif stage == "preprocess":
        workflow.run_preprocess(settings)
    elif stage == "topics":
        for corpus in args.corpus:
            workflow.run_topics(settings, corpus)
    elif stage == "networks":
        workflow.run_networks(settings)
    elif stage == "evaluate":
        for corpus in args.corpus:
            workflow.run_evaluate(settings, corpus)


def main(argv: Sequence[str] | None = None) -> int:
    """Executa a(s) etapa(s) pedida(s).

    Parameters
    ----------
    argv : Sequence[str], optional
        Argumentos de linha de comando.

    Returns
    -------
    int
        Código de saída (0 = sucesso).
    """
    args = parse_args(argv)
    settings = load_settings(args.config_dir)
    configure_logging(settings.logging, settings.paths.logs)
    seed_everything(settings.random_seed)

    stages = STAGES[:-1] if args.stage == "all" else (args.stage,)
    for stage in stages:
        _run_stage(stage, settings, args)
    logger.info("Etapa '%s' concluída", args.stage)
    return 0


if __name__ == "__main__":
    sys.exit(main())
