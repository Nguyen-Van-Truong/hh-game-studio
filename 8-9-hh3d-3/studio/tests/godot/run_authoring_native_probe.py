"""Bounded native O2 authoring diagnostic on a disposable Godot editor.

The runner freezes the candidate catalog and probe source, copies only those
inputs into a fresh project, and launches one direct pinned GUI executable under
the existing owned Job wrapper. It captures actual process exit/tree proof and
checks native readback/UndoRedo/isolation rows. The result is AUTHORITY=0
diagnostic evidence: the candidate profile stays disabled and no GT06 closure
or accepted capability is touched.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))

_RUNNER_SPEC = importlib.util.spec_from_file_location(
    "o2_native_run_fixture", STUDIO / "build/bootstrap/run_fixture.py")
_RUNNER = importlib.util.module_from_spec(_RUNNER_SPEC)
sys.modules[_RUNNER_SPEC.name] = _RUNNER
_RUNNER_SPEC.loader.exec_module(_RUNNER)

_CONTRACT_SPEC = importlib.util.spec_from_file_location(
    "o2_native_authoring_contract", STUDIO / "godot-addon/authoring_contract.py")
_CONTRACT = importlib.util.module_from_spec(_CONTRACT_SPEC)
sys.modules[_CONTRACT_SPEC.name] = _CONTRACT
_CONTRACT_SPEC.loader.exec_module(_CONTRACT)

_EDGE_SPEC = importlib.util.spec_from_file_location(
    "o2_native_gameplay_edges", STUDIO / "godot-addon/gameplay_edges.py")
_EDGE = importlib.util.module_from_spec(_EDGE_SPEC)
sys.modules[_EDGE_SPEC.name] = _EDGE
_EDGE_SPEC.loader.exec_module(_EDGE)
from studio.protocol.core import Request, canonical_bytes

_RESOURCE_SPEC = importlib.util.spec_from_file_location(
    "o2_native_resource_authoring", STUDIO / "godot-addon/resource_authoring.py")
_RESOURCE = importlib.util.module_from_spec(_RESOURCE_SPEC)
sys.modules[_RESOURCE_SPEC.name] = _RESOURCE
_RESOURCE_SPEC.loader.exec_module(_RESOURCE)


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def source_files() -> dict[str, str]:
    names = [
        "build/bootstrap/run_fixture.py",
        "toolchain.lock.json",
        "godot-addon/authoring_contract.py",
        "contracts/godot-authoring-schema-v1.json",
        "tests/godot/authoring_native_probe.gd",
        "tests/godot/authoring_native_plugin.gd",
        "tests/godot/gameplay_edges_native.gd",
        "tests/godot/run_authoring_native_probe.py",
        "godot-addon/gameplay_edges.py",
        "godot-addon/resource_authoring.py",
        "protocol/core.py",
        "protocol/_rfc8785/__init__.py",
        "protocol/_rfc8785/_impl.py",
    ]
    return {name: sha(STUDIO / name) for name in sorted(names)}


def closure(manifest: dict[str, str]) -> str:
    rows = "".join(f"8-9-hh3d-3/studio/{name}\0{digest}\n"
                    for name, digest in sorted(manifest.items()))
    return hashlib.sha256(rows.encode("utf-8")).hexdigest()


def resolve_gui(binary: Path, lock: dict) -> tuple[Path, str, str]:
    binary = binary.resolve(strict=True)
    if sha(binary) == lock["gui_sha256"]:
        return binary, lock["gui_sha256"], "gui-direct"
    if sha(binary) == lock["console_sha256"] and binary.name.lower().endswith("_console.exe"):
        sibling = binary.with_name(binary.name[:-len("_console.exe")] + ".exe")
        if sibling.is_file() and sha(sibling) == lock["gui_sha256"]:
            return sibling, lock["gui_sha256"], "console-input-resolved-to-gui-direct"
    raise ValueError("PIN_HASH")


def project_files(project: Path) -> dict[str, str]:
    return {
        path.relative_to(project).as_posix(): sha(path)
        for path in sorted(project.rglob("*"))
        if path.is_file() and ".godot" not in path.relative_to(project).parts
        and path.name not in ("o2-native-result.json", "editor.log")
        and path.suffix != ".uid"
    }


def expected_labels(catalog: dict) -> set[str]:
    labels = {
        "actual_editor", "root_scene_loaded", "root_identity", "project_isolation",
        "user_data_isolation", "run_root_recorded", "native_history_available",
        "initial_history_empty", "catalog_shape", "InputMap_singleton_readback",
        "InputMap_node_mutation_rejected", "cleanup_empty_history",
        "cleanup_temporary_nodes",
    }
    for row in catalog["classes"]:
        prefix = "class_" + row["class_name"]
        labels.update({prefix + suffix for suffix in (
            "_classdb_exists", "_classdb_parent", "_reject_unknown_property")})
        if row.get("kind") == "singleton":
            labels.update({prefix + "_classdb_instantiable_advisory", prefix + "_singleton_only"})
        else:
            labels.update({prefix + suffix for suffix in (
                "_classdb_instantiable", "_native_construct", "_readback_all_properties",
                "_undo_do_readback", "_undo_transition", "_undo_readback",
                "_redo_transition", "_redo_readback")})
    return labels


def expected_edge_labels() -> set[str]:
    labels = {"edge_proposal_count"}
    for operation in ("scene.signal.connect", "scene.group.assign", "input.action.define"):
        prefix = "edge_" + operation.replace(".", "_")
        labels.update(prefix + suffix for suffix in (
            "_binding", "_fixture_target", "_before", "_do_readback", "_effect",
            "_undo_transition", "_undo_readback", "_redo_transition", "_redo_readback",
            "_redo_effect", "_cleanup_transition", "_cleanup_readback"))
    return labels


def expected_resource_labels() -> set[str]:
    labels = {"resource_proposal_count"}
    for resource_type in ("RectangleShape2D", "CapsuleShape2D", "BoxShape3D", "CapsuleShape3D"):
        prefix = "resource_" + resource_type
        labels.update(prefix + suffix for suffix in (
            "_binding", "_classdb", "_node_created", "_before", "_shape_readback", "_do_readback", "_identity",
            "_undo_transition", "_undo_readback", "_redo_transition",
            "_redo_readback", "_cleanup_transition", "_cleanup_readback"))
    return labels


def edge_proposals() -> list[dict]:
    context = _EDGE.EdgeContext(
        "project.fixture", "sha256:" + "1" * 64, "sha256:" + "2" * 64,
        3, "lease.fixture", 7, 31000, 1000,
        (_EDGE.EdgeNode("root"), _EDGE.EdgeNode("actor"), _EDGE.EdgeNode("bot")))
    rows = (
        ("scene.signal.connect", {"stable_id": "actor"},
         {"signal_name": "pressed", "target_stable_id": "bot", "method": "hide"}),
        ("scene.group.assign", {"stable_id": "actor"},
         {"group_name": "o2_probe_group"}),
        ("input.action.define", {"stable_id": "root"},
         {"action_name": "o2_probe_jump", "physical_key": 32, "deadzone": 0.25}),
    )
    result: list[dict] = []
    for index, (operation, target, body) in enumerate(rows, 1):
        payload = {"expected_generation": context.generation,
                   "expected_project_revision": context.project_revision, **body}
        request = Request(
            command_id=f"edge.native.{index}", project_id=context.project_id,
            operation=operation, lease_id=context.lease_id,
            fencing_epoch=context.fencing_epoch, expected_revision=context.revision,
            target=target, payload=payload,
            payload_hash="sha256:" + __import__("hashlib").sha256(canonical_bytes(payload)).hexdigest(),
            deadline_ms=2000)
        result.append(_EDGE.validate_request(request, context).projection)
    return result


def resource_proposals() -> list[dict]:
    context = _RESOURCE.ValidationContext(
        "project.fixture", "sha256:" + "1" * 64, "sha256:" + "2" * 64,
        4, "lease.fixture", 9, 31000, 1000,
        (_RESOURCE.NodeState("root", None, "Node2D", "Root"),
         _RESOURCE.NodeState("collider", "root", "CollisionShape2D", "Collider"),
         _RESOURCE.NodeState("collider3d", "root", "CollisionShape3D", "Collider3D")))
    rows = (
        ("RectangleShape2D", "collider", {"size": [8, 4]}),
        ("CapsuleShape2D", "collider", {"radius": 2, "height": 5}),
        ("BoxShape3D", "collider3d", {"size": [2, 3, 4]}),
        ("CapsuleShape3D", "collider3d", {"radius": 1.5, "height": 4}),
    )
    result: list[dict] = []
    for index, (resource_type, target_id, properties) in enumerate(rows, 1):
        payload = {"expected_generation": context.generation,
                   "expected_project_revision": context.project_revision,
                   "resource_id": "native." + resource_type.lower(),
                   "resource_type": resource_type, "properties": properties}
        request = Request(
            command_id=f"resource.native.{index}", project_id=context.project_id,
            operation="scene.resource.create", lease_id=context.lease_id,
            fencing_epoch=context.fencing_epoch, expected_revision=context.revision,
            target={"stable_id": target_id}, payload=payload,
            payload_hash="sha256:" + hashlib.sha256(canonical_bytes(payload)).hexdigest(),
            deadline_ms=2000)
        result.append(_RESOURCE.validate_request(request, context).projection)
    return result


def validate_result(result: object, catalog: dict, process: dict, run_root: Path) -> tuple[bool, str | None]:
    if not isinstance(result, dict):
        return False, "result-not-object"
    if result.get("schema") != "hh-o2-native-authoring-observation-1":
        return False, "schema"
    if result.get("actual_editor") is not True or result.get("runtime_authorized") is not False:
        return False, "authorization-binding"
    if result.get("native_mutation") is not True or result.get("formal_acceptance") is not False:
        return False, "native-diagnostic-binding"
    if result.get("failures") != []:
        return False, "probe-failures"
    checks = result.get("checks")
    if not isinstance(checks, list) or not checks:
        return False, "checks"
    labels = []
    for row in checks:
        if not isinstance(row, dict) or not isinstance(row.get("label"), str) or row.get("passed") is not True:
            return False, "check-failed"
        labels.append(row["label"])
    expected = expected_labels(catalog) | expected_edge_labels() | expected_resource_labels()
    if len(labels) != len(set(labels)) or set(labels) != expected:
        missing = sorted(expected - set(labels))
        extra = sorted(set(labels) - expected)
        return False, f"check-label-set missing={missing} extra={extra}"
    isolation = result.get("isolation")
    if not isinstance(isolation, dict) or isolation.get("project_under_run_root") is not True or isolation.get("user_under_run_root") is not True or isolation.get("network_used") is not False or isolation.get("arbitrary_script_loaded") is not False or isolation.get("public_ack") is not False:
        return False, "isolation"
    normalized_root = run_root.resolve().as_posix().rstrip("/") + "/"
    for key in ("project_root", "user_root"):
        value = result.get(key)
        if not isinstance(value, str) or not value.replace("\\", "/").startswith(normalized_root):
            return False, key
    if result.get("pid") != process.get("target_pid"):
        return False, "pid-binding"
    return True, None


def run(godot: Path, run_id: str, output: Path) -> dict:
    if not re.fullmatch(r"o2-native-[a-z0-9-]{1,32}", run_id):
        raise ValueError("RUN_ID")
    output = output.resolve()
    if output.exists() or _RUNNER._within(output, STUDIO):
        raise ValueError("OUTPUT_SCOPE")
    output.mkdir(parents=True)
    lock = json.loads((STUDIO / "toolchain.lock.json").read_text(encoding="utf-8"))["godot"]
    requested_binary = godot.resolve(strict=True)
    binary, binary_sha256, binary_mode = resolve_gui(requested_binary, lock)
    manifest = source_files()
    source_closure = closure(manifest)
    catalog = _CONTRACT.load_catalog().as_dict()
    root = output / "run"
    project = root / "project"
    project.mkdir(parents=True)
    addon = project / "addons/o2_native"
    tests = project / "tests"
    scenes = project / "scenes"
    addon.mkdir(parents=True)
    tests.mkdir(parents=True)
    scenes.mkdir(parents=True)
    shutil.copyfile(STUDIO / "tests/godot/authoring_native_plugin.gd", addon / "plugin.gd")
    shutil.copyfile(STUDIO / "tests/godot/authoring_native_probe.gd", tests / "authoring_native_probe.gd")
    shutil.copyfile(STUDIO / "tests/godot/gameplay_edges_native.gd", tests / "gameplay_edges_native.gd")
    (addon / "plugin.cfg").write_text(
        '[plugin]\nname="HH O2 Native Diagnostic"\ndescription="Disposable O2 probe"\n'
        'author="HH Studio"\nversion="0.0-diagnostic"\nscript="plugin.gd"\n',
        encoding="utf-8", newline="\n")
    (project / "project.godot").write_text(
        'config_version=5\n[application]\nconfig/name="HH O2 Native Diagnostic"\n'
        'run/main_scene="res://scenes/fixture.tscn"\n[editor_plugins]\n'
        'enabled=PackedStringArray("res://addons/o2_native/plugin.cfg")\n'
        '[rendering]\nrenderer/rendering_method="gl_compatibility"\n',
        encoding="utf-8", newline="\n")
    (scenes / "fixture.tscn").write_text(
        '[gd_scene format=3]\n\n[node name="Fixture" type="Node3D"]\n'
        'metadata/hh_o2_native_root = "fixture-root"\n', encoding="utf-8", newline="\n")
    (project / "catalog-input.json").write_bytes(
        json.dumps({"catalog_version": catalog["catalog_version"], "classes": catalog["classes"]},
                   ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    write_json(project / "edge-input.json", {"proposals": edge_proposals()})
    write_json(project / "resource-input.json", {"proposals": resource_proposals()})
    project_before = project_files(project)
    write_json(output / "freeze.json", {"run_id": run_id, "source_files": manifest,
              "source_closure_sha256": source_closure, "binary_sha256": binary_sha256,
              "binary_mode": binary_mode, "catalog_digest": _CONTRACT.load_catalog().digest,
              "project_files": project_before, "authority": 0, "formal_acceptance": False})
    env = _RUNNER._isolated_user_env(root / "godot-user")
    env["HH_O2_RUN_ROOT"] = root.resolve().as_posix()
    log = project / "editor.log"
    process = _RUNNER.run_process(
        [str(binary), "--headless", "--editor", "--path", str(project),
         "--log-file", str(log), "res://scenes/fixture.tscn"],
        cwd=project, output=output, timeout=90, label="editor", env=env)
    result_path = project / "o2-native-result.json"
    result = json.loads(result_path.read_text(encoding="utf-8")) if result_path.is_file() else None
    project_after = project_files(project)
    source_after = source_files()
    labels_ok, result_error = validate_result(result, catalog, process, root) if result is not None else (False, "missing-result")
    project_unchanged = project_before == project_after
    source_unchanged = manifest == source_after
    log_text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
    clean_log = not re.search(r"(?mi)^(?:SCRIPT ERROR|ERROR:|WARNING:)|ObjectDB instances leaked", log_text)
    capture = {
        "schema": "hh-o2-native-authoring-capture-1", "run_id": run_id,
        "source_closure_sha256": source_closure, "binary_sha256": binary_sha256,
        "binary_mode": binary_mode, "process": process,
        "probe": result, "probe_error": result_error, "project_unchanged": project_unchanged,
        "source_unchanged": source_unchanged, "clean_log": clean_log,
        "project_files_before": project_before, "project_files_after": project_after,
        "log_sha256": sha(log) if log.is_file() else None,
        "raw_artifacts": {path.relative_to(output).as_posix(): sha(path)
                          for path in sorted(output.rglob("*")) if path.is_file()},
        "formal_acceptance": False, "authority": 0,
    }
    capture["passed"] = bool(process.get("exit_code") == 0 and process.get("wrapper_exit_code") == 0
                              and process.get("timed_out") is False and process.get("tree_verified") is True
                              and labels_ok and project_unchanged and source_unchanged and clean_log)
    write_json(output / "capture.json", capture)
    # Refresh artifact hashes after capture itself is written.
    capture["raw_artifacts"] = {path.relative_to(output).as_posix(): sha(path)
                                for path in sorted(output.rglob("*")) if path.is_file()}
    write_json(output / "result.json", capture)
    return capture


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = run(args.godot, args.run_id, args.output)
    print(json.dumps({"run_id": report["run_id"], "passed": report["passed"],
                      "probe_error": report["probe_error"]}))
    raise SystemExit(0 if report["passed"] else 1)
