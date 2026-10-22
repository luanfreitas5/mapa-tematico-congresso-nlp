"""Testes dos adaptadores do extra ``nlp`` (pulados quando as bibliotecas não estão instaladas)."""

import numpy as np
import pytest

pytest.importorskip("bertopic")
pytest.importorskip("hdbscan")
pytest.importorskip("umap")

from topics.model import build_topic_model, fit_topic_model, summarize_topics

pytestmark = [pytest.mark.ml, pytest.mark.slow]


def test_fit_topic_model_separates_two_synthetic_clusters(base_settings):
    """Dois clusters gaussianos bem separados, com vocabulários distintos, geram ≥ 2 tópicos."""
    rng = np.random.default_rng(0)
    n = 120
    embeddings = np.vstack(
        [rng.normal(0, 0.1, (n, 16)) + 3, rng.normal(0, 0.1, (n, 16)) - 3]
    ).astype(np.float32)
    docs = [f"saúde hospital vacina atendimento paciente {i % 7}" for i in range(n)] + [
        f"educação escola professor ensino aluno {i % 7}" for i in range(n)
    ]
    params = base_settings.model.model_copy(
        update={
            "hdbscan": base_settings.model.hdbscan.model_copy(
                update={"min_cluster_size": 10, "min_samples": 3}
            ),
            "vectorizer": base_settings.model.vectorizer.model_copy(update={"min_df": 1}),
            "umap": base_settings.model.umap.model_copy(update={"n_neighbors": 10}),
        }
    )
    model = build_topic_model(params, seed=42)
    topics = fit_topic_model(model, docs, embeddings)
    assert len(set(topics) - {-1}) >= 2
    summary = summarize_topics(model, top_n_words=5)
    assert summary["count"].sum() == len(docs)


def test_fit_rejects_misaligned_inputs(base_settings):
    """docs e embeddings com tamanhos diferentes falham antes do treino."""
    model = build_topic_model(base_settings.model, seed=1)
    with pytest.raises(ValueError):
        fit_topic_model(model, ["a", "b"], np.zeros((3, 4), dtype=np.float32))
