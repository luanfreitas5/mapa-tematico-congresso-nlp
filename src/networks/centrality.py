"""Métricas de centralidade e comunidades de um grafo ponderado."""

import networkx as nx
import polars as pl

_COLUMNS = {
    "node": pl.String,
    "degree": pl.Int64,
    "strength": pl.Float64,
    "betweenness": pl.Float64,
    "eigenvector": pl.Float64,
    "pagerank": pl.Float64,
    "community": pl.Int64,
}


def _add_distance(graph: nx.Graph) -> nx.Graph:
    """Copia o grafo e define ``distance = 1 / weight`` em cada aresta."""
    weighted = graph.copy()
    for _, _, data in weighted.edges(data=True):
        data["distance"] = 1.0 / data["weight"] if data.get("weight") else 1.0
    return weighted


def _compute_eigenvector(graph: nx.Graph) -> dict:
    """Calcula a centralidade de autovetor; zera os nós se não convergir."""
    try:
        return nx.eigenvector_centrality_numpy(graph, weight="weight")
    except (nx.NetworkXException, RuntimeError):
        return dict.fromkeys(graph.nodes, 0.0)


def compute_centrality_table(graph: nx.Graph, seed: int = 42) -> pl.DataFrame:
    """Calcula centralidades e comunidades (Louvain) de cada nó.

    ``strength`` é o grau ponderado. Para a intermediação, a distância da aresta é
    ``1 / weight`` (pesos maiores = nós mais próximos). Se o autovetor não
    convergir, a coluna ``eigenvector`` fica em zero.

    Parameters
    ----------
    graph : nx.Graph
        Grafo com atributo ``weight`` nas arestas.
    seed : int, optional
        Semente do Louvain, by default 42.

    Returns
    -------
    pl.DataFrame
        Uma linha por nó, ordenada por ``strength`` decrescente. ``node`` é
        sempre texto (id do deputado ou sigla do partido).

    Examples
    --------
    >>> compute_centrality_table(nx.path_graph(3)).height
    3
    """
    if graph.number_of_nodes() == 0:
        return pl.DataFrame(schema=_COLUMNS)

    weighted = _add_distance(graph)
    eigenvector = _compute_eigenvector(weighted)
    betweenness = nx.betweenness_centrality(weighted, weight="distance")
    pagerank = nx.pagerank(weighted, weight="weight")
    communities = nx.community.louvain_communities(weighted, weight="weight", seed=seed)
    community_of = {
        node: index
        for index, members in enumerate(sorted(communities, key=len, reverse=True))
        for node in members
    }
    degree = dict(weighted.degree())
    strength = dict(weighted.degree(weight="weight"))

    rows = [
        {
            "node": str(node),
            "degree": int(degree[node]),
            "strength": float(strength[node]),
            "betweenness": float(betweenness[node]),
            "eigenvector": float(eigenvector[node]),
            "pagerank": float(pagerank[node]),
            "community": community_of[node],
        }
        for node in weighted.nodes
    ]
    return pl.DataFrame(rows, schema=_COLUMNS).sort("strength", descending=True)
