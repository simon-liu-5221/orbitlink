"""Pick the sentiment model for an analysis run (decision B1).

Default: the lexicon stand-in (no heavy deps, deterministic, runs in CI).
``use_real_sentiment_model``: the XLM-RoBERTa + toxicity models (ADR-0004),
loaded lazily so the import cost is only paid when actually enabled. The real
loader raises a clear error if the optional ``transformers`` extra is missing.
"""

from __future__ import annotations

import logging

from app.analysis.sentiment import PredictFn, SentimentAnalyzer
from app.analysis.sentiment_lexicon import lexicon_predict
from app.core.config import Settings

logger = logging.getLogger(__name__)

#: Whether the analyzer in use is the real model. Persisted alongside results so
#: the UI can label stand-in output honestly.
STANDIN_LABEL = "lexicon-standin"
REAL_LABEL = "xlm-roberta"


def build_sentiment_analyzer(settings: Settings) -> tuple[SentimentAnalyzer, str]:
    """Return ``(analyzer, model_label)``."""
    if settings.use_real_sentiment_model:
        return SentimentAnalyzer(_load_real_model()), REAL_LABEL
    logger.info("sentiment: using the lexicon stand-in (not the real model)")
    return SentimentAnalyzer(lexicon_predict), STANDIN_LABEL


def _load_real_model() -> PredictFn:  # pragma: no cover - exercised only when enabled
    try:
        from app.services.sentiment_transformers import transformers_predict
    except ImportError as exc:  # transformers/torch not installed
        raise RuntimeError(
            "use_real_sentiment_model is on but transformers/torch are not "
            "installed — run `uv pip install transformers torch` (decision B1)"
        ) from exc
    return transformers_predict
