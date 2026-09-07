"""Shared fixtures for the analysis-layer unit tests.

Everything here is offline and deterministic: hand-built graphs, plus the
standard benchmark graphs (Zachary, LFR, Erdős–Rényi) with fixed seeds.
"""

from __future__ import annotations

import networkx as nx
import pytest

# LFR params proven stable + deterministic on this toolchain (networkx 3.6):
# 7 planted communities, mu=0.1, recovered at NMI 1.0 by a correct Louvain.
LFR_KWARGS = {
    "n": 500,
    "tau1": 3,
    "tau2": 1.5,
    "mu": 0.1,
    "average_degree": 18,
    "min_community": 30,
    "seed": 42,
    "max_iters": 5000,
}


@pytest.fixture
def karate_graph() -> nx.Graph:
    """Zachary's karate club — the canonical community-detection sanity check."""
    return nx.karate_club_graph()


@pytest.fixture
def lfr_graph() -> nx.Graph:
    """LFR benchmark with known ground truth in each node's ``community`` attr."""
    try:
        graph = nx.LFR_benchmark_graph(**LFR_KWARGS)
    except nx.ExceededMaxIterations:  # pragma: no cover - toolchain-dependent
        pytest.skip("LFR benchmark generator failed to converge on this toolchain")
    graph.remove_edges_from(nx.selfloop_edges(graph))
    return nx.Graph(graph)


def lfr_ground_truth(graph: nx.Graph) -> dict[int, int]:
    communities = {frozenset(graph.nodes[node]["community"]) for node in graph}
    return {node: index for index, community in enumerate(communities) for node in community}


@pytest.fixture
def random_graph() -> nx.Graph:
    """Erdős–Rényi graph — no community structure by construction."""
    return nx.erdos_renyi_graph(n=120, p=0.15, seed=7)


@pytest.fixture
def two_triangle_graph() -> nx.DiGraph:
    """Two directed triangles joined by a single bridge edge (c -> d).

    Node attributes are hand-chosen so community metrics can be checked by hand:

    community {a, b, c}: comments 5+3+2=10, likes 10+4+0=14, sentiment mean 0.1
    community {d, e, f}: comments 8+1+4=13, likes 20+1+6=27, sentiment mean 0.1
    each triangle: density 1.0, clustering 1.0
    """
    graph: nx.DiGraph = nx.DiGraph()
    attrs: dict[str, dict[str, float]] = {
        "a": {"comment_count": 5, "like_count": 10, "sentiment": 0.5},
        "b": {"comment_count": 3, "like_count": 4, "sentiment": 0.1},
        "c": {"comment_count": 2, "like_count": 0, "sentiment": -0.3},
        "d": {"comment_count": 8, "like_count": 20, "sentiment": 0.9},
        "e": {"comment_count": 1, "like_count": 1, "sentiment": 0.0},
        "f": {"comment_count": 4, "like_count": 6, "sentiment": -0.6},
    }
    for node, data in attrs.items():
        graph.add_node(node, **data)
    for source, target in [
        ("a", "b"),
        ("b", "c"),
        ("c", "a"),
        ("d", "e"),
        ("e", "f"),
        ("f", "d"),
        ("c", "d"),
    ]:
        graph.add_edge(source, target, weight=1)
    return graph
