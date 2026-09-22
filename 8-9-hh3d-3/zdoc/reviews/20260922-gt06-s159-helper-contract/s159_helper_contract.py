"""Stricter process-free helper contract for a future S159 diagnostic."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


class ContractError(ValueError):
    pass


def closure_for(files: dict) -> str:
    raw = (json.dumps(files, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _safe(value: object) -> bool:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value or value.startswith("/"):
        return False
    return all(part not in ("", ".", "..") for part in value.split("/"))


def validate_helper_freeze(freeze: dict, *, child_script: str) -> dict:
    root = Path(freeze.get("helper_root", ""))
    files = freeze.get("helper_files")
    closure = freeze.get("helper_closure_sha256")
    if not root.is_absolute() or root.is_symlink() or not isinstance(files, dict) or not files:
        raise ContractError("S159_HELPER_PIN_MISSING")
    if not isinstance(closure, str) or len(closure) != 64 or closure != closure_for(files):
        raise ContractError("S159_HELPER_CLOSURE_MISMATCH")
    if not _safe(child_script) or child_script not in files:
        raise ContractError("S159_CHILD_SCRIPT_NOT_PINNED")
    root = root.resolve()
    for rel, digest in files.items():
        if not _safe(rel) or not isinstance(digest, str) or len(digest) != 64:
            raise ContractError("S159_HELPER_MAP_INVALID")
        path = (root / rel).resolve()
        if path == root or root not in path.parents or path.is_symlink() or not path.is_file():
            raise ContractError("S159_HELPER_PATH_INVALID")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != digest:
            raise ContractError("S159_HELPER_DRIFT")
    return {"helper_root": str(root), "child_script": child_script,
            "helper_closure_sha256": closure, "helper_files": dict(files)}


def validate_prefix_and_pid(summary: dict, child_target: dict, *, max_batches: int = 8) -> dict:
    rows = summary.get("screened_batches")
    if not isinstance(rows, list) or not rows or len(rows) > max_batches:
        raise ContractError("S159_PREFIX_BOUND")
    if [row.get("index") for row in rows if isinstance(row, dict)] != list(range(len(rows))):
        raise ContractError("S159_PREFIX_NOT_CONTIGUOUS")
    pid = summary.get("pid")
    actual = child_target.get("actual_target_exit") if isinstance(child_target, dict) else None
    if not isinstance(pid, int) or pid <= 0 or not isinstance(actual, dict) or actual.get("pid") != pid:
        raise ContractError("S159_TARGET_PID_NOT_BOUND")
    return {"prefix_count": len(rows), "target_pid": pid}
