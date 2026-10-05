"""Private typed-update gate into the existing registered editor owner.

Only the common position/scale update vocabulary is supported. This validator
does not issue grants, mutate an editor, save files or enable an AUTH profile.
The owner supplies its freshly inspected context while holding admission, then
uses its existing accepted projection and effect-time lease checks unchanged.
"""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys

from studio.host.core.limits import SafetyViolation
from studio.protocol.core import canonical_bytes, parse_json

HERE = Path(__file__).resolve().parent
CATALOG = HERE.parent / 'contracts/godot-authoring-schema-v1.json'


class AuthoringUpdateBridgeError(SafetyViolation):
    pass


def _need(value, code):
    if not value:
        raise AuthoringUpdateBridgeError(code)


def _read(path):
    for component in (path, *path.parents):
        info = component.stat(follow_symlinks=False)
        _need(not component.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400,
              'AUTHORING_BRIDGE_REPARSE')
    _need(path.is_file() and path.stat().st_size <= 256 * 1024, 'AUTHORING_BRIDGE_SOURCE_SIZE')
    return path.read_bytes()


class AuthoringUpdateBridge:
    def __init__(self):
        contract_path = HERE / 'authoring_contract.py'
        paths = (Path(__file__).resolve(), contract_path, CATALOG)
        captured = {path: _read(path) for path in paths}
        self._sources = {path: hashlib.sha256(raw).hexdigest() for path, raw in captured.items()}
        raw = captured[contract_path]
        key = '_hh_authoring_update_' + hashlib.sha256(str(contract_path).encode() + b'\0' + raw).hexdigest()
        if key not in sys.modules:
            spec = importlib.util.spec_from_file_location(key, contract_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[key] = module
            try:
                exec(compile(raw, str(contract_path), 'exec', dont_inherit=True), module.__dict__)
            except BaseException:
                del sys.modules[key]
                raise
        self._candidate = sys.modules[key]
        self._catalog = self._candidate.load_catalog()
        _need(canonical_bytes(self._catalog.as_dict()) == canonical_bytes(parse_json(captured[CATALOG])['x-candidate']),
              'AUTHORING_BRIDGE_SOURCE_CHANGED')
        self._same_sources()

    def _same_sources(self):
        _need(all(hashlib.sha256(_read(path)).hexdigest() == digest for path, digest in self._sources.items()),
              'AUTHORING_BRIDGE_SOURCE_CHANGED')

    def validate(self, request, context, accepted):
        """Extra validation only; context/accepted come from owner admission.

        Exact historical retries bypass new admission entirely. No request is
        rewritten, so candidate/accepted paths keep the same dedupe identity.
        """
        self._same_sources()
        _need(request.operation == 'scene.node.update', 'AUTHORING_BRIDGE_OPERATION')
        changes = request.payload.get('changes')
        _need(type(changes) is dict and changes and set(changes) <= {'position', 'scale'},
              'AUTHORING_BRIDGE_PROPERTIES')
        target = next((node for node in context.nodes if node.stable_id == request.target.get('stable_id')), None)
        _need(target is not None and target.node_type in ('Node3D', 'MeshInstance3D'), 'AUTHORING_BRIDGE_TARGET')
        model = self._candidate
        observed = model.ValidationContext(context.project_id, context.revision, context.project_revision,
            context.generation, context.lease_id, context.fencing_epoch, context.lease_expires_ms,
            context.now_ms, tuple(model.NodeState(node.stable_id, node.parent_id, node.node_type, node.name)
                                  for node in context.nodes), stopped=context.stopped)
        candidate = model.validate_request(request, observed, self._catalog)
        _need(candidate.request_digest == accepted.request_digest == request.digest
              and canonical_bytes(candidate.projection) == canonical_bytes(accepted.projection),
              'AUTHORING_BRIDGE_PROJECTION_MISMATCH')
        return candidate
