"""Testes de integração das etapas preprocess, networks e evaluate (sem o extra nlp)."""

import polars as pl
import pytest

from config.settings import Settings
from ingestion.runner import run_ingestion
from pipelines import workflow
from storage.parquet import read_parquet, write_parquet

pytestmark = pytest.mark.integration


def test_ingest_then_preprocess_writes_validated_silver(tmp_settings, fake_client):
    """Bronze simulada → silver validada para as cinco tabelas."""
    run_ingestion(tmp_settings, client=fake_client)
    workflow.run_preprocess(tmp_settings)
    silver = tmp_settings.paths.silver
    for name in ("deputies", "propositions", "authors", "votes", "speeches"):
        assert read_parquet(silver / f"{name}.parquet").height == 1
    assert "email" not in read_parquet(silver / "deputies.parquet").columns


def test_preprocess_skips_missing_bronze(tmp_settings):
    """Sem bronze, a etapa não falha: apenas pula as fontes ausentes."""
    workflow.run_preprocess(tmp_settings)
    assert not tmp_settings.paths.silver.exists()


@pytest.fixture
def networks_settings(tmp_settings: Settings) -> Settings:
    """Configuração com limiares baixos para dados sintéticos pequenos."""
    networks = tmp_settings.networks.model_copy(
        update={
            "min_party_members_per_vote": 1,
            "min_common_votings": 2,
            "min_edge_weight": 0.0,
        }
    )
    return tmp_settings.model_copy(update={"networks": networks})


def test_run_networks_writes_nodes_edges_and_figures(networks_settings):
    """Gera nós, arestas e figuras das duas redes a partir de silver sintética."""
    silver = networks_settings.paths.silver
    write_parquet(
        pl.DataFrame(
            {
                "deputy_id": [1, 2, 3],
                "name": ["Ana", "Bia", "Caio"],
                "party": ["A", "B", "C"],
                "state": ["SP", "RJ", "MG"],
                "legislature_id": [57, 57, 57],
            }
        ),
        silver / "deputies.parquet",
    )
    write_parquet(
        pl.DataFrame({"proposition_id": [1, 1, 2, 2, 2], "deputy_id": [1, 2, 1, 2, 3]}),
        silver / "authors.parquet",
    )
    rows = [
        (f"V{v}", d, party, vote)
        for v in (1, 2, 3)
        for d, party, vote in [
            (1, "A", "Sim"),
            (2, "B", "Sim" if v < 3 else "Não"),
            (3, "C", "Não"),
        ]
    ]
    write_parquet(
        pl.DataFrame(rows, schema=["voting_id", "deputy_id", "party", "vote"], orient="row"),
        silver / "votes.parquet",
    )

    workflow.run_networks(networks_settings)

    gold = networks_settings.paths.gold
    nodes = read_parquet(gold / "network_coauthorship_nodes.parquet")
    assert nodes.height == 3
    assert "name" in nodes.columns
    assert read_parquet(gold / "network_party_alignment_edges.parquet").height >= 1
    assert (networks_settings.paths.figures / "coautoria_strength.png").is_file()
    assert (networks_settings.paths.figures / "alinhamento_strength.svg").is_file()


def test_run_evaluate_creates_sample_then_summarizes_labels(tmp_settings):
    """Primeira execução cria a amostra; após rotular, a segunda gera o resumo.

    Os rótulos já preenchidos não são sobrescritos.
    """
    gold = tmp_settings.paths.gold
    write_parquet(
        pl.DataFrame(
            {
                "doc_id": [str(i) for i in range(10)],
                "topic": [0] * 5 + [1] * 5,
                "period": [None] * 10,
                "text": [f"texto {i}" for i in range(10)],
            },
            schema_overrides={"period": pl.Date},
        ),
        gold / "doc_topics_propositions.parquet",
    )
    write_parquet(
        pl.DataFrame({"topic": [0, 1], "name": ["0_saude", "1_educacao"]}),
        gold / "topics_propositions.parquet",
    )

    sample_path = workflow.run_evaluate(tmp_settings, "propositions")
    assert sample_path.is_file()
    unlabeled = pl.read_csv(sample_path)
    assert unlabeled.height > 0

    workflow.run_evaluate(tmp_settings, "propositions")  # sem rótulos: não gera resumo
    summary_path = sample_path.with_name("review_summary_propositions.csv")
    assert not summary_path.exists()

    unlabeled.with_columns(pl.lit(1).alias("is_coherent")).write_csv(sample_path)
    workflow.run_evaluate(tmp_settings, "propositions")
    assert summary_path.is_file()
    assert pl.read_csv(sample_path)["is_coherent"].sum() == unlabeled.height


def test_unknown_corpus_is_rejected(tmp_settings):
    """Corpus desconhecido falha antes de qualquer processamento."""
    with pytest.raises(ValueError, match="Corpus"):
        workflow.run_evaluate(tmp_settings, "inexistente")
    with pytest.raises(ValueError, match="Corpus"):
        workflow.run_topics(tmp_settings, "inexistente")
