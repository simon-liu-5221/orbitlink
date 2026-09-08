"""Parse a user-supplied YouTube link into a target (spec PR-01).

Pure: no network, table-driven-testable (PR-01 AC-2 / AC-3).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import parse_qs, urlparse

TargetKind = Literal["video", "channel", "handle"]

_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_CHANNEL_ID = re.compile(r"^UC[A-Za-z0-9_-]{22}$")
_HANDLE = re.compile(r"^[A-Za-z0-9_.\-]{3,30}$")

_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
}
_VIDEO_PATH_PREFIXES = {"shorts", "live", "embed", "v"}

_EXAMPLES = (
    "https://www.youtube.com/watch?v=VIDEOID  ·  https://youtu.be/VIDEOID  ·  "
    "https://www.youtube.com/@handle  ·  https://www.youtube.com/channel/UC..."
)


@dataclass(frozen=True)
class YouTubeTarget:
    kind: TargetKind
    #: video id, ``UC...`` channel id, or handle (without the leading ``@``)
    value: str


class InvalidYouTubeURLError(ValueError):
    def __init__(self, reason: str) -> None:
        super().__init__(f"{reason}. Expected one of: {_EXAMPLES}")


def parse_youtube_url(url: str) -> YouTubeTarget:
    raw = (url or "").strip()
    if not raw:
        raise InvalidYouTubeURLError("empty link")

    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = parsed.netloc.lower().split(":")[0]
    if host not in _HOSTS:
        raise InvalidYouTubeURLError(f"{parsed.netloc or raw!r} is not a YouTube link")

    segments = [s for s in parsed.path.split("/") if s]

    if host == "youtu.be":
        return _video(segments[0]) if segments else _bad("no video id in the youtu.be link")

    if segments and segments[0] == "watch":
        values = parse_qs(parsed.query).get("v", [])
        return _video(values[0]) if values else _bad("watch link has no ?v= parameter")

    if len(segments) >= 2 and segments[0] in _VIDEO_PATH_PREFIXES:
        return _video(segments[1])

    if len(segments) >= 2 and segments[0] == "channel":
        if _CHANNEL_ID.match(segments[1]):
            return YouTubeTarget("channel", segments[1])
        return _bad(f"{segments[1]!r} is not a valid channel id")

    if segments and segments[0].startswith("@"):
        handle = segments[0][1:]
        if _HANDLE.match(handle):
            return YouTubeTarget("handle", handle)
        return _bad(f"{segments[0]!r} is not a valid handle")

    if segments and segments[0] in {"c", "user"}:
        return _bad(
            "legacy /c/ and /user/ URLs aren't supported — paste the @handle or /channel/UC... URL"
        )

    return _bad("could not find a video, channel, or handle in the link")


def _video(candidate: str) -> YouTubeTarget:
    if _VIDEO_ID.match(candidate):
        return YouTubeTarget("video", candidate)
    return _bad(f"{candidate!r} is not a valid video id")


def _bad(reason: str) -> YouTubeTarget:
    raise InvalidYouTubeURLError(reason)
