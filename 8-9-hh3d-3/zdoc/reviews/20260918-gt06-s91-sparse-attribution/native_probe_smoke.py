"""Generate and optionally run one private, 20-second S91 helper smoke.

--self-test performs pure Python validation only. --run-id is an explicit native
launch using the existing trusted Job runner; coordinator serializes that launch.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import sys

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
STUDIO = ROOT / "studio"
HELPER = BASE / "object_probe_s91.gd"
SERIAL_IDS = [9007199254740993, 9223372036854775807, -9007199254740993, -9223372036854775807]

PRELUDE = '''extends SceneTree

class SparseProbe:
    extends Node
    var _mode: String = "full"
    var _batch: int = 4
    var _input: Dictionary = {"run_id": __RUN_ID__}
    var _failed: bool = false
    var failures: PackedStringArray = PackedStringArray()
    var records: Dictionary = {}
    var output_directory: String = ""

    func _fail(code: String) -> void:
        _failed = true
        failures.append(code)

    func _write_new(name: String, value: Dictionary) -> Dictionary:
        if name not in ["sparse-00.json", "sparse-post-00.json", "sparse-01.json", "sparse-post-01.json", "serialization.json", "smoke-status.json"]:
            _fail("SMOKE_OUTPUT_NAME")
            return {}
        if output_directory not in ["res://out/tree_item_and_node", "res://out/tree_item_only"]:
            _fail("SMOKE_OUTPUT_DIRECTORY")
            return {}
        var target: String = output_directory + "/" + name
        var temporary: String = target + ".pending"
        if records.has(name) or FileAccess.file_exists(target) or FileAccess.file_exists(temporary):
            _fail("SMOKE_OUTPUT_EXISTS")
            return {}
        # Atomic per-name claim in this fresh private project; never overwrite.
        if DirAccess.make_dir_absolute(target + ".claim") != OK:
            _fail("SMOKE_OUTPUT_CLAIM")
            return {}
        var raw: PackedByteArray = (JSON.stringify(value, "", true, true) + "\\n").to_utf8_buffer()
        if raw.size() > 1048576:
            _fail("SMOKE_OUTPUT_CAP")
            return {}
        var file: FileAccess = FileAccess.open(temporary, FileAccess.WRITE)
        if file == null:
            _fail("SMOKE_OUTPUT_OPEN")
            return {}
        file.store_buffer(raw)
        file.flush()
        var error: Error = file.get_error()
        file.close()
        file = null
        if error != OK or DirAccess.rename_absolute(temporary, target) != OK:
            _fail("SMOKE_OUTPUT_PUBLISH")
            return {}
        var digest: String = raw.get_string_from_utf8().sha256_text()
        if FileAccess.get_sha256(target) != digest:
            _fail("SMOKE_OUTPUT_READBACK")
            return {}
        records[name] = value
        return {"sha256": digest, "size_bytes": raw.size()}

'''

POSTLUDE = '''
# END_EXACT_INDENTED_S91_HELPER

var checks: Dictionary = {}

func _initialize() -> void:
    _run.call_deferred()

func _check(name: String, passed: bool) -> void:
    checks[name] = passed

func _run_arm(arm: String, include_node: bool) -> bool:
    checks.clear()
    var probe: SparseProbe = SparseProbe.new()
    probe.output_directory = "res://out/" + arm
    root.add_child(probe)
    var tree: Tree = Tree.new()
    probe.add_child(tree)
    var root_item: TreeItem = tree.create_item()
    var child_item: TreeItem = tree.create_item(root_item)
    var original_node: Node3D = Node3D.new()
    probe.add_child(original_node)
    var expected: Dictionary = {"tree_id": str(tree.get_instance_id()),
        "root_item_id": str(root_item.get_instance_id()), "child_item_id": str(child_item.get_instance_id()),
        "original_node_id": str(original_node.get_instance_id())}
    probe._batch = 4
    probe._s91_before_batch()
    _check("baseline_helper_not_failed", not probe._failed)
    _check("baseline_one_snapshot", probe._s91_snapshot_count == 1)
    if probe.records.has("sparse-00.json"):
        var baseline: Dictionary = probe.records["sparse-00.json"]
        _check("baseline_self_drift_false", baseline.counter_self_drift == false)
        _check("baseline_original_counter_delta_zero", baseline.before == baseline.after_collection)
        _check("baseline_target_counts", baseline.tree_count == 1 and baseline.tree_item_count == 2 and baseline.node3d_count == 1 and baseline.target_id_count == 4)
        _check("baseline_partial_inventory", baseline.partial_inventory == true and baseline.complete_within_target_scope == true)
    else:
        _check("baseline_record_exists", false)
    # Godot 4.7.2 TreeItem::Cell instantiates one TextParagraph per column.
    # https://github.com/godotengine/godot/blob/4.7.2-stable/scene/gui/tree.h#L124
    var before_creation: int = int(Performance.get_monitor(Performance.OBJECT_COUNT))
    var added_item: TreeItem = tree.create_item(root_item)
    var after_item_creation: int = int(Performance.get_monitor(Performance.OBJECT_COUNT))
    expected["added_item_id"] = str(added_item.get_instance_id())
    if include_node:
        var added_node: Node3D = Node3D.new()
        probe.add_child(added_node)
        expected["added_node_id"] = str(added_node.get_instance_id())
    var after_node_creation: int = int(Performance.get_monitor(Performance.OBJECT_COUNT))
    var expected_object_delta: int = 3 if include_node else 2
    var expected_target_delta: int = 2 if include_node else 1
    _check("one_column_tree", tree.columns == 1)
    _check("tree_item_creation_adds_two_objects", after_item_creation - before_creation == 2)
    _check("node_creation_delta_expected", after_node_creation - after_item_creation == (1 if include_node else 0))
    _check("no_drift_before_controlled_creation", before_creation == probe._s91_baseline_objects)
    probe._batch = 5
    probe._s91_before_batch()
    _check("growth_helper_not_failed", not probe._failed)
    _check("growth_two_snapshots", probe._s91_snapshot_count == 2)
    if probe.records.has("sparse-01.json"):
        var growth: Dictionary = probe.records["sparse-01.json"]
        _check("growth_self_drift_false", growth.counter_self_drift == false)
        _check("growth_original_counter_delta_expected", growth.object_delta_from_baseline == expected_object_delta)
        _check("growth_target_net_count_expected", growth.delta.target_net_count == expected_target_delta)
        _check("growth_node_delta_expected", growth.delta.node3d_ids.net_count == (1 if include_node else 0))
        _check("growth_tree_delta_one", growth.delta.trees[tree.get_instance_id()].net_count == 1)
    else:
        _check("growth_record_exists", false)
    var writes_before_third: int = probe.records.size()
    probe._batch = 6
    probe._s91_before_batch()
    _check("third_snapshot_capped", probe._s91_snapshot_count == 2 and probe.records.size() == writes_before_third)
    _check("no_third_snapshot_file", not FileAccess.file_exists(probe.output_directory + "/sparse-02.json"))
    for name: String in ["sparse-post-00.json", "sparse-post-01.json"]:
        _check(name + "_self_drift_false", probe.records.has(name) and probe.records[name].counter_self_drift == false)
    var packed_ids: PackedInt64Array = PackedInt64Array([9007199254740993, 9223372036854775807, -9007199254740993, -9223372036854775807])
    var keyed_ids: Dictionary = {}
    for value: int in packed_ids:
        keyed_ids[value] = str(value)
    var serial_receipt: Dictionary = probe._write_new("serialization.json", {"packed_ids": packed_ids, "id_keys": keyed_ids})
    _check("serialization_written", not serial_receipt.is_empty())
    var passed: bool = not probe._failed
    for value: bool in checks.values():
        passed = passed and value
    var status: Dictionary = {"schema_id": "hh-studio.gt06.s91-controlled-smoke", "schema_version": "1.0.0",
        "run_id": __RUN_ID__, "helper_sha256": __HELPER_SHA__, "passed": passed, "arm": arm,
        "checks": checks, "expected_ids": expected, "helper_failures": probe.failures,
        "expected_growth": {"objects": expected_object_delta, "target_ids": expected_target_delta,
            "TreeItem": 1, "TextParagraph": 1, "Node3D": 1 if include_node else 0},
        "controlled_creation": {"before": before_creation, "after_tree_item": after_item_creation, "after_node3d": after_node_creation},
        "ownership_source": "Godot4.7.2 TreeItem::Cell owns one TextParagraph per column; this fixture has one column",
        "s86_root_cause_claim": false,
        "formal_acceptance": false, "eligible_for_dataset": false}
    var status_receipt: Dictionary = probe._write_new("smoke-status.json", status)
    passed = passed and not status_receipt.is_empty() and not probe._failed
    print("HH_S91_CONTROLLED_SMOKE " + JSON.stringify(status, "", true, true))
    probe.free()
    return passed

func _run() -> void:
    var pair_passed: bool = _run_arm("tree_item_and_node", true)
    var item_passed: bool = _run_arm("tree_item_only", false)
    quit(0 if pair_passed and item_passed else 1)
'''


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def require(ok, code: str) -> None:
    if not ok:
        raise RuntimeError(code)


def generate(helper: bytes, run_id: str) -> bytes:
    require(re.fullmatch(r"gt06-s91-sparse-smoke-[a-z0-9-]{1,32}", run_id) is not None, "SMOKE_RUN_ID")
    text = helper.decode("utf-8")
    require(text.startswith("# S91_SPARSE_HELPER_BOUNDARY\n"), "SMOKE_HELPER_BOUNDARY")
    # Prefix indentation only; preserve every original helper character/newline.
    indented = "".join("    " + line for line in text.splitlines(keepends=True))
    pre = PRELUDE.replace("__RUN_ID__", json.dumps(run_id))
    post = POSTLUDE.replace("__RUN_ID__", json.dumps(run_id)).replace("__HELPER_SHA__", json.dumps(sha(helper)))
    return (pre + indented + post).encode("utf-8")


def write_new(path: Path, value: bytes | dict) -> None:
    raw = value if isinstance(value, bytes) else (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw)


def validate_native_outputs(output: Path, helper_sha: str, run_id: str, arm: str) -> dict:
    include_node = arm == "tree_item_and_node"
    expected_files = {"sparse-00.json", "sparse-post-00.json", "sparse-01.json", "sparse-post-01.json", "serialization.json", "smoke-status.json"}
    require({p.name for p in output.iterdir() if p.is_file()} == expected_files, "SMOKE_OUTPUT_SET")
    docs = {name: json.loads((output / name).read_bytes()) for name in expected_files}
    status = docs["smoke-status.json"]
    require(status["helper_sha256"] == helper_sha and status["run_id"] == run_id and status["arm"] == arm, "SMOKE_BINDING")
    require(status["passed"] is True and not status["helper_failures"] and status["checks"] and all(value is True for value in status["checks"].values()), "SMOKE_NATIVE_CHECKS")
    ids = {key: int(value) for key, value in status["expected_ids"].items()}
    baseline, growth = docs["sparse-00.json"], docs["sparse-01.json"]
    inventory = baseline["baseline_primitive_inventory"]
    require(inventory["trees"] == {str(ids["tree_id"]): sorted([ids["root_item_id"], ids["child_item_id"]])}, "SMOKE_BASE_TREE_IDS")
    require(inventory["node3d_ids"] == [ids["original_node_id"]], "SMOKE_BASE_NODE_IDS")
    tree_delta = growth["delta"]["trees"][str(ids["tree_id"])]
    node_delta = growth["delta"]["node3d_ids"]
    require(tree_delta["added"] == [ids["added_item_id"]] and tree_delta["removed"] == [], "SMOKE_GROWTH_TREE_IDS")
    require(node_delta["added"] == ([ids["added_node_id"]] if include_node else []) and node_delta["removed"] == [], "SMOKE_GROWTH_NODE_IDS")
    require(growth["delta"]["target_net_count"] == (2 if include_node else 1), "SMOKE_TARGET_GROWTH")
    require(growth["object_delta_from_baseline"] == (3 if include_node else 2), "SMOKE_OBJECT_GROWTH")
    creation = status["controlled_creation"]
    require(creation["after_tree_item"] - creation["before"] == 2, "SMOKE_TREE_ITEM_OWNED_OBJECT")
    require(creation["after_node3d"] - creation["after_tree_item"] == (1 if include_node else 0), "SMOKE_CONTROLLED_NODE_OBJECT")
    require(status["s86_root_cause_claim"] is False, "SMOKE_SCOPE")
    for index in (0, 1):
        snap, post = docs[f"sparse-{index:02d}.json"], docs[f"sparse-post-{index:02d}.json"]
        require(snap["counter_self_drift"] is False and post["counter_self_drift"] is False, "SMOKE_COUNTER_DRIFT")
        require(post["snapshot_sha256"] == sha((output / f"sparse-{index:02d}.json").read_bytes()), "SMOKE_POST_BINDING")
    serial = docs["serialization.json"]
    require(isinstance(serial["packed_ids"], list) and all(type(value) is int for value in serial["packed_ids"]), "SMOKE_PACKED_JSON_ARRAY")
    require(serial["packed_ids"] == SERIAL_IDS, "SMOKE_PACKED_JSON_PRECISION")
    require(serial["id_keys"] == {str(value): str(value) for value in SERIAL_IDS}, "SMOKE_DICTIONARY_KEY_PRECISION")
    return {"passed": True, "native_checks": status["checks"], "exact_id_serialization": True,
            "expected_growth": status["expected_growth"], "controlled_creation": creation,
            "artifacts": {name: sha((output / name).read_bytes()) for name in sorted(expected_files)}}


def seal_existing(run_id: str) -> dict:
    require(re.fullmatch(r"gt06-s91-sparse-smoke-[a-z0-9-]{1,32}", run_id) is not None, "SMOKE_RUN_ID")
    output = STUDIO / ".local/reviews" / run_id
    require(output.is_dir() and output.resolve().is_relative_to(STUDIO.resolve()), "SMOKE_SEAL_BOUNDARY")
    manifest = output / "output-manifest.json"
    require(not manifest.exists(), "SMOKE_SEAL_EXISTS")
    entries = {}
    for path in sorted(output.rglob("*")):
        require(not path.is_symlink(), "SMOKE_SEAL_SYMLINK")
        if path.is_file():
            raw = path.read_bytes()
            entries[path.relative_to(output).as_posix()] = {"sha256": sha(raw), "size_bytes": len(raw)}
    require("smoke-result.json" in entries and "native-host/process-exit.json" in entries, "SMOKE_SEAL_TERMINAL_FILES")
    value = {"run_id": run_id, "files": entries, "file_count": len(entries),
             "seal_scope": "existing complete raw and captured source; append-only manifest; no prior bytes changed",
             "formal_acceptance": False, "eligible_for_dataset": False}
    write_new(manifest, value)
    return {"run_id": run_id, "file_count": len(entries), "manifest_sha256": sha(manifest.read_bytes())}


def run(run_id: str, expected_helper: str) -> dict:
    require(os.name == "nt", "SMOKE_WINDOWS_REQUIRED")
    helper = HELPER.read_bytes()
    require(sha(helper) == expected_helper, "SMOKE_HELPER_HASH")
    generated = generate(helper, run_id)
    sys.path.insert(0, str(ROOT))
    from studio.pipeline import native_job

    lock_path = STUDIO / "toolchain.lock.json"
    lock = json.loads(lock_path.read_bytes())["godot"]
    require(lock["version"] == "4.7.2-stable", "SMOKE_PIN_VERSION")
    executable = STUDIO / ".local/tooling/godot-4.7.2-stable" / lock["gui_executable"]
    require(sha(executable.read_bytes()) == lock["gui_sha256"], "SMOKE_BINARY_HASH")
    output = STUDIO / ".local/reviews" / run_id
    require(output.resolve().is_relative_to(STUDIO.resolve()), "SMOKE_OUTPUT_BOUNDARY")
    output.mkdir(exist_ok=False)
    project = output / "project"
    for arm in ("tree_item_and_node", "tree_item_only"):
        (project / "out" / arm).mkdir(parents=True)
    write_new(project / "project.godot", b'config_version=5\n[application]\nconfig/name="S91 Controlled Diagnostic"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n')
    write_new(project / "smoke.gd", generated)
    paths = {Path(__file__).resolve(), HELPER, lock_path, project / "project.godot", project / "smoke.gd"}
    for module in tuple(sys.modules.values()):
        name = getattr(module, "__file__", None)
        if name:
            path = Path(name).absolute()
            if path.suffix == ".py" and path.is_relative_to(ROOT):
                paths.add(path)
    sources = {path.relative_to(ROOT).as_posix(): sha(path.read_bytes()) for path in sorted(paths)}
    for path in sorted(paths):
        write_new(output / "source" / path.relative_to(ROOT), path.read_bytes())
    argv = [str(executable), "--headless", "--path", str(project), "--script", "res://smoke.gd"]
    write_new(output / "smoke-input.json", {"run_id": run_id, "source_files": sources,
        "helper_sha256": expected_helper, "generated_script_sha256": sha(generated),
        "binary_sha256": lock["gui_sha256"], "argv": argv, "timeout_seconds": 20,
        "helper_embedding": "exact_text_with_four_space_indent_only", "formal_acceptance": False, "eligible_for_dataset": False})
    result = {"run_id": run_id, "passed": False, "formal_acceptance": False, "eligible_for_dataset": False}
    try:
        native_job.run_trusted_stage(argv, cwd=project, output=output / "native-host", source_files=sources,
                                    source_root=ROOT, binary_sha256=lock["gui_sha256"], timeout_seconds=20)
        capture = output / "native-host/capture.json"
        verified = native_job.verify_captured_stage(output / "native-host", sha(capture.read_bytes()))
        require(not (output / "native-host/stderr.txt").read_bytes().strip(), "SMOKE_STDERR")
        stdout = (output / "native-host/stdout.txt").read_text(encoding="utf-8")
        require(not re.search(r"(?:SCRIPT ERROR|ERROR|WARNING):", stdout), "SMOKE_ENGINE_DIAGNOSTIC")
        arms = {arm: validate_native_outputs(project / "out" / arm, expected_helper, run_id, arm)
                for arm in ("tree_item_and_node", "tree_item_only")}
        result.update(passed=True, arms=arms)
        result.update(actual_process_exit=verified["actual_process_exit"], capture_sha256=sha(capture.read_bytes()),
                      helper_sha256=expected_helper, generated_script_sha256=sha(generated))
    except BaseException as exc:
        result["failure"] = str(exc)
        result["failure_type"] = type(exc).__name__
        raise
    finally:
        write_new(output / "smoke-result.json", result)
        if (output / "native-host/process-exit.json").is_file():
            seal_existing(run_id)
    return result


def self_test() -> dict:
    helper = HELPER.read_bytes()
    generated = generate(helper, "gt06-s91-sparse-smoke-selftest")
    indented = b"".join(b"    " + line for line in helper.splitlines(keepends=True))
    require(generated.count(indented) == 1, "SMOKE_EXACT_HELPER_EMBED")
    require(b"".join(line[4:] for line in indented.splitlines(keepends=True)) == helper, "SMOKE_INDENT_ROUNDTRIP")
    require(b"__RUN_ID__" not in generated and b"__HELPER_SHA__" not in generated, "SMOKE_TEMPLATE_BINDING")
    ast.parse(Path(__file__).read_text(encoding="utf-8"))
    try:
        generate(helper, "../unsafe")
    except RuntimeError as exc:
        require(str(exc) == "SMOKE_RUN_ID", "SMOKE_INVALID_RUN_CHECK")
    else:
        raise RuntimeError("SMOKE_INVALID_RUN_ACCEPTED")
    return {"passed": True, "checks": 5, "helper_sha256": sha(helper), "generated_script_sha256": sha(generated),
            "godot_executed": False, "files_written": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-test", action="store_true")
    mode.add_argument("--run-id")
    mode.add_argument("--seal-run-id", help="Append a hash manifest to an existing completed smoke; no engine launch")
    parser.add_argument("--helper-sha256")
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test(), sort_keys=True))
    elif args.seal_run_id:
        print(json.dumps(seal_existing(args.seal_run_id), sort_keys=True))
    else:
        parser.error("--helper-sha256 is required with --run-id") if not args.helper_sha256 else None
        print(json.dumps(run(args.run_id, args.helper_sha256), sort_keys=True))
