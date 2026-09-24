"""M8 — fetches real comments straight from the YouTube Data API for the
sentiment-model evaluation set (ADR-0004 / AN-03 AC-9) and the case study.

Deliberately bypasses the app's own ingest -> analyze -> delete pipeline:
docs/data-ethics.md's raw-comment-deletion policy protects real users' data in
the production system, and doesn't apply to a one-off, offline research file
built for this validation. Only public comment text + like count are kept —
no author names, no channel ids, nothing that could re-identify a commenter.

    export YOUTUBE_API_KEY=...   # from the repo-root .env
    uv run python scripts/eval_sentiment/fetch_comments.py \
        "https://youtube.com/watch?v=..." \
        --max-comments 800 \
        -o scripts/eval_sentiment/data/raw_comments.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.ingest.urls import parse_youtube_url
from app.ingest.youtube import YouTubeClient


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="a YouTube video or channel URL")
    parser.add_argument("--max-comments", type=int, default=800)
    parser.add_argument("--channel-video-count", type=int, default=15)
    parser.add_argument(
        "-o",
        "--output",
        default="scripts/eval_sentiment/data/raw_comments.json",
    )
    args = parser.parse_args()

    api_key = os.environ.get("YOUTUBE_API_KEY", "")
    if not api_key:
        raise SystemExit("YOUTUBE_API_KEY is not set in the environment")

    target = parse_youtube_url(args.url)
    client = YouTubeClient(api_key)
    result = client.fetch(
        target,
        max_comments=args.max_comments,
        channel_video_count=args.channel_video_count,
    )

    rows = [
        {
            "id": c.comment_id,
            "text": c.text,
            "like_count": c.like_count,
            "is_reply": c.parent_id is not None,
        }
        for c in result.comments
    ]

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"fetched {len(rows)} comments from {len(result.video_ids)} video(s)")
    print(f"quota used: {result.quota_used}")
    if result.truncated:
        print("note: hit --max-comments before exhausting the source")
    if result.comments_disabled_videos:
        print(f"skipped (comments disabled): {result.comments_disabled_videos}")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
