"""RQ task entrypoints — dependency wiring, with everything external mocked."""

from __future__ import annotations

import types
import uuid
from typing import Any

import pytest

from app.jobs import tasks


class _FakeSession:
    def __init__(self, log: dict[str, Any]) -> None:
        self._log = log

    def __enter__(self) -> _FakeSession:
        return self

    def __exit__(self, *_exc: object) -> bool:
        return False

    def commit(self) -> None:
        self._log["committed"] = True


def test_run_analysis_job_wires_dependencies_and_commits(monkeypatch: pytest.MonkeyPatch) -> None:
    log: dict[str, Any] = {}
    monkeypatch.setattr(tasks, "SessionLocal", lambda: _FakeSession(log))
    monkeypatch.setattr(tasks, "YouTubeClient", lambda key: ("client", key))
    monkeypatch.setattr(
        tasks, "build_sentiment_analyzer", lambda _s: ("analyzer", "lexicon-standin")
    )

    def fake_run(session: object, job_id: uuid.UUID, **kwargs: Any) -> object:
        log["job_id"] = job_id
        log["client"] = kwargs["youtube_client"]
        log["label"] = kwargs["sentiment"].label
        return types.SimpleNamespace(status="completed")

    monkeypatch.setattr(tasks, "run_analysis", fake_run)

    job_id = str(uuid.uuid4())
    assert tasks.run_analysis_job(job_id) == "completed"
    assert log["committed"] is True
    assert str(log["job_id"]) == job_id
    assert log["client"][0] == "client"
    assert log["label"] == "lexicon-standin"


def test_reaper_task_reaps_then_reschedules_itself(monkeypatch: pytest.MonkeyPatch) -> None:
    log: dict[str, Any] = {}
    monkeypatch.setattr(tasks, "SessionLocal", lambda: _FakeSession(log))
    monkeypatch.setattr(
        tasks, "reap_stale_jobs", lambda _session, *, timeout_minutes: [uuid.uuid4(), uuid.uuid4()]
    )
    queue = types.SimpleNamespace(
        enqueue_in=lambda delta, fn: log.__setitem__("scheduled", (delta, fn))
    )
    monkeypatch.setattr(tasks, "get_queue", lambda: queue)

    assert tasks.reap_stale_jobs_task() == 2
    assert log["committed"] is True
    assert log["scheduled"][0] == tasks.REAPER_INTERVAL
    assert log["scheduled"][1] is tasks.reap_stale_jobs_task
