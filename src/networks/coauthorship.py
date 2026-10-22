"""Rede de coautoria de proposições entre deputados."""

from collections import Counter
from itertools import combinations

import networkx as nx
import polars as pl


def build_coauthorship_graph(authors: pl.DataFrame, max_authors: int) -> nx.Graph:
    """Constrói a rede de coautoria: arestas ponderadas pelo nº de proposições em comum.

    Proposições com mais de ``max_authors`` autores (ex.: PECs de bancada) são
    ignoradas nas arestas, pois geram cliques que dominam a estrutura da rede;
    seus autores permanecem como nós.

    Parameters
    ----------
    authors : pl.DataFrame
        Tabela silver de autoria (``proposition_id``, ``deputy_id``).
    max_authors : int
        Máximo de autores para uma proposição contribuir com arestas.

    Returns
    -------
    nx.Graph
        Grafo não direcionado; aresta com atributo ``weight`` (proposições em comum).

    Raises
    ------
    ValueError
        Se ``max_authors`` for menor que 2.

    Examples
    --------
    >>> graph = build_coauthorship_graph(authors, max_authors=30)
    >>> graph.number_of_nodes() >= 0
    True
    """
    if max_authors < 2:
        raise ValueError("max_authors deve ser pelo menos 2")
    graph = nx.Graph()
    graph.add_nodes_from(authors["deputy_id"].unique().to_list())
    grouped = authors.group_by("proposition_id").agg(pl.col("deputy_id").unique().sort())
    weights: Counter[tuple[int, int]] = Counter()
    for deputy_ids in grouped["deputy_id"].to_list():
        if 2 <= len(deputy_ids) <= max_authors:
            weights.update(combinations(deputy_ids, 2))
    graph.add_weighted_edges_from((a, b, w) for (a, b), w in weights.items())
    return graph


def annotate_nodes(graph: nx.Graph, deputies: pl.DataFrame) -> nx.Graph:
    """Anexa partido e UF (da tabela silver de deputados) como atributos dos nós.

    Parameters
    ----------
    graph : nx.Graph
        Grafo cujos nós são ``deputy_id``.
    deputies : pl.DataFrame
        Tabela silver de deputados.

    Returns
    -------
    nx.Graph
        O mesmo grafo, modificado in-place.
    """
    lookup = {
        row["deputy_id"]: {"party": row["party"], "state": row["state"]}
        for row in deputies.select("deputy_id", "party", "state").iter_rows(named=True)
    }
    nx.set_node_attributes(graph, {n: lookup[n] for n in graph.nodes if n in lookup})
    return graph
