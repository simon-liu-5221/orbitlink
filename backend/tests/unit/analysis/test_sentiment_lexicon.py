"""The M2 lexicon sentiment stand-in (decision B1)."""

from __future__ import annotations

from app.analysis.sentiment_lexicon import lexicon_predict


def _label(text: str) -> str:
    p = lexicon_predict([text])[0]
    return max(
        (("negative", p.negative), ("neutral", p.neutral), ("positive", p.positive)),
        key=lambda kv: kv[1],
    )[0]


def test_clearly_positive_text() -> None:
    assert _label("this is amazing, I love it, best video ever") == "positive"


def test_clearly_negative_text() -> None:
    assert _label("terrible, awful, worst thing I have ever watched, waste of time") == "negative"


def test_neutral_when_no_sentiment_words() -> None:
    assert _label("the video is about twelve minutes long") == "neutral"


def test_probabilities_roughly_sum_to_one() -> None:
    # the stand-in rounds to 4dp, so exact normalisation isn't guaranteed
    for text in ("great stuff", "boring nonsense", "just some words here"):
        p = lexicon_predict([text])[0]
        assert abs(p.negative + p.neutral + p.positive - 1.0) < 1e-3


def test_toxic_language_raises_toxicity() -> None:
    clean = lexicon_predict(["nice work everyone"])[0]
    toxic = lexicon_predict(["you are an idiot and a moron, shut up"])[0]
    assert toxic.toxicity > 0.5
    assert clean.toxicity == 0.0


def test_batch_shape() -> None:
    out = lexicon_predict(["a", "b", "c"])
    assert len(out) == 3
