"""Testes de CLI, ambiente, logging e figuras."""

import logging
import os
import random
from datetime import datetime

import polars as pl
import pytest

from config.environment import seed_everything
from config.logging import _rename_rotated, configure_logging
from main import parse_args
from visualization.figures import plot_centrality_ranking, plot_topics_over_time, save_figure


@pytest.mark.smoke
def test_parse_args_defaults_and_validation():
    """O CLI aceita etapas conhecidas e rejeita as demais."""
    args = parse_args(["ingest", "--sources", "deputies", "--refresh"])
    assert args.stage == "ingest"
    assert args.sources == ["deputies"]
    assert args.refresh is True
    with pytest.raises(SystemExit):
        parse_args(["etapa-inexistente"])


def test_seed_everything_makes_random_deterministic():
    """A mesma semente reproduz a sequência e define PYTHONHASHSEED."""
    seed_everything(7)
    first = random.random()
    seed_everything(7)
    assert random.random() == first
    assert os.environ["PYTHONHASHSEED"] == "7"


def test_configure_logging_is_idempotent_and_overrides_level(tmp_path):
    """Chamar duas vezes não duplica handlers e ``level`` sobrescreve o root."""
    config_path = tmp_path / "logging.yaml"
    config_path.write_text(
        "version: 1\n"
        "disable_existing_loggers: false\n"
        "handlers:\n"
        "  console:\n"
        '    "()": config.logging.create_console_handler\n'
        "root:\n"
        "  level: INFO\n"
        "  handlers: [console]\n",
        encoding="utf-8",
    )
    root = logging.getLogger()
    saved_handlers, saved_level = root.handlers[:], root.level
    try:
        configure_logging("debug", config_path)
        configure_logging("debug", config_path)
        assert len(root.handlers) == 1
        assert root.level == logging.DEBUG
    finally:
        root.handlers[:] = saved_handlers
        root.setLevel(saved_level)
        logging.captureWarnings(False)


def test_daily_file_handler_renames_rotated_file(tmp_path):
    """O arquivo rotacionado recebe o nome ``log_YYYY-MM-DD.log``."""
    assert _rename_rotated(str(tmp_path / "log.log.2026-09-27")).endswith("log_2026-09-27.log")


def test_figures_are_saved_in_png_and_svg(tmp_path):
    """As figuras de ranking e de tópicos no tempo são salvas nos dois formatos."""
    table = pl.DataFrame({"node": ["a", "b"], "strength": [2.0, 1.0], "community": [0, 1]})
    paths = save_figure(plot_centrality_ranking(table, "strength"), "ranking", tmp_path)
    assert [p.suffix for p in paths] == [".png", ".svg"]
    assert all(p.is_file() for p in paths)

    over_time = pl.DataFrame(
        {
            "topic": [0, 0, 1, -1],
            "frequency": [3, 5, 2, 9],
            "timestamp": [datetime(2023, 1, 1), datetime(2023, 2, 1)] * 2,
        }
    )
    fig = plot_topics_over_time(over_time, {0: "saude", 1: "educacao"})
    assert save_figure(fig, "temporal", tmp_path)[0].is_file()


def test_plot_centrality_rejects_unknown_metric():
    """Métrica inexistente é erro de uso."""
    with pytest.raises(ValueError):
        plot_centrality_ranking(pl.DataFrame({"node": ["a"]}), "inexistente")
