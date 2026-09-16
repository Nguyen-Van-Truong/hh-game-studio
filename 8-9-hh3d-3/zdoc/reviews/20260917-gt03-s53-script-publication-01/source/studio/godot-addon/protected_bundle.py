"""Owned immutable bundle files and one native selector slot, no public ACK.

The exact ProtectedFileRoot transfers on successful construction. No public
worker paths, authorization, engine execution or recovered write authority.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import sys
import threading
import uuid

from studio.host.core.limits import SafetyViolation
from studio.host.core.safe_open import FileIdentity
from studio.host.core.safe_replace import ProtectedFileRoot, FileVersion, MAX_FILES, MAX_TOTAL_BYTES
from studio.host.core.safe_create import MAX_BYTES
from studio.protocol.core import canonical_bytes, parse_json

_path = Path(__file__).with_name('fixture_profile.py').resolve()
_source = _path.read_bytes()
_key = '_hh_protected_fixture_' + hashlib.sha256(str(_path).encode() + b'\0' + _source).hexdigest()
if _key not in sys.modules:
    _spec = importlib.util.spec_from_file_location(_key, _path)
    _module = importlib.util.module_from_spec(_spec)
    _module._protected_source_sha256 = hashlib.sha256(_source).hexdigest()
    sys.modules[_key] = _module
    try:
        exec(compile(_source, str(_path), 'exec'), _module.__dict__)
    except BaseException:
        del sys.modules[_key]
        raise
fixture_profile = sys.modules[_key]
if (fixture_profile.__file__ != str(_path)
        or fixture_profile._protected_source_sha256 != hashlib.sha256(_source).hexdigest()):
    raise ImportError('protected bundle factory source binding mismatch')
bundle_codec = fixture_profile.staging.bundle_codec

MANIFEST_KEY = '@manifest'
SELECTOR_NAME = 'active.json'
SELECTOR_MAX_BYTES = 16 * 1024
SELECTOR_RESERVE_FILES = 2
SELECTOR_RESERVE_BYTES = 2 * SELECTOR_MAX_BYTES
MAX_ATTEMPTS = 64
SELECTOR_SCHEMA = 'hh-godot-active-selection-1'
_NAME = re.compile(r'obj-[0-9a-f]{32}\Z')
_COMMAND = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z')
_HASH = re.compile(r'[0-9a-f]{64}\Z')
_ID = re.compile(r'[0-9a-f]{32}\Z')
_VOLUME = re.compile(r'(?:0|[1-9][0-9]{0,19})\Z')
_REVISION = re.compile(r'sha256:[0-9a-f]{64}\Z')
_MARKER = '_hh_gt03_protected_bundle_owner'


class ProtectedBundleError(SafetyViolation):
    def __init__(self, code, *, outcome_unknown=False, cleanup_owner=None):
        self.outcome_unknown = outcome_unknown
        self.cleanup_owner = cleanup_owner
        super().__init__(code)


def _need(value, code):
    if not value:
        raise ProtectedBundleError(code)


def _shape(value, keys):
    _need(type(value) is dict and set(value) == set(keys), 'PROTECTED_BUNDLE_DESCRIPTOR_SHAPE')


def _root_value(identity):
    return {'volume': str(identity.volume), 'file_id': identity.file_id}


def _version_value(name, version):
    return {'name': name, **_root_value(version.identity), 'size_bytes': version.identity.size,
            'sha256': version.sha256}


@dataclass(frozen=True, slots=True)
class ProtectedBundleIntent:
    command_id: str
    project_revision: str
    root_identity: FileIdentity
    names: tuple[tuple[str, str], ...]
    public_ack: bool = field(default=False, init=False)


@dataclass(frozen=True, slots=True)
class ProtectedBundleReceipt:
    command_id: str
    project_revision: str
    root_identity: FileIdentity
    files: tuple[tuple[str, str, FileVersion], ...]
    manifest: tuple[str, FileVersion]
    status: str = field(default='DURABLE_BUNDLE_BYTES_READ_BACK', init=False)
    public_ack: bool = field(default=False, init=False)
    engine_effects_verified: bool = field(default=False, init=False)
    namespace_durability_verified: bool = field(default=True, init=False)


@dataclass(frozen=True, slots=True)
class ProtectedBundleAttempt:
    command_id: str
    project_revision: str
    status: str
    names: tuple[tuple[str, str], ...]
    reserved_files: int
    reserved_bytes: int
    attempted_writes: int
    versions: tuple[tuple[str, str, FileVersion], ...]
    public_ack: bool = field(default=False, init=False)


@dataclass(frozen=True, slots=True)
class ProtectedPrepareCancellation:
    command_id: str
    project_revision: str
    names: tuple[tuple[str, str], ...]
    status: str = field(default='CANCELED_NO_WRITES', init=False)
    public_ack: bool = field(default=False, init=False)


@dataclass(frozen=True, slots=True)
class ProtectedSelectionSnapshot:
    source_bytes: bytes
    version: FileVersion
    public_ack: bool = field(default=False, init=False)

    @property
    def selection(self):
        return parse_json(self.source_bytes)['selection']

    @property
    def descriptor(self):
        return parse_json(self.source_bytes)['descriptor']


@dataclass(frozen=True, slots=True)
class ProtectedSelectionIntent:
    command_id: str
    project_revision: str
    root_identity: FileIdentity
    source_bytes: bytes
    expected: ProtectedSelectionSnapshot | None
    public_ack: bool = field(default=False, init=False)


@dataclass(frozen=True, slots=True)
class ProtectedSelectionReceipt:
    command_id: str
    project_revision: str
    snapshot: ProtectedSelectionSnapshot
    status: str = field(default='DURABLE_SELECTION_BYTES_READ_BACK', init=False)
    public_ack: bool = field(default=False, init=False)
    engine_effects_verified: bool = field(default=False, init=False)
    namespace_durability_verified: bool = field(default=True, init=False)

    @property
    def source_bytes(self):
        return self.snapshot.source_bytes

    @property
    def version(self):
        return self.snapshot.version

    @property
    def selection(self):
        return self.snapshot.selection

    @property
    def descriptor(self):
        return self.snapshot.descriptor


@dataclass(frozen=True, slots=True)
class ProtectedSelectionAttempt:
    command_id: str
    status: str
    source_bytes: bytes
    expected_version: FileVersion | None
    attempted_writes: int
    returned_version: FileVersion | None
    public_ack: bool = field(default=False, init=False)


@dataclass
class _Record:
    intent: ProtectedBundleIntent
    names: tuple[tuple[str, str], ...]
    bundle: object
    inventory: dict
    reserved_bytes: int
    status: str = 'PREPARED'
    attempted_writes: int = 0
    versions: list = field(default_factory=list)
    receipt: ProtectedBundleReceipt | None = None
    cancellation: ProtectedPrepareCancellation | None = None


@dataclass
class _SelectionRecord:
    intent: ProtectedSelectionIntent
    bundle_receipt: ProtectedBundleReceipt
    source_bytes: bytes
    expected: ProtectedSelectionSnapshot | None
    status: str = 'PREPARED'
    attempted_writes: int = 0
    returned_version: FileVersion | None = None
    receipt: ProtectedSelectionReceipt | None = None


class ProtectedBundleStore:
    """One lifecycle owner; readonly reopening grants reads, never mutation."""
    def __init__(self, files: ProtectedFileRoot):
        _need(type(files) is ProtectedFileRoot, 'PROTECTED_BUNDLE_EXACT_ROOT_REQUIRED')
        self._mutex = threading.RLock()
        self._files, self._root, self._identity = files, files.root, files.root_identity
        self._readonly = files._readonly
        self._held = self._closed = False
        self._records = {}
        self._selection_records = {}
        self._snapshots = {}
        self._current_snapshot = None
        # Constructor validation does not transfer ownership on failure.
        with files._mutex:
            files._check()
            _need(getattr(files, _MARKER, None) is None
                  and getattr(files, '_fixture_file_consumer', None) is None
                  and getattr(files, '_fixture_selector', None) is None,
                  'PROTECTED_BUNDLE_ROOT_ALREADY_OWNED')
            self._baseline_inventory = self._inventory_locked()
            self._selector_version = self._baseline_inventory.pop(SELECTOR_NAME, None)
            setattr(files, _MARKER, self)

    @property
    def root(self):
        return self._root

    @property
    def root_identity(self):
        return self._identity

    @property
    def readonly(self):
        return self._readonly

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _healthy(self, *, mutation=False):
        _need(not self._closed, 'PROTECTED_BUNDLE_CLOSED')
        _need(not self._held, 'PROTECTED_BUNDLE_HELD')
        _need(not mutation or not self._readonly, 'PROTECTED_BUNDLE_READONLY')

    def _hold(self, code, record=None, *, unknown=True):
        self._held = True
        if record is not None:
            record.status = 'UNKNOWN'
        return ProtectedBundleError(code, outcome_unknown=unknown, cleanup_owner=self)

    def _check_locked(self):
        files = self._files
        files._check()
        _need(files.root == self._root and files.root_identity == self._identity
              and files._readonly is self._readonly and getattr(files, _MARKER, None) is self,
              'PROTECTED_BUNDLE_OWNER_CHANGED')

    def _inventory_locked(self):
        """Caller owns native mutex. Names only from enumeration, facts from handles."""
        files = self._files
        files._check()
        inventory = {}
        with os.scandir(self._root) as entries:
            for entry in entries:
                if entry.name == '.writer':
                    continue
                _need(len(inventory) < MAX_FILES and
                      (entry.name == SELECTOR_NAME or _NAME.fullmatch(entry.name)),
                      'PROTECTED_BUNDLE_INVENTORY_INVALID')
                path = files._path(entry.name)
                handle = files._api.open_file(path)
                try:
                    version, _ = files._version(handle, path)
                    _need(version.identity.size <= (SELECTOR_MAX_BYTES if entry.name == SELECTOR_NAME else MAX_BYTES),
                          'PROTECTED_BUNDLE_INVENTORY_INVALID')
                    inventory[entry.name] = version
                finally:
                    files._close_operation(handle)
        _need(sum(v.identity.size for v in inventory.values()) <= MAX_TOTAL_BYTES,
              'PROTECTED_BUNDLE_INVENTORY_INVALID')
        files._check()
        return inventory

    def _inventory(self, *, prospective_selector=None):
        with self._files._mutex:
            self._check_locked()
            result = self._inventory_locked()
            expected = {**self._baseline_inventory,
                **{name: version for record in self._records.values() for _, name, version in record.versions}}
            selector = self._selector_version if prospective_selector is None else prospective_selector
            if selector is not None:
                expected[SELECTOR_NAME] = selector
            _need(result == expected, 'PROTECTED_BUNDLE_INVENTORY_CHANGED')
            self._check_locked()
            return result

    def prepare(self, command_id: str, bundle) -> ProtectedBundleIntent:
        """Native reads only; reserve one batch and mint all journalable names."""
        _need(type(command_id) is str and _COMMAND.fullmatch(command_id), 'PROTECTED_BUNDLE_COMMAND_REQUIRED')
        _need(type(bundle) is bundle_codec.CompleteFixtureBundle, 'PROTECTED_BUNDLE_EXACT_CODEC_REQUIRED')
        bundle = bundle_codec.decode_bundle(bundle.manifest_bytes, bundle.files)
        with self._mutex:
            self._healthy(mutation=True)
            prior = self._records.get(command_id)
            if prior is not None:
                _need(prior.bundle == bundle, 'PROTECTED_BUNDLE_COMMAND_CONFLICT')
                _need(prior.status != 'CANCELED_NO_WRITES', 'PROTECTED_BUNDLE_CANCELED')
            else:
                _need(len(self._records) < MAX_ATTEMPTS, 'PROTECTED_BUNDLE_ATTEMPT_LIMIT')
                _need(not any(record.status == 'PREPARED' for record in self._records.values()),
                      'PROTECTED_BUNDLE_PENDING')
            try:
                inventory = self._inventory()
                self._files.check_mutation_available()
            except BaseException as exc:
                raise self._hold('PROTECTED_BUNDLE_OWNER_UNVERIFIED') from exc
            if prior is not None:
                self._record(prior.intent)
                return prior.intent
            size = len(bundle.manifest_bytes) + sum(map(len, bundle.files.values()))
            count = len(bundle_codec.PATHS) + 1
            _need(len(inventory) + count + SELECTOR_RESERVE_FILES <= MAX_FILES
                  and sum(v.identity.size for v in inventory.values()) + size + SELECTOR_RESERVE_BYTES <= MAX_TOTAL_BYTES,
                  'PROTECTED_BUNDLE_QUOTA')
            names, used = [], set(inventory) | {name for r in self._records.values() for _, name in r.names}
            for logical in (*bundle_codec.PATHS, MANIFEST_KEY):
                name = 'obj-' + uuid.uuid4().hex
                _need(name not in used, 'PROTECTED_BUNDLE_NAME_COLLISION')
                used.add(name)
                names.append((logical, name))
            intent = ProtectedBundleIntent(command_id, bundle.project_revision, self._identity, tuple(names))
            objects = {name: version for name, version in inventory.items() if name != SELECTOR_NAME}
            self._records[command_id] = _Record(intent, intent.names, bundle, objects, size)
            return intent

    def _record(self, value, *, receipt=False):
        expected = ProtectedBundleReceipt if receipt else ProtectedBundleIntent
        _need(type(value) is expected, 'PROTECTED_BUNDLE_REGISTERED_OBJECT_REQUIRED')
        record = self._records.get(value.command_id)
        _need(record is not None and (record.receipt if receipt else record.intent) is value,
              'PROTECTED_BUNDLE_REGISTERED_OBJECT_REQUIRED')
        _need(value.project_revision == record.bundle.project_revision and value.root_identity == self._identity
              and value.public_ack is False, 'PROTECTED_BUNDLE_REGISTERED_OBJECT_CHANGED')
        if receipt:
            _need(value.files == tuple(record.versions[:-1]) and value.manifest == record.versions[-1][1:]
                  and value.status == 'DURABLE_BUNDLE_BYTES_READ_BACK'
                  and value.engine_effects_verified is False and value.namespace_durability_verified is True,
                  'PROTECTED_BUNDLE_REGISTERED_OBJECT_CHANGED')
        else:
            _need(value.names == record.names, 'PROTECTED_BUNDLE_REGISTERED_OBJECT_CHANGED')
        return record

    def _read_record(self, record):
        _need(len(record.versions) == len(bundle_codec.PATHS) + 1, 'PROTECTED_BUNDLE_INCOMPLETE')
        contents, manifest = {}, None
        for (logical, name), (actual_logical, actual_name, version) in zip(record.names, record.versions):
            _need((logical, name) == (actual_logical, actual_name), 'PROTECTED_BUNDLE_PLAN_MISMATCH')
            current, raw = self._files.read(name)
            wanted = record.bundle.manifest_bytes if logical == MANIFEST_KEY else record.bundle.files[logical]
            _need(current == version and raw == wanted, 'PROTECTED_BUNDLE_READBACK_MISMATCH')
            if logical == MANIFEST_KEY:
                manifest = raw
            else:
                contents[logical] = raw
        decoded = bundle_codec.decode_bundle(manifest, contents)
        _need(decoded == record.bundle, 'PROTECTED_BUNDLE_READBACK_MISMATCH')
        inventory = self._inventory()
        wanted_inventory = {**record.inventory, **{name: version for _, name, version in record.versions}}
        # Later batches are legitimate, but all files present at this batch's
        # barrier must retain exact identities/bytes. Unknown names still fail.
        _need(all(inventory.get(name) == version for name, version in wanted_inventory.items()),
              'PROTECTED_BUNDLE_INVENTORY_CHANGED')
        return decoded

    def stage(self, intent: ProtectedBundleIntent) -> ProtectedBundleReceipt:
        with self._mutex:
            self._healthy(mutation=True)
            record = self._record(intent)
            _need(record.status != 'CANCELED_NO_WRITES', 'PROTECTED_BUNDLE_CANCELED')
            try:
                if record.receipt is not None:
                    self._record(record.receipt, receipt=True)
                    self._read_record(record)
                    return record.receipt
                _need(record.status == 'PREPARED', 'PROTECTED_BUNDLE_NOT_PREPARED')
                _need({n: v for n, v in self._inventory().items() if n != SELECTOR_NAME} == record.inventory,
                      'PROTECTED_BUNDLE_INVENTORY_CHANGED')
                self._files.check_mutation_available()
                for logical, name in record.names:
                    raw = record.bundle.manifest_bytes if logical == MANIFEST_KEY else record.bundle.files[logical]
                    record.attempted_writes += 1
                    version = self._files.create_new(name, raw)
                    _need(type(version) is FileVersion, 'PROTECTED_BUNDLE_VERSION_REQUIRED')
                    record.versions.append((logical, name, version))
                    _need(self._files.read(name) == (version, raw), 'PROTECTED_BUNDLE_READBACK_MISMATCH')
                self._read_record(record)
                manifest_name, manifest_version = record.versions[-1][1:]
                self._files.confirm_barrier(manifest_name, manifest_version)
                self._read_record(record)
                _need({n: v for n, v in self._inventory().items() if n != SELECTOR_NAME} == {**record.inventory,
                    **{name: version for _, name, version in record.versions}}, 'PROTECTED_BUNDLE_INVENTORY_CHANGED')
                receipt = ProtectedBundleReceipt(intent.command_id, intent.project_revision, self._identity,
                    tuple(record.versions[:-1]), (manifest_name, manifest_version))
                record.receipt, record.status = receipt, 'DURABLE_BUNDLE_BYTES_READ_BACK'
                return receipt
            except BaseException as exc:
                raise self._hold('PROTECTED_BUNDLE_STAGE_UNKNOWN', record) from exc

    def readback(self, receipt: ProtectedBundleReceipt):
        with self._mutex:
            self._healthy()
            record = self._record(receipt, receipt=True)
            try:
                return self._read_record(record)
            except BaseException as exc:
                raise self._hold('PROTECTED_BUNDLE_READBACK_UNVERIFIED', record) from exc

    def descriptor(self, receipt: ProtectedBundleReceipt) -> dict:
        with self._mutex:
            self.readback(receipt)
            return {'root_identity': _root_value(self._identity), 'project_revision': receipt.project_revision,
                'files': {logical: _version_value(name, version) for logical, name, version in receipt.files},
                'manifest': _version_value(*receipt.manifest)}

    def _parse_descriptor(self, value):
        _shape(value, ('root_identity', 'project_revision', 'files', 'manifest'))
        root = value['root_identity']
        _shape(root, ('volume', 'file_id'))
        _need(type(root['volume']) is str and type(root['file_id']) is str
              and root == _root_value(self._identity), 'PROTECTED_BUNDLE_DESCRIPTOR_ROOT')
        _need(type(value['project_revision']) is str and _REVISION.fullmatch(value['project_revision']),
              'PROTECTED_BUNDLE_DESCRIPTOR_REVISION')
        _shape(value['files'], bundle_codec.PATHS)
        parsed, names, identities = [], set(), set()
        for logical in (*bundle_codec.PATHS, MANIFEST_KEY):
            row = value['manifest'] if logical == MANIFEST_KEY else value['files'][logical]
            _shape(row, ('name', 'volume', 'file_id', 'size_bytes', 'sha256'))
            cap = bundle_codec.MAX_MANIFEST_BYTES if logical == MANIFEST_KEY else bundle_codec.FILE_PROFILE[logical][1]
            _need(type(row['name']) is str and _NAME.fullmatch(row['name']) and row['name'] not in names
                  and type(row['volume']) is str and _VOLUME.fullmatch(row['volume'])
                  and int(row['volume']) < 2**64 and row['volume'] == str(self._identity.volume)
                  and type(row['file_id']) is str and _ID.fullmatch(row['file_id']) and row['file_id'] not in identities
                  and type(row['size_bytes']) is int and 0 < row['size_bytes'] <= cap
                  and type(row['sha256']) is str and _HASH.fullmatch(row['sha256']),
                  'PROTECTED_BUNDLE_DESCRIPTOR_INVALID')
            names.add(row['name'])
            identities.add(row['file_id'])
            parsed.append((logical, row['name'], FileVersion(
                FileIdentity(int(row['volume']), row['file_id'], row['size_bytes']), row['sha256'])))
        _need(sum(v.identity.size for _, _, v in parsed) <= bundle_codec.MAX_BUNDLE_BYTES,
              'PROTECTED_BUNDLE_DESCRIPTOR_INVALID')
        return tuple(parsed), value['project_revision']

    def _read_descriptor(self, value, *, prospective_selector=None):
        parsed, revision = self._parse_descriptor(value)
        inventory = self._inventory(prospective_selector=prospective_selector)
        contents, manifest = {}, None
        for logical, name, version in parsed:
            _need(inventory.get(name) == version, 'PROTECTED_BUNDLE_DESCRIPTOR_MISMATCH')
            actual, raw = self._files.read(name)
            _need(actual == version, 'PROTECTED_BUNDLE_DESCRIPTOR_MISMATCH')
            if logical == MANIFEST_KEY:
                manifest = raw
            else:
                contents[logical] = raw
        result = bundle_codec.decode_bundle(manifest, contents)
        _need(result.project_revision == revision, 'PROTECTED_BUNDLE_DESCRIPTOR_MISMATCH')
        _need(self._inventory(prospective_selector=prospective_selector) == inventory,
              'PROTECTED_BUNDLE_INVENTORY_CHANGED')
        return result

    def read_descriptor(self, value: dict):
        """Verify strict descriptor and native bytes; does not adopt or rearm."""
        with self._mutex:
            self._healthy()
            self._parse_descriptor(value)
            try:
                return self._read_descriptor(value)
            except BaseException as exc:
                raise self._hold('PROTECTED_BUNDLE_DESCRIPTOR_UNVERIFIED') from exc

    def cancel_unused_prepare(self, intent: ProtectedBundleIntent) -> ProtectedPrepareCancellation:
        """Release a write-free reservation; retain its ID/name tombstones."""
        with self._mutex:
            self._healthy(mutation=True)
            record = self._record(intent)
            _need(record.status in ('PREPARED', 'CANCELED_NO_WRITES') and record.attempted_writes == 0
                  and not record.versions and record.receipt is None, 'PROTECTED_BUNDLE_CANCEL_NOT_UNUSED')
            try:
                inventory = self._inventory()
                self._files.check_mutation_available()
                _need(all(name not in inventory for _, name in record.names), 'PROTECTED_BUNDLE_CANCEL_NAME_EXISTS')
            except BaseException as exc:
                raise self._hold('PROTECTED_BUNDLE_CANCEL_UNVERIFIED', record) from exc
            if record.cancellation is None:
                record.cancellation = ProtectedPrepareCancellation(intent.command_id, intent.project_revision, record.names)
                record.status = 'CANCELED_NO_WRITES'
            result = record.cancellation
            _need(type(result) is ProtectedPrepareCancellation and result.command_id == intent.command_id
                  and result.project_revision == intent.project_revision and result.names == record.names
                  and result.status == 'CANCELED_NO_WRITES' and result.public_ack is False,
                  'PROTECTED_BUNDLE_REGISTERED_OBJECT_CHANGED')
            return result

    @staticmethod
    def _selection(value):
        _shape(value, ('generation', 'identity'))
        _need(type(value['generation']) is int and 0 <= value['generation'] <= 2**53 - 1
              and type(value['identity']) is str and _REVISION.fullmatch(value['identity']),
              'PROTECTED_SELECTION_INVALID')

    def _parse_selector(self, raw):
        _need(type(raw) is bytes and 0 < len(raw) <= SELECTOR_MAX_BYTES, 'PROTECTED_SELECTION_BYTES')
        value = parse_json(raw)
        _shape(value, ('schema', 'command_id', 'parent_selection', 'selection', 'descriptor_sha256', 'descriptor'))
        _need(value['schema'] == SELECTOR_SCHEMA and type(value['command_id']) is str
              and _COMMAND.fullmatch(value['command_id']) and canonical_bytes(value) == raw,
              'PROTECTED_SELECTION_SCHEMA')
        self._selection(value['selection'])
        parent = value['parent_selection']
        if parent is None:
            _need(value['selection']['generation'] == 0, 'PROTECTED_SELECTION_INITIAL_GENERATION')
        else:
            self._selection(parent)
            _need(value['selection']['generation'] == parent['generation'] + 1,
                  'PROTECTED_SELECTION_GENERATION')
        self._parse_descriptor(value['descriptor'])
        _need(type(value['descriptor_sha256']) is str
              and value['descriptor_sha256'] == hashlib.sha256(canonical_bytes(value['descriptor'])).hexdigest(),
              'PROTECTED_SELECTION_DESCRIPTOR_HASH')
        return value

    def _registered_snapshot(self, snapshot):
        _need(type(snapshot) is ProtectedSelectionSnapshot, 'PROTECTED_SELECTION_REGISTERED_SNAPSHOT_REQUIRED')
        saved = self._snapshots.get(id(snapshot))
        _need(saved is not None and saved[0] is snapshot, 'PROTECTED_SELECTION_REGISTERED_SNAPSHOT_REQUIRED')
        _need(snapshot.source_bytes == saved[1] and snapshot.version == saved[2] and snapshot.public_ack is False,
              'PROTECTED_SELECTION_REGISTERED_OBJECT_CHANGED')
        return snapshot

    def _new_snapshot(self, raw, version):
        snapshot = ProtectedSelectionSnapshot(raw, version)
        self._snapshots[id(snapshot)] = (snapshot, raw, version)
        return snapshot

    def inspect_selection(self) -> ProtectedSelectionSnapshot | None:
        """Current native selection plus complete bundle readback; no authority."""
        with self._mutex:
            self._healthy()
            try:
                inventory = self._inventory()
                if self._selector_version is None:
                    _need(SELECTOR_NAME not in inventory, 'PROTECTED_SELECTION_UNEXPECTED')
                    return None
                version, raw = self._files.read(SELECTOR_NAME)
                _need(version == self._selector_version, 'PROTECTED_SELECTION_VERSION_CHANGED')
                value = self._parse_selector(raw)
                self._read_descriptor(value['descriptor'])
                _need(self._files.read(SELECTOR_NAME) == (version, raw), 'PROTECTED_SELECTION_READBACK_MISMATCH')
                if self._current_snapshot is None:
                    self._current_snapshot = self._new_snapshot(raw, version)
                current = self._registered_snapshot(self._current_snapshot)
                _need(current.source_bytes == raw and current.version == version, 'PROTECTED_SELECTION_READBACK_MISMATCH')
                return current
            except BaseException as exc:
                raise self._hold('PROTECTED_SELECTION_INSPECT_UNVERIFIED') from exc

    def prepare_selection(self, receipt: ProtectedBundleReceipt, selection: dict,
                          *, expected: ProtectedSelectionSnapshot | None) -> ProtectedSelectionIntent:
        """Write-free internal storage intent. The caller owns all authorization."""
        self._selection(selection)
        with self._mutex:
            self._healthy(mutation=True)
            self._record(receipt, receipt=True)
            if expected is not None:
                self._registered_snapshot(expected)
            descriptor = self.descriptor(receipt)
            raw = canonical_bytes({'schema': SELECTOR_SCHEMA, 'command_id': receipt.command_id,
                'parent_selection': None if expected is None else expected.selection,
                'selection': selection, 'descriptor_sha256': hashlib.sha256(canonical_bytes(descriptor)).hexdigest(),
                'descriptor': descriptor})
            self._parse_selector(raw)
            prior = self._selection_records.get(receipt.command_id)
            if prior is not None:
                _need(prior.bundle_receipt is receipt and prior.source_bytes == raw and prior.expected is expected,
                      'PROTECTED_SELECTION_COMMAND_CONFLICT')
                self._selection_record(prior.intent)
                self.inspect_selection()
                return prior.intent
            _need(len(self._selection_records) < MAX_ATTEMPTS, 'PROTECTED_SELECTION_ATTEMPT_LIMIT')
            _need(not any(r.status == 'PREPARED' for r in self._selection_records.values()), 'PROTECTED_SELECTION_PENDING')
            _need(self.inspect_selection() is expected, 'PROTECTED_SELECTION_EXPECTED_CHANGED')
            try:
                inventory = self._inventory()
                self._files.check_mutation_available()
            except BaseException as exc:
                raise self._hold('PROTECTED_SELECTION_OWNER_UNVERIFIED') from exc
            _need(len(inventory) + 1 <= MAX_FILES
                  and sum(v.identity.size for v in inventory.values()) + len(raw) <= MAX_TOTAL_BYTES,
                  'PROTECTED_SELECTION_QUOTA')
            intent = ProtectedSelectionIntent(receipt.command_id, receipt.project_revision, self._identity, raw, expected)
            self._selection_records[receipt.command_id] = _SelectionRecord(intent, receipt, raw, expected)
            return intent

    def _selection_record(self, intent):
        _need(type(intent) is ProtectedSelectionIntent, 'PROTECTED_SELECTION_REGISTERED_INTENT_REQUIRED')
        record = self._selection_records.get(intent.command_id)
        _need(record is not None and record.intent is intent, 'PROTECTED_SELECTION_REGISTERED_INTENT_REQUIRED')
        self._record(record.bundle_receipt, receipt=True)
        _need(intent.command_id == record.bundle_receipt.command_id
              and intent.project_revision == record.bundle_receipt.project_revision
              and intent.root_identity == self._identity and intent.source_bytes == record.source_bytes
              and intent.expected is record.expected and intent.public_ack is False,
              'PROTECTED_SELECTION_REGISTERED_OBJECT_CHANGED')
        if record.expected is not None:
            self._registered_snapshot(record.expected)
        return record

    def _selection_receipt(self, record):
        receipt = record.receipt
        _need(type(receipt) is ProtectedSelectionReceipt and receipt.command_id == record.bundle_receipt.command_id
              and receipt.project_revision == record.bundle_receipt.project_revision
              and receipt.status == 'DURABLE_SELECTION_BYTES_READ_BACK' and receipt.public_ack is False
              and receipt.engine_effects_verified is False and receipt.namespace_durability_verified is True,
              'PROTECTED_SELECTION_REGISTERED_OBJECT_CHANGED')
        snapshot = self._registered_snapshot(receipt.snapshot)
        _need(snapshot.source_bytes == record.source_bytes and snapshot.version == record.returned_version,
              'PROTECTED_SELECTION_REGISTERED_OBJECT_CHANGED')
        return receipt

    def select(self, intent: ProtectedSelectionIntent) -> ProtectedSelectionReceipt:
        """Initialize/CAS the native slot, not lease admission or public commit."""
        with self._mutex:
            self._healthy(mutation=True)
            record = self._selection_record(intent)
            if record.receipt is not None:
                receipt = self._selection_receipt(record)
                self.inspect_selection()
                self.readback(record.bundle_receipt)
                return receipt  # Historical duplicate; never a second CAS.
            _need(record.status == 'PREPARED', 'PROTECTED_SELECTION_NOT_PREPARED')
            try:
                _need(self.inspect_selection() is record.expected, 'PROTECTED_SELECTION_EXPECTED_CHANGED')
                self.readback(record.bundle_receipt)
                self._files.check_mutation_available()
                record.attempted_writes += 1  # Before entering a possibly effectful native call.
                if record.expected is None:
                    version = self._files.create_new(SELECTOR_NAME, record.source_bytes)
                else:
                    version = self._files.atomic_replace(SELECTOR_NAME, record.source_bytes, expected=record.expected.version)
                _need(type(version) is FileVersion, 'PROTECTED_SELECTION_VERSION_REQUIRED')
                record.returned_version = version
                _need(self._files.read(SELECTOR_NAME) == (version, record.source_bytes), 'PROTECTED_SELECTION_READBACK_MISMATCH')
                self._files.confirm_barrier(SELECTOR_NAME, version)
                value = self._parse_selector(record.source_bytes)
                self._read_descriptor(value['descriptor'], prospective_selector=version)
                _need(self._files.read(SELECTOR_NAME) == (version, record.source_bytes), 'PROTECTED_SELECTION_READBACK_MISMATCH')
                self._inventory(prospective_selector=version)
                snapshot = self._new_snapshot(record.source_bytes, version)
                receipt = ProtectedSelectionReceipt(intent.command_id, intent.project_revision, snapshot)
                record.receipt, record.status = receipt, 'DURABLE_SELECTION_BYTES_READ_BACK'
                self._selector_version, self._current_snapshot = version, snapshot
                return receipt
            except BaseException as exc:
                raise self._hold('PROTECTED_SELECTION_UNKNOWN', record, unknown=record.attempted_writes > 0) from exc

    def lookup_selection(self, command_id: str):
        _need(type(command_id) is str and _COMMAND.fullmatch(command_id), 'PROTECTED_BUNDLE_COMMAND_REQUIRED')
        with self._mutex:
            self._healthy()
            self.inspect_selection()
            record = self._selection_records.get(command_id)
            if record is None or record.receipt is None:
                return None
            self._selection_record(record.intent)
            self.readback(record.bundle_receipt)
            return self._selection_receipt(record)

    def selection_snapshot(self) -> tuple[ProtectedSelectionAttempt, ...]:
        """In-memory attempt diagnostics, available while held/closed."""
        with self._mutex:
            return tuple(ProtectedSelectionAttempt(r.bundle_receipt.command_id, r.status, r.source_bytes,
                None if r.expected is None else self._snapshots[id(r.expected)][2], r.attempted_writes, r.returned_version)
                for r in self._selection_records.values())

    def lookup(self, command_id: str, project_revision: str | None = None):
        _need(type(command_id) is str and _COMMAND.fullmatch(command_id), 'PROTECTED_BUNDLE_COMMAND_REQUIRED')
        _need(project_revision is None or type(project_revision) is str and _REVISION.fullmatch(project_revision),
              'PROTECTED_BUNDLE_DESCRIPTOR_REVISION')
        with self._mutex:
            self._healthy()
            record = self._records.get(command_id)
            if record is not None:
                _need(project_revision is None or record.bundle.project_revision == project_revision,
                      'PROTECTED_BUNDLE_COMMAND_CONFLICT')
            try:
                self._inventory()
                if record is not None and record.receipt is not None:
                    self._record(record.receipt, receipt=True)
            except BaseException as exc:
                raise self._hold('PROTECTED_BUNDLE_OWNER_UNVERIFIED') from exc
            return None if record is None else record.receipt

    def snapshot(self) -> tuple[ProtectedBundleAttempt, ...]:
        """In-memory ownership diagnostics remain available while held/closed."""
        with self._mutex:
            return tuple(ProtectedBundleAttempt(r.intent.command_id, r.intent.project_revision, r.status,
                r.names, 0 if r.cancellation else len(r.names), 0 if r.cancellation else r.reserved_bytes,
                r.attempted_writes, tuple(r.versions))
                for r in self._records.values())

    def close(self):
        with self._mutex:
            self._closed = True
            try:
                self._files.close()
            except BaseException as exc:
                for record in self._records.values():
                    record.status = 'UNKNOWN'
                for record in self._selection_records.values():
                    record.status = 'UNKNOWN'
                raise self._hold('PROTECTED_BUNDLE_CLOSE_UNCERTAIN') from exc
            if getattr(self._files, _MARKER, None) is self:
                setattr(self._files, _MARKER, None)
