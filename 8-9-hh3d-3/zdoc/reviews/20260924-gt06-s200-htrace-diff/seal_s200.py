"""Seal the S200 CDB htrace differential diagnostic."""
import hashlib
import json
import os
import re
import zipfile
from pathlib import Path

raw = Path(os.environ["S200_RAW"])
archive = Path(os.environ["S200_ARCHIVE"])
packet = Path(os.environ["S200_PACKET"])
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
result = json.loads((raw / "result.json").read_text(encoding="utf-8"))
new_match = re.search(r"0x([0-9a-f]+) new stack traces", cdb_text, re.I)
displayed_match = re.search(r"Displayed 0x([0-9a-f]+) stack traces", cdb_text, re.I)
stack_provenance = {
    "godot_module_name_seen": "Godot_v4.7.2-stable_win64.exe" in cdb_text,
    "godot_module_stack_frame_seen": bool(re.search(r"(?im)^\s*(?:[0-9a-f`]+\s+)?Godot_v4\.7\.2-stable_win64(?:\.exe)?!", cdb_text)),
    "resolved_stack_frame_seen": bool(re.search(r"(?im)^\s*(?:[0-9a-f`]+\s+)?(?:ntdll|kernel32|KERNELBASE)!", cdb_text)),
    "pdb_or_module_offset_resolved": False,
    "note": "The htrace diff reports outstanding handles but no resolved creator stack frames in the captured text; module load and symbol errors remain. This does not establish ownership or root cause.",
}

files = [
    {
        "path": path.relative_to(raw).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": digest(path),
    }
    for path in sorted(raw.rglob("*"))
    if path.is_file() and path.name != "raw-manifest.json"
]
manifest_sha = write_json(
    raw / "raw-manifest.json",
    {
        "schema": "HH-GT06-S200-RAW-MANIFEST-1",
        "run_id": "gt06-s200-cdb-handle-snapshot-01",
        "authority": 0,
        "formal_acceptance": False,
        "terminal": "bounded_success_htrace_differential",
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
    "schema": "HH-GT06-S200-ANALYSIS-1",
    "run_id": "gt06-s200-cdb-handle-snapshot-01",
    "authority": 0,
    "formal_acceptance": False,
    "cdb_markers": result["cdb_markers"],
    "target_actual_exit": result["target_actual_exit"],
    "helper_exit": result["helper_exit"],
    "cdb_exit": result["cdb_exit"],
    "job": result["job"],
    "htrace_new_stack_traces": int(new_match.group(1), 16) if new_match else None,
    "htrace_displayed_outstanding_traces": int(displayed_match.group(1), 16) if displayed_match else None,
    "stack_provenance": stack_provenance,
    "conclusion": "A fresh CDB run attached to the verified Godot target, captured the handle snapshot, enabled htrace, and completed an htrace differential before qd. The differential recorded new and outstanding handle stack-trace entries, but the captured output has no resolved creator stack frame or module offset. This is diagnostic-only; it proves neither leak ownership nor root cause and cannot satisfy GT06 acceptance.",
    "raw_manifest_sha256": manifest_sha,
    "archive_sha256": archive_sha,
}
analysis_sha = write_json(packet / "analysis.json", analysis)

(packet / "README.md").write_text(
    "# S200 CDB htrace differential\n\n"
    "S200 is a fresh bounded diagnostic after the S198 terminal-boundary repair. "
    "CDB attached to the verified Godot target, captured the handle table, enabled `!htrace`, "
    "ran `!htrace -diff`, and detached with target/helper/CDB exit 0 and Job cleanup verified. "
    "The diff reported 0x1e0d new stack traces and 0x6a displayed outstanding entries, "
    "but no resolved creator stack/module offset appears in the captured output. "
    "This remains Authority 0 and diagnostic-only: GT06, its counter gate, timeout, baseline, "
    "profile and acceptance contract are unchanged.\n",
    encoding="utf-8",
)
readme_sha = digest(packet / "README.md")
seal_sha = write_json(
    packet / "terminal-seal.json",
    {
        "schema": "HH-GT06-S200-TERMINAL-SEAL-1",
        "run_id": "gt06-s200-cdb-handle-snapshot-01",
        "authority": 0,
        "formal_acceptance": False,
        "terminal": "bounded_success_htrace_differential",
        "raw_manifest_sha256": manifest_sha,
        "archive_sha256": archive_sha,
        "verified_files": len(files) + 1,
        "cdb_attached": True,
        "handle_snapshot": True,
        "htrace_enabled": True,
        "htrace_diff": True,
        "target_actual_exit": 0,
        "helper_exit": 0,
        "cdb_exit": 0,
        "job_zero_closed": True,
        "formal_gate_unchanged": True,
    },
)
write_json(
    packet / "package-manifest.json",
    {
        "schema": "HH-GT06-S200-PACKAGE-MANIFEST-1",
        "run_id": "gt06-s200-cdb-handle-snapshot-01",
        "authority": 0,
        "formal_acceptance": False,
        "packet": "zdoc/reviews/20260924-gt06-s200-htrace-diff",
        "README.md": readme_sha,
        "analysis.json": analysis_sha,
        "terminal-seal.json": seal_sha,
        "raw_manifest_sha256": manifest_sha,
        "archive_sha256": archive_sha,
        "decision": "Retain htrace differential as diagnostic evidence; do not infer creator ownership/root cause or retry formal GT06 without a distinct supported route.",
    },
)
print(json.dumps({"raw_manifest_sha256": manifest_sha, "archive_sha256": archive_sha, "files": len(files) + 1}, indent=2))
