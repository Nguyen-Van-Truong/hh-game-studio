"""GT07 preparation: bounded selection over a trusted, coherent queue snapshot.

This pure policy grants no lease, starts no worker and acknowledges no effect.
The future durable broker must read, select, reserve slots/resources and persist
the returned cursor in ONE transaction, then recheck authorization/fencing/Stop
at its existing adapter boundary. Draining and uncertain jobs remain active.
No public route uses this candidate before GT06 acceptance and GT07 integration.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Mapping


class DispatchPolicyError(ValueError):
    pass


@dataclass(frozen=True)
class QueueLimits:
    """Internal candidate profile; does not alter an installed public profile."""
    pending: int = 64
    project_pending: int = 32
    session_pending: int = 8
    active: int = 4
    project_active: int = 2
    session_active: int = 1
    resources: int = 8
    dependencies: int = 16
    receipts: int = 1024


@dataclass(frozen=True)
class PendingJob:
    job_id: str
    project_id: str
    session_id: str
    sequence: int  # durable enqueue sequence, not caller timestamp/priority
    deadline_ms: int
    resources: tuple[str, ...]  # host-resolved global resource identities
    dependencies: tuple[str, ...] = ()


@dataclass(frozen=True)
class ActiveJob:
    job_id: str
    project_id: str
    session_id: str
    resources: tuple[str, ...]


@dataclass(frozen=True)
class Cursor:
    last_project: str | None = None
    # Canonically sorted project -> last session, bounded to live projects.
    sessions: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Selection:
    job_id: str
    next_cursor: Cursor


def _need(condition: bool, code: str) -> None:
    if not condition:
        raise DispatchPolicyError(code)


def _identifier(value: object) -> bool:
    # These are opaque trusted IDs, never filesystem paths or credentials.
    return type(value) is str and 0 < len(value) <= 128 and all(
        c.isascii() and (c.isalnum() or c in '.-_:/') for c in value)


def _integer(value: object, minimum: int = 0) -> bool:
    return type(value) is int and minimum <= value <= (1 << 53) - 1


def _ids(values: object, cap: int, *, allow_empty: bool) -> bool:
    return (type(values) is tuple and len(values) <= cap
            and (allow_empty or bool(values)) and all(_identifier(v) for v in values)
            and len(set(values)) == len(values))


def _next(values: set[str], previous: str | None) -> str:
    ordered = sorted(values)
    return next((v for v in ordered if previous is not None and v > previous), ordered[0])


def select_next(*, pending: tuple[PendingJob, ...], active: tuple[ActiveJob, ...],
                receipts: Mapping[str, str], cursor: Cursor, now_ms: int,
                stopped: bool, limits: QueueLimits = QueueLimits()) -> Selection | None:
    """Project/session round-robin with per-session and per-resource FIFO.

    Only the first unexpired ticket of each session can be selected. Any older
    unexpired ticket claiming a resource blocks younger tickets for that resource,
    even if its dependency is unresolved. Unrelated resources still progress.
    Failed/UNKNOWN prerequisites never count as completed. Expiration here merely
    excludes a ticket; durable terminal receipts remain the broker's job.
    """
    _need(type(limits) is QueueLimits and all(_integer(v, 1) and v <= 1024
          for v in vars(limits).values()), 'DISPATCH_LIMITS_INVALID')
    _need(limits.session_active <= limits.project_active <= limits.active,
          'DISPATCH_LIMITS_INVALID')
    _need(limits.session_pending <= limits.project_pending, 'DISPATCH_LIMITS_INVALID')
    _need(type(pending) is tuple and len(pending) <= limits.pending
          and type(active) is tuple and len(active) <= limits.active, 'DISPATCH_CAPACITY')
    _need(type(stopped) is bool and _integer(now_ms), 'DISPATCH_CONTEXT_INVALID')
    _need(isinstance(receipts, Mapping) and len(receipts) <= limits.receipts,
          'DISPATCH_RECEIPTS_INVALID')
    _need(all(_identifier(k) and type(v) is str and v in
              {'COMMITTED', 'REJECTED', 'CANCELED', 'UNKNOWN'} for k, v in receipts.items()),
          'DISPATCH_RECEIPTS_INVALID')
    _need(type(cursor) is Cursor and (cursor.last_project is None or _identifier(cursor.last_project))
          and type(cursor.sessions) is tuple and len(cursor.sessions) <= limits.pending + limits.active,
          'DISPATCH_CURSOR_INVALID')
    _need(all(type(row) is tuple and len(row) == 2 and all(_identifier(v) for v in row)
              for row in cursor.sessions), 'DISPATCH_CURSOR_INVALID')
    _need(tuple(sorted(cursor.sessions)) == cursor.sessions
          and len({p for p, _ in cursor.sessions}) == len(cursor.sessions), 'DISPATCH_CURSOR_INVALID')

    seen_ids: set[str] = set()
    sequences: set[int] = set()
    project_active: Counter[str] = Counter()
    session_active: Counter[tuple[str, str]] = Counter()
    occupied: set[str] = set()
    project_pending: Counter[str] = Counter()
    session_pending: Counter[tuple[str, str]] = Counter()
    for job in active:
        _need(type(job) is ActiveJob and all(_identifier(v) for v in
              (job.job_id, job.project_id, job.session_id))
              and _ids(job.resources, limits.resources, allow_empty=False), 'DISPATCH_JOB_INVALID')
        _need(job.job_id not in seen_ids and job.job_id not in receipts,
              'DISPATCH_ID_CONFLICT')
        _need(not occupied.intersection(job.resources), 'DISPATCH_RESOURCE_CONFLICT')
        seen_ids.add(job.job_id)
        occupied.update(job.resources)
        project_active[job.project_id] += 1
        session_active[(job.project_id, job.session_id)] += 1
    _need(all(n <= limits.project_active for n in project_active.values())
          and all(n <= limits.session_active for n in session_active.values()), 'DISPATCH_ACTIVE_OVER_QUOTA')
    for job in pending:
        _need(type(job) is PendingJob and all(_identifier(v) for v in
              (job.job_id, job.project_id, job.session_id)) and _integer(job.sequence, 1)
              and _integer(job.deadline_ms) and _ids(job.resources, limits.resources, allow_empty=False)
              and _ids(job.dependencies, limits.dependencies, allow_empty=True), 'DISPATCH_JOB_INVALID')
        _need(job.job_id not in seen_ids and job.job_id not in receipts
              and job.sequence not in sequences, 'DISPATCH_ID_CONFLICT')
        _need(job.job_id not in job.dependencies, 'DISPATCH_DEPENDENCY_INVALID')
        seen_ids.add(job.job_id)
        sequences.add(job.sequence)
        project_pending[job.project_id] += 1
        session_pending[(job.project_id, job.session_id)] += 1
    _need(all(n <= limits.project_pending for n in project_pending.values())
          and all(n <= limits.session_pending for n in session_pending.values()),
          'DISPATCH_PENDING_OVER_QUOTA')
    if stopped or len(active) == limits.active:
        return None

    heads: set[tuple[str, str]] = set()
    older_resources: set[str] = set()
    eligible: dict[str, dict[str, PendingJob]] = {}
    for job in sorted(pending, key=lambda row: row.sequence):
        if job.deadline_ms <= now_ms:
            continue
        scope = (job.project_id, job.session_id)
        is_head = scope not in heads
        heads.add(scope)
        resource_busy = bool((occupied | older_resources).intersection(job.resources))
        older_resources.update(job.resources)
        if (not is_head or resource_busy or project_active[job.project_id] >= limits.project_active
                or session_active[scope] >= limits.session_active
                or not all(receipts.get(key) == 'COMMITTED' for key in job.dependencies)):
            continue
        eligible.setdefault(job.project_id, {})[job.session_id] = job
    if not eligible:
        return None

    project = _next(set(eligible), cursor.last_project)
    last_sessions = dict(cursor.sessions)
    session = _next(set(eligible[project]), last_sessions.get(project))
    last_sessions[project] = session
    # Retain the cursor for blocked/live projects too, without unbounded history.
    live_projects = {job.project_id for job in (*pending, *active)}
    next_cursor = Cursor(project, tuple(sorted((p, s) for p, s in last_sessions.items() if p in live_projects)))
    return Selection(eligible[project][session].job_id, next_cursor)
