"""Typed broker-owned restart bindings and durable event high-water custody.

The registry leaf is the OS-protected trust anchor. These records are never
accepted from transport clients. The registry primitive supplies persistence,
the supervisor owns the project writer guard, and the event log validates the
actual chain. A checksum detects damaged records; it is not authentication
against an unrestricted broker-account process or administrator.
"""
from __future__ import annotations

import copy
import hashlib
import ntpath
from pathlib import Path
import re
import threading

from .limits import SafetyViolation, canonical_json, parse_json_utf8
from .private_events import EventBinding, EventHead, _head_valid, _identity_valid
from .safe_open import FileIdentity

MAX_STATE_BYTES = 16 * 1024
MAX_EPOCH = 1_000_000
_SCHEMA = 'hh-fixture-custody-1'


class CustodyError(SafetyViolation):
    def __init__(self, code, *, outcome_unknown=False):
        self.outcome_unknown = outcome_unknown
        super().__init__(code)


def _need(condition, code='CUSTODY_INVALID_STATE'):
    if not condition:
        raise CustodyError(code)


def _shape(value, keys):
    _need(type(value) is dict and set(value) == set(keys))


def identity_value(identity):
    _need(_identity_valid(identity))
    return {'volume': str(identity.volume), 'file_id': identity.file_id, 'size': identity.size}


def identity_from(value):
    _shape(value, ('volume', 'file_id', 'size'))
    _need(type(value['volume']) is str and re.fullmatch(r'0|[1-9][0-9]{0,19}', value['volume']) is not None)
    identity = FileIdentity(int(value['volume']), value['file_id'], value['size'])
    _need(_identity_valid(identity))
    return identity


def binding_value(binding):
    _need(type(binding) is EventBinding and _head_valid(binding.witnessed))
    return {'root': identity_value(binding.root), 'stream': identity_value(binding.stream),
            'witnessed': {'sequence': binding.witnessed.sequence, 'sha256': binding.witnessed.sha256,
                          'size': binding.witnessed.size}}


def binding_from(value):
    _shape(value, ('root', 'stream', 'witnessed'))
    _shape(value['witnessed'], ('sequence', 'sha256', 'size'))
    head = EventHead(**value['witnessed'])
    _need(_head_valid(head))
    root, stream = identity_from(value['root']), identity_from(value['stream'])
    _need(root.volume == stream.volume and not root.same_file(stream))
    return EventBinding(root, stream, head)


def _path(value, prefix):
    _need(type(value) is str and len(value) <= 2048 and '\x00' not in value)
    _need(re.match(r'^[A-Za-z]:\\', value) is not None and '/' not in value)
    _need(ntpath.normpath(value) == value and ':' not in value[2:])
    parts = value[3:].split('\\')
    _need(all(p and not p.endswith((' ', '.')) for p in parts))
    _need(re.fullmatch(prefix + r'[0-9a-f]{32}', parts[-1]) is not None)
    return value


def validate_record(record):
    _shape(record, ('schema', 'storage_id', 'project_id', 'epoch', 'phase', 'files', 'blobs', 'events'))
    _need(record['schema'] == _SCHEMA)
    _need(type(record['storage_id']) is str and re.fullmatch('[0-9a-f]{32}', record['storage_id']) is not None)
    _need(type(record['project_id']) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', record['project_id']) is not None)
    _need(type(record['epoch']) is int and 0 <= record['epoch'] <= MAX_EPOCH)
    if record['phase'] == 'PROVISIONING':
        _need(record['epoch'] == 0 and all(record[key] is None for key in ('files', 'blobs', 'events')))
    else:
        _need(record['phase'] == 'READY' and record['epoch'] > 0)
        for key, prefix in (('files', 'hh-files-'), ('blobs', 'hh-private-')):
            _shape(record[key], ('path', 'identity'))
            _path(record[key]['path'], prefix)
            identity_from(record[key]['identity'])
        _shape(record['events'], ('path', 'binding'))
        _path(record['events']['path'], 'hh-private-')
        binding = binding_from(record['events']['binding'])
        identities = [identity_from(record[k]['identity']) for k in ('files', 'blobs')] + [binding.root]
        _need(len({i.volume for i in identities}) == 1)
        _need(len({(i.volume, i.file_id) for i in identities}) == 3)
        _need(len({record[k]['path'].casefold() for k in ('files', 'blobs', 'events')}) == 3)
    return record


def encode_record(record):
    validate_record(record)
    raw = canonical_json(record)
    result = canonical_json({'record': record, 'sha256': hashlib.sha256(raw).hexdigest()})
    _need(len(result) <= MAX_STATE_BYTES)
    return result


def decode_record(raw):
    _need(type(raw) is bytes and 0 < len(raw) <= MAX_STATE_BYTES)
    try:
        value = parse_json_utf8(raw)
        _shape(value, ('record', 'sha256'))
        _need(type(value['sha256']) is str and value['sha256'] == hashlib.sha256(canonical_json(value['record'])).hexdigest())
        record = validate_record(value['record'])
        _need(encode_record(record) == raw)
        return record
    except (TypeError, KeyError, ValueError, OverflowError):
        raise CustodyError('CUSTODY_INVALID_STATE') from None


class WitnessCustody:
    """One supervisor owns registry lifetime and the protected file writer guard.

    bind_custody() attaches exactly this type to one event log. persist_binding
    never reads or calls the log and is safe while its append lock is held.
    Poisoned instances cannot confirm old state or silently retry a write.
    """
    def __init__(self, registry, *, storage_id, project_id, create=False):
        from .custody_registry import RegistryCustody
        _need(type(registry) is RegistryCustody, 'CUSTODY_TRUSTED_REGISTRY_REQUIRED')
        _need(registry.local_id == storage_id, 'CUSTODY_STORAGE_MISMATCH')
        self._registry, self._mutex = registry, threading.RLock()
        self._poisoned = False
        raw = registry.read()
        if create:
            _need(raw is None, 'CUSTODY_ALREADY_PROVISIONED')
            record = {'schema': _SCHEMA, 'storage_id': storage_id, 'project_id': project_id,
                      'epoch': 0, 'phase': 'PROVISIONING', 'files': None, 'blobs': None, 'events': None}
            raw = encode_record(record)
            registry.store(raw, expected=None)
        else:
            _need(raw is not None, 'CUSTODY_INCOMPLETE_PROVISIONING')
            record = decode_record(raw)
        _need(record['storage_id'] == storage_id and record['project_id'] == project_id, 'CUSTODY_PROJECT_MISMATCH')
        self._raw, self._record = raw, record

    def _check(self):
        if self._poisoned:
            raise CustodyError('CUSTODY_RECONCILIATION_REQUIRED', outcome_unknown=True)

    def confirm_current(self):
        """After acquiring the writer guard, reject a raced/stale bootstrap read."""
        with self._mutex:
            self._check()
            try:
                _need(self._registry.read() == self._raw, 'CUSTODY_CURRENT_CHANGED')
            except BaseException:
                self._poisoned = True
                raise CustodyError('CUSTODY_CURRENT_UNCERTAIN', outcome_unknown=True) from None

    @property
    def record(self):
        with self._mutex:
            self._check()
            return copy.deepcopy(self._record)

    @property
    def binding(self):
        with self._mutex:
            self._check()
            _need(self._record['phase'] == 'READY', 'CUSTODY_INCOMPLETE_PROVISIONING')
            return binding_from(self._record['events']['binding'])

    def _persist(self, record):
        self._check()
        raw = encode_record(record)
        try:
            self._registry.store(raw, expected=self._raw)
        except BaseException:
            self._poisoned = True
            raise CustodyError('CUSTODY_PERSIST_UNCERTAIN', outcome_unknown=True) from None
        self._raw, self._record = raw, record

    def activate(self, *, file_root, file_identity, blob_root, blob_identity, event_root, event_binding):
        """Host provisioning only, before CONFIG/lease/command admission."""
        with self._mutex:
            self._check()
            _need(self._record['phase'] == 'PROVISIONING', 'CUSTODY_ALREADY_PROVISIONED')
            record = self.record
            record.update(phase='READY', epoch=1,
                          files={'path': str(Path(file_root)), 'identity': identity_value(file_identity)},
                          blobs={'path': str(Path(blob_root)), 'identity': identity_value(blob_identity)},
                          events={'path': str(Path(event_root)), 'binding': binding_value(event_binding)})
            self._persist(record)

    def persist_binding(self, binding):
        """Called only with the log's checked head; no client recovery authority."""
        with self._mutex:
            old = self.binding
            _need(type(binding) is EventBinding and _head_valid(binding.witnessed))
            _need(old.root.same_file(binding.root) and old.stream.same_file(binding.stream), 'CUSTODY_BINDING_CHANGED')
            if old.witnessed == binding.witnessed:
                return
            _need(binding.witnessed.sequence > old.witnessed.sequence
                  and binding.witnessed.size > old.witnessed.size, 'CUSTODY_HIGH_WATER_REGRESSION')
            record = self.record
            record['epoch'] += 1
            record['events']['binding'] = binding_value(binding)
            self._persist(record)
