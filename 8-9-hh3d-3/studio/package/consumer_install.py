"""Immutable offline releases with one atomic selector/command journal.

The private install root is separate from consumer projects. No operation here
creates, deletes or modifies game, art or saves. Removing a project addon is a
separate integration step; deactivation is not proof of that acceptance gate.
Cooperating writers use the bootstrap OS guard. Hostile concurrent filesystem
writers and Windows power-loss durability are outside this process-crash claim.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping
import uuid
import shutil

from .release_contract import (
    PackageError, SCHEMA, HEX, canonical, digest_bytes, digest_file, need,
    strict_json, verify_package, verify_manifest, verify_contents, MAX_MEMBER,
)
try:
    from build.bootstrap.install_toolchain import safe_path, mutation_guard, sync_directory
except ModuleNotFoundError:
    from studio.build.bootstrap.install_toolchain import safe_path, mutation_guard, sync_directory

STATE_SCHEMA = "hh-studio-install-3"
MAX_STATE = 16 * 1024**2
MAX_COMMANDS = 8192


def _new_file(path: Path, data: bytes) -> None:
    path = safe_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


class ConsumerInstall:
    def __init__(self, root: Path, *, trusted_keys: Mapping[str, bytes], target: str = "Windows"):
        # Do not resolve first: that would hide a pre-existing symlink.
        self.root = safe_path(root)
        self.versions = safe_path(self.root / "releases")
        self.stages = safe_path(self.root / "stages")
        self.state_path = safe_path(self.root / ".install.json")
        self.trusted_keys = dict(trusted_keys)
        self.target = target
        need(target in ("Windows", "Linux", "Linux-headless"), "unsupported consumer target")
        need(self.trusted_keys and all(isinstance(k, str) and isinstance(v, bytes) and len(v) == 32
                                      for k, v in self.trusted_keys.items()), "public trust store required")
        self.root.mkdir(parents=True, exist_ok=True)
        with mutation_guard(self.root):
            self.versions.mkdir(exist_ok=True)
            self.stages.mkdir(exist_ok=True)

    def _state(self) -> tuple[dict, str]:
        path = safe_path(self.state_path)
        if not path.exists():
            return {"schema": STATE_SCHEMA, "target": self.target, "revision": 0,
                    "active": None, "previous": None, "commands": {}, "owned_components": {}}, "ABSENT"
        with path.open("rb") as stream:
            raw = stream.read(MAX_STATE + 1)
        need(len(raw) <= MAX_STATE, "install journal full; retain state and use a new store")
        state = strict_json(raw)
        need(isinstance(state, dict) and set(state) == {
            "schema", "target", "revision", "active", "previous", "commands", "owned_components"
        } and state["schema"] == STATE_SCHEMA and state["target"] == self.target,
             "install state schema/target mismatch")
        need(type(state["revision"]) is int and state["revision"] >= 0
             and isinstance(state["commands"], dict) and len(state["commands"]) <= MAX_COMMANDS,
             "install state invalid")
        need(isinstance(state["owned_components"], dict), "install ownership invalid")
        for field in ("active", "previous"):
            need(state[field] is None or isinstance(state[field], str) and HEX.fullmatch(state[field]),
                 "install state release identity invalid")
        for command_id, row in state["commands"].items():
            self._command_id(command_id)
            need(isinstance(row, dict) and set(row) == {"request_digest", "receipt"}
                 and isinstance(row["request_digest"], str) and HEX.fullmatch(row["request_digest"])
                 and isinstance(row["receipt"], dict) and row["receipt"].get("command_id") == command_id,
                 "install journal entry invalid")
        return state, digest_bytes(raw)

    def snapshot(self) -> dict:
        with mutation_guard(self.root):
            state, token = self._state()
            return {**state, "state_sha256": token}

    def lookup(self, command_id: str) -> dict | None:
        self._command_id(command_id)
        with mutation_guard(self.root):
            state, _ = self._state()
            row = state["commands"].get(command_id)
            return None if row is None else row["receipt"]

    @staticmethod
    def _command_id(command_id: str) -> None:
        need(isinstance(command_id, str) and 0 < len(command_id) <= 160
             and all(32 < ord(c) < 127 for c in command_id), "invalid command_id")

    def _begin(self, command_id: str, request: dict, expected_state_sha256: str) -> tuple:
        self._command_id(command_id)
        need(expected_state_sha256 == "ABSENT" or isinstance(expected_state_sha256, str)
             and HEX.fullmatch(expected_state_sha256), "expected state token required")
        state, token = self._state()
        digest = digest_bytes(canonical(request))
        existing = state["commands"].get(command_id)
        # Retry precedes CAS. The request consists only of immutable caller
        # parameters, never active/previous read after an earlier attempt.
        if existing is not None:
            need(existing["request_digest"] == digest, "command_id conflict")
            return state, digest, existing["receipt"]
        need(token == expected_state_sha256, "install state CAS mismatch")
        need(len(state["commands"]) < MAX_COMMANDS, "install journal full")
        return state, digest, None

    def _publish(self, state: dict, expected: str) -> None:
        raw = canonical(state) + b"\n"
        need(len(raw) <= MAX_STATE, "install journal byte limit")
        temporary = safe_path(self.root / (".install-" + uuid.uuid4().hex + ".tmp"))
        _new_file(temporary, raw)
        need(self._state()[1] == expected, "install state changed before publish")
        os.replace(temporary, safe_path(self.state_path))
        sync_directory(self.root)
        # Failure after replace has indeterminate ACK, not a compensating write.
        # lookup/retry resolves the state from this same atomic document.
        need(safe_path(self.state_path).read_bytes() == raw, "install publish readback indeterminate")

    def _commit(self, state: dict, command_id: str, digest: str, expected: str,
                action: str, manifest: dict | None) -> dict:
        state["revision"] += 1
        receipt = {"status": "COMMITTED", "action": action, "command_id": command_id,
                   "revision": state["revision"], "active": state["active"], "previous": state["previous"],
                   "package_id": None if manifest is None else manifest["package_id"],
                   "version": None if manifest is None else manifest["version"],
                   "source_closure_sha256": None if manifest is None else manifest["source_closure_sha256"]}
        state["commands"][command_id] = {"request_digest": digest, "receipt": receipt}
        self._publish(state, expected)
        return receipt

    def _read_release(self, identity: str) -> dict:
        need(isinstance(identity, str) and HEX.fullmatch(identity), "invalid release identity")
        root = safe_path(self.versions / identity)
        need(root.is_dir(), "trusted release missing")
        manifest_path = safe_path(root / "manifest.json")
        with manifest_path.open("rb") as stream:
            raw = stream.read(4 * 1024**2 + 1)
        need(len(raw) <= 4 * 1024**2 and digest_bytes(raw) == identity, "stored manifest changed")
        manifest = strict_json(raw)
        verify_manifest(manifest, trusted_keys=self.trusted_keys, target=self.target)
        members = {}
        for directory, dirs, files in os.walk(root, followlinks=False):
            for name in dirs:
                safe_path(Path(directory) / name)
            for name in files:
                path = safe_path(Path(directory) / name)
                relative = path.relative_to(root).as_posix()
                if relative == "manifest.json":
                    continue
                need(relative in manifest["files"], "unowned file in immutable release")
                row = manifest["files"][relative]
                need(path.stat().st_size == row["size"] <= MAX_MEMBER, "release file size changed")
                with path.open("rb") as stream:
                    members[relative] = stream.read(row["size"] + 1)
        verify_contents(manifest, members)
        return manifest

    def active_path(self) -> Path:
        with mutation_guard(self.root):
            state, _ = self._state()
            need(state["active"] is not None, "no active release")
            self._read_release(state["active"])
            return self.versions / state["active"] / "payload" / "studio"

    def _stage(self, verified: dict) -> str:
        identity = verified["manifest_sha256"]
        final = safe_path(self.versions / identity)
        if final.exists():
            need(self._read_release(identity) == verified["manifest"], "existing release differs")
            return identity
        stage = safe_path(self.stages / uuid.uuid4().hex)
        stage.mkdir()
        # Failed stages remain diagnostic; never recursively delete an existing
        # directory. A retry uses a fresh stage or verifies a renamed orphan.
        for name, data in verified["members"].items():
            _new_file(stage / name, data)
        _new_file(stage / "manifest.json", canonical(verified["manifest"]))
        for name, data in verified["members"].items():
            need(digest_file(stage / name) == digest_bytes(data), "staged readback mismatch")
        sync_directory(stage)
        need(not final.exists(), "release appeared during staging")
        os.rename(stage, final)
        sync_directory(self.versions)
        self._read_release(identity)
        return identity

    def install(self, package_path: Path, *, command_id: str, expected_state_sha256: str) -> dict:
        verified = verify_package(package_path, trusted_keys=self.trusted_keys, target=self.target)
        request = {"action": "install", "archive_sha256": verified["archive_sha256"],
                   "release": verified["manifest_sha256"], "target": self.target}
        with mutation_guard(self.root):
            state, digest, prior = self._begin(command_id, request, expected_state_sha256)
            if prior is not None:
                return prior
            # Verify last-good before activation; never overwrite owner edits.
            if state["active"] is not None:
                self._read_release(state["active"])
            identity = self._stage(verified)
            if state["active"] != identity:
                state["previous"], state["active"] = state["active"], identity
            return self._commit(state, command_id, digest, expected_state_sha256, "install", verified["manifest"])

    def rollback(self, *, command_id: str, destination: str, expected_state_sha256: str) -> dict:
        request = {"action": "rollback", "destination": destination, "target": self.target}
        with mutation_guard(self.root):
            state, digest, prior = self._begin(command_id, request, expected_state_sha256)
            if prior is not None:
                return prior
            need(state["previous"] is not None and destination == state["previous"], "rollback is not last-good")
            manifest = self._read_release(destination)  # Signature/closure/compatibility before effect.
            state["active"], state["previous"] = destination, None
            return self._commit(state, command_id, digest, expected_state_sha256, "rollback", manifest)

    def deactivate(self, *, command_id: str, expected_state_sha256: str) -> dict:
        request = {"action": "deactivate", "target": self.target}
        with mutation_guard(self.root):
            state, digest, prior = self._begin(command_id, request, expected_state_sha256)
            if prior is not None:
                return prior
            state["active"], state["previous"] = None, None
            return self._commit(state, command_id, digest, expected_state_sha256, "deactivate", None)

    @staticmethod
    def _ownership_key(project: Path) -> str:
        return project.resolve().as_posix() + "::addons/hh_studio"

    def install_addon(self, project: Path, *, command_id: str, expected_state_sha256: str,
                      repair: bool = False) -> dict:
        """Install the package-owned addon into a pre-existing consumer project."""
        project = safe_path(project)
        with mutation_guard(self.root):
            state, _ = self._state()
            action = "repair-addon" if repair else "install-addon"
            request = {"action": action, "project": project.as_posix(), "release": state["active"]}
            state, digest, prior = self._begin(command_id, request, expected_state_sha256)
            if prior is not None: return prior
            need(state["active"] is not None, "no active release")
            source = safe_path(self.versions / state["active"] / "payload/studio/godot-addon")
            destination = safe_path(project / "addons/hh_studio")
            need(source.is_dir(), "addon source unavailable")
            ownership_key = self._ownership_key(project)
            prior_owned = state["owned_components"].get(ownership_key)
            need(prior_owned is None or repair, "addon already installed")
            if prior_owned is None:
                prior_owned = {}
            stage = safe_path(project / (".hh-studio-addon-" + uuid.uuid4().hex + ".stage"))
            destination.parent.mkdir(parents=True, exist_ok=True)
            stage.mkdir()
            owned = {}
            preexisting = set()
            try:
                if destination.exists():
                    need(destination.is_dir(), "addon destination is not a directory")
                    for existing_path in destination.rglob("*"):
                        rel = existing_path.relative_to(destination)
                        target = stage / rel
                        if existing_path.is_dir():
                            target.mkdir(parents=True, exist_ok=True)
                        elif existing_path.is_file():
                            target.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copyfile(existing_path, target)
                            preexisting.add((destination / rel).relative_to(project).as_posix())
                source_names = set()
                for src in sorted(source.rglob("*")):
                    rel = src.relative_to(source)
                    dst = safe_path(stage / rel)
                    if src.is_dir(): dst.mkdir(parents=True, exist_ok=True); continue
                    need(src.is_file(), "addon contains nonregular member")
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    project_relative = (destination / rel).relative_to(project).as_posix()
                    source_names.add(project_relative)
                    # A first install never takes ownership of a colliding
                    # consumer file.  A repair may replace only a path that
                    # this install journal already owns.
                    if project_relative in preexisting and project_relative not in prior_owned:
                        continue
                    shutil.copyfile(src, dst)
                    owned[project_relative] = digest_file(dst)
                # Remove package files deleted from a newer release only when
                # they still contain the bytes this journal installed.
                for project_relative, expected in prior_owned.items():
                    if project_relative in source_names:
                        continue
                    old_path = safe_path(project / project_relative)
                    staged_path = safe_path(stage / Path(project_relative).relative_to(destination.relative_to(project)))
                    if old_path.is_file() and digest_file(old_path) == expected and staged_path.is_file():
                        staged_path.unlink()
                if destination.exists():
                    backup = safe_path(project / (".hh-studio-addon-" + uuid.uuid4().hex + ".backup"))
                    os.replace(destination, backup)
                    try:
                        os.replace(stage, destination)
                    except BaseException:
                        if not destination.exists() and backup.exists(): os.replace(backup, destination)
                        raise
                    shutil.rmtree(backup, ignore_errors=True)
                else:
                    os.replace(stage, destination)
            except BaseException:
                shutil.rmtree(stage, ignore_errors=True); raise
            state["owned_components"][ownership_key] = owned
            return self._commit(state, command_id, digest, expected_state_sha256, action, None)

    def uninstall_addon(self, project: Path, *, command_id: str, expected_state_sha256: str) -> dict:
        project = safe_path(project)
        with mutation_guard(self.root):
            state, _ = self._state()
            request = {"action": "uninstall-addon", "project": project.as_posix()}
            state, digest, prior = self._begin(command_id, request, expected_state_sha256)
            if prior is not None: return prior
            preserved = []
            ownership_key = self._ownership_key(project)
            for component, files in list(state["owned_components"].items()):
                if component != ownership_key: continue
                for relative, expected in files.items():
                    path = safe_path(project / relative)
                    if path.is_file() and digest_file(path) == expected:
                        path.unlink()
                    elif path.exists():
                        preserved.append(relative)
                root = safe_path(project / "addons/hh_studio")
                if root.is_dir():
                    for directory, dirs, names in os.walk(root, topdown=False):
                        for name in names:
                            pass
                        for name in dirs:
                            try: (Path(directory) / name).rmdir()
                            except OSError: pass
                    try: root.rmdir()
                    except OSError: pass
                state["owned_components"].pop(component, None)
            return self._commit(state, command_id, digest, expected_state_sha256, "uninstall-addon", None)

