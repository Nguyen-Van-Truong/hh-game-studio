"""Small, process-free contract layer for a future S158 diagnostic helper.

The S157 candidate remains immutable.  A future runner may compose these
checks before spawning anything; this module intentionally has no process or
Godot imports.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


class ContractError(ValueError):
    pass


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative(value: object) -> bool:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value or value.startswith("/"):
        return False
    parts = value.split("/")
    return all(part not in ("", ".", "..") for part in parts)


def validate_helper_pin(freeze: dict, *, child_script: str) -> dict:
    """Require the exact helper bytes used by a future launch.

    S157 only pins the original execution map.  This contract additionally
    requires a helper-root map and a declared child script within that map.
    """
    root = Path(freeze.get("helper_root", ""))
    files = freeze.get("helper_files")
    declared = freeze.get("child_script")
    if not root.is_absolute() or not isinstance(files, dict) or not files:
        raise ContractError("S158_HELPER_PIN_MISSING")
    if declared != child_script or child_script not in files:
        raise ContractError("S158_CHILD_SCRIPT_NOT_PINNED")
    for relative, digest in files.items():
        if not _safe_relative(relative) or not isinstance(digest, str) or len(digest) != 64:
            raise ContractError("S158_HELPER_MAP_INVALID")
        path = (root / relative).resolve()
        if root.resolve() not in path.parents and path != root.resolve():
            raise ContractError("S158_HELPER_TRAVERSAL")
        if not path.is_file() or _hash(path) != digest:
            raise ContractError("S158_HELPER_DRIFT")
    return {"helper_root": str(root.resolve()), "child_script": child_script,
            "helper_files": dict(files)}


def validate_boundary_binding(summary: dict, child_target: dict) -> dict:
    """Bind a diagnostic boundary to a real prefix and target PID."""
    rows = summary.get("screened_batches")
    if not isinstance(rows, list) or not rows:
        raise ContractError("S158_PREFIX_MISSING")
    indexes = [row.get("index") for row in rows if isinstance(row, dict)]
    if len(indexes) != len(rows) or indexes != list(range(len(rows))):
        raise ContractError("S158_PREFIX_NOT_CONTIGUOUS")
    pid = summary.get("pid")
    actual = child_target.get("actual_target_exit") if isinstance(child_target, dict) else None
    if not isinstance(pid, int) or pid <= 0 or not isinstance(actual, dict) or actual.get("pid") != pid:
        raise ContractError("S158_TARGET_PID_NOT_BOUND")
    return {"prefix_count": len(rows), "target_pid": pid}


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ContractError("S158_JSON_OBJECT_REQUIRED")
    return value
