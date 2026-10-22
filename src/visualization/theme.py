"""Tema visual compartilhado."""

import matplotlib.pyplot as plt
import seaborn as sns

PALETTE: list[str] = [
    "#1b6ca8",
    "#e07a1f",
    "#2a9d8f",
    "#c0392b",
    "#7d5ba6",
    "#8c6d31",
    "#d4568b",
    "#5f6b73",
]


def apply_theme() -> None:
    """Aplica o estilo seaborn e a paleta do projeto globalmente.

    Examples
    --------
    >>> apply_theme()
    """
    sns.set_theme(style="whitegrid", palette=PALETTE, context="notebook")
    plt.rcParams["figure.dpi"] = 120
