"""Analysis job state machine (ADR-0002).

Pure: no DB, no RQ. The service layer calls :func:`assert_transition` before
writing a new status, and :func:`progress_floor` to keep progress monotonic.

    queued -> fetching -> building_graph -> analyzing -> persisting -> completed

Any non-terminal status may also go straight to ``failed`` (an error) or
``cancelled`` (the user asked to stop). Terminal statuses have no exits.
The ADR diagram draws a failed -> cancelled arrow; we treat cancellation as
reachable only from a live job, which is what PR-01's "user presses cancel"
flow actually means.
"""

from __future__ import annotations

import enum


class JobStatus(enum.StrEnum):
    QUEUED = "queued"
    FETCHING = "fetching"
    BUILDING_GRAPH = "building_graph"
    ANALYZING = "analyzing"
    PERSISTING = "persisting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


#: The happy path, in order.
PIPELINE: tuple[JobStatus, ...] = (
    JobStatus.QUEUED,
    JobStatus.FETCHING,
    JobStatus.BUILDING_GRAPH,
    JobStatus.ANALYZING,
    JobStatus.PERSISTING,
    JobStatus.COMPLETED,
)

TERMINAL: frozenset[JobStatus] = frozenset(
    {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}
)

#: Progress value each status is worth on entry (0–100). Between ``analyzing``
#: and ``persisting`` the worker may raise progress further, up to 89.
PROGRESS_FLOOR: dict[JobStatus, int] = {
    JobStatus.QUEUED: 0,
    JobStatus.FETCHING: 10,
    JobStatus.BUILDING_GRAPH: 40,
    JobStatus.ANALYZING: 55,
    JobStatus.PERSISTING: 90,
    JobStatus.COMPLETED: 100,
}


class InvalidJobTransitionError(ValueError):
    """Raised when a status change is not allowed by the state machine."""


def _pipeline_successor(status: JobStatus) -> JobStatus | None:
    try:
        index = PIPELINE.index(status)
    except ValueError:
        return None
    return PIPELINE[index + 1] if index + 1 < len(PIPELINE) else None


def can_transition(current: JobStatus, target: JobStatus) -> bool:
    if current in TERMINAL:
        return False
    if target in (JobStatus.FAILED, JobStatus.CANCELLED):
        return True
    return target == _pipeline_successor(current)


def assert_transition(current: JobStatus, target: JobStatus) -> None:
    if not can_transition(current, target):
        raise InvalidJobTransitionError(f"cannot move job from {current} to {target}")


def progress_floor(status: JobStatus) -> int:
    """Lowest progress value consistent with being in ``status``.

    Terminal failure states keep whatever progress the job had reached, so they
    are not listed here — callers pass through the existing value.
    """
    return PROGRESS_FLOOR.get(status, 0)


def clamp_progress(current: int, status: JobStatus, proposed: int | None = None) -> int:
    """Monotonic, in-range progress.

    Never decreases, never exceeds 100, and entering a status lifts progress to
    at least that status's floor. ``proposed`` lets a stage report sub-steps.
    """
    floor = PROGRESS_FLOOR.get(status, current)
    candidate = floor if proposed is None else max(floor, proposed)
    return max(current, min(100, candidate))
