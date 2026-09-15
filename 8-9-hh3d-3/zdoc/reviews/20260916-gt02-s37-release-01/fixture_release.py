"""Complete immutable *fixture* release graphs, not engine assets or activation.

The fixture has a closed asset grammar: value plus explicit asset-ID references.
All reachable files must be present, every declared file must be reachable, and
readback checks both bytes and the reference graph. No filesystem path, importer,
script evaluation, generation selection or command outcome is supplied here.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import uuid

from .limits import SafetyViolation, canonical_json, parse_json_utf8
from .private_store import PrivateBlobStore, StagedBlob
from .safe_open import FileIdentity

MAX_ASSETS = 16
MAX_ASSET_BYTES = 64 * 1024
MAX_RELEASE_BYTES = 1024 * 1024
_ASSET_ID = re.compile(r'[a-z][a-z0-9_-]{0,47}\Z')
_NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z')
_HASH = re.compile(r'[0-9a-f]{64}\Z')
_RELEASE_ID = re.compile(r'release-[0-9a-f]{32}\Z')
_BLOB_ID = re.compile(r'blob-[0-9a-f]{32}\Z')
_FORMAT = 'hh-fixture-release-1'


class ReleaseError(SafetyViolation):
    def __init__(self, code: str, *, outcome_unknown: bool = False) -> None:
        self.outcome_unknown = outcome_unknown
        super().__init__(code)


@dataclass(frozen=True)
class StagedRelease:
    release_id: str
    manifest: StagedBlob


@dataclass(frozen=True)
class PinnedRelease:
    release: StagedRelease
    project_id: str
    source_revision: str
    source_sha256: str
    game_revision: str
    entrypoint: str
    assets: tuple[tuple[str, bytes], ...]

    def read(self, asset_id: str) -> bytes:
        _asset_id(asset_id)
        for name, data in self.assets:
            if name == asset_id:
                return data
        raise ReleaseError('RELEASE_ASSET_NOT_FOUND')


def _matches(pattern: re.Pattern, value: object, code: str) -> None:
    if type(value) is not str or not pattern.fullmatch(value):
        raise ReleaseError(code)


def _asset_id(value: object) -> None:
    _matches(_ASSET_ID, value, 'INVALID_RELEASE_ASSET_ID')


def _fields(value: object, fields: set[str]) -> None:
    if type(value) is not dict or set(value) != fields:
        raise ReleaseError('INVALID_RELEASE_SCHEMA')


def _blob_value(blob: StagedBlob) -> dict:
    if type(blob) is not StagedBlob or type(blob.identity) is not FileIdentity:
        raise ReleaseError('INVALID_RELEASE_BLOB')
    return {'object_id': blob.object_id, 'volume': str(blob.identity.volume),
            'file_id': blob.identity.file_id, 'size': blob.identity.size, 'sha256': blob.sha256}


def _parse_blob(value: object) -> StagedBlob:
    _fields(value, {'object_id', 'volume', 'file_id', 'size', 'sha256'})
    _matches(_BLOB_ID, value['object_id'], 'INVALID_RELEASE_BLOB')
    _matches(_HASH, value['sha256'], 'INVALID_RELEASE_BLOB')
    _matches(re.compile('[0-9a-f]{32}'), value['file_id'], 'INVALID_RELEASE_BLOB')
    _matches(re.compile('0|[1-9][0-9]{0,19}'), value['volume'], 'INVALID_RELEASE_BLOB')
    if (int(value['volume']) >= 2**64 or type(value['size']) is not int
            or not 0 < value['size'] <= MAX_ASSET_BYTES):
        raise ReleaseError('INVALID_RELEASE_BLOB')
    return StagedBlob(value['object_id'], FileIdentity(int(value['volume']), value['file_id'], value['size']), value['sha256'])


def release_value(release: StagedRelease) -> dict:
    """Local typed descriptor encoding for the future protected selector log."""
    if type(release) is not StagedRelease:
        raise ReleaseError('INVALID_RELEASE_DESCRIPTOR')
    _matches(_RELEASE_ID, release.release_id, 'INVALID_RELEASE_DESCRIPTOR')
    blob = _blob_value(release.manifest)
    _parse_blob(blob)
    return {'release_id': release.release_id, 'manifest': blob}


def parse_release(value: object) -> StagedRelease:
    _fields(value, {'release_id', 'manifest'})
    _matches(_RELEASE_ID, value['release_id'], 'INVALID_RELEASE_DESCRIPTOR')
    return StagedRelease(value['release_id'], _parse_blob(value['manifest']))


def _asset(data: bytes) -> tuple[bytes, tuple[str, ...]]:
    if type(data) is not bytes or not 0 < len(data) <= MAX_ASSET_BYTES:
        raise ReleaseError('RELEASE_ASSET_LIMIT')
    value = parse_json_utf8(data)
    _fields(value, {'value', 'references'})
    references = value['references']
    if type(references) is not list or len(references) > MAX_ASSETS:
        raise ReleaseError('INVALID_RELEASE_REFERENCES')
    for name in references:
        _asset_id(name)
    if len(set(references)) != len(references) or references != sorted(references):
        raise ReleaseError('INVALID_RELEASE_REFERENCES')
    result = canonical_json(value)
    if len(result) > MAX_ASSET_BYTES:
        raise ReleaseError('RELEASE_ASSET_LIMIT')
    return result, tuple(references)


def _graph(entrypoint: str, graph: dict[str, tuple[str, ...]]) -> None:
    _asset_id(entrypoint)
    if entrypoint not in graph or any(ref not in graph for refs in graph.values() for ref in refs):
        raise ReleaseError('RELEASE_CLOSURE_INCOMPLETE')
    reached, pending = set(), [entrypoint]
    while pending:
        name = pending.pop()
        if name in reached:
            continue
        reached.add(name)
        pending.extend(graph[name])
    if reached != set(graph):
        raise ReleaseError('RELEASE_UNREACHABLE_ASSET')


def stage_fixture_release(store: PrivateBlobStore, *, project_id: str, source_revision: str,
                          source_sha256: str, game_revision: str, entrypoint: str,
                          assets: dict[str, bytes]) -> StagedRelease:
    if type(store) is not PrivateBlobStore:
        raise ReleaseError('RELEASE_STORE_REQUIRED')
    for name in (project_id, source_revision, game_revision):
        _matches(_NAME, name, 'INVALID_RELEASE_REVISION')
    _matches(_HASH, source_sha256, 'INVALID_RELEASE_SOURCE_HASH')
    if type(assets) is not dict or not 1 <= len(assets) <= MAX_ASSETS:
        raise ReleaseError('RELEASE_ASSET_LIMIT')
    prepared, graph = {}, {}
    # Copy/validate the entire grammar and graph before any file creation.
    for name, data in tuple(assets.items()):
        _asset_id(name)
        prepared[name], graph[name] = _asset(data)
    _graph(entrypoint, graph)
    if sum(map(len, prepared.values())) > MAX_RELEASE_BYTES:
        raise ReleaseError('RELEASE_BYTES_LIMIT')
    release_id = 'release-' + uuid.uuid4().hex
    try:
        records = []
        for name in sorted(prepared):
            blob = store.put_bytes(prepared[name])
            records.append({'asset_id': name, 'blob': _blob_value(blob), 'references': list(graph[name])})
        manifest = canonical_json({'format': _FORMAT, 'release_id': release_id,
                                   'project_id': project_id, 'source_revision': source_revision,
                                   'source_sha256': source_sha256, 'game_revision': game_revision,
                                   'store_id': store.root.name,
                                   'root_file_id': store.root_identity.file_id,
                                   'volume': str(store.root_identity.volume),
                                   'entrypoint': entrypoint, 'assets': records})
        if len(manifest) > MAX_ASSET_BYTES:
            raise ReleaseError('RELEASE_MANIFEST_LIMIT')
        release = StagedRelease(release_id, store.put_bytes(manifest))
        pin_fixture_release(store, release, project_id=project_id)
        return release
    except BaseException as exc:
        # Several blobs may already exist. Never treat quota or a later
        # validation-shaped error as proof that this staging attempt had no
        # effect. Preserve orphan/partial files; a selector owns reconciliation.
        store._poisoned = True
        if isinstance(exc, (SafetyViolation, OSError)):
            raise ReleaseError('RELEASE_STAGE_UNCERTAIN', outcome_unknown=True) from exc
        raise


def pin_fixture_release(store: PrivateBlobStore, release: StagedRelease, *, project_id: str) -> PinnedRelease:
    if type(store) is not PrivateBlobStore:
        raise ReleaseError('RELEASE_STORE_REQUIRED')
    _matches(_NAME, project_id, 'INVALID_RELEASE_PROJECT')
    release_value(release)
    raw = store.read_blob(release.manifest)
    value = parse_json_utf8(raw)
    _fields(value, {'format', 'release_id', 'project_id', 'source_revision', 'source_sha256',
                    'game_revision', 'store_id', 'root_file_id', 'volume', 'entrypoint', 'assets'})
    if (canonical_json(value) != raw or value['format'] != _FORMAT
            or value['release_id'] != release.release_id or value['project_id'] != project_id
            or value['store_id'] != store.root.name or value['root_file_id'] != store.root_identity.file_id
            or value['volume'] != str(store.root_identity.volume)):
        raise ReleaseError('RELEASE_BINDING_MISMATCH')
    for name in ('source_revision', 'game_revision'):
        _matches(_NAME, value[name], 'INVALID_RELEASE_REVISION')
    _matches(_HASH, value['source_sha256'], 'INVALID_RELEASE_SOURCE_HASH')
    records = value['assets']
    if type(records) is not list or not 1 <= len(records) <= MAX_ASSETS:
        raise ReleaseError('RELEASE_ASSET_LIMIT')
    graph, descriptors = {}, {}
    for record in records:
        _fields(record, {'asset_id', 'blob', 'references'})
        name = record['asset_id']
        _asset_id(name)
        if name in descriptors:
            raise ReleaseError('RELEASE_DUPLICATE_ASSET')
        blob = _parse_blob(record['blob'])
        if blob.object_id == release.manifest.object_id or blob.object_id in {item.object_id for item in descriptors.values()}:
            raise ReleaseError('RELEASE_DUPLICATE_BLOB')
        descriptors[name] = blob
    if list(descriptors) != sorted(descriptors):
        raise ReleaseError('RELEASE_ASSET_ORDER')
    if sum(blob.identity.size for blob in descriptors.values()) > MAX_RELEASE_BYTES:
        raise ReleaseError('RELEASE_BYTES_LIMIT')
    pinned = []
    for record in records:
        name = record['asset_id']
        data = store.read_blob(descriptors[name])
        canonical, refs = _asset(data)
        if data != canonical or record['references'] != list(refs):
            raise ReleaseError('RELEASE_GRAPH_MISMATCH')
        graph[name] = refs
        pinned.append((name, canonical))
    _graph(value['entrypoint'], graph)
    return PinnedRelease(release, project_id, value['source_revision'], value['source_sha256'],
                         value['game_revision'], value['entrypoint'], tuple(pinned))
