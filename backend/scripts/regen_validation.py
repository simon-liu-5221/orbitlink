"""Regenerate the numbers in ``docs/algorithm-validation.md`` (M1 sections).

Run:  ``uv run python scripts/regen_validation.py``

Deterministic where the algorithms allow it. LFR generation is stochastic and
can fail to converge on some parameter sets — those rows are marked accordingly.
Full-pipeline timings (1k / 10k comments) and sentiment F1 belong to M2 / M8 and
are not produced here.
"""

from __future__ import annotations

import time
from collections.abc import Callable

import networkx as nx
import numpy as np
from scipy.stats import spearmanr
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

from app.analysis.communities import detect_communities
from app.analysis.engagement import DEFAULT_WEIGHTS, score_engagement, weight_sensitivity

SEED = 42


def _rule(title: str) -> None:
    print(f"\n{'=' * 4} {title} {'=' * (72 - len(title))}")


# --- 1.1 Zachary karate club --------------------------------------------------


def zachary() -> None:
    _rule("1.1 Zachary karate club")
    result = detect_communities(nx.karate_club_graph())
    print(f"modularity           {result.modularity:.4f}   (literature ~0.42)")
    print(f"communities           {len(result.communities)}        (literature 4)")
    print(f"resolution chosen     {result.resolution_used}")


# --- 1.2 LFR benchmark -------------------------------------------------------


def _lfr(mu: float) -> nx.Graph | None:
    try:
        graph = nx.LFR_benchmark_graph(
            n=500,
            tau1=3,
            tau2=1.5,
            mu=mu,
            average_degree=18,
            min_community=30,
            seed=SEED,
            max_iters=5000,
        )
    except nx.ExceededMaxIterations:
        return None
    graph.remove_edges_from(nx.selfloop_edges(graph))
    return nx.Graph(graph)


def lfr_benchmark() -> None:
    _rule("1.2 LFR benchmark (n=500, avg_degree=18, min_community=30)")
    print(f"{'mu':>4} | {'NMI':>6} | {'ARI':>6} | {'modularity':>10} | comms")
    for mu in (0.1, 0.3, 0.5, 0.7):
        graph = _lfr(mu)
        if graph is None:
            print(f"{mu:>4} | generator did not converge")
            continue
        truth_sets = {frozenset(graph.nodes[node]["community"]) for node in graph}
        truth = {node: idx for idx, comm in enumerate(truth_sets) for node in comm}
        result = detect_communities(graph)
        nodes = list(graph)
        gold = [truth[n] for n in nodes]
        pred = [result.node_communities[n] for n in nodes]
        nmi = normalized_mutual_info_score(gold, pred)
        ari = adjusted_rand_score(gold, pred)
        print(
            f"{mu:>4} | {nmi:>6.3f} | {ari:>6.3f} | {result.modularity:>10.3f} | "
            f"{len(result.communities)} (truth {len(truth_sets)})"
        )


# --- 1.3 multi-resolution vs fixed 1.0 --------------------------------------


def multi_resolution() -> None:
    _rule("1.3 multi-resolution vs fixed resolution=1.0")
    print(f"{'graph':>18} | {'fixed 1.0':>10} | {'multi-res':>10} | {'delta':>8} | res")
    graphs: dict[str, nx.Graph] = {"karate": nx.karate_club_graph()}
    for mu in (0.1, 0.3, 0.5):
        graph = _lfr(mu)
        if graph is not None:
            graphs[f"LFR mu={mu}"] = graph
    for name, graph in graphs.items():
        fixed = detect_communities(graph, resolutions=[1.0])
        multi = detect_communities(graph)
        delta = multi.modularity - fixed.modularity
        print(
            f"{name:>18} | {fixed.modularity:>10.4f} | {multi.modularity:>10.4f} | "
            f"{delta:>+8.4f} | {multi.resolution_used}"
        )


# --- realistic engagement graph -------------------------------------------


def _engagement_graph(n: int = 200) -> nx.DiGraph:
    rng = np.random.default_rng(SEED)
    unit = max(1, n // 20)
    base = nx.stochastic_block_model(
        sizes=[7 * unit, 6 * unit, 4 * unit, 3 * unit],
        p=[
            [0.18, 0.01, 0.01, 0.01],
            [0.01, 0.20, 0.01, 0.01],
            [0.01, 0.01, 0.22, 0.02],
            [0.01, 0.01, 0.02, 0.25],
        ],
        seed=SEED,
    )
    graph: nx.DiGraph = nx.DiGraph()
    graph.graph["period_days"] = 30
    for node in base.nodes():
        degree = base.degree(node)
        comments = int(max(1, rng.poisson(2 + degree)))
        graph.add_node(
            str(node),
            comment_count=comments,
            like_count=int(rng.poisson(degree)),
            replies_received=0,
            active_days=int(min(30, 1 + rng.poisson(degree / 3))),
            avg_text_length=float(rng.uniform(20, 200)),
        )
    for u, v in base.edges():
        weight = int(1 + rng.poisson(1))
        graph.add_edge(str(u), str(v), weight=weight)
        if rng.random() < 0.4:
            graph.add_edge(str(v), str(u), weight=int(1 + rng.poisson(1)))
    for node in graph.nodes:
        graph.nodes[node]["replies_received"] = int(
            sum(d.get("weight", 1) for _, _, d in graph.in_edges(node, data=True))
        )
    return graph


# --- 2.1 weight sensitivity ------------------------------------------------


def weight_sensitivity_table() -> None:
    _rule("2.1 engagement weight sensitivity (+/-10%, top-5)")
    graph = _engagement_graph()
    sensitivity = weight_sensitivity(graph, delta=0.1, top_n=5)
    print(f"{'weight':>16} | top-5 stable | worst Spearman vs baseline")
    for metric in DEFAULT_WEIGHTS:
        print(
            f"{metric:>16} | {sensitivity.top_stable[metric]!s:>12} | "
            f"{sensitivity.spearman[metric]:>.4f}"
        )


# --- 2.2 engagement score vs raw comment count ---------------------------


def engagement_vs_comment_count() -> None:
    _rule("2.2 engagement score vs ranking by comment count alone")
    graph = _engagement_graph()
    result = score_engagement(graph)
    order = [n.node_id for n in result.rankings]
    score_rank = {node: i for i, node in enumerate(order)}
    by_comments = sorted(
        graph.nodes,
        key=lambda node: (-int(graph.nodes[node]["comment_count"]), str(node)),
    )
    comment_rank = {node: i for i, node in enumerate(by_comments)}
    nodes = list(graph.nodes)
    rho = spearmanr([score_rank[n] for n in nodes], [comment_rank[n] for n in nodes]).statistic
    print(f"Spearman(engagement rank, comment-count rank) = {rho:.4f}")
    print(
        "interpretation: > 0.9 would mean the six-factor score adds little over "
        "just counting comments."
    )


# --- 4. performance ------------------------------------------------------


def _time(label: str, fn: Callable[[], object], repeat: int = 5) -> None:
    samples = []
    for _ in range(repeat):
        start = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - start)
    samples.sort()
    p50 = samples[len(samples) // 2]
    p95 = samples[min(len(samples) - 1, int(len(samples) * 0.95))]
    print(f"{label:>44} | p50 {p50 * 1000:8.1f} ms | p95 {p95 * 1000:8.1f} ms")


def performance() -> None:
    _rule("4. performance (local dev machine)")
    graph_5k = nx.gaussian_random_partition_graph(5000, 40, 10, 0.05, 0.01, seed=SEED)
    _time(
        "detect_communities, ~5000 nodes (k=500 betweenness)",
        lambda: detect_communities(graph_5k),
        repeat=3,
    )

    graph_2k = nx.gaussian_random_partition_graph(2000, 40, 10, 0.05, 0.01, seed=SEED)
    _time(
        "detect_communities, 2000 nodes, exact betweenness",
        lambda: detect_communities(graph_2k, betweenness_k_threshold=10_000),
        repeat=3,
    )
    _time(
        "detect_communities, 2000 nodes, k=500 betweenness",
        lambda: detect_communities(graph_2k, betweenness_k_threshold=1000),
        repeat=3,
    )
    _time(
        "score_engagement, 2000 nodes", lambda: score_engagement(_engagement_graph(2000)), repeat=3
    )
    print("\nfull-pipeline 1k/10k-comment timings and sentiment inference: M2 / M8")


def main() -> None:
    zachary()
    lfr_benchmark()
    multi_resolution()
    weight_sensitivity_table()
    engagement_vs_comment_count()
    performance()


if __name__ == "__main__":
    main()
