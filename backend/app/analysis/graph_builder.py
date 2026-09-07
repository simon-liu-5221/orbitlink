"""Build the reply-interaction graph from a comment DataFrame.

Pure: takes a ``pandas.DataFrame``, returns a ``networkx.DiGraph``. It does not
fetch data and does not pseudonymise author ids — the caller passes whatever
author identifier it wants as node ids (in production, an HMAC pseudonym; in
tests, a plain string). See ADR-0003.

Expected columns
----------------
Required: ``comment_id``, ``author_id``, ``parent_id`` (``parent_id`` is null
for a top-level comment).
Optional: ``like_count`` (int), ``published_at`` (datetime-like), ``text`` (str)
or ``text_length`` (int), ``sentiment`` (float in [-1, 1]).

Graph shape
-----------
* Node per author. Node attrs: ``comment_count``, ``like_count`` (received on
  their comments), ``replies_received``, ``active_days``, ``avg_text_length``,
  and ``sentiment`` (mean, only when a ``sentiment`` column was supplied and the
  author has at least one non-null value).
* Directed edge ``replier -> parent_author`` with ``weight`` = number of such
  replies. Self-replies are dropped. Replies whose parent comment is not in the
  frame are dropped (author unknown).
* Graph attrs: ``n_comments``, ``period_days`` (distinct calendar days,
  minimum 1), ``start``, ``end``.
"""

from __future__ import annotations

import networkx as nx
import pandas as pd

REQUIRED_COLUMNS: tuple[str, ...] = ("comment_id", "author_id", "parent_id")


def _clean_parent(value: object) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None


def build_interaction_graph(comments: pd.DataFrame) -> nx.DiGraph:
    missing = [c for c in REQUIRED_COLUMNS if c not in comments.columns]
    if missing:
        raise ValueError(f"comments frame missing required columns: {missing}")

    df = comments.copy()
    df["comment_id"] = df["comment_id"].astype(str)
    df["author_id"] = df["author_id"].astype(str)
    df["parent_id"] = df["parent_id"].map(_clean_parent)

    if "like_count" in df.columns:
        df["like_count"] = pd.to_numeric(df["like_count"], errors="coerce").fillna(0).astype(int)
    else:
        df["like_count"] = 0

    if "text" in df.columns:
        df["text_length"] = df["text"].fillna("").astype(str).str.len().astype(int)
    elif "text_length" in df.columns:
        df["text_length"] = pd.to_numeric(df["text_length"], errors="coerce").fillna(0).astype(int)
    else:
        df["text_length"] = 0

    has_ts = "published_at" in df.columns
    if has_ts:
        df["published_at"] = pd.to_datetime(df["published_at"], errors="coerce", utc=True)
        has_ts = bool(df["published_at"].notna().any())

    has_sentiment = "sentiment" in df.columns
    if has_sentiment:
        df["sentiment"] = pd.to_numeric(df["sentiment"], errors="coerce")

    graph: nx.DiGraph = nx.DiGraph()
    graph.graph["n_comments"] = len(df)
    if has_ts:
        ts = df["published_at"].dropna()
        graph.graph["start"] = ts.min().to_pydatetime()
        graph.graph["end"] = ts.max().to_pydatetime()
        graph.graph["period_days"] = max(int(ts.dt.floor("D").nunique()), 1)
    else:
        graph.graph["start"] = None
        graph.graph["end"] = None
        graph.graph["period_days"] = 1

    _add_nodes(graph, df, has_ts=has_ts, has_sentiment=has_sentiment)
    _add_edges(graph, df)
    return graph


def _add_nodes(graph: nx.DiGraph, df: pd.DataFrame, *, has_ts: bool, has_sentiment: bool) -> None:
    for author, group in df.groupby("author_id", sort=True):
        attrs: dict[str, object] = {
            "comment_count": len(group),
            "like_count": int(group["like_count"].sum()),
            "avg_text_length": float(group["text_length"].mean()),
            "replies_received": 0,
            "active_days": 0,
        }
        if has_ts:
            days = group["published_at"].dropna()
            attrs["active_days"] = int(days.dt.floor("D").nunique())
        if has_sentiment and group["sentiment"].notna().any():
            attrs["sentiment"] = float(group["sentiment"].dropna().mean())
        graph.add_node(str(author), **attrs)


def _add_edges(graph: nx.DiGraph, df: pd.DataFrame) -> None:
    comment_author: dict[str, str] = dict(zip(df["comment_id"], df["author_id"], strict=True))

    counts: dict[tuple[str, str], int] = {}
    replies = df.loc[df["parent_id"].notna(), ["author_id", "parent_id"]]
    for author, parent_id in zip(replies["author_id"], replies["parent_id"], strict=True):
        parent_author = comment_author.get(str(parent_id))
        if parent_author is None or parent_author == author:
            continue
        key = (str(author), str(parent_author))
        counts[key] = counts.get(key, 0) + 1

    for (source, target), weight in counts.items():
        graph.add_edge(source, target, weight=weight)
    _recompute_replies_received(graph)


def _recompute_replies_received(graph: nx.DiGraph) -> None:
    for node in graph.nodes:
        graph.nodes[node]["replies_received"] = int(
            sum(data.get("weight", 1) for _, _, data in graph.in_edges(node, data=True))
        )


def to_undirected_weighted(graph: nx.DiGraph | nx.Graph) -> nx.Graph:
    """Collapse a directed interaction graph to undirected, summing edge weights.

    ``A -> B`` (weight ``w1``) and ``B -> A`` (weight ``w2``) become a single
    undirected edge ``A - B`` with weight ``w1 + w2``. Node attributes are kept.
    """
    undirected: nx.Graph = nx.Graph()
    undirected.add_nodes_from(graph.nodes(data=True))
    for source, target, data in graph.edges(data=True):
        weight = data.get("weight", 1)
        if undirected.has_edge(source, target):
            undirected[source][target]["weight"] += weight
        else:
            undirected.add_edge(source, target, weight=weight)
    return undirected
