"""Internal complete-fixture staging; no selection, journal or public ACK.

The exact PrivateBlobStore transfers to this lifecycle owner on construction.
Neither that store nor its roots may be concurrently used by another owner.
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

from studio.host.core.limits import SafetyViolation
from studio.host.core.private_store import (PrivateBlobStore, StagedBlob, MAX_BLOB_BYTES,
                                            MAX_STAGED_OBJECTS, MAX_STAGED_BYTES)
from studio.host.core.safe_open import FileIdentity

# Bind the sibling codec to its actual path AND exact bytes. Independent source
# snapshots must not silently reuse a module left by another checkout.
_CODEC_PATH = Path(__file__).with_name('bundle_v2.py').resolve()
_CODEC_BYTES = _CODEC_PATH.read_bytes()
_CODEC_SHA256 = hashlib.sha256(_CODEC_BYTES).hexdigest()
_CODEC_MODULE = '_hh_gt03_bundle_v2_' + hashlib.sha256(
    str(_CODEC_PATH).encode('utf-8') + b'\0' + _CODEC_BYTES).hexdigest()
if _CODEC_MODULE not in sys.modules:
    _spec = importlib.util.spec_from_file_location(_CODEC_MODULE, _CODEC_PATH)
    _module = importlib.util.module_from_spec(_spec)
    _module._bundle_source_sha256 = _CODEC_SHA256
    sys.modules[_CODEC_MODULE] = _module
    try:
        exec(compile(_CODEC_BYTES, str(_CODEC_PATH), 'exec'), _module.__dict__)
    except BaseException:
        del sys.modules[_CODEC_MODULE]
        raise
bundle_codec = sys.modules[_CODEC_MODULE]
if (getattr(bundle_codec, '__file__', None) != str(_CODEC_PATH)
        or getattr(bundle_codec, '_bundle_source_sha256', None) != _CODEC_SHA256):
    raise ImportError('complete bundle codec source binding mismatch')

_COMMAND = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z')
_BLOB = re.compile(r'blob-[0-9a-f]{32}\Z')
_REVISION = re.compile(r'sha256:[0-9a-f]{64}\Z')
MANIFEST_KEY = '@manifest'


class BundleStagingError(SafetyViolation):
    def __init__(self, code: str, *, outcome_unknown: bool = False, cleanup_owner=None):
        self.outcome_unknown = outcome_unknown
        self.cleanup_owner = cleanup_owner
        super().__init__(code)


def _need(condition, code):
    if not condition:
        raise BundleStagingError(code)


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True, slots=True)
class StageReceipt:
    """Historical internal byte readback only; valid here by registered identity."""
    command_id: str
    project_revision: str
    manifest_sha256: str
    root_identity: FileIdentity
    files: tuple[tuple[str, StagedBlob], ...]
    manifest: StagedBlob
    status: str = field(default='STAGED_BYTES_READ_BACK', init=False)
    public_ack: bool = field(default=False, init=False)
    engine_effects_verified: bool = field(default=False, init=False)
    namespace_durability_verified: bool = field(default=False, init=False)


@dataclass(frozen=True, slots=True)
class StageAttempt:
    """In-memory ownership diagnostic, usable while held; no native-read claim."""
    command_id: str
    project_revision: str
    status: str
    reserved_objects: int
    reserved_bytes: int
    attempted_puts: int
    descriptors: tuple[tuple[str, StagedBlob], ...]
    public_ack: bool = field(default=False, init=False)


@dataclass
class _Record:
    command_id: str
    bundle: object
    reserved_bytes: int
    status: str = 'RESERVED'
    attempted_puts: int = 0
    descriptors: list = field(default_factory=list)
    receipt: StageReceipt | None = None


class BundleStager:
    """One trusted, local lifecycle owner. No durable retry or recovery API.

    Successful construction transfers exclusive store use and close ownership.
    Use ``bundle_codec`` from this module to construct exact codec instances.
    A journal-owned store cannot be shared with this standalone owner.
    """
    def __init__(self, store: PrivateBlobStore):
        _need(type(store) is PrivateBlobStore, 'BUNDLE_STAGE_EXACT_STORE_REQUIRED')
        self._mutex = threading.RLock()
        self._store, self._root_identity = store, store.root_identity
        self._held = self._closed = False
        self._records = {}
        # This marker is on the exact native owner, so independently imported
        # copies of this module still cannot wrap it a second time.
        with store._mutex:
            store._check()
            _need(getattr(store, '_hh_gt03_bundle_stager_owner', None) is None,
                  'BUNDLE_STAGE_STORE_ALREADY_OWNED')
            store._hh_gt03_bundle_stager_owner = self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _healthy(self):
        _need(not self._closed, 'BUNDLE_STAGE_CLOSED')
        _need(not self._held, 'BUNDLE_STAGE_HELD')

    def _hold(self, code, *, unknown=False):
        self._held = True
        return BundleStagingError(code, outcome_unknown=unknown, cleanup_owner=self)

    def _verify_owner(self):
        with self._store._mutex:
            self._store._check()
            _need(self._root_identity == self._store.root_identity
                  and self._store._hh_gt03_bundle_stager_owner is self,
                  'BUNDLE_STAGE_OWNER_CHANGED')

    def _inventory(self):
        """Fresh native metadata for quota admission; no caller file metadata.

        GT-02 private APIs are read/verify only. Enumeration supplies names;
        every size, identity and DACL comes from a verified native handle.
        """
        with self._store._mutex:
            store = self._store
            store._check()
            _need(self._root_identity == store.root_identity
                  and store._hh_gt03_bundle_stager_owner is self,
                  'BUNDLE_STAGE_OWNER_CHANGED')
            inventory = {}
            total = 0
            with os.scandir(store.root) as entries:
                for entry in entries:
                    if entry.name == '.writer':
                        continue
                    _need(len(inventory) < MAX_STAGED_OBJECTS and _BLOB.fullmatch(entry.name),
                          'BUNDLE_STAGE_INVENTORY_INVALID')
                    path = store.root / entry.name
                    handle = store._api.open(path)
                    try:
                        identity = store._api.inspect(handle, path)
                        store._api.check_security(handle)
                        _need(type(identity) is FileIdentity and identity.volume == self._root_identity.volume
                              and 0 <= identity.size <= MAX_BLOB_BYTES, 'BUNDLE_STAGE_INVENTORY_INVALID')
                        inventory[entry.name] = identity
                        total += identity.size
                    finally:
                        store._api.close(handle)
            _need(total <= MAX_STAGED_BYTES, 'BUNDLE_STAGE_INVENTORY_INVALID')
            store._check()
            return inventory, total

    def _read_record(self, record):
        bundle = record.bundle
        expected = tuple((path, bundle.files[path]) for path in bundle_codec.PATHS) + (
            (MANIFEST_KEY, bundle.manifest_bytes),)
        _need(len(record.descriptors) == len(expected), 'BUNDLE_STAGE_INCOMPLETE')
        actual_files = {}
        manifest = None
        for (path, descriptor), (expected_path, raw) in zip(record.descriptors, expected):
            _need(path == expected_path and type(descriptor) is StagedBlob,
                  'BUNDLE_STAGE_DESCRIPTOR_MISMATCH')
            actual = self._store.read_blob(descriptor)
            _need(actual == raw and len(actual) == descriptor.identity.size
                  and _digest(actual) == descriptor.sha256, 'BUNDLE_STAGE_CONTENT_MISMATCH')
            if path == MANIFEST_KEY:
                manifest = actual
            else:
                actual_files[path] = actual
        decoded = bundle_codec.decode_bundle(manifest, actual_files)
        _need(decoded.manifest_bytes == bundle.manifest_bytes and decoded.files == bundle.files
              and decoded.project_revision == bundle.project_revision, 'BUNDLE_STAGE_CONTENT_MISMATCH')
        self._verify_owner()
        return decoded

    def stage(self, command_id: str, bundle) -> StageReceipt:
        """Reserve all twelve objects, then put/read/decode exact owned bytes.

        A failed put call may already have created a blob without returning a
        descriptor. Such ownership stays UNKNOWN and this owner never retries.
        """
        _need(type(command_id) is str and _COMMAND.fullmatch(command_id), 'BUNDLE_STAGE_COMMAND_REQUIRED')
        _need(type(bundle) is bundle_codec.CompleteFixtureBundle, 'BUNDLE_STAGE_EXACT_BUNDLE_REQUIRED')
        # Revalidate at the boundary before any native operation.
        bundle = bundle_codec.decode_bundle(bundle.manifest_bytes, bundle.files)
        with self._mutex:
            self._healthy()
            prior = self._records.get(command_id)
            if prior is not None:
                _need(prior.bundle.manifest_bytes == bundle.manifest_bytes and prior.bundle.files == bundle.files,
                      'BUNDLE_STAGE_COMMAND_CONFLICT')
                try:
                    self._verify_owner()
                except BaseException as exc:
                    raise self._hold('BUNDLE_STAGE_OWNER_UNVERIFIED') from exc
                return prior.receipt
            payloads = tuple((path, bundle.files[path]) for path in bundle_codec.PATHS) + (
                (MANIFEST_KEY, bundle.manifest_bytes),)
            reserved = sum(len(raw) for _, raw in payloads)
            try:
                inventory, used_bytes = self._inventory()
            except BaseException as exc:
                raise self._hold('BUNDLE_STAGE_INVENTORY_UNVERIFIED') from exc
            # Known, no-effect exhaustion is ordinary rejection, not a hold.
            _need(len(inventory) + len(payloads) <= MAX_STAGED_OBJECTS
                  and used_bytes + reserved <= MAX_STAGED_BYTES, 'BUNDLE_STAGE_QUOTA')
            record = _Record(command_id, bundle, reserved)
            self._records[command_id] = record  # reservation precedes first put
            try:
                for path, raw in payloads:
                    record.attempted_puts += 1  # even an unreturned put may create
                    descriptor = self._store.put_bytes(raw)
                    _need(type(descriptor) is StagedBlob, 'BUNDLE_STAGE_DESCRIPTOR_MISMATCH')
                    record.descriptors.append((path, descriptor))
                    _need(self._store.read_blob(descriptor) == raw, 'BUNDLE_STAGE_CONTENT_MISMATCH')
                # Complete-set second readback is distinct from put's own check.
                self._read_record(record)
                actual_inventory, actual_bytes = self._inventory()
                expected_inventory = {**inventory, **{blob.object_id: blob.identity
                                      for _, blob in record.descriptors}}
                _need(len(expected_inventory) == len(inventory) + len(payloads)
                      and actual_inventory == expected_inventory
                      and actual_bytes == used_bytes + reserved, 'BUNDLE_STAGE_INVENTORY_CHANGED')
                receipt = StageReceipt(command_id, bundle.project_revision, _digest(bundle.manifest_bytes),
                                       self._root_identity, tuple(record.descriptors[:-1]),
                                       record.descriptors[-1][1])
                record.receipt, record.status = receipt, 'STAGED_BYTES_READ_BACK'
                return receipt
            except BaseException as exc:
                record.status = 'UNKNOWN'
                raise self._hold('BUNDLE_STAGE_UNKNOWN', unknown=True) from exc

    def lookup(self, command_id: str, project_revision: str | None = None) -> StageReceipt | None:
        _need(type(command_id) is str and _COMMAND.fullmatch(command_id), 'BUNDLE_STAGE_COMMAND_REQUIRED')
        _need(project_revision is None or (type(project_revision) is str
              and _REVISION.fullmatch(project_revision)), 'BUNDLE_STAGE_PROJECT_REQUIRED')
        with self._mutex:
            self._healthy()
            record = self._records.get(command_id)
            if record is not None and project_revision is not None:
                _need(record.bundle.project_revision == project_revision, 'BUNDLE_STAGE_COMMAND_CONFLICT')
            try:
                self._verify_owner()
            except BaseException as exc:
                raise self._hold('BUNDLE_STAGE_OWNER_UNVERIFIED') from exc
            return None if record is None else record.receipt

    def readback(self, receipt: StageReceipt):
        """Re-read only an exact receipt object issued and retained by this owner."""
        _need(type(receipt) is StageReceipt, 'BUNDLE_STAGE_REGISTERED_RECEIPT_REQUIRED')
        with self._mutex:
            self._healthy()
            record = self._records.get(receipt.command_id)
            _need(record is not None and record.receipt is receipt
                  and receipt.project_revision == record.bundle.project_revision
                  and receipt.manifest_sha256 == _digest(record.bundle.manifest_bytes)
                  and receipt.root_identity == self._root_identity
                  and receipt.files == tuple(record.descriptors[:-1])
                  and receipt.manifest == record.descriptors[-1][1],
                  'BUNDLE_STAGE_REGISTERED_RECEIPT_REQUIRED')
            try:
                self._verify_owner()
                return self._read_record(record)
            except BaseException as exc:
                raise self._hold('BUNDLE_STAGE_READBACK_UNVERIFIED') from exc

    def snapshot(self) -> tuple[StageAttempt, ...]:
        """Return retained in-memory ownership, including UNKNOWN after failure.

        This diagnostic intentionally remains usable after hold/close. It does
        not validate native state or authorize cleanup, reuse or resumption.
        """
        with self._mutex:
            return tuple(StageAttempt(record.command_id, record.bundle.project_revision, record.status,
                         len(bundle_codec.PATHS) + 1, record.reserved_bytes, record.attempted_puts,
                         tuple(record.descriptors)) for record in self._records.values())

    def close(self) -> None:
        with self._mutex:
            # Keep the same store/marker on failed close so its native handle
            # registry and this cleanup owner remain reachable for close retry.
            self._closed = True
            try:
                self._store.close()
            except BaseException as exc:
                raise self._hold('BUNDLE_STAGE_CLOSE_UNCERTAIN', unknown=True) from exc
            if getattr(self._store, '_hh_gt03_bundle_stager_owner', None) is self:
                self._store._hh_gt03_bundle_stager_owner = None
