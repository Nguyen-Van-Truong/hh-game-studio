"""Always-on bounded benchmark observations, separate from command receipts.

Factories delegate once to the unchanged host, journal and HTTP operations.
One producer owns one recorder for its whole lifetime, including cleanup.
The rolling window is supplemental attribution, never an acceptance exemption
or a complete transport log. No request bodies, credentials, exception text,
socket objects, disk I/O, retries or per-chunk instrumentation are retained.
"""
from collections import deque, namedtuple
from array import array
from contextlib import ExitStack, contextmanager
import http.client
import math
import os
import re
import threading
import time
from studio.tests.replay.benchmark_transport_metadata import (
    TransportMetadataError, validate_transport_event,
)


PHASES = frozenset({
    'client.call', 'client.connect', 'client.request', 'client.headers', 'client.body',
    'server.handle', 'server.read_request', 'server.dispatch', 'server.lookup',
    'server.send', 'host.finish', 'journal.guard_wait', 'journal.guard_held',
    'journal.snapshot', 'journal.reload', 'journal.append', 'journal.load',
})
ROUTES = frozenset({'discovery', 'lease', 'commands', 'lookup', 'archive', 'cancel', 'stop', 'other'})
ENDPOINTS = {'/v1/' + name: name for name in ROUTES if name != 'other'}
_WINDOW_FIELDS = frozenset({'schema_id', 'schema_version', 'formal_acceptance', 'pid', 'clock',
    'captured_ns', 'event_capacity', 'active_capacity', 'events_evicted', 'spans_dropped',
    'identity_missing', 'failure_trigger', 'transport_failures_by_route',
    'transport_events', 'transport_events_evicted', 'events', 'unfinished'})
_SPAN_FIELDS = frozenset({'span_id', 'parent_id', 'root_id', 'thread_id', 'phase', 'route',
    'server_port', 'client_port', 'started_ns'})
_EVENT_FIELDS = _SPAN_FIELDS | {'event_id', 'kind', 'timestamp_ns', 'outcome'}
_Event = namedtuple('_Event', 'span_id parent_id root_id thread_id phase route '
                   'server_port client_port started_ns event_id kind timestamp_ns outcome')


def validate_phase_snapshot(snapshot, expected_pid):
    """Validate supplemental structure, never turn observed gaps into new gates.

    Rolling-window evictions, dropped spans, unavailable socket identities and
    transport failures remain visible, valid observations. The command/profile
    verifier alone decides the existing workload and performance thresholds.
    """
    def need(condition):
        if not condition:
            raise ValueError('INVALID_HTTP_PHASE_SNAPSHOT')

    def integer(value, minimum=0):
        return type(value) is int and value >= minimum

    def shape(value, fields):
        need(type(value) is dict and set(value) == fields)

    def span(row, captured, *, event):
        shape(row, _EVENT_FIELDS if event else _SPAN_FIELDS)
        need(integer(row['span_id'], 1) and integer(row['root_id'], 1)
             and integer(row['thread_id'], 1) and integer(row['started_ns'])
             and row['started_ns'] <= captured)
        parent = row['parent_id']
        need(parent is None or integer(parent, 1) and parent < row['span_id'])
        need(row['root_id'] == row['span_id'] if parent is None
             else row['root_id'] <= parent)
        need(type(row['phase']) is str and row['phase'] in PHASES
             and type(row['route']) is str and row['route'] in ROUTES)
        ports = row['server_port'], row['client_port']
        need(ports == (None, None) or all(integer(port, 1) and port < 65536 for port in ports))
        if event:
            need(integer(row['event_id'], 1) and integer(row['timestamp_ns'])
                 and row['started_ns'] <= row['timestamp_ns'] <= captured)
            need(type(row['kind']) is str and row['kind'] in {'enter', 'bind', 'exit'})
            need(type(row['outcome']) is str and row['outcome'] in ('returned', 'raised') if row['kind'] == 'exit'
                 else row['outcome'] is None)

    def transport_event(row):
        try:
            validate_transport_event(row)
        except TransportMetadataError:
            raise ValueError('INVALID_HTTP_PHASE_SNAPSHOT')

    def window(value, *, first):
        shape(value, _WINDOW_FIELDS | ({'failed_call_id'} if first else
                                      {'transport_failures_observed', 'first_failure'}))
        need(value['schema_id'] == 'hh-studio.benchmark-http-phase-window'
             and value['schema_version'] == '1.0.0' and value['formal_acceptance'] is False
             and type(value['pid']) is int and value['pid'] == expected_pid
             and value['clock'] == 'perf_counter_ns'
             and value['failure_trigger'] == 'first_lookup_transport_failure')
        need(integer(value['captured_ns'])
             and integer(value['event_capacity'], 1) and value['event_capacity'] <= 8192
             and integer(value['active_capacity'], 1) and value['active_capacity'] <= 64)
        for key in ('events_evicted', 'spans_dropped', 'identity_missing'):
            need(integer(value[key]))
        need(integer(value['transport_events_evicted']))
        need(type(value['transport_events']) is list and len(value['transport_events']) <= 64)
        for row in value['transport_events']:
            transport_event(row)
        routes = value['transport_failures_by_route']
        shape(routes, ROUTES)
        need(all(integer(count) for count in routes.values()))
        need(type(value['events']) is list and len(value['events']) <= value['event_capacity']
             and type(value['unfinished']) is list and len(value['unfinished']) <= value['active_capacity'])
        need(value['events_evicted'] == 0 or len(value['events']) == value['event_capacity'])
        previous = value['events_evicted']
        for row in value['events']:
            span(row, value['captured_ns'], event=True)
            need(row['event_id'] == previous + 1)
            previous = row['event_id']
        seen = set()
        for row in value['unfinished']:
            span(row, value['captured_ns'], event=False)
            need(row['span_id'] not in seen)
            seen.add(row['span_id'])
        if first:
            failed = value['failed_call_id']
            need(failed is None or integer(failed, 1))
            if failed is not None:
                need(any(row['span_id'] == failed and row['phase'] == 'client.call'
                         and row['route'] == 'lookup' for row in value['events'] + value['unfinished']))
            need(routes['lookup'] > 0)
        else:
            need(integer(value['transport_failures_observed'])
                 and value['transport_failures_observed'] == sum(routes.values()))

    need(integer(expected_pid, 1))
    window(snapshot, first=False)
    first = snapshot['first_failure']
    if first is None:
        need(snapshot['transport_failures_by_route']['lookup'] == 0)
        return
    window(first, first=True)
    need(first['captured_ns'] <= snapshot['captured_ns'])
    for key in ('event_capacity', 'active_capacity'):
        need(first[key] == snapshot[key])
    for key in ('events_evicted', 'spans_dropped', 'identity_missing'):
        need(first[key] <= snapshot[key])
    need(all(count <= snapshot['transport_failures_by_route'][route]
             for route, count in first['transport_failures_by_route'].items()))


def route_for(path):
    return ENDPOINTS.get(path, 'other') if type(path) is str else 'other'


def loopback_pair(stream, *, client):
    """Only numeric (server port, client port); no address or socket retention."""
    if stream is None:
        return None
    try:
        local, peer = stream.getsockname(), stream.getpeername()
        if (type(local) is not tuple or type(peer) is not tuple
                or len(local) != 2 or len(peer) != 2
                or local[0] != '127.0.0.1' or peer[0] != '127.0.0.1'
                or type(local[1]) is not int or type(peer[1]) is not int
                or not 0 < local[1] < 65536 or not 0 < peer[1] < 65536):
            return None
        return (peer[1], local[1]) if client else (local[1], peer[1])
    except OSError:
        return None


class PhaseRecorder:
    """Immutable event ring plus bounded unfinished spans and first-failure window.

    IDs are recorder-local. Entries precede the operation; timestamps are QPC
    perf_counter_ns, including snapshots. Instrumentation time is not subtracted.
    """

    def __init__(self, *, event_capacity=512, active_capacity=64):
        if (type(event_capacity) is not int or not 1 <= event_capacity <= 8192
                or type(active_capacity) is not int or not 1 <= active_capacity <= 64):
            raise ValueError('INVALID_OBSERVATION_CAPACITY')
        self._lock, self._local = threading.Lock(), threading.local()
        self._events, self._active = deque(maxlen=event_capacity), {}
        self._event_capacity, self._active_capacity = event_capacity, active_capacity
        self._next_span, self._next_event = 0, 0
        self._evicted, self._overflow, self._identity_missing = 0, 0, 0
        self._failure_count, self._first_failure = 0, None
        self._failures_by_route = {route: 0 for route in sorted(ROUTES)}
        self._transport_events = deque(maxlen=64)
        self._transport_events_evicted = 0
        self._pid = os.getpid()

    def _stack(self):
        if not hasattr(self._local, 'stack'):
            self._local.stack = []
        return self._local.stack

    def _emit(self, row, kind, timestamp_ns, outcome=None):
        # Caller holds only this recorder's mutex, never across delegated work.
        self._next_event += 1
        self._evicted += int(len(self._events) == self._event_capacity)
        self._events.append(_Event(**row, event_id=self._next_event, kind=kind,
                                   timestamp_ns=timestamp_ns, outcome=outcome))

    @contextmanager
    def span(self, phase, *, route=None):
        if type(phase) is not str or phase not in PHASES:
            raise ValueError('INVALID_OBSERVATION_PHASE')
        if route is not None and (type(route) is not str or route not in ROUTES):
            raise ValueError('INVALID_OBSERVATION_ROUTE')
        stack, span_id = self._stack(), None
        with self._lock:
            if len(self._active) >= self._active_capacity:
                self._overflow += 1
            else:
                parent = self._active.get(stack[-1]) if stack else None
                self._next_span += 1
                span_id = self._next_span
                row = {'span_id': span_id, 'parent_id': parent['span_id'] if parent else None,
                       'root_id': parent['root_id'] if parent else span_id,
                       'thread_id': threading.get_ident(), 'phase': phase,
                       'route': route or (parent['route'] if parent else 'other'),
                       'server_port': parent['server_port'] if parent else None,
                       'client_port': parent['client_port'] if parent else None,
                       'started_ns': time.perf_counter_ns()}
                self._active[span_id] = row
                stack.append(span_id)
                self._emit(row, 'enter', row['started_ns'])
        returned = False
        try:
            yield span_id
            returned = True
        finally:
            if span_id is not None:
                ended = time.perf_counter_ns()
                with self._lock:
                    row = self._active.pop(span_id)
                    stack.pop()
                    self._emit(row, 'exit', ended, 'returned' if returned else 'raised')

    def bind_socket(self, stream, *, client):
        pair = loopback_pair(stream, client=client)
        with self._lock:
            if pair is None:
                self._identity_missing += 1
                return
            timestamp = time.perf_counter_ns()
            for span_id in self._stack():
                row = self._active[span_id]
                if (row['server_port'], row['client_port']) != pair:
                    row['server_port'], row['client_port'] = pair
                    self._emit(row, 'bind', timestamp)

    def _snapshot(self):
        # All retained fields are fixed enums, integers, booleans or None.
        # Share immutable event rows with the ring at failure time. Eviction or
        # socket rebinding cannot mutate this window; dictionaries are expanded
        # only for the external snapshot, never retained twice in the producer.
        return {'schema_id': 'hh-studio.benchmark-http-phase-window', 'schema_version': '1.0.0',
                'formal_acceptance': False,
                'pid': self._pid, 'clock': 'perf_counter_ns',
                'captured_ns': time.perf_counter_ns(),
                'event_capacity': self._event_capacity, 'active_capacity': self._active_capacity,
                'events_evicted': self._evicted, 'spans_dropped': self._overflow,
                'identity_missing': self._identity_missing,
                'failure_trigger': 'first_lookup_transport_failure',
                'transport_failures_by_route': dict(self._failures_by_route),
                'transport_events': list(self._transport_events),
                'transport_events_evicted': self._transport_events_evicted,
                'events': tuple(self._events),
                'unfinished': [dict(row) for row in self._active.values()]}

    @staticmethod
    def _materialize(window):
        return dict(window,
                    transport_failures_by_route=dict(window['transport_failures_by_route']),
                    events=[row._asdict() for row in window['events']],
                    unfinished=[dict(row) for row in window['unfinished']])

    def capture_failure(self, call_id, *, route):
        """Count every route; freeze only lookup, before retry clears metadata.

        An earlier non-lookup transport failure must not consume the target
        lookup window. A commands drop is injected only in the focused tests;
        it is not asserted to occur in the current coupled producer.
        """
        if call_id is not None and (type(call_id) is not int or call_id <= 0):
            raise ValueError('INVALID_OBSERVATION_CALL_ID')
        if type(route) is not str or route not in ROUTES:
            raise ValueError('INVALID_OBSERVATION_ROUTE')
        with self._lock:
            self._failure_count += 1
            self._failures_by_route[route] += 1
            if route == 'lookup' and self._first_failure is None:
                self._first_failure = self._snapshot()
                self._first_failure['failed_call_id'] = call_id

    def snapshot(self):
        with self._lock:
            result = self._materialize(self._snapshot())
            first = self._first_failure
            result['transport_failures_observed'] = self._failure_count
            result['first_failure'] = None if first is None else self._materialize(first)
            return result

    def capture_transport(self, event):
        """Keep bounded phase-keyed transport diagnostics without secrets."""
        try:
            validate_transport_event(event)
        except TransportMetadataError as error:
            raise ValueError('INVALID_TRANSPORT_EVENT') from error
        if type(event) is not dict:
            raise ValueError('INVALID_TRANSPORT_EVENT')
        with self._lock:
            if len(self._transport_events) == self._transport_events.maxlen:
                self._transport_events_evicted += 1
            self._transport_events.append(dict(event))


def observed_connection_type(base, recorder):
    """Return an HTTPConnection subclass; caller installs it only in its process."""
    class Response(base.response_class):
        def read(self, *args, **kwargs):
            with recorder.span('client.body'):
                return super().read(*args, **kwargs)

    class Connection(base):
        response_class = Response

        def connect(self):
            with recorder.span('client.connect'):
                try:
                    return super().connect()
                finally:
                    # Bind immediately after connect, before request send can hang.
                    recorder.bind_socket(self.sock, client=True)

        def request(self, *args, **kwargs):
            with recorder.span('client.request'):
                return super().request(*args, **kwargs)

        def getresponse(self):
            with recorder.span('client.headers'):
                return super().getresponse()

    return Connection


def observed_client_type(base, recorder):
    """Base is BenchmarkFixtureClient, preserving its existing failure metadata."""
    connection_type = observed_connection_type(http.client.HTTPConnection, recorder)

    class Client(base):
        def _connection(self, port):
            # Per-producer connection type; never patch the global HTTP module.
            return connection_type('127.0.0.1', port, timeout=self.timeout)

        def _call(self, path, body, *, control=False):
            route = route_for(path)
            # Some protocol-only test clients do not inherit the transport
            # observation mixin.  Keep the observer compatible with those
            # clients while still recording all O6 events for real clients.
            cursor = getattr(self, 'transport_event_total', 0)
            with recorder.span('client.call', route=route) as call_id:
                result = super()._call(path, body, control=control)
                read_events = getattr(self, 'transport_events_since', None)
                if read_events is not None:
                    for event in read_events(cursor):
                        recorder.capture_transport(event)
                if self.last_transport_failure is not None:
                    recorder.capture_failure(call_id, route=route)
                return result

    return Client


def observed_host_type(base, recorder):
    class Host(base):
        def _handle(self, stream, listener):
            with recorder.span('server.handle'):
                recorder.bind_socket(stream, client=False)
                return super()._handle(stream, listener)

        def _read_request(self, stream):
            with recorder.span('server.read_request'):
                return super()._read_request(stream)

        def _dispatch(self, path, body, session, control):
            with recorder.span('server.dispatch', route=route_for(path)):
                return super()._dispatch(path, body, session, control)

        def _lookup(self, command_id):
            with recorder.span('server.lookup'):
                return super()._lookup(command_id)

        def _send(self, stream, value, status=200, redactor=None):
            with recorder.span('server.send'):
                return super()._send(stream, value, status, redactor)

        def _finish(self, job, response):
            with recorder.span('host.finish'):
                return super()._finish(job, response)

    return Host


class JournalTimingBook:
    """Bounded direct journal timings for the O5 host-only diagnostic.

    The first 5,000 and rolling last 5,000 samples are retained by operation;
    counters also prove how often reload/load/tail paths were entered. This
    supplemental book is separate from the HTTP phase ring and is never an
    acceptance override.
    """
    def __init__(self, *, window=5000):
        if type(window) is not int or window <= 0:
            raise ValueError('INVALID_JOURNAL_TIMING_WINDOW')
        self._lock = threading.Lock()
        self._window = window
        # Numeric buffers are one fixed observation allocation at startup,
        # rather than cardinality-growing Python float objects during soak.
        self._first = {key: array('d', [0]) * window for key in ('lookup', 'append')}
        self._last = {key: array('d', [0]) * window for key in ('lookup', 'append')}
        self._batch = {key: array('d', [0]) * 4096 for key in ('lookup', 'append')}
        self._batch_counts = {'lookup': 0, 'append': 0}
        self._batch_dropped = {'lookup': 0, 'append': 0}
        self._counts = {'lookup': 0, 'append': 0, 'reload': 0, 'load': 0,
                        'tail_replay': 0, 'no_tail': 0}

    def operation(self, name, elapsed_ns):
        with self._lock:
            self._counts[name] += 1
            if name in self._first:
                ordinal = self._counts[name] - 1
                value = elapsed_ns / 1_000_000
                if ordinal < self._window:
                    self._first[name][ordinal] = value
                self._last[name][ordinal % self._window] = value
                batch = self._batch_counts[name]
                if batch < len(self._batch[name]):
                    self._batch[name][batch] = value
                    self._batch_counts[name] += 1
                else:
                    self._batch_dropped[name] += 1

    def path(self, name):
        with self._lock:
            self._counts[name] += 1

    def snapshot(self):
        with self._lock:
            def last(key):
                count = self._counts[key]
                if count <= self._window:
                    return list(self._last[key][:count])
                pivot = count % self._window
                return list(self._last[key][pivot:]) + list(self._last[key][:pivot])
            return {'window': self._window,
                    'first_ms': {key: list(value[:min(self._counts[key], self._window)])
                                 for key, value in self._first.items()},
                    'last_ms': {key: last(key) for key in self._last},
                    'counts': dict(self._counts), 'formal_acceptance': False}

    def take_batch(self):
        with self._lock:
            result = {'latency_ms': {key: list(value[:self._batch_counts[key]])
                                    for key, value in self._batch.items()},
                      'dropped': dict(self._batch_dropped), 'counts': dict(self._counts),
                      'formal_acceptance': False}
            for key in self._batch_counts:
                self._batch_counts[key] = self._batch_dropped[key] = 0
            return result


def observed_journal_type(base, recorder, timings=None):
    class Journal(base):
        def _timed(self, name, action, *args, **kwargs):
            started = time.perf_counter_ns()
            try:
                return action(*args, **kwargs)
            finally:
                if timings is not None:
                    timings.operation(name, time.perf_counter_ns() - started)

        def _snapshot(self, *, synchronize):
            with recorder.span('journal.snapshot'):
                return super()._snapshot(synchronize=synchronize)

        def _reload(self):
            if timings is not None:
                timings.path('reload')
            with recorder.span('journal.reload'):
                return super()._reload()

        def _append(self, record):
            with recorder.span('journal.append'):
                return self._timed('append', super()._append, record)

        def _load(self):
            if timings is not None:
                timings.path('load')
            with recorder.span('journal.load'):
                return super()._load()

        def _tail_replay(self):
            if timings is not None:
                timings.path('tail_replay')
            before = self._verified_size
            result = super()._tail_replay()
            if timings is not None and result and self._verified_size == before:
                timings.path('no_tail')
            return result

        def lookup(self, *args, **kwargs):
            return self._timed('lookup', super().lookup, *args, **kwargs)

        @contextmanager
        def _writer_lock(self):
            with ExitStack() as guard:
                with recorder.span('journal.guard_wait'):
                    value = guard.enter_context(super()._writer_lock())
                with recorder.span('journal.guard_held'):
                    # Release/suppression/error mapping remain the base's work;
                    # close inside held so it includes the original guard exit.
                    with guard:
                        yield value

    return Journal
