"""Seal S202 symbol-path diagnostic and its proven harness boundary failures."""
import hashlib
import json
import os
import re
import zipfile
from pathlib import Path

raw = Path(os.environ["S202_RAW"])
archive = Path(os.environ["S202_ARCHIVE"])
packet = Path(os.environ["S202_PACKET"])
packet.mkdir(parents=True, exist_ok=True)
archive.parent.mkdir(parents=True, exist_ok=True)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    data = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    return digest(path)


cdb_text = (raw / "cdb.stdout.txt").read_text(encoding="utf-8", errors="replace")
editor_text = (raw / "editor-host" / "stdout.txt").read_text(encoding="utf-8", errors="replace")
result = json.loads((raw / "result.json").read_text(encoding="utf-8"))
new_match = re.search(r"0x([0-9a-f]+) new stack traces", cdb_text, re.I)
displayed_match = re.search(r"Displayed 0x([0-9a-f]+) stack traces", cdb_text, re.I)
files = [
    {"path": path.relative_to(raw).as_posix(), "bytes": path.stat().st_size, "sha256": digest(path)}
    for path in sorted(raw.rglob("*"))
    if path.is_file() and path.name != "raw-manifest.json"
]
manifest_sha = write_json(
    raw / "raw-manifest.json",
    {
        "schema": "HH-GT06-S202-RAW-MANIFEST-1",
        "run_id": "gt06-s202-cdb-handle-snapshot-01",
        "authority": 0,
        "formal_acceptance": False,
        "terminal": "bounded_success_harness_boundary_failure",
        "files": files,
    },
)
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as handle:
    for path in sorted(raw.rglob("*")):
        if path.is_file():
            info = zipfile.ZipInfo(path.relative_to(raw).as_posix())
            info.date_time = (2026, 9, 24, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            handle.writestr(info, path.read_bytes())
archive_sha = digest(archive)
analysis = {
    "schema": "HH-GT06-S202-ANALYSIS-1",
    "run_id": "gt06-s202-cdb-handle-snapshot-01",
    "authority": 0,
    "formal_acceptance": False,
    "cdb_markers": result["cdb_markers"],
    "target_actual_exit": result["target_actual_exit"],
    "helper_exit": result["helper_exit"],
    "cdb_exit": result["cdb_exit"],
    "job": result["job"],
    "actual_native_completion_marker": "HH_S200_COMPLETE" in editor_text,
    "collector_native_completion_rows": len(result["native_completion"]),
    "htrace_new_stack_traces": int(new_match.group(1), 16) if new_match else None,
    "htrace_displayed_outstanding_traces": int(displayed_match.group(1), 16) if displayed_match else None,
    "symbol_path_rejected": "is not a valid store" in cdb_text,
    "harness_failures": [
        "relative symbol-store path was rejected by dbghelp",
        "copied runner expected HH_S202_COMPLETE while fixture emitted HH_S200_COMPLETE, so derived native_completion was empty",
    ],
    "conclusion": "S202 attached CDB, captured a handle snapshot and completed htrace, but its symbol-store path and completion-marker collector were invalid. Raw target exit and cleanup remain preserved; no creator stack, ownership, root cause or GT06 acceptance claim is made. A single bounded repair may fix only these proven harness boundaries.",
    "raw_manifest_sha256": manifest_sha,
    "archive_sha256": archive_sha,
}
analysis_sha = write_json(packet / "analysis.json", analysis)
(packet / "README.md").write_text(
    "# S202 symbol-path htrace diagnostic\n\n"
    "S202 used a fresh diagnostic ID to try Microsoft symbol resolution. The Godot target, helper and CDB exited 0 and the owned Job closed. "
    "The raw CDB output records the symbol-store rejection `not a valid store`; the copied runner also looked for `HH_S202_COMPLETE` while the fixture emitted `HH_S200_COMPLETE`, leaving its derived native-completion list empty. "
    "This package retains the raw evidence and is diagnostic-only. The timeout, baseline, profile, counter gate and GT06 acceptance contract remain unchanged.\n",
    encoding="utf-8",
)
readme_sha = digest(packet / "README.md")
seal_sha = write_json(
    packet / "terminal-seal.json",
    {
        "schema": "HH-GT06-S202-TERMINAL-SEAL-1",
        "run_id": "gt06-s202-cdb-handle-snapshot-01",
        "authority": 0,
        "formal_acceptance": False,
        "terminal": "bounded_success_harness_boundary_failure",
        "raw_manifest_sha256": manifest_sha,
        "archive_sha256": archive_sha,
        "verified_files": len(files) + 1,
        "target_actual_exit": 0,
        "helper_exit": 0,
        "cdb_exit": 0,
        "job_zero_closed": True,
        "symbol_path_valid": False,
        "collector_marker_valid": False,
        "formal_gate_unchanged": True,
    },
)
write_json(
    packet / "package-manifest.json",
    {
        "schema": "HH-GT06-S202-PACKAGE-MANIFEST-1",
        "run_id": "gt06-s202-cdb-handle-snapshot-01",
        "authority": 0,
        "formal_acceptance": False,
        "packet": "zdoc/reviews/20260924-gt06-s202-symbol-htrace",
        "README.md": readme_sha,
        "analysis.json": analysis_sha,
        "terminal-seal.json": seal_sha,
        "raw_manifest_sha256": manifest_sha,
        "archive_sha256": archive_sha,
        "decision": "Retain S202 harness failure; permit only one fresh S203 run after repairing the rejected symbol-store path and marker collector.",
    },
)
print(json.dumps({"raw_manifest_sha256": manifest_sha, "archive_sha256": archive_sha, "files": len(files) + 1}, indent=2))
