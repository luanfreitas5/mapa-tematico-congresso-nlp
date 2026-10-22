"""Testes da avaliação: coerência (partes puras) e revisão manual."""

import polars as pl
import pytest

from evaluation.coherence import filter_topic_words, summarize_coherence
from evaluation.review import REVIEW_COLUMNS, create_review_sample, summarize_review


def test_filter_topic_words_drops_noise_topic_and_unknown_words():
    """O tópico -1, palavras fora do vocabulário e tópicos com < 2 palavras são descartados."""
    topic_words = {-1: ["x", "y"], 0: ["a", "b", "z"], 1: ["a", "q"]}
    assert filter_topic_words(topic_words, {"a", "b", "x"}) == [["a", "b"]]


def test_filter_topic_words_raises_when_nothing_evaluable():
    """Sem tópicos avaliáveis, falha explicitamente."""
    with pytest.raises(ValueError):
        filter_topic_words({-1: ["a", "b"]}, {"a", "b"})


def test_summarize_coherence_reports_interval_per_metric():
    """Cada métrica recebe média, IC e nº de tópicos."""
    summary = summarize_coherence({"c_v": [0.4, 0.5, 0.6], "c_npmi": [0.0, 0.1]}, 200, 42)
    assert summary["metric"].to_list() == ["c_v", "c_npmi"]
    row = summary.row(0, named=True)
    assert row["ci_low"] <= row["mean"] <= row["ci_high"]
    assert row["n_topics"] == 3


@pytest.fixture
def doc_topics() -> pl.DataFrame:
    """Gold sintético: tópico 0 (6 docs), 1 (4 docs) e ruído -1 (2 docs)."""
    topics = [0] * 6 + [1] * 4 + [-1] * 2
    return pl.DataFrame(
        {
            "doc_id": [str(i) for i in range(12)],
            "topic": topics,
            "text": [f"texto {i}" for i in range(12)],
        }
    )


def test_review_sample_is_stratified_and_skips_noise(doc_topics):
    """Sorteia até N por tópico entre os maiores e ignora o -1."""
    sample = create_review_sample(
        doc_topics, {0: "saude", 1: "educacao"}, per_topic=3, max_topics=2, seed=42
    )
    assert sample.columns == list(REVIEW_COLUMNS)
    assert sample.height == 6
    assert -1 not in sample["topic"].to_list()
    assert sample.filter(pl.col("topic") == 0)["topic_name"].unique().to_list() == ["saude"]
    assert sample["is_coherent"].null_count() == sample.height


def test_review_sample_is_reproducible(doc_topics):
    """A mesma semente produz a mesma amostra."""
    args = (doc_topics, {0: "a", 1: "b"}, 2, 2, 7)
    assert create_review_sample(*args).equals(create_review_sample(*args))


def test_review_sample_with_only_noise_is_empty():
    """Sem tópicos válidos a amostra é vazia, mas mantém as colunas."""
    noise = pl.DataFrame({"doc_id": ["1"], "topic": [-1], "text": ["x"]})
    sample = create_review_sample(noise, {}, 3, 3, 1)
    assert sample.is_empty()
    assert sample.columns == list(REVIEW_COLUMNS)


def test_summarize_review_reports_total_and_per_topic():
    """Calcula proporção e IC de Wilson no total e por tópico."""
    reviewed = pl.DataFrame(
        {"topic": [0, 0, 1, 1], "is_coherent": [1, 1, 0, 1], "doc_id": list("abcd")}
    )
    summary = summarize_review(reviewed)
    total = summary.filter(pl.col("scope") == "total").row(0, named=True)
    assert total["n"] == 4
    assert total["proportion"] == pytest.approx(0.75)
    assert total["ci_low"] < 0.75 < total["ci_high"]
    assert summary.height == 3


def test_summarize_review_validates_labels():
    """Sem rótulos ou com valores fora de {0, 1} é erro."""
    empty = pl.DataFrame(
        {"topic": [0], "is_coherent": [None]}, schema_overrides={"is_coherent": pl.Int64}
    )
    with pytest.raises(ValueError, match="Nenhum"):
        summarize_review(empty)
    bad = pl.DataFrame({"topic": [0], "is_coherent": [2]})
    with pytest.raises(ValueError, match="0 ou 1"):
        summarize_review(bad)
