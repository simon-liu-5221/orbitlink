"""AN-02 acceptance tests — one test per acceptance criterion."""

from __future__ import annotations

import networkx as nx
import pytest

from app.analysis.engagement import (
    DEFAULT_WEIGHTS,
    normalize,
    raw_metrics,
    score_engagement,
    weight_sensitivity,
    weighted_score,
)
from app.analysis.types import ENGAGEMENT_METRICS


def _node(**overrides: float) -> dict[str, float]:
    base = {
        "comment_count": 1,
        "like_count": 0,
        "replies_received": 0,
        "active_days": 1,
        "avg_text_length": 0.0,
    }
    base.update(overrides)
    return base


def _graph(
    nodes: dict[str, dict[str, float]], edges: list[tuple[str, str, int]], *, period_days: int = 10
) -> nx.DiGraph:
    graph: nx.DiGraph = nx.DiGraph()
    graph.graph["period_days"] = period_days
    for name, attrs in nodes.items():
        graph.add_node(name, **attrs)
    for source, target, weight in edges:
        graph.add_edge(source, target, weight=weight)
    return graph


def test_ac2_default_weights_sum_to_one() -> None:
    """AC-2: sum(DEFAULT_WEIGHTS.values()) == 1.0 within 1e-9."""
    assert sum(DEFAULT_WEIGHTS.values()) == pytest.approx(1.0, abs=1e-9)
    assert set(DEFAULT_WEIGHTS) == set(ENGAGEMENT_METRICS)


def test_ac1_all_scores_within_one_to_ten() -> None:
    """AC-1: every score lands in the closed interval [1.0, 10.0]."""
    graph = _graph(
        {
            "a": _node(
                comment_count=10,
                like_count=40,
                replies_received=12,
                active_days=8,
                avg_text_length=60,
            ),
            "b": _node(
                comment_count=3,
                like_count=1,
                replies_received=9,
                active_days=2,
                avg_text_length=120,
            ),
            "c": _node(
                comment_count=1, like_count=0, replies_received=0, active_days=1, avg_text_length=5
            ),
            "d": _node(
                comment_count=6, like_count=6, replies_received=2, active_days=4, avg_text_length=30
            ),
        },
        [("b", "a", 3), ("d", "b", 2), ("a", "d", 1)],
    )
    result = score_engagement(graph)
    assert all(1.0 <= node.score <= 10.0 for node in result.rankings)
    assert [n.rank for n in result.rankings] == [1, 2, 3, 4]


def test_ac3_hand_computed_scores_match_to_four_decimals() -> None:
    """AC-3: three nodes with known raw metrics -> totals match a hand calc."""
    raw = {
        "x": {
            "engagement": 10.0,
            "consistency": 1.0,
            "network": 4.0,
            "quality": 2.0,
            "activity": 10.0,
            "responsiveness": 0.5,
        },
        "y": {
            "engagement": 5.0,
            "consistency": 0.5,
            "network": 2.0,
            "quality": 1.0,
            "activity": 5.0,
            "responsiveness": 0.25,
        },
        "z": {
            "engagement": 0.0,
            "consistency": 0.0,
            "network": 0.0,
            "quality": 0.0,
            "activity": 0.0,
            "responsiveness": 0.0,
        },
    }
    # each metric is min 0..max -> normalised = value / max. x -> all 1.0, z -> all 0.0,
    # y -> all 0.5. score = 1 + 9 * sum(w * norm).
    scores = weighted_score(normalize(raw), DEFAULT_WEIGHTS)
    assert scores["x"] == pytest.approx(10.0, abs=1e-4)
    assert scores["y"] == pytest.approx(5.5, abs=1e-4)
    assert scores["z"] == pytest.approx(1.0, abs=1e-4)


def test_ac4_higher_engagement_wins_when_all_else_equal() -> None:
    """AC-4: two nodes differ only in Engagement -> higher one scores higher."""
    common = {"comment_count": 4, "active_days": 3, "avg_text_length": 20, "replies_received": 2}
    graph = _graph(
        {
            "high": _node(**common, like_count=50),
            "low": _node(**common, like_count=0),
            "filler": _node(comment_count=1, like_count=0, replies_received=0, active_days=1),
        },
        [],
    )
    result = score_engagement(graph)
    scores = {n.node_id: n.score for n in result.rankings}
    assert scores["high"] > scores["low"]


def test_ac5_uniform_metric_normalises_to_half_without_dividing_by_zero() -> None:
    """AC-5: every node has the same Activity -> that metric is 0.5 for all."""
    graph = _graph(
        {
            name: _node(comment_count=5, like_count=idx, replies_received=idx)
            for idx, name in enumerate("abcd")
        },
        [],
    )
    normalized = normalize(raw_metrics(graph))
    assert all(node["activity"] == 0.5 for node in normalized.values())


def test_ac6_top_n_returns_actual_count_for_small_network() -> None:
    """AC-6: a 2-node network asked for top 5 returns 2, not padded."""
    graph = _graph(
        {"a": _node(comment_count=3, like_count=2), "b": _node(comment_count=1, like_count=0)},
        [("b", "a", 1)],
    )
    result = score_engagement(graph, top_n=5)
    assert len(result.top) == 2
    assert len(result.rankings) == 2


def test_ac7_custom_weights_change_scores_but_stay_in_range() -> None:
    """AC-7: overriding DEFAULT_WEIGHTS shifts scores, still within [1, 10]."""
    graph = _graph(
        {
            "talker": _node(comment_count=20, like_count=0, replies_received=0, active_days=1),
            "sparker": _node(comment_count=2, like_count=0, replies_received=15, active_days=1),
            "filler": _node(comment_count=1, like_count=0, replies_received=0, active_days=1),
        },
        [],
    )
    default = {n.node_id: n.score for n in score_engagement(graph).rankings}
    activity_heavy = dict(
        DEFAULT_WEIGHTS,
        activity=0.9,
        engagement=0.02,
        consistency=0.02,
        network=0.02,
        quality=0.02,
        responsiveness=0.02,
    )
    tuned = {n.node_id: n.score for n in score_engagement(graph, weights=activity_heavy).rankings}

    assert tuned != default
    assert all(1.0 <= score <= 10.0 for score in tuned.values())
    # weighting activity heavily should lift the high-volume commenter
    assert tuned["talker"] > default["talker"]


def test_ac8_top_entries_carry_all_six_subscores() -> None:
    """AC-8: every top-N entry includes the six-metric breakdown."""
    graph = _graph(
        {name: _node(comment_count=idx + 1, like_count=idx) for idx, name in enumerate("abcdefg")},
        [("b", "a", 2), ("c", "a", 1)],
    )
    result = score_engagement(graph, top_n=5)
    assert len(result.top) == 5
    for entry in result.top:
        assert set(entry.breakdown) == set(ENGAGEMENT_METRICS)
        assert set(entry.raw) == set(ENGAGEMENT_METRICS)


def test_period_zero_days_does_not_divide_by_zero() -> None:
    """Exception flow: period_days coerced to >= 1."""
    graph = _graph({"a": _node(active_days=1), "b": _node(active_days=1)}, [], period_days=0)
    metrics = raw_metrics(graph)
    assert metrics["a"]["consistency"] == 1.0


def test_user_who_never_replies_has_zero_responsiveness_and_is_kept() -> None:
    """Exception flow: Responsiveness = 0, node not dropped."""
    graph = _graph(
        {"a": _node(comment_count=5), "b": _node(comment_count=5)},
        [("a", "b", 2)],  # only a replies
    )
    metrics = raw_metrics(graph)
    assert metrics["b"]["responsiveness"] == 0.0
    assert {n.node_id for n in score_engagement(graph).rankings} == {"a", "b"}


def test_raw_metrics_quality_uses_log_compression() -> None:
    """Implementation note: Quality = log1p(avg_length) * avg_replies_per_comment."""
    import math

    graph = _graph({"a": _node(comment_count=4, replies_received=8, avg_text_length=99)}, [])
    expected = math.log1p(99) * (8 / 4)
    assert raw_metrics(graph)["a"]["quality"] == pytest.approx(expected)


def test_weights_missing_a_metric_raises() -> None:
    graph = _graph({"a": _node(), "b": _node()}, [])
    with pytest.raises(ValueError, match="missing metrics"):
        score_engagement(graph, weights={"engagement": 1.0})


def test_negative_and_zero_total_weights_raise() -> None:
    graph = _graph({"a": _node(), "b": _node()}, [])
    with pytest.raises(ValueError, match="non-negative"):
        score_engagement(
            graph, weights=dict.fromkeys(ENGAGEMENT_METRICS, 0.0) | {"engagement": -1.0}
        )
    with pytest.raises(ValueError, match="positive number"):
        score_engagement(graph, weights=dict.fromkeys(ENGAGEMENT_METRICS, 0.0))


def test_normalize_empty_input_returns_empty() -> None:
    assert normalize({}) == {}
    assert score_engagement(nx.DiGraph()).rankings == []


def test_weight_sensitivity_reports_all_metrics() -> None:
    """weight_sensitivity returns a stable/spearman entry per metric."""
    graph = _graph(
        {
            name: _node(
                comment_count=idx + 1,
                like_count=idx * 2,
                replies_received=idx,
                active_days=(idx % 3) + 1,
            )
            for idx, name in enumerate("abcdefghij")
        },
        [("b", "a", 3), ("c", "a", 1), ("d", "b", 2), ("e", "c", 1)],
    )
    sensitivity = weight_sensitivity(graph, delta=0.1)
    assert set(sensitivity.top_stable) == set(ENGAGEMENT_METRICS)
    assert set(sensitivity.spearman) == set(ENGAGEMENT_METRICS)
    assert all(-1.0 <= rho <= 1.0 for rho in sensitivity.spearman.values())
