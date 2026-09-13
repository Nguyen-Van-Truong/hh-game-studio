"""Fail-closed verifier for the GT-01 frozen source/runtime package.

This verifier is deliberately read-only.  It does not run Godot, Blender, or
the installer.  A package is eligible for critic review only when the source
closure on disk, the official run evidence, and every referenced log agree on
one independently computed closure hash.  ``CANDIDATE`` runtime evidence is
rejected: it is useful diagnostic material, never acceptance evidence.
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
ROOT_PREFIX = "8-9-hh3d-3/"


class VerificationError(ValueError):
    pass


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise VerificationError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs)
    except (OSError, UnicodeError, json.JSONDecodeError, VerificationError) as exc:
        raise VerificationError(f"invalid JSON {path.name}: {type(exc).__name__}") from exc
    if not isinstance(value, dict):
        raise VerificationError(f"JSON root is not an object: {path.name}")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalise(rel: str) -> str:
    if not isinstance(rel, str) or not rel or "\\" in rel or not SAFE_REL.fullmatch(rel):
        raise VerificationError("unsafe source path")
    rel = rel.lstrip("./")
    if rel.startswith(ROOT_PREFIX):
        rel = rel[len(ROOT_PREFIX):]
    parts = rel.split("/")
    if not parts or any(part in ("", ".", "..") for part in parts):
        raise VerificationError("traversal in source path")
    return "/".join(parts)


def _closure_records(manifest: dict[str, Any]) -> dict[str, str]:
    records = manifest.get("required_files")
    if not isinstance(records, list) or not records:
        raise VerificationError("required_files is missing or empty")
    result: dict[str, str] = {}
    for record in records:
        if not isinstance(record, dict):
            raise VerificationError("malformed required file record")
        rel = _normalise(record.get("path"))
        digest = record.get("sha256")
        if not isinstance(digest, str) or not HEX64.fullmatch(digest):
            raise VerificationError(f"invalid source hash: {rel}")
        if record.get("required") is not True or record.get("exists") is not True:
            raise VerificationError(f"source record is not present/required: {rel}")
        if record.get("regular") is not True or record.get("symlink") or record.get("reparse"):
            raise VerificationError(f"unsafe source identity: {rel}")
        if int(record.get("hard_links", 0)) != 1:
            raise VerificationError(f"unexpected hard-link count: {rel}")
        if rel in result:
            raise VerificationError(f"duplicate source path: {rel}")
        result[rel] = digest
    return result


def closure_hash(records: dict[str, str]) -> str:
    canonical = "".join(f"{path}\0{records[path]}\n" for path in sorted(records))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _safe_under(root: Path, rel: str) -> Path:
    candidate = (root / Path(rel)).resolve(strict=False)
    root = root.resolve(strict=True)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise VerificationError("path escapes repository root") from exc
    return candidate


def _check_source_on_disk(repo_root: Path, records: dict[str, str]) -> None:
    for rel, expected in records.items():
        path = _safe_under(repo_root, rel)
        try:
            info = os.lstat(path)
        except OSError as exc:
            raise VerificationError(f"missing source file: {rel}") from exc
        if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode) or int(info.st_nlink) != 1:
            raise VerificationError(f"unsafe source file: {rel}")
        if sha256(path) != expected:
            raise VerificationError(f"source hash mismatch: {rel}")


def _log_path(evidence_path: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value or "\\" in value or Path(value).is_absolute():
        raise VerificationError("unsafe log reference")
    path = (evidence_path.parent / value).resolve(strict=False)
    try:
        path.relative_to(evidence_path.parent.resolve(strict=True))
    except ValueError as exc:
        raise VerificationError("log reference escapes evidence directory") from exc
    return path


def _check_logs(evidence_path: Path, evidence: dict[str, Any]) -> None:
    runs = evidence.get("runs")
    hashes = evidence.get("log_hashes")
    if not isinstance(runs, list) or not runs or not isinstance(hashes, dict):
        raise VerificationError("runs/log_hashes are missing")
    for index, run in enumerate(runs):
        if not isinstance(run, dict):
            raise VerificationError(f"malformed run {index}")
        if run.get("exit_code") != 0 or run.get("wrapper_exit_code") != 0 or run.get("timed_out") is not False:
            raise VerificationError(f"run {index} did not exit cleanly")
        if run.get("tree_verified") is not True or run.get("ownership") != "gated_job_kill_on_close":
            raise VerificationError(f"run {index} has unverified process ownership")
        for stream in ("stdout", "stderr"):
            rel = run.get(stream)
            path = _log_path(evidence_path, rel)
            if not path.is_file():
                raise VerificationError(f"missing {stream} log for run {index}")
            key = str(rel).replace("\\", "/")
            expected = hashes.get(key)
            if not isinstance(expected, str) or not HEX64.fullmatch(expected) or sha256(path) != expected:
                raise VerificationError(f"stale or unbound {stream} log for run {index}")
            text = path.read_text(encoding="utf-8")
            if re.search(r"(?im)^\s*(?:warning|error)\s*[:)]", text):
                raise VerificationError(f"warning/error in {stream} log for run {index}")


def verify(source_manifest_path: Path, evidence_path: Path, repo_root: Path) -> dict[str, Any]:
    failures: list[str] = []
    try:
        manifest = load_json(source_manifest_path)
        evidence = load_json(evidence_path)
        if manifest.get("status") == "GAP" or manifest.get("gaps") not in ([], None):
            raise VerificationError("source closure reports gaps")
        records = _closure_records(manifest)
        _check_source_on_disk(repo_root, records)
        source_hash = closure_hash(records)
        if evidence.get("source_closure_sha256") != source_hash:
            raise VerificationError("evidence is not bound to computed source closure hash")
        bound = evidence.get("source_manifest")
        if not isinstance(bound, dict):
            raise VerificationError("evidence source_manifest is missing")
        for rel, digest in records.items():
            if bound.get(rel) != digest and bound.get(ROOT_PREFIX + rel) != digest:
                raise VerificationError(f"evidence source hash missing/mismatched: {rel}")
        if evidence.get("status") not in ("OFFICIAL", "ACCEPTED"):
            raise VerificationError("runtime evidence is not official/accepted")
        checks = evidence.get("checks")
        if not isinstance(checks, dict) or not checks or not all(value is True for value in checks.values()):
            raise VerificationError("runtime checks are incomplete or failed")
        _check_logs(evidence_path, evidence)
        traces = evidence.get("trace_lines")
        if not isinstance(traces, list) or len(traces) != 1 or '"result":"PASS"' not in traces[0]:
            raise VerificationError("trace evidence is missing or duplicated")
    except VerificationError as exc:
        failures.append(str(exc))
    result = {
        "schema": "HH3D-GT01-FREEZE-PACKAGE-1",
        "status": "READY_FOR_CRITIC" if not failures else "GAP",
        "source_closure_sha256": (closure_hash(_closure_records(load_json(source_manifest_path))) if not failures else None),
        "failures": failures,
        "evidence_status": evidence.get("status") if "evidence" in locals() else None,
        "limits": ["read-only verifier; two independent critics and coordinator acceptance remain required"],
    }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-manifest", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = verify(args.source_manifest, args.evidence, args.repo_root)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["status"] == "READY_FOR_CRITIC" else 2


if __name__ == "__main__":
    raise SystemExit(main())
