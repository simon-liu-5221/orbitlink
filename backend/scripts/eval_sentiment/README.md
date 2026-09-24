# Sentiment model evaluation (M8, ADR-0004, AN-03 AC-9)

Real human labels are the entire point — nothing here fabricates them. This
directory is tooling to make that labeling efficient and the resulting F1
numbers reproducible, not a shortcut around doing it.

## Why the sample is 150–200, not the spec's original 500

AC-9 originally asked for 500 hand-labeled comments. Labeling that many by
hand (judging sentiment, sometimes across languages) is realistically several
hours of solo work. This uses a smaller, deliberately **stratified** sample
instead — 3 language buckets (English / Chinese / mixed), sampled so no
bucket gets crowded out by whatever the raw comment pool happens to be
dominated by — and says so plainly in `docs/algorithm-validation.md` rather
than quietly shipping a smaller number under the original claim.

## Pipeline

```bash
cd backend

# 1. fetch real comments straight from the YouTube Data API (bypasses the
#    app's own ingest->analyze->delete pipeline on purpose — see
#    fetch_comments.py's docstring)
export YOUTUBE_API_KEY=...   # from the repo-root .env
uv run python scripts/eval_sentiment/fetch_comments.py \
    "<video or channel url>" --max-comments 800

# 2. stratified sample -> scripts/eval_sentiment/data/sample.json
uv run python scripts/eval_sentiment/sample.py --target 180

# 3. label them yourself — resumable, saves after every answer
uv run python scripts/eval_sentiment/label_cli.py

# 4. once labeling is done, score every candidate model against your labels
#    (needs the real model's deps — see app/services/sentiment_transformers.py
#    for the exact pinned versions; vaderSentiment for the baseline)
uv run python scripts/eval_sentiment/run_eval.py \
    --systems lexicon,transformers,vader
```

`run_eval.py` writes `data/results.json`: accuracy / macro F1 / weighted F1 /
per-class precision-recall-F1 / confusion matrix, for each system, both
overall and broken down by language bucket — the shape
`docs/algorithm-validation.md` §3 is written from.

## What's committed vs. not

- `data/raw_comments.json` (the full unsampled fetch) — gitignored, easily
  regenerated, and there's no reason to keep every comment a video has.
- `data/sample.json`, `data/labels.json`, `data/results.json` — committed once
  they hold real data. This is the actual evidence behind the numbers in
  `docs/algorithm-validation.md`; hiding it would defeat the point of doing a
  real evaluation instead of asserting one.

## Systems compared

- `lexicon` — the stand-in actually deployed by default (decision B1, no
  heavy deps). English-only keyword matching; expected to do badly on
  Chinese/mixed.
- `transformers` — the real model ADR-0004 decided on
  (`cardiffnlp/twitter-xlm-roberta-base-sentiment`). Needs `transformers` +
  `torch` installed locally; not part of the deployed image.
- `vader` — ADR-0004's own baseline. English-only, rule-based; included so
  "we beat a trivial baseline" is an actual measured claim, not an assertion.
