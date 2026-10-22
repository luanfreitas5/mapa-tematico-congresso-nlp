"""BERTopic com UMAP + HDBSCAN sobre embeddings pré-calculados."""

from __future__ import annotations

import logging
from datetime import date, datetime, time
from typing import TYPE_CHECKING, cast

import numpy as np
import polars as pl

from config.settings import ModelParams
from constants.tokens import DEFAULT_STOPWORDS

if TYPE_CHECKING:
    from bertopic import BERTopic

logger = logging.getLogger(__name__)


def build_topic_model(params: ModelParams, seed: int) -> BERTopic:
    """Monta o BERTopic com UMAP, HDBSCAN e c-TF-IDF em português.

    Parameters
    ----------
    params : ModelParams
        Hiperparâmetros validados.
    seed : int
        Semente do UMAP (torna o resultado reprodutível, ao custo de paralelismo).

    Returns
    -------
    BERTopic
        Modelo não treinado, pronto para ``fit_topic_model``.

    Raises
    ------
    ImportError
        Se o extra ``nlp`` não estiver instalado.
    """
    try:
        from bertopic import BERTopic
        from hdbscan import HDBSCAN
        from sklearn.feature_extraction.text import CountVectorizer
        from umap import UMAP
    except ImportError as exc:
        raise ImportError("Instale o extra de PLN: uv sync --extra nlp") from exc

    umap_model = UMAP(
        n_neighbors=params.umap.n_neighbors,
        n_components=params.umap.n_components,
        min_dist=params.umap.min_dist,
        metric=params.umap.metric,
        random_state=seed,
    )
    hdbscan_model = HDBSCAN(
        min_cluster_size=params.hdbscan.min_cluster_size,
        min_samples=params.hdbscan.min_samples,
        metric=params.hdbscan.metric,
        cluster_selection_method=params.hdbscan.cluster_selection_method,
        prediction_data=True,
    )
    vectorizer = CountVectorizer(
        ngram_range=params.vectorizer.ngram_range,
        min_df=params.vectorizer.min_df,
        stop_words=sorted(DEFAULT_STOPWORDS),
    )
    return BERTopic(
        embedding_model=None,
        umap_model=umap_model,
        hdbscan_model=hdbscan_model,
        vectorizer_model=vectorizer,
        top_n_words=params.bertopic.top_n_words,
        nr_topics=params.bertopic.nr_topics,
        calculate_probabilities=False,
        verbose=True,
    )


def fit_topic_model(
    model: BERTopic, docs: list[str], embeddings: np.ndarray, reduce_outliers: bool = False
) -> list[int]:
    """Treina o modelo sobre documentos e embeddings pré-calculados.

    Parameters
    ----------
    model : BERTopic
        Modelo devolvido por ``build_topic_model``.
    docs : list[str]
        Documentos (texto limpo).
    embeddings : np.ndarray
        Embeddings alinhados a ``docs``.
    reduce_outliers : bool, optional
        Reatribui documentos do tópico -1 ao tópico mais próximo, by default False.

    Returns
    -------
    list[int]
        Tópico de cada documento (-1 = ruído, se não reduzido).

    Raises
    ------
    ValueError
        Se ``docs`` e ``embeddings`` tiverem tamanhos diferentes.
    """
    if len(docs) != len(embeddings):
        raise ValueError("docs e embeddings devem ter o mesmo tamanho")
    topics, _ = model.fit_transform(docs, embeddings=embeddings)
    if reduce_outliers:
        topics = model.reduce_outliers(docs, topics, embeddings=embeddings)
        model.update_topics(docs, topics=topics)
    return [int(topic) for topic in topics]


def summarize_topics(model: BERTopic, top_n_words: int) -> pl.DataFrame:
    """Resume os tópicos: tamanho, nome e palavras mais representativas.

    Parameters
    ----------
    model : BERTopic
        Modelo treinado.
    top_n_words : int
        Número de palavras por tópico.

    Returns
    -------
    pl.DataFrame
        Colunas ``topic``, ``count``, ``name`` e ``top_words``.
    """
    info = model.get_topic_info()
    rows = []
    for topic, count, name in zip(info["Topic"], info["Count"], info["Name"], strict=True):
        # stubs do BERTopic tipam o retorno como bool | list; em runtime é list[tuple[str, float]]
        topic_words = cast("list[tuple[str, float]]", model.get_topic(int(topic)) or [])
        words = [word for word, _ in topic_words][:top_n_words]
        rows.append(
            {"topic": int(topic), "count": int(count), "name": str(name), "top_words": words}
        )
    return pl.DataFrame(
        rows,
        schema={
            "topic": pl.Int64,
            "count": pl.Int64,
            "name": pl.String,
            "top_words": pl.List(pl.String),
        },
    )


def compute_topics_over_time(
    model: BERTopic, docs: list[str], periods: list[date], nr_bins: int
) -> pl.DataFrame:
    """Calcula a frequência de cada tópico ao longo do tempo.

    Parameters
    ----------
    model : BERTopic
        Modelo treinado.
    docs : list[str]
        Documentos usados no treino.
    periods : list[date]
        Data (mês) de cada documento.
    nr_bins : int
        Número de intervalos temporais.

    Returns
    -------
    pl.DataFrame
        Colunas ``topic``, ``words``, ``frequency`` e ``timestamp``.
    """
    stamps = [datetime.combine(period, time.min) for period in periods]
    # stubs do BERTopic aceitam só str/int, mas a biblioteca suporta datetime
    result = model.topics_over_time(docs, stamps, nr_bins=nr_bins)  # pyright: ignore[reportArgumentType]
    return pl.DataFrame(
        {
            "topic": result["Topic"].astype(int).tolist(),
            "words": result["Words"].astype(str).tolist(),
            "frequency": result["Frequency"].astype(int).tolist(),
            "timestamp": result["Timestamp"].tolist(),
        }
    )
