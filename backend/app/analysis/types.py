"""Shared result types for the analysis layer.

Plain frozen dataclasses only — no pydantic, no ORM. The service layer maps
these to DB rows and API schemas (later milestones).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

# A node id is the (pseudonymised, in production) author identifier.
NodeId = str

#: The three sentiment classes, in a fixed order (AN-03).
SENTIMENT_LABELS: tuple[str, ...] = ("negative", "neutral", "positive")


@dataclass(frozen=True)
class CommunityMetrics:
    """Aggregate stats for a single detected community."""

    community_id: int
    size: int
    total_comments: int
    total_likes: int
    #: Mean of member sentiment scores in [-1, 1]; ``None`` when sentiment was
    #: not supplied for any member (AN-01: sentiment is an optional input).
    avg_sentiment: float | None
    #: Up to 3 member node ids, ranked by PageRank within the community subgraph.
    top_influencers: list[NodeId]
    #: Members that also sit in the whole-graph betweenness top band — the
    #: people holding this community to the rest of the network.
    bridge_users: list[NodeId]
    #: Mean clustering coefficient of the community subgraph.
    cohesion: float
    #: Density of the community subgraph.
    density: float


#: The six engagement sub-metrics (AN-02), in a fixed order.
ENGAGEMENT_METRICS: tuple[str, ...] = (
    "engagement",
    "consistency",
    "network",
    "quality",
    "activity",
    "responsiveness",
)


@dataclass(frozen=True)
class NodeEngagement:
    """One node's engagement score (AN-02)."""

    node_id: NodeId
    #: Final score on the 1.0–10.0 scale.
    score: float
    #: 1-based rank (1 = most engaged).
    rank: int
    #: The six normalised sub-scores in [0, 1] — the breakdown the frontend shows.
    breakdown: dict[str, float]
    #: The six raw (pre-normalisation) metric values.
    raw: dict[str, float]


@dataclass(frozen=True)
class EngagementResult:
    """Outcome of :func:`app.analysis.engagement.score_engagement`."""

    #: Every node, ordered by score descending then node id.
    rankings: list[NodeEngagement]
    #: ``rankings[:top_n]`` — kept separately for the frontend's top-N panels.
    top: list[NodeEngagement]
    #: The (normalised-to-sum-1) weights actually applied.
    weights: dict[str, float]


@dataclass(frozen=True)
class WeightSensitivity:
    """Sensitivity of the ranking to a ±delta perturbation of each weight."""

    delta: float
    #: metric name -> did the top-N set stay the same when this weight moved ±delta.
    top_stable: dict[str, bool]
    #: metric name -> min Spearman correlation (over the ± perturbations) with the
    #: baseline full ranking.
    spearman: dict[str, float]


@dataclass(frozen=True)
class SentimentPrediction:
    """What an injected model returns for one comment: 3 class probabilities
    (should sum to ~1) plus a 0–1 toxicity score."""

    negative: float
    neutral: float
    positive: float
    toxicity: float


@dataclass(frozen=True)
class CommentSentiment:
    """Per-comment sentiment outcome (AN-03)."""

    comment_id: str
    #: argmax label, or ``None`` when skipped / failed.
    label: str | None
    #: Continuous score ``p_positive - p_negative`` in [-1, 1]; ``None`` when
    #: skipped / failed.
    score: float | None
    toxicity: float | None
    #: Empty / emoji-only text — not sent to the model, excluded from aggregates.
    skipped: bool = False
    #: The batch this comment was in exhausted its retries.
    failed: bool = False
    #: Text was truncated before inference.
    truncated: bool = False


@dataclass(frozen=True)
class SentimentTrendPoint:
    bucket_start: datetime
    mean_score: float
    count: int


@dataclass(frozen=True)
class SentimentResult:
    """Outcome of :meth:`app.analysis.sentiment.SentimentAnalyzer.analyze`."""

    comments: list[CommentSentiment]
    #: Percentage of scored comments in each class; keys are ``SENTIMENT_LABELS``,
    #: values sum to ~100 (0.0 each when nothing was scored).
    distribution: dict[str, float]
    #: Mean score per time bucket, ordered by bucket start.
    trend: list[SentimentTrendPoint]
    #: ``"hour"`` when the analysis window is < 7 days, else ``"day"``.
    trend_bucket: str
    #: community id -> mean sentiment score (empty when no ``community_id`` given).
    by_community: dict[int, float]
    #: Fraction of scored comments with toxicity above the threshold.
    toxic_ratio: float
    skipped_count: int
    #: failed comments / comments sent to the model.
    failed_ratio: float
    #: truncated comments / comments sent to the model.
    truncated_ratio: float


@dataclass(frozen=True)
class CommunityDetectionResult:
    """Outcome of :func:`app.analysis.communities.detect_communities`."""

    #: node id -> community id. Empty when ``insufficient_data``.
    node_communities: dict[NodeId, int] = field(default_factory=dict)
    communities: list[CommunityMetrics] = field(default_factory=list)
    #: Modularity of the chosen partition (0.0 when ``insufficient_data``).
    modularity: float = 0.0
    #: Resolution parameter that produced the chosen partition.
    resolution_used: float = 0.0
    #: Too few nodes/edges to detect communities (< 3 nodes or < 2 edges).
    insufficient_data: bool = False
    #: Best modularity fell below the weak-structure threshold (default 0.3).
    weak_structure: bool = False
    #: Betweenness centrality was estimated with k-sampling (large graphs).
    approximated: bool = False
