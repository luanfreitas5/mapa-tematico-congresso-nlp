"""Coerência de tópicos (c_v, c_npmi) com incerteza por bootstrap."""

import logging
from collections.abc import Collection, Sequence

import polars as pl

from utils.statistics import bootstrap_mean_interval

logger = logging.getLogger(__name__)


def filter_topic_words(
    topic_words: dict[int, list[str]], vocabulary: Collection[str]
) -> list[list[str]]:
    """Mantém só palavras do vocabulário e tópicos avaliáveis (≥ 2 palavras, sem o -1).

    Parameters
    ----------
    topic_words : dict[int, list[str]]
        Palavras representativas de cada tópico; o tópico -1 (ruído) é ignorado.
    vocabulary : Collection[str]
        Vocabulário do corpus tokenizado.

    Returns
    -------
    list[list[str]]
        Listas de palavras, uma por tópico avaliável.

    Raises
    ------
    ValueError
        Se nenhum tópico for avaliável.

    Examples
    --------
    >>> filter_topic_words({-1: ["x", "y"], 0: ["a", "b", "z"]}, {"a", "b"})
    [['a', 'b']]
    """
    filtered = [
        [word for word in words if word in vocabulary]
        for topic, words in topic_words.items()
        if topic != -1
    ]
    filtered = [words for words in filtered if len(words) >= 2]
    if not filtered:
        raise ValueError("Nenhum tópico avaliável com palavras presentes no corpus")
    return filtered


def summarize_coherence(
    per_topic: dict[str, list[float]], n_resamples: int, seed: int
) -> pl.DataFrame:
    """Resume as notas por tópico em média e IC 95% (bootstrap sobre os tópicos).

    Parameters
    ----------
    per_topic : dict[str, list[float]]
        Notas por tópico de cada métrica.
    n_resamples : int
        Reamostragens do bootstrap.
    seed : int
        Semente do bootstrap.

    Returns
    -------
    pl.DataFrame
        Uma linha por métrica: ``metric``, ``mean``, ``ci_low``, ``ci_high``, ``n_topics``.
    """
    rows = []
    for metric, scores in per_topic.items():
        mean, low, high = bootstrap_mean_interval(scores, n_resamples=n_resamples, seed=seed)
        logger.info("Coerência %s: %.3f (IC95%% %.3f a %.3f)", metric, mean, low, high)
        rows.append(
            {
                "metric": metric,
                "mean": mean,
                "ci_low": low,
                "ci_high": high,
                "n_topics": len(scores),
            }
        )
    return pl.DataFrame(rows)


def compute_per_topic_coherence(
    topics: list[list[str]], tokenized_docs: Sequence[Sequence[str]], metrics: Sequence[str]
) -> dict[str, list[float]]:
    """Calcula a coerência por tópico com o gensim.

    Parameters
    ----------
    topics : list[list[str]]
        Palavras de cada tópico (já filtradas por ``filter_topic_words``).
    tokenized_docs : Sequence[Sequence[str]]
        Corpus tokenizado com o mesmo analisador dos rótulos dos tópicos.
    metrics : Sequence[str]
        Métricas do gensim (ex.: ``["c_v", "c_npmi"]``).

    Returns
    -------
    dict[str, list[float]]
        Notas por tópico de cada métrica.

    Raises
    ------
    ImportError
        Se o extra ``nlp`` (gensim) não estiver instalado.
    """
    try:
        from gensim.corpora import Dictionary
        from gensim.models import CoherenceModel
    except ImportError as exc:
        raise ImportError("Instale o extra de PLN: uv sync --extra nlp") from exc

    texts = [list(doc) for doc in tokenized_docs]
    dictionary = Dictionary(texts)
    results: dict[str, list[float]] = {}
    for metric in metrics:
        model = CoherenceModel(
            topics=topics, texts=texts, dictionary=dictionary, coherence=metric, processes=1
        )
        results[metric] = [float(score) for score in model.get_coherence_per_topic()]
    return results
