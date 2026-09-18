"""Private in-process credentials, bounded HTTP and typed reviewer projections.

The UI never receives bearer text, headers, paths, arbitrary errors or raw wire
objects. Reconnect only looks up the originally allocated Play command. No
method restarts a stopped owner or retries an uncertain mutation automatically.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import re
import secrets
import socket
import threading
import time

from studio.host.core.transport import epoch_ms
from studio.host.replay import contract
from studio.protocol.core import Request, Response, canonical_bytes, parse_json
from .model import (UiAction, Phase, UiCode, EventKind, ReviewerEvent,
                    HistoricalSummary, ObservationRow, CaptureMetadata)

HTTP_CALL_SECONDS = 8
_HASH = re.compile(r'[0-9a-f]{64}\Z')


def _digest(value):
    _need(type(value) is str and _HASH.fullmatch(value))


def _process(value):
    _need(type(value) is dict and set(value) == {'pid', 'process_start'})
    _need(type(value['pid']) is int and 0 < value['pid'] <= 0xffffffff)
    start = value['process_start']
    _need(type(start) is str and re.fullmatch(r'windows:[1-9][0-9]{0,19}', start))
    _need(int(start.split(':', 1)[1]) <= 18446744073709551615)


class _Rejected(Exception):
    pass


def _need(value):
    if not value:
        raise ValueError('INVALID_REVIEWER_RESPONSE')


class ReplayClient:
    """Trusted controller supplies actual loopback ports and a scoped credential."""
    def __init__(self, *, port, control_port, stop_port, credential, project_id, binding):
        for value in (port, control_port, stop_port):
            _need(type(value) is int and 0 < value < 65536)
        _need(len({port, control_port, stop_port}) == 3)
        contract.PreparedRuntime(binding, ('menu',))
        _need(type(project_id) is str and 0 < len(project_id) <= 128)
        self._ports = (port, control_port, stop_port)
        self._authorization = 'Bearer ' + credential.bearer
        self._project = project_id
        self._binding_raw = canonical_bytes(binding)
        self._command = 'review.play.' + secrets.token_hex(12)
        self._stop_command = 'review.stop.' + secrets.token_hex(12)
        self._attempted = False
        self._launch_inflight = False
        self._stopped = threading.Event()
        self._guard, self._work = threading.Lock(), threading.Lock()
        self._terminal = None
        self._cursor = None

    def _binding(self):
        return json.loads(self._binding_raw)

    def _call(self, route, body):
        port = self._ports[2] if route == '/v1/stop' else self._ports[1] if route == '/v1/lookup' else self._ports[0]
        deadline = time.monotonic() + HTTP_CALL_SECONDS
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=HTTP_CALL_SECONDS)
        timer = None
        expired = threading.Event()
        try:
            connection.connect()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError()
            owned_socket = connection.sock
            def interrupt_owned_socket():
                expired.set()
                try:
                    owned_socket.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
            timer = threading.Timer(remaining, interrupt_owned_socket)
            timer.daemon = True
            timer.start()
            connection.request('POST', route, canonical_bytes(body), {'Content-Type': 'application/json',
                'Authorization': self._authorization, 'X-HH-Catalog': contract.CATALOG_DIGEST})
            response = connection.getresponse()
            raw = response.read(262145)
            if expired.is_set() or time.monotonic() >= deadline:
                raise TimeoutError()
            _need(len(raw) <= 262144)
            value = parse_json(raw)
            if response.status != 200:
                raise _Rejected()
            _need(type(value) is dict)
            return value
        finally:
            if timer is not None:
                timer.cancel()
            connection.close()

    def _submit(self, command, operation, payload):
        _need(not self._stopped.is_set())
        lease = self._call('/v1/lease', {'project_id': self._project, 'ttl_ms': 30_000})
        _need(lease['binding'] == self._binding())
        request = Request(command, self._project, operation, lease['lease_id'], lease['fencing_epoch'],
            lease['expected_revision'], {'stable_id': self._binding()['runtime_instance_id']}, payload,
            'sha256:' + hashlib.sha256(canonical_bytes(payload)).hexdigest(),
            min(lease['expires_ms'], epoch_ms() + 19_000))
        _need(not self._stopped.is_set())
        return self._call('/v1/commands', request.as_dict())

    def _preconditions(self):
        binding = self._binding()
        return {'expected_generation': binding['generation'],
            'expected_snapshot_sha256': binding['runtime_snapshot_sha256'],
            'expected_source_sha256': binding['source_closure_sha256']}

    def _launch_result(self, action, value):
        response = Response.from_dict(value)
        _need(response.command_id == self._command)
        if response.status.value == 'COMMITTED':
            facts = value['postconditions']
            _need(response.code == 'REPLAY_NATIVE_COMPLETED' and facts['binding'] == self._binding())
            artifact = facts['artifact']
            _need(contract.artifact_reference(**artifact) == artifact and artifact['kind'] == 'observation')
            _digest(facts['native_capture_sha256'])
            process = facts['process']
            _process(process)
            # A detached validated DTO also checks the values rendered in Tk.
            summary = self._summary(report_sha256=artifact['sha256'], pid=process['pid'])
            with self._guard:
                self._terminal = canonical_bytes(value)
            if self._stopped.is_set():
                return ReviewerEvent(action, Phase.DRAINING, UiCode.DRAINING)
            return ReviewerEvent(action, Phase.COMMITTED, UiCode.COMPLETED, progress=100, historical=summary)
        if response.status.value == 'ACCEPTED_PENDING':
            return ReviewerEvent(action, Phase.DRAINING if self._stopped.is_set() else Phase.RUNNING,
                                 UiCode.DRAINING if self._stopped.is_set() else UiCode.RUNNING)
        if response.status.value == 'CANCELED':
            self._stopped.set()
            return ReviewerEvent(action, Phase.DRAINING, UiCode.DRAINING)
        phase = Phase.REJECTED if response.status.value == 'REJECTED' else Phase.UNKNOWN
        return ReviewerEvent(action, phase, UiCode.REJECTED if phase is Phase.REJECTED else UiCode.UNKNOWN)

    def _lookup(self, action):
        with self._guard:
            attempted = self._attempted
            launch_inflight = self._launch_inflight
        if launch_inflight:
            # The initial POST may still be obtaining its lease / persisting
            # intent. NOT_FOUND during that interval is not a finished lookup.
            return ReviewerEvent(action, Phase.DRAINING if self._stopped.is_set() else Phase.QUEUED,
                                 UiCode.DRAINING if self._stopped.is_set() else UiCode.QUEUED)
        if not attempted:
            return ReviewerEvent(action, Phase.DRAINING if self._stopped.is_set() else Phase.READY,
                                 UiCode.DRAINING if self._stopped.is_set() else UiCode.NO_COMMAND)
        value = self._call('/v1/lookup', {'project_id': self._project, 'command_id': self._command})
        return self._launch_result(action, value)

    def _summary(self, **values):
        binding = self._binding()
        return HistoricalSummary(source_sha256=binding['source_closure_sha256'],
            snapshot_sha256=binding['runtime_snapshot_sha256'], trace_sha256=binding['trace_sha256'],
            generation=binding['generation'], **values)

    def _retained(self, action):
        with self._guard:
            _need(self._terminal is not None)
            terminal = json.loads(self._terminal)
        facts, binding = terminal['postconditions'], self._binding()
        command = 'review.read.' + secrets.token_hex(12)
        if action is UiAction.INSPECT:
            expected = {key: binding[key] for key in ('runtime_instance_id', 'generation',
                'source_closure_sha256', 'runtime_snapshot_sha256')}
            expected.update(report_sha256=facts['artifact']['sha256'], **facts['process'])
            query = {'expected': expected, 'properties': ['phase', 'body_position', 'sim_tick', 'ui_tick'],
                     'phase': 'PAUSED', 'page_size': 8}
            if self._cursor is not None:
                query['cursor'] = self._cursor
            value = self._submit(command, 'play.inspect', query)
            response = Response.from_dict(value)
            _need(response.command_id == command and response.status.value == 'COMMITTED')
            observed = value['postconditions']['observation']
            _need(observed['schema_id'] == 'hh-studio.retained-play-inspection' and observed['schema_version'] == '1.0.0')
            _need(observed['historical'] is True and observed['live'] is False and observed['completed'] is True)
            provenance = observed['provenance']
            _need(provenance['binding'] == binding and provenance['process'] == facts['process']
                  and provenance['report_sha256'] == facts['artifact']['sha256']
                  and provenance['native_capture_sha256'] == facts['native_capture_sha256'])
            raw_rows = observed['rows']
            _need(type(raw_rows) is list and len(raw_rows) <= 8)
            _need(all(type(row) is dict and set(row) == {'tick', 'properties'}
                and type(row['properties']) is dict and set(row['properties']) == set(query['properties'])
                and row['properties']['phase'] == 'PAUSED' for row in raw_rows))
            rows = tuple(ObservationRow(tick=row['tick'], phase=row['properties']['phase'],
                sim_tick=row['properties']['sim_tick'], ui_tick=row['properties']['ui_tick'],
                body_position=tuple(row['properties']['body_position'])) for row in raw_rows)
            _need(all(a.tick < b.tick for a, b in zip(rows, rows[1:])))
            _need(type(observed['returned_count']) is int and observed['returned_count'] == len(rows))
            cursor = observed['next_cursor']
            _need(cursor is None or type(cursor) is str and 0 < len(cursor) <= 2048)
            summary = self._summary(report_sha256=provenance['report_sha256'], pid=facts['process']['pid'],
                rows=rows, total_matches=observed['total_matches'], has_next=cursor is not None)
            self._cursor = cursor
            code = UiCode.INSPECTION_READY
        else:
            value = self._submit(command, 'play.capture', {**self._preconditions(), 'label': 'menu'})
            response = Response.from_dict(value)
            _need(response.command_id == command and response.status.value == 'COMMITTED')
            result = value['postconditions']
            _need(result['historical'] is True and result['binding'] == binding and result['process'] == facts['process'])
            artifact = result['artifact']
            _need(contract.artifact_reference(**artifact) == artifact and artifact['kind'] == 'capture')
            _need(result['label'] == 'menu' and result['phase'] == 'MENU')
            capture = CaptureMetadata(result['label'], result['observed_tick'], result['phase'],
                                      artifact['sha256'], artifact['size_bytes'])
            summary = self._summary(report_sha256=facts['artifact']['sha256'], pid=facts['process']['pid'], capture=capture)
            code = UiCode.CAPTURE_READY
        return ReviewerEvent(action, Phase.COMMITTED, code, progress=100, historical=summary)

    def perform(self, action: UiAction) -> ReviewerEvent:
        _need(type(action) is UiAction)
        acquired = False
        try:
            if action is UiAction.STOP:
                self._stopped.set()
                reply = self._call('/v1/stop', {'project_id': self._project, 'command_id': self._stop_command})
                _need(reply['stopped'] is True and reply['runtime_instance_id'] == self._binding()['runtime_instance_id'])
                # A Stop receipt acknowledges the latch, not all native handles.
                return ReviewerEvent(action, Phase.DRAINING, UiCode.DRAINING)
            if action is UiAction.LOOKUP:
                return self._lookup(action)
            acquired = self._work.acquire(blocking=False)
            if not acquired:
                return ReviewerEvent(action, Phase.UNKNOWN, UiCode.BUSY)
            if action is UiAction.PLAY:
                with self._guard:
                    attempted = self._attempted
                    self._attempted = True
                    self._launch_inflight = not attempted and not self._stopped.is_set()
                if attempted or self._stopped.is_set():
                    return self._lookup(action)
                try:
                    reply = self._submit(self._command, 'play.start',
                        {**self._preconditions(), 'trace_sha256': self._binding()['trace_sha256']})
                    return self._launch_result(action, reply)
                finally:
                    with self._guard:
                        self._launch_inflight = False
            _need(not self._stopped.is_set())
            return self._retained(action)
        except _Rejected:
            return ReviewerEvent(action, Phase.UNKNOWN if action in (UiAction.STOP, UiAction.LOOKUP)
                                 else Phase.REJECTED, UiCode.REJECTED)
        except (OSError, http.client.HTTPException):
            return ReviewerEvent(action, Phase.DISCONNECTED, UiCode.DISCONNECTED, kind=EventKind.DISCONNECTED)
        except Exception:
            return ReviewerEvent(action, Phase.UNKNOWN, UiCode.INVALID_RESPONSE)
        finally:
            if acquired:
                self._work.release()
