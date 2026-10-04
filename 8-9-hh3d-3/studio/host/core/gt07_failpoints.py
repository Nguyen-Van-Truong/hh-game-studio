"""Opt-in GT07 publication failpoints.

Failpoints are diagnostic controls only, disabled by absence. The crash harness
arms a bounded file in its private .local root, waits for the reached receipt,
then terminates the owned process blocked at that phase. An exception caught by
an adapter is not a process-crash proof. Production/release admission must call
assert_disabled; wiring the hook and release scanner is separate integration.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import time

PHASES = frozenset({"PREPARED", "VALIDATED", "ACTIVATING", "COMMITTED",
                    "RELOAD", "ACK"})
_SCHEMA = "HH-GT07-FAILPOINT-1"


class FailpointTimeout(RuntimeError):
    """Harness did not kill at the phase; never continue the effect as PASS."""


def config_path(root: Path) -> Path:
    return Path(root).absolute() / ".local" / "gt07-failpoint.json"


def runtime_root(default: Path) -> Path:
    """Resolve the private diagnostic root selected by the native harness.

    The environment override is accepted only as an absolute path.  Release
    callers that do not opt into the harness stay bound to the product's own
    root, and a malformed override fails closed before any publication phase.
    """
    raw = os.environ.get("HH_GT07_FAILPOINT_ROOT")
    if raw is None or raw == "":
        return Path(default).absolute()
    path = Path(raw).expanduser()
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("GT07_FAILPOINT_ROOT_UNSAFE")
    return path.absolute()


def _read(root: Path) -> dict | None:
    path = config_path(root)
    for parent in (path.parent, *path.parent.parents):
        if parent.is_symlink() or (parent.exists() and getattr(parent.lstat(), "st_file_attributes", 0) & 0x400):
            raise ValueError("GT07_FAILPOINT_UNSAFE_CONFIG")
    if not path.exists():
        return None
    info = path.lstat()
    if (stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or getattr(info, "st_file_attributes", 0) & 0x400):
        raise ValueError("GT07_FAILPOINT_UNSAFE_CONFIG")
    if info.st_size > 4096:
        raise ValueError("GT07_FAILPOINT_CONFIG_TOO_LARGE")
    value = json.loads(path.read_bytes())
    if type(value) is not dict or value.get("schema") != _SCHEMA:
        raise ValueError("GT07_FAILPOINT_SCHEMA")
    if type(value.get("enabled")) is not bool:
        raise ValueError("GT07_FAILPOINT_INVALID")
    if value["enabled"] is False:
        return None
    if (set(value) != {"schema", "enabled", "phase", "action", "run_id", "wait_seconds"}
            or value.get("phase") not in PHASES or value.get("action") != "pause"
            or type(value.get("run_id")) is not str or not value["run_id"]
            or len(value["run_id"]) > 128
            or type(value.get("wait_seconds")) is not int or not 1 <= value["wait_seconds"] <= 300):
        raise ValueError("GT07_FAILPOINT_INVALID")
    return value


def assert_disabled(root: Path) -> None:
    """Reject a native or final-package admission while a failpoint is armed."""
    if _read(root) is not None:
        raise ValueError("GT07_FAILPOINT_ENABLED")


def hit(root: Path, phase: str) -> None:
    """Apply the configured diagnostic action at one adapter phase.

    Writes one reached receipt before waiting for the harness to terminate the
    owned process. Timeout raises; it never silently resumes publication.
    """
    if phase not in PHASES:
        raise ValueError("GT07_FAILPOINT_PHASE")
    value = _read(root)
    if value is None or value["phase"] != phase:
        return
    receipt = config_path(root).with_name("gt07-failpoint-reached.json")
    with receipt.open("x", encoding="utf-8") as stream:
        json.dump({"schema": "HH-GT07-FAILPOINT-REACHED-1", "run_id": value["run_id"],
                   "phase": phase, "pid": os.getpid(), "monotonic_ns": time.monotonic_ns()}, stream)
        stream.flush()
        os.fsync(stream.fileno())
    deadline = time.monotonic() + value["wait_seconds"]
    while time.monotonic() < deadline:
        time.sleep(0.25)
    raise FailpointTimeout("GT07_FAILPOINT_NOT_TERMINATED_" + phase)
