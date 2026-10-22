"""Revisão manual de uma amostra estratificada por tópico."""

import polars as pl

from utils.statistics import wilson_interval

REVIEW_COLUMNS = ("doc_id", "topic", "topic_name", "text", "is_coherent", "notes")


def create_review_sample(
    doc_topics: pl.DataFrame,
    topic_names: dict[int, str],
    per_topic: int,
    max_topics: int,
    seed: int,
) -> pl.DataFrame:
    """Sorteia documentos por tópico para revisão manual (ignora o tópico -1).

    Escolhe os ``max_topics`` maiores tópicos e sorteia até ``per_topic`` documentos
    de cada um. As colunas ``is_coherent`` (1/0) e ``notes`` ficam vazias para
    preenchimento pelo revisor.

    Parameters
    ----------
    doc_topics : pl.DataFrame
        Tabela gold (``doc_id``, ``topic``, ``text``).
    topic_names : dict[int, str]
        Rótulo de cada tópico.
    per_topic : int
        Documentos por tópico.
    max_topics : int
        Quantidade máxima de tópicos revisados.
    seed : int
        Semente do sorteio.

    Returns
    -------
    pl.DataFrame
        Amostra com as colunas de ``REVIEW_COLUMNS``.

    Examples
    --------
    >>> sample = create_review_sample(doc_topics, names, per_topic=5, max_topics=20, seed=42)
    """
    valid = doc_topics.filter(pl.col("topic") != -1)
    top_topics = (
        valid.group_by("topic")
        .len()
        .sort(["len", "topic"], descending=[True, False])
        .head(max_topics)["topic"]
        .to_list()
    )
    parts = [
        valid.filter(pl.col("topic") == topic).sample(
            n=min(per_topic, valid.filter(pl.col("topic") == topic).height), seed=seed
        )
        for topic in top_topics
    ]
    if not parts:
        return pl.DataFrame(schema=dict.fromkeys(REVIEW_COLUMNS, pl.String))
    return (
        pl.concat(parts)
        .with_columns(
            pl.col("topic").replace_strict(topic_names, default="").alias("topic_name"),
            pl.lit(None, dtype=pl.Int64).alias("is_coherent"),
            pl.lit(None, dtype=pl.String).alias("notes"),
        )
        .select(REVIEW_COLUMNS)
        .sort(["topic", "doc_id"])
    )


def summarize_review(reviewed: pl.DataFrame) -> pl.DataFrame:
    """Resume a revisão manual: proporção de coerentes com IC de Wilson, por tópico e total.

    Parameters
    ----------
    reviewed : pl.DataFrame
        Amostra preenchida (``is_coherent`` com 0/1; linhas nulas são ignoradas).

    Returns
    -------
    pl.DataFrame
        Colunas ``scope`` (``"total"`` ou ``topic``), ``n``, ``coherent``,
        ``proportion``, ``ci_low`` e ``ci_high``.

    Raises
    ------
    ValueError
        Se não houver nenhuma linha revisada ou houver valores fora de {0, 1}.
    """
    done = reviewed.filter(pl.col("is_coherent").is_not_null())
    if done.is_empty():
        raise ValueError("Nenhum documento revisado (is_coherent vazio)")
    if not done["is_coherent"].is_in([0, 1]).all():
        raise ValueError("is_coherent deve conter apenas 0 ou 1")

    def row(scope: str, frame: pl.DataFrame) -> dict[str, object]:
        """Calcula proporção e IC para um recorte da amostra."""
        coherent, total = int(frame["is_coherent"].sum()), frame.height
        proportion, low, high = wilson_interval(coherent, total)
        return {
            "scope": scope,
            "n": total,
            "coherent": coherent,
            "proportion": proportion,
            "ci_low": low,
            "ci_high": high,
        }

    rows = [row("total", done)]
    rows += [
        row(str(topic), frame)
        for (topic,), frame in done.sort("topic").partition_by("topic", as_dict=True).items()
    ]
    return pl.DataFrame(rows)
