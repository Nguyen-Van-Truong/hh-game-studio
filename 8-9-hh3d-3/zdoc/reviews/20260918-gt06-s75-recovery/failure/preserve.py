"""Read-only failed S73 launch-2 inputs; writes only this evidence directory.

This is preservation and static verification, not an engine/test launcher.
Run once: python -B <this file>. Existing evidence is never overwritten.
"""
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
SUPERVISOR = CAMPAIGN.with_name(CAMPAIGN.name + "-supervisor-launch-02")
ATTEMPT = CAMPAIGN / "run-00-attempt-02"
PWSH = r"C:\Users\truon\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe"
SOURCE_CHECKPOINT = "cb4d1f6f633e6824a30a45873f05024c3bf7cd58"


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
    if not target.resolve().is_relative_to(OUT):
        raise RuntimeError("output escaped preservation scope")
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = value if isinstance(value, bytes) else (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()
    with target.open("xb") as stream:
        stream.write(raw)


def read(path):
    return json.loads(path.read_bytes())


def capture(name, argv):
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
        if path.is_symlink() or getattr(path.lstat(), "st_file_attributes", 0) & 0x400:
            raise RuntimeError(f"unexpected reparse point: {path}")
        if path.is_file():
            before = path.stat()
            value = digest(path)
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise RuntimeError(f"raw input changed: {path}")
            rows.append({"path": path.relative_to(base).as_posix(), "bytes": after.st_size,
                         "sha256": value, "mtime_ns": after.st_mtime_ns})
    return rows


def closure(files):
    return hashlib.sha256("".join(name + "\0" + files[name] + "\n" for name in sorted(files)).encode()).hexdigest()


started = utc()
baseline = capture("observations/git-head", ["git", "rev-parse", "HEAD"]).decode().strip()
capture("observations/tracked-status", ["git", "status", "--porcelain=v1", "--untracked-files=no"])
launcher = ROOT / "studio/tests/replay/campaign_task.ps1"
launcher_digest = digest(launcher)
scheduler = json.loads(capture("observations/scheduler-terminal", [PWSH, "-NoProfile",
    "-ExecutionPolicy", "Bypass", "-File", str(launcher), "-Command", "status",
    "-CampaignId", CAMPAIGN.name, "-LaunchNumber", "2"]))
processes = json.loads(capture("observations/processes", [PWSH, "-NoProfile", "-Command",
    "$items = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'Godot|Blender|python' } | "
    "Select-Object ProcessId,ParentProcessId,Name); ConvertTo-Json -InputObject $items -Depth 4"]))
assert scheduler["state"] == 3 and scheduler["last_task_result"] == 1 and scheduler["instances"] == []

raw = {"campaign": inventory(CAMPAIGN), "supervisor": inventory(SUPERVISOR)}
write("raw-locator-hashmaps.json", {"created_utc": utc(), "algorithm": "sha256",
    "scope": "Complete inventory of both named raw roots, including prior attempt 1 and caches. No raw files excluded. Bytes remain at raw locators unless selected below.",
    "roots": {"campaign": str(CAMPAIGN), "supervisor": str(SUPERVISOR)}, "files": raw})

selected = [("campaign", CAMPAIGN / name) for name in ["campaign.json", "benchmark-profile.json"]]
for name in ["child-failure.json", "parent-failure.json", "context.json", "source-files.json",
             "benchmark-profile.json", "toolchain.lock.json", "initial-project-files.json", "editor-snapshot.json"]:
    selected.append(("campaign", ATTEMPT / name))
for directory in ["host-owner", "editor-host", "import-host"]:
    selected.extend(("campaign", p) for p in sorted((ATTEMPT / directory).iterdir()) if p.is_file())
for pattern in ["joint-*.json", "batch-capture-*.json", "sample-preview-*.json"]:
    selected.extend(("campaign", p) for p in sorted(ATTEMPT.glob(pattern)))
for name in ["input.json", "input/ack-09.json", "input/start-09.json", "out/ready-09.json",
             "out/ready-10.json", "out/batch-09.json"]:
    selected.append(("campaign", ATTEMPT / "project/benchmark" / name))
for name in ["run_benchmark_campaign.py", "benchmark_assembly.py"]:
    selected.append(("campaign", CAMPAIGN / "source/studio/tests/replay" / name))
selected.extend(("supervisor", p) for p in sorted(SUPERVISOR.iterdir()) if p.is_file())

copies = []
for kind, source in selected:
    root = CAMPAIGN if kind == "campaign" else SUPERVISOR
    relative = source.relative_to(root).as_posix()
    expected = next(row for row in raw[kind] if row["path"] == relative)
    destination = f"raw/{kind}/{relative}"
    data = source.read_bytes()
    assert hashlib.sha256(data).hexdigest() == expected["sha256"], f"input changed before copy: {source}"
    write(destination, data)
    assert digest(OUT / destination) == expected["sha256"], f"copy mismatch: {source}"
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
    result = subprocess.run(["git", "show", f"{SOURCE_CHECKPOINT}:8-9-hh3d-3/studio/{name}"], cwd=ROOT,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
    row["checkpoint_git_show_exit"] = result.returncode
    row["checkpoint_git_blob_sha256"] = hashlib.sha256(result.stdout).hexdigest() if result.returncode == 0 else None
    row["checkpoint_git_blob_matches"] = row["checkpoint_git_blob_sha256"] == expected
    source_rows.append(row)
source_closure = closure(campaign["source_files"])
assert len(source_rows) == 49 and source_closure == campaign["source_closure_sha256"]
assert context["source_files"] == campaign["source_files"] == read(ATTEMPT / "source-files.json")
assert all(r["campaign_frozen_matches"] and r["attempt_frozen_matches"] and r["checkpoint_git_blob_matches"] for r in source_rows)
write("source-map-verification.json", {"created_utc": utc(), "source_checkpoint": SOURCE_CHECKPOINT,
    "git_verification": "git show <checkpoint>:8-9-hh3d-3/studio/<path>, captured as raw bytes via subprocess; per-file exits below",
    "frozen_source_closure_sha256": source_closure, "source_file_count": len(source_rows),
    "context_source_map_equal": True, "attempt_source_map_equal": True,
    "campaign_sha256_matches_context": digest(CAMPAIGN / "campaign.json") == context["campaign_sha256"],
    "all_frozen_files_match": True, "all_checkpoint_git_blobs_match": True,
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
             "project/benchmark/out/index.json", "project/benchmark/input/start-10.json", "project/benchmark/input/ack-10.json"]:
    absences["run-00-attempt-02/" + name] = not os.path.lexists(ATTEMPT / name)
for index in range(10, 35):
    name = f"project/benchmark/out/batch-{index:02d}.json"
    absences["run-00-attempt-02/" + name] = not os.path.lexists(ATTEMPT / name)
for name in ["campaign-capture.json", "dataset.json", "summary.json"]:
    absences[name] = not os.path.lexists(CAMPAIGN / name)

host_exit = read(ATTEMPT / "host-owner/process-exit.json")
editor_start = read(ATTEMPT / "editor-host/process-start.json")
host_cleanup = read(ATTEMPT / "host-owner/cleanup-001.json")
editor_cleanup = read(ATTEMPT / "editor-host/cleanup-001.json")
import_capture = read(ATTEMPT / "import-host/capture.json")
parent_failure = read(ATTEMPT / "parent-failure.json")
cleanup_checks = []
for role, record in [("host", host_cleanup), ("editor", editor_cleanup), ("import", import_capture)]:
    job = record["job"]
    job_clean = (job["active_count"] == 0 and job["zero_observed"] and job["closed"]
        and not any(job[k] for k in ["handle_retained", "tainted", "create_uncertain", "close_uncertain", "failed_operations", "native_error"]))
    wrapper = record.get("wrapper_process_handle")
    wrapper_clean = wrapper["closed"] and not wrapper["handle_retained"] and not wrapper["close_uncertain"] if wrapper else None
    cleanup_checks.append({"role": role, "job_zero_closed_without_uncertainty": job_clean,
        "wrapper_handle_closed_without_uncertainty": wrapper_clean,
        "note": "Import capture does not contain a wrapper_process_handle object" if wrapper is None else None})
assert all(c["job_zero_closed_without_uncertainty"] and c["wrapper_handle_closed_without_uncertainty"] is not False for c in cleanup_checks)
assert parent_failure["owned_tree_zero"] and parent_failure["owner_closed"] and parent_failure["cleanup_error"] is None

facts = {"observed_utc": utc(), "git_head_at_preservation": baseline, "status_launcher_sha256": launcher_digest,
    "formal_acceptance": False, "scheduler": scheduler,
    "native_process_names_observed": [p for p in processes if any(n in p["Name"].lower() for n in ["godot", "blender"])],
    "recorded_owned_target_pids_present_in_snapshot": [p for p in processes if p["ProcessId"] in [host_exit["pid"], editor_start["pid"], import_capture["actual_process_exit"]["pid"]]],
    "child_failure_code": failure["code"], "child_failure_phase": failure["phase"],
    "completed_batches": failure["completed_batches"], "warmup_batches_completed": 5,
    "captured_measured_batches": failure["completed_batches"] - 5,
    "measured_sample_screen_pass_count": 4, "completed_full_runs": 0, "partial_command": failure["partial_command"],
    "host_actual_target_exit": host_exit, "editor_actual_target_start": editor_start,
    "editor_actual_target_exit": None, "host_cleanup": host_cleanup, "editor_cleanup": editor_cleanup,
    "import_capture": import_capture, "parent_failure": parent_failure,
    "supervisor_return": read(SUPERVISOR / "return.json"), "cleanup_static_checks": cleanup_checks,
    "fixed_attempt_slots": attempt_slots, "confirmed_absences": absences,
    "raw_file_count": sum(map(len, raw.values())), "raw_total_bytes": sum(r["bytes"] for rows in raw.values() for r in rows),
    "preserved_input_file_count": len(copies), "preserved_input_bytes": sum(r["bytes"] for r in copies),
    "started_utc": started, "finished_utc": utc()}
write("terminal-facts.json", facts)

samples = [read(p) for p in sorted(ATTEMPT.glob("sample-preview-*.json"))]
baseline_memory = samples[4]["memory"]
screens = []
for sample in samples:
    breaches = []
    # The frozen assembler constructs editor counters RSS, handles, objects,
    # resources. JSON serialization sorts keys, so do not infer runtime order
    # from the sample-preview file's dictionary order.
    for role, names in [("host", ["held_handles", "rss_bytes"]),
                        ("editor", ["rss_bytes", "held_handles", "objects", "resources"])]:
        for name in names:
            value = sample["memory"][role][name]["value"]
            reference = baseline_memory[role][name]["value"]
            limit_exceeded = value * 100 > reference * 110 if name == "rss_bytes" else value > reference
            if sample["index"] >= 5 and limit_exceeded:
                breaches.append({"role": role, "metric": name, "value": value, "baseline": reference,
                    "code": "CAMPAIGN_RSS_GROWTH" if name == "rss_bytes" else "CAMPAIGN_RETAINED_COUNTER_GROWTH"})
    gap_exceeded = sample["max_status_gap_ms"] > 2000
    if sample["index"] >= 5 and gap_exceeded:
        breaches.append({"metric": "max_status_gap_ms", "value": sample["max_status_gap_ms"], "limit": 2000, "code": "CAMPAIGN_STATUS_GAP"})
    screens.append({"index": sample["index"], "measured": sample["index"] >= 5, "memory": sample["memory"],
        "max_status_gap_ms": sample["max_status_gap_ms"], "status_gap_above_2000": gap_exceeded,
        "warmup_status_gap_exempt_under_frozen_screen": sample["index"] < 5,
        "applicable_screen_breaches": breaches})
assert [r["index"] for r in screens if r["applicable_screen_breaches"]] == [9]
assert screens[9]["applicable_screen_breaches"][0]["metric"] == "held_handles"
write("completeness-and-screen.json", {"observed_utc": utc(),
    "scope": "Read-only interpretation of failed-run records; no root-cause proof or acceptance",
    "source_checkpoint": SOURCE_CHECKPOINT, "run_id": failure["run_id"], "recorded_failure": failure["code"],
    "recorded_phase": failure["phase"], "captured_batch_indexes": [s["index"] for s in samples],
    "warmup_batches": 5, "collected_measured_batches": 5, "screen_passed_measured_batches": 4,
    "complete_runs": 0, "baseline_memory": baseline_memory, "failed_sample_memory": samples[9]["memory"],
    "primary_failing_comparison": screens[9]["applicable_screen_breaches"][0],
    "additional_observed_comparison": screens[9]["applicable_screen_breaches"][1],
    "additional_comparison_emitted_separate_failure": False,
    "runtime_editor_counter_order": ["rss_bytes", "held_handles", "objects", "resources"],
    "order_evidence": "Frozen benchmark_assembly.py constructs editor counter order; run_benchmark_campaign.py screen_sample iterates that order",
    "samples": screens, "next_native_ready_exists": (ATTEMPT / "project/benchmark/out/ready-10.json").is_file(),
    "confirmed_absences": absences, "stop_slots_checked": len(attempt_slots),
    "stop_latches_present": sum(s["stop_request_lexists"] for s in attempt_slots), "preserved_partial_data_is_accepted": False})

references = []
for path in sorted(ATTEMPT.glob("batch-capture-*.json")):
    record = read(path)
    for kind, ref in record.items():
        if kind == "index":
            continue
        target = ATTEMPT / ref["file"]
        assert target.resolve().is_relative_to(ATTEMPT)
        actual = digest(target)
        assert actual == ref["sha256"] and target.stat().st_size == ref["size_bytes"]
        references.append({"capture": path.name, "kind": kind, **ref, "verified": True})
assert len(references) == 60
assert raw["campaign"] == inventory(CAMPAIGN) and raw["supervisor"] == inventory(SUPERVISOR), "raw inventory changed"
assert all(digest(OUT / r["path"]) == r["sha256"] for r in copies)
assert all(absences.values()) and not any(s["stop_request_lexists"] for s in attempt_slots)
write("verification.json", {"verified_utc": utc(), "status": "PASS",
    "scope": "Forensic byte preservation and static checks only; no engine test, critic signature, or GT-06 acceptance",
    "raw_files_rehashed": facts["raw_file_count"], "exact_copies_reverified": len(copies),
    "batch_references_verified": len(references), "completed_batch_capture_count": len(samples),
    "source_closure_recomputed": source_closure, "source_git_checkpoint_blobs_verified": 49,
    "stop_slots_checked": len(attempt_slots), "errors": [], "batch_references": references})
print(json.dumps({"out": str(OUT), "raw_files": facts["raw_file_count"], "raw_bytes": facts["raw_total_bytes"],
    "copied_files": len(copies), "copied_bytes": facts["preserved_input_bytes"], "source_closure": source_closure,
    "scheduler_state": scheduler["state"], "scheduler_result": scheduler["last_task_result"],
    "primary_comparison": screens[9]["applicable_screen_breaches"][0], "additional_comparison": screens[9]["applicable_screen_breaches"][1]}))
