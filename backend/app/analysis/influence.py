"""Influencer ranking (AN-04).

Blends PageRank, betweenness and weighted degree into one influence score, so
the people holding the conversation together surface above those who merely post
a lot. Pure: builds on :mod:`app.analysis.centrality`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import networkx as nx

from app.analysis import centrality
from app.analysis.types import NodeId

#: Blend weights — PageRank leads (steady influence), betweenness next (brokerage),
#: raw reach last. Renormalised internally, so any non-negative set works.
DEFAULT_WEIGHTS: dict[str, float] = {"pagerank": 0.5, "betweenness": 0.3, "degree": 0.2}


@dataclass(frozen=True)
class Influencer:
    node_id: NodeId
    rank: int
    #: Blended score in [0, 1].
    influence_score: float
    pagerank: float
    betweenness: float
    weighted_degree: float


@dataclass(frozen=True)
class InfluenceResult:
    ranking: list[Influencer]
    #: Betweenness was estimated from a pivot sample (large graph).
    approximated: bool


def rank_influencers(
    graph: nx.Graph | nx.DiGraph,
    *,
    weights: Mapping[str, float] = DEFAULT_WEIGHTS,
    betweenness_k_threshold: int = centrality.DEFAULT_K_THRESHOLD,
    seed: int = 42,
    top_n: int | None = None,
) -> InfluenceResult:
    applied = _normalized_weights(weights)
    nodes = list(graph.nodes())
    if not nodes:
        return InfluenceResult(ranking=[], approximated=False)

    pagerank = centrality.pagerank(graph)
    betweenness, approximated = centrality.betweenness(
        graph, k_threshold=betweenness_k_threshold, seed=seed
    )
    degree = centrality.weighted_degree_centrality(graph)

    components = {
        "pagerank": _minmax([pagerank.get(n, 0.0) for n in nodes]),
        "betweenness": _minmax([betweenness.get(n, 0.0) for n in nodes]),
        "degree": _minmax([degree.get(n, 0.0) for n in nodes]),
    }
    scores = {
        node: applied["pagerank"] * components["pagerank"][i]
        + applied["betweenness"] * components["betweenness"][i]
        + applied["degree"] * components["degree"][i]
        for i, node in enumerate(nodes)
    }

    ordered = sorted(nodes, key=lambda n: (-scores[n], str(n)))
    ranking = [
        Influencer(
            node_id=node,
            rank=index + 1,
            influence_score=round(float(scores[node]), 6),
            pagerank=round(float(pagerank.get(node, 0.0)), 6),
            betweenness=round(float(betweenness.get(node, 0.0)), 6),
            weighted_degree=round(float(degree.get(node, 0.0)), 6),
        )
        for index, node in enumerate(ordered)
    ]
    if top_n is not None:
        ranking = ranking[:top_n]
    return InfluenceResult(ranking=ranking, approximated=approximated)


def _minmax(values: Sequence[float]) -> list[float]:
    lo, hi = min(values), max(values)
    span = hi - lo
    return [0.5 if span == 0 else (v - lo) / span for v in values]


def _normalized_weights(weights: Mapping[str, float]) -> dict[str, float]:
    keys = ("pagerank", "betweenness", "degree")
    missing = set(keys) - set(weights)
    if missing:
        raise ValueError(f"influence weights missing: {sorted(missing)}")
    if any(weights[k] < 0 for k in keys):
        raise ValueError("influence weights must be non-negative")
    total = sum(weights[k] for k in keys)
    if total <= 0:
        raise ValueError("influence weights must sum to a positive number")
    return {k: weights[k] / total for k in keys}
