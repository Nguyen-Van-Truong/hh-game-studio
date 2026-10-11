"""Immutable offline releases with one atomic selector/command journal.

The private install root is separate from consumer projects. No operation here
creates, deletes or modifies game, art or saves. Removing a project addon is a
separate integration step; deactivation is not proof of that acceptance gate.
Cooperating writers use the bootstrap OS guard. Hostile concurrent filesystem
writers and Windows power-loss durability are outside this process-crash claim.
"""
from __future__ import annotations

import errno
import os
from pathlib import Path
from typing import Mapping
import uuid
import time
from . import addon_transaction
from . import lifecycle_transaction

from .release_contract import (
    PackageError, SCHEMA, HEX, canonical, digest_bytes, digest_file, need,
    strict_json, verify_package, verify_manifest, verify_contents, MAX_MEMBER,
)
try:
    from build.bootstrap.install_toolchain import safe_path, mutation_guard, sync_directory
except ModuleNotFoundError:
    from studio.build.bootstrap.install_toolchain import safe_path, mutation_guard, sync_directory

STATE_SCHEMA = "hh-studio-install-4"
MAX_STATE = 16 * 1024**2
MAX_COMMANDS = 8192
WINDOWS_RENAME_RETRY_SECONDS = 2.0
WINDOWS_RENAME_RETRY_INTERVAL_SECONDS = 0.05


def _new_file(path: Path, data: bytes) -> None:
    path = safe_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _publish_stage(stage: Path, final: Path) -> None:
    """Atomically publish a staged directory, tolerating short AV share locks.

    Windows scanners can briefly hold a just-written file in the staging tree.
    The operation remains one atomic rename; only the bounded transient sharing
    errors are retried.  A real permission/configuration failure still escapes
    with the original exception after the measured two-second window.
    """
    deadline = time.monotonic() + WINDOWS_RENAME_RETRY_SECONDS
    while True:
        try:
            os.rename(stage, final)
            return
        except PermissionError as error:
            transient = (getattr(error, "winerror", None) in (5, 32)
                         or error.errno in (errno.EACCES, errno.EBUSY))
            if os.name != "nt" or not transient:
                raise
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise
            time.sleep(min(WINDOWS_RENAME_RETRY_INTERVAL_SECONDS, remaining))


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
            addon_transaction.recover(self)
            lifecycle_transaction.recover(self)

    def _recover_pending(self) -> None:
        # Ordinary addon WALs predate the combined lifecycle record. Recover
        # them first, then reconcile a selector/addon intent if one exists.
        addon_transaction.recover(self)
        lifecycle_transaction.recover(self)

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
        for component, owned in state["owned_components"].items():
            need(isinstance(component, str) and component.endswith("::addons/hh_studio")
                 and isinstance(owned, dict), "install ownership component invalid")
            for relative, digest in owned.items():
                need(isinstance(relative, str) and relative and not Path(relative).is_absolute()
                     and ".." not in Path(relative).parts and "\\" not in relative and ":" not in relative
                     and isinstance(digest, str) and HEX.fullmatch(digest), "install ownership path invalid")
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
            self._recover_pending()
            state, token = self._state()
            return {**state, "state_sha256": token}

    def lookup(self, command_id: str) -> dict | None:
        self._command_id(command_id)
        with mutation_guard(self.root):
            self._recover_pending()
            state, _ = self._state()
            row = state["commands"].get(command_id)
            return None if row is None else row["receipt"]

    @staticmethod
    def _command_id(command_id: str) -> None:
        need(isinstance(command_id, str) and 0 < len(command_id) <= 160
             and all(32 < ord(c) < 127 for c in command_id), "invalid command_id")

    def _begin(self, command_id: str, request: dict, expected_state_sha256: str) -> tuple:
        self._recover_pending()
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
        need(not lifecycle_transaction.stopped(self), "lifecycle stop latch is durable")
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
        receipt = self._record(state, command_id, digest, action, manifest)
        self._publish(state, expected)
        return receipt

    def _record(self, state: dict, command_id: str, digest: str,
                action: str, manifest: dict | None) -> dict:
        state["revision"] += 1
        receipt = {"status": "COMMITTED", "action": action, "command_id": command_id,
                   "revision": state["revision"], "active": state["active"], "previous": state["previous"],
                   "package_id": None if manifest is None else manifest["package_id"],
                   "version": None if manifest is None else manifest["version"],
                   "source_closure_sha256": None if manifest is None else manifest["source_closure_sha256"]}
        state["commands"][command_id] = {"request_digest": digest, "receipt": receipt}
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
            self._recover_pending()
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
        _publish_stage(stage, final)
        sync_directory(self.versions)
        self._read_release(identity)
        return identity

    def install(self, package_path: Path, *, command_id: str, expected_state_sha256: str,
                expected_version: str | None = None) -> dict:
        """Verify an artifact completely before entering the install mutation.

        ``expected_version`` is optional for the normal selector path.  The
        release/upgrade coordinator can bind a requested version at the same
        pre-unpack boundary, so a valid but stale package cannot reach staging.
        """
        verified = verify_package(package_path, trusted_keys=self.trusted_keys,
                                  target=self.target, expected_version=expected_version)
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

    def _verify_package(self, package_path: Path) -> dict:
        """Package verification hook used by the combined lifecycle API."""
        return verify_package(package_path, trusted_keys=self.trusted_keys, target=self.target)

    def install_lifecycle(self, project: Path, package_path: Path, *, command_id: str,
                          expected_state_sha256: str, stop_event=None) -> dict:
        """Atomically reconcile a trusted release selector and project addon.

        ``stop_event`` requests cancellation before intent or a drain after
        intent. Recovery on the next process invocation uses the same durable
        lifecycle record. This API exposes no diagnostic failure hooks.
        """
        return lifecycle_transaction.install(
            self, safe_path(project), safe_path(package_path), command_id=command_id,
            expected_state_sha256=expected_state_sha256, stop_event=stop_event)

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

    def rollback_lifecycle(self, project: Path, *, command_id: str, destination: str,
                           expected_state_sha256: str, stop_event=None) -> dict:
        """Rollback selector and addon as one durable lifecycle transaction."""
        return lifecycle_transaction.rollback(
            self, safe_path(project), destination, command_id=command_id,
            expected_state_sha256=expected_state_sha256, stop_event=stop_event)

    def stop(self, *, command_id: str = "lifecycle.stop") -> dict:
        """Durably stop new lifecycle admissions and drain a pending intent."""
        return lifecycle_transaction.stop(self, command_id=command_id)

    @staticmethod
    def stop_existing(root: Path, *, command_id: str = "lifecycle.stop") -> dict:
        """Stop through the independent control lock without opening work state."""
        from types import SimpleNamespace
        root = safe_path(root)
        need(root.is_dir(), "install root required for Stop")
        control = SimpleNamespace(root=root, _command_id=ConsumerInstall._command_id)
        return lifecycle_transaction.stop(control, command_id=command_id)

    def resume(self, *, command_id: str = "lifecycle.resume") -> dict:
        """Explicitly clear a durable Stop latch after recovery is complete."""
        return lifecycle_transaction.resume(self, command_id=command_id)

    def lifecycle_status(self) -> dict:
        """Read the durable lifecycle Stop/pending state for a coordinator."""
        with mutation_guard(self.root):
            self._recover_pending()
            return lifecycle_transaction.status(self)

    # Descriptive aliases used by coordinator workers.
    apply_lifecycle = install_lifecycle
    install_upgrade = install_lifecycle
    rollback_release = rollback_lifecycle

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
        return os.path.normcase(str(project)) + "::addons/hh_studio"

    def addon_files(self, release: str) -> dict[str, bytes]:
        """Complete project addon, including its protocol preload dependency."""
        self._read_release(release)
        studio = self.versions / release / "payload/studio"
        files = addon_transaction.tree_bytes(studio / "godot-addon/addons/hh_studio")
        need(files is not None, "addon source unavailable")
        files["jcs_godot.gd"] = safe_path(studio / "protocol/jcs_godot.gd").read_bytes()
        return files

    def install_addon(self, project: Path, *, command_id: str, expected_state_sha256: str,
                      repair: bool = False, release: str) -> dict:
        """Install/repair an explicitly selected trusted release's addon.

        An unowned collision is rejected before mutation, even if bytes match.
        A repair explicitly authorizes replacing changed files already owned by
        this installer. Other manual content and deleted-package edits survive.
        """
        project = safe_path(project)
        need(project.is_dir() and (project / "project.godot").is_file(), "consumer project required")
        with mutation_guard(self.root):
            action = "repair-addon" if repair else "install-addon"
            request = {"action": action, "project": str(project), "release": release}
            state, digest, prior = self._begin(command_id, request, expected_state_sha256)
            if prior is not None:
                return prior
            need(state["active"] == release, "addon release is not active")
            manifest = self._read_release(release)
            source = self.addon_files(release)
            destination = safe_path(project / "addons/hh_studio")
            ownership_key = self._ownership_key(project)
            prior_owned = state["owned_components"].get(ownership_key)
            need(prior_owned is None or repair, "addon already installed; use explicit repair")
            prior_owned = prior_owned or {}
            original = addon_transaction.tree_bytes(destination)
            before = addon_transaction.files_hash(original)
            files = dict(original or {})
            owned = {}
            for relative, data in source.items():
                need(relative not in files or relative in prior_owned,
                     "unowned addon file conflict: " + relative + "; preserve it and reconcile before install")
                files[relative] = data
                owned[relative] = digest_bytes(data)
            for relative, expected in prior_owned.items():
                if relative not in source and relative in files and digest_bytes(files[relative]) == expected:
                    del files[relative]
            state["owned_components"][ownership_key] = owned
            return addon_transaction.replace(self, project, files, state, expected_state_sha256,
                                             command_id, digest, action, manifest, before)

    def uninstall_addon(self, project: Path, *, command_id: str, expected_state_sha256: str) -> dict:
        project = safe_path(project)
        with mutation_guard(self.root):
            request = {"action": "uninstall-addon", "project": str(project)}
            state, digest, prior = self._begin(command_id, request, expected_state_sha256)
            if prior is not None:
                return prior
            destination = safe_path(project / "addons/hh_studio")
            original = addon_transaction.tree_bytes(destination)
            before = addon_transaction.files_hash(original)
            files = dict(original or {})
            ownership_key = self._ownership_key(project)
            for relative, expected in state["owned_components"].get(ownership_key, {}).items():
                if relative in files and digest_bytes(files[relative]) == expected:
                    del files[relative]
            state["owned_components"].pop(ownership_key, None)
            return addon_transaction.replace(self, project, files, state, expected_state_sha256,
                                             command_id, digest, "uninstall-addon", None, before)
