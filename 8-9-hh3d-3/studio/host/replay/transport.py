"""Replay adapter for the accepted three-listener publication transport.

ReplayTransport(owner).start() exposes port, control_port and stop_port.
The owner supplies sessions (ReplaySession), an immutable binding, and
discover/lease/submit/lookup/stop(body, *, authorization, catalog_digest).
The owner still validates every complete envelope and implements effects.

Only discovery, lease and commands use the work listener. Lookup and the
compatible Stop route use control_port; canonical Stop has its own stop_port.
Framing, authentication, finite byte/connection limits, lookup reservation,
response handling and close/drain behavior are inherited without changes.
Owner effects must be stopped/drained before transport.close(). FIFO lease
routes and arbitrary script execution are not part of this adapter.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import MappingProxyType

from studio.host.core.limits import SafetyViolation
from studio.protocol.core import canonical_bytes


_PATH = Path(__file__).resolve().parents[2] / 'godot-addon' / 'publication_transport.py'
_SPEC = importlib.util.spec_from_file_location('hh_gt06_accepted_publication_transport', _PATH)
_ACCEPTED = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_ACCEPTED)


class _BoundSessions:
    """Supply owner scope to the inherited historical-lookup precheck.

    Retain immutable canonical bytes and decode a fresh value on each call;
    neither request data nor later mutation of an owner's returned dict can
    replace the binding used for control admission.
    """

    def __init__(self, owner):
        binding = owner.binding
        self._sessions = owner.sessions
        if type(binding) is not dict or canonical_bytes(binding) != canonical_bytes(self._sessions.binding):
            raise SafetyViolation('REPLAY_TRANSPORT_BINDING')
        self._binding = canonical_bytes(binding)

    def authenticate(self, authorization):
        return self._sessions.authenticate(authorization)

    def authorize(self, authorization, operation, *, project_id, catalog_digest):
        return self._sessions.authorize(authorization, operation, project_id=project_id,
                                       catalog_digest=catalog_digest, binding=json.loads(self._binding))

    def validate_public_identifier(self, identifier):
        return self._sessions.validate_public_identifier(identifier)

    def encode_output(self, value):
        return self._sessions.encode_output(value)


class ReplayTransport(_ACCEPTED.PublicationTransport):
    """Finite loopback transport; no runtime creation or acceptance authority."""

    work_routes = MappingProxyType({'/v1/discovery': 'discover', '/v1/lease': 'lease',
                                    '/v1/commands': 'submit'})

    def __init__(self, owner):
        sessions = _BoundSessions(owner)
        super().__init__(owner)
        self.sessions = sessions
