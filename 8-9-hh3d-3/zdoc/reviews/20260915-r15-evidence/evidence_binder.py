"""Fail-closed binder for one frozen GT-01 source closure and runner output.

The binder never launches a process and never trusts a runner supplied closure
hash or exit summary.  It recomputes every source and log digest, then emits a
small review report.  ``READY_FOR_CRITIC`` is only eligibility; it is not WP
acceptance and still needs two independent critics and coordinator sign-off.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Any

HEX64 = re.compile(r"^[0-9a-f]{64}$")
SAFE_REL = re.compile(r"^[A-Za-z0-9._/-]+$")


class BindError(ValueError):
    pass


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise BindError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs)
    except (OSError, UnicodeError, json.JSONDecodeError, BindError) as exc:
        raise BindError(f"invalid JSON: {path.name}") from exc
    if not isinstance(value, dict):
        raise BindError(f"JSON root is not object: {path.name}")
    return value


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _rel(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value or not SAFE_REL.fullmatch(value):
        raise BindError("unsafe relative path")
    parts = value.lstrip("./").split("/")
    if not parts or any(part in ("", ".", "..") for part in parts):
        raise BindError("path traversal")
    return "/".join(parts)


def _records(manifest: dict[str, Any]) -> dict[str, str]:
    rows = manifest.get("required_files")
    if manifest.get("status") == "GAP" or manifest.get("gaps") not in (None, []):
        raise BindError("source manifest contains gaps")
    if not isinstance(rows, list) or not rows:
        raise BindError("required_files missing or empty")
    result: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise BindError("malformed source record")
        rel = _rel(row.get("path"))
        digest = row.get("sha256")
        if not isinstance(digest, str) or not HEX64.fullmatch(digest):
            raise BindError(f"invalid source digest: {rel}")
        if row.get("required") is not True or row.get("exists") is not True:
            raise BindError(f"source is not present/required: {rel}")
        if row.get("regular") is not True or row.get("symlink") or row.get("reparse"):
            raise BindError(f"unsafe source identity: {rel}")
        if row.get("hard_links") != 1:
            raise BindError(f"unexpected hard-link count: {rel}")
        if rel in result:
            raise BindError(f"duplicate source path: {rel}")
        result[rel] = digest
    return result


def closure_sha256(records: dict[str, str]) -> str:
    canonical = "".join(f"{path}\0{records[path]}\n" for path in sorted(records))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _under(root: Path, rel: str) -> Path:
    root = root.resolve(strict=True)
    path = (root / Path(rel)).resolve(strict=False)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise BindError("source path escapes repo root") from exc
    return path


def _check_disk(repo_root: Path, records: dict[str, str]) -> None:
    for rel, expected in records.items():
        path = _under(repo_root, rel)
        try:
            info = os.lstat(path)
        except OSError as exc:
            raise BindError(f"missing source: {rel}") from exc
        if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode) or info.st_nlink != 1:
            raise BindError(f"unsafe source file: {rel}")
        if _sha(path) != expected:
            raise BindError(f"source digest mismatch: {rel}")


def _log_path(evidence_path: Path, value: Any) -> Path:
    rel = _rel(value)
    path = (evidence_path.parent / Path(rel)).resolve(strict=False)
    try:
        path.relative_to(evidence_path.parent.resolve(strict=True))
    except ValueError as exc:
        raise BindError("log path escapes evidence directory") from exc
    return path


def _check_runs(evidence_path: Path, evidence: dict[str, Any]) -> None:
    runs, hashes = evidence.get("runs"), evidence.get("log_hashes")
    if not isinstance(runs, list) or not runs or not isinstance(hashes, dict):
        raise BindError("runs/log_hashes missing")
    for i, run in enumerate(runs):
        if not isinstance(run, dict):
            raise BindError(f"malformed run {i}")
        if (not isinstance(run.get("wrapper_pid"), int) or run.get("wrapper_pid") <= 0
                or not isinstance(run.get("target_pid"), int) or run.get("target_pid") <= 0
                or not isinstance(run.get("started_at"), str) or not run.get("started_at")
                or not isinstance(run.get("argv"), list) or not run.get("argv")
                or not all(isinstance(arg, str) and arg for arg in run["argv"])):
            raise BindError(f"run {i} lacks host-captured identity/argv")
        if run.get("exit_code") != 0 or run.get("wrapper_exit_code") != 0 or run.get("timed_out") is not False:
            raise BindError(f"run {i} did not exit cleanly")
        if run.get("tree_verified") is not True or run.get("ownership") != "gated_job_kill_on_close":
            raise BindError(f"run {i} process tree is unverified")
        for stream in ("stdout", "stderr"):
            rel = _rel(run.get(stream))
            path = _log_path(evidence_path, rel)
            if not path.is_file():
                raise BindError(f"missing {stream} log for run {i}")
            expected = hashes.get(rel)
            if not isinstance(expected, str) or not HEX64.fullmatch(expected) or _sha(path) != expected:
                raise BindError(f"stale/unbound {stream} log for run {i}")
            text = path.read_text(encoding="utf-8")
            if re.search(r"(?im)^\s*(?:warning|error)\s*[:)]", text):
                raise BindError(f"warning/error in {stream} log for run {i}")


def _check_trace(evidence: dict[str, Any]) -> None:
    traces = evidence.get("trace_lines")
    if not isinstance(traces, list) or len(traces) != 1 or not isinstance(traces[0], str):
        raise BindError("trace must contain exactly one line")
    line = traces[0]
    if not line.startswith("GT01_TRACE "):
        raise BindError("trace prefix missing")
    try:
        data = json.loads(line.removeprefix("GT01_TRACE "), object_pairs_hook=_pairs)
    except (json.JSONDecodeError, BindError) as exc:
        raise BindError("trace JSON invalid or duplicated") from exc
    if not isinstance(data, dict) or data.get("result") != "PASS" or data.get("phase") != "QUITTING":
        raise BindError("trace is not a passing quit trace")
    observations = data.get("observations")
    labels = [x.get("label") for x in observations] if isinstance(observations, list) and all(isinstance(x, dict) for x in observations) else []
    if labels != ["menu", "start", "moved", "paused_frozen", "resumed", "quitting"]:
        raise BindError("trace observations are incomplete/out of order")


def bind(source_manifest: Path, runner_output: Path, repo_root: Path) -> dict[str, Any]:
    failures: list[str] = []
    source_hash: str | None = None
    run_id = command_id = None
    try:
        manifest = load_json(source_manifest)
        evidence = load_json(runner_output)
        records = _records(manifest)
        _check_disk(repo_root, records)
        source_hash = closure_sha256(records)
        run_id, command_id = evidence.get("run_id"), evidence.get("command_id")
        if evidence.get("status") not in ("OFFICIAL", "ACCEPTED"):
            raise BindError("runner output is candidate/diagnostic, not official")
        bound = evidence.get("source_manifest")
        if not isinstance(bound, dict):
            raise BindError("runner source_manifest missing")
        for rel, digest in records.items():
            if bound.get(rel) != digest and bound.get("8-9-hh3d-3/" + rel) != digest:
                raise BindError(f"runner source binding missing: {rel}")
        checks = evidence.get("checks")
        if not isinstance(checks, dict) or not checks or not all(value is True for value in checks.values()):
            raise BindError("runtime checks incomplete/failed")
        _check_runs(runner_output, evidence)
        _check_trace(evidence)
    except BindError as exc:
        failures.append(str(exc))
    return {"schema": "HH3D-GT01-EVIDENCE-BINDER-1", "status": "READY_FOR_CRITIC" if not failures else "GAP", "run_id": run_id, "command_id": command_id, "source_closure_sha256": source_hash if not failures else None, "failures": failures, "limits": ["Binder is read-only; READY_FOR_CRITIC is not WP acceptance; two independent critics and coordinator sign-off remain required"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-manifest", required=True, type=Path)
    parser.add_argument("--runner-output", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    result = bind(args.source_manifest, args.runner_output, args.repo_root)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "READY_FOR_CRITIC" else 2


if __name__ == "__main__":
    raise SystemExit(main())
