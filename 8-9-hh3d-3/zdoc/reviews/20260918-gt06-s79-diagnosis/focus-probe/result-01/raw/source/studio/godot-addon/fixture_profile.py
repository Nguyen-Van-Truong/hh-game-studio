"""Trusted release bytes plus closed candidate eligibility, never engine proof.

The source pins and this factory belong to the frozen installed host release.
Candidate bundle roles/hashes cannot substitute their own plugin or config.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import MappingProxyType

HERE = Path(__file__).resolve().parent
STUDIO = HERE.parent
PROFILE = 'hh-godot-managed-fixture-1'
DEFAULT_SCRIPT = b'extends Node3D\n@export var fixture_value: int = 7\n'
DEFAULT_SCENE = (b'[gd_scene load_steps=2 format=3]\n\n'
    b'[ext_resource type="Script" path="res://scripts/fixture_actor.gd" id="1_script"]\n\n'
    b'[node name="Fixture" type="Node3D"]\nscript = ExtResource("1_script")\n'
    b'fixture_value = 23\nmetadata/hh_studio_id = "root"\n')
_SOURCES = {
    'project.godot': 'godot-addon/fixture_profile/project.godot',
    'scripts/fixture_actor.gd.uid': 'godot-addon/fixture_profile/scripts/fixture_actor.gd.uid',
    'addons/hh_studio/plugin.cfg': 'godot-addon/addons/hh_studio/plugin.cfg',
    'addons/hh_studio/plugin.gd': 'godot-addon/addons/hh_studio/plugin.gd',
    'addons/hh_studio/plugin.gd.uid': 'godot-addon/fixture_profile/addons/hh_studio/plugin.gd.uid',
    'addons/hh_studio/scene_commands.gd': 'godot-addon/addons/hh_studio/scene_commands.gd',
    'addons/hh_studio/scene_commands.gd.uid': 'godot-addon/fixture_profile/addons/hh_studio/scene_commands.gd.uid',
    'addons/hh_studio/jcs_godot.gd': 'protocol/jcs_godot.gd',
    'addons/hh_studio/jcs_godot.gd.uid': 'godot-addon/fixture_profile/addons/hh_studio/jcs_godot.gd.uid',
}


class FixtureProfileError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _need(condition, code):
    if not condition:
        raise FixtureProfileError(code)


def _sibling(name):
    path = HERE / (name + '.py')
    raw = path.read_bytes()
    key = '_hh_fixture_' + hashlib.sha256(str(path).encode() + b'\0' + raw).hexdigest()
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, path)
        module = importlib.util.module_from_spec(spec)
        module._fixture_source_sha256 = hashlib.sha256(raw).hexdigest()
        sys.modules[key] = module
        try:
            exec(compile(raw, str(path), 'exec'), module.__dict__)
        except BaseException:
            del sys.modules[key]
            raise
    module = sys.modules[key]
    _need(module.__file__ == str(path)
          and module._fixture_source_sha256 == hashlib.sha256(raw).hexdigest(),
          'FIXTURE_MODULE_SOURCE_MISMATCH')
    return module


# The staging owner and factory deliberately use one source-bound codec class.
staging = _sibling('bundle_staging')
bundle_codec = staging.bundle_codec


def trusted_files():
    """Exact installed-release content; no paths or pins from the candidate."""
    pins = json.loads((HERE / 'fixture_profile/source-pins.json').read_bytes())
    _need(type(pins) is dict and set(pins) == {'schema', 'profile', 'files'}
          and pins['schema'] == 'hh-godot-fixture-source-pins-1'
          and pins['profile'] == PROFILE and type(pins['files']) is dict
          and set(pins['files']) == set(_SOURCES), 'FIXTURE_RELEASE_PINS')
    contents = {}
    for name, source in _SOURCES.items():
        row = pins['files'][name]
        _need(type(row) is dict and set(row) == {'source', 'sha256'}
              and row['source'] == source, 'FIXTURE_RELEASE_PINS')
        path = STUDIO / source
        # This is release-source verification, not the native file-effect API.
        _need(not path.is_symlink() and not getattr(path.stat(follow_symlinks=False),
              'st_file_attributes', 0) & 0x400, 'FIXTURE_RELEASE_REPARSE')
        raw = path.read_bytes()
        _need(hashlib.sha256(raw).hexdigest() == row['sha256'], 'FIXTURE_RELEASE_BYTES_CHANGED')
        contents[name] = raw
    return MappingProxyType(contents)


def compose(scene: bytes, script: bytes, *, scene_revision: str, engine_sha256: str):
    """Create a complete inert bundle; observations still belong to the caller."""
    files = dict(trusted_files())
    files[bundle_codec.SCENE_PATH] = scene
    files[bundle_codec.SCRIPT_PATH] = script
    return bundle_codec.create_bundle(files, scene_revision=scene_revision, engine_sha256=engine_sha256)


@dataclass(frozen=True, slots=True)
class EligibleFixture:
    """Byte eligibility only. Public activation/ACK require native validation."""
    bundle: object
    scene: object = field(init=False)
    script: object = field(init=False)
    profile: str = field(default=PROFILE, init=False)

    def __post_init__(self):
        _need(type(self.bundle) is bundle_codec.CompleteFixtureBundle, 'FIXTURE_BUNDLE_TYPE')
        # Re-decode to verify even a locally forged object before examining data.
        checked = bundle_codec.decode_bundle(self.bundle.manifest_bytes, self.bundle.files)
        for path, raw in trusted_files().items():
            _need(checked.files[path] == raw, 'FIXTURE_UNTRUSTED_RELEASE_CONTENT')
        scene_module = _sibling('scene_profile')
        scene = scene_module.validate_scene(checked.files[bundle_codec.SCENE_PATH],
            script_uid=checked.files[bundle_codec.UID_PATH],
            script_source=checked.files[bundle_codec.SCRIPT_PATH])
        reserved_uids = {raw.decode('ascii').strip() for path, raw in checked.files.items()
                         if path.endswith('.gd.uid')}
        _need(len(reserved_uids) == 4 and scene.scene_uid not in reserved_uids,
              'FIXTURE_RELEASE_UID_COLLISION')
        script = _sibling('script_profile').validate_script(checked.files[bundle_codec.SCRIPT_PATH])
        object.__setattr__(self, 'bundle', checked)
        object.__setattr__(self, 'scene', scene)
        object.__setattr__(self, 'script', script)


def qualify(bundle):
    return EligibleFixture(bundle)
