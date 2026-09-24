"""M8 — stratified sampling for the sentiment evaluation set.

Buckets by a rough language heuristic (has-CJK / has-ASCII-letters) so the
sample doesn't accidentally end up all-English just because that's what
dominates the raw pool — AN-03's own scope explicitly cares about English /
Chinese / mixed performance separately (docs/algorithm-validation.md §3.5).

    uv run python scripts/eval_sentiment/sample.py \
        --input scripts/eval_sentiment/data/raw_comments.json \
        --target 180 \
        -o scripts/eval_sentiment/data/sample.json
"""

from __future__ import annotations

import argparse
import json
import random
import re
import unicodedata
from pathlib import Path

_CJK = re.compile(r"[一-鿿㐀-䶿]")
_ASCII_LETTER = re.compile(r"[A-Za-z]")

# Roughly proportion the sample across buckets; adjusted down per-bucket if the
# raw pool doesn't have enough of one kind (see `_take`).
_BUCKET_WEIGHTS = {"english": 0.4, "chinese": 0.3, "mixed": 0.3}


def _lang_bucket(text: str) -> str:
    has_cjk = bool(_CJK.search(text))
    has_ascii = bool(_ASCII_LETTER.search(text))
    if has_cjk and has_ascii:
        return "mixed"
    if has_cjk:
        return "chinese"
    return "english"


def _is_meaningful(text: str) -> bool:
    return any(unicodedata.category(ch)[0] in {"L", "N"} for ch in text)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="scripts/eval_sentiment/data/raw_comments.json")
    parser.add_argument("--target", type=int, default=180)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("-o", "--output", default="scripts/eval_sentiment/data/sample.json")
    args = parser.parse_args()

    raw = json.loads(Path(args.input).read_text(encoding="utf-8"))

    seen_text: set[str] = set()
    buckets: dict[str, list[dict]] = {"english": [], "chinese": [], "mixed": []}
    for row in raw:
        text = (row["text"] or "").strip()
        if not _is_meaningful(text) or len(text) < 3:
            continue
        if text in seen_text:
            continue
        seen_text.add(text)
        buckets[_lang_bucket(text)].append(row)

    rng = random.Random(args.seed)
    for bucket in buckets.values():
        rng.shuffle(bucket)

    picked: list[dict] = []
    for name, weight in _BUCKET_WEIGHTS.items():
        want = round(args.target * weight)
        picked.extend(buckets[name][:want])

    # If a bucket came up short (e.g. no Chinese comments on this video),
    # top up from whichever bucket still has a surplus rather than silently
    # shipping a smaller sample.
    shortfall = args.target - len(picked)
    if shortfall > 0:
        leftovers = [
            row
            for name in _BUCKET_WEIGHTS
            for row in buckets[name][round(args.target * _BUCKET_WEIGHTS[name]) :]
        ]
        rng.shuffle(leftovers)
        picked.extend(leftovers[:shortfall])

    rng.shuffle(picked)

    sample = [
        {"index": i, "id": row["id"], "text": row["text"], "lang_bucket": _lang_bucket(row["text"])}
        for i, row in enumerate(picked)
    ]

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8")

    counts = {name: sum(1 for s in sample if s["lang_bucket"] == name) for name in _BUCKET_WEIGHTS}
    print(f"pool sizes: { {k: len(v) for k, v in buckets.items()} }")
    print(f"sampled {len(sample)} comments: {counts}")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
