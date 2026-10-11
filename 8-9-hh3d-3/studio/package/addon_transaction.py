"""Recoverable addon replacement for cooperating installers.

The write-ahead record lives in the install root. Work directories are siblings
of the consumer project on the same volume. Backups are retained, never silently
deleted: recovery completes the recorded intent or stops on a conflicting edit.
This covers process death, not hostile filesystem writers or Windows power loss.
Callers hold the install guard; this module also serializes writers per project.
"""
from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import uuid

from .release_contract import canonical, digest_bytes, need, safe_path, strict_json
try:
    from build.bootstrap.install_toolchain import mutation_guard, sync_directory
except ModuleNotFoundError:
    from studio.build.bootstrap.install_toolchain import mutation_guard, sync_directory

MAX_WAL = 32 * 1024**2


def tree_bytes(root: Path) -> dict[str, bytes] | None:
    root = safe_path(root)
    if not root.exists():
        return None
    need(root.is_dir(), "addon tree is not a directory")
    result = {}
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs:
            safe_path(Path(directory) / name)
        for name in files:
            path = safe_path(Path(directory) / name)
            result[path.relative_to(root).as_posix()] = path.read_bytes()
    return result


def tree_hash(root: Path) -> str | None:
    return files_hash(tree_bytes(root))


def files_hash(files: dict[str, bytes] | None) -> str | None:
    if files is None:
        return None
    return digest_bytes(canonical({k: digest_bytes(v) for k, v in sorted(files.items())}))


def workspace(project: Path) -> Path:
    # Resolve lexical aliases/case before choosing the one project lock domain.
    identity = os.path.normcase(str(safe_path(project)))
    return safe_path(project.parent / (".hh-studio-addon-" + digest_bytes(identity.encode())[:24]))


@contextmanager
def project_guard(owner, project: Path):
    work = workspace(project)
    work.mkdir(parents=True, exist_ok=True)
    with mutation_guard(work):
        pin = safe_path(work / "owner.json")
        identity = {"install_root": os.path.normcase(str(owner.root)), "project": str(project)}
        if pin.exists():
            need(strict_json(pin.read_bytes()) == identity,
                 "addon project belongs to another install root; use its installer")
        else:
            write_file(pin, canonical(identity))
        yield work


def write_file(path: Path, data: bytes) -> None:
    path = safe_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def recover(owner) -> None:
    wal = safe_path(owner.root / ".addon-pending.json")
    if not wal.exists():
        return
    with wal.open("rb") as stream:
        raw = stream.read(MAX_WAL + 1)
    need(len(raw) <= MAX_WAL, "addon pending record too large")
    record = strict_json(raw)
    need(isinstance(record, dict) and set(record) == {
        "schema", "project", "txid", "before", "after", "expected_state", "state"
    } and record["schema"] == "hh-addon-transaction-1", "invalid addon pending record")
    txid = record["txid"]
    need(isinstance(txid, str) and len(txid) == 32 and all(c in "0123456789abcdef" for c in txid),
         "invalid addon transaction identity")
    project = safe_path(Path(record["project"]))
    need(project.is_dir(), "addon recovery project missing")
    with project_guard(owner, project) as work:
        finish(owner, record, work, wal)


def finish(owner, record: dict, work: Path, wal: Path) -> None:
    project = safe_path(Path(record["project"]))
    txdir = safe_path(work / record["txid"])
    stage, backup = safe_path(txdir / "stage"), safe_path(txdir / "backup")
    destination = safe_path(project / "addons/hh_studio")
    state, token = owner._state()
    after_raw = canonical(record["state"]) + b"\n"
    need(token in (record["expected_state"], digest_bytes(after_raw)), "addon recovery state conflict")
    if stage.exists():
        need(token == record["expected_state"], "addon state committed before tree replacement")
        need(tree_hash(stage) == record["after"], "addon stage changed; preserve and reconcile")
        if backup.exists():
            need(not destination.exists() and tree_hash(backup) == record["before"],
                 "addon backup/destination conflict")
        elif record["before"] is not None:
            need(tree_hash(destination) == record["before"], "addon owner edit before replacement")
            os.rename(destination, backup)
            sync_directory(destination.parent)
            sync_directory(txdir)
        else:
            need(not destination.exists(), "addon destination appeared")
        os.rename(stage, destination)
        sync_directory(destination.parent)
    need(tree_hash(destination) == record["after"], "addon readback conflict; preserve and reconcile")
    if record["before"] is not None:
        need(tree_hash(backup) == record["before"], "addon recovery backup changed")
    if token == record["expected_state"]:
        owner._publish(record["state"], token)
    need(owner._state()[1] == digest_bytes(after_raw), "addon journal readback indeterminate")
    # Backup is intentionally retained outside the consumer source tree.
    # Removing it would require a separate crash-safe, ownership-aware GC.
    wal.unlink()
    sync_directory(owner.root)


def replace(owner, project: Path, files: dict[str, bytes], state: dict, expected: str,
            command_id: str, digest: str, action: str, manifest: dict | None, expected_tree: str | None) -> dict:
    """Stage -> durable intent -> directory rename -> journal/readback -> ACK."""
    with project_guard(owner, project) as work:
        destination = safe_path(project / "addons/hh_studio")
        destination.parent.mkdir(parents=True, exist_ok=True)
        txid = uuid.uuid4().hex
        txdir = safe_path(work / txid)
        stage = safe_path(txdir / "stage")
        stage.mkdir(parents=True)
        before = tree_hash(destination)
        need(before == expected_tree, "addon owner edit before staging")
        for relative, data in files.items():
            target = safe_path(stage / relative)
            need(target.is_relative_to(stage), "addon stage path outside root")
            write_file(target, data)
        for directory, dirs, names in os.walk(stage, topdown=False):
            sync_directory(Path(directory))
        receipt = owner._record(state, command_id, digest, action, manifest)
        record = {"schema": "hh-addon-transaction-1", "project": str(project), "txid": txid,
                  "before": before, "after": tree_hash(stage), "expected_state": expected, "state": state}
        wal = safe_path(owner.root / ".addon-pending.json")
        need(not wal.exists() and owner._state()[1] == expected, "addon pending/CAS conflict")
        raw = canonical(record)
        need(len(raw) <= MAX_WAL, "addon transaction too large")
        temporary = safe_path(owner.root / (".addon-intent-" + txid + ".tmp"))
        write_file(temporary, raw)
        os.rename(temporary, wal)
        sync_directory(owner.root)
        finish(owner, record, work, wal)
        return receipt
