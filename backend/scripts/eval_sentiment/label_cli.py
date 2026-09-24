"""M8 — a resumable CLI for the human labeling ADR-0004 asks for.

Not something an LLM can do on your behalf: the whole point of this
evaluation is a real, independent human judgment call to compare the model
predictions against — a machine-generated "ground truth" would just be
fabricating the very thing this measures.

Shows one comment at a time; every answer is saved to disk immediately (Ctrl-C
or `q` any time — nothing already labeled is lost, and re-running picks up
where you left off).

    uv run python scripts/eval_sentiment/label_cli.py \
        --sample scripts/eval_sentiment/data/sample.json \
        --labels scripts/eval_sentiment/data/labels.json

Labels: p = positive, n = negative, u = neutral, s = skip (not really
sentiment-bearing — spam, a link, pure emoji), q = quit and save.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

_KEYS = {"p": "positive", "n": "negative", "u": "neutral", "s": "skipped"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", default="scripts/eval_sentiment/data/sample.json")
    parser.add_argument("--labels", default="scripts/eval_sentiment/data/labels.json")
    args = parser.parse_args()

    sample = json.loads(Path(args.sample).read_text(encoding="utf-8"))
    labels_path = Path(args.labels)
    labels: dict[str, str] = (
        json.loads(labels_path.read_text(encoding="utf-8")) if labels_path.exists() else {}
    )

    remaining = [item for item in sample if str(item["index"]) not in labels]
    total = len(sample)

    print(f"{len(labels)}/{total} already labeled. {len(remaining)} left.")
    print("p=positive  n=negative  u=neutral  s=skip (not sentiment-bearing)  q=quit\n")

    for item in remaining:
        print(f"--- [{item['lang_bucket']}] ({len(labels)}/{total}) ---")
        print(item["text"])
        while True:
            choice = input("> ").strip().lower()
            if choice == "q":
                labels_path.parent.mkdir(parents=True, exist_ok=True)
                labels_path.write_text(
                    json.dumps(labels, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                print(f"saved {len(labels)}/{total}. resume any time.")
                return
            if choice in _KEYS:
                labels[str(item["index"])] = _KEYS[choice]
                labels_path.parent.mkdir(parents=True, exist_ok=True)
                labels_path.write_text(
                    json.dumps(labels, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                break
            print("p / n / u / s / q")
        print()

    print(f"done: {len(labels)}/{total} labeled.")


if __name__ == "__main__":
    main()
