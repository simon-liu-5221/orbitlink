"""AN-03 acceptance tests — one test per acceptance criterion.

AC-9 (macro F1 >= 0.65 on 500 hand-labelled comments) is deferred to M8: it
needs a real labelled dataset, not a fake model.
"""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd
import pytest

from app.analysis.sentiment import (
    SentimentAnalysisFailed,
    SentimentAnalyzer,
    SentimentModelNotLoaded,
)
from app.analysis.types import SENTIMENT_LABELS, SentimentPrediction

_FIXED = SentimentPrediction(negative=0.2, neutral=0.5, positive=0.3, toxicity=0.1)


class FakeModel:
    """Records calls; can be told to raise for a given 0-based batch index.

    Batch index advances only when the text list changes — retries reuse the
    same list, so they do not count as a new batch.
    """

    def __init__(
        self,
        response: SentimentPrediction | dict[str, SentimentPrediction] = _FIXED,
        *,
        raise_on_batch: int | None = None,
    ) -> None:
        self.response = response
        self.raise_on_batch = raise_on_batch
        self.calls: list[list[str]] = []
        self._batch_index = -1
        self._last_texts: list[str] | None = None

    def __call__(self, texts: Sequence[str]) -> list[SentimentPrediction]:
        batch = list(texts)
        if batch != self._last_texts:
            self._batch_index += 1
            self._last_texts = batch
        self.calls.append(batch)
        if self.raise_on_batch is not None and self._batch_index == self.raise_on_batch:
            raise RuntimeError("model exploded")
        return [self._predict(text) for text in batch]

    def _predict(self, text: str) -> SentimentPrediction:
        if isinstance(self.response, dict):
            for key, prediction in self.response.items():
                if key in text:
                    return prediction
            return _FIXED
        return self.response


def _frame(n: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "comment_id": [f"c{i}" for i in range(n)],
            "text": [f"comment number {i}" for i in range(n)],
        }
    )


def test_ac1_batches_split_correctly_and_every_comment_has_a_result() -> None:
    model = FakeModel()
    result = SentimentAnalyzer(model, batch_size=32).analyze(_frame(70))
    assert len(model.calls) == 3  # 32 + 32 + 6
    assert [len(c) for c in model.calls] == [32, 32, 6]
    assert len(result.comments) == 70
    assert all(c.label in SENTIMENT_LABELS for c in result.comments)


def test_ac2_hundred_comments_batch_32_calls_model_four_times() -> None:
    model = FakeModel()
    SentimentAnalyzer(model, batch_size=32).analyze(_frame(100))
    assert len(model.calls) == 4


def test_ac3_empty_comment_is_skipped_and_excluded_from_distribution() -> None:
    frame = pd.DataFrame({"comment_id": ["a", "b", "c"], "text": ["i love it", "", "i love it"]})
    model = FakeModel({"love": SentimentPrediction(0.05, 0.15, 0.8, 0.0)})
    result = SentimentAnalyzer(model).analyze(frame)

    skipped = next(c for c in result.comments if c.comment_id == "b")
    assert skipped.skipped is True and skipped.label is None
    assert result.skipped_count == 1
    # distribution is over the 2 scored comments, not 3
    assert result.distribution["positive"] == pytest.approx(100.0)


def test_ac4_failing_batch_is_isolated_and_failed_ratio_is_reported() -> None:
    # 500 comments / batch 50 -> 10 batches; batch index 1 (comments 50-99) fails.
    # 50 / 500 = 10% failure, below the 20% threshold -> a result is returned.
    model = FakeModel(raise_on_batch=1)
    result = SentimentAnalyzer(model, batch_size=50, max_retries=2).analyze(_frame(500))

    failed = [c for c in result.comments if c.failed]
    assert len(failed) == 50
    assert result.failed_ratio == pytest.approx(0.1)
    # the other 9 batches scored normally
    assert sum(1 for c in result.comments if c.label is not None) == 450
    # batch 1 was attempted 3 times (1 + 2 retries); the other 9 batches once each
    assert len(model.calls) == 9 + 3


def test_ac5_failure_above_threshold_raises() -> None:
    model = FakeModel(raise_on_batch=0)  # first (only) batch fails
    with pytest.raises(SentimentAnalysisFailed, match="threshold"):
        SentimentAnalyzer(model, batch_size=50).analyze(_frame(40))


def test_ac6_distribution_percentages_sum_to_100() -> None:
    frame = pd.DataFrame(
        {
            "comment_id": [f"c{i}" for i in range(7)],
            "text": ["pos", "pos", "neg", "neg", "neg", "neu", "neu"],
        }
    )
    model = FakeModel(
        {
            "pos": SentimentPrediction(0.1, 0.2, 0.7, 0.0),
            "neg": SentimentPrediction(0.7, 0.2, 0.1, 0.0),
            "neu": SentimentPrediction(0.2, 0.6, 0.2, 0.0),
        }
    )
    result = SentimentAnalyzer(model).analyze(frame)
    assert sum(result.distribution.values()) == pytest.approx(100.0, abs=0.1)
    assert result.distribution["negative"] == pytest.approx(300 / 7, abs=1e-4)


def test_ac7_trend_bucket_is_hourly_under_a_week_daily_over() -> None:
    model = FakeModel()

    three_days = pd.DataFrame(
        {
            "comment_id": ["a", "b", "c"],
            "text": ["x", "y", "z"],
            "published_at": [
                "2026-03-01T00:00:00Z",
                "2026-03-02T00:00:00Z",
                "2026-03-04T00:00:00Z",
            ],
        }
    )
    assert SentimentAnalyzer(model).analyze(three_days).trend_bucket == "hour"

    thirty_days = three_days.assign(
        published_at=["2026-03-01T00:00:00Z", "2026-03-15T00:00:00Z", "2026-03-31T00:00:00Z"]
    )
    assert SentimentAnalyzer(model).analyze(thirty_days).trend_bucket == "day"


def test_ac8_missing_model_raises_not_defaults() -> None:
    with pytest.raises(SentimentModelNotLoaded):
        SentimentAnalyzer().analyze(_frame(3))


def test_emoji_only_comment_is_skipped() -> None:
    frame = pd.DataFrame({"comment_id": ["a", "b"], "text": ["real text", "😀🎉🔥"]})
    result = SentimentAnalyzer(FakeModel()).analyze(frame)
    assert next(c for c in result.comments if c.comment_id == "b").skipped is True


def test_continuous_score_is_p_pos_minus_p_neg() -> None:
    frame = pd.DataFrame({"comment_id": ["a"], "text": ["hello"]})
    model = FakeModel(SentimentPrediction(negative=0.6, neutral=0.1, positive=0.3, toxicity=0.0))
    result = SentimentAnalyzer(model).analyze(frame)
    assert result.comments[0].score == pytest.approx(-0.3)
    assert result.comments[0].label == "negative"


def test_toxic_ratio_counts_scored_comments_over_threshold() -> None:
    frame = pd.DataFrame({"comment_id": ["a", "b", "c", "d"], "text": ["tox", "ok", "ok", "ok"]})
    model = FakeModel(
        {
            "tox": SentimentPrediction(0.5, 0.3, 0.2, 0.95),
            "ok": SentimentPrediction(0.2, 0.6, 0.2, 0.05),
        }
    )
    result = SentimentAnalyzer(model, toxicity_threshold=0.7).analyze(frame)
    assert result.toxic_ratio == pytest.approx(0.25)


def test_by_community_means_when_column_present() -> None:
    frame = pd.DataFrame(
        {
            "comment_id": ["a", "b", "c"],
            "text": ["pos", "pos", "neg"],
            "community_id": [0, 0, 1],
        }
    )
    model = FakeModel(
        {
            "pos": SentimentPrediction(0.1, 0.1, 0.8, 0.0),
            "neg": SentimentPrediction(0.8, 0.1, 0.1, 0.0),
        }
    )
    result = SentimentAnalyzer(model).analyze(frame)
    assert result.by_community == {0: pytest.approx(0.7), 1: pytest.approx(-0.7)}


def test_long_comment_is_truncated_and_ratio_reported() -> None:
    frame = pd.DataFrame({"comment_id": ["a", "b"], "text": ["short", "x" * 5000]})
    model = FakeModel()
    result = SentimentAnalyzer(model, max_chars=2000).analyze(frame)
    assert len(model.calls[0][1]) == 2000
    assert next(c for c in result.comments if c.comment_id == "b").truncated is True
    assert result.truncated_ratio == pytest.approx(0.5)


def test_missing_text_column_raises() -> None:
    with pytest.raises(ValueError, match="text"):
        SentimentAnalyzer(FakeModel()).analyze(pd.DataFrame({"comment_id": ["a"]}))


def test_model_returning_wrong_count_raises() -> None:
    def bad_model(texts: Sequence[str]) -> list[SentimentPrediction]:
        return [_FIXED]  # always one, regardless of batch size

    with pytest.raises(SentimentAnalysisFailed, match="predictions for"):
        SentimentAnalyzer(bad_model).analyze(_frame(5))


def test_all_comments_skipped_yields_zero_distribution() -> None:
    frame = pd.DataFrame({"comment_id": ["a", "b"], "text": ["", "   "]})
    result = SentimentAnalyzer(FakeModel()).analyze(frame)
    assert result.distribution == dict.fromkeys(SENTIMENT_LABELS, 0.0)
    assert result.trend == []
    assert result.failed_ratio == 0.0


def test_no_timestamp_or_community_columns_yield_empty_trend_and_grouping() -> None:
    result = SentimentAnalyzer(FakeModel()).analyze(_frame(3))
    assert result.trend == []
    assert result.trend_bucket == "day"
    assert result.by_community == {}


def test_unparseable_timestamps_and_communities_are_dropped() -> None:
    frame = pd.DataFrame(
        {
            "comment_id": ["a", "b"],
            "text": ["hello", "world"],
            "published_at": ["not-a-date", "also-bad"],
            "community_id": ["x", None],
        }
    )
    result = SentimentAnalyzer(FakeModel()).analyze(frame)
    assert result.trend == []
    assert result.by_community == {}


def test_trend_points_are_ordered_and_aggregated() -> None:
    frame = pd.DataFrame(
        {
            "comment_id": ["a", "b", "c"],
            "text": ["p", "p", "n"],
            "published_at": [
                "2026-05-02T09:00:00Z",
                "2026-05-02T09:30:00Z",
                "2026-05-01T10:00:00Z",
            ],
        }
    )
    model = FakeModel(
        {"p": SentimentPrediction(0.0, 0.2, 0.8, 0.0), "n": SentimentPrediction(0.8, 0.2, 0.0, 0.0)}
    )
    trend = SentimentAnalyzer(model).analyze(frame).trend
    assert [point.count for point in trend] == [1, 2]
    assert trend[0].bucket_start < trend[1].bucket_start
