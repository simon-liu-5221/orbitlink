"""YouTube Data API client — driven by an in-memory fake over httpx.MockTransport.

No network. Covers pagination, quota counting, reply parsing, the comment cap,
and error mapping (PR-01 exception flows).
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.ingest.urls import YouTubeTarget
from app.ingest.youtube import YouTubeClient, YouTubeError


def _thread(
    cid: str,
    author: str,
    text: str,
    *,
    likes: int = 0,
    replies: list[dict[str, Any]] | None = None,
    total_replies: int | None = None,
) -> dict[str, Any]:
    reply_nodes = [
        {
            "id": r["id"],
            "snippet": {
                "parentId": cid,
                "authorChannelId": {"value": r["author"]},
                "authorDisplayName": r["author"],
                "textOriginal": r["text"],
                "likeCount": r.get("likes", 0),
                "publishedAt": "2026-01-02T00:00:00Z",
            },
        }
        for r in (replies or [])
    ]
    item: dict[str, Any] = {
        "snippet": {
            "topLevelComment": {
                "id": cid,
                "snippet": {
                    "authorChannelId": {"value": author},
                    "authorDisplayName": author,
                    "textOriginal": text,
                    "likeCount": likes,
                    "publishedAt": "2026-01-01T00:00:00Z",
                },
            },
            "totalReplyCount": total_replies if total_replies is not None else len(reply_nodes),
        }
    }
    if reply_nodes:
        item["replies"] = {"comments": reply_nodes}
    return item


class FakeYouTube:
    def __init__(self) -> None:
        self.page_size = 2
        self.channels: dict[str, str] = {}
        self.videos: dict[str, list[str]] = {}
        self.comments: dict[str, list[dict[str, Any]]] = {}
        self.endpoint_error: dict[str, httpx.Response] = {}
        self.video_error: dict[str, httpx.Response] = {}

    def client(self) -> YouTubeClient:
        transport = httpx.MockTransport(self)
        return YouTubeClient(
            "test-key", http=httpx.Client(transport=transport), page_size=self.page_size
        )

    def __call__(self, request: httpx.Request) -> httpx.Response:
        endpoint = request.url.path.rsplit("/", 1)[-1]
        params = dict(request.url.params)
        if endpoint in self.endpoint_error:
            return self.endpoint_error[endpoint]

        if endpoint == "channels":
            cid = self.channels.get(params.get("forHandle", ""))
            return httpx.Response(200, json={"items": [{"id": cid}] if cid else []})

        if endpoint == "playlistItems":
            channel_id = "UC" + params["playlistId"][2:]
            return self._page(
                [{"contentDetails": {"videoId": v}} for v in self.videos.get(channel_id, [])],
                params,
            )

        if endpoint == "commentThreads":
            video = params["videoId"]
            if video in self.video_error:
                return self.video_error[video]
            return self._page(self.comments.get(video, []), params)

        return httpx.Response(404, json={"error": {"code": 404, "message": "unknown endpoint"}})

    def _page(self, items: list[dict[str, Any]], params: dict[str, str]) -> httpx.Response:
        start = int(params.get("pageToken", "0"))
        body: dict[str, Any] = {"items": items[start : start + self.page_size]}
        if start + self.page_size < len(items):
            body["nextPageToken"] = str(start + self.page_size)
        return httpx.Response(200, json=body)


def _error(status: int, reason: str) -> httpx.Response:
    return httpx.Response(
        status,
        json={"error": {"code": status, "errors": [{"reason": reason}], "message": reason}},
    )


VIDEO = YouTubeTarget("video", "vid00000001")


def test_fetches_all_comments_across_pages_and_counts_quota() -> None:
    fake = FakeYouTube()
    fake.comments["vid00000001"] = [_thread(f"c{i}", f"user{i}", "hi") for i in range(5)]
    result = fake.client().fetch(VIDEO)

    assert [c.comment_id for c in result.comments] == ["c0", "c1", "c2", "c3", "c4"]
    assert result.quota_used == 3  # ceil(5 / page_size 2)
    assert result.video_ids == ["vid00000001"]
    assert result.truncated is False


def test_parses_replies_with_parent_id() -> None:
    fake = FakeYouTube()
    fake.comments["vid00000001"] = [
        _thread("top1", "alice", "root", replies=[{"id": "r1", "author": "bob", "text": "re"}])
    ]
    comments = fake.client().fetch(VIDEO).comments
    reply = next(c for c in comments if c.comment_id == "r1")
    assert reply.parent_id == "top1"
    assert reply.author_channel_id == "bob"


def test_flags_replies_truncated_when_more_than_inline() -> None:
    fake = FakeYouTube()
    fake.comments["vid00000001"] = [_thread("t", "a", "x", total_replies=12)]
    assert fake.client().fetch(VIDEO).replies_truncated is True


def test_stops_at_max_comments() -> None:
    fake = FakeYouTube()
    fake.comments["vid00000001"] = [_thread(f"c{i}", "u", "x") for i in range(10)]
    result = fake.client().fetch(VIDEO, max_comments=3)
    assert len(result.comments) == 3
    assert result.truncated is True


def test_channel_target_resolves_handle_then_videos_then_comments() -> None:
    fake = FakeYouTube()
    fake.channels["@creator"] = "UCcreator00000000000000"
    fake.videos["UCcreator00000000000000"] = ["v1", "v2", "v3"]
    fake.comments = {"v1": [_thread("a", "x", "1")], "v2": [_thread("b", "y", "2")], "v3": []}

    result = fake.client().fetch(YouTubeTarget("handle", "creator"), channel_video_count=3)
    assert result.video_ids == ["v1", "v2", "v3"]
    assert {c.comment_id for c in result.comments} == {"a", "b"}


def test_unknown_handle_is_resource_not_found() -> None:
    with pytest.raises(YouTubeError) as exc:
        FakeYouTube().client().fetch(YouTubeTarget("handle", "ghost"))
    assert exc.value.error_code == "RESOURCE_NOT_FOUND"


def test_quota_exceeded_is_mapped() -> None:
    fake = FakeYouTube()
    fake.video_error["vid00000001"] = _error(403, "quotaExceeded")
    with pytest.raises(YouTubeError) as exc:
        fake.client().fetch(VIDEO)
    assert exc.value.error_code == "QUOTA_EXCEEDED"


def test_comments_disabled_fails_a_video_target() -> None:
    fake = FakeYouTube()
    fake.video_error["vid00000001"] = _error(403, "commentsDisabled")
    with pytest.raises(YouTubeError) as exc:
        fake.client().fetch(VIDEO)
    assert exc.value.error_code == "COMMENTS_DISABLED"


def test_comments_disabled_skips_one_channel_video() -> None:
    fake = FakeYouTube()
    fake.channels["@c"] = "UCc0000000000000000000"
    fake.videos["UCc0000000000000000000"] = ["good", "bad"]
    fake.comments["good"] = [_thread("g", "u", "hi")]
    fake.video_error["bad"] = _error(403, "commentsDisabled")

    result = fake.client().fetch(YouTubeTarget("handle", "c"), channel_video_count=2)
    assert result.comments_disabled_videos == ["bad"]
    assert [c.comment_id for c in result.comments] == ["g"]


def test_404_maps_to_resource_not_found() -> None:
    fake = FakeYouTube()
    fake.video_error["vid00000001"] = _error(404, "videoNotFound")
    with pytest.raises(YouTubeError) as exc:
        fake.client().fetch(VIDEO)
    assert exc.value.error_code == "RESOURCE_NOT_FOUND"


def test_invalid_key_maps_to_config_error() -> None:
    fake = FakeYouTube()
    fake.video_error["vid00000001"] = _error(403, "keyInvalid")
    with pytest.raises(YouTubeError) as exc:
        fake.client().fetch(VIDEO)
    assert exc.value.error_code == "CONFIG_ERROR"


def test_unrecognised_failure_falls_back_to_youtube_error() -> None:
    fake = FakeYouTube()
    fake.video_error["vid00000001"] = httpx.Response(500, text="upstream boom")
    with pytest.raises(YouTubeError) as exc:
        fake.client().fetch(VIDEO)
    assert exc.value.error_code == "YOUTUBE_ERROR"
    assert "500" in str(exc.value)


def test_missing_or_bad_fields_are_tolerated() -> None:
    fake = FakeYouTube()
    fake.comments["vid00000001"] = [
        {
            "snippet": {
                "topLevelComment": {
                    "id": "sparse",
                    "snippet": {"textOriginal": "hi", "publishedAt": "not-a-date"},
                },
                "totalReplyCount": 0,
            }
        }
    ]
    comment = fake.client().fetch(VIDEO).comments[0]
    assert comment.published_at is None
    assert comment.author_channel_id == "anonymous"
    assert comment.like_count == 0


def test_comment_cap_hit_exactly_at_a_video_boundary() -> None:
    fake = FakeYouTube()
    fake.channels["@c"] = "UCc0000000000000000000"
    fake.videos["UCc0000000000000000000"] = ["v1", "v2"]
    fake.comments = {
        "v1": [_thread("a", "u", "x"), _thread("b", "u", "y")],
        "v2": [_thread("c", "u", "z")],
    }
    result = fake.client().fetch(
        YouTubeTarget("handle", "c"), max_comments=2, channel_video_count=2
    )
    assert [c.comment_id for c in result.comments] == ["a", "b"]
    assert result.truncated is True


def test_empty_api_key_rejected() -> None:
    with pytest.raises(ValueError, match="api_key is required"):
        YouTubeClient("")
