"""Complete, inert managed-fixture bytes. Declared source is not trusted proof."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import re
from types import MappingProxyType

from studio.protocol.core import ValidationError, canonical_bytes, parse_json

SCHEMA = 'hh-godot-fixture-bundle-2'
PROFILE = 'hh-godot-managed-fixture-1'
SCENE_PATH = 'scenes/fixture.tscn'
SCRIPT_PATH = 'scripts/fixture_actor.gd'
UID_PATH = SCRIPT_PATH + '.uid'
MAX_MANIFEST_BYTES = 16 * 1024
MAX_BUNDLE_BYTES = 2 * 1024 * 1024
FILE_PROFILE = MappingProxyType({
    SCENE_PATH: ('managed_scene', 1024 * 1024),
    SCRIPT_PATH: ('managed_script', 16 * 1024),
    UID_PATH: ('managed_uid', 128),
    'project.godot': ('trusted_config', 16 * 1024),
    'addons/hh_studio/plugin.cfg': ('trusted_addon', 4 * 1024),
    'addons/hh_studio/plugin.gd': ('trusted_addon', 128 * 1024),
    'addons/hh_studio/plugin.gd.uid': ('trusted_uid', 128),
    'addons/hh_studio/scene_commands.gd': ('trusted_addon', 128 * 1024),
    'addons/hh_studio/scene_commands.gd.uid': ('trusted_uid', 128),
    'addons/hh_studio/jcs_godot.gd': ('trusted_addon', 128 * 1024),
    'addons/hh_studio/jcs_godot.gd.uid': ('trusted_uid', 128),
})
PATHS = tuple(sorted(FILE_PROFILE))
TRUSTED_PATHS = tuple(path for path in PATHS if FILE_PROFILE[path][0].startswith('trusted_'))
_HASH = re.compile(r'[0-9a-f]{64}\Z')
_REVISION = re.compile(r'sha256:[0-9a-f]{64}\Z')
_UID = re.compile(rb'uid://[a-z0-9]+\n\Z')


class BundleError(ValidationError):
    def __init__(self, code: str):
        super().__init__(code, 'complete inert Godot fixture bundle validation')


def _need(condition: object, code: str) -> None:
    if not condition:
        raise BundleError(code)


def _shape(value: object, fields) -> None:
    _need(type(value) is dict and set(value) == set(fields), 'BUNDLE_V2_INVALID_SHAPE')


def _hash(value: object, *, revision: bool = False) -> None:
    pattern = _REVISION if revision else _HASH
    _need(type(value) is str and pattern.fullmatch(value) is not None, 'BUNDLE_V2_INVALID_HASH')


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _bytes(value: object, limit: int) -> bytes:
    # Bound exact builtin buffers before copying. No arbitrary buffer hooks.
    _need(type(value) in (bytes, bytearray), 'BUNDLE_V2_BYTES_REQUIRED')
    _need(0 < len(value) <= limit, 'BUNDLE_V2_SIZE_LIMIT')
    return bytes(value)


def _files(files: Mapping[str, bytes]) -> Mapping[str, bytes]:
    _need(isinstance(files, Mapping) and len(files) == len(PATHS)
          and set(files) == set(PATHS), 'BUNDLE_V2_INVALID_PATHS')
    copied = {}
    total = 0
    for path in PATHS:
        role, limit = FILE_PROFILE[path]
        raw = _bytes(files[path], limit)
        total += len(raw)
        _need(total <= MAX_BUNDLE_BYTES, 'BUNDLE_V2_SIZE_LIMIT')
        try:
            raw.decode('utf-8', 'strict')
        except UnicodeDecodeError as exc:
            raise BundleError('BUNDLE_V2_INVALID_UTF8') from exc
        if role.endswith('_uid'):
            _need(_UID.fullmatch(raw) is not None, 'BUNDLE_V2_INVALID_UID')
        copied[path] = raw
    return MappingProxyType(copied)


def _observations(scene_revision: str, engine_sha256: str) -> dict:
    _hash(scene_revision, revision=True)
    _hash(engine_sha256)
    return {'scene_revision': scene_revision, 'engine_sha256': engine_sha256}


def _revision(value: dict) -> str:
    return 'sha256:' + _digest(canonical_bytes(value))


def _body(files: Mapping[str, bytes], observations: dict) -> dict:
    metadata = {path: {'sha256': _digest(files[path]), 'size_bytes': len(files[path]),
                       'role': FILE_PROFILE[path][0]} for path in PATHS}
    trusted = {'profile': PROFILE, 'files': {path: metadata[path] for path in TRUSTED_PATHS}}
    return {'schema': SCHEMA, 'profile': PROFILE, 'files': metadata,
            'trusted_source_revision': _revision(trusted), 'caller_observations': observations}


def _validate(manifest: bytes, files: Mapping[str, bytes]) -> None:
    value = parse_json(manifest)
    _shape(value, {'schema', 'profile', 'files', 'trusted_source_revision',
                   'caller_observations', 'project_revision'})
    _need(value['schema'] == SCHEMA and value['profile'] == PROFILE, 'BUNDLE_V2_UNSUPPORTED_PROFILE')
    _shape(value['files'], PATHS)
    for path, raw in files.items():
        entry = value['files'][path]
        _shape(entry, {'sha256', 'size_bytes', 'role'})
        _hash(entry['sha256'])
        _need(type(entry['size_bytes']) is int and entry['size_bytes'] == len(raw),
              'BUNDLE_V2_LENGTH_MISMATCH')
        _need(entry['sha256'] == _digest(raw), 'BUNDLE_V2_CONTENT_MISMATCH')
        _need(entry['role'] == FILE_PROFILE[path][0], 'BUNDLE_V2_ROLE_MISMATCH')
    observed = value['caller_observations']
    _shape(observed, {'scene_revision', 'engine_sha256'})
    body = _body(files, _observations(observed['scene_revision'], observed['engine_sha256']))
    _hash(value['trusted_source_revision'], revision=True)
    _hash(value['project_revision'], revision=True)
    _need(value['trusted_source_revision'] == body['trusted_source_revision'],
          'BUNDLE_V2_TRUSTED_REVISION_MISMATCH')
    _need(value['project_revision'] == _revision(body), 'BUNDLE_V2_REVISION_MISMATCH')
    _need(canonical_bytes(value) == manifest, 'BUNDLE_V2_NONCANONICAL_MANIFEST')


@dataclass(frozen=True, slots=True)
class CompleteFixtureBundle:
    """Immutable validated copies; no syntax, release trust or engine claim.

    Direct construction is validated too. ``trusted_source_revision`` names
    caller-declared bytes; only a separately pinned trusted factory can attest
    that those bytes belong to an approved release.
    """
    manifest_bytes: bytes
    files: Mapping[str, bytes]

    def __post_init__(self) -> None:
        manifest = _bytes(self.manifest_bytes, MAX_MANIFEST_BYTES)
        files = _files(self.files)
        _need(len(manifest) + sum(map(len, files.values())) <= MAX_BUNDLE_BYTES,
              'BUNDLE_V2_SIZE_LIMIT')
        _validate(manifest, files)
        object.__setattr__(self, 'manifest_bytes', manifest)
        object.__setattr__(self, 'files', files)

    @property
    def project_revision(self) -> str:
        return parse_json(self.manifest_bytes)['project_revision']

    @property
    def trusted_source_revision(self) -> str:
        return parse_json(self.manifest_bytes)['trusted_source_revision']

    @property
    def scene_revision(self) -> str:
        return parse_json(self.manifest_bytes)['caller_observations']['scene_revision']

    @property
    def engine_sha256(self) -> str:
        return parse_json(self.manifest_bytes)['caller_observations']['engine_sha256']

    @property
    def script_sha256(self) -> str:
        return _digest(self.files[SCRIPT_PATH])

    @property
    def uid_sha256(self) -> str:
        return _digest(self.files[UID_PATH])


def create_bundle(files: Mapping[str, bytes], *, scene_revision: str,
                  engine_sha256: str) -> CompleteFixtureBundle:
    """Construct exact profile bytes, with explicitly unverified observations."""
    files = _files(files)
    body = _body(files, _observations(scene_revision, engine_sha256))
    return CompleteFixtureBundle(canonical_bytes({**body, 'project_revision': _revision(body)}), files)


def decode_bundle(manifest: bytes, files: Mapping[str, bytes]) -> CompleteFixtureBundle:
    return CompleteFixtureBundle(manifest, files)


def replace_script(bundle: CompleteFixtureBundle, new_script: bytes, *,
                   expected_project_revision: str, expected_script_sha256: str,
                   expected_uid_sha256: str) -> CompleteFixtureBundle:
    """Pure replacement, preserving every other byte; no external-state CAS."""
    _need(type(bundle) is CompleteFixtureBundle, 'BUNDLE_V2_REQUIRED')
    _hash(expected_project_revision, revision=True)
    _hash(expected_script_sha256)
    _hash(expected_uid_sha256)
    _need(expected_project_revision == bundle.project_revision, 'BUNDLE_V2_STALE_PROJECT')
    _need(expected_script_sha256 == bundle.script_sha256, 'BUNDLE_V2_STALE_SCRIPT')
    _need(expected_uid_sha256 == bundle.uid_sha256, 'BUNDLE_V2_STALE_UID')
    return create_bundle({**bundle.files, SCRIPT_PATH: new_script},
                         scene_revision=bundle.scene_revision, engine_sha256=bundle.engine_sha256)
