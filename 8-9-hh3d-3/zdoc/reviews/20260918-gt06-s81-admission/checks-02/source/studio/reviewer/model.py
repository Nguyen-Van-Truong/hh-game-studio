"""Pure bounded reviewer state. No credentials, arbitrary log text or I/O."""
from dataclasses import dataclass, replace
from enum import Enum
import math
import re


class UiAction(str, Enum):
    PLAY = 'play'
    STOP = 'stop'
    LOOKUP = 'lookup'
    INSPECT = 'inspect'
    CAPTURE = 'capture'


class Phase(str, Enum):
    READY = 'ready'
    QUEUED = 'queued'
    RUNNING = 'running'
    DRAINING = 'draining'
    UNKNOWN = 'unknown'
    COMMITTED = 'committed'
    REJECTED = 'rejected'
    DISCONNECTED = 'disconnected'
    STOPPED = 'stopped'
    CLOSED = 'closed'


class UiCode(str, Enum):
    READY = 'ready'
    QUEUED = 'queued'
    RUNNING = 'running'
    STOP_REQUESTED = 'stop_requested'
    DRAINING = 'draining'
    STOPPED = 'stopped'
    COMPLETED = 'completed'
    REJECTED = 'rejected'
    UNKNOWN = 'unknown'
    DISCONNECTED = 'disconnected'
    LOOKUP_REQUIRED = 'lookup_required'
    INSPECTION_READY = 'inspection_ready'
    CAPTURE_READY = 'capture_ready'
    INVALID_RESPONSE = 'invalid_response'
    CLIENT_ERROR = 'client_error'
    BUSY = 'busy'
    CLOSED = 'closed'
    NO_COMMAND = 'no_command'
    CLEANUP_HELD = 'cleanup_held'


class NextAction(str, Enum):
    PLAY = 'play'
    WAIT = 'wait'
    LOOKUP = 'lookup'
    STOP = 'stop'
    REVIEW_EVIDENCE = 'review_evidence'
    REVIEW_ERROR = 'review_error'
    CLOSE = 'close'


class EventKind(str, Enum):
    REQUESTED = 'requested'
    UPDATE = 'update'
    DISCONNECTED = 'disconnected'


NATIVE_PHASES = frozenset({'MENU', 'PLAY', 'PAUSED', 'QUITTING'})
CAPTURE_LABELS = frozenset({'menu', 'moved', 'interact', 'paused_a', 'paused_b', 'resumed', 'camera'})
_HASH = re.compile(r'[0-9a-f]{64}\Z')
MAX_PENDING = 3
MAX_HISTORY = 12


def _need(value):
    if not value:
        raise ValueError('INVALID_REVIEWER_VALUE')


def _int(value, low, high):
    _need(type(value) is int and low <= value <= high)


@dataclass(frozen=True, slots=True)
class ObservationRow:
    tick: int
    phase: str
    sim_tick: int
    ui_tick: int
    body_position: tuple[float, float, float]

    def __post_init__(self):
        _int(self.tick, 0, 599)
        _need(type(self.phase) is str and self.phase in NATIVE_PHASES)
        _int(self.sim_tick, 0, 600)
        _int(self.ui_tick, 0, 10_000)
        _need(type(self.body_position) is tuple and len(self.body_position) == 3)
        _need(all(type(v) in (int, float) and math.isfinite(v) and abs(v) <= 10_000
                  for v in self.body_position))


@dataclass(frozen=True, slots=True)
class CaptureMetadata:
    label: str
    tick: int
    phase: str
    sha256: str
    size_bytes: int

    def __post_init__(self):
        _need(type(self.label) is str and self.label in CAPTURE_LABELS)
        _int(self.tick, 0, 599)
        _need(type(self.phase) is str and self.phase in NATIVE_PHASES)
        _need(type(self.sha256) is str and _HASH.fullmatch(self.sha256))
        _int(self.size_bytes, 1, 1024 * 1024)


@dataclass(frozen=True, slots=True)
class HistoricalSummary:
    report_sha256: str | None = None
    source_sha256: str | None = None
    snapshot_sha256: str | None = None
    trace_sha256: str | None = None
    pid: int | None = None
    generation: int | None = None
    rows: tuple[ObservationRow, ...] = ()
    total_matches: int = 0
    has_next: bool = False
    capture: CaptureMetadata | None = None

    def __post_init__(self):
        for digest in (self.report_sha256, self.source_sha256, self.snapshot_sha256, self.trace_sha256):
            _need(digest is None or type(digest) is str and _HASH.fullmatch(digest))
        if self.pid is not None:
            _int(self.pid, 1, 4294967295)
        if self.generation is not None:
            _int(self.generation, 1, 2147483647)
        _need(type(self.rows) is tuple and len(self.rows) <= 8 and all(type(row) is ObservationRow for row in self.rows))
        _int(self.total_matches, len(self.rows), 600)
        _need(type(self.has_next) is bool)
        _need(self.capture is None or type(self.capture) is CaptureMetadata)


@dataclass(frozen=True, slots=True)
class ReviewerEvent:
    action: UiAction
    phase: Phase
    code: UiCode
    progress: int | None = None
    next_action: NextAction | None = None
    historical: HistoricalSummary | None = None
    stop_confirmed: bool = False
    request_id: int = 0
    kind: EventKind = EventKind.UPDATE

    def __post_init__(self):
        _need(type(self.action) is UiAction and type(self.phase) is Phase and type(self.code) is UiCode)
        _need(type(self.kind) is EventKind and type(self.stop_confirmed) is bool)
        _int(self.request_id, 0, 1_000_000)
        if self.progress is not None:
            _int(self.progress, 0, 100)
        _need(self.next_action is None or type(self.next_action) is NextAction)
        _need(self.historical is None or type(self.historical) is HistoricalSummary)


@dataclass(frozen=True, slots=True)
class ReviewerState:
    phase: Phase = Phase.READY
    code: UiCode = UiCode.READY
    next_action: NextAction = NextAction.PLAY
    progress: int | None = None
    started: bool = False
    completed: bool = False
    stop_latched: bool = False
    stop_confirmed: bool = False
    connected: bool = True
    pending: tuple[tuple[int, UiAction], ...] = ()
    historical: HistoricalSummary | None = None
    history: tuple[UiCode, ...] = ()
    dropped_updates: int = 0


def enabled_actions(state: ReviewerState) -> frozenset[UiAction]:
    if state.phase is Phase.CLOSED:
        return frozenset()
    pending = {action for _, action in state.pending}
    result = {UiAction.STOP, UiAction.LOOKUP}
    if state.phase is Phase.READY and not state.started and not state.stop_latched and state.connected:
        result.add(UiAction.PLAY)
    if state.phase is Phase.COMMITTED and not state.stop_latched and state.connected:
        result.update((UiAction.INSPECT, UiAction.CAPTURE))
    occupied = {lane(action) for action in pending}
    return frozenset(action for action in result if lane(action) not in occupied)


def lane(action: UiAction) -> str:
    return 'stop' if action is UiAction.STOP else 'lookup' if action is UiAction.LOOKUP else 'work'


def _next(phase):
    return {Phase.READY: NextAction.PLAY, Phase.QUEUED: NextAction.WAIT,
        Phase.RUNNING: NextAction.STOP, Phase.DRAINING: NextAction.LOOKUP,
        Phase.COMMITTED: NextAction.REVIEW_EVIDENCE, Phase.REJECTED: NextAction.REVIEW_ERROR,
        Phase.UNKNOWN: NextAction.LOOKUP, Phase.DISCONNECTED: NextAction.LOOKUP,
        Phase.STOPPED: NextAction.CLOSE, Phase.CLOSED: NextAction.CLOSE}[phase]


def reduce(state: ReviewerState, event: ReviewerEvent) -> ReviewerState:
    """A response closes one local request; reconnect never creates a Play."""
    _need(type(state) is ReviewerState and type(event) is ReviewerEvent)
    if state.phase is Phase.CLOSED:
        return state
    if event.kind is EventKind.REQUESTED:
        if (event.request_id <= 0 or event.action not in enabled_actions(state)
                or len(state.pending) >= MAX_PENDING
                or any(number == event.request_id for number, _ in state.pending)):
            return state
        phase, code = state.phase, UiCode.QUEUED
        if event.action is UiAction.PLAY:
            phase = Phase.QUEUED
        elif event.action is UiAction.STOP:
            phase, code = Phase.DRAINING, UiCode.STOP_REQUESTED
        elif event.action is UiAction.LOOKUP:
            code = UiCode.LOOKUP_REQUIRED
        return replace(state, phase=phase, code=code, next_action=_next(phase), progress=None,
            started=state.started or event.action is UiAction.PLAY,
            stop_latched=state.stop_latched or event.action is UiAction.STOP,
            pending=state.pending + ((event.request_id, event.action),),
            history=(state.history + (code,))[-MAX_HISTORY:])
    pair = (event.request_id, event.action)
    if pair not in state.pending:
        return replace(state, dropped_updates=min(1_000_000, state.dropped_updates + 1))
    pending = tuple(item for item in state.pending if item != pair)
    phase, code = event.phase, event.code
    connected = event.kind is not EventKind.DISCONNECTED and phase is not Phase.DISCONNECTED
    if not connected:
        phase, code = Phase.DISCONNECTED, UiCode.DISCONNECTED
    elif (event.action is UiAction.LOOKUP and phase is Phase.READY
          and code is UiCode.NO_COMMAND and not event.stop_confirmed):
        # The client emits NO_COMMAND locally before its launch worker enters.
        # It is neither a server receipt nor permission to replay an attempted
        # command. A delayed local result preserves the newer launch state.
        if state.started:
            phase, code = state.phase, state.code
    elif phase in (Phase.READY, Phase.CLOSED) or event.stop_confirmed and phase is not Phase.STOPPED:
        phase, code = Phase.UNKNOWN, UiCode.INVALID_RESPONSE
    confirmed = state.stop_confirmed or event.stop_confirmed and phase is Phase.STOPPED
    latched = state.stop_latched or confirmed
    completed = state.completed or phase is Phase.COMMITTED
    if completed and phase in (Phase.QUEUED, Phase.RUNNING):
        phase, code = Phase.COMMITTED, UiCode.COMPLETED
    if connected and latched and phase not in (Phase.UNKNOWN, Phase.REJECTED):
        phase = Phase.STOPPED if confirmed else Phase.DRAINING
        code = UiCode.STOPPED if confirmed else UiCode.DRAINING
    if phase is Phase.STOPPED and not confirmed:
        phase, code = Phase.UNKNOWN, UiCode.INVALID_RESPONSE
    # A callback cannot turn an uncertain result into an instruction to retry
    # Play. Next actions follow the state machine, never remote strings.
    progress = event.progress if phase in (Phase.QUEUED, Phase.RUNNING, Phase.COMMITTED) else None
    return replace(state, phase=phase, code=code, next_action=_next(phase), progress=progress,
        completed=completed, stop_latched=latched, stop_confirmed=confirmed, connected=connected, pending=pending,
        historical=event.historical if event.historical is not None else state.historical,
        history=(state.history + (code,))[-MAX_HISTORY:])


def cleanup_held(state: ReviewerState) -> ReviewerState:
    return replace(state, phase=Phase.UNKNOWN, code=UiCode.CLEANUP_HELD, progress=None,
                   next_action=NextAction.LOOKUP, stop_latched=True)


def closed(state: ReviewerState) -> ReviewerState:
    _need(not state.pending)
    return replace(state, phase=Phase.CLOSED, code=UiCode.CLOSED, next_action=NextAction.CLOSE,
                   progress=None, stop_latched=True)
