"""Tests for graph_builder — comment DataFrame -> reply-interaction DiGraph.

No spec of its own; covers the edge cases named in ADR-0003 (empty frame,
single comment, self-reply, missing parent_id) plus weight merging.
"""

from __future__ import annotations

import networkx as nx
import pandas as pd
import pytest

from app.analysis.graph_builder import build_interaction_graph, to_undirected_weighted


def _frame(rows: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(
        rows, columns=["comment_id", "author_id", "parent_id", "like_count", "text"]
    )


def test_missing_required_columns_raises() -> None:
    with pytest.raises(ValueError, match="required columns"):
        build_interaction_graph(pd.DataFrame({"comment_id": ["1"]}))


def test_empty_frame_yields_empty_graph() -> None:
    graph = build_interaction_graph(_frame([]))
    assert graph.number_of_nodes() == 0
    assert graph.number_of_edges() == 0
    assert graph.graph["n_comments"] == 0
    assert graph.graph["period_days"] == 1


def test_single_comment_one_node_no_edges() -> None:
    graph = build_interaction_graph(
        _frame(
            [
                {
                    "comment_id": "1",
                    "author_id": "alice",
                    "parent_id": None,
                    "like_count": 3,
                    "text": "hi",
                }
            ]
        )
    )
    assert set(graph.nodes) == {"alice"}
    assert graph.number_of_edges() == 0
    assert graph.nodes["alice"]["comment_count"] == 1
    assert graph.nodes["alice"]["like_count"] == 3


def test_reply_creates_directed_edge_replier_to_parent_author() -> None:
    graph = build_interaction_graph(
        _frame(
            [
                {
                    "comment_id": "1",
                    "author_id": "alice",
                    "parent_id": None,
                    "like_count": 0,
                    "text": "root",
                },
                {
                    "comment_id": "2",
                    "author_id": "bob",
                    "parent_id": "1",
                    "like_count": 0,
                    "text": "reply",
                },
            ]
        )
    )
    assert graph.has_edge("bob", "alice")
    assert not graph.has_edge("alice", "bob")
    assert graph["bob"]["alice"]["weight"] == 1
    assert graph.nodes["alice"]["replies_received"] == 1
    assert graph.nodes["bob"]["replies_received"] == 0


def test_self_reply_produces_no_edge() -> None:
    graph = build_interaction_graph(
        _frame(
            [
                {
                    "comment_id": "1",
                    "author_id": "alice",
                    "parent_id": None,
                    "like_count": 0,
                    "text": "a",
                },
                {
                    "comment_id": "2",
                    "author_id": "alice",
                    "parent_id": "1",
                    "like_count": 0,
                    "text": "self",
                },
            ]
        )
    )
    assert graph.number_of_edges() == 0
    assert graph.nodes["alice"]["comment_count"] == 2


def test_reply_to_unknown_parent_is_dropped() -> None:
    graph = build_interaction_graph(
        _frame(
            [
                {
                    "comment_id": "2",
                    "author_id": "bob",
                    "parent_id": "999",
                    "like_count": 0,
                    "text": "orphan",
                },
            ]
        )
    )
    assert set(graph.nodes) == {"bob"}
    assert graph.number_of_edges() == 0


def test_repeated_interactions_accumulate_edge_weight() -> None:
    graph = build_interaction_graph(
        _frame(
            [
                {
                    "comment_id": "1",
                    "author_id": "alice",
                    "parent_id": None,
                    "like_count": 0,
                    "text": "x",
                },
                {
                    "comment_id": "2",
                    "author_id": "bob",
                    "parent_id": "1",
                    "like_count": 0,
                    "text": "y",
                },
                {
                    "comment_id": "3",
                    "author_id": "bob",
                    "parent_id": "1",
                    "like_count": 0,
                    "text": "z",
                },
            ]
        )
    )
    assert graph["bob"]["alice"]["weight"] == 2
    assert graph.nodes["alice"]["replies_received"] == 2


def test_active_days_and_period_from_timestamps() -> None:
    frame = pd.DataFrame(
        [
            {
                "comment_id": "1",
                "author_id": "a",
                "parent_id": None,
                "published_at": "2026-01-01T10:00:00Z",
            },
            {
                "comment_id": "2",
                "author_id": "a",
                "parent_id": None,
                "published_at": "2026-01-01T22:00:00Z",
            },
            {
                "comment_id": "3",
                "author_id": "a",
                "parent_id": None,
                "published_at": "2026-01-04T09:00:00Z",
            },
        ]
    )
    graph = build_interaction_graph(frame)
    assert graph.nodes["a"]["active_days"] == 2
    assert graph.graph["period_days"] == 2


def test_sentiment_column_averaged_per_author_when_present() -> None:
    frame = pd.DataFrame(
        [
            {"comment_id": "1", "author_id": "a", "parent_id": None, "sentiment": 0.4},
            {"comment_id": "2", "author_id": "a", "parent_id": None, "sentiment": -0.2},
            {"comment_id": "3", "author_id": "b", "parent_id": None, "sentiment": None},
        ]
    )
    graph = build_interaction_graph(frame)
    assert graph.nodes["a"]["sentiment"] == pytest.approx(0.1)
    assert "sentiment" not in graph.nodes["b"]


def test_precomputed_text_length_column_is_used() -> None:
    frame = pd.DataFrame(
        [
            {"comment_id": "1", "author_id": "a", "parent_id": None, "text_length": 40},
            {"comment_id": "2", "author_id": "a", "parent_id": None, "text_length": 60},
        ]
    )
    graph = build_interaction_graph(frame)
    assert graph.nodes["a"]["avg_text_length"] == pytest.approx(50.0)


def test_to_undirected_weighted_sums_both_directions() -> None:
    directed: nx.DiGraph = nx.DiGraph()
    directed.add_edge("a", "b", weight=2)
    directed.add_edge("b", "a", weight=3)
    directed.add_node("a", comment_count=1)
    undirected = to_undirected_weighted(directed)
    assert undirected["a"]["b"]["weight"] == 5
    assert undirected.nodes["a"]["comment_count"] == 1
