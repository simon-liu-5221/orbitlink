"""Community detection with multi-resolution Louvain (AN-01).

Public entry point: :func:`detect_communities`.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

import networkx as nx
import numpy as np
from networkx.algorithms.community import louvain_communities, modularity

from app.analysis import centrality
from app.analysis.graph_builder import to_undirected_weighted
from app.analysis.types import CommunityDetectionResult, CommunityMetrics, NodeId

logger = logging.getLogger(__name__)

DEFAULT_RESOLUTIONS: tuple[float, ...] = (0.5, 1.0, 1.5, 2.0)
WEAK_MODULARITY_THRESHOLD = 0.3
BRIDGE_PERCENTILE = 90.0
MIN_NODES = 3
MIN_EDGES = 2

Partition = list[set[NodeId]]


def detect_communities(
    graph: nx.Graph | nx.DiGraph,
    *,
    resolutions: Sequence[float] = DEFAULT_RESOLUTIONS,
    seed: int = 42,
    weak_modularity_threshold: float = WEAK_MODULARITY_THRESHOLD,
    betweenness_k_threshold: int = centrality.DEFAULT_K_THRESHOLD,
    bridge_percentile: float = BRIDGE_PERCENTILE,
) -> CommunityDetectionResult:
    """Detect communities and compute per-community metrics.

    The input may be the directed interaction graph or an already-undirected
    graph. Node attributes ``comment_count`` / ``like_count`` / ``sentiment``
    (all optional) feed the community metrics.
    """
    undirected = (
        to_undirected_weighted(graph) if graph.is_directed() else _as_weighted_undirected(graph)
    )

    if undirected.number_of_nodes() < MIN_NODES or undirected.number_of_edges() < MIN_EDGES:
        return CommunityDetectionResult(insufficient_data=True)

    partition, resolution_used, best_modularity = _best_partition(undirected, resolutions, seed)
    ordered = _order_partition(partition)

    betweenness_scores, approximated = centrality.betweenness(
        undirected, k_threshold=betweenness_k_threshold, seed=seed
    )
    bridge_users = _bridge_users(betweenness_scores, bridge_percentile)

    node_communities: dict[NodeId, int] = {
        node: index for index, community in enumerate(ordered) for node in community
    }
    metrics = [
        _community_metrics(index, members, graph, undirected, bridge_users)
        for index, members in enumerate(ordered)
    ]

    return CommunityDetectionResult(
        node_communities=node_communities,
        communities=metrics,
        modularity=round(float(best_modularity), 6),
        resolution_used=float(resolution_used),
        weak_structure=best_modularity < weak_modularity_threshold,
        approximated=approximated,
    )


def _as_weighted_undirected(graph: nx.Graph) -> nx.Graph:
    undirected: nx.Graph = nx.Graph()
    undirected.add_nodes_from(graph.nodes(data=True))
    for source, target, data in graph.edges(data=True):
        undirected.add_edge(source, target, weight=data.get("weight", 1))
    return undirected


def _sweep_resolutions(
    graph: nx.Graph, resolutions: Sequence[float], seed: int
) -> list[tuple[Partition, float, float]]:
    """One Louvain run per resolution, each scored by standard (γ=1) modularity."""
    results: list[tuple[Partition, float, float]] = []
    for resolution in resolutions:
        communities = louvain_communities(graph, weight="weight", resolution=resolution, seed=seed)
        quality = modularity(graph, communities, weight="weight")
        results.append(([set(c) for c in communities], float(resolution), float(quality)))
    return results


def _best_partition(
    graph: nx.Graph, resolutions: Sequence[float], seed: int
) -> tuple[Partition, float, float]:
    try:
        candidates = _sweep_resolutions(graph, resolutions, seed)
        if not candidates:
            raise ValueError("no resolutions supplied")
        return max(candidates, key=lambda item: item[2])
    except Exception:
        logger.warning(
            "resolution optimisation failed; falling back to resolution=1.0", exc_info=True
        )
        communities = louvain_communities(graph, weight="weight", resolution=1.0, seed=seed)
        quality = float(modularity(graph, communities, weight="weight"))
        return [set(c) for c in communities], 1.0, quality


def _order_partition(partition: Partition) -> list[list[NodeId]]:
    """Deterministic community ordering: larger first, then lowest member id."""
    return [
        sorted(community, key=_sort_key)
        for community in sorted(
            partition, key=lambda c: (-len(c), _sort_key(min(c, key=_sort_key)))
        )
    ]


def _sort_key(node: NodeId) -> str:
    return str(node)


def _bridge_users(betweenness_scores: dict[NodeId, float], percentile: float) -> set[NodeId]:
    positive = [score for score in betweenness_scores.values() if score > 0]
    if not positive:
        return set()
    cutoff = float(np.percentile(positive, percentile))
    return {node for node, score in betweenness_scores.items() if score > 0 and score >= cutoff}


def _community_metrics(
    community_id: int,
    members: list[NodeId],
    original: nx.Graph | nx.DiGraph,
    undirected: nx.Graph,
    bridge_users: set[NodeId],
) -> CommunityMetrics:
    member_set = set(members)
    sub_undirected = undirected.subgraph(member_set)
    sub_original = original.subgraph(member_set)

    if sub_original.number_of_edges() > 0:
        ranked = centrality.pagerank(sub_original)
        top_influencers = [
            node for node, _ in sorted(ranked.items(), key=lambda kv: (-kv[1], _sort_key(kv[0])))
        ][:3]
    else:
        top_influencers = members[:3]

    sentiments = [
        undirected.nodes[node]["sentiment"]
        for node in member_set
        if undirected.nodes[node].get("sentiment") is not None
    ]
    avg_sentiment = float(np.mean(sentiments)) if sentiments else None

    cohesion = (
        float(nx.average_clustering(sub_undirected))
        if sub_undirected.number_of_nodes() > 2
        else 0.0
    )

    return CommunityMetrics(
        community_id=community_id,
        size=len(member_set),
        total_comments=sum(int(undirected.nodes[n].get("comment_count", 0)) for n in member_set),
        total_likes=sum(int(undirected.nodes[n].get("like_count", 0)) for n in member_set),
        avg_sentiment=avg_sentiment,
        top_influencers=top_influencers,
        bridge_users=sorted((n for n in member_set if n in bridge_users), key=_sort_key),
        cohesion=round(cohesion, 6),
        density=round(float(nx.density(sub_undirected)), 6),
    )
