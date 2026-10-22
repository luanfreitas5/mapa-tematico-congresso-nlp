"""Intervalos de confiança para métricas (nunca reportar apenas o ponto)."""

import math
from collections.abc import Sequence

import numpy as np


def bootstrap_mean_interval(
    values: Sequence[float],
    n_resamples: int = 2000,
    confidence: float = 0.95,
    seed: int = 42,
) -> tuple[float, float, float]:
    """Estima a média e seu intervalo de confiança por bootstrap percentílico.

    Parameters
    ----------
    values : Sequence[float]
        Observações (ex.: coerência por tópico).
    n_resamples : int, optional
        Número de reamostragens, by default 2000.
    confidence : float, optional
        Nível de confiança, by default 0.95.
    seed : int, optional
        Semente do gerador, by default 42.

    Returns
    -------
    tuple[float, float, float]
        ``(média, limite_inferior, limite_superior)``.

    Raises
    ------
    ValueError
        Se ``values`` estiver vazio ou ``confidence`` fora de (0, 1).

    Examples
    --------
    >>> mean, low, high = bootstrap_mean_interval([0.4, 0.5, 0.6])
    >>> low <= mean <= high
    True
    """
    if not values:
        raise ValueError("values não pode ser vazio")
    if not 0 < confidence < 1:
        raise ValueError("confidence deve estar entre 0 e 1")
    data = np.asarray(values, dtype=float)
    means = (
        np.random.default_rng(seed)
        .choice(data, size=(n_resamples, data.size), replace=True)
        .mean(axis=1)
    )
    alpha = (1 - confidence) / 2
    low, high = np.quantile(means, [alpha, 1 - alpha])
    return float(data.mean()), float(low), float(high)


def wilson_interval(
    successes: int, total: int, confidence: float = 0.95
) -> tuple[float, float, float]:
    """Calcula a proporção e o intervalo de Wilson para proporções binomiais.

    Parameters
    ----------
    successes : int
        Número de sucessos (ex.: documentos coerentes com o tópico).
    total : int
        Total de observações.
    confidence : float, optional
        Nível de confiança (0.90, 0.95 ou 0.99), by default 0.95.

    Returns
    -------
    tuple[float, float, float]
        ``(proporção, limite_inferior, limite_superior)``.

    Raises
    ------
    ValueError
        Se ``total`` for não positivo, ``successes`` fora de [0, total] ou
        ``confidence`` não suportado.

    Examples
    --------
    >>> p, low, high = wilson_interval(8, 10)
    >>> low < p < high
    True
    """
    z_values = {0.90: 1.6449, 0.95: 1.9600, 0.99: 2.5758}
    if total <= 0:
        raise ValueError("total deve ser positivo")
    if not 0 <= successes <= total:
        raise ValueError("successes deve estar entre 0 e total")
    if confidence not in z_values:
        raise ValueError("confidence deve ser 0.90, 0.95 ou 0.99")
    z = z_values[confidence]
    p = successes / total
    denominator = 1 + z**2 / total
    center = (p + z**2 / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z**2 / (4 * total**2)) / denominator
    return p, max(0.0, center - margin), min(1.0, center + margin)
