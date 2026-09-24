from __future__ import annotations

import threading

from app.core.request_context import get_request_id, set_request_id


def test_defaults_to_none_when_nothing_has_been_set() -> None:
    # Each thread gets its own top-level contextvars.Context, so this is
    # unaffected by other tests in this process having already called
    # set_request_id on the main thread's context.
    result: list[str | None] = []
    thread = threading.Thread(target=lambda: result.append(get_request_id()))
    thread.start()
    thread.join()
    assert result == [None]


def test_set_then_get_round_trips() -> None:
    set_request_id("abc-123")
    assert get_request_id() == "abc-123"


def test_setting_again_overwrites_the_previous_value() -> None:
    set_request_id("first")
    set_request_id("second")
    assert get_request_id() == "second"
