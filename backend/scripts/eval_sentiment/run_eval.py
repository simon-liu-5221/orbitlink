"""M8 — computes accuracy / macro F1 / weighted F1 / per-class P-R-F1 /
confusion matrix for each candidate sentiment predictor against the human
labels (ADR-0004, AN-03 AC-9), overall and broken down by language bucket.

    uv run python scripts/eval_sentiment/run_eval.py \
        --sample scripts/eval_sentiment/data/sample.json \
        --labels scripts/eval_sentiment/data/labels.json \
        --systems lexicon,transformers,vader \
        -o scripts/eval_sentiment/data/results.json

Same label-from-probabilities rule production uses
(app/analysis/sentiment.py's ``_to_comment_sentiment``): argmax over
negative/neutral/positive.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
)

from app.analysis.sentiment_lexicon import lexicon_predict
from app.analysis.types import SENTIMENT_LABELS, SentimentPrediction

_PREDICT_FNS = {"lexicon": lexicon_predict}


def _get_transformers_predict():
    from app.services.sentiment_transformers import transformers_predict

    return transformers_predict


def _get_vader_predict():
    from scripts.eval_sentiment.predictors import vader_predict

    return vader_predict


_LAZY_PREDICT_FNS = {"transformers": _get_transformers_predict, "vader": _get_vader_predict}


def _argmax_label(pred: SentimentPrediction) -> str:
    return max(SENTIMENT_LABELS, key=lambda name: getattr(pred, name))


def _metrics_for(y_true: list[str], y_pred: list[str]) -> dict:
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=list(SENTIMENT_LABELS), zero_division=0
    )
    macro_f1 = float(sum(f1) / len(f1))
    _, _, weighted_f1, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=list(SENTIMENT_LABELS), average="weighted", zero_division=0
    )
    cm = confusion_matrix(y_true, y_pred, labels=list(SENTIMENT_LABELS)).tolist()
    return {
        "n": len(y_true),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": macro_f1,
        "weighted_f1": float(weighted_f1),
        "per_class": {
            label: {
                "precision": float(precision[i]),
                "recall": float(recall[i]),
                "f1": float(f1[i]),
                "support": int(support[i]),
            }
            for i, label in enumerate(SENTIMENT_LABELS)
        },
        "confusion_matrix": {"labels": list(SENTIMENT_LABELS), "matrix": cm},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", default="scripts/eval_sentiment/data/sample.json")
    parser.add_argument("--labels", default="scripts/eval_sentiment/data/labels.json")
    parser.add_argument("--systems", default="lexicon,transformers,vader")
    parser.add_argument("-o", "--output", default="scripts/eval_sentiment/data/results.json")
    args = parser.parse_args()

    sample = {
        item["index"]: item for item in json.loads(Path(args.sample).read_text(encoding="utf-8"))
    }
    labels: dict[str, str] = json.loads(Path(args.labels).read_text(encoding="utf-8"))

    items = [
        {**sample[int(idx)], "gold": gold}
        for idx, gold in labels.items()
        if gold != "skipped" and int(idx) in sample
    ]
    if not items:
        raise SystemExit("no labeled (non-skipped) items found")

    texts = [item["text"] for item in items]
    gold = [item["gold"] for item in items]
    buckets = [item["lang_bucket"] for item in items]

    requested = args.systems.split(",")
    results: dict = {"n_labeled": len(items), "systems": {}}

    for system in requested:
        if system in _PREDICT_FNS:
            predict_fn = _PREDICT_FNS[system]
        elif system in _LAZY_PREDICT_FNS:
            try:
                predict_fn = _LAZY_PREDICT_FNS[system]()
            except ImportError as exc:
                print(f"skipping {system}: {exc}")
                continue
        else:
            print(f"unknown system: {system}")
            continue

        print(f"running {system}...")
        predictions = predict_fn(texts)
        pred_labels = [_argmax_label(p) for p in predictions]

        by_scope: dict[str, dict] = {"overall": _metrics_for(gold, pred_labels)}
        for scope in ("english", "chinese", "mixed"):
            idxs = [i for i, b in enumerate(buckets) if b == scope]
            if idxs:
                by_scope[scope] = _metrics_for(
                    [gold[i] for i in idxs], [pred_labels[i] for i in idxs]
                )
        results["systems"][system] = by_scope

        overall = by_scope["overall"]
        print(
            f"  {system}: accuracy={overall['accuracy']:.3f} "
            f"macro_f1={overall['macro_f1']:.3f} weighted_f1={overall['weighted_f1']:.3f}"
        )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
