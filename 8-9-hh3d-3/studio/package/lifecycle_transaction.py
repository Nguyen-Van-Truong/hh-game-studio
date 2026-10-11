"""Process-crash-safe release selector and addon lifecycle.

A lifecycle WAL is durable *before* the selector changes, and carries the
already-staged addon intent. Thus a crash between selector publication and
addon WAL publication is recoverable. The terminal command receipt is written
by the addon transaction only after addon readback. Callers hold the root guard.
Stop has its own OS lock and durable latch so it never waits for the work lock.
Windows directory fsync limitations remain those of the bootstrap protocol.
"""
from __future__ import annotations

import copy
import os
from pathlib import Path
import uuid

from . import addon_transaction as addon
from .release_contract import PackageError, HEX, canonical, digest_bytes, need, safe_path, strict_json
try:
    from build.bootstrap.install_toolchain import mutation_guard, sync_directory
except ModuleNotFoundError:
    from studio.build.bootstrap.install_toolchain import mutation_guard, sync_directory

SCHEMA = "hh-lifecycle-transaction-1"
CONTROL_SCHEMA = "hh-lifecycle-control-1"
MAX_WAL = 64 * 1024**2


class LifecycleStopped(PackageError):
    pass


def _wal(owner) -> Path:
    return safe_path(owner.root / ".lifecycle-pending.json")


def _control_root(owner) -> Path:
    return safe_path(owner.root / ".lifecycle-control")


def _read(path: Path, limit: int = MAX_WAL) -> dict:
    with safe_path(path).open("rb") as stream:
        raw = stream.read(limit + 1)
    need(len(raw) <= limit, "lifecycle record too large")
    value = strict_json(raw)
    need(isinstance(value, dict), "invalid lifecycle record")
    return value


def _write(path: Path, value: dict) -> None:
    raw = canonical(value) + b"\n"
    need(len(raw) <= MAX_WAL, "lifecycle record too large")
    temporary = safe_path(path.parent / (".lifecycle-" + uuid.uuid4().hex + ".tmp"))
    addon.write_file(temporary, raw)
    os.replace(temporary, safe_path(path))
    sync_directory(path.parent)
    need(path.read_bytes() == raw, "lifecycle record readback indeterminate")


def _control(owner) -> dict:
    path = safe_path(_control_root(owner) / "state.json")
    if not path.exists():
        return {"schema": CONTROL_SCHEMA, "stopped": False, "active": None, "phase": "IDLE", "commands": {}}
    value = _read(path, 64 * 1024)
    need(set(value) == {"schema", "stopped", "active", "phase", "commands"}
         and value["schema"] == CONTROL_SCHEMA and type(value["stopped"]) is bool
         and (value["active"] is None or isinstance(value["active"], str))
         and value["phase"] in ("IDLE", "PREPARING", "DRAINING", "STOPPED")
         and isinstance(value["commands"], dict) and len(value["commands"]) <= 8192,
         "invalid lifecycle control state")
    return value


def _save_control(owner, state: dict) -> None:
    _write(safe_path(_control_root(owner) / "state.json"), state)


def _guard_control(owner):
    root = _control_root(owner)
    root.mkdir(exist_ok=True)
    return mutation_guard(root)


def stopped(owner) -> bool:
    return _control(owner)["stopped"]


def _admit(owner, command_id: str) -> None:
    with _guard_control(owner):
        state = _control(owner)
        if state["stopped"]:
            raise LifecycleStopped("lifecycle stop latch is durable; explicit resume required")
        # The caller already holds the root OS guard. A PREPARING record from
        # a dead worker is diagnostic, and same-ID retry can stage afresh.
        state.update(active=command_id, phase="PREPARING")
        _save_control(owner, state)


def _terminal_control(owner) -> None:
    with _guard_control(owner):
        state = _control(owner)
        state.update(active=None, phase="STOPPED" if state["stopped"] else "IDLE")
        _save_control(owner, state)


def _check_event(owner, event) -> None:
    if event is not None and event.is_set():
        # A new operation gets a distinct cancellation command. Reusing a
        # prior Stop ID after explicit resume must only replay that old ACK.
        active = _control(owner)["active"]
        stop(owner, command_id="event.stop." + digest_bytes(canonical(active)))


def _cancel(owner, state: dict, command_id: str, digest: str, expected: str,
            action: str) -> dict:
    # Persist a terminal tombstone in the same command table, preserving the
    # selector and ownership. Retrying this ID never silently resumes work.
    receipt = owner._record(state, command_id, digest, action, None)
    receipt["status"] = "CANCELLED"
    receipt["reason"] = "STOP_BEFORE_INTENT"
    owner._publish(state, expected)
    _terminal_control(owner)
    return receipt


def _validate(owner, row: dict) -> None:
    need(set(row) == {"schema", "command_id", "request_digest", "before_state", "selector_state",
                      "selector_sha256", "final_sha256", "release", "addon"}
         and row["schema"] == SCHEMA, "invalid lifecycle pending record")
    owner._command_id(row["command_id"])
    need(isinstance(row["request_digest"], str) and HEX.fullmatch(row["request_digest"])
         and (row["before_state"] == "ABSENT" or isinstance(row["before_state"], str)
              and HEX.fullmatch(row["before_state"]))
         and isinstance(row["selector_state"], dict)
         and isinstance(row["release"], str) and HEX.fullmatch(row["release"])
         and isinstance(row["addon"], dict), "invalid lifecycle values")
    intent = row["addon"]
    need(set(intent) == {"schema", "project", "txid", "before", "after", "expected_state", "state"}
         and intent["schema"] == "hh-addon-transaction-1"
         and isinstance(intent["project"], str) and isinstance(intent["txid"], str)
         and len(intent["txid"]) == 32 and all(c in "0123456789abcdef" for c in intent["txid"])
         and (intent["before"] is None or isinstance(intent["before"], str) and HEX.fullmatch(intent["before"]))
         and isinstance(intent["after"], str) and HEX.fullmatch(intent["after"])
         and isinstance(intent["state"], dict), "invalid lifecycle addon intent")
    need(row["selector_sha256"] == digest_bytes(canonical(row["selector_state"]) + b"\n")
         and row["final_sha256"] == digest_bytes(canonical(intent["state"]) + b"\n")
         and intent["expected_state"] == row["selector_sha256"]
         and row["selector_state"]["active"] == row["release"]
         and intent["state"]["active"] == row["release"], "lifecycle selector binding mismatch")
    command = intent["state"]["commands"].get(row["command_id"])
    need(isinstance(command, dict) and command["request_digest"] == row["request_digest"]
         and command["receipt"]["status"] == "COMMITTED", "lifecycle command binding mismatch")


def _finish(owner, row: dict) -> None:
    _validate(owner, row)
    owner._read_release(row["release"])
    project = safe_path(Path(row["addon"]["project"]))
    need(project.is_dir() and safe_path(project / "project.godot").is_file(), "lifecycle project missing")
    addon_wal = safe_path(owner.root / ".addon-pending.json")
    _, token = owner._state()
    need(token in (row["before_state"], row["selector_sha256"], row["final_sha256"]),
         "lifecycle selector changed; preserve and reconcile")
    with addon.project_guard(owner, project) as work:
        if token == row["before_state"]:
            need(addon.tree_hash(project / "addons/hh_studio") == row["addon"]["before"],
                 "lifecycle owner edit before selector")
            owner._publish(row["selector_state"], token)
        if owner._state()[1] != row["final_sha256"]:
            if addon_wal.exists():
                need(_read(addon_wal) == row["addon"], "lifecycle/addon WAL conflict")
            else:
                _write(addon_wal, row["addon"])
            addon.finish(owner, row["addon"], work, addon_wal)
        else:
            need(addon.tree_hash(project / "addons/hh_studio") == row["addon"]["after"],
                 "lifecycle final addon readback conflict")
            if addon_wal.exists():
                need(_read(addon_wal) == row["addon"], "lifecycle terminal WAL conflict")
                addon.finish(owner, row["addon"], work, addon_wal)
        need(owner._state()[1] == row["final_sha256"]
             and addon.tree_hash(project / "addons/hh_studio") == row["addon"]["after"],
             "lifecycle postcondition indeterminate")
    _wal(owner).unlink()
    sync_directory(owner.root)
    _terminal_control(owner)


def recover(owner) -> None:
    path = _wal(owner)
    if path.exists():
        _finish(owner, _read(path))


def _prepare(owner, project: Path, release: str, state: dict) -> tuple[dict, str | None]:
    source = owner.addon_files(release)
    destination = safe_path(project / "addons/hh_studio")
    original = addon.tree_bytes(destination)
    before = addon.files_hash(original)
    owned = state["owned_components"].get(owner._ownership_key(project), {})
    files = dict(original or {})
    for relative, data in source.items():
        need(relative not in files or relative in owned,
             "unowned addon file conflict: " + relative + "; preserve and reconcile")
        files[relative] = data
    for relative, digest in owned.items():
        if relative not in source and relative in files and digest_bytes(files[relative]) == digest:
            del files[relative]
    state["owned_components"][owner._ownership_key(project)] = {k: digest_bytes(v) for k, v in source.items()}
    return files, before


def _execute(owner, project: Path, *, command_id: str, digest: str, before: dict,
             selector: dict, expected: str, action: str, manifest: dict,
             stop_event=None) -> dict:
    need(project.is_dir() and safe_path(project / "project.godot").is_file(), "consumer project required")
    files, tree_before = _prepare(owner, project, selector["active"], selector)
    # The provisional selector contains no terminal command receipt or updated
    # ownership; those become visible only after the addon postcondition.
    final = copy.deepcopy(selector)
    selector["owned_components"] = copy.deepcopy(before["owned_components"])
    receipt = owner._record(final, command_id, digest, action, manifest)
    selected_token = digest_bytes(canonical(selector) + b"\n")
    intent = addon.prepare(owner, project, files, final, selected_token, tree_before)
    _check_event(owner, stop_event)
    with _guard_control(owner):
        control = _control(owner)
        if control["stopped"]:
            cancelled = True
        else:
            row = {"schema": SCHEMA, "command_id": command_id, "request_digest": digest,
                   "before_state": expected, "selector_state": selector,
                   "selector_sha256": selected_token,
                   "final_sha256": digest_bytes(canonical(final) + b"\n"),
                   "release": selector["active"], "addon": intent}
            need(not _wal(owner).exists() and owner._state()[1] == expected, "lifecycle pending/CAS conflict")
            _write(_wal(owner), row)
            control["phase"] = "DRAINING"
            _save_control(owner, control)
            cancelled = False
    if cancelled:
        return _cancel(owner, before, command_id, digest, expected, action)
    _check_event(owner, stop_event)
    _finish(owner, row)
    return receipt


def install(owner, project: Path, package_path: Path, *, command_id: str,
            expected_state_sha256: str, stop_event=None) -> dict:
    verified = owner._verify_package(package_path)
    request = {"action": "lifecycle-install", "archive_sha256": verified["archive_sha256"],
               "release": verified["manifest_sha256"], "project": str(project), "target": owner.target}
    with mutation_guard(owner.root):
        state, digest, prior = owner._begin(command_id, request, expected_state_sha256)
        if prior is not None:
            return prior
        _admit(owner, command_id)
        if state["active"] is not None:
            owner._read_release(state["active"])
        identity = owner._stage(verified)
        _check_event(owner, stop_event)
        selected = copy.deepcopy(state)
        if selected["active"] != identity:
            selected["previous"], selected["active"] = selected["active"], identity
        return _execute(owner, project, command_id=command_id, digest=digest, before=state,
                        selector=selected, expected=expected_state_sha256, action="install",
                        manifest=verified["manifest"], stop_event=stop_event)


def rollback(owner, project: Path, destination: str, *, command_id: str,
             expected_state_sha256: str, stop_event=None) -> dict:
    request = {"action": "lifecycle-rollback", "destination": destination,
               "project": str(project), "target": owner.target}
    with mutation_guard(owner.root):
        state, digest, prior = owner._begin(command_id, request, expected_state_sha256)
        if prior is not None:
            return prior
        need(state["previous"] is not None and destination == state["previous"], "rollback is not last-good")
        manifest = owner._read_release(destination)
        _admit(owner, command_id)
        selected = copy.deepcopy(state)
        selected["active"], selected["previous"] = destination, None
        return _execute(owner, project, command_id=command_id, digest=digest, before=state,
                        selector=selected, expected=expected_state_sha256, action="rollback",
                        manifest=manifest, stop_event=stop_event)


def stop(owner, *, command_id: str = "lifecycle.stop") -> dict:
    owner._command_id(command_id)
    # This lock is independent of the root work lock: Stop can durably latch
    # while a worker is parked or performing filesystem I/O under that lock.
    with _guard_control(owner):
        state = _control(owner)
        prior = state["commands"].get(command_id)
        if prior is not None:
            need(prior["action"] == "stop", "control command_id conflict")
            return prior["receipt"]
        need(len(state["commands"]) < 8192, "lifecycle control journal full")
        state["stopped"] = True
        pending = _wal(owner).exists()
        state["phase"] = "DRAINING" if pending else "STOPPED" if state["active"] is None else "PREPARING"
        receipt = {"status": "DRAINING" if pending else "CANCEL_PENDING" if state["active"] else "STOPPED",
                "stopped": True, "durable": True, "draining": pending,
                "active_command_id": state["active"], "command_id": command_id}
        state["commands"][command_id] = {"action": "stop", "receipt": receipt}
        _save_control(owner, state)
        return receipt


def status(owner) -> dict:
    state = _control(owner)
    return {**state, "pending": _wal(owner).exists()}


def resume(owner, *, command_id: str = "lifecycle.resume") -> dict:
    owner._command_id(command_id)
    with mutation_guard(owner.root):
        recover(owner)
        with _guard_control(owner):
            state = _control(owner)
            prior = state["commands"].get(command_id)
            if prior is not None:
                need(prior["action"] == "resume", "control command_id conflict")
                return prior["receipt"]
            need(len(state["commands"]) < 8192, "lifecycle control journal full")
            state.update(stopped=False, active=None, phase="IDLE")
            receipt = {"status": "RESUMED", "stopped": False, "durable": True, "command_id": command_id}
            state["commands"][command_id] = {"action": "resume", "receipt": receipt}
            _save_control(owner, state)
            return receipt
