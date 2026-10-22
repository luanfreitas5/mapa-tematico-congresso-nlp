"""Exportação de grafos para tabelas."""

import networkx as nx
import polars as pl


def export_edges(graph: nx.Graph) -> pl.DataFrame:
    """Converte as arestas de um grafo em uma tabela.

    Parameters
    ----------
    graph : nx.Graph
        Grafo com atributo ``weight`` nas arestas.

    Returns
    -------
    pl.DataFrame
        Colunas ``source``, ``target`` (texto) e ``weight`` (float).

    Examples
    --------
    >>> export_edges(nx.Graph([(1, 2)])).columns
    ['source', 'target', 'weight']
    """
    rows = [
        {"source": str(u), "target": str(v), "weight": float(data.get("weight", 1.0))}
        for u, v, data in graph.edges(data=True)
    ]
    return pl.DataFrame(
        rows, schema={"source": pl.String, "target": pl.String, "weight": pl.Float64}
    )
