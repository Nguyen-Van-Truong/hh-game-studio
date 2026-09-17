"""Read-only S73 inputs; write only this bounded failure-evidence directory."""
from __future__ import annotations

import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
CAMPAIGN = ROOT / "studio/.local/reviews/gt06-s73-campaign-01"
SUPERVISOR = CAMPAIGN.with_name(CAMPAIGN.name + "-supervisor")
ATTEMPT = CAMPAIGN / "run-00-attempt-01"
PWSH = r"C:\Users\truon\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe"


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write(name, value):
    target = OUT / name
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = value if isinstance(value, bytes) else (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()
    with target.open("xb") as stream:
        stream.write(raw)


def read(path):
    return json.loads(path.read_bytes())


def capture(name, argv):
    original = name
    suffix = 2
    while (OUT / (name + ".capture.json")).exists():
        name = original + f"-retry-{suffix:02d}"
        suffix += 1
    started = utc()
    result = subprocess.run(argv, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45)
    write(name + ".stdout.txt", result.stdout)
    write(name + ".stderr.txt", result.stderr)
    write(name + ".capture.json", {
        "argv": argv, "cwd": str(ROOT), "started_utc": started,
        "finished_utc": utc(), "returncode": result.returncode,
        "scope": "read-only observation; not a native target exit receipt",
        "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(result.stderr).hexdigest(),
    })
    if result.returncode:
        raise RuntimeError(f"observation failed: {name}")
    return result.stdout


def inventory(base):
    rows = []
    for path in sorted(base.rglob("*")):
        if path.is_symlink():
            raise RuntimeError(f"unexpected symlink: {path}")
        if path.is_file():
            before = path.stat()
            value = digest(path)
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise RuntimeError(f"raw input changed: {path}")
            rows.append({"path": path.relative_to(base).as_posix(), "bytes": after.st_size,
                         "sha256": value, "mtime_ns": after.st_mtime_ns})
    return rows


started = utc()
baseline = capture("observations/git-head", ["git", "rev-parse", "HEAD"]).decode().strip()
capture("observations/tracked-status", ["git", "status", "--porcelain=v1", "--untracked-files=no"])
launcher = ROOT / "studio/tests/replay/campaign_task.ps1"
launcher_digest = digest(launcher)
scheduler = json.loads(capture("observations/scheduler-terminal", [PWSH, "-NoProfile",
    "-ExecutionPolicy", "Bypass", "-File", str(launcher), "-Command", "status",
    "-CampaignId", CAMPAIGN.name, "-LaunchNumber", "1"]))
processes = json.loads(capture("observations/processes", [PWSH, "-NoProfile", "-Command",
    "$items = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'Godot|Blender|python' } | "
    "Select-Object ProcessId,ParentProcessId,Name); ConvertTo-Json -InputObject $items -Depth 4"]))

raw = {"campaign": inventory(CAMPAIGN), "supervisor": inventory(SUPERVISOR)}
write("raw-locator-hashmaps.json", {"created_utc": utc(), "algorithm": "sha256",
    "scope": "Complete file inventory of the two named raw roots, including caches; bytes remain in the raw roots. No raw files excluded.",
    "roots": {"campaign": str(CAMPAIGN), "supervisor": str(SUPERVISOR)},
    "files": raw})

selected = [("campaign", p) for p in [CAMPAIGN / "campaign.json", CAMPAIGN / "benchmark-profile.json"]]
for name in ["child-failure.json", "parent-failure.json", "context.json", "source-files.json",
             "benchmark-profile.json", "toolchain.lock.json", "initial-project-files.json", "editor-snapshot.json"]:
    selected.append(("campaign", ATTEMPT / name))
for directory in ["host-owner", "editor-host", "import-host"]:
    selected.extend(("campaign", p) for p in sorted((ATTEMPT / directory).iterdir()) if p.is_file())
for pattern in ["joint-*.json", "batch-capture-*.json", "sample-preview-*.json"]:
    selected.extend(("campaign", p) for p in sorted(ATTEMPT.glob(pattern)))
for name in ["input.json", "input/ack-05.json", "input/start-05.json", "out/ready-05.json",
             "out/ready-06.json", "out/batch-05.json"]:
    selected.append(("campaign", ATTEMPT / "project/benchmark" / name))
selected.append(("campaign", CAMPAIGN / "source/studio/tests/replay/run_benchmark_campaign.py"))
selected.extend(("supervisor", p) for p in sorted(SUPERVISOR.iterdir()) if p.is_file())

copies = []
for kind, source in selected:
    root = CAMPAIGN if kind == "campaign" else SUPERVISOR
    relative = source.relative_to(root).as_posix()
    expected = next(row for row in raw[kind] if row["path"] == relative)
    destination = f"raw/{kind}/{relative}"
    data = source.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected["sha256"]:
        raise RuntimeError(f"input changed before copy: {source}")
    write(destination, data)
    if digest(OUT / destination) != expected["sha256"]:
        raise RuntimeError(f"copy readback mismatch: {source}")
    copies.append({"path": destination, "raw_root": kind, "raw_path": relative,
                   "bytes": len(data), "sha256": expected["sha256"]})
write("preserved-byte-manifest.json", {"created_utc": utc(), "scope": "Exact unmodified selected input bytes; derived observations and analysis are separate.", "files": copies})

campaign = read(CAMPAIGN / "campaign.json")
context = read(ATTEMPT / "context.json")
failure = read(ATTEMPT / "child-failure.json")
source_rows = []
for name, expected in campaign["source_files"].items():
    row = {"path": name, "expected_sha256": expected}
    for key, base in [("campaign_frozen", CAMPAIGN / "source/studio"),
                      ("attempt_frozen", ATTEMPT / "source/studio"), ("live_at_preservation", ROOT / "studio")]:
        path = base / name
        row[key + "_sha256"] = digest(path) if path.is_file() else None
        row[key + "_matches"] = row[key + "_sha256"] == expected
    source_rows.append(row)
write("source-map-verification.json", {"created_utc": utc(), "frozen_source_closure_sha256": campaign["source_closure_sha256"],
    "source_file_count": len(source_rows), "context_source_map_equal": context["source_files"] == campaign["source_files"],
    "attempt_source_map_equal": read(ATTEMPT / "source-files.json") == campaign["source_files"],
    "all_frozen_files_match": all(r["campaign_frozen_matches"] and r["attempt_frozen_matches"] for r in source_rows),
    "all_live_files_match_at_preservation": all(r["live_at_preservation_matches"] for r in source_rows), "files": source_rows})

attempt_slots = []
for index in range(10):
    for attempt in range(1, 4):
        path = CAMPAIGN / f"run-{index:02d}-attempt-{attempt:02d}"
        attempt_slots.append({"path": path.relative_to(CAMPAIGN).as_posix(), "exists": os.path.lexists(path),
            "stop_request_lexists": os.path.lexists(path / "stop-request.json"),
            "run_capture_exists": (path / "run-capture.json").is_file()})
absences = {}
for name in ["editor-host/process-exit.json", "editor-host/capture.json", "host-owner/capture.json", "child-result.json",
             "cleanup.json", "assembly-manifest.json", "assembled-run.json", "run-capture.json",
             "project/benchmark/out/index.json", "project/benchmark/out/batch-06.json", "project/benchmark/out/batch-34.json",
             "project/benchmark/input/start-06.json", "project/benchmark/input/ack-06.json"]:
    absences["run-00-attempt-01/" + name] = not os.path.lexists(ATTEMPT / name)
for name in ["campaign-capture.json", "dataset.json", "summary.json"]:
    absences[name] = not os.path.lexists(CAMPAIGN / name)
write("terminal-facts.json", {"observed_utc": utc(), "git_head_at_preservation": baseline,
    "status_launcher_sha256": launcher_digest, "formal_acceptance": False,
    "scheduler": scheduler, "native_process_names_observed": [p for p in processes if any(n in p["Name"].lower() for n in ["godot", "blender"])],
    "child_failure_code": failure["code"], "child_failure_phase": failure["phase"],
    "completed_batches": failure["completed_batches"], "warmup_batches_completed": 5,
    "captured_measured_batches": failure["completed_batches"] - 5,
    "measured_sample_screen_pass_count": 0, "completed_full_runs": 0,
    "partial_command": failure["partial_command"],
    "host_actual_target_exit": read(ATTEMPT / "host-owner/process-exit.json"),
    "editor_actual_target_start": read(ATTEMPT / "editor-host/process-start.json"),
    "editor_actual_target_exit": None,
    "host_cleanup": read(ATTEMPT / "host-owner/cleanup-001.json"),
    "editor_cleanup": read(ATTEMPT / "editor-host/cleanup-001.json"),
    "import_capture": read(ATTEMPT / "import-host/capture.json"),
    "fixed_attempt_slots": attempt_slots, "confirmed_absences": absences,
    "raw_file_count": sum(map(len, raw.values())), "raw_total_bytes": sum(r["bytes"] for rows in raw.values() for r in rows),
    "preserved_input_file_count": len(copies), "preserved_input_bytes": sum(r["bytes"] for r in copies),
    "started_utc": started, "finished_utc": utc()})
print(json.dumps({"out": str(OUT), "raw_files": sum(map(len, raw.values())),
    "copied_files": len(copies), "copied_bytes": sum(r["bytes"] for r in copies),
    "scheduler_state": scheduler["state"], "scheduler_result": scheduler["last_task_result"],
    "all_frozen_match": all(r["campaign_frozen_matches"] and r["attempt_frozen_matches"] for r in source_rows)}))
