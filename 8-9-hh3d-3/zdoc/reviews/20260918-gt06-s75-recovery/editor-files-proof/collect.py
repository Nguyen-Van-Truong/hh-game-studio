"""Seal/read-only verify existing S75 diagnostics; never starts native code.

Only --collect writes, and only below this file's directory. Raw roots and
production source are never changed. Frozen source copies are the sole input
for source checks; importing the current benchmark implementation is forbidden.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
PRODUCT = HERE.parents[3]
RAW = PRODUCT / "studio/.local/reviews"
PREFIX = "gt06-s75-editor-files-"
HARNESS = {"01": "diagnose_editor_files-v1.py", "02": "diagnose_editor_files-v2.py",
           "03": "diagnose_editor_files.py"}
SCHEMA = "contracts/perf-collector.schema.json"
MUTABLE = "scenes/fixture.tscn"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read(path: Path) -> bytes:
    assert path.is_file() and not path.is_symlink(), str(path)
    return path.read_bytes()


def obj(path: Path):
    return json.loads(read(path))


def closure(files: dict[str, str]) -> str:
    return sha("".join(k + "\0" + v + "\n" for k, v in sorted(files.items())).encode())


def inventory(root: Path) -> dict[str, dict]:
    result = {}
    for path in sorted(root.rglob("*")):
        assert not path.is_symlink(), str(path)
        if path.is_file():
            data = read(path)
            result[path.relative_to(root).as_posix()] = {"sha256": sha(data), "size_bytes": len(data)}
    return result


def write(rel: str, data: bytes) -> None:
    path = HERE / rel
    assert path.resolve().is_relative_to(HERE)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and read(path) == data:
        return
    path.write_bytes(data)


def emit(rel: str, data) -> None:
    write(rel, (json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode())


def source_path(root: Path, run_id: str, name: str) -> Path:
    prefix = f".local/reviews/{run_id}/"
    if name.startswith(prefix):
        return root / name[len(prefix):]
    assert not name.startswith(".local/")
    return root / "source/studio" / name


def clean_job(data: dict) -> None:
    job = data["job"]
    assert job["zero_observed"] and job["closed"] and job["active_count"] == 0
    assert not job["handle_retained"] and not job["tainted"]
    assert not job["close_uncertain"] and not job["create_uncertain"]
    assert not job["failed_operations"]
    if "wrapper_process_handle" in data:
        handle = data["wrapper_process_handle"]
        assert handle["closed"] and not handle["handle_retained"] and not handle["close_uncertain"]


def lane_check(root: Path, lane: str, expected_exit: int, source: dict) -> dict:
    folder = root / lane
    exit_record = obj(folder / "process-exit.json")
    start_record = obj(folder / "process-start.json")
    invocation = obj(folder / "invocation.json")
    assert exit_record["pid"] == start_record["pid"]
    assert exit_record["exit_code"] == expected_exit
    assert invocation["source_files"] == source
    assert not read(folder / "stderr.txt").strip()
    stdout = read(folder / "stdout.txt")
    assert not re.search(rb"\b(?:WARNING|ERROR)\b|ObjectDB instances leaked", stdout)
    capture = None
    if (folder / "capture.json").exists():
        capture = obj(folder / "capture.json")
        for name, digest in capture["artifacts"].items():
            assert sha(read(folder / name)) == digest
        assert capture["actual_process_exit"] == exit_record
        assert capture["wrapper_exit_code"] == expected_exit
        assert capture["completed"] and capture["natural_tree_exit"]
        clean_job(capture)
        if "invocation_sha256" in capture:
            assert capture["invocation_sha256"] == sha(read(folder / "invocation.json"))
            assert capture["source_files"] == source and capture["source_unchanged"]
            assert capture["binary_sha256"] == invocation["binary_sha256"]
    else:
        assert expected_exit == 86 and lane == "editor-host"
    cleanup = None
    if lane == "editor-host":
        cleanup = obj(folder / "cleanup-001.json")
        assert cleanup["wrapper_exit_code"] == expected_exit
        clean_job(cleanup)
    return {"pid": exit_record["pid"], "actual_exit": expected_exit,
            "capture_present": capture is not None,
            "capture_artifact_hashes_verified": len(capture["artifacts"]) if capture else 0,
            "active_at_wrapper_exit": capture.get("active_at_wrapper_exit") if capture else None,
            "active_before_cleanup": capture.get("active_before_cleanup") if capture else None,
            "job_zero_and_closed": True,
            "wrapper_handle_released": True if cleanup else None,
            "wrapper_failure_code": cleanup["failure_code"] if cleanup else None}


def analyze(root: Path, scripts: Path) -> dict:
    run_id = root.name if root.name.startswith(PREFIX) else PREFIX + root.name
    arm = run_id.removeprefix(PREFIX)
    version = arm[-2:]
    failed = arm == "ignored-02"
    ignored = arm.startswith("ignored")
    d = obj(root / "diagnostic.json")
    assert d["run_id"] == run_id and d["ignored"] == ignored
    assert d["formal_acceptance"] is False and d["full_benchmark"] is False
    harness = read(scripts / HARNESS[version])
    assert sha(harness) == d["runner_sha256"]
    assert (b"filesystem.scan()" in harness) == (version == "01")
    assert (b"filesystem.scan_sources()" in harness) == (version != "01")
    assert (b"filesystem.sources_changed.connect" in harness) == (version == "03")
    assert (b"filesystem.filesystem_changed.connect" in harness) == (version != "03")
    source = d["source_files"]
    assert len(source) == (38 if version == "01" else 39)
    assert (SCHEMA in source) == (version != "01")
    assert closure(source) == d["binding"]["source_closure_sha256"]
    for name, digest in source.items():
        assert sha(read(root / "source/studio" / name)) == digest
    runtime = obj(root / "runtime-source-files.json")
    for name, digest in runtime.items():
        assert sha(read(source_path(root, run_id, name))) == digest
    initial = d["initial_project_files"]
    for name, digest in initial.items():
        if name != MUTABLE:
            assert sha(read(root / "project" / name)) == digest
    guard = root / "project/benchmark/.gdignore"
    assert guard.exists() == ignored
    if ignored:
        assert read(guard) == b"# Diagnostic evidence is not imported.\n"
    import_info = lane_check(root, "import-host", 0, source)
    editor_info = lane_check(root, "editor-host", 86 if failed else 0, runtime)
    index = obj(root / "project/benchmark/out/index.json")
    assert index["input"] == d["binding"]
    assert index["cycles_per_batch"] == 1 and index["batches_completed"] == 1
    assert not index["benchmark_complete"] and not index["formal_acceptance"] and not index["host_integrated"]
    for batch in index["batches"]:
        data = read(root / "project/benchmark/out" / batch["file"])
        assert sha(data) == batch["sha256"] and len(data) == batch["size_bytes"]
    output = read(root / "editor-host/stdout.txt")
    markers = [json.loads(line.split(b" ", 1)[1]) for line in output.splitlines()
               if line.startswith(b"HH_GT06_BENCHMARK_COMPLETE ")]
    assert len(markers) == 1
    assert markers[0]["index_sha256"] == sha(read(root / "project/benchmark/out/index.json"))
    assert markers[0]["pid"] == editor_info["pid"]
    result = {"run_id": run_id, "arm": arm, "formal_acceptance": False,
              "full_benchmark": False, "status": "FAILED_DIAGNOSTIC_WAITER" if failed else "DIAGNOSTIC_COMPLETED",
              "scan_api": "scan" if version == "01" else "scan_sources",
              "wait_signal": "sources_changed(bool)" if version == "03" else "filesystem_changed",
              "runner_file": "scripts/" + HARNESS[version], "runner_sha256": d["runner_sha256"],
              "declared_base_source_count": len(source), "declared_runtime_source_count": len(runtime),
              "base_source_closure_sha256": closure(source), "runtime_source_closure_sha256": closure(runtime),
              "all_declared_frozen_source_hashes_verified": True,
              "perf_schema_bound": SCHEMA in source, "initial_project_immutable_hashes_verified": len(initial)-1,
              "initial_mutable_scene_hash_matches_final": sha(read(root / "project" / MUTABLE)) == initial[MUTABLE],
              "import": import_info, "editor": editor_info,
              "one_native_semantic_cycle_and_index_hash_verified": True}
    expected = ([f"res://benchmark/out/ready-{i:02}.json" for i in range(10)] +
                [f"res://benchmark/input/start-{i:02}.json" for i in range(10)] +
                [f"res://benchmark/input/ack-{i:02}.json" for i in range(9)] +
                [f"res://benchmark/out/batch-{i:02}.json" for i in range(1, 10)])
    synthetic = sorted("res://" + p.relative_to(root / "project").as_posix()
                       for p in (root / "project/benchmark").rglob("*.json")
                       if read(p) == b'{"diagnostic_only":true}\n')
    if failed:
        assert not synthetic and not (root / "result.json").exists()
        assert not (root / "census/before.json").exists() and not (root / "census/after.json").exists()
        assert b'"code":"DIAGNOSTIC_SCAN_TIMEOUT"' in output
        assert b"HH_S75_CENSUS_COMPLETE" not in output
        assert obj(root / "failure.json")["detail"] == "BENCHMARK_WRAPPER_EXIT"
        result.update(synthetic_json_files_observed=0, census_available=False,
                      reason="v2 awaited filesystem_changed for an ignored/no-change scan; it timed out before either census or synthetic-file creation")
        return result
    assert synthetic == sorted(expected)
    assert b"HH_S75_CENSUS_COMPLETE 38" in output and b"HH_GT06_BENCHMARK_FAILED" not in output
    a, b = [obj(root / f"census/{label}.json") for label in ("before", "after")]
    assert a["pid"] == b["pid"] == editor_info["pid"]
    assert [a["scan_generation"], b["scan_generation"]] == [1, 2]
    assert a["mono_us"] < b["mono_us"] and a["resources"] == b["resources"] == 6
    na, nb = [{n["id"]: n for n in c["nodes"]} for c in (a, b)]
    assert len(na) == len(a["nodes"]) == len(nb) == len(b["nodes"]) == 21482
    identity = lambda n: {k: (v["class"], v["path"]) for k, v in n.items()}
    assert identity(na) == identity(nb)
    paragraphs = lambda n: {k: v["paragraphs"] for k, v in n.items() if "paragraphs" in v}
    assert paragraphs(na) == paragraphs(nb) and len(paragraphs(na)) == 39
    changed = []
    total = [sum(len(n.get("items", [])) for n in c["nodes"]) for c in (a, b)]
    for key in na:
        old, new = na[key], nb[key]
        if "items" not in old:
            continue
        ca, cb = [Counter((i["metadata"], i["text"]) for i in n["items"]) for n in (old, new)]
        if ca != cb:
            additions, removals = cb-ca, ca-cb
            changed.append({"node_id": key, "node_path": old["path"],
                            "items_before": len(old["items"]), "items_after": len(new["items"]),
                            "added_metadata": sorted(k[0] for k, v in additions.items() for _ in range(v)),
                            "removed_metadata": sorted(k[0] for k, v in removals.items() for _ in range(v))})
    assert b["objects"]-a["objects"] == (0 if ignored else 76)
    assert total[1]-total[0] == (0 if ignored else 38)
    if ignored:
        assert changed == []
    else:
        assert len(changed) == 1 and "/FileSystem/" in changed[0]["node_path"]
        assert changed[0]["items_before"] == 22 and changed[0]["items_after"] == 60
        assert changed[0]["added_metadata"] == synthetic and changed[0]["removed_metadata"] == []
    raw_result = obj(root / "result.json")
    assert raw_result["objects"] == [a["objects"], b["objects"]]
    assert raw_result["tree_items"] == total and raw_result["nodes"] == [21482, 21482]
    result.update(census_available=True, synthetic_json_files_observed=38,
                  synthetic_resource_paths=synthetic, objects=[a["objects"], b["objects"]],
                  object_delta=b["objects"]-a["objects"], tree_items=total,
                  tree_item_delta=total[1]-total[0], nodes=[21482, 21482],
                  node_ids_classes_paths_identical=True, richtext_label_count=39,
                  richtext_paragraph_counts_identical=True, resources=[6, 6],
                  scan_generations=[1, 2], changed_trees=changed)
    return result


def selected(name: str) -> bool:
    parts = Path(name).parts
    if len(parts) == 1 or parts[0] in ("source", "census"):
        return True
    if parts[0] in ("editor-host", "import-host"):
        return len(parts) == 2
    return parts[0] == "project" and ".godot" not in parts


def collect() -> None:
    copy_map, raw_inventory, arms = {}, {}, []
    for version, harness in HARNESS.items():
        original = HERE.parent / harness
        write("scripts/" + harness, read(original))
        copy_map["scripts/" + harness] = {"source": original.relative_to(PRODUCT).as_posix(),
                                          "sha256": sha(read(original)), "size_bytes": len(read(original))}
    for version in ("01", "02", "03"):
        for mode in ("indexed", "ignored"):
            arm = mode + "-" + version
            root = RAW / (PREFIX + arm)
            inv = inventory(root)
            raw_inventory[arm] = {"raw_root": root.relative_to(PRODUCT).as_posix(), "files": inv,
                                  "file_count": len(inv), "size_bytes": sum(x["size_bytes"] for x in inv.values()),
                                  "closure_sha256": closure({k: v["sha256"] for k, v in inv.items()})}
            analysis = analyze(root, HERE / "scripts")
            for name, metadata in inv.items():
                if selected(name):
                    rel = "arms/" + arm + "/" + name
                    write(rel, read(root / name))
                    copy_map[rel] = {"source": root.relative_to(PRODUCT).as_posix()+"/"+name, **metadata}
            assert inv == inventory(root), "raw changed during collection"
            assert analysis == analyze(HERE / "arms" / arm, HERE / "scripts")
            arms.append(analysis)
    emit("raw-inventory.json", {"schema": "HH-S75-PROBE-RAW-INVENTORY-1", "arms": raw_inventory})
    emit("copy-map.json", {"schema": "HH-S75-PROBE-EXACT-COPIES-1", "files": copy_map})
    summary = {"schema": "HH-S75-PROBE-SUMMARY-1", "collection_date": "2026-09-18", "formal_acceptance": False,
               "full_benchmark": False, "collection_kind": "retrospective_exact_byte_seal",
               "native_runs_started_by_collector": 0, "arms": arms,
               "raw_file_count": sum(v["file_count"] for v in raw_inventory.values()),
               "raw_bytes": sum(v["size_bytes"] for v in raw_inventory.values()),
               "exact_copy_count": len(copy_map), "exact_copy_bytes": sum(v["size_bytes"] for v in copy_map.values()),
               "limitations": ["v1 omits contracts/perf-collector.schema.json from its base/runtime maps; do not repair old provenance with current bytes",
                               "v2 and v3 bind that schema; all declared maps are checked against frozen snapshots, not live production source",
                               "ignored-02 is a failed waiter diagnostic with native exit86 and clean owner cleanup; it supplies no before/after census",
                               "supplemental present-day census hashes are not retrospective native receipts",
                               "only one semantic cycle plus synthetic diagnostic JSON and an explicit scan intervention per successful arm",
                               "census records live Node identity/paths, TreeItem column0 metadata/text, and RichText paragraph counts; it is not a full ObjectDB class census",
                               "no causal guarantee for the original campaign's extra38 Objects; no in-run kernel-handle or RSS proof; no acceptance or TICK claim"]}
    emit("summary.json", summary)
    payloads = inventory(HERE)
    payloads.pop("MANIFEST.json", None)
    emit("MANIFEST.json", {"schema": "HH-S75-PROBE-PACKAGE-1", "formal_acceptance": False,
                           "files": payloads, "payload_file_count": len(payloads),
                           "payload_bytes": sum(v["size_bytes"] for v in payloads.values()),
                           "payload_closure_sha256": closure({k: v["sha256"] for k, v in payloads.items()}),
                           "hash_domain": "sha256 of UTF-8 sorted path + NUL + exact-byte sha256 + LF; MANIFEST.json excluded"})


def verify() -> dict:
    manifest = obj(HERE / "MANIFEST.json")
    observed = inventory(HERE)
    observed.pop("MANIFEST.json")
    assert observed == manifest["files"], "package membership or exact-byte mismatch"
    assert manifest["payload_closure_sha256"] == closure({k: v["sha256"] for k, v in observed.items()})
    raw = obj(HERE / "raw-inventory.json")["arms"]
    for entry in raw.values():
        assert inventory(PRODUCT / entry["raw_root"]) == entry["files"], "raw mismatch"
    copied = obj(HERE / "copy-map.json")["files"]
    for name, entry in copied.items():
        data = read(HERE / name)
        assert data == read(PRODUCT / entry["source"]), "copy mismatch"
        assert sha(data) == entry["sha256"] and len(data) == entry["size_bytes"]
    summary = obj(HERE / "summary.json")
    for arm in summary["arms"]:
        assert analyze(HERE / "arms" / arm["arm"], HERE / "scripts") == arm
    return {"verified": True, "formal_acceptance": False, "native_runs_started": 0,
            "raw_files": summary["raw_file_count"], "exact_copies": len(copied),
            "payload_files": len(observed), "package_files_including_manifest": len(observed)+1,
            "manifest_sha256": sha(read(HERE / "MANIFEST.json")),
            "payload_closure_sha256": manifest["payload_closure_sha256"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collect", action="store_true")
    args = parser.parse_args()
    if args.collect:
        collect()
    print(json.dumps(verify(), indent=2, sort_keys=True))
