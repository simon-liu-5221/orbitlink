"""A tiny lexicon sentiment/toxicity model — the M2 stand-in (decision B1).

This is **not** the real model. It is a deterministic, dependency-free
``predict_fn`` so the whole pipeline runs in CI and local dev without pulling in
transformers/torch. The real XLM-RoBERTa + toxicity models (ADR-0004) sit behind
``SETTINGS.use_real_sentiment_model`` and are evaluated for real in M8. English
only, keyword matching — it will be wrong a lot, which is why its output is
labelled a stand-in wherever it surfaces.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.analysis.types import SentimentPrediction

_TOKEN = re.compile(r"[a-z']+")

_POSITIVE = frozenset(
    [
        "good",
        "great",
        "love",
        "loved",
        "lovely",
        "excellent",
        "amazing",
        "awesome",
        "best",
        "wonderful",
        "happy",
        "nice",
        "thanks",
        "thank",
        "thankyou",
        "beautiful",
        "perfect",
        "brilliant",
        "fantastic",
        "enjoy",
        "enjoyed",
        "favorite",
        "favourite",
        "helpful",
        "cool",
        "incredible",
        "superb",
        "underrated",
        "masterpiece",
        "goat",
        "respect",
        "legend",
        "inspiring",
        "wholesome",
    ]
)
_NEGATIVE = frozenset(
    [
        "bad",
        "worse",
        "worst",
        "hate",
        "hated",
        "terrible",
        "awful",
        "horrible",
        "disappointing",
        "disappointed",
        "boring",
        "bored",
        "sad",
        "angry",
        "annoyed",
        "annoying",
        "waste",
        "wasted",
        "broken",
        "poor",
        "wrong",
        "fail",
        "failed",
        "ugly",
        "cringe",
        "trash",
        "garbage",
        "nonsense",
        "overrated",
        "ruined",
        "disgusting",
        "mess",
        "unwatchable",
        "pointless",
    ]
)
_TOXIC_PHRASES = (
    "shut up",
    "kill yourself",
    "you people",
    "hate you",
)
_TOXIC_WORDS = frozenset(
    [
        "idiot",
        "idiots",
        "moron",
        "morons",
        "stupid",
        "dumb",
        "loser",
        "losers",
        "pathetic",
        "scum",
        "clown",
        "braindead",
        "braindead",
    ]
)


def lexicon_predict(texts: Sequence[str]) -> list[SentimentPrediction]:
    return [_score(text) for text in texts]


def _score(text: str) -> SentimentPrediction:
    lowered = text.lower()
    tokens = _TOKEN.findall(lowered)
    positive = sum(1 for token in tokens if token in _POSITIVE)
    negative = sum(1 for token in tokens if token in _NEGATIVE)

    total = positive + negative
    if total == 0:
        p_neg, p_neu, p_pos = 0.15, 0.70, 0.15
    else:
        p_pos = 0.1 + 0.8 * positive / total
        p_neg = 0.1 + 0.8 * negative / total
        p_neu = max(0.05, 1.0 - p_pos - p_neg)
        scale = p_pos + p_neg + p_neu
        p_pos, p_neg, p_neu = p_pos / scale, p_neg / scale, p_neu / scale

    toxic_hits = sum(1 for word in tokens if word in _TOXIC_WORDS)
    toxic_hits += sum(1 for phrase in _TOXIC_PHRASES if phrase in lowered)
    toxicity = min(1.0, 0.45 * toxic_hits)

    return SentimentPrediction(
        negative=round(p_neg, 4),
        neutral=round(p_neu, 4),
        positive=round(p_pos, 4),
        toxicity=round(toxicity, 4),
    )
