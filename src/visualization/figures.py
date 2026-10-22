"""Figuras de tópicos e redes."""

from pathlib import Path

import matplotlib.pyplot as plt
import polars as pl
import seaborn as sns
from matplotlib.figure import Figure

from visualization.theme import apply_theme


def save_figure(fig: Figure, name: str, directory: Path) -> list[Path]:
    """Salva a figura em PNG (300 dpi) e SVG.

    Parameters
    ----------
    fig : Figure
        Figura do matplotlib.
    name : str
        Nome base do arquivo, sem extensão.
    directory : Path
        Diretório de destino (criado se necessário).

    Returns
    -------
    list[Path]
        Caminhos gravados.
    """
    directory.mkdir(parents=True, exist_ok=True)
    paths = [directory / f"{name}.png", directory / f"{name}.svg"]
    fig.savefig(paths[0], dpi=300, bbox_inches="tight")
    fig.savefig(paths[1], bbox_inches="tight")
    plt.close(fig)
    return paths


def plot_topics_over_time(
    over_time: pl.DataFrame, topic_names: dict[int, str], top_n: int = 8
) -> Figure:
    """Plota a frequência dos ``top_n`` maiores tópicos ao longo do tempo.

    Parameters
    ----------
    over_time : pl.DataFrame
        Saída de ``compute_topics_over_time`` (``topic``, ``frequency``, ``timestamp``).
    topic_names : dict[int, str]
        Rótulo de cada tópico.
    top_n : int, optional
        Quantidade de tópicos exibidos, by default 8.

    Returns
    -------
    Figure
        Figura pronta para ``save_figure``.
    """
    apply_theme()
    valid = over_time.filter(pl.col("topic") != -1)
    top = (
        valid.group_by("topic").agg(pl.col("frequency").sum()).sort("frequency", descending=True)
    ).head(top_n)["topic"]
    data = (
        valid.filter(pl.col("topic").is_in(top))
        .with_columns(
            pl.col("topic").replace_strict(topic_names, default="").alias("label"),
        )
        .to_pandas()
    )
    fig, ax = plt.subplots(figsize=(11, 5))
    sns.lineplot(data=data, x="timestamp", y="frequency", hue="label", marker="o", ax=ax)
    ax.set_title("Evolução dos principais tópicos")
    ax.set_xlabel("Período")
    ax.set_ylabel("Documentos por intervalo")
    ax.legend(title="Tópico", fontsize=8, loc="upper left", bbox_to_anchor=(1, 1))
    return fig


def plot_centrality_ranking(table: pl.DataFrame, metric: str, top_n: int = 15) -> Figure:
    """Plota o ranking dos nós por uma métrica de centralidade.

    Parameters
    ----------
    table : pl.DataFrame
        Saída de ``compute_centrality_table``.
    metric : str
        Coluna da métrica (ex.: ``"strength"``).
    top_n : int, optional
        Quantidade de nós exibidos, by default 15.

    Returns
    -------
    Figure
        Figura pronta para ``save_figure``.

    Raises
    ------
    ValueError
        Se ``metric`` não existir na tabela.
    """
    if metric not in table.columns:
        raise ValueError(f"Métrica desconhecida: {metric}")
    apply_theme()
    data = (
        table.sort(metric, descending=True)
        .head(top_n)
        .with_columns(pl.col("community").cast(pl.String))  # hue categórico
        .to_pandas()
    )
    fig, ax = plt.subplots(figsize=(8, 0.4 * len(data) + 1.5))
    sns.barplot(data=data, y="node", x=metric, hue="community", dodge=False, ax=ax)
    ax.set_title(f"Ranking por {metric}")
    ax.set_xlabel(metric)
    ax.set_ylabel("Nó")
    return fig
