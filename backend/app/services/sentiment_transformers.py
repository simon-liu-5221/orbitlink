"""Real sentiment + toxicity models (ADR-0004).

Only imported when ``use_real_sentiment_model`` is on and ``transformers`` +
``torch`` are installed. Not covered by CI — its accuracy is evaluated for real
in M8 (docs/algorithm-validation.md §3).

    uv pip install transformers torch
"""

from __future__ import annotations

import functools
from collections.abc import Sequence
from typing import Any

from app.analysis.types import SentimentPrediction

_SENTIMENT_MODEL = "cardiffnlp/twitter-xlm-roberta-base-sentiment"
_TOXICITY_MODEL = "unitary/multilingual-toxic-xlm-roberta"
_MAX_TOKENS = 512


@functools.lru_cache(maxsize=1)
def _pipelines() -> tuple[Any, Any]:
    from transformers import pipeline

    sentiment = pipeline(
        "sentiment-analysis",
        model=_SENTIMENT_MODEL,
        top_k=None,
        truncation=True,
        max_length=_MAX_TOKENS,
    )
    toxicity = pipeline(
        "text-classification",
        model=_TOXICITY_MODEL,
        top_k=None,
        truncation=True,
        max_length=_MAX_TOKENS,
    )
    return sentiment, toxicity


def transformers_predict(texts: Sequence[str]) -> list[SentimentPrediction]:
    sentiment_pipe, toxicity_pipe = _pipelines()
    batch = list(texts)
    sentiment_out = sentiment_pipe(batch)
    toxicity_out = toxicity_pipe(batch)

    results: list[SentimentPrediction] = []
    for sent_scores, tox_scores in zip(sentiment_out, toxicity_out, strict=True):
        probs = {row["label"].lower(): float(row["score"]) for row in sent_scores}
        tox = {row["label"].lower(): float(row["score"]) for row in tox_scores}
        results.append(
            SentimentPrediction(
                negative=probs.get("negative", 0.0),
                neutral=probs.get("neutral", 0.0),
                positive=probs.get("positive", 0.0),
                toxicity=tox.get("toxic", tox.get("toxicity", 0.0)),
            )
        )
    return results
