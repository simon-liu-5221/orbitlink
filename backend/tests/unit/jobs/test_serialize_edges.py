"""PR-10 — serializing the interaction graph's edges for persistence."""

from __future__ import annotations

import networkx as nx

from app.services.analysis_service import _serialize_edges


def test_serializes_every_edge_with_its_weight() -> None:
    graph = nx.DiGraph()
    graph.add_edge("alice", "bob", weight=3)
    graph.add_edge("bob", "carol", weight=1)

    edges = _serialize_edges(graph)

    assert edges == [
        {"source": "alice", "target": "bob", "weight": 3},
        {"source": "bob", "target": "carol", "weight": 1},
    ]


def test_defaults_to_weight_one_when_missing() -> None:
    graph = nx.DiGraph()
    graph.add_edge("alice", "bob")  # no weight attribute

    assert _serialize_edges(graph) == [{"source": "alice", "target": "bob", "weight": 1}]


def test_an_empty_graph_serializes_to_an_empty_list() -> None:
    assert _serialize_edges(nx.DiGraph()) == []


def test_node_ids_are_coerced_to_strings() -> None:
    """Pseudonyms are always strings, but the graph itself is generic."""
    graph = nx.DiGraph()
    graph.add_edge(1, 2, weight=1)

    assert _serialize_edges(graph) == [{"source": "1", "target": "2", "weight": 1}]
