"""AN-01 acceptance tests — one test per acceptance criterion."""

from __future__ import annotations

import logging

import networkx as nx
import pytest
from sklearn.metrics import normalized_mutual_info_score

from app.analysis import communities
from app.analysis.communities import detect_communities

from .conftest import lfr_ground_truth


def test_ac1_zachary_karate_club(karate_graph: nx.Graph) -> None:
    """AC-1: modularity >= 0.40 and 2-5 communities on the karate club."""
    result = detect_communities(karate_graph)
    assert result.modularity >= 0.40
    assert 2 <= len(result.communities) <= 5
    assert result.insufficient_data is False


def test_ac2_lfr_benchmark_nmi(lfr_graph: nx.Graph) -> None:
    """AC-2: NMI vs planted communities >= 0.85 at mu=0.1."""
    truth = lfr_ground_truth(lfr_graph)
    result = detect_communities(lfr_graph)
    nodes = list(lfr_graph)
    nmi = normalized_mutual_info_score(
        [truth[n] for n in nodes], [result.node_communities[n] for n in nodes]
    )
    assert nmi >= 0.85


def test_ac3_two_node_graph_is_insufficient_data() -> None:
    """AC-3: 2 nodes / 1 edge -> insufficient_data, no exception."""
    result = detect_communities(nx.Graph([("x", "y")]))
    assert result.insufficient_data is True
    assert result.communities == []
    assert result.node_communities == {}


def test_ac4_random_graph_flags_weak_structure(random_graph: nx.Graph) -> None:
    """AC-4: an Erdős–Rényi graph has no real structure -> weak_structure."""
    result = detect_communities(random_graph)
    assert result.weak_structure is True
    assert result.modularity < communities.WEAK_MODULARITY_THRESHOLD


def test_ac5_same_seed_gives_identical_assignment(karate_graph: nx.Graph) -> None:
    """AC-5: deterministic community assignment for a fixed random_state."""
    first = detect_communities(karate_graph, seed=123)
    second = detect_communities(karate_graph, seed=123)
    assert first.node_communities == second.node_communities
    assert first.modularity == second.modularity
    assert first.resolution_used == second.resolution_used


def test_ac6_hand_fixture_metrics_match_by_hand(two_triangle_graph: nx.DiGraph) -> None:
    """AC-6: per-community size / density / mean sentiment / totals are exact."""
    result = detect_communities(two_triangle_graph)
    assert len(result.communities) == 2

    by_members = {
        frozenset(n for n, c in result.node_communities.items() if c == cm.community_id): cm
        for cm in result.communities
    }
    left = by_members[frozenset({"a", "b", "c"})]
    right = by_members[frozenset({"d", "e", "f"})]

    assert left.size == 3 and right.size == 3
    assert left.density == 1.0 and right.density == 1.0
    assert left.cohesion == 1.0 and right.cohesion == 1.0
    assert left.total_comments == 10 and left.total_likes == 14
    assert right.total_comments == 13 and right.total_likes == 27
    assert left.avg_sentiment == pytest.approx(0.1)
    assert right.avg_sentiment == pytest.approx(0.1)
    # c and d are the two ends of the only inter-community edge -> bridges
    assert "c" in left.bridge_users
    assert "d" in right.bridge_users


def test_ac7_resolution_sweep_failure_falls_back_to_res_1(
    karate_graph: nx.Graph,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """AC-7: if the resolution optimisation throws, return the resolution=1.0
    result and log a warning — do not propagate the exception."""

    def boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("optimisation exploded")

    monkeypatch.setattr(communities, "_sweep_resolutions", boom)

    with caplog.at_level(logging.WARNING, logger="app.analysis.communities"):
        result = detect_communities(karate_graph)

    assert result.resolution_used == 1.0
    assert result.insufficient_data is False
    assert len(result.communities) >= 2
    assert any("resolution optimisation failed" in r.message for r in caplog.records)


def test_ac8_module_does_not_import_io_layers() -> None:
    """AC-8: communities.py imports nothing from db / api / http (belt-and-braces
    next to the import-linter contract in CI)."""
    import app.analysis.communities as module

    source = module.__file__
    assert source is not None
    text = __import__("pathlib").Path(source).read_text(encoding="utf-8")
    for forbidden in (
        "import sqlalchemy",
        "import fastapi",
        "import httpx",
        "from app.db",
        "from app.api",
    ):
        assert forbidden not in text


def test_empty_resolution_list_falls_back_without_raising(
    karate_graph: nx.Graph, caplog: pytest.LogCaptureFixture
) -> None:
    """Exception-flow row: an empty resolution sweep still yields a result."""
    with caplog.at_level(logging.WARNING, logger="app.analysis.communities"):
        result = detect_communities(karate_graph, resolutions=[])
    assert result.resolution_used == 1.0
    assert len(result.communities) >= 2


def test_disconnected_graph_is_handled(two_triangle_graph: nx.DiGraph) -> None:
    """Exception-flow row: a disconnected graph is processed normally."""
    graph = nx.DiGraph(two_triangle_graph)
    graph.remove_edge("c", "d")  # split into two components
    graph.add_node("lonely", comment_count=1, like_count=0)
    result = detect_communities(graph)
    assert result.insufficient_data is False
    assert result.node_communities["a"] != result.node_communities["d"]


def test_sentiment_is_optional(two_triangle_graph: nx.DiGraph) -> None:
    """Implementation note: missing sentiment -> avg_sentiment None, no error."""
    for node in two_triangle_graph.nodes:
        del two_triangle_graph.nodes[node]["sentiment"]
    result = detect_communities(two_triangle_graph)
    assert all(c.avg_sentiment is None for c in result.communities)
