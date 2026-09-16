"""Actual EditorPlugin diagnostic on fresh, owned, trusted fixture processes.

This freezes its complete input set. It is not an untrusted-script sandbox,
public transport, production save transaction or GT-03 acceptance runner.
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
import tempfile

STUDIO = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def inputs():
    paths = []
    for directory in ("godot-addon", "tests/godot"):
        paths.extend(path for path in (STUDIO / directory).rglob("*")
                     if path.is_file() and "__pycache__" not in path.parts)
    paths.extend(STUDIO / name for name in (
        "protocol/jcs_godot.gd", "build/bootstrap/run_fixture.py", "toolchain.lock.json"))
    paths.extend(path for path in (STUDIO / "protocol").rglob("*.py") if "__pycache__" not in path.parts)
    result = {}
    for path in sorted(paths):
        if path.is_symlink() or getattr(path.stat(follow_symlinks=False), "st_file_attributes", 0) & 0x400:
            raise ValueError("source reparse forbidden")
        result[path.relative_to(STUDIO).as_posix()] = sha(path)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", args.run_id):
        parser.error("invalid run ID")
    output = args.output.resolve()
    output.relative_to(STUDIO.parent / "zdoc/reviews")
    output.mkdir(parents=True, exist_ok=False)
    before = inputs()
    source = output / "source/studio"
    for name, digest in before.items():
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((STUDIO / name).read_bytes())
        if sha(target) != digest:
            raise ValueError("source changed during freeze")
    spec = importlib.util.spec_from_file_location("owned_gt03", source / "build/bootstrap/run_fixture.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    closure = runner.source_closure_sha256(before)
    write_json(output / "source-closure.json", {"files": before, "source_closure_sha256": closure})
    lock = json.loads((source / "toolchain.lock.json").read_text(encoding="utf-8"))["godot"]
    local = json.loads((STUDIO / ".local/toolchain.local.json").read_text(encoding="utf-8"))
    binary = Path(local["godot_console"]).with_name(lock["gui_executable"])
    if sha(binary) != lock["gui_sha256"]:
        raise ValueError("pinned GUI binary hash mismatch")
    capture = {"run_id": args.run_id, "scope": "trusted_actual_editor_in_memory_and_pack_reopen",
               "source_closure_sha256": closure, "godot_sha256": sha(binary), "lanes": [],
               "production_save_verified": False, "hostile_script_sandbox_verified": False}
    unit_code = (
        "import unittest,json,sys; "
        "suite=unittest.defaultTestLoader.discover('tests/godot',pattern='test_*.py'); "
        "result=unittest.TextTestRunner(verbosity=2).run(suite); "
        "print('GT03_UNIT_COMPLETE '+json.dumps({'run':result.testsRun,"
        "'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped)}),flush=True); "
        "sys.exit(not result.wasSuccessful())")
    unit_host = runner.run_process([sys.executable, "-B", "-c", unit_code], cwd=source,
                                  output=output, timeout=60, label="unit")
    unit_lines = (output / unit_host["stdout"]).read_text(encoding="utf-8").splitlines()
    markers = [line.removeprefix("GT03_UNIT_COMPLETE ") for line in unit_lines if line.startswith("GT03_UNIT_COMPLETE ")]
    unit_counts = json.loads(markers[0]) if len(markers) == 1 else None
    capture["unit"] = {"host": unit_host, "counts": unit_counts,
                       "passed": unit_host["exit_code"] == 0 and unit_host["wrapper_exit_code"] == 0
                       and unit_host["tree_verified"] and not unit_host["timed_out"]
                       and unit_counts is not None and unit_counts["run"] > 0
                       and unit_counts["failures"] == 0 and unit_counts["errors"] == 0 and unit_counts["skips"] == 0}
    temporary = Path(tempfile.mkdtemp(prefix="hh-gt03-editor-"))
    try:
        project = temporary / "project"
        addon = project / "addons/hh_studio"
        shutil.copytree(source / "godot-addon/addons/hh_studio", addon)
        shutil.copyfile(source / "protocol/jcs_godot.gd", addon / "jcs_godot.gd")
        shutil.copyfile(source / "tests/godot/diagnostic_plugin.gd", addon / "diagnostic_plugin.gd")
        config = (addon / "plugin.cfg").read_text(encoding="utf-8")
        (addon / "plugin.cfg").write_text(config.replace('script="plugin.gd"', 'script="diagnostic_plugin.gd"'), encoding="utf-8")
        (project / "tests").mkdir()
        shutil.copyfile(source / "tests/godot/editor_probe.gd", project / "tests/editor_probe.gd")
        (project / "scenes").mkdir()
        (project / "saved").mkdir()
        (project / "scripts").mkdir()
        (project / "scripts/fixture_actor.gd").write_text('extends Node3D\n', encoding="utf-8")
        initial_scene = '[gd_scene format=3]\n\n[node name="Fixture" type="Node3D"]\nmetadata/hh_studio_id = "root"\n'
        (project / "scenes/fixture.tscn").write_text(initial_scene, encoding="utf-8")
        (project / "project.godot").write_text(
            'config_version=5\n[application]\nconfig/name="HH GT03 trusted editor fixture"\n'
            '[rendering]\nrenderer/rendering_method="gl_compatibility"\n'
            '[editor_plugins]\nenabled=PackedStringArray("res://addons/hh_studio/plugin.cfg")\n', encoding="utf-8")
        write_json(output / "fixture-inputs.json", {
            p.relative_to(project).as_posix(): sha(p) for p in sorted(project.rglob("*")) if p.is_file()})
        env = runner._isolated_user_env(temporary)
        saved_revision = None
        initial_observation = None
        for label, mode in (("edit", "edit"), ("reopen", "reopen"), ("contract", "contract")):
            if mode == "reopen":
                saved = project / "saved/fixture.tscn"
                if not saved.is_file():
                    break
                shutil.copyfile(saved, output / "packed-scene.tscn")
                shutil.copyfile(saved, project / "scenes/fixture.tscn")
                # The engine-generated scene UID belongs to one resource path.
                # Retain evidence outside the project, not a duplicate imported UID.
                saved.unlink()
            if mode == "contract":
                (project / "scenes/fixture.tscn").write_text(initial_scene, encoding="utf-8")
                vector_spec = importlib.util.spec_from_file_location("gt03_frozen_vectors", source / "tests/godot/contract_vectors.py")
                vectors_module = importlib.util.module_from_spec(vector_spec)
                vector_spec.loader.exec_module(vectors_module)
                vectors = vectors_module.generate_vectors(initial_observation, file_hashes={
                    name: sha(project / name) for name in ("scenes/fixture.tscn", "scripts/fixture_actor.gd")})
                vector_bytes = vectors_module.canonical_bytes(vectors)
                (output / "contract-vectors.json").write_bytes(vector_bytes)
                (project / "tests/contract-vectors.json").write_bytes(vector_bytes)
            result_path = project / "diagnostic-result.json"
            if result_path.exists():
                result_path.unlink()
            progress_path = project / "diagnostic-progress.jsonl"
            if progress_path.exists():
                progress_path.unlink()
            log = project / f"{label}-engine.log"
            host = runner.run_process([
                str(binary), "--headless", "--editor", "--path", str(project),
                "--log-file", str(log), "res://scenes/fixture.tscn", "--",
                "--hh-studio-editor-probe", f"--probe-mode={mode}"],
                cwd=project, output=output, timeout=90, label=label, env=env)
            result = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else None
            if log.exists():
                shutil.copyfile(log, output / f"{label}-engine.log")
            if result_path.exists():
                shutil.copyfile(result_path, output / f"{label}-result.json")
            if progress_path.exists():
                shutil.copyfile(progress_path, output / f"{label}-progress.jsonl")
            logs = "\n".join((output / filename).read_text(encoding="utf-8", errors="replace")
                             for filename in (host["stdout"], host["stderr"]))
            if log.exists():
                logs += log.read_text(encoding="utf-8", errors="replace")
            clean_log = re.search(r"(?m)^(?:SCRIPT ERROR|ERROR|WARNING):|ObjectDB instances leaked", logs) is None
            passed = (host["exit_code"] == 0 and host["wrapper_exit_code"] == 0
                      and not host["timed_out"] and host["tree_verified"] and clean_log
                      and result is not None and result.get("ok") is True and result.get("mode") == mode)
            if mode == "edit" and result is not None:
                saved_revision = result.get("saved_revision")
                initial_observation = next(row["detail"] for row in result["checks"]
                                           if row["label"] == "actual_editor_initialized")
            exact_reopen = mode != "reopen" or (result is not None and saved_revision is not None
                                                and result.get("saved_revision") == saved_revision)
            passed = passed and exact_reopen
            capture["lanes"].append({"mode": mode, "host": host, "clean_log": clean_log,
                                     "exact_reopen_revision": exact_reopen, "passed": passed})
            if not passed:
                break
        if (project / "saved/fixture.tscn").exists():
            shutil.copyfile(project / "saved/fixture.tscn", output / "packed-scene.tscn")
    finally:
        # Only the freshly created temporary subtree is eligible for cleanup.
        if temporary.parent.resolve() != Path(tempfile.gettempdir()).resolve() or not temporary.name.startswith("hh-gt03-editor-"):
            raise ValueError("temporary cleanup boundary mismatch")
        shutil.rmtree(temporary)
        capture["temporary_removed"] = not temporary.exists()
        capture["source_unchanged"] = before == inputs()
        capture["snapshot_unchanged"] = all(sha(source / name) == digest for name, digest in before.items())
        capture["passed"] = (len(capture["lanes"]) == 3 and all(lane["passed"] for lane in capture["lanes"])
                             and capture["unit"]["passed"] and capture["source_unchanged"] and capture["snapshot_unchanged"])
        write_json(output / "capture.json", capture)
    print(json.dumps({k: v for k, v in capture.items() if k != "lanes"}))
    return 0 if capture["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
