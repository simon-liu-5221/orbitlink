"""Six-factor engagement scoring (AN-02).

Finds the people *driving* discussion, not just the ones commenting most. Pure:
takes the directed interaction graph (from ``graph_builder``), returns
dataclasses.

Pipeline (kept as three testable steps):

1. :func:`raw_metrics`      graph -> six raw numbers per node
2. :func:`normalize`        each metric min-max scaled to [0, 1] across the network
3. :func:`weighted_score`   weighted sum, linearly mapped to [1, 10]

The weights are heuristic and **not empirically calibrated** — carried over from
the original FYP. :func:`weight_sensitivity` quantifies how much the ranking
depends on them (see ``docs/algorithm-validation.md`` §2.1).
"""

from __future__ import annotations

import math
from collections.abc import Mapping

import networkx as nx
from scipy.stats import spearmanr

from app.analysis.types import (
    ENGAGEMENT_METRICS,
    EngagementResult,
    NodeEngagement,
    NodeId,
    WeightSensitivity,
)

#: Default metric weights. MUST sum to 1.0 (AN-02 AC-2). Defined in this module
#: per the spec.
DEFAULT_WEIGHTS: dict[str, float] = {
    "engagement": 0.25,
    "consistency": 0.20,
    "network": 0.20,
    "quality": 0.15,
    "activity": 0.10,
    "responsiveness": 0.10,
}

_SCORE_MIN = 1.0
_SCORE_MAX = 10.0


def raw_metrics(graph: nx.DiGraph) -> dict[NodeId, dict[str, float]]:
    """Compute the six raw metrics for every node.

    Node attributes used (from ``graph_builder``): ``comment_count``,
    ``like_count``, ``replies_received``, ``active_days``, ``avg_text_length``.
    Graph attribute: ``period_days`` (defaults to 1).
    """
    period_days = max(int(graph.graph.get("period_days", 1)), 1)
    out_strength = _out_strength(graph)

    metrics: dict[NodeId, dict[str, float]] = {}
    for node, data in graph.nodes(data=True):
        comments = max(int(data.get("comment_count", 0)), 0)
        likes = float(data.get("like_count", 0))
        replies_received = float(data.get("replies_received", 0))
        active_days = float(data.get("active_days", 0))
        avg_length = float(data.get("avg_text_length", 0.0))
        replies_made = float(out_strength.get(node, 0.0))
        avg_replies_per_comment = replies_received / comments if comments else 0.0

        metrics[node] = {
            "engagement": replies_received + likes,
            "consistency": active_days / period_days,
            "network": float(_incident_strength(graph, node)),
            "quality": math.log1p(max(avg_length, 0.0)) * avg_replies_per_comment,
            "activity": float(comments),
            "responsiveness": replies_made / comments if comments else 0.0,
        }
    return metrics


def normalize(raw: dict[NodeId, dict[str, float]]) -> dict[NodeId, dict[str, float]]:
    """Min-max scale each metric to [0, 1] across the network.

    When every node shares a value for a metric (max == min) that metric is set
    to 0.5 for all nodes — no division by zero (AN-02 exception flow).
    """
    if not raw:
        return {}
    normalized: dict[NodeId, dict[str, float]] = {node: {} for node in raw}
    for metric in ENGAGEMENT_METRICS:
        values = [node_metrics[metric] for node_metrics in raw.values()]
        lo, hi = min(values), max(values)
        span = hi - lo
        for node, node_metrics in raw.items():
            normalized[node][metric] = 0.5 if span == 0 else (node_metrics[metric] - lo) / span
    return normalized


def weighted_score(
    normalized: dict[NodeId, dict[str, float]],
    weights: Mapping[str, float],
) -> dict[NodeId, float]:
    """Weighted sum of normalised metrics, linearly mapped to [1, 10].

    ``weights`` is normalised to sum to 1 internally, so any set of non-negative
    weights keeps scores in range (AN-02 AC-7).
    """
    applied = _normalized_weights(weights)
    scores: dict[NodeId, float] = {}
    for node, node_metrics in normalized.items():
        combined = sum(applied[metric] * node_metrics[metric] for metric in ENGAGEMENT_METRICS)
        scores[node] = _SCORE_MIN + (_SCORE_MAX - _SCORE_MIN) * combined
    return scores


def score_engagement(
    graph: nx.DiGraph,
    *,
    weights: Mapping[str, float] = DEFAULT_WEIGHTS,
    top_n: int = 5,
) -> EngagementResult:
    """Full pipeline: raw metrics -> normalise -> weight -> rank."""
    raw = raw_metrics(graph)
    normalized = normalize(raw)
    scores = weighted_score(normalized, weights)
    applied = _normalized_weights(weights)

    ordered = sorted(scores, key=lambda node: (-scores[node], str(node)))
    rankings = [
        NodeEngagement(
            node_id=node,
            score=round(scores[node], 6),
            rank=index + 1,
            breakdown={m: round(normalized[node][m], 6) for m in ENGAGEMENT_METRICS},
            raw={m: round(raw[node][m], 6) for m in ENGAGEMENT_METRICS},
        )
        for index, node in enumerate(ordered)
    ]
    return EngagementResult(rankings=rankings, top=rankings[:top_n], weights=applied)


def weight_sensitivity(
    graph: nx.DiGraph,
    *,
    weights: Mapping[str, float] = DEFAULT_WEIGHTS,
    delta: float = 0.1,
    top_n: int = 5,
) -> WeightSensitivity:
    """Perturb each weight by ±``delta`` (relative) and measure ranking drift.

    For each metric: does the top-N set survive, and what is the worst-case
    Spearman correlation of the full ranking against the baseline.
    """
    baseline = score_engagement(graph, weights=weights, top_n=top_n)
    baseline_order = [n.node_id for n in baseline.rankings]
    baseline_rank = {node: i for i, node in enumerate(baseline_order)}
    baseline_top = {n.node_id for n in baseline.top}

    top_stable: dict[str, bool] = {}
    spearman: dict[str, float] = {}
    for metric in ENGAGEMENT_METRICS:
        stable = True
        worst_rho = 1.0
        for factor in (1.0 - delta, 1.0 + delta):
            perturbed = dict(weights)
            perturbed[metric] = weights[metric] * factor
            result = score_engagement(graph, weights=perturbed, top_n=top_n)
            stable = stable and {n.node_id for n in result.top} == baseline_top
            if len(baseline_order) > 1:
                perturbed_rank = [baseline_rank[n.node_id] for n in result.rankings]
                rho = float(spearmanr(list(range(len(perturbed_rank))), perturbed_rank).statistic)
                worst_rho = min(worst_rho, rho)
        top_stable[metric] = stable
        spearman[metric] = round(worst_rho, 4)
    return WeightSensitivity(delta=delta, top_stable=top_stable, spearman=spearman)


def _normalized_weights(weights: Mapping[str, float]) -> dict[str, float]:
    missing = set(ENGAGEMENT_METRICS) - set(weights)
    if missing:
        raise ValueError(f"weights missing metrics: {sorted(missing)}")
    if any(weights[m] < 0 for m in ENGAGEMENT_METRICS):
        raise ValueError("weights must be non-negative")
    total = sum(weights[m] for m in ENGAGEMENT_METRICS)
    if total <= 0:
        raise ValueError("weights must sum to a positive number")
    return {m: weights[m] / total for m in ENGAGEMENT_METRICS}


def _incident_strength(graph: nx.DiGraph, node: NodeId) -> float:
    return float(graph.degree(node, weight="weight"))


def _out_strength(graph: nx.DiGraph) -> dict[NodeId, float]:
    return {node: float(strength) for node, strength in graph.out_degree(weight="weight")}
