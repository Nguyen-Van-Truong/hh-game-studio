"""Independent, stdlib-only S82 evidence analysis. Never starts an engine/helper.

--write regenerates derived files and manifests in the two S82 review folders.
--verify checks existing outputs, complete manifests and original byte preservation.
The expected long helper failure is evidence, not an analyzer failure or GT06 PASS.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
REPO = ROOT.parent
SPECS = (
    ("", "result-01", 6, 25, 71129, 39992, 26028, 38336, 6720, 0),
    ("-long", "result-long-01", 16, 45, 71127, 11332, 43304, 49872, 45692, 1),
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def closure(files):
    return sha("".join(name + "\0" + files[name] + "\n" for name in sorted(files)).encode())


def item(path):
    require(path.is_file() and not path.is_symlink(), f"not a regular file: {path}")
    data = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(data), "sha256": sha(data)}


def inventory(folder):
    return [item(p) for p in sorted(folder.rglob("*")) if p.is_file()]


def verify_items(items):
    for row in items:
        require(item(ROOT / row["path"]) == row, f"byte mismatch: {row['path']}")


def git_byte_audit(paths):
    rows = []
    for path in paths:
        data = path.read_bytes()
        name = path.relative_to(REPO).as_posix()
        raw = subprocess.run(["git", "hash-object", "--no-filters", "--stdin"],
                             input=data, capture_output=True, cwd=REPO, check=True).stdout.decode().strip()
        filtered = subprocess.run(["git", "hash-object", "--path=" + name, "--stdin"],
                                  input=data, capture_output=True, cwd=REPO, check=True).stdout.decode().strip()
        rows.append({**item(path), "crlf_count": data.count(b"\r\n"),
                     "raw_git_blob": raw, "filtered_git_blob": filtered,
                     "git_filters_change_bytes": raw != filtered})
    return rows


def lane(raw, name, expected_pid, source_files):
    folder = raw / name
    capture, invocation = load(folder / "capture.json"), load(folder / "invocation.json")
    start, end = load(folder / "process-start.json"), load(folder / "process-exit.json")
    require(start == {"pid": expected_pid}, f"{name} process-start")
    require(end == {"pid": expected_pid, "exit_code": 0}, f"{name} process-exit")
    require(capture["actual_process_exit"] == end, f"{name} exit capture disagreement")
    require(invocation["source_files"] == source_files, f"{name} source map")
    for filename, digest in capture["artifacts"].items():
        require(sha((folder / filename).read_bytes()) == digest, f"{name}/{filename} artifact hash")
    require(capture["completed"] is True and capture["wrapper_exit_code"] == 0,
            f"{name} wrapper completion")
    require(capture["natural_tree_exit"] is True and capture["active_before_cleanup"] == 0,
            f"{name} natural tree exit")
    job = capture["job"]
    require(all(job[k] is True for k in ("configured", "assigned", "closed", "zero_observed")),
            f"{name} Job closure")
    require(all(job[k] is False for k in ("tainted", "handle_retained", "create_uncertain", "close_uncertain")),
            f"{name} Job uncertainty")
    require(job["active_count"] == 0 and not job["failed_operations"] and job["native_error"] is None,
            f"{name} Job residuals")
    stderr, stdout = (folder / "stderr.txt").read_bytes(), (folder / "stdout.txt").read_bytes()
    require(stderr == b"", f"{name} stderr")
    require(not re.search(rb"\b(?:WARNING|ERROR)\b|ObjectDB instances leaked|HH_GT06_BENCHMARK_FAILED", stdout),
            f"{name} diagnostic in stdout")
    if name == "editor-host":
        require(capture["invocation_sha256"] == sha((folder / "invocation.json").read_bytes()), "editor invocation hash")
        require(capture["source_files"] == source_files and capture["source_unchanged"] is True, "editor source claim")
        handle = capture["wrapper_process_handle"]
        require(handle == {"required": True, "closed": True, "handle_retained": False, "close_uncertain": False},
                "editor wrapper handle closure")
        require(capture["active_at_wrapper_exit"] == 0, "editor active wrapper exit")
    return capture, invocation


def analyze(spec):
    suffix, outer_name, count, point_count, objects, editor_pid, import_pid, child_pid, wrapper_pid, child_exit = spec
    review = ROOT / "zdoc/reviews" / ("20260918-gt06-s82-diagnosis" + suffix)
    raw = ROOT / "studio/.local/reviews" / ("gt06-s82-object-diagnostic" + suffix + "-01")
    run_id = raw.name
    outer = review / outer_name
    metadata = load(raw / "diagnostic.json")
    source, runtime = metadata["source_files"], load(raw / "runtime-source-files.json")
    require(len(source) == 40 and len(runtime) == 55, "probe source/runtime map sizes")
    require(closure(source) == metadata["binding"]["source_closure_sha256"], "source closure")
    require(metadata["run_id"] == run_id and metadata["cycles_each"] == 100 and metadata["idle_seconds"] == 120,
            "original metadata binding")
    for name, digest in source.items():
        require(sha((raw / "source/studio" / name).read_bytes()) == digest, f"frozen source {name}")
        require(runtime[name] == digest, f"runtime source {name}")
    project_prefix = ".local/reviews/" + run_id + "/project/"
    for name, digest in runtime.items():
        path = raw / "source/studio" / name if name in source else raw / "project" / name.removeprefix(project_prefix)
        require(name in source or name.startswith(project_prefix), "runtime path scope")
        require(sha(path.read_bytes()) == digest, f"runtime exact bytes {name}")
    for name, digest in metadata["initial_project_files"].items():
        if name != "scenes/fixture.tscn":
            require(sha((raw / "project" / name).read_bytes()) == digest, f"immutable initial project file {name}")
    imported, import_invocation = lane(raw, "import-host", import_pid, source)
    editor, editor_invocation = lane(raw, "editor-host", editor_pid, runtime)
    lock = load(raw / "source/studio/toolchain.lock.json")["godot"]
    require(editor["binary_sha256"] == editor_invocation["binary_sha256"] == import_invocation["binary_sha256"] == lock["gui_sha256"],
            "captured binary digest versus frozen lock")
    host, process_host = load(outer / "capture.json"), load(outer / "probe-host.json")
    h = host["host"]
    require(h["target_pid"] == process_host["target_pid"] == child_pid, "outer child PID")
    require(h["exit_code"] == process_host["exit_code"] == child_exit, "outer child exit")
    require(h["wrapper_pid"] == wrapper_pid and h["wrapper_exit_code"] == 0, "outer wrapper PID/exit")
    require(h["timed_out"] is False and h["tree_verified"] is True and host["helper_source_unchanged"] is True,
            "outer cleanup/helper immutability")
    helper_binding = load(outer / "invocation.json")
    for name, digest in helper_binding["helper_files"].items():
        require(sha((outer / name).read_bytes()) == digest == sha((review / name).read_bytes()), "executed helper exact bytes")
    require(metadata["runner_sha256"] == helper_binding["helper_files"]["diagnose_objects.py"], "helper binding")
    require(metadata["probe_sha256"] == helper_binding["helper_files"]["object_probe.gd"], "probe binding")
    out = raw / "project/benchmark/out"
    idx = load(out / "index.json")
    require(idx["completed"] is True and idx["benchmark_complete"] is False and idx["host_integrated"] is False,
            "diagnostic native completion only")
    require(idx["pid"] == editor_pid and idx["input"] == metadata["binding"], "native index binding")
    require(idx["startup_readiness"]["before"]["scene_file_sha256"] == metadata["initial_project_files"]["scenes/fixture.tscn"],
            "initial mutable scene bytes bound by native startup capture")
    require(idx["batches_completed"] == count and idx["cycles_per_batch"] == 100, "native dimensions")
    require(len(list(out.glob("batch-*.json"))) == len(idx["batches"]) == count, "exact native batch set")
    lines = (raw / "editor-host/stdout.txt").read_text(encoding="utf-8").splitlines()
    records = lambda prefix: [json.loads(line[len(prefix):]) for line in lines if line.startswith(prefix)]
    complete = records("HH_GT06_BENCHMARK_COMPLETE ")
    require(len(complete) == 1, "single native completion marker")
    require(complete[0] == {"batches": count, "benchmark_complete": False, "host_integrated": False,
            "index_sha256": sha((out / "index.json").read_bytes()), "mode": "diagnostic", "pid": editor_pid, "run_id": run_id},
            "native complete marker/index hash")
    batch_markers = records("HH_GT06_BENCHMARK_BATCH ")
    require(len(batch_markers) == count, "native batch marker count")
    batches = []
    for n, row in enumerate(idx["batches"]):
        path = out / f"batch-{n:02d}.json"
        data, b = path.read_bytes(), load(path)
        require(row == {"file": path.name, "index": n, "sha256": sha(data), "size_bytes": len(data)}, "index batch exact digest")
        require(b["index"] == n and b["pid"] == editor_pid and b["run_id"] == run_id, "batch identity")
        require(len(b["cycles"]) == 100, "100 cycles")
        require(batch_markers[n]["index"] == n and batch_markers[n]["sha256"] == sha(data), "batch stdout digest")
        for c, cycle in enumerate(b["cycles"]):
            require(cycle["index"] == c and cycle["main_thread"] is True, "cycle sequence/thread")
            require(cycle["effects"] == {"create": 1, "undo": 1, "save": 1, "reload": 1}, "cycle effects")
            require(cycle["before_sha256"] == cycle["undone_sha256"] == cycle["reloaded_sha256"], "cycle restored state")
        mem = b["memory"]["editor"]
        require(mem["objects"]["value"] == objects and mem["resources"]["value"] == 6, "batch stable counters")
        batches.append({**row, "cycles": 100, "objects": objects, "resources": 6})
    require(sha((raw / "project/scenes/fixture.tscn").read_bytes()) == b["cycles"][-1]["saved_file_sha256"],
            "final mutable scene bytes match final native save")
    point_paths = sorted(out.glob("object-*.json"))
    require(len(point_paths) == point_count == 2 * count + 13, "exact snapshot count")
    points, churn, counter_values = [], [], set()
    for n, path in enumerate(point_paths):
        p = load(path)
        require(path.name == f"object-{n:04d}.json" and p["sequence"] == n, "snapshot sequence")
        require(p["pid"] == editor_pid and p["run_id"] == run_id, "snapshot identity")
        label = ("settle" if n % 2 == 0 else "after_batch") if n < count * 2 else ("idle_end" if n == point_count - 1 else "idle")
        require(p["label"] == label and p["batch"] == min(n // 2, count - 1), "snapshot label/batch")
        before, after = p["counters_before"], p["counters_after"]
        require(before == after and p["counters_equal_across_collection"] is True, "counter collection stability")
        require(before["objects"] == objects and before["cached_resources"] == 6, "snapshot stable counters")
        require(p["inventory_complete_objectdb"] is False, "partial inventory boundary")
        require(p["inventory_count"] == sum(p["class_counts"].values()) == 27401,
                "reachable inventory class/count accounting")
        require(p["unattributed_object_count"] == objects - p["inventory_count"], "unattributed count accounting")
        counter_values.add(before["objects"])
        if n > 0:
            expected_churn = label == "settle"
            require(len(p["added"]) == len(p["removed"]) == (18 if expected_churn else 0), "snapshot identity delta")
            if expected_churn:
                require(Counter(r["class"] for r in p["added"]) == Counter({"TreeItem": 17, "Node3D": 1}), "added classes")
                require(Counter(r["class"] for r in p["removed"]) == Counter({"TreeItem": 17, "Node3D": 1}), "removed classes")
                churn.append(n)
        points.append({"file": path.name, "sha256": sha(path.read_bytes()), "sequence": n,
                       "label": label, "batch": p["batch"], "mono_us": p["mono_us"],
                       "objects_before": before["objects"], "objects_after": after["objects"],
                       "added_count": len(p["added"]), "removed_count": len(p["removed"]),
                       "changed_count": len(p["changed"]), "inventory_count": p["inventory_count"],
                       "unattributed_object_count": p["unattributed_object_count"]})
    first = load(point_paths[0])
    require(first["initial_inventory_ids_omitted"] is True and len(first["added"]) == 146 and not first["removed"], "baseline partial descriptors")
    idle_span = (points[-1]["mono_us"] - points[count * 2 - 1]["mono_us"]) / 1e6
    require(idle_span >= 120, "at least 120s from final after_batch to idle_end")
    if child_exit:
        failure = load(raw / "failure.json")
        require(failure["type"] == "AssertionError" and not (raw / "result.json").exists(), "preserved helper failure")
        require("assert len(batches) == 6" in (outer / "probe-stderr.txt").read_text() and "AssertionError" in (outer / "probe-stderr.txt").read_text(), "original failure traceback")
        require(metadata["native_batches"] == 6, "preserved stale long metadata")
    else:
        result = load(raw / "result.json")
        require(result["actual_process_exit"] == editor["actual_process_exit"] and result["point_count"] == point_count, "short helper result")
        require(result["points"] == {p.name: sha(p.read_bytes()) for p in point_paths}, "short helper point hashes")
        require((outer / "probe-stderr.txt").read_bytes() == b"", "short helper stderr")
    return review, raw, {
        "schema": "HH-GT06-S82-RAW-REANALYSIS-2", "authority": 0, "formal_acceptance": False,
        "full_benchmark": False, "run_id": run_id, "native_completion_verified": True,
        "analysis_scope": "existing raw only; no engine/helper execution; not GT06 acceptance",
        "original_metadata": item(raw / "diagnostic.json"),
        "source_closure": closure(source), "source_files": len(source), "runtime_files": len(runtime),
        "frozen_source_and_runtime_bytes_verified": True, "captured_source_unchanged": editor["source_unchanged"],
        "source_scope_note": "40-file probe closure, distinct from the S81 51-file campaign closure; captured binary digest agrees with frozen lock, no new native execution",
        "native_batches": count, "original_metadata_native_batches": metadata["native_batches"],
        "metadata_correction_required": metadata["native_batches"] != count,
        "total_native_cycles": count * 100, "object_points": point_count,
        "all_object_count_deltas_zero": len(counter_values) == 1,
        "all_identity_deltas_zero_after_initial_inventory": not churn,
        "object_values": sorted(counter_values), "resources_values": [6],
        "identity_churn": {"snapshot_sequences": churn, "snapshots": len(churn),
                           "added_each": 18, "removed_each": 18,
                           "classes_each": {"TreeItem": 17, "Node3D": 1},
                           "initial_inventory_excluded": True, "initial_selected_descriptors": 146},
        "inventory_complete_objectdb": False,
        "editor_actual_exit": editor["actual_process_exit"], "import_actual_exit": imported["actual_process_exit"],
        "editor_elapsed_seconds": editor["elapsed_seconds"], "idle_after_batch_to_end_seconds": idle_span,
        "native_job_zero_closed": True, "native_wrapper_handles_closed": True,
        "editor_stderr_empty": True, "native_logs_no_warning_error": True,
        "outer_child": {"pid": child_pid, "exit_code": child_exit},
        "outer_wrapper": {"pid": wrapper_pid, "exit_code": 0, "tree_verified": True, "timed_out": False},
        "executed_helper_succeeded": child_exit == 0,
        "helper_failure": "AssertionError at assert len(batches) == 6; raw failure/traceback preserved" if child_exit else None,
        "conclusion": "Stable sampled ObjectDB/ResourceCache counters in this narrower no-HTTP native probe; identities churn between batches. Nonreproduction does not rule out a leak or identify the S81 +2 owner.",
        "limitations": ["Partial reachable inventory, not a full ObjectDB census.",
                        "No HTTP host-command-before-native sequence or full campaign cadence.",
                        "Sample stability does not prove stability between samples.",
                        "Long native editor observation is about 507s, much shorter than the roughly 31-minute S81 failed campaign.",
                        "Outer run_fixture.py is bound by its recorded invocation digest; the original package did not archive its bytes in the 40-file probe source set. No complete outer-runner execution-closure claim.",
                        "No GT06 acceptance, campaign PASS, counter adjustment, or retry authorization."],
        "batches": batches, "points": points,
        "git_byte_audit": git_byte_audit([review / "diagnose_objects.py", outer / "diagnose_objects.py"]),
    }


def main():
    # Explicit token handling keeps the only supported invocations obvious.
    import sys
    require(sys.argv[1:] in (["--write"], ["--verify"]), "use --write or --verify")
    writing = sys.argv[1] == "--write"
    shared_paths = [BASE / name for name in ("analyze_existing_raw.py", "test_existing_raw_analyzer.py", "analysis-test-run.json")]
    test_receipt = load(shared_paths[-1])
    require(test_receipt["actual_exit_code"] == 0 and test_receipt["engine_rerun"] is False,
            "static analyzer test receipt")
    for path in shared_paths[:2]:
        require(sha(path.read_bytes()) == test_receipt["source_sha256"][path.name], "stale analyzer test source")
    for spec in SPECS:
        review, raw, result = analyze(spec)
        before = load(review / "pre-repair-byte-inventory.json")
        verify_items(before["immutable_files"])
        require(inventory(raw) == before["raw_tree_files"], "original raw tree set/bytes unchanged")
        name = "long-result.json" if spec[0] else "analysis-result.json"
        output = review / name
        result["analyzer"] = item(Path(__file__).resolve())
        if writing:
            output.write_bytes(encoded(result))
        else:
            require(output.read_bytes() == encoded(result), f"derived analysis differs: {output}")
        corrected = {"schema": "HH-S82-DERIVED-DIAGNOSTIC-METADATA-1", "authority": 0,
                     "formal_acceptance": False, "full_benchmark": False,
                     "provenance": item(raw / "diagnostic.json"),
                     "original_raw_metadata_preserved": True,
                     "original_native_batches": result["original_metadata_native_batches"],
                     "native_batches": result["native_batches"], "cycles_each": 100, "idle_seconds": 120,
                     "run_id": raw.name, "native_completion_verified": True,
                     "executed_helper_succeeded": result["executed_helper_succeeded"],
                     "reason": "Native index, batch set and COMPLETE marker determine actual batch count; original helper/metadata remain unchanged.",
                     "analysis_sha256": sha(output.read_bytes())}
        corrected_path = review / "diagnostic-corrected.json"
        if writing:
            corrected_path.write_bytes(encoded(corrected))
        else:
            require(corrected_path.read_bytes() == encoded(corrected), "derived metadata differs")
        manifest_path = review / "artifact-hashes.json"
        raw_files = inventory(raw)
        review_files = [item(p) for p in sorted(review.rglob("*")) if p.is_file() and p != manifest_path]
        shared_files = [item(p) for p in shared_paths if not p.is_relative_to(review)]
        files = sorted(raw_files + review_files + shared_files, key=lambda row: row["path"])
        manifest = {"schema": "HH-GT06-S82-EXACT-ARTIFACTS-2", "authority": 0,
                    "formal_acceptance": False, "run_id": raw.name,
                    "coverage": "Every regular file under the complete local raw tree and this review folder, plus the shared verifier and its test receipt; only this manifest excludes itself.",
                    "hash_domain": "SHA256 of exact filesystem bytes; no Git/EOL normalization",
                    "raw_tree_file_count": len(raw_files), "review_file_count_excluding_manifest": len(review_files),
                    "shared_verifier_file_count": len(shared_files),
                    "file_count": len(files), "files": files,
                    "closure_sha256": closure({row["path"]: row["sha256"] for row in files})}
        if writing:
            manifest_path.write_bytes(encoded(manifest))
        else:
            require(load(manifest_path) == manifest, "manifest exact content/set")
            verify_items(manifest["files"])
        print(json.dumps({"run_id": raw.name, "analysis_verified": True, "original_raw_bytes_preserved": True,
                          "native_batches": result["native_batches"], "object_points": result["object_points"],
                          "helper_exit": result["outer_child"]["exit_code"], "formal_acceptance": False,
                          "manifest_sha256": sha(manifest_path.read_bytes())}))


if __name__ == "__main__":
    main()
