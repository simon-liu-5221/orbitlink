"""In-memory YouTube Data API fake over ``httpx.MockTransport``.

Shared by the ingest unit tests and the analysis-service integration tests.
No network.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.ingest.youtube import YouTubeClient


def thread(
    cid: str,
    author: str,
    text: str,
    *,
    likes: int = 0,
    published: str = "2026-01-01T00:00:00Z",
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
                "publishedAt": r.get("published", "2026-01-02T00:00:00Z"),
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
                    "publishedAt": published,
                },
            },
            "totalReplyCount": total_replies if total_replies is not None else len(reply_nodes),
        }
    }
    if reply_nodes:
        item["replies"] = {"comments": reply_nodes}
    return item


def api_error(status: int, reason: str) -> httpx.Response:
    return httpx.Response(
        status,
        json={"error": {"code": status, "errors": [{"reason": reason}], "message": reason}},
    )


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
