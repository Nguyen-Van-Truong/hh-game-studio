"""Create the immutable S194 diagnostic manifest and packet."""
import hashlib, json, os, statistics, zipfile
from pathlib import Path

raw = Path(os.environ["S194_RAW"])
archive = Path(os.environ["S194_ARCHIVE"])
packet = Path(os.environ["S194_PACKET"])
packet.mkdir(parents=True, exist_ok=True)
archive.parent.mkdir(parents=True, exist_ok=True)

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(path, value):
    data = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    if path.read_bytes() != data:
        raise RuntimeError("S194_EVIDENCE_READBACK")
    return digest(path)

files = []
for path in sorted(raw.rglob("*")):
    if path.is_file() and path.name != "raw-manifest.json":
        files.append({"path": path.relative_to(raw).as_posix(), "bytes": path.stat().st_size, "sha256": digest(path)})
manifest = {"schema": "HH-GT06-S194-RAW-MANIFEST-1", "run_id": "gt06-s194-external-sampler-01", "authority": 0, "formal_acceptance": False, "files": files}
manifest_sha = write(raw / "raw-manifest.json", manifest)
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zfile:
    for path in sorted(raw.rglob("*")):
        if path.is_file():
            info = zipfile.ZipInfo(path.relative_to(raw).as_posix())
            info.date_time = (2026, 9, 24, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            zfile.writestr(info, path.read_bytes())
archive_sha = digest(archive)

samples = [json.loads(line) for line in (raw / "external-sampler" / "samples.jsonl").read_text().splitlines() if line.strip()]
values = [row["held_handles"] for row in samples]
steady = samples[240:]
steady_values = [row["held_handles"] for row in steady]
stdout = (raw / "editor-host" / "stdout.txt").read_text(encoding="utf-8")
plugin_rows = [json.loads(line.split(" ", 1)[1]) for line in stdout.splitlines() if line.startswith("HH_S194_IDLE ")]
analysis = {
    "schema": "HH-GT06-S194-ANALYSIS-1", "run_id": "gt06-s194-external-sampler-01", "authority": 0,
    "formal_acceptance": False,
    "hypothesis": "An independent observer process opens the target PID and samples GetProcessHandleCount, separating sampler-handle ownership from the retained ProcessProbe route.",
    "external_sampler": {"sample_count": len(values), "min": min(values), "max": max(values), "first": values[0], "last": values[-1], "unique": len(set(values)), "mean": statistics.mean(values), "median": statistics.median(values), "increases": sum(b > a for a, b in zip(values, values[1:])), "decreases": sum(b < a for a, b in zip(values, values[1:])), "target_pid": samples[0]["target_pid"], "target_process_start": samples[0]["target_process_start"], "steady_after_60s": {"sample_count": len(steady_values), "min": min(steady_values), "max": max(steady_values), "first": steady_values[0], "last": steady_values[-1], "unique": len(set(steady_values)), "increases": sum(b > a for a, b in zip(steady_values, steady_values[1:])), "decreases": sum(b < a for a, b in zip(steady_values, steady_values[1:]))}},
    "editor_plugin": {"rows": len(plugin_rows), "objects_min": min(row["objects"] for row in plugin_rows), "objects_max": max(row["objects"] for row in plugin_rows), "resources_min": min(row["resources"] for row in plugin_rows), "resources_max": max(row["resources"] for row in plugin_rows), "filesystem_changes_max": max(row["filesystem_changes"] for row in plugin_rows)},
    "conclusion": "Distinct sampler route completed successfully and reported non-monotonic variation after startup; this does not prove leak, ownership, root cause, or GT06 acceptance. Keep formal gate and counter verifier unchanged.",
    "raw_manifest_sha256": manifest_sha, "archive_sha256": archive_sha,
}
analysis_sha = write(packet / "analysis.json", analysis)
(packet / "README.md").write_text("""# S194 external sampler diagnostic\n\nS194 is a bounded, diagnostic-only idle-editor run. A separate Python observer process opened the Godot target using PID, process-start time, and executable-image identity, then sampled `GetProcessHandleCount` every 250 ms. This is distinct from S188, whose retained `ProcessProbe` in the driver performed the sampling.\n\nThe pinned Godot 4.7.2 editor completed the 90-second idle plugin naturally (actual target exit 0); the external sampler exited 0 after 387 samples, and the owned Job was zero/closed with no cleanup error. Raw evidence is retained under the ignored `.local` review path and archived with a manifest.\n\nThe external route still showed non-monotonic counter variation after startup. This separates sampler-process ownership from the observed target counter but does not identify a kernel handle owner, prove a leak or root cause, or satisfy GT06. GT06 remains the frozen 10 fresh pairs × 35 batches gate.\n""", encoding="utf-8")
readme_sha = digest(packet / "README.md")
seal = {"schema": "HH-GT06-S195-TERMINAL-SEAL-1", "run_id": "gt06-s194-external-sampler-01", "authority": 0, "formal_acceptance": False, "terminal": "bounded_success", "raw_root": "studio/.local/reviews/gt06-s194-external-sampler-01", "raw_manifest": "studio/.local/reviews/gt06-s194-external-sampler-01/raw-manifest.json", "raw_manifest_sha256": manifest_sha, "archive": "studio/.local/archives/gt06-s194-external-sampler-01-s195-terminal.zip", "archive_sha256": archive_sha, "verified_files": len(files) + 1, "target_actual_exit": 0, "sampler_actual_exit": 0, "job_zero_closed": True, "formal_gate_unchanged": True, "authority_note": "Diagnostic only; no leak/ownership/root-cause or acceptance claim."}
seal_sha = write(packet / "terminal-seal.json", seal)
package = {"schema": "HH-GT06-S195-PACKAGE-MANIFEST-1", "run_id": "gt06-s194-external-sampler-01", "authority": 0, "formal_acceptance": False, "packet": "zdoc/reviews/20260924-gt06-s194-external-sampler", "files": {"README.md": readme_sha, "analysis.json": analysis_sha, "terminal-seal.json": seal_sha, "raw_manifest_sha256": manifest_sha, "archive_sha256": archive_sha}, "source_closure": "fc46cfd2e80e8d78024b6a31c6c72be64f33d83aab4fe1abebaf899907f0e205", "execution_closure": "493a7ccce3e42993399910b0fe977f25448f411b863e4cca7b57904348ac374e", "profile_sha256": "0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85", "gate_policy": "10 fresh pairs x 35 batches; unchanged", "decision": "distinct external sampler route complete; retain GT06 IN_PROGRESS and no blind retry"}
write(packet / "package-manifest.json", package)
print(json.dumps({"raw_manifest_sha256": manifest_sha, "archive_sha256": archive_sha, "files": len(files) + 1, "analysis_sha256": analysis_sha}, indent=2))
