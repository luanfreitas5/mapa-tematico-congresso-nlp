"""Testes de CLI, ambiente, logging e figuras."""

import logging
import os
import random
from datetime import datetime

import polars as pl
import pytest

from config.environment import seed_everything
from config.logging import configure_logging
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


def test_configure_logging_creates_daily_file(base_settings, tmp_path):
    """O arquivo de log do dia é criado no diretório configurado."""
    configure_logging(base_settings.logging, tmp_path)
    root = logging.getLogger()
    try:
        logging.getLogger("teste").info("mensagem de teste")
        for handler in root.handlers:
            handler.flush()
        assert list(tmp_path.glob("log_*.log"))
    finally:
        for handler in root.handlers[:]:  # libera o arquivo (necessário no Windows)
            handler.close()
            root.removeHandler(handler)


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
