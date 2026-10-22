"""Testes das redes: coautoria, alinhamento partidário e centralidades."""

import networkx as nx
import polars as pl
import pytest

from networks.centrality import compute_centrality_table
from networks.coauthorship import annotate_nodes, build_coauthorship_graph
from networks.export import export_edges
from networks.voting import build_party_alignment_graph, compute_party_positions


@pytest.fixture
def authors() -> pl.DataFrame:
    """Autoria sintética: p1=[1,2], p2=[1,2,3], p3=[1,2,3,4] (acima do limite)."""
    rows = [(1, 1), (1, 2), (2, 1), (2, 2), (2, 3), (3, 1), (3, 2), (3, 3), (3, 4)]
    return pl.DataFrame(rows, schema=["proposition_id", "deputy_id"], orient="row")


def test_coauthorship_weights_count_shared_propositions(authors):
    """O peso é o nº de proposições em comum; proposições grandes não geram arestas."""
    graph = build_coauthorship_graph(authors, max_authors=3)
    assert graph.edges[1, 2]["weight"] == 2
    assert graph.edges[1, 3]["weight"] == 1
    assert 4 in graph.nodes
    assert graph.degree(4) == 0


def test_coauthorship_rejects_invalid_limit(authors):
    """max_authors < 2 é inválido."""
    with pytest.raises(ValueError):
        build_coauthorship_graph(authors, max_authors=1)


def test_annotate_nodes_adds_party_and_state(authors):
    """Atributos de partido e UF são anexados aos nós conhecidos."""
    graph = build_coauthorship_graph(authors, max_authors=3)
    deputies = pl.DataFrame({"deputy_id": [1], "party": ["AAA"], "state": ["SP"]})
    annotate_nodes(graph, deputies)
    assert graph.nodes[1] == {"party": "AAA", "state": "SP"}
    assert graph.nodes[2] == {}


@pytest.fixture
def votes() -> pl.DataFrame:
    """Votos: A sempre Sim; B Sim em V1-V2 e Não em V3-V4; C sempre Não."""
    position = {"A": ["Sim"] * 4, "B": ["Sim", "Sim", "Não", "Não"], "C": ["Não"] * 4}
    rows = []
    deputy_id = 1
    for party, party_votes in position.items():
        for index, vote in enumerate(party_votes, start=1):
            rows.append((f"V{index}", deputy_id, party, vote))
            deputy_id += 1
    return pl.DataFrame(rows, schema=["voting_id", "deputy_id", "party", "vote"], orient="row")


def test_party_positions_use_majority_and_ignore_other_votes(votes):
    """Abstenções e empates não geram posição."""
    extra = pl.DataFrame(
        {
            "voting_id": ["V1", "V1"],
            "deputy_id": [100, 101],
            "party": ["D", "D"],
            "vote": ["Abstenção", "Sim"],
        }
    )
    positions = compute_party_positions(pl.concat([votes, extra]), min_members=1)
    d_positions = positions.filter(pl.col("party") == "D")
    assert d_positions["position"].to_list() == ["Sim"]
    assert positions.filter(pl.col("party") == "A").height == 4


def test_party_positions_respect_minimum_members(votes):
    """Partidos com menos votos Sim/Não que o mínimo ficam de fora."""
    assert compute_party_positions(votes, min_members=2).is_empty()


def test_alignment_graph_weights_are_agreement_rates(votes):
    """O peso é a fração de votações com mesma posição; arestas fracas são podadas."""
    positions = compute_party_positions(votes, min_members=1)
    graph = build_party_alignment_graph(positions, min_common_votings=2, min_edge_weight=0.5)
    assert graph.edges["A", "B"]["weight"] == pytest.approx(0.5)
    assert graph.edges["B", "C"]["weight"] == pytest.approx(0.5)
    assert not graph.has_edge("A", "C")
    assert set(graph.nodes) == {"A", "B", "C"}


def test_alignment_graph_rejects_invalid_threshold(votes):
    """Limiar fora de [0, 1] é inválido."""
    positions = compute_party_positions(votes, min_members=1)
    with pytest.raises(ValueError):
        build_party_alignment_graph(positions, 1, 1.5)


def test_centrality_table_has_one_row_per_node_sorted_by_strength(authors):
    """Uma linha por nó, ordenada por força, com todas as métricas."""
    graph = build_coauthorship_graph(authors, max_authors=3)
    table = compute_centrality_table(graph, seed=42)
    assert table.height == graph.number_of_nodes()
    assert table["strength"].to_list() == sorted(table["strength"].to_list(), reverse=True)
    assert {"degree", "betweenness", "eigenvector", "pagerank", "community"} <= set(table.columns)


def test_centrality_table_on_empty_graph_keeps_schema():
    """Grafo vazio devolve tabela vazia com as mesmas colunas."""
    table = compute_centrality_table(nx.Graph())
    assert table.is_empty()
    assert "strength" in table.columns


def test_export_edges_returns_text_endpoints():
    """As arestas exportadas têm extremos em texto e peso numérico."""
    edges = export_edges(nx.Graph([(1, 2, {"weight": 3})]))
    assert edges.rows() == [("1", "2", 3.0)]
