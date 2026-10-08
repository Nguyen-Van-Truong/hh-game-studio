"""Trusted, fixture-scoped gameplay-source host registration.

The registration is deliberately host-owned.  A caller cannot select a path,
project, capability flag, or config file.  The module reads the one checked-in
host policy and returns an opaque profile created by this module.  Every
operation revalidates the policy bytes so an edited config fails closed.

This is an authority-zero registration seam.  It only makes the already
durable ``GameplaySourcePublicationOwner`` route usable for the two GT-09
fixtures; it does not publish a global capability or imply acceptance.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import stat
import sys
from typing import Any, Mapping


PROFILE = "hh-godot-gameplay-source-1"
CONFIG_SCHEMA = "hh-gameplay-fixture-host-config-1"
PROFILE_VERSION = 1
SUPPORTED_CLIENT_VERSIONS = frozenset({"pc-godot-4.7.2"})
OPERATIONS = ("scene.node.create", "scene.node.update", "scene.resource.create",
              "gameplay-source.inspect", "gameplay-source.publish")
FIXTURE_PROJECTS = {"project.registered.arena": {"root_type": "Node2D"},
                    "project.registered.room": {"root_type": "Node3D"}}
_ID = re.compile(r"[a-z][a-z0-9._-]{0,63}\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_TOKEN = object()
CONFIG_PATH = Path(__file__).with_name("fixture_profile.json")
_MODULE_PATH = Path(__file__)
_MODULE_BYTES = _MODULE_PATH.read_bytes()
_MODULE_SHA256 = hashlib.sha256(_MODULE_BYTES).hexdigest()
if sys._getframe().f_code != compile(_MODULE_BYTES, str(_MODULE_PATH), "exec", dont_inherit=True):
    raise ValueError("FIXTURE_PROFILE_IMPORT_CHANGED")


class FixtureProfileError(ValueError):
    """Typed failure while loading or validating trusted host policy."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _need(value: object, code: str) -> None:
    if not value:
        raise FixtureProfileError(code)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    """Stable JSON used for the profile digest, independent of file spacing."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _read_config() -> tuple[dict[str, Any], bytes, str]:
    try:
        path = CONFIG_PATH.absolute()
        for part in (path, *path.parents):
            info = part.lstat()
            _need(not stat.S_ISLNK(info.st_mode)
                  and not getattr(info, "st_file_attributes", 0) & 0x400,
                  "FIXTURE_CONFIG_REPARSE")
        before = path.stat(follow_symlinks=False)
        _need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
              and before.st_size <= 16384, "FIXTURE_CONFIG_SIZE")
        with path.open("rb") as stream:
            raw = stream.read(16385)
        after = path.stat(follow_symlinks=False)
        _need(len(raw) <= 16384
              and (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
              == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
              "FIXTURE_CONFIG_CHANGED")
    except OSError as exc:
        raise FixtureProfileError("FIXTURE_CONFIG_UNAVAILABLE") from exc
    config_digest = _sha(raw)
    try:
        def unique_pairs(pairs):
            result = {}
            for key, item in pairs:
                _need(key not in result, "FIXTURE_CONFIG_DUPLICATE_KEY")
                result[key] = item
            return result
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FixtureProfileError("FIXTURE_CONFIG_INVALID") from exc
    _need(type(value) is dict, "FIXTURE_CONFIG_SHAPE")
    return value, raw, config_digest


def _validate_config(value: Mapping[str, Any]) -> dict[str, Any]:
    required = {"schema", "profile", "version", "authority", "script_enabled",
                "public_runtime_enabled", "client_versions", "operations", "projects"}
    _need(set(value) == required, "FIXTURE_CONFIG_FIELDS")
    _need(value["schema"] == CONFIG_SCHEMA and value["profile"] == PROFILE,
          "FIXTURE_CONFIG_IDENTITY")
    _need(type(value["version"]) is int and value["version"] == PROFILE_VERSION,
          "FIXTURE_PROFILE_VERSION")
    _need(type(value["authority"]) is int and value["authority"] == 0,
          "FIXTURE_PROFILE_AUTHORITY")
    _need(value["script_enabled"] is True and value["public_runtime_enabled"] is False,
          "FIXTURE_PROFILE_DISABLED")
    clients = value["client_versions"]
    _need(type(clients) is list and all(type(item) is str for item in clients)
          and tuple(clients) == tuple(sorted(set(clients)))
          and tuple(clients) == tuple(sorted(SUPPORTED_CLIENT_VERSIONS)),
          "FIXTURE_CLIENT_VERSIONS")
    operations = value["operations"]
    _need(type(operations) is list and tuple(operations) == OPERATIONS,
          "FIXTURE_PROFILE_OPERATIONS")
    projects = value["projects"]
    _need(type(projects) is dict and projects == FIXTURE_PROJECTS, "FIXTURE_PROJECTS")
    checked: dict[str, dict[str, str]] = {}
    for project_id, entry in projects.items():
        _need(type(project_id) is str and _ID.fullmatch(project_id),
              "FIXTURE_PROJECT_ID")
        _need(type(entry) is dict and set(entry) == {"root_type"}
              and entry["root_type"] in {"Node2D", "Node3D"},
              "FIXTURE_PROJECT_ROOT")
        checked[project_id] = {"root_type": entry["root_type"]}
    # Return a detached, normalized policy.  A caller cannot mutate the JSON
    # object retained by a previously-issued profile.
    return {
        "schema": CONFIG_SCHEMA, "profile": PROFILE,
        "version": PROFILE_VERSION, "authority": 0,
        "script_enabled": True, "public_runtime_enabled": False,
        "client_versions": sorted(SUPPORTED_CLIENT_VERSIONS),
        "operations": list(OPERATIONS), "projects": checked,
    }


@dataclass(frozen=True, slots=True)
class FixtureProfile:
    """Opaque host grant for one allowlisted fixture project."""

    project_id: str
    root_type: str
    profile: str
    version: int
    profile_digest: str
    config_sha256: str
    module_sha256: str
    authority: int
    script_enabled: bool
    public_runtime_enabled: bool
    operations: tuple[str, ...]
    client_versions: tuple[str, ...]
    _token: object

    def __post_init__(self) -> None:
        _need(self._token is _TOKEN, "FIXTURE_PROFILE_UNTRUSTED")
        _need(_ID.fullmatch(self.project_id) is not None,
              "FIXTURE_PROJECT_ID")
        _need(self.profile == PROFILE and self.version == PROFILE_VERSION,
              "FIXTURE_PROFILE_VERSION")
        _need(_HEX.fullmatch(self.profile_digest) is not None
              and _HEX.fullmatch(self.config_sha256) is not None
              and self.module_sha256 == _MODULE_SHA256,
              "FIXTURE_PROFILE_DIGEST")
        _need(self.authority == 0 and self.script_enabled is True
              and self.public_runtime_enabled is False,
              "FIXTURE_PROFILE_DISABLED")
        _need(self.root_type in {"Node2D", "Node3D"}
              and self.operations == OPERATIONS
              and self.client_versions == tuple(sorted(SUPPORTED_CLIENT_VERSIONS)),
              "FIXTURE_PROFILE_SHAPE")

    @property
    def enabled(self) -> bool:
        return self.script_enabled and not self.public_runtime_enabled

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": CONFIG_SCHEMA,
            "profile": self.profile,
            "version": self.version,
            "project_id": self.project_id,
            "root_type": self.root_type,
            "profile_digest": self.profile_digest,
            "catalog_digest": "sha256:" + self.profile_digest,
            "config_sha256": self.config_sha256,
            "module_sha256": self.module_sha256,
            "authority": self.authority,
            "script_enabled": self.script_enabled,
            "public_runtime_enabled": self.public_runtime_enabled,
            "operations": list(self.operations),
            "client_versions": list(self.client_versions),
        }


def load_fixture_profile(project_id: str) -> FixtureProfile | None:
    """Return a host-created profile only for an allowlisted project.

    Unknown projects deliberately return ``None``.  This keeps default/global
    discovery empty and gives the adapter a typed, pre-effect rejection path.
    """
    value, _raw, config_digest = _read_config()
    policy = _validate_config(value)
    if type(project_id) is not str or project_id not in policy["projects"]:
        return None
    project = policy["projects"][project_id]
    profile_body = {
        "schema": CONFIG_SCHEMA, "profile": PROFILE,
        "version": PROFILE_VERSION, "authority": 0,
        "project_id": project_id, "root_type": project["root_type"],
        "operations": list(OPERATIONS),
        "client_versions": list(sorted(SUPPORTED_CLIENT_VERSIONS)),
    }
    return FixtureProfile(
        project_id=project_id, root_type=project["root_type"],
        profile=PROFILE, version=PROFILE_VERSION,
        profile_digest=_sha(_canonical(profile_body)),
        config_sha256=config_digest, module_sha256=_MODULE_SHA256,
        authority=0, script_enabled=True,
        public_runtime_enabled=False, operations=OPERATIONS,
        client_versions=tuple(sorted(SUPPORTED_CLIENT_VERSIONS)), _token=_TOKEN)


def validate_fixture_profile(profile: FixtureProfile, *, project_id: str,
                             source_files: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Recheck issued policy, including optional frozen owner closure binding."""
    _need(type(profile) is FixtureProfile and profile._token is _TOKEN,
          "FIXTURE_PROFILE_UNTRUSTED")
    _need(project_id == profile.project_id, "FIXTURE_PROFILE_PROJECT")
    _need(_MODULE_PATH.read_bytes() == _MODULE_BYTES, "FIXTURE_PROFILE_SOURCE_CHANGED")
    current = load_fixture_profile(project_id)
    _need(current is not None and current == profile, "FIXTURE_CONFIG_CHANGED")
    if source_files is not None:
        _need(isinstance(source_files, Mapping)
              and source_files.get("godot-addon/fixture_profile.json") == profile.config_sha256
              and source_files.get("godot-addon/gameplay_fixture_profile.py") == _MODULE_SHA256,
              "FIXTURE_PROFILE_CLOSURE")
    return profile.as_dict()


__all__ = [
    "CONFIG_PATH", "CONFIG_SCHEMA", "FixtureProfile", "FixtureProfileError",
    "OPERATIONS", "PROFILE", "PROFILE_VERSION", "SUPPORTED_CLIENT_VERSIONS",
    "load_fixture_profile", "validate_fixture_profile",
]
