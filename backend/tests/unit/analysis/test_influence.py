"""AN-04 influencer ranking."""

from __future__ import annotations

import networkx as nx
import pytest

from app.analysis.influence import DEFAULT_WEIGHTS, rank_influencers


def test_default_weights_sum_to_one() -> None:
    assert sum(DEFAULT_WEIGHTS.values()) == pytest.approx(1.0)


def test_empty_graph_returns_empty_ranking() -> None:
    result = rank_influencers(nx.DiGraph())
    assert result.ranking == []
    assert result.approximated is False


def test_hub_of_a_star_ranks_first(two_triangle_graph: nx.DiGraph) -> None:
    # add a hub wired to every node
    graph = nx.DiGraph(two_triangle_graph)
    for node in list(graph.nodes):
        graph.add_edge("hub", node, weight=1)
        graph.add_edge(node, "hub", weight=1)
    result = rank_influencers(graph)
    assert result.ranking[0].node_id == "hub"
    assert result.ranking[0].rank == 1
    assert 0.0 <= result.ranking[0].influence_score <= 1.0


def test_ranking_is_deterministic(karate_graph: nx.Graph) -> None:
    first = [i.node_id for i in rank_influencers(karate_graph).ranking]
    second = [i.node_id for i in rank_influencers(karate_graph).ranking]
    assert first == second


def test_top_n_truncates() -> None:
    result = rank_influencers(nx.karate_club_graph(), top_n=3)
    assert len(result.ranking) == 3
    assert [i.rank for i in result.ranking] == [1, 2, 3]


def test_large_graph_flags_approximation() -> None:
    graph = nx.random_regular_graph(4, 80, seed=1)
    result = rank_influencers(graph, betweenness_k_threshold=50)
    assert result.approximated is True


def test_weights_must_be_complete_and_non_negative() -> None:
    graph = nx.karate_club_graph()
    with pytest.raises(ValueError, match="missing"):
        rank_influencers(graph, weights={"pagerank": 1.0})
    with pytest.raises(ValueError, match="non-negative"):
        rank_influencers(graph, weights={"pagerank": 1.0, "betweenness": -1.0, "degree": 1.0})
    with pytest.raises(ValueError, match="positive number"):
        rank_influencers(graph, weights={"pagerank": 0.0, "betweenness": 0.0, "degree": 0.0})
