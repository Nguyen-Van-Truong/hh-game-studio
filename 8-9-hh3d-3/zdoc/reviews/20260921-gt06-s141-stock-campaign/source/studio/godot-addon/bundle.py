"""Inert, bounded two-file fixture bundles; no Godot or filesystem operations."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import re
from types import MappingProxyType

from studio.protocol.core import ValidationError, canonical_bytes, parse_json

SCHEMA = 'hh-godot-fixture-bundle-1'
SCENE_PATH = 'scenes/fixture.tscn'
SCRIPT_PATH = 'scripts/fixture_actor.gd'
MAX_SCENE_BYTES = 1024 * 1024
MAX_SCRIPT_BYTES = 16 * 1024
MAX_MANIFEST_BYTES = 4096
_PATHS = frozenset((SCENE_PATH, SCRIPT_PATH))
_HASH = re.compile(r'[0-9a-f]{64}\Z')
_REVISION = re.compile(r'sha256:[0-9a-f]{64}\Z')


class BundleError(ValidationError):
    def __init__(self, code: str):
        super().__init__(code, 'inert Godot fixture bundle validation')


def _need(condition: object, code: str) -> None:
    if not condition:
        raise BundleError(code)


def _shape(value: object, fields: set[str] | frozenset[str]) -> None:
    _need(type(value) is dict and set(value) == fields, 'BUNDLE_INVALID_SHAPE')


def _hash(value: object, *, revision: bool = False) -> None:
    pattern = _REVISION if revision else _HASH
    _need(type(value) is str and pattern.fullmatch(value) is not None, 'BUNDLE_INVALID_HASH')


def _bytes(value: object, limit: int) -> bytes:
    # Check before copying/decoding. No arbitrary buffer or coercion hooks.
    _need(type(value) in (bytes, bytearray), 'BUNDLE_BYTES_REQUIRED')
    _need(len(value) <= limit, 'BUNDLE_SIZE_LIMIT')
    return bytes(value)


def _text(value: object, limit: int) -> bytes:
    raw = _bytes(value, limit)
    try:
        raw.decode('utf-8', 'strict')
    except UnicodeDecodeError as exc:
        raise BundleError('BUNDLE_INVALID_UTF8') from exc
    return raw


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _observations(scene_revision: str, engine_sha256: str) -> dict:
    _hash(scene_revision, revision=True)
    _hash(engine_sha256)
    return {'scene_revision': scene_revision, 'engine_sha256': engine_sha256}


def _body(scene: bytes, script: bytes, observations: dict) -> dict:
    return {'schema': SCHEMA, 'files': {
        SCENE_PATH: {'sha256': _digest(scene), 'size_bytes': len(scene)},
        SCRIPT_PATH: {'sha256': _digest(script), 'size_bytes': len(script)}},
        'caller_observations': observations}


def _revision(body: dict) -> str:
    return 'sha256:' + _digest(canonical_bytes(body))


def _validate(manifest: bytes, scene: bytes, script: bytes) -> None:
    value = parse_json(manifest)
    _shape(value, {'schema', 'files', 'caller_observations', 'project_revision'})
    _need(value['schema'] == SCHEMA, 'BUNDLE_UNSUPPORTED_SCHEMA')
    _shape(value['files'], _PATHS)
    for path, raw in ((SCENE_PATH, scene), (SCRIPT_PATH, script)):
        entry = value['files'][path]
        _shape(entry, {'sha256', 'size_bytes'})
        _hash(entry['sha256'])
        _need(type(entry['size_bytes']) is int and entry['size_bytes'] == len(raw),
              'BUNDLE_LENGTH_MISMATCH')
        _need(entry['sha256'] == _digest(raw), 'BUNDLE_CONTENT_MISMATCH')
    observed = value['caller_observations']
    _shape(observed, {'scene_revision', 'engine_sha256'})
    _observations(observed['scene_revision'], observed['engine_sha256'])
    _hash(value['project_revision'], revision=True)
    expected = _body(scene, script, observed)
    _need(value['project_revision'] == _revision(expected), 'BUNDLE_REVISION_MISMATCH')
    _need(canonical_bytes(value) == manifest, 'BUNDLE_NONCANONICAL_MANIFEST')


@dataclass(frozen=True, slots=True)
class FixtureBundle:
    """Validated immutable copies. Construction also validates direct callers.

    Observations are untrusted assertions until an external trusted caller
    independently establishes them. Content bytes are not parsed as Godot.
    """
    manifest_bytes: bytes
    scene_bytes: bytes
    script_bytes: bytes

    def __post_init__(self) -> None:
        manifest = _bytes(self.manifest_bytes, MAX_MANIFEST_BYTES)
        scene = _text(self.scene_bytes, MAX_SCENE_BYTES)
        script = _text(self.script_bytes, MAX_SCRIPT_BYTES)
        _validate(manifest, scene, script)
        object.__setattr__(self, 'manifest_bytes', manifest)
        object.__setattr__(self, 'scene_bytes', scene)
        object.__setattr__(self, 'script_bytes', script)

    @property
    def files(self) -> Mapping[str, bytes]:
        return MappingProxyType({SCENE_PATH: self.scene_bytes, SCRIPT_PATH: self.script_bytes})

    @property
    def project_revision(self) -> str:
        return parse_json(self.manifest_bytes)['project_revision']

    @property
    def script_sha256(self) -> str:
        return _digest(self.script_bytes)

    @property
    def scene_revision(self) -> str:
        return parse_json(self.manifest_bytes)['caller_observations']['scene_revision']

    @property
    def engine_sha256(self) -> str:
        return parse_json(self.manifest_bytes)['caller_observations']['engine_sha256']


def create_bundle(scene: bytes, script: bytes, *, scene_revision: str,
                  engine_sha256: str) -> FixtureBundle:
    """Copy and hash exact UTF-8 bytes; caller observations are not attested."""
    scene = _text(scene, MAX_SCENE_BYTES)
    script = _text(script, MAX_SCRIPT_BYTES)
    body = _body(scene, script, _observations(scene_revision, engine_sha256))
    manifest = canonical_bytes({**body, 'project_revision': _revision(body)})
    return FixtureBundle(manifest, scene, script)


def decode_bundle(manifest: bytes, files: Mapping[str, bytes]) -> FixtureBundle:
    """Verify an exact canonical manifest and exact two-path content mapping."""
    _need(isinstance(files, Mapping) and len(files) == 2 and set(files) == _PATHS,
          'BUNDLE_INVALID_PATHS')
    return FixtureBundle(manifest, files[SCENE_PATH], files[SCRIPT_PATH])


def replace_script(bundle: FixtureBundle, new_script: bytes, *,
                   expected_project_revision: str,
                   expected_script_sha256: str) -> FixtureBundle:
    """Return a new inert bundle with both old-revision preconditions checked.

    This is not compare-and-swap on external state and does not validate or
    authorize script execution. The old bundle is never changed.
    """
    _need(type(bundle) is FixtureBundle, 'BUNDLE_REQUIRED')
    _hash(expected_project_revision, revision=True)
    _hash(expected_script_sha256)
    _need(expected_project_revision == bundle.project_revision, 'BUNDLE_STALE_PROJECT')
    _need(expected_script_sha256 == bundle.script_sha256, 'BUNDLE_STALE_SCRIPT')
    return create_bundle(bundle.scene_bytes, new_script, scene_revision=bundle.scene_revision,
                         engine_sha256=bundle.engine_sha256)
