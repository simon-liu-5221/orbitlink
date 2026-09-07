"""Sentiment + toxicity aggregation (AN-03).

The model is **injected** — ``SentimentAnalyzer(predict_fn=...)``. That is what
makes this module offline-testable: tests pass a fake ``predict_fn``; the real
XLM-RoBERTa wrappers (ADR-0004) are wired in the worker (M2). If no model is
injected, :meth:`SentimentAnalyzer.analyze` raises rather than inventing scores.

Token-level truncation to 512 tokens is the model wrapper's job; here we apply a
character-length guard (``max_chars``) and report the ratio truncated.

Input: a ``pandas.DataFrame`` with ``comment_id`` and ``text``; optionally
``published_at`` (enables the trend) and ``community_id`` (enables per-community
means).
"""

from __future__ import annotations

import logging
import unicodedata
from collections.abc import Callable, Sequence

import pandas as pd

from app.analysis.types import (
    SENTIMENT_LABELS,
    CommentSentiment,
    SentimentPrediction,
    SentimentResult,
    SentimentTrendPoint,
)

logger = logging.getLogger(__name__)

#: ``predict_fn`` takes a batch of texts, returns one prediction per text.
PredictFn = Callable[[Sequence[str]], Sequence[SentimentPrediction]]

DEFAULT_BATCH_SIZE = 32
DEFAULT_MAX_RETRIES = 2
DEFAULT_FAILED_THRESHOLD = 0.20
DEFAULT_TOXICITY_THRESHOLD = 0.70
DEFAULT_MAX_CHARS = 2000
_WEEK = pd.Timedelta(days=7)


# Name fixed by spec AN-03 (AC-5) — keep it, no "Error" suffix.
class SentimentAnalysisFailed(RuntimeError):  # noqa: N818
    """Raised when too large a fraction of comments could not be scored."""


class SentimentModelNotLoaded(SentimentAnalysisFailed):
    """Raised when ``analyze`` is called without an injected model."""


class SentimentAnalyzer:
    def __init__(
        self,
        predict_fn: PredictFn | None = None,
        *,
        batch_size: int = DEFAULT_BATCH_SIZE,
        max_retries: int = DEFAULT_MAX_RETRIES,
        failed_threshold: float = DEFAULT_FAILED_THRESHOLD,
        toxicity_threshold: float = DEFAULT_TOXICITY_THRESHOLD,
        max_chars: int = DEFAULT_MAX_CHARS,
    ) -> None:
        self._predict_fn = predict_fn
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.failed_threshold = failed_threshold
        self.toxicity_threshold = toxicity_threshold
        self.max_chars = max_chars

    def analyze(self, comments: pd.DataFrame) -> SentimentResult:
        if self._predict_fn is None:
            raise SentimentModelNotLoaded("no sentiment model injected")
        for column in ("comment_id", "text"):
            if column not in comments.columns:
                raise ValueError(f"comments frame missing required column: {column!r}")

        df = comments.reset_index(drop=True)
        texts = df["text"].fillna("").astype(str)

        per_comment: dict[str, CommentSentiment] = {}
        pending: list[tuple[str, str, bool]] = []  # (comment_id, text_to_send, truncated)
        for comment_id, text in zip(df["comment_id"].astype(str), texts, strict=True):
            if _is_meaningless(text):
                per_comment[comment_id] = CommentSentiment(
                    comment_id=comment_id, label=None, score=None, toxicity=None, skipped=True
                )
                continue
            truncated = len(text) > self.max_chars
            pending.append((comment_id, text[: self.max_chars], truncated))

        sent_count = len(pending)
        failed_count = 0
        for start in range(0, sent_count, self.batch_size):
            batch = pending[start : start + self.batch_size]
            predictions = self._run_batch([text for _, text, _ in batch])
            if predictions is None:
                failed_count += len(batch)
                for comment_id, _, truncated in batch:
                    per_comment[comment_id] = CommentSentiment(
                        comment_id=comment_id,
                        label=None,
                        score=None,
                        toxicity=None,
                        failed=True,
                        truncated=truncated,
                    )
                continue
            for (comment_id, _, truncated), prediction in zip(batch, predictions, strict=True):
                per_comment[comment_id] = _to_comment_sentiment(comment_id, prediction, truncated)

        failed_ratio = failed_count / sent_count if sent_count else 0.0
        if failed_ratio > self.failed_threshold:
            raise SentimentAnalysisFailed(
                f"{failed_ratio:.0%} of comments failed sentiment inference "
                f"(threshold {self.failed_threshold:.0%})"
            )

        ordered = [per_comment[str(cid)] for cid in df["comment_id"].astype(str)]
        return self._aggregate(df, ordered, sent_count=sent_count, failed_count=failed_count)

    # -- internals ---------------------------------------------------------

    def _run_batch(self, texts: list[str]) -> Sequence[SentimentPrediction] | None:
        assert self._predict_fn is not None
        attempts = self.max_retries + 1
        for attempt in range(1, attempts + 1):
            try:
                predictions = self._predict_fn(texts)
            except Exception:
                logger.warning(
                    "sentiment batch inference failed (attempt %d/%d)",
                    attempt,
                    attempts,
                    exc_info=True,
                )
                continue
            if len(predictions) != len(texts):
                raise SentimentAnalysisFailed(
                    f"model returned {len(predictions)} predictions for {len(texts)} texts"
                )
            return predictions
        return None

    def _aggregate(
        self,
        df: pd.DataFrame,
        ordered: list[CommentSentiment],
        *,
        sent_count: int,
        failed_count: int,
    ) -> SentimentResult:
        scored = [c for c in ordered if c.label is not None and c.score is not None]

        distribution = dict.fromkeys(SENTIMENT_LABELS, 0.0)
        if scored:
            for comment in scored:
                distribution[str(comment.label)] += 1
            distribution = {k: round(v / len(scored) * 100, 6) for k, v in distribution.items()}

        toxic = sum(
            1 for c in scored if c.toxicity is not None and c.toxicity > self.toxicity_threshold
        )
        toxic_ratio = toxic / len(scored) if scored else 0.0

        score_by_id = {c.comment_id: c.score for c in scored}
        trend, trend_bucket = _build_trend(df, score_by_id)
        by_community = _by_community(df, score_by_id)

        return SentimentResult(
            comments=ordered,
            distribution=distribution,
            trend=trend,
            trend_bucket=trend_bucket,
            by_community=by_community,
            toxic_ratio=round(toxic_ratio, 6),
            skipped_count=sum(1 for c in ordered if c.skipped),
            failed_ratio=round(failed_count / sent_count, 6) if sent_count else 0.0,
            truncated_ratio=(
                round(sum(1 for c in ordered if c.truncated) / sent_count, 6) if sent_count else 0.0
            ),
        )


def _is_meaningless(text: str) -> bool:
    """True for empty / whitespace / emoji-only / punctuation-only text."""
    return not any(unicodedata.category(ch)[0] in {"L", "N"} for ch in text)


def _to_comment_sentiment(
    comment_id: str, prediction: SentimentPrediction, truncated: bool
) -> CommentSentiment:
    probs = {
        "negative": prediction.negative,
        "neutral": prediction.neutral,
        "positive": prediction.positive,
    }
    label = max(SENTIMENT_LABELS, key=lambda name: probs[name])
    return CommentSentiment(
        comment_id=comment_id,
        label=label,
        score=float(prediction.positive - prediction.negative),
        toxicity=float(prediction.toxicity),
        truncated=truncated,
    )


def _build_trend(
    df: pd.DataFrame, score_by_id: dict[str, float | None]
) -> tuple[list[SentimentTrendPoint], str]:
    if "published_at" not in df.columns:
        return [], "day"
    timestamps = pd.to_datetime(df["published_at"], errors="coerce", utc=True)
    frame = pd.DataFrame(
        {
            "ts": timestamps,
            "score": df["comment_id"].astype(str).map(score_by_id),
        }
    ).dropna(subset=["ts", "score"])
    if frame.empty:
        return [], "day"

    span = frame["ts"].max() - frame["ts"].min()
    unit, label = ("h", "hour") if span < _WEEK else ("D", "day")
    frame["bucket"] = frame["ts"].dt.floor(unit)
    grouped = frame.groupby("bucket")["score"].agg(["mean", "count"]).sort_index().reset_index()
    points = [
        SentimentTrendPoint(
            bucket_start=pd.Timestamp(bucket).to_pydatetime(),
            mean_score=round(float(mean), 6),
            count=int(count),
        )
        for bucket, mean, count in grouped.itertuples(index=False, name=None)
    ]
    return points, label


def _by_community(df: pd.DataFrame, score_by_id: dict[str, float | None]) -> dict[int, float]:
    if "community_id" not in df.columns:
        return {}
    frame = pd.DataFrame(
        {
            "community_id": pd.to_numeric(df["community_id"], errors="coerce"),
            "score": df["comment_id"].astype(str).map(score_by_id),
        }
    ).dropna(subset=["community_id", "score"])
    if frame.empty:
        return {}
    means = frame.groupby("community_id")["score"].mean().reset_index()
    return {
        int(community_id): round(float(mean), 6)
        for community_id, mean in means.itertuples(index=False, name=None)
    }


__all__ = [
    "PredictFn",
    "SentimentAnalysisFailed",
    "SentimentAnalyzer",
    "SentimentModelNotLoaded",
]
