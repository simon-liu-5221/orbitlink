"""Centrality measures over the interaction graph.

Thin, well-behaved wrappers around ``networkx`` so callers get consistent
handling of empty/tiny graphs and large-graph betweenness sampling (AN-01).
"""

from __future__ import annotations

import networkx as nx

#: Above this node count, betweenness is estimated from a pivot sample.
DEFAULT_K_THRESHOLD = 2000
#: Sample size used when estimating betweenness on large graphs.
DEFAULT_K = 500


def pagerank(
    graph: nx.Graph | nx.DiGraph, *, weight: str | None = "weight", alpha: float = 0.85
) -> dict[str, float]:
    """PageRank per node. Empty graph -> empty dict."""
    if graph.number_of_nodes() == 0:
        return {}
    scores: dict[str, float] = dict(nx.pagerank(graph, alpha=alpha, weight=weight))
    return scores


def weighted_degree_centrality(
    graph: nx.Graph | nx.DiGraph, *, weight: str | None = "weight"
) -> dict[str, float]:
    """Degree centrality using edge weights, normalised by ``n - 1``.

    Matches ``networkx.degree_centrality`` when every edge weight is 1.
    """
    n = graph.number_of_nodes()
    if n <= 1:
        return dict.fromkeys(graph.nodes(), 0.0)
    norm = 1.0 / (n - 1)
    return {node: float(degree) * norm for node, degree in graph.degree(weight=weight)}


def betweenness(
    graph: nx.Graph | nx.DiGraph,
    *,
    k_threshold: int = DEFAULT_K_THRESHOLD,
    k: int = DEFAULT_K,
    seed: int = 42,
    weight: str | None = None,
) -> tuple[dict[str, float], bool]:
    """Betweenness centrality. Returns ``(scores, approximated)``.

    ``approximated`` is ``True`` when the graph exceeded ``k_threshold`` nodes and
    the result was estimated from ``k`` sampled pivots. Computed unweighted by
    default: edge weights here are interaction *counts*, not path lengths.
    """
    n = graph.number_of_nodes()
    if n <= 2:
        return dict.fromkeys(graph.nodes(), 0.0), False
    if n > k_threshold:
        sample = min(k, n)
        approx: dict[str, float] = dict(
            nx.betweenness_centrality(graph, k=sample, seed=seed, weight=weight, normalized=True)
        )
        return approx, True
    exact: dict[str, float] = dict(nx.betweenness_centrality(graph, weight=weight, normalized=True))
    return exact, False
