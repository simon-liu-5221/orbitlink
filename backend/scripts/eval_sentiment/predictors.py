"""Adapters so every candidate model shares one ``predict_fn`` shape
(``Sequence[str] -> Sequence[SentimentPrediction]``) — the same interface
production injects into ``SentimentAnalyzer`` (app/analysis/sentiment.py).
"""

from __future__ import annotations

from collections.abc import Sequence

from app.analysis.types import SentimentPrediction


def vader_predict(texts: Sequence[str]) -> list[SentimentPrediction]:
    """VADER — the ADR-0004 baseline. English-only, lexicon + rules; expected
    to fall over on Chinese/mixed text, which is exactly the comparison point.
    """
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

    analyzer = SentimentIntensityAnalyzer()
    results = []
    for text in texts:
        scores = analyzer.polarity_scores(text)
        results.append(
            SentimentPrediction(
                negative=scores["neg"],
                neutral=scores["neu"],
                positive=scores["pos"],
                toxicity=0.0,
            )
        )
    return results
