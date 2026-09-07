"""Tests for centrality wrappers (ADR-0003: match networkx within tolerance)."""

from __future__ import annotations

import networkx as nx
import pytest

from app.analysis import centrality


def test_pagerank_matches_networkx_within_tolerance() -> None:
    graph = nx.karate_club_graph()
    ours = centrality.pagerank(graph, weight=None)
    reference = nx.pagerank(graph, weight=None)
    for node in graph:
        assert ours[node] == pytest.approx(reference[node], abs=1e-6)


def test_pagerank_empty_graph_returns_empty_dict() -> None:
    assert centrality.pagerank(nx.DiGraph()) == {}


def test_weighted_degree_centrality_matches_unweighted_when_weights_are_one() -> None:
    graph = nx.path_graph(5)
    ours = centrality.weighted_degree_centrality(graph, weight=None)
    reference = nx.degree_centrality(graph)
    for node in graph:
        assert ours[node] == pytest.approx(reference[node])


def test_weighted_degree_centrality_degenerate_graphs_are_zero() -> None:
    assert centrality.weighted_degree_centrality(nx.Graph()) == {}
    assert centrality.weighted_degree_centrality(nx.Graph([("solo", "solo")])) == {"solo": 0.0}


def test_weighted_degree_centrality_uses_edge_weights() -> None:
    graph: nx.Graph = nx.Graph()
    graph.add_edge("a", "b", weight=4)
    graph.add_edge("b", "c", weight=1)
    scores = centrality.weighted_degree_centrality(graph)
    # b has weighted degree 5 over (n-1)=2
    assert scores["b"] == pytest.approx(2.5)
    assert scores["a"] == pytest.approx(2.0)


def test_betweenness_exact_for_small_graph() -> None:
    graph = nx.path_graph(5)
    scores, approximated = centrality.betweenness(graph)
    assert approximated is False
    reference = nx.betweenness_centrality(graph, normalized=True)
    for node in graph:
        assert scores[node] == pytest.approx(reference[node])


def test_betweenness_flags_approximation_above_threshold() -> None:
    graph = nx.random_regular_graph(4, 60, seed=1)
    _, approximated = centrality.betweenness(graph, k_threshold=50, k=20, seed=1)
    assert approximated is True


def test_betweenness_tiny_graph_is_all_zero() -> None:
    scores, approximated = centrality.betweenness(nx.Graph([("a", "b")]))
    assert scores == {"a": 0.0, "b": 0.0}
    assert approximated is False
