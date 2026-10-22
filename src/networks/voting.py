"""Rede de alinhamento de votos entre partidos."""

import networkx as nx
import polars as pl

from constants.columns import VOTE_NO, VOTE_YES


def compute_party_positions(votes: pl.DataFrame, min_members: int) -> pl.DataFrame:
    """Define a posição (Sim/Não) de cada partido em cada votação pela maioria dos votos.

    Votos diferentes de Sim/Não (abstenção, obstrução, artigo 17) são ignorados.
    Partidos com menos de ``min_members`` votos Sim/Não na votação, ou com empate,
    ficam sem posição naquela votação.

    Parameters
    ----------
    votes : pl.DataFrame
        Tabela silver de votos (``voting_id``, ``party``, ``vote``).
    min_members : int
        Mínimo de votos Sim/Não do partido na votação.

    Returns
    -------
    pl.DataFrame
        Colunas ``voting_id``, ``party`` e ``position``.

    Examples
    --------
    >>> compute_party_positions(votes, min_members=3).columns
    ['voting_id', 'party', 'position']
    """
    return (
        votes.filter(pl.col("vote").is_in([VOTE_YES, VOTE_NO]) & pl.col("party").is_not_null())
        .group_by("voting_id", "party")
        .agg(
            (pl.col("vote") == VOTE_YES).sum().alias("yes"),
            (pl.col("vote") == VOTE_NO).sum().alias("no"),
        )
        .filter((pl.col("yes") + pl.col("no") >= min_members) & (pl.col("yes") != pl.col("no")))
        .select(
            "voting_id",
            "party",
            pl.when(pl.col("yes") > pl.col("no"))
            .then(pl.lit(VOTE_YES))
            .otherwise(pl.lit(VOTE_NO))
            .alias("position"),
        )
    )


def build_party_alignment_graph(
    positions: pl.DataFrame, min_common_votings: int, min_edge_weight: float
) -> nx.Graph:
    """Constrói a rede de partidos ponderada pela taxa de votos alinhados.

    O peso da aresta é a fração de votações, entre as que ambos os partidos
    tiveram posição, em que votaram do mesmo lado.

    Parameters
    ----------
    positions : pl.DataFrame
        Saída de :func:`compute_party_positions`.
    min_common_votings : int
        Mínimo de votações em comum para criar a aresta.
    min_edge_weight : float
        Alinhamento mínimo (0 a 1) para manter a aresta.

    Returns
    -------
    nx.Graph
        Grafo não direcionado; aresta com ``weight`` (alinhamento) e ``common_votings``.

    Raises
    ------
    ValueError
        Se ``min_edge_weight`` estiver fora de [0, 1].
    """
    if not 0 <= min_edge_weight <= 1:
        raise ValueError("min_edge_weight deve estar entre 0 e 1")
    graph = nx.Graph()
    graph.add_nodes_from(positions["party"].unique().to_list())
    pairs = (
        positions.join(positions, on="voting_id", suffix="_b")
        .filter(pl.col("party") < pl.col("party_b"))
        .group_by("party", "party_b")
        .agg(
            pl.len().alias("common_votings"),
            (pl.col("position") == pl.col("position_b")).sum().alias("agreements"),
        )
        .with_columns((pl.col("agreements") / pl.col("common_votings")).alias("weight"))
        .filter(
            (pl.col("common_votings") >= min_common_votings) & (pl.col("weight") >= min_edge_weight)
        )
    )
    for row in pairs.iter_rows(named=True):
        graph.add_edge(
            row["party"],
            row["party_b"],
            weight=row["weight"],
            common_votings=row["common_votings"],
        )
    return graph
