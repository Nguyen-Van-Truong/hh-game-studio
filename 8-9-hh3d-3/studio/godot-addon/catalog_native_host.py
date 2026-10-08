"""Execute admitted catalog transactions in a bounded, script-free editor.

The native addon receives projections, never a fixture builder or an expected
snapshot. The host independently checks each readback and the saved scene,
including the actual process exit and Job cleanup. Generated gameplay scripts
belong to the sandbox publication owner and cannot enter this editor project.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
from typing import Any

from studio.pipeline import native_job
from studio.protocol.core import canonical_bytes, parse_json

STUDIO = Path(__file__).resolve().parents[1]
INPUT_SCHEMA = "hh-catalog-native-input-1"
OBSERVATION_SCHEMA = "hh-catalog-native-observation-1"
RESULT_SCHEMA = "hh-catalog-native-result-1"
EPSILON = 0.000001  # Godot float32 vectors/shape sizes, recorded in every receipt.
NATIVE_FILES = {
    "addons/hh_catalog/catalog_scene_adapter.gd": "godot-addon/catalog_scene_adapter.gd",
    "addons/hh_catalog/catalog_scene_plugin.gd": "tests/godot/catalog_scene_plugin.gd",
    "addons/hh_catalog/jcs_godot.gd": "protocol/jcs_godot.gd",
}
ARTIFACTS = ("native-observation.json", "project/scenes/authored.tscn",
             "editor-host/capture.json", "editor-host/process-start.json",
             "editor-host/process-exit.json", "editor-host/stdout.txt",
             "editor-host/stderr.txt", "editor-host/invocation.json")


def need(condition: object, code: str) -> None:
    if not condition:
        raise ValueError(code)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def copy(value: Any) -> Any:
    return parse_json(canonical_bytes(value))


def read(path: Path, maximum: int = 2 * 1024**2) -> bytes:
    path = path.absolute()
    for part in (path, *path.parents):
        info = part.stat(follow_symlinks=False)
        need(not part.is_symlink() and not getattr(info, "st_file_attributes", 0) & 0x400,
             "CATALOG_REPARSE")
    before = path.stat()
    need(path.is_file() and before.st_size <= maximum, "CATALOG_FILE_LIMIT")
    raw = path.read_bytes()
    after = path.stat()
    need((before.st_size, before.st_mtime_ns, before.st_ino) ==
         (after.st_size, after.st_mtime_ns, after.st_ino) and len(raw) <= maximum,
         "CATALOG_FILE_CHANGED")
    return raw


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = value if isinstance(value, bytes) else canonical_bytes(value) + b"\n"
    with path.open("xb") as stream:
        stream.write(raw)


def idle_window() -> None:
    local = os.environ.get("LOCALAPPDATA")
    need(local, "CATALOG_LOCALAPPDATA")
    need(not (Path(local) / "HHGodotAgent/measure-window.lock").exists(),
         "MEASUREMENT_WINDOW_HELD")


def source_manifest(extra: set[str]) -> tuple[dict[str, str], str]:
    names = extra | set(NATIVE_FILES.values()) | {
        "godot-addon/catalog_native_host.py", "toolchain.lock.json"}
    # Imported host validators, protocol/JCS and Windows Job code are execution
    # dependencies too. Capture them rather than only the dispatch facade.
    for module in tuple(sys.modules.values()):
        name = getattr(module, "__file__", None)
        if name:
            path = Path(name).resolve()
            if path.is_relative_to(STUDIO) and path.suffix == ".py":
                names.add(path.relative_to(STUDIO).as_posix())
    files = {name: sha(read(STUDIO / name)) for name in sorted(names)}
    return files, "sha256:" + sha(canonical_bytes(files))


def make_input(transaction: Any, admission: Any, root_spec: dict, catalog: Any,
               assets: dict) -> dict:
    return {"schema": INPUT_SCHEMA, "transaction": transaction.as_dict(),
            "admission": admission.as_dict(), "root_spec": copy(root_spec),
            "catalog": {name: {"instantiable": spec.instantiable,
                         "properties": {key: asdict(prop) for key, prop in spec.properties.items()}}
                        for name, spec in catalog.classes.items()},
            "assets": copy(assets)}


def expected_readbacks(data: dict) -> tuple[list[dict], dict]:
    """Independent host projection reducer; its output never enters Godot."""
    transaction = data["transaction"]
    body = {key: value for key, value in transaction.items() if key != "transaction_digest"}
    need(transaction.get("transaction_digest") == "sha256:" + sha(canonical_bytes(body)),
         "CATALOG_TRANSACTION_DIGEST")
    need(transaction.get("command_ids") == [row["command_id"] for row in transaction["commands"]]
         and len(set(transaction["command_ids"])) == len(transaction["command_ids"]), "CATALOG_COMMAND_IDS")
    root = copy(data["root_spec"])
    root["parent_id"] = None
    nodes, resources = {root["stable_id"]: root}, {}
    rows = []
    for command in transaction["commands"]:
        projection, operation = command["projection"], command["operation"]
        payload, target = projection["payload"], command["target_stable_id"]
        need(projection["operation"] == operation and projection["command_id"] == command["command_id"]
             and projection["target_stable_id"] == target, "CATALOG_COMMAND_BINDING")
        need(command["projection_sha256"] == "sha256:" + sha(canonical_bytes(projection)),
             "CATALOG_PROJECTION_DIGEST")
        if operation == "scene.node.create":
            ident = payload["stable_id"]
            need(ident not in nodes and target in nodes, "CATALOG_NODE_IDENTITY")
            row = {"stable_id": ident, "parent_id": target, "node_type": payload["node_type"],
                   "name": payload["name"], "properties": copy(payload["properties"])}
            nodes[ident] = row
        elif operation == "scene.node.update":
            need(target in nodes, "CATALOG_NODE_MISSING")
            row = nodes[target]
            row["properties"].update(copy(payload["changes"]))
        elif operation == "scene.resource.create":
            ident = payload["resource_id"]
            need(ident not in resources and target in nodes, "CATALOG_RESOURCE_IDENTITY")
            row = {"resource_id": ident, "owner_stable_id": target,
                   "resource_type": payload["resource_type"], "properties": copy(payload["properties"])}
            resources[ident] = row
        else:
            raise ValueError("CATALOG_OPERATION_UNSUPPORTED")
        rows.append({"command_id": command["command_id"], "operation": operation,
                     "target_stable_id": target, "projection_sha256": command["projection_sha256"],
                     "verified": True, "readback": copy(row)})
    snapshot = {"nodes": list(nodes.values()), "resources": list(resources.values())}
    # A Node3D room recipe owns a typed mesh resource in its authoring
    # snapshot.  The Node2D arena still mounts the same immutable Blender
    # assets for gameplay consumption, but its scene projection intentionally
    # has no mesh resource, so asset mounting must not invent one in the
    # catalog oracle.
    if data["assets"] and data.get("root_spec", {}).get("node_type") == "Node3D":
        snapshot["asset_resources"] = [{"resource_id": name, "base": "Mesh"}
                                       for name in data["assets"]]
    return rows, snapshot


def semantic_equal(actual: Any, expected: Any) -> bool:
    if type(expected) in (int, float):
        return type(actual) in (int, float) and math.isfinite(actual) and abs(actual - expected) <= EPSILON
    if isinstance(expected, dict):
        return isinstance(actual, dict) and actual.keys() == expected.keys() and all(
            semantic_equal(actual[key], value) for key, value in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(
            semantic_equal(a, b) for a, b in zip(actual, expected))
    return type(actual) is type(expected) and actual == expected


def verify_observation(data: dict, observation: dict, *, input_raw: bytes,
                       scene_raw: bytes, pid: int) -> None:
    transaction = data["transaction"]
    need(observation.get("schema") == OBSERVATION_SCHEMA and observation.get("authority") == 0
         and observation.get("public_ack") is False and observation.get("failures") == []
         and observation.get("pid") == pid, "CATALOG_NATIVE_OBSERVATION")
    need(observation.get("input_sha256") == sha(input_raw)
         and observation.get("transaction_digest") == transaction["transaction_digest"]
         and observation.get("command_ids") == transaction["command_ids"], "CATALOG_NATIVE_BINDING")
    rows, snapshot = expected_readbacks(data)
    need(semantic_equal(observation.get("commands"), rows), "CATALOG_COMMAND_READBACK")
    snapshots = observation.get("snapshots", {})
    need(semantic_equal(snapshots.get("after_apply"), snapshot)
         and semantic_equal(snapshots.get("after_reload"), snapshot), "CATALOG_SNAPSHOT_READBACK")
    checks = observation.get("checks", {})
    need(all(checks.get(key) is True for key in ("undo", "redo", "save", "reload"))
         and all(value is True for value in checks.values()), "CATALOG_NATIVE_CHECKS")
    need(observation.get("scene_sha256") == sha(scene_raw), "CATALOG_SAVED_BYTES")


def _bound_file(root: Path, name: str, digest: str) -> bytes:
    need(type(name) is str and not Path(name).is_absolute() and "\\" not in name
         and all(part not in ("", ".", "..") for part in name.split("/")), "CATALOG_BOUND_PATH")
    raw = read(root / name)
    need(sha(raw) == digest, "CATALOG_BOUND_HASH")
    return raw


def verify_native(root: Path, *, require_current_source: bool = True) -> dict:
    result = parse_json(read(root / "result.json"))
    return _verify_native(root, result, require_current_source=require_current_source)


def _verify_native(root: Path, result: dict, *, require_current_source: bool = True) -> dict:
    binding = parse_json(read(root / "binding.json"))
    need(result.get("schema") == RESULT_SCHEMA and result.get("status") == "DIAGNOSTIC_PASS"
         and result.get("authority") == 0 and result.get("public_ack") is False
         and result.get("binding_sha256") == sha(read(root / "binding.json")), "CATALOG_RESULT")
    files = binding["source_files"]
    need(set(NATIVE_FILES.values()) | {"godot-addon/catalog_native_host.py", "toolchain.lock.json"}
         <= set(files), "CATALOG_SOURCE_SET")
    need(binding.get("source_closure_sha256") == "sha256:" + sha(canonical_bytes(files)),
         "CATALOG_SOURCE_DIGEST")
    for name, digest in files.items():
        _bound_file(root / "source", name, digest)
        if require_current_source:
            _bound_file(STUDIO, name, digest)
    for name, digest in binding["project_files"].items():
        _bound_file(root / "project", name, digest)
    for name, source in NATIVE_FILES.items():
        need(read(root / "project" / name) == read(root / "source" / source), "CATALOG_ADDON_BINDING")
    need(set(result.get("artifacts", {})) == set(ARTIFACTS), "CATALOG_ARTIFACT_SET")
    for name, digest in result["artifacts"].items():
        _bound_file(root, name, digest)
    stage = native_job.verify_captured_stage(root / "editor-host", result["artifacts"]["editor-host/capture.json"])
    project = root / "project"
    input_raw = read(project / "catalog-input.json")
    observation_raw = read(root / "native-observation.json")
    need(observation_raw == read(project / "native-observation.json"), "CATALOG_OBSERVATION_COPY")
    verify_observation(parse_json(input_raw), parse_json(observation_raw), input_raw=input_raw,
                       scene_raw=read(project / "scenes/authored.tscn"), pid=stage["actual_process_exit"]["pid"])
    need(not read(root / "editor-host/stderr.txt").strip() and not re.search(
        rb"\b(?:ERROR|WARNING)\b|ObjectDB instances leaked", read(root / "editor-host/stdout.txt")), "CATALOG_NATIVE_LOG")
    invocation = parse_json(read(root / "editor-host/invocation.json"))
    pin = parse_json(read(root / "source/toolchain.lock.json"))["godot"]["gui_sha256"]
    need(invocation.get("source_files") == files and invocation.get("binary_sha256") == pin
         and binding.get("binary_sha256") == pin and invocation.get("cwd") == str(project)
         and invocation.get("argv") == [binding["binary_path"], "--headless", "--editor", "--path",
                                        str(project), "res://scenes/workbench.tscn"], "CATALOG_INVOCATION")
    return result


def execute(*, output: Path, godot: Path, data: dict, source_files: dict[str, str],
            blender: Any) -> dict:
    """Trusted owner callback. All paths/configuration come from the host."""
    idle_window()
    need(output.is_absolute() and not output.exists(), "CATALOG_OUTPUT_EXISTS")
    # Reduce before creating files so a malformed transaction has no native effect.
    expected_readbacks(data)
    output.mkdir(parents=True)
    project = output / "project"
    project_files = {
        "project.godot": b'config_version=5\n[application]\nconfig/name="HH Catalog Fixture"\n'
            b'run/main_scene="res://scenes/workbench.tscn"\n[editor_plugins]\n'
            b'enabled=PackedStringArray("res://addons/hh_catalog/plugin.cfg")\n'
            b'[rendering]\nrenderer/rendering_method="gl_compatibility"\n'
            b'[threading]\nworker_pool/max_threads=4\n',
        "scenes/workbench.tscn": b'[gd_scene format=3]\n[node name="Workbench" type="Node"]\n',
        "addons/hh_catalog/plugin.cfg": b'[plugin]\nname="HH catalog fixture"\n'
            b'description="Transaction executor"\nauthor="HH Studio"\nversion="0.1"\n'
            b'script="catalog_scene_plugin.gd"\n',
        "catalog-input.json": canonical_bytes(data) + b"\n",
        **{name: read(STUDIO / source) for name, source in NATIVE_FILES.items()},
    }
    for asset in data["assets"].values():
        need(asset["path"] == "assets/avatar.glb" and asset["sha256"] == blender.glb_sha256,
             "CATALOG_ASSET_BINDING")
        raw = read(Path(blender.published_root) / "scene.glb")
        need(sha(raw) == asset["sha256"], "CATALOG_ASSET_CHANGED")
        project_files[asset["path"]] = raw
        # The registered room recipe carries the companion sprite provenance
        # in the same trusted Blender handoff.  Mount it beside the GLB so the
        # later gameplay consumer can prove both imports came from one
        # immutable publication; it does not alter the scene projection oracle.
        sprite_path = asset.get("sprite_path")
        sprite_sha = asset.get("sprite_sha256")
        if sprite_path is not None:
            need(sprite_path == "assets/sprite_sheet.png" and
                 type(sprite_sha) is str and re.fullmatch(r"[0-9a-f]{64}", sprite_sha),
                 "CATALOG_SPRITE_BINDING")
            sprite = read(Path(blender.published_root) / "sprite_sheet.png")
            need(sha(sprite) == sprite_sha, "CATALOG_SPRITE_CHANGED")
            project_files[sprite_path] = sprite
    for name, raw in project_files.items():
        write(project / name, raw)
    for name, digest in source_files.items():
        raw = read(STUDIO / name)
        need(sha(raw) == digest, "CATALOG_FREEZE_RACE")
        write(output / "source" / name, raw)
    executable = godot.resolve(strict=True)
    pin = parse_json(read(STUDIO / "toolchain.lock.json"))["godot"]["gui_sha256"]
    binding = {"schema": "hh-catalog-native-binding-1", "source_files": source_files,
               "source_closure_sha256": "sha256:" + sha(canonical_bytes(source_files)),
               "project_files": {name: sha(raw) for name, raw in project_files.items()},
               "binary_path": str(executable), "binary_sha256": pin,
               "blender_handoff": blender.as_dict(), "numeric_epsilon": EPSILON}
    write(output / "binding.json", binding)
    result = {"schema": RESULT_SCHEMA, "authority": 0, "public_ack": False,
              "status": "DIAGNOSTIC_FAIL", "binding_sha256": sha(read(output / "binding.json"))}
    try:
        idle_window()
        native_job.run_trusted_stage([str(executable), "--headless", "--editor", "--path", str(project),
            "res://scenes/workbench.tscn"], cwd=project, output=output / "editor-host",
            source_root=STUDIO, source_files=source_files, binary_sha256=pin)
        write(output / "native-observation.json", read(project / "native-observation.json"))
        result.update(status="DIAGNOSTIC_PASS", artifacts={name: sha(read(output / name)) for name in ARTIFACTS})
    except Exception as error:
        result["error_code"] = str(error) if re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", str(error)) else type(error).__name__
    if result["status"] == "DIAGNOSTIC_PASS":
        try:
            _verify_native(output, result)
        except Exception as error:
            result.update(status="DIAGNOSTIC_FAIL", verification_error=str(error)
                if re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", str(error)) else type(error).__name__)
    write(output / "result.json", result)
    # Always retain the original failure and host capture; no relabelling/retry.
    return verify_native(output)
