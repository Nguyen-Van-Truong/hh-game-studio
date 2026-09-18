"""Bounded work, lookup/control and canonical Stop-only Blender client listeners.

Reuse the accepted byte-limited HTTP reader/writer verbatim by delegation.
No fixture host is constructed, no fixture scope grants Blender authority, and
the transport never creates an engine receipt or declares a commit itself.
The owner defines its read-only catalog; this layer grants no write capability.
There is no dependency on Godot adapter code.

Only one authenticated historical lookup may enter owner I/O at a time. The
canonical stop_port accepts only /v1/stop and has its own connection budget,
so incomplete work/control requests and historical reads cannot consume Stop
admission. The existing control-port Stop route remains compatible. This is
isolation from the other listeners, not a universal latency guarantee against
saturation of stop_port itself or arbitrary OS scheduling delays.
"""
from __future__ import annotations

from collections import deque
import re
import socketserver
import threading

from studio.host.core.transport import LoopbackFixtureHost, TransportLimits
from studio.host.core.limits import SafetyViolation, parse_json_utf8
from studio.host.core.redaction import Redactor
from studio.protocol.core import ValidationError


class BlenderClientTransportError(SafetyViolation):
    """Keep the exact transport reachable when active handlers still need drain."""
    def __init__(self, code, cleanup_owner):
        super().__init__(code)
        self.cleanup_owner = cleanup_owner


class _Connection(socketserver.BaseRequestHandler):
    def handle(self):
        self.server.owner._handle(self.request, self.server)


class _ReaderContext:
    """Exact core framing/auth with a Host allowlist for this socket's port."""
    _read_request = LoopbackFixtureHost._read_request

    def __init__(self, owner, port):
        self.limits, self.sessions = owner.limits, owner.sessions
        self.allowed_origins = owner.allowed_origins
        # Both legacy reader aliases intentionally name this one listener.
        self.port = self.control_port = port


class _Port(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = False
    daemon_threads = True
    block_on_close = False
    request_queue_size = 2

    def __init__(self, owner, role):
        self.owner, self.role = owner, role
        self.slots = threading.BoundedSemaphore(2)
        super().__init__(('127.0.0.1', 0), _Connection)

    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        self.owner._entered()
        try:
            super().process_request(request, address)
        except BaseException:
            self.owner._exited()
            self.slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.owner._exited()
            self.slots.release()

    def handle_error(self, request, address):
        self.owner.diagnostics.append('BLENDER_HANDLER_FAILED')


class BlenderClientTransport:
    # Reader and writer implementation remain in the accepted core source.
    # Only the local reader context narrows Host to the actual listener.
    _send = LoopbackFixtureHost._send
    work_routes = {'/v1/discovery':'discover', '/v1/lease':'lease', '/v1/commands':'submit'}

    def __init__(self, owner):
        self.owner, self.sessions = owner, owner.sessions
        self.limits = TransportLimits(max_connections=2, max_control_connections=2)
        self.allowed_origins = frozenset()
        self._redactor = Redactor()
        self._guard = threading.Lock()
        self._lookup_slot = threading.BoundedSemaphore(1)
        self._connections = 0
        self._drained = threading.Event(); self._drained.set()
        self._threads = []
        self._server_threads = {}
        self._closed = False
        self.diagnostics = deque(maxlen=32)
        self._listeners = []
        try:
            for name, role in (('_main', 'work'), ('_control', 'control'), ('_stop', 'stop')):
                server = _Port(self, role)
                self._listeners.append(server)
                setattr(self, name, server)
        except BaseException:
            for server in reversed(self._listeners):
                server.server_close()
            raise
        self._listeners = tuple(self._listeners)

    @property
    def port(self):
        return self._main.server_address[1]

    @property
    def control_port(self):
        return self._control.server_address[1]

    @property
    def stop_port(self):
        """Canonical Stop route, isolated from work/control congestion."""
        return self._stop.server_address[1]

    def _entered(self):
        with self._guard:
            self._connections += 1
            self._drained.clear()

    def _exited(self):
        with self._guard:
            self._connections -= 1
            if self._connections == 0:
                self._drained.set()

    def start(self):
        if self._threads or self._closed:
            raise SafetyViolation('BLENDER_TRANSPORT_ALREADY_STARTED')
        try:
            for server in self._listeners:
                thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval':.05},
                                          name='hh-blender-client-loopback', daemon=True)
                self._threads.append(thread)
                self._server_threads[server] = thread
                thread.start()
        except BaseException:
            try:
                self.close()
            except BaseException as error:
                raise BlenderClientTransportError('BLENDER_TRANSPORT_CLEANUP_REQUIRED', self) from error
            raise
        return self

    def close(self):
        if not self._closed:
            for server in self._listeners:
                thread = self._server_threads.get(server)
                if thread is not None and thread.is_alive():
                    server.shutdown()
                server.server_close()
            self._closed = True
        for thread in self._threads:
            if thread.ident is not None:
                thread.join(timeout=1)
        # Owner Stop/drain precedes transport close. Retain the object on
        # timeout; closing listening sockets does not prove active effects ended.
        if not self._drained.wait(timeout=2) or any(t.is_alive() for t in self._threads):
            raise BlenderClientTransportError('BLENDER_TRANSPORT_DRAIN_REQUIRED', self)

    def _handle(self, stream, listener):
        command_id = 'transport.request'
        lookup_owned = False
        try:
            reader = _ReaderContext(self, listener.server_address[1])
            path, headers, raw = reader._read_request(stream)
            body = parse_json_utf8(raw)
            if type(body) is not dict:
                raise SafetyViolation('INVALID_ENVELOPE')
            candidate = body.get('command_id')
            if candidate is not None:
                self.sessions.validate_public_identifier(candidate)
                command_id = candidate
            if listener is self._stop:
                routes = {'/v1/stop':'stop'}
            elif listener is self._control:
                routes = {'/v1/lookup':'lookup', '/v1/stop':'stop'}
            else:
                routes = self.work_routes
            if path not in routes:
                raise SafetyViolation('UNSUPPORTED_ROUTE')
            if listener is self._control and path == '/v1/lookup':
                # Authenticate operation/project/catalog even when admission
                # is busy. The owner still validates its complete envelope and
                # lifecycle before reading any historical receipt.
                self.sessions.authorize(headers.get('authorization', ''), 'control.lookup',
                    project_id=body.get('project_id'), catalog_digest=headers.get('x-hh-catalog', ''))
                lookup_owned = self._lookup_slot.acquire(blocking=False)
                if not lookup_owned:
                    raise SafetyViolation('BLENDER_LOOKUP_BUSY')
            result = getattr(self.owner, routes[path])(body, authorization=headers.get('authorization', ''),
                catalog_digest=headers.get('x-hh-catalog', ''))
            self._send(stream, result)
        except (SafetyViolation, ValidationError) as exc:
            code = exc.code if re.fullmatch(r'[A-Z][A-Z0-9_]{0,63}', exc.code) else 'BLENDER_REQUEST_REJECTED'
            self.diagnostics.append(code)
            self._error(stream, 'REJECTED', code, command_id, 400)
        except (OSError, TimeoutError):
            self.diagnostics.append('BLENDER_TRANSPORT_DISCONNECTED')
        except Exception:
            self.diagnostics.append('BLENDER_TRANSPORT_FAILED')
            self._error(stream, 'UNKNOWN', 'BLENDER_TRANSPORT_FAILED', command_id, 500)
        finally:
            # Keep the reservation through response send/drain as well as I/O.
            # Disconnects and owner failures must not consume it permanently.
            if lookup_owned:
                self._lookup_slot.release()

    def _error(self, stream, status, code, command_id, http_status):
        try:
            self._send(stream, {'status':status, 'code':code, 'command_id':command_id,
                               'public_ack':False}, http_status)
        except OSError:
            pass
