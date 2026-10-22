"""Etapas do pipeline: ingestão → silver → tópicos → redes → avaliação."""

import logging
from collections.abc import Callable, Sequence
from pathlib import Path

import polars as pl

from config.settings import Settings
from exceptions.data import DataNotFoundError
from ingestion.runner import SOURCE_ORDER, build_labels, run_ingestion
from networks.centrality import compute_centrality_table
from networks.coauthorship import annotate_nodes, build_coauthorship_graph
from networks.export import export_edges
from networks.voting import build_party_alignment_graph, compute_party_positions
from preprocessing import pipeline as silver_builders
from schemas.datasets import DOC_TOPICS_SCHEMA, validate_frame
from storage.bronze import BronzeStore
from storage.parquet import read_parquet, write_parquet

logger = logging.getLogger(__name__)

CORPORA: tuple[str, ...] = ("propositions", "speeches")


def run_ingest(
    settings: Settings, sources: Sequence[str] = SOURCE_ORDER, refresh: bool = False
) -> None:
    """Etapa 1: ingere as fontes selecionadas para a camada bronze.

    Parameters
    ----------
    settings : Settings
        Configuração validada.
    sources : Sequence[str], optional
        Fontes a ingerir, by default todas.
    refresh : bool, optional
        Ignora o cache e grava novo snapshot datado, by default False.
    """
    run_ingestion(settings, selected=sources, refresh=refresh)


def run_preprocess(settings: Settings) -> None:
    """Etapa 2: transforma a bronze em silver, validando cada contrato.

    Fontes ainda não ingeridas são puladas com um aviso.

    Parameters
    ----------
    settings : Settings
        Configuração validada.
    """
    store = BronzeStore(settings.paths.bronze)
    labels = build_labels(settings)
    pre = settings.preprocessing
    builders: dict[str, Callable[[pl.DataFrame], pl.DataFrame]] = {
        "deputies": silver_builders.build_silver_deputies,
        "propositions": lambda df: silver_builders.build_silver_propositions(
            df, pre.min_tokens_summary
        ),
        "authors": silver_builders.build_silver_authors,
        "votes": silver_builders.build_silver_votes,
        "speeches": lambda df: silver_builders.build_silver_speeches(
            df, pre.min_tokens_speech, pre.max_speech_chars
        ),
    }
    for name, build in builders.items():
        try:
            bronze = store.read_latest(name, labels[name])
        except DataNotFoundError:
            logger.warning("Bronze ausente para '%s'; etapa pulada", name)
            continue
        write_parquet(build(bronze), settings.paths.silver / f"{name}.parquet")


def _load_corpus(settings: Settings, corpus: str) -> pl.DataFrame:
    """Lê o corpus silver e acrescenta ``doc_id``."""
    silver = read_parquet(settings.paths.silver / f"{corpus}.parquet")
    id_column = "proposition_id" if corpus == "propositions" else "speech_id"
    return silver.with_columns(pl.col(id_column).cast(pl.String).alias("doc_id"))


def run_topics(settings: Settings, corpus: str) -> None:
    """Etapa 3: embeddings, BERTopic, tópicos ao longo do tempo e coerência (extra ``nlp``).

    Gera em ``data/gold``: ``doc_topics_<corpus>``, ``topics_<corpus>``,
    ``topics_over_time_<corpus>`` e ``coherence_<corpus>``, além da figura temporal.

    Parameters
    ----------
    settings : Settings
        Configuração validada.
    corpus : str
        ``"propositions"`` ou ``"speeches"``.

    Raises
    ------
    ValueError
        Se o corpus for desconhecido.
    """
    if corpus not in CORPORA:
        raise ValueError(f"Corpus desconhecido: {corpus}")
    from embeddings.encoder import load_or_encode
    from evaluation.coherence import (
        compute_per_topic_coherence,
        filter_topic_words,
        summarize_coherence,
    )
    from topics.model import (
        build_topic_model,
        compute_topics_over_time,
        fit_topic_model,
        summarize_topics,
    )
    from visualization.figures import plot_topics_over_time, save_figure

    params, gold = settings.model, settings.paths.gold
    frame = _load_corpus(settings, corpus)
    docs = frame["text_clean"].to_list()
    periods = frame["period"].to_list()

    embeddings = load_or_encode(docs, params.embeddings, gold / f"embeddings_{corpus}.npy")
    model = build_topic_model(params, settings.random_seed)
    topics = fit_topic_model(model, docs, embeddings, params.bertopic.reduce_outliers)

    doc_topics = frame.select("doc_id", "period", "text").with_columns(
        pl.Series("topic", topics, dtype=pl.Int64)
    )
    doc_topics = validate_frame(
        doc_topics.select(list(DOC_TOPICS_SCHEMA.columns)),
        DOC_TOPICS_SCHEMA,
        f"doc_topics {corpus}",
    )
    summary = summarize_topics(model, params.evaluation.top_n_words)
    over_time = compute_topics_over_time(model, docs, periods, params.topics_over_time.nr_bins)

    write_parquet(doc_topics, gold / f"doc_topics_{corpus}.parquet")
    write_parquet(summary, gold / f"topics_{corpus}.parquet")
    write_parquet(over_time, gold / f"topics_over_time_{corpus}.parquet")

    analyzer = model.vectorizer_model.build_analyzer()
    topic_words = {
        # stubs do BERTopic tipam o valor como float; em runtime é list[tuple[str, float]]
        int(topic): [word for word, _ in words][: params.evaluation.top_n_words]  # pyright: ignore[reportGeneralTypeIssues]
        for topic, words in model.get_topics().items()
    }
    vocabulary = {token for doc in docs for token in analyzer(doc)}
    valid_topics = filter_topic_words(topic_words, vocabulary)
    per_topic = compute_per_topic_coherence(
        valid_topics, [analyzer(doc) for doc in docs], params.evaluation.coherence_metrics
    )
    coherence = summarize_coherence(
        per_topic, params.evaluation.bootstrap_resamples, settings.random_seed
    )
    write_parquet(coherence, gold / f"coherence_{corpus}.parquet")

    names = dict(zip(summary["topic"].to_list(), summary["name"].to_list(), strict=True))
    save_figure(
        plot_topics_over_time(over_time, names),
        f"topics_over_time_{corpus}",
        settings.paths.figures,
    )


def run_networks(settings: Settings) -> None:
    """Etapa 4: redes de coautoria (deputados) e de alinhamento de votos (partidos).

    Gera em ``data/gold`` os nós (com centralidades e comunidade) e as arestas de
    cada rede, além dos rankings de centralidade em ``reports/figures``.

    Parameters
    ----------
    settings : Settings
        Configuração validada.
    """
    from visualization.figures import plot_centrality_ranking, save_figure

    cfg, gold, seed = settings.networks, settings.paths.gold, settings.random_seed

    deputies = read_parquet(settings.paths.silver / "deputies.parquet")
    authors = read_parquet(settings.paths.silver / "authors.parquet")
    coauthorship = annotate_nodes(
        build_coauthorship_graph(authors, cfg.max_authors_per_proposition), deputies
    )
    nodes = (
        compute_centrality_table(coauthorship, seed)
        .with_columns(pl.col("node").cast(pl.Int64).alias("deputy_id"))
        .join(deputies.select("deputy_id", "name", "party", "state"), on="deputy_id", how="left")
    )
    write_parquet(nodes, gold / "network_coauthorship_nodes.parquet")
    write_parquet(export_edges(coauthorship), gold / "network_coauthorship_edges.parquet")
    labelled = nodes.with_columns(pl.coalesce("name", "node").alias("node"))
    save_figure(
        plot_centrality_ranking(labelled, "strength"),
        "coautoria_strength",
        settings.paths.figures,
    )

    votes = read_parquet(settings.paths.silver / "votes.parquet")
    positions = compute_party_positions(votes, cfg.min_party_members_per_vote)
    alignment = build_party_alignment_graph(positions, cfg.min_common_votings, cfg.min_edge_weight)
    party_nodes = compute_centrality_table(alignment, seed)
    write_parquet(party_nodes, gold / "network_party_alignment_nodes.parquet")
    write_parquet(export_edges(alignment), gold / "network_party_alignment_edges.parquet")
    save_figure(
        plot_centrality_ranking(party_nodes, "strength"),
        "alinhamento_strength",
        settings.paths.figures,
    )


def run_evaluate(settings: Settings, corpus: str) -> Path:
    """Etapa 5: gera a amostra de revisão manual e, se já rotulada, resume-a com IC de Wilson.

    A amostra (``reports/review/review_sample_<corpus>.csv``) nunca é sobrescrita,
    para não perder rótulos manuais. Preencha ``is_coherent`` (1/0) e rode a etapa de novo.

    Parameters
    ----------
    settings : Settings
        Configuração validada.
    corpus : str
        ``"propositions"`` ou ``"speeches"``.

    Returns
    -------
    Path
        Caminho do CSV de revisão.

    Raises
    ------
    ValueError
        Se o corpus for desconhecido.
    """
    from evaluation.review import create_review_sample, summarize_review

    if corpus not in CORPORA:
        raise ValueError(f"Corpus desconhecido: {corpus}")
    review_dir = settings.paths.review
    sample_path = review_dir / f"review_sample_{corpus}.csv"
    evaluation = settings.model.evaluation

    if not sample_path.exists():
        doc_topics = read_parquet(settings.paths.gold / f"doc_topics_{corpus}.parquet")
        summary = read_parquet(settings.paths.gold / f"topics_{corpus}.parquet")
        names = dict(zip(summary["topic"].to_list(), summary["name"].to_list(), strict=True))
        sample = create_review_sample(
            doc_topics,
            names,
            evaluation.review_sample_per_topic,
            evaluation.review_max_topics,
            settings.random_seed,
        )
        review_dir.mkdir(parents=True, exist_ok=True)
        sample.write_csv(sample_path)
        logger.info("Amostra de revisão criada: %s", sample_path)
        return sample_path

    reviewed = pl.read_csv(
        sample_path, schema_overrides={"is_coherent": pl.Int64, "notes": pl.String}
    )
    if reviewed["is_coherent"].null_count() == reviewed.height:
        logger.info("Amostra ainda sem rótulos: preencha 'is_coherent' em %s", sample_path)
        return sample_path
    summarize_review(reviewed).write_csv(review_dir / f"review_summary_{corpus}.csv")
    logger.info("Resumo da revisão gravado em %s", review_dir)
    return sample_path
