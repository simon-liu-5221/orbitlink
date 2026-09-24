from __future__ import annotations

import json
import logging

from app.core.logging import JsonFormatter
from app.core.request_context import set_request_id


def _make_record(msg: str = "hello", exc_info: bool = False) -> logging.LogRecord:
    exc = None
    if exc_info:
        try:
            raise ValueError("boom")
        except ValueError:
            import sys

            exc = sys.exc_info()
    return logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=(),
        exc_info=exc,
    )


def test_basic_fields_are_present() -> None:
    payload = json.loads(JsonFormatter().format(_make_record("hello world")))
    assert payload["msg"] == "hello world"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "test.logger"
    assert "ts" in payload


def test_request_id_is_included_when_set() -> None:
    set_request_id("req-42")
    payload = json.loads(JsonFormatter().format(_make_record()))
    assert payload["request_id"] == "req-42"


def test_exception_traceback_is_included() -> None:
    payload = json.loads(JsonFormatter().format(_make_record(exc_info=True)))
    assert "ValueError: boom" in payload["exc"]


def test_extra_fields_are_merged_in() -> None:
    record = _make_record()
    record.extra_fields = {"user_id": "u1", "count": 3}  # type: ignore[attr-defined]
    payload = json.loads(JsonFormatter().format(record))
    assert payload["user_id"] == "u1"
    assert payload["count"] == 3
