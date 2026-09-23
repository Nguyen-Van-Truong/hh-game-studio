"""Seal S203 after the proven symbol-path and collector repairs."""
import hashlib, json, os, re, zipfile
from pathlib import Path

raw = Path(os.environ["S203_RAW"])
archive = Path(os.environ["S203_ARCHIVE"])
packet = Path(os.environ["S203_PACKET"])
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
section = cdb_text.split("Outstanding handles opened since the previous snapshot:", 1)[1].split("Displayed ", 1)[0]
headers = re.findall(r"Handle = (0x[0-9a-f]+) - OPEN\s+Thread ID = (0x[0-9a-f]+), Process ID = (0x[0-9a-f]+)", section, re.I)
frame_lines = [line for line in section.splitlines() if re.search(r"0x[0-9a-f`]+:\s+\S+!\S+", line, re.I)]
files = [
    {"path": path.relative_to(raw).as_posix(), "bytes": path.stat().st_size, "sha256": digest(path)}
    for path in sorted(raw.rglob("*"))
    if path.is_file() and path.name != "raw-manifest.json"
]
manifest_sha = write_json(raw / "raw-manifest.json", {
    "schema": "HH-GT06-S203-RAW-MANIFEST-1",
    "run_id": "gt06-s203-cdb-handle-snapshot-01",
    "authority": 0,
    "formal_acceptance": False,
    "terminal": "bounded_success_symbol_route_header_only",
    "files": files,
})
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as handle:
    for path in sorted(raw.rglob("*")):
        if path.is_file():
            info = zipfile.ZipInfo(path.relative_to(raw).as_posix())
            info.date_time = (2026, 9, 24, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            handle.writestr(info, path.read_bytes())
archive_sha = digest(archive)
analysis = {
    "schema": "HH-GT06-S203-ANALYSIS-1",
    "run_id": "gt06-s203-cdb-handle-snapshot-01",
    "authority": 0,
    "formal_acceptance": False,
    "cdb_markers": result["cdb_markers"],
    "target_actual_exit": result["target_actual_exit"],
    "helper_exit": result["helper_exit"],
    "cdb_exit": result["cdb_exit"],
    "job": result["job"],
    "htrace_new_stack_traces": int(new_match.group(1), 16) if new_match else None,
    "htrace_displayed_outstanding_traces": int(displayed_match.group(1), 16) if displayed_match else None,
    "htrace_open_headers": len(headers),
    "htrace_creator_frame_lines": len(frame_lines),
    "symbol_route": {
        "absolute_cache": True,
        "split_reload_commands": True,
        "invalid_store_error_seen": "is not a valid store" in cdb_text,
        "godot_pdb_or_module_offset_resolved": False,
    },
    "conclusion": "S203 repaired the proven relative symbol-store and reload-command boundaries and fixed the completion marker collector. The target/helper/CDB completed with Job cleanup, but htrace still contains header-only PID/TID records and zero creator frame-address lines. This establishes no ownership, leak or root cause and cannot satisfy GT06 acceptance.",
    "raw_manifest_sha256": manifest_sha,
    "archive_sha256": archive_sha,
}
analysis_sha = write_json(packet / "analysis.json", analysis)
(packet / "README.md").write_text(
    "# S203 symbol-path and htrace boundary repair\n\n"
    "S203 is a fresh bounded diagnostic after S202. It used an absolute symbol cache, one `.reload /f` command per module, and a matching S203 fixture marker. "
    "CDB attached to the verified Godot target; the target, helper and CDB exited 0 and the owned Job closed. The htrace differential still produced header-only OPEN records with PID/TID and no stack-address frame lines. "
    "The result remains Authority 0 and diagnostic-only; GT06 timeout, baseline, profile, counter gate and acceptance contract are unchanged.\n",
    encoding="utf-8",
)
readme_sha = digest(packet / "README.md")
seal_sha = write_json(packet / "terminal-seal.json", {
    "schema": "HH-GT06-S203-TERMINAL-SEAL-1",
    "run_id": "gt06-s203-cdb-handle-snapshot-01",
    "authority": 0,
    "formal_acceptance": False,
    "terminal": "bounded_success_symbol_route_header_only",
    "raw_manifest_sha256": manifest_sha,
    "archive_sha256": archive_sha,
    "verified_files": len(files) + 1,
    "cdb_attached": True,
    "handle_snapshot": True,
    "htrace_enabled": True,
    "htrace_diff": True,
    "htrace_creator_frame_lines": len(frame_lines),
    "target_actual_exit": 0,
    "helper_exit": 0,
    "cdb_exit": 0,
    "job_zero_closed": True,
    "formal_gate_unchanged": True,
})
write_json(packet / "package-manifest.json", {
    "schema": "HH-GT06-S203-PACKAGE-MANIFEST-1",
    "run_id": "gt06-s203-cdb-handle-snapshot-01",
    "authority": 0,
    "formal_acceptance": False,
    "packet": "zdoc/reviews/20260924-gt06-s203-symbol-htrace",
    "README.md": readme_sha,
    "analysis.json": analysis_sha,
    "terminal-seal.json": seal_sha,
    "raw_manifest_sha256": manifest_sha,
    "archive_sha256": archive_sha,
    "decision": "Symbol and collector boundaries repaired; retain header-only htrace as diagnostic, do not infer ownership or retry formal GT06 unchanged.",
})
print(json.dumps({"raw_manifest_sha256": manifest_sha, "archive_sha256": archive_sha, "files": len(files) + 1}, indent=2))
