"""YouTube Data API v3 client — fetch comments for a video or channel (PR-01).

Not part of the pure analysis layer: this module does I/O. It hands the service
layer plain ``RawComment`` rows; pseudonymisation and graph building happen
downstream.

Quota: ``channels.list`` / ``playlistItems.list`` / ``commentThreads.list`` are
1 unit each. The default 10,000-unit daily quota is rarely the real limit —
wall-clock time to page through comments is.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

from app.ingest.urls import YouTubeTarget

# YouTube API JSON is dynamic; parsing helpers work in terms of Any.
Json = dict[str, Any]

_API_ROOT = "https://www.googleapis.com/youtube/v3"
_PAGE_SIZE = 100
_QUOTA_REASONS = {"quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded"}


@dataclass(frozen=True)
class RawComment:
    comment_id: str
    parent_id: str | None
    author_channel_id: str
    author_display_name: str
    text: str
    like_count: int
    published_at: datetime | None


@dataclass
class FetchResult:
    comments: list[RawComment] = field(default_factory=list)
    video_ids: list[str] = field(default_factory=list)
    quota_used: int = 0
    #: Hit ``max_comments`` before exhausting the source.
    truncated: bool = False
    #: A thread had more replies than the API returned inline (>5).
    replies_truncated: bool = False
    #: Videos skipped because their comments are disabled.
    comments_disabled_videos: list[str] = field(default_factory=list)


class YouTubeError(RuntimeError):
    """A YouTube API failure mapped to a stable ``error_code`` (PR-01)."""

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(f"{error_code}: {message}")
        self.error_code = error_code


class YouTubeClient:
    def __init__(
        self,
        api_key: str,
        *,
        http: httpx.Client | None = None,
        page_size: int = _PAGE_SIZE,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self._api_key = api_key
        self._http = http or httpx.Client(base_url=_API_ROOT, timeout=30.0)
        self._page_size = page_size
        self._quota_used = 0

    # -- public ----------------------------------------------------------

    def fetch(
        self,
        target: YouTubeTarget,
        *,
        max_comments: int = 5000,
        channel_video_count: int = 10,
    ) -> FetchResult:
        result = FetchResult()
        if target.kind == "video":
            result.video_ids = [target.value]
        else:
            channel_id = self._resolve_channel_id(target)
            result.video_ids = self._recent_video_ids(channel_id, channel_video_count)

        for video_id in result.video_ids:
            if len(result.comments) >= max_comments:
                result.truncated = True
                break
            try:
                self._collect_video_comments(video_id, max_comments, result)
            except YouTubeError as exc:
                # For a channel, skip the odd video with comments off and carry on.
                # For a single-video target, the error is the whole result (PR-01).
                if exc.error_code == "COMMENTS_DISABLED" and target.kind != "video":
                    result.comments_disabled_videos.append(video_id)
                    continue
                raise

        if len(result.comments) > max_comments:
            del result.comments[max_comments:]
            result.truncated = True
        result.quota_used = self._quota_used
        return result

    # -- resolution ----------------------------------------------------

    def _resolve_channel_id(self, target: YouTubeTarget) -> str:
        if target.kind == "channel":
            return target.value
        params = {"part": "id", "forHandle": f"@{target.value}"}
        data = self._get("channels", params)
        items = data.get("items") or []
        if not items:
            raise YouTubeError("RESOURCE_NOT_FOUND", f"no channel for handle @{target.value}")
        return str(items[0]["id"])

    def _recent_video_ids(self, channel_id: str, count: int) -> list[str]:
        uploads_playlist = "UU" + channel_id[2:]
        video_ids: list[str] = []
        page_token: str | None = None
        while len(video_ids) < count:
            params: dict[str, str | int] = {
                "part": "contentDetails",
                "playlistId": uploads_playlist,
                "maxResults": min(50, count - len(video_ids)),
            }
            if page_token:
                params["pageToken"] = page_token
            data = self._get("playlistItems", params)
            for item in data.get("items") or []:
                video_ids.append(str(item["contentDetails"]["videoId"]))
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        return video_ids[:count]

    # -- comments ----------------------------------------------------

    def _collect_video_comments(
        self, video_id: str, max_comments: int, result: FetchResult
    ) -> None:
        page_token: str | None = None
        while len(result.comments) < max_comments:
            params: dict[str, str | int] = {
                "part": "snippet,replies",
                "videoId": video_id,
                "maxResults": self._page_size,
                "order": "relevance",
                "textFormat": "plainText",
            }
            if page_token:
                params["pageToken"] = page_token
            data = self._get("commentThreads", params)
            for item in data.get("items") or []:
                for comment in _parse_thread(item):
                    result.comments.append(comment)
                if _thread_replies_truncated(item):
                    result.replies_truncated = True
            page_token = data.get("nextPageToken")
            if not page_token:
                break

    # -- transport ---------------------------------------------------

    def _get(self, path: str, params: Mapping[str, str | int]) -> Json:
        response = self._http.get(f"{_API_ROOT}/{path}", params={**params, "key": self._api_key})
        if response.status_code == 200:
            self._quota_used += 1
            payload: Json = response.json()
            return payload
        raise _map_error(response)


def _map_error(response: httpx.Response) -> YouTubeError:
    try:
        error = response.json().get("error", {})
        reasons = {e.get("reason", "") for e in error.get("errors", [])}
        message = str(error.get("message") or response.text)
    except ValueError:
        reasons, message = set(), response.text

    if reasons & _QUOTA_REASONS:
        return YouTubeError("QUOTA_EXCEEDED", message)
    if "commentsDisabled" in reasons:
        return YouTubeError("COMMENTS_DISABLED", message)
    if response.status_code == 404 or "videoNotFound" in reasons or "channelNotFound" in reasons:
        return YouTubeError("RESOURCE_NOT_FOUND", message)
    if response.status_code == 403 and {"keyInvalid", "forbidden"} & reasons:
        return YouTubeError("CONFIG_ERROR", message)
    return YouTubeError("YOUTUBE_ERROR", f"HTTP {response.status_code}: {message}")


def _parse_thread(item: Json) -> list[RawComment]:
    snippet = _as_dict(item.get("snippet"))
    top = _as_dict(snippet.get("topLevelComment"))
    comments = [_parse_comment(top, parent_id=None)]
    replies = _as_dict(item.get("replies"))
    for reply in replies.get("comments") or []:
        comments.append(_parse_comment(_as_dict(reply), parent_id=comments[0].comment_id))
    return comments


def _parse_comment(node: Json, *, parent_id: str | None) -> RawComment:
    comment_id = str(node.get("id", ""))
    snippet = _as_dict(node.get("snippet"))
    author_channel = _as_dict(snippet.get("authorChannelId"))
    return RawComment(
        comment_id=comment_id,
        parent_id=str(snippet.get("parentId")) if snippet.get("parentId") else parent_id,
        author_channel_id=str(author_channel.get("value") or "anonymous"),
        author_display_name=str(snippet.get("authorDisplayName") or ""),
        text=str(snippet.get("textOriginal") or snippet.get("textDisplay") or ""),
        like_count=int(snippet.get("likeCount") or 0),
        published_at=_parse_ts(snippet.get("publishedAt")),
    )


def _thread_replies_truncated(item: Json) -> bool:
    snippet = _as_dict(item.get("snippet"))
    total = int(snippet.get("totalReplyCount") or 0)
    inline = len(_as_dict(item.get("replies")).get("comments") or [])
    return total > inline


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _as_dict(value: Any) -> Json:
    return value if isinstance(value, dict) else {}
