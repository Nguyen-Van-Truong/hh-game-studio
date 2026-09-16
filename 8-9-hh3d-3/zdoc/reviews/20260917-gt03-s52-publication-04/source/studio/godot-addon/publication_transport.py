"""Two bounded loopback listeners for the Godot owner, without fixture routing.

Reuse the accepted byte-limited HTTP reader/writer verbatim by delegation.
No fixture host is constructed, no fixture scope grants Godot authority, and
the transport never creates an engine receipt or declares a commit itself.
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


class _Connection(socketserver.BaseRequestHandler):
    def handle(self):
        self.server.owner._handle(self.request, self.server.control)


class _Port(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = False
    daemon_threads = True
    block_on_close = False
    request_queue_size = 2

    def __init__(self, owner, control):
        self.owner, self.control = owner, control
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
        self.owner.diagnostics.append('GODOT_HANDLER_FAILED')


class PublicationTransport:
    # These methods access only limits/ports/origins/sessions/redactor. Their
    # exact implementation remains in the frozen accepted core source.
    _read_request = LoopbackFixtureHost._read_request
    _send = LoopbackFixtureHost._send

    def __init__(self, owner):
        self.owner, self.sessions = owner, owner.sessions
        self.limits = TransportLimits(max_connections=2, max_control_connections=2)
        self.allowed_origins = frozenset()
        self._redactor = Redactor()
        self._guard = threading.Lock()
        self._connections = 0
        self._drained = threading.Event(); self._drained.set()
        self._threads = []
        self._server_threads = {}
        self._closed = False
        self.diagnostics = deque(maxlen=32)
        self._main = _Port(self, False)
        try:
            self._control = _Port(self, True)
        except BaseException:
            self._main.server_close()
            raise

    @property
    def port(self):
        return self._main.server_address[1]

    @property
    def control_port(self):
        return self._control.server_address[1]

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
            raise SafetyViolation('GODOT_TRANSPORT_ALREADY_STARTED')
        try:
            for server in (self._main, self._control):
                thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval':.05},
                                          name='hh-godot-loopback', daemon=True)
                self._threads.append(thread)
                self._server_threads[server] = thread
                thread.start()
        except BaseException:
            self.close()
            raise
        return self

    def close(self):
        if not self._closed:
            for server in (self._main, self._control):
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
            raise SafetyViolation('GODOT_TRANSPORT_DRAIN_REQUIRED')

    def _handle(self, stream, control):
        command_id = 'transport.request'
        try:
            path, headers, raw = self._read_request(stream)
            body = parse_json_utf8(raw)
            if type(body) is not dict:
                raise SafetyViolation('INVALID_ENVELOPE')
            candidate = body.get('command_id')
            if candidate is not None:
                self.sessions.validate_public_identifier(candidate)
                command_id = candidate
            routes = ({'/v1/lookup':'lookup', '/v1/stop':'stop'} if control else
                      {'/v1/discovery':'discover', '/v1/lease':'lease', '/v1/commands':'submit'})
            if path not in routes:
                raise SafetyViolation('UNSUPPORTED_ROUTE')
            result = getattr(self.owner, routes[path])(body, authorization=headers.get('authorization', ''),
                catalog_digest=headers.get('x-hh-catalog', ''))
            self._send(stream, result)
        except (SafetyViolation, ValidationError) as exc:
            code = exc.code if re.fullmatch(r'[A-Z][A-Z0-9_]{0,63}', exc.code) else 'GODOT_REQUEST_REJECTED'
            self.diagnostics.append(code)
            self._error(stream, 'REJECTED', code, command_id, 400)
        except (OSError, TimeoutError):
            self.diagnostics.append('GODOT_TRANSPORT_DISCONNECTED')
        except Exception:
            self.diagnostics.append('GODOT_TRANSPORT_FAILED')
            self._error(stream, 'UNKNOWN', 'GODOT_TRANSPORT_FAILED', command_id, 500)

    def _error(self, stream, status, code, command_id, http_status):
        try:
            self._send(stream, {'status':status, 'code':code, 'command_id':command_id,
                               'public_ack':False}, http_status)
        except OSError:
            pass
