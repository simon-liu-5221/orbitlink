"""YouTube ingestion (spec PR-01).

- ``urls.parse_youtube_url`` — pure link parsing
- ``pseudonym.pseudonymize`` — HMAC author-id pseudonymisation (data-ethics.md)
- ``youtube.YouTubeClient`` — Data API v3 comment fetching
"""

from app.ingest.pseudonym import pseudonymize
from app.ingest.urls import InvalidYouTubeURLError, YouTubeTarget, parse_youtube_url
from app.ingest.youtube import FetchResult, RawComment, YouTubeClient, YouTubeError

__all__ = [
    "FetchResult",
    "InvalidYouTubeURLError",
    "RawComment",
    "YouTubeClient",
    "YouTubeError",
    "YouTubeTarget",
    "parse_youtube_url",
    "pseudonymize",
]
