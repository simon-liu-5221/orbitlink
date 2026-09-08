"""Analysis job state machine (ADR-0002 / AN-05) — pure, no DB."""

from __future__ import annotations

import itertools

import pytest

from app.jobs.state_machine import (
    PIPELINE,
    PROGRESS_FLOOR,
    TERMINAL,
    InvalidJobTransitionError,
    JobStatus,
    _pipeline_successor,
    assert_transition,
    can_transition,
    clamp_progress,
    progress_floor,
)

LIVE = [s for s in JobStatus if s not in TERMINAL]


def test_happy_path_advances_one_step_at_a_time() -> None:
    for current, nxt in itertools.pairwise(PIPELINE):
        assert can_transition(current, nxt)


def test_cannot_skip_a_pipeline_step() -> None:
    assert not can_transition(JobStatus.QUEUED, JobStatus.ANALYZING)
    assert not can_transition(JobStatus.FETCHING, JobStatus.PERSISTING)


def test_cannot_move_backwards() -> None:
    assert not can_transition(JobStatus.ANALYZING, JobStatus.FETCHING)
    assert not can_transition(JobStatus.COMPLETED, JobStatus.ANALYZING)


@pytest.mark.parametrize("status", LIVE)
def test_any_live_status_can_fail_or_cancel(status: JobStatus) -> None:
    assert can_transition(status, JobStatus.FAILED)
    assert can_transition(status, JobStatus.CANCELLED)


@pytest.mark.parametrize("status", sorted(TERMINAL))
def test_terminal_statuses_have_no_exit(status: JobStatus) -> None:
    for target in JobStatus:
        assert not can_transition(status, target)


def test_pipeline_successor_is_none_off_the_happy_path() -> None:
    assert _pipeline_successor(JobStatus.COMPLETED) is None  # last step
    assert _pipeline_successor(JobStatus.FAILED) is None  # not on the pipeline


def test_assert_transition_raises_on_illegal_move() -> None:
    with pytest.raises(InvalidJobTransitionError, match="cannot move job"):
        assert_transition(JobStatus.COMPLETED, JobStatus.FAILED)
    assert_transition(JobStatus.QUEUED, JobStatus.FETCHING)  # legal -> no raise


def test_progress_floor_matches_pipeline_order() -> None:
    floors = [PROGRESS_FLOOR[s] for s in PIPELINE]
    assert floors == sorted(floors)
    assert floors[0] == 0
    assert floors[-1] == 100
    assert progress_floor(JobStatus.FAILED) == 0  # not in the map -> 0


def test_clamp_progress_never_decreases() -> None:
    assert clamp_progress(60, JobStatus.ANALYZING) == 60  # floor 55 < current
    assert clamp_progress(30, JobStatus.BUILDING_GRAPH) == 40  # bumped to floor


def test_clamp_progress_honours_sub_step_but_caps_at_100() -> None:
    assert clamp_progress(55, JobStatus.ANALYZING, proposed=80) == 80
    assert clamp_progress(55, JobStatus.ANALYZING, proposed=999) == 100
    assert clamp_progress(90, JobStatus.PERSISTING, proposed=10) == 90  # can't go down


def test_clamp_progress_keeps_value_for_failure_states() -> None:
    assert clamp_progress(62, JobStatus.FAILED) == 62
    assert clamp_progress(62, JobStatus.CANCELLED) == 62
