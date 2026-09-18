"""Closed GT06 replay wire contract; validation is not runtime authority.

The host supplies the prepared binding and current lease observations. This
module does not open files, verify artifacts, launch engines or authorize an
effect. Retained-report inspection is explicit; no live inspector is claimed.
Stop/lookup use separate authenticated fixed routes, outside work Requests.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re

from studio.host.core.limits import (DEFAULT_LIMITS, SafetyViolation, parse_json_utf8,
                                     validate_envelope)
from studio.protocol.core import (Capability, Discovery, MAX_ARRAY_ITEMS, MAX_OBJECT_MEMBERS,
    PROTOCOL_VERSION, Request, SAFE_INTEGER, SCHEMA_VERSION, ValidationError,
    canonical_bytes, parse_json, validate_for_dispatch)

SCHEMA_ID = 'hh-studio.replay-catalog'
SCHEMA_ID_VERSION = '1.0.0'
OPERATIONS = frozenset({'play.start', 'play.inspect', 'play.capture'})
MAX_WIRE_BYTES = DEFAULT_LIMITS.max_envelope_bytes
MAX_RESULT_BYTES = DEFAULT_LIMITS.max_result_bytes
MAX_PAYLOAD_BYTES = 16 * 1024
MAX_COMMAND_MS = 20_000
MAX_INSPECT_PAGE = 8
MAX_CURSOR_CHARS = 2048
INSPECT_PROPERTIES = ('sim_tick', 'ui_tick', 'phase', 'body_position', 'body_velocity',
    'animation', 'camera', 'outfit_visible', 'emote_count', 'prop_count', 'tree_paused')
PHASES = frozenset({'MENU', 'PLAY', 'PAUSED', 'QUITTING'})
BINDING_FIELDS = frozenset({'run_id', 'command_id', 'runtime_instance_id',
    'source_closure_sha256', 'runtime_snapshot_sha256', 'trace_sha256', 'glb_sha256', 'generation'})
INSPECT_EXPECTED_FIELDS = frozenset({'runtime_instance_id', 'generation',
    'source_closure_sha256', 'runtime_snapshot_sha256', 'report_sha256', 'pid', 'process_start'})
_ID = re.compile(r'[a-z][a-z0-9._-]{0,63}\Z')
_BOUND_ID = re.compile(r'[a-z][a-z0-9._-]{0,127}\Z')
_SHA = re.compile(r'[0-9a-f]{64}\Z')
_LABEL = re.compile(r'[a-z][a-z0-9]*(?:_[a-z0-9]+)*\Z')
_DEVICE = re.compile(r'(?:con|prn|aux|nul|com[1-9]|lpt[1-9])\Z')
_CURSOR = re.compile(r'[A-Za-z0-9_-]+\.[0-9a-f]{64}\Z')
_PROCESS_START = re.compile(r'windows:[1-9][0-9]{0,19}\Z')
_PRECONDITIONS = frozenset({'expected_generation', 'expected_snapshot_sha256', 'expected_source_sha256'})
_ARTIFACT_LIMITS = {'observation': 8 * 1024 * 1024, 'capture': 1024 * 1024,
                    'perf': 8 * 1024 * 1024, 'process_metrics': 8 * 1024 * 1024,
                    'trace': 256 * 1024}
_LIMITS = {'max_request_bytes': MAX_WIRE_BYTES, 'max_result_bytes': MAX_RESULT_BYTES,
    'max_payload_bytes': MAX_PAYLOAD_BYTES, 'max_array_items': MAX_ARRAY_ITEMS,
    'max_object_members': MAX_OBJECT_MEMBERS, 'max_command_ms': MAX_COMMAND_MS,
    'max_inspect_page': MAX_INSPECT_PAGE, 'max_cursor_chars': MAX_CURSOR_CHARS,
    'max_capture_labels': 16, 'max_trace_frames': 600, 'max_properties': len(INSPECT_PROPERTIES)}
_CATALOG_RAW = canonical_bytes({
    'schema_id': SCHEMA_ID, 'schema_version': SCHEMA_ID_VERSION,
    'protocol_version': PROTOCOL_VERSION, 'envelope_schema_version': SCHEMA_VERSION,
    'target': {'stable_id': 'exact prepared runtime_instance_id'},
    'binding_fields': sorted(BINDING_FIELDS),
    'expected_revision': 'sha256: followed by exact prepared runtime_snapshot_sha256',
    'operations': {
        'play.start': {'required': sorted(_PRECONDITIONS | {'trace_sha256'}), 'optional': [],
                       'meaning': 'launch only the fixed prepared immutable replay snapshot'},
        'play.capture': {'required': sorted(_PRECONDITIONS | {'label'}), 'optional': [],
                         'meaning': 'resolve only a capture label declared by the prepared trace'},
        'play.inspect': {'required': ['expected', 'properties'],
            'optional': ['phase', 'tick_min', 'tick_max', 'page_size', 'cursor'],
            'expected_fields': sorted(INSPECT_EXPECTED_FIELDS), 'properties': list(INSPECT_PROPERTIES),
            'phases': sorted(PHASES), 'meaning': 'bounded page from one admitted completed report',
            'live_supported': False}},
    'control_routes': {'/v1/stop': {'required': ['project_id', 'command_id']},
                       '/v1/lookup': {'required': ['project_id', 'command_id']}},
    'control_policy': 'separate authentication; no work lease, fence or work deadline',
    'limits': _LIMITS, 'large_artifacts': {'reference_fields': ['kind', 'sha256', 'size_bytes'],
                                        'limits': _ARTIFACT_LIMITS, 'inline_bytes': False},
    'runtime_enabled_by_default': [], 'runtime_authorized': False, 'public_ack': False,
    'persistent_ack_or_durability_claim': False})
CATALOG_DIGEST = 'sha256:' + hashlib.sha256(_CATALOG_RAW).hexdigest()


class ReplayContractError(ValidationError):
    def __init__(self, code: str):
        super().__init__(code, 'Replay catalog validation')


def _need(value, code):
    if not value:
        raise ReplayContractError(code)


def _integer(value, low, high, code='REPLAY_INVALID_INTEGER'):
    _need(type(value) is int and low <= value <= high, code)


def _hash(value):
    _need(type(value) is str and _SHA.fullmatch(value), 'REPLAY_INVALID_HASH')


def _shape(value, required, optional=frozenset()):
    _need(type(value) is dict and set(required) <= set(value) <= set(required) | set(optional),
          'REPLAY_INVALID_PAYLOAD')


def _binding(value):
    _need(type(value) is dict and set(value) == BINDING_FIELDS, 'REPLAY_BINDING_FIELDS')
    for name in ('run_id', 'command_id', 'runtime_instance_id'):
        _need(type(value[name]) is str and _BOUND_ID.fullmatch(value[name]), 'REPLAY_BINDING_ID')
    for name in ('source_closure_sha256', 'runtime_snapshot_sha256', 'trace_sha256', 'glb_sha256'):
        _hash(value[name])
    _integer(value['generation'], 1, 2147483647, 'REPLAY_BINDING_GENERATION')
    return canonical_bytes(value)


@dataclass(frozen=True, slots=True, init=False)
class PreparedRuntime:
    """Defensive immutable scope, supplied after the owner's preparation checks.

    Capture labels must come from the already validated exact trace. Freezing
    this value does not itself prove the trace, GLB or source artifacts exist.
    """
    _binding_raw: bytes
    capture_labels: tuple[str, ...]

    def __init__(self, binding: dict, capture_labels: tuple[str, ...]):
        raw = _binding(binding)
        _need(type(capture_labels) is tuple and len(capture_labels) <= 16, 'REPLAY_CAPTURE_LABELS')
        for label in capture_labels:
            _need(type(label) is str and len(label) <= 48 and _LABEL.fullmatch(label)
                  and not _DEVICE.fullmatch(label), 'REPLAY_CAPTURE_LABELS')
        _need(len(set(capture_labels)) == len(capture_labels), 'REPLAY_CAPTURE_LABELS')
        object.__setattr__(self, '_binding_raw', raw)
        object.__setattr__(self, 'capture_labels', capture_labels)

    @property
    def binding(self):
        return parse_json(self._binding_raw)

    @property
    def binding_sha256(self):
        return hashlib.sha256(self._binding_raw).hexdigest()

    @property
    def revision(self):
        return 'sha256:' + self.binding['runtime_snapshot_sha256']


@dataclass(frozen=True, slots=True)
class ReplayContext:
    """Trusted observations for validation; this is never a lease/grant issuer."""
    project_id: str
    prepared: PreparedRuntime
    lease_id: str
    fencing_epoch: int
    lease_expires_ms: int
    now_ms: int
    runtime_enabled: frozenset[str] = frozenset()
    stopped: bool = False


def catalog() -> dict:
    return parse_json(_CATALOG_RAW)


def discovery(project_id: str, *, runtime_enabled: frozenset[str] = frozenset()) -> Discovery:
    _need(type(project_id) is str and _ID.fullmatch(project_id), 'REPLAY_INVALID_PROJECT')
    _need(type(runtime_enabled) is frozenset and runtime_enabled <= OPERATIONS, 'REPLAY_INVALID_RUNTIME_CATALOG')
    capabilities = tuple(Capability(operation, ('replay.read',),
        ('replay.launch',) if operation == 'play.start' else (),
        {'max_payload_bytes': MAX_PAYLOAD_BYTES, 'max_result_bytes': MAX_RESULT_BYTES})
        for operation in sorted(runtime_enabled))
    return Discovery(PROTOCOL_VERSION, SCHEMA_VERSION, CATALOG_DIGEST, 'hh.replay', SCHEMA_ID_VERSION,
                     project_id, capabilities, dict(_LIMITS))


def _context(value):
    _need(type(value) is ReplayContext and type(value.prepared) is PreparedRuntime, 'REPLAY_CONTEXT_REQUIRED')
    discovery(value.project_id, runtime_enabled=value.runtime_enabled)
    _need(type(value.lease_id) is str and _ID.fullmatch(value.lease_id), 'REPLAY_INVALID_LEASE')
    _integer(value.fencing_epoch, 1, SAFE_INTEGER, 'REPLAY_INVALID_FENCE')
    _integer(value.now_ms, 0, SAFE_INTEGER, 'REPLAY_INVALID_CLOCK')
    _integer(value.lease_expires_ms, 1, SAFE_INTEGER, 'REPLAY_INVALID_LEASE')
    _need(type(value.stopped) is bool, 'REPLAY_INVALID_CONTEXT')
    _need(not value.stopped, 'REPLAY_STOPPED')
    return value.prepared.binding


def _preconditions(payload, binding):
    _integer(payload['expected_generation'], 1, 2147483647)
    _need(payload['expected_generation'] == binding['generation'], 'REPLAY_STALE_GENERATION')
    for name, bound in (('expected_snapshot_sha256', 'runtime_snapshot_sha256'),
                        ('expected_source_sha256', 'source_closure_sha256')):
        _hash(payload[name])
        _need(payload[name] == binding[bound], 'REPLAY_STALE_' + ('SNAPSHOT' if 'snapshot' in name else 'SOURCE'))


def _inspect(payload, binding):
    _shape(payload, {'expected', 'properties'}, {'phase', 'tick_min', 'tick_max', 'page_size', 'cursor'})
    expected = payload['expected']
    _shape(expected, INSPECT_EXPECTED_FIELDS)
    _need(type(expected['runtime_instance_id']) is str and
          expected['runtime_instance_id'] == binding['runtime_instance_id'], 'REPLAY_STALE_RUNTIME')
    _integer(expected['generation'], 1, 2147483647)
    _need(expected['generation'] == binding['generation'], 'REPLAY_STALE_GENERATION')
    for name in ('source_closure_sha256', 'runtime_snapshot_sha256'):
        _hash(expected[name])
        _need(expected[name] == binding[name], 'REPLAY_STALE_SOURCE' if name.startswith('source') else 'REPLAY_STALE_SNAPSHOT')
    _hash(expected['report_sha256'])
    _integer(expected['pid'], 1, 4294967295, 'REPLAY_INVALID_PID')
    _need(type(expected['process_start']) is str and _PROCESS_START.fullmatch(expected['process_start'])
          and int(expected['process_start'].split(':')[1]) <= 18446744073709551615, 'REPLAY_INVALID_PROCESS_START')
    properties = payload['properties']
    _need(type(properties) is list and 1 <= len(properties) <= len(INSPECT_PROPERTIES), 'REPLAY_PROPERTY_LIMIT')
    _need(all(type(name) is str and name in INSPECT_PROPERTIES for name in properties)
          and len(set(properties)) == len(properties), 'REPLAY_UNSUPPORTED_PROPERTY')
    phase = payload.get('phase')
    _need(phase is None or type(phase) is str and phase in PHASES, 'REPLAY_INVALID_PHASE')
    lower, upper = payload.get('tick_min', 0), payload.get('tick_max', 599)
    _integer(lower, 0, 599, 'REPLAY_TICK_RANGE')
    _integer(upper, lower, 599, 'REPLAY_TICK_RANGE')
    _integer(payload.get('page_size', MAX_INSPECT_PAGE), 1, MAX_INSPECT_PAGE, 'REPLAY_PAGE_LIMIT')
    cursor = payload.get('cursor')
    _need(cursor is None or type(cursor) is str and len(cursor) <= MAX_CURSOR_CHARS and _CURSOR.fullmatch(cursor),
          'REPLAY_INVALID_CURSOR')


def validate_request(body: dict | bytes, context: ReplayContext) -> Request:
    """Return a defensive accepted Request; revalidate at effect admission.

    The accepted Request contains JSON mappings, so it is not an authority
    object. The session/owner separately admits, journals and rechecks effects.
    Report/PID/process equality and cursor signatures belong to the inspector.
    """
    try:
        binding = _context(context)
        _need(type(body) in (dict, bytes), 'REPLAY_REQUEST_REQUIRED')
        if type(body) is bytes:
            value = parse_json_utf8(body)
        else:
            raw = canonical_bytes(body)
            _need(len(raw) <= MAX_WIRE_BYTES, 'ENVELOPE_TOO_LARGE')
            value = parse_json_utf8(raw)
        validate_envelope(value, now_ms=context.now_ms)
        request = Request.from_dict(value)
        validate_for_dispatch(request, discovery(context.project_id, runtime_enabled=context.runtime_enabled))
        _need(type(request.command_id) is str and _ID.fullmatch(request.command_id), 'REPLAY_INVALID_COMMAND_ID')
        _need(dict(request.target) == {'stable_id': binding['runtime_instance_id']}, 'REPLAY_TARGET_MISMATCH')
        _need(request.expected_revision == context.prepared.revision, 'REPLAY_STALE_REVISION')
        _need(request.lease_id == context.lease_id and request.fencing_epoch == context.fencing_epoch,
              'REPLAY_STALE_LEASE')
        _need(context.now_ms < request.deadline_ms <= min(context.now_ms + MAX_COMMAND_MS,
              context.lease_expires_ms), 'REPLAY_DEADLINE_OUT_OF_RANGE')
        _need(len(canonical_bytes(request.payload)) <= MAX_PAYLOAD_BYTES, 'REPLAY_PAYLOAD_LIMIT')
        payload = request.payload
        if request.operation == 'play.inspect':
            _inspect(payload, binding)
        else:
            _shape(payload, _PRECONDITIONS | ({'trace_sha256'} if request.operation == 'play.start' else {'label'}))
            _preconditions(payload, binding)
            if request.operation == 'play.start':
                _hash(payload['trace_sha256'])
                _need(payload['trace_sha256'] == binding['trace_sha256'], 'REPLAY_STALE_TRACE')
            else:
                _need(type(payload['label']) is str and payload['label'] in context.prepared.capture_labels,
                      'REPLAY_UNDECLARED_CAPTURE')
        return request
    except (ValidationError, SafetyViolation) as error:
        # Never echo an arbitrary field value or secret in a public error.
        raise ReplayContractError(error.code) from None


def artifact_reference(*, kind: str, sha256: str, size_bytes: int) -> dict:
    """Validate reference metadata only; no path, inline bytes or existence claim."""
    _need(type(kind) is str and kind in _ARTIFACT_LIMITS, 'REPLAY_ARTIFACT_KIND')
    _hash(sha256)
    _integer(size_bytes, 1, _ARTIFACT_LIMITS[kind], 'REPLAY_ARTIFACT_SIZE')
    return {'kind': kind, 'sha256': sha256, 'size_bytes': size_bytes}
