"""Bounded diagnostic phase observations; importing this file installs nothing.

Factories delegate to caller-supplied pinned classes in a future disposable
HTTP diagnostic process. No runtime imports, wire fields, retries or disk IO.
"""
from collections import deque
from contextlib import ExitStack, contextmanager
import os
import threading
import time


PHASES = frozenset({
    'client.call', 'client.connect', 'client.request', 'client.headers', 'client.body',
    'server.handle', 'server.read_request', 'server.dispatch', 'server.lookup',
    'server.send', 'host.finish', 'journal.guard_wait', 'journal.guard_held',
    'journal.snapshot', 'journal.reload', 'journal.append', 'journal.load',
})
ROUTES = frozenset({'discovery', 'lease', 'commands', 'lookup', 'archive', 'cancel', 'stop', 'other'})
ENDPOINTS = {'/v1/' + name: name for name in ROUTES if name != 'other'}


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
    """Primitive event ring plus bounded unfinished spans and first-failure copy.

    IDs are recorder-local. Entries precede the operation; timestamps are QPC
    perf_counter_ns, including snapshots. Instrumentation time is not subtracted.
    """

    def __init__(self, *, event_capacity=512, active_capacity=64):
        if (type(event_capacity) is not int or not 1 <= event_capacity <= 8192
                or type(active_capacity) is not int or not 1 <= active_capacity <= 256):
            raise ValueError('INVALID_OBSERVATION_CAPACITY')
        self._lock, self._local = threading.Lock(), threading.local()
        self._events, self._active = deque(maxlen=event_capacity), {}
        self._event_capacity, self._active_capacity = event_capacity, active_capacity
        self._next_span, self._next_event = 0, 0
        self._evicted, self._overflow, self._identity_missing = 0, 0, 0
        self._failure_count, self._first_failure = 0, None
        self._failures_by_route = {route: 0 for route in sorted(ROUTES)}
        self._pid = os.getpid()

    def _stack(self):
        if not hasattr(self._local, 'stack'):
            self._local.stack = []
        return self._local.stack

    def _emit(self, row, kind, timestamp_ns, outcome=None):
        # Caller holds only this recorder's mutex, never across delegated work.
        self._next_event += 1
        self._evicted += int(len(self._events) == self._event_capacity)
        self._events.append(dict(row, event_id=self._next_event, kind=kind,
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
        return {'schema': 'HH-S95-HTTP-PHASES-1', 'formal_acceptance': False,
                'pid': self._pid, 'clock': 'perf_counter_ns',
                'captured_ns': time.perf_counter_ns(),
                'event_capacity': self._event_capacity, 'active_capacity': self._active_capacity,
                'events_evicted': self._evicted, 'spans_dropped': self._overflow,
                'identity_missing': self._identity_missing,
                'failure_trigger': 'first_lookup_transport_failure',
                'transport_failures_by_route': dict(self._failures_by_route),
                'events': [dict(row) for row in self._events],
                'unfinished': [dict(row) for row in self._active.values()]}

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
            result = self._snapshot()
            first = self._first_failure
            result['transport_failures_observed'] = self._failure_count
            result['first_failure'] = (None if first is None else dict(first,
                transport_failures_by_route=dict(first['transport_failures_by_route']),
                events=[dict(row) for row in first['events']],
                unfinished=[dict(row) for row in first['unfinished']]))
            return result


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
    class Client(base):
        def _call(self, path, body, *, control=False):
            route = route_for(path)
            with recorder.span('client.call', route=route) as call_id:
                result = super()._call(path, body, control=control)
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


def observed_journal_type(base, recorder):
    class Journal(base):
        def _snapshot(self, *, synchronize):
            with recorder.span('journal.snapshot'):
                return super()._snapshot(synchronize=synchronize)

        def _reload(self):
            with recorder.span('journal.reload'):
                return super()._reload()

        def _append(self, record):
            with recorder.span('journal.append'):
                return super()._append(record)

        def _load(self):
            with recorder.span('journal.load'):
                return super()._load()

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
