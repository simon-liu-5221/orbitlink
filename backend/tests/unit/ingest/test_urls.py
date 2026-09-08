"""PR-01 AC-2 / AC-3 — table-driven YouTube link parsing."""

from __future__ import annotations

import pytest

from app.ingest.urls import InvalidYouTubeURLError, YouTubeTarget, parse_youtube_url

VALID = [
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", ("video", "dQw4w9WgXcQ")),
    ("https://youtube.com/watch?v=dQw4w9WgXcQ&t=42s&list=PLxyz", ("video", "dQw4w9WgXcQ")),
    ("https://youtu.be/dQw4w9WgXcQ", ("video", "dQw4w9WgXcQ")),
    ("https://youtu.be/dQw4w9WgXcQ?si=abcdef", ("video", "dQw4w9WgXcQ")),
    ("https://www.youtube.com/shorts/dQw4w9WgXcQ", ("video", "dQw4w9WgXcQ")),
    ("https://www.youtube.com/live/dQw4w9WgXcQ", ("video", "dQw4w9WgXcQ")),
    ("https://m.youtube.com/watch?v=dQw4w9WgXcQ", ("video", "dQw4w9WgXcQ")),
    ("https://www.youtube.com/@MrBeast", ("handle", "MrBeast")),
    ("https://www.youtube.com/@MrBeast/videos", ("handle", "MrBeast")),
    ("youtube.com/@lofi.girl", ("handle", "lofi.girl")),
    (
        "https://www.youtube.com/channel/UCX6OQ3DkcsbYNE6H8uQQuVA",
        ("channel", "UCX6OQ3DkcsbYNE6H8uQQuVA"),
    ),
    ("  https://youtu.be/dQw4w9WgXcQ  ", ("video", "dQw4w9WgXcQ")),
]


@pytest.mark.parametrize(("url", "expected"), VALID)
def test_parses_supported_formats(url: str, expected: tuple[str, str]) -> None:
    target = parse_youtube_url(url)
    assert target == YouTubeTarget(expected[0], expected[1])  # type: ignore[arg-type]


INVALID = [
    "",
    "not a url",
    "https://vimeo.com/12345",
    "https://www.youtube.com/watch",  # no ?v=
    "https://youtu.be/",  # no id
    "https://www.youtube.com/watch?v=tooShort",
    "https://www.youtube.com/channel/notAChannelId",
    "https://www.youtube.com/@ab",  # handle too short
    "https://www.youtube.com/c/SomeLegacyName",
    "https://www.youtube.com/user/SomeLegacyName",
    "https://www.youtube.com/",
]


@pytest.mark.parametrize("url", INVALID)
def test_rejects_bad_links_with_format_guidance(url: str) -> None:
    with pytest.raises(InvalidYouTubeURLError) as exc:
        parse_youtube_url(url)
    assert "Expected one of" in str(exc.value)


def test_legacy_url_error_names_the_alternative() -> None:
    with pytest.raises(InvalidYouTubeURLError, match="@handle or /channel"):
        parse_youtube_url("https://www.youtube.com/c/Legacy")
