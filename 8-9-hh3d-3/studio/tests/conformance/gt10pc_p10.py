"""GT-10-PC P10 installed-artifact regression producer.

P10 is deliberately separate from the historical GT-09 matrix.  It installs
the signed package into a disposable consumer, snapshots the exact installed
``payload/studio`` tree, and executes the GT-08A PC rows plus fresh K8/K10
catalog publications from that snapshot.  No retained GT-09 evidence is used
as a substitute.  The producer and verifier only emit authority-zero
diagnostics; the coordinator owns acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SCHEMA = "hh-gt10pc-p10-installed-regression-1"
RUNTIME_SCHEMA = "hh-gt10pc-p10-runtime-snapshot-1"


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise ValueError("GT10PC_P10_JSON_OBJECT")
    return value


def _need(value: object, code: str) -> None:
    if not value:
        raise ValueError(code)


def _ledger(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for directory, dirs, names in os.walk(root, followlinks=False):
        for name in dirs:
            _need(not (Path(directory) / name).is_symlink(), "GT10PC_P10_PROJECT_SYMLINK")
        dirs[:] = [name for name in dirs if name != ".godot"]
        for name in names:
            path = Path(directory) / name
            _need(not path.is_symlink(), "GT10PC_P10_PROJECT_SYMLINK")
            result[path.relative_to(root).as_posix()] = _sha(path)
    return result


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError("GT10PC_P10_IMPORT")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _child(output: Path, command: list[str], *, cwd: Path, env: dict[str, str],
           timeout: int, label: str) -> dict[str, Any]:
    """Capture an independent host process exit and its raw streams."""
    # Use the shared job/process-group launcher so a timeout cannot leave a
    # Godot or Blender descendant behind while the parent claims a clean tree.
    from studio.build.bootstrap.run_fixture import run_process
    output.mkdir(parents=True, exist_ok=True)
    started = time.time()
    process = run_process(command, cwd=cwd, output=output, timeout=timeout,
                          label=label, env=env)
    row = {"schema": "hh-gt10pc-p10-child-1", "label": label,
           "command": command, "cwd": str(cwd), **process,
           "duration_s": round(time.time() - started, 3)}
    row["stdout_sha256"] = _sha(output / process["stdout"])
    row["stderr_sha256"] = _sha(output / process["stderr"])
    (output / (label + "-receipt.json")).write_text(
        json.dumps(row, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return row


def _clean(row: dict[str, Any]) -> bool:
    return (row.get("exit_code") == 0 and row.get("timed_out") is False
            and row.get("tree_verified") is True
            and row.get("wrapper_exit_code", 0) == 0)


def _runtime_files(root: Path) -> dict[str, str]:
    """Return the actual immutable snapshot closure, rejecting links/extras."""
    root = root.resolve()
    _need(root.is_dir(), "GT10PC_P10_RUNTIME_ROOT")
    result: dict[str, str] = {}
    for directory, dirs, names in os.walk(root, followlinks=False):
        for name in dirs:
            _need(not (Path(directory) / name).is_symlink(), "GT10PC_P10_RUNTIME_SYMLINK")
        dirs[:] = sorted(name for name in dirs if name not in {".local", ".godot", "__pycache__"})
        for name in sorted(names):
            path = Path(directory) / name
            _need(not path.is_symlink(), "GT10PC_P10_RUNTIME_SYMLINK")
            relative = path.relative_to(root).as_posix()
            _need(".." not in Path(relative).parts and "\\" not in relative,
                  "GT10PC_P10_RUNTIME_PATH")
            result[relative] = _sha(path)
    return result


def _under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _verify_child_receipt(root: Path, row: dict[str, Any]) -> None:
    """Re-read the captured streams; a self-written receipt is not enough."""
    _need(_clean(row), "GT10PC_P10_CHILD_EXIT")
    for field in ("stdout", "stderr"):
        name = row.get(field)
        _need(isinstance(name, str) and Path(name).name == name,
              "GT10PC_P10_CHILD_STREAM_NAME")
        stream = root / name
        _need(stream.is_file() and _sha(stream) == row.get(field + "_sha256"),
              "GT10PC_P10_CHILD_STREAM_HASH")


def _environment(runtime_parent: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(runtime_parent)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    # Publication and installed Godot probes read this override instead of
    # looking for a dependency inside the immutable release snapshot.
    linux = ROOT / ".local/tooling/godot-4.7.2-stable-linux/Godot_v4.7.2-stable_linux.x86_64"
    env["HH_STUDIO_LINUX_GODOT"] = str(linux)
    return env


def _runtime_snapshot(install, output: Path) -> tuple[Path, dict, dict[str, str]]:
    """Copy the verified installed payload and prove every byte is bound."""
    active = install.active_path().resolve()
    manifest = install._read_release(install.snapshot()["active"])
    runtime = output / "installed-runtime" / "studio"
    runtime.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(active, runtime, symlinks=False)
    files: dict[str, str] = {}
    for name, row in manifest["files"].items():
        if not name.startswith("payload/studio/"):
            continue
        rel = name.removeprefix("payload/studio/")
        path = runtime / rel
        _need(path.is_file() and _sha(path) == row["sha256"], "GT10PC_P10_RUNTIME_BYTE_BINDING")
        files[rel] = row["sha256"]
    expected = {name.removeprefix("payload/studio/"): row["sha256"]
               for name, row in manifest["files"].items() if name.startswith("payload/studio/")}
    _need(files == expected, "GT10PC_P10_RUNTIME_CLOSURE")
    snapshot = {"schema": RUNTIME_SCHEMA, "authority": 0, "acceptance": False,
                "active_release": install.snapshot()["active"],
                "manifest_sha256": _sha(install.versions / install.snapshot()["active"] / "manifest.json"),
                "source_closure_sha256": manifest["source_closure_sha256"],
                "files": files}
    (output / "runtime-snapshot.json").write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n",
                                                   encoding="utf-8")
    return runtime, manifest, files


def _installed_setup(output: Path, artifact: Path, trust: Path, trust_sha256: str):
    from studio.package.consumer_install import ConsumerInstall
    from studio.package.trust import load_trust
    keys = load_trust(trust, expected_sha256=trust_sha256)
    install = ConsumerInstall(output / "consumer" / "install", trusted_keys=keys, target="Windows")
    first = install.install(artifact, command_id="p10.install", expected_state_sha256="ABSENT")
    project = output / "consumer" / "project"
    active = install.active_path()
    shutil.copytree(active / "fixtures" / "sample-game", project)
    (project / "owner-save.dat").write_bytes(b"p10-owner-save-before\n")
    lifecycle = install.install_lifecycle(project, artifact, command_id="p10.lifecycle",
                                          expected_state_sha256=install.snapshot()["state_sha256"])
    _need(lifecycle.get("active") == first.get("active"), "GT10PC_P10_LIFECYCLE_ACTIVE")
    return install, project, keys


def run_gt08a(output: Path, runtime: Path, manifest: dict, *, tooling: Path,
              godot_console: Path) -> dict[str, Any]:
    """Run the installed GT-08A implementation's Windows PC rows."""
    mod = _load("gt10pc_p10_installed_gt08a", runtime / "build/ci/gt08a_matrix.py")
    mod.TOOLING = tooling.resolve()
    mod.FIXTURE = (runtime / "fixtures/sample-game").resolve()
    tools = mod.toolchain()
    source_tree = mod.checked_tree(mod.FIXTURE)
    source = mod.closure_hash(source_tree)
    work = output / "gt08a" / "work"
    work.mkdir(parents=True)
    project = work / "fixture Ñé with spaces"
    shutil.copytree(mod.FIXTURE, project)
    mod.write_presets(project)
    template_hashes = mod.stage_templates(Path(tools["templates"]), work / "godot-data")
    env = os.environ.copy()
    env.update({"APPDATA": str(work / "godot-data"), "HOME": str(work / "home"),
               "GODOT_DATA_DIR": str(work / "godot-data"), "GODOT_CACHE_DIR": str(work / "cache"),
               "PYTHONPATH": str(runtime.parent), "PYTHONDONTWRITEBYTECODE": "1"})
    (work / "home").mkdir(); (work / "cache").mkdir()
    rows: list[dict[str, Any]] = [{"id": "W01", "status": "PASS",
        "source_closure": source, "path_has_unicode_space": "fixture Ñé with spaces" in str(project),
        "zdoc_excluded": not any("zdoc" in p for p in source_tree)}]
    _need(rows[0]["path_has_unicode_space"] and rows[0]["zdoc_excluded"], "GT10PC_P10_GT08A_W01")
    win = Path(tools["windows"])
    lock = _json(runtime / "toolchain.lock.json")
    _need(win.resolve() == godot_console.resolve()
          and _sha(win) == lock["godot"]["console_sha256"], "GT10PC_P10_GT08A_BINARY")
    import_dir = output / "gt08a" / "W02"; import_dir.mkdir(parents=True)
    imported = mod.run_process([str(win), "--headless", "--path", str(project), "--editor", "--quit"],
                               project, env, 90, import_dir)
    _need(imported["status"] == "PASS" and not (import_dir / "stderr.txt").read_bytes(),
          "GT10PC_P10_GT08A_W02")
    rows.append({"id": "W02", "status": "PASS", "source_closure": source, "process": imported,
                 "cache_key": mod.cache_key(source, tools, "Windows")})
    export_dir = output / "gt08a" / "W03"; export_dir.mkdir(parents=True)
    export = export_dir / "fixture.exe"
    exported = mod.run_process([str(win), "--headless", "--path", str(project), "--export-release",
                                "Windows Desktop", str(export)], project, env, 180, export_dir)
    _need(exported["status"] == "PASS" and export.is_file() and export.stat().st_size > 0,
          "GT10PC_P10_GT08A_W03")
    rows.append({"id": "W03", "status": "PASS", "source_closure": source, "process": exported,
                 "artifact_sha256": _sha(export), "cache_key": mod.cache_key(source, tools, "Windows")})
    report = {"schema": "hh-gt10pc-p10-gt08a-1", "authority": 0, "acceptance": False,
              "status": "DIAGNOSTIC_PASS", "installed": True, "installed_manifest_sha256": _sha(
                  output / "consumer/install/releases" / manifest.get("_active_release", "") / "manifest.json")
              if manifest.get("_active_release") else None,
              "installed_source_closure_sha256": manifest["source_closure_sha256"],
              "runtime_gt08a_module_sha256": _sha(runtime / "build/ci/gt08a_matrix.py"),
              "fixture_source_closure_sha256": source, "toolchain": tools,
              "template_files": template_hashes, "rows": rows}
    (output / "gt08a.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def _run_catalog_processes(output: Path, runtime: Path, *, blender: Path, godot_gui: Path,
                           env: dict[str, str]) -> dict[str, Any]:
    """Generate fresh Blender/catalog/publication/K8/K10 evidence."""
    py = Path(sys.executable)
    # Keep native Blender/Godot evidence under the installed-runtime boundary
    # but outside the copied payload tree.  The payload-relative path used by
    # r13 nested `.local/reviews` below `installed-runtime/studio`, pushing the
    # Windows path past Blender's legacy MAX_PATH handling; Blender then saw
    # its already-created output directory as missing.  This shorter sibling
    # root preserves the runtime binding verifier while remaining accessible
    # to the pinned native binary.
    review = runtime.parent / "reviews"
    review.mkdir(parents=True, exist_ok=True)
    content_id = "gt09-content-p10-" + output.name[-12:]
    content = review / content_id
    blender_cmd = [str(py), "-B", str(runtime / "tests/conformance/run_gt09_blender_content.py"),
                   "--run-id", content_id, "--output", str(content), "--binary", str(blender)]
    receipts = {"blender": _child(output / "children", blender_cmd, cwd=runtime.parent,
                                   env=env, timeout=240, label="blender-content")}
    content_result = _json(content / "result.json")
    _need(_clean(receipts["blender"]) and content_result.get("status") == "DIAGNOSTIC_PASS",
          "GT10PC_P10_BLENDER")
    content_publication = Path(content_result.get("publication", {}).get("published_root", ""))
    _need(content_publication.is_absolute() and content_publication.is_dir(),
          "GT10PC_P10_BLENDER_PUBLICATION")
    registered: dict[str, Path] = {}
    for fixture in ("arena", "room"):
        rid = "o2-registered-authoring-" + output.name[-12:] + "-" + fixture
        root = review / rid
        command = [str(py), "-B", str(runtime / "tests/godot/run_registered_authoring_probe.py"),
                   "--run-id", rid, "--godot", str(godot_gui), "--blender-published", str(content),
                   "--fixture", fixture]
        key = "registered-" + fixture
        receipts[key] = _child(output / "children", command, cwd=runtime.parent, env=env,
                               timeout=300, label=key)
        registered_result = _json(root / "registered-owner-result.json")
        _need(_clean(receipts[key]) and registered_result.get("status") == "DIAGNOSTIC_PASS",
              "GT10PC_P10_REGISTERED_" + fixture.upper())
        registered[fixture] = root
    pubs: dict[str, Path] = {}
    for fixture, runtime_fixture, option in (("arena", "gameplay_arena_physics", "arena"),
                                               ("room", "gameplay_source_room_3d_native", "room")):
        rid = "o2-publication-gt10pc-p10-" + output.name[-12:] + "-" + fixture
        root = review / rid
        command = [str(py), "-B", str(runtime / "tests/godot/run_gameplay_publication_probe.py"),
                   "--run-id", rid, "--fixture", runtime_fixture,
                   "--blender-content-published", str(content_publication)]
        if option == "arena":
            owner = _json(registered["arena"] / "registered-owner-result.json")
            catalog = review / owner["native_run_id"]
            command += ["--catalog-arena", str(catalog), "--registered-arena", str(registered["arena"])]
        else:
            owner = _json(registered["room"] / "registered-owner-result.json")
            catalog = review / owner["native_run_id"]
            command += ["--catalog-room", str(catalog), "--registered-room", str(registered["room"])]
        key = "publication-" + fixture
        receipts[key] = _child(output / "children", command, cwd=runtime.parent, env=env,
                               timeout=300, label=key)
        _need(_clean(receipts[key]) and _json(root / "result.json").get("status") == "DIAGNOSTIC_PASS",
              "GT10PC_P10_PUBLICATION_" + fixture.upper())
        pubs[fixture] = root
    report_path = output / "k10-conformance.json"
    command = [str(py), "-B", str(runtime / "tests/conformance/gt09_fixture_conformance.py"),
               "--arena", str(pubs["arena"]), "--room", str(pubs["room"]), "--output", str(report_path)]
    receipts["conformance"] = _child(output / "children", command, cwd=runtime.parent, env=env,
                                     timeout=120, label="k10-conformance")
    conformance = _json(report_path)
    _need(_clean(receipts["conformance"]) and conformance.get("status") == "CANDIDATE_PASS",
          "GT10PC_P10_K8_K10_CONFORMANCE")
    return {"status": "DIAGNOSTIC_PASS", "authority": 0, "acceptance": False,
            "blender": str(content), "registered": {k: str(v) for k, v in registered.items()},
            "publications": {k: str(v) for k, v in pubs.items()},
            "conformance": str(report_path), "conformance_sha256": _sha(report_path),
            "receipts": receipts}


def run_p10(output: Path, artifact: Path, *, trust: Path, trust_sha256: str,
            tooling: Path, godot_console: Path, godot_gui: Path, blender: Path,
            phase: str = "all") -> dict[str, Any]:
    _need(not output.exists(), "GT10PC_P10_OUTPUT_EXISTS")
    output.mkdir(parents=True)
    install, project, _keys = _installed_setup(output, artifact, trust, trust_sha256)
    active_release = install.snapshot()["active"]
    project_before = _ledger(project)
    runtime, manifest, _files = _runtime_snapshot(install, output)
    manifest = dict(manifest); manifest["_active_release"] = active_release
    result: dict[str, Any] = {"schema": SCHEMA, "authority": 0, "acceptance": False,
        "mode": "DIAGNOSTIC", "status": "DIAGNOSTIC_PASS", "active_release": active_release,
        "manifest_sha256": _sha(install.versions / active_release / "manifest.json"),
        "source_closure_sha256": manifest["source_closure_sha256"], "phase": phase, "rows": {}}
    if phase in ("all", "gt08a"):
        result["rows"]["GT08A_PC"] = run_gt08a(output, runtime, manifest, tooling=tooling,
                                                godot_console=godot_console)
    if phase in ("all", "catalog"):
        env = _environment(runtime.parent)
        result["rows"]["K8_K10"] = _run_catalog_processes(output, runtime, blender=blender,
                                                           godot_gui=godot_gui, env=env)
    project_after = _ledger(project)
    _need(project_before == project_after, "GT10PC_P10_PROJECT_READBACK")
    result["project_before_sha256"] = hashlib.sha256(
        json.dumps(project_before, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    result["project_after_sha256"] = hashlib.sha256(
        json.dumps(project_after, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    (output / "p10.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def verify(path: Path) -> dict[str, Any]:
    path = path.resolve(); report = _json(path / "p10.json")
    _need(report.get("schema") == SCHEMA and report.get("authority") == 0
          and report.get("acceptance") is False and report.get("status") == "DIAGNOSTIC_PASS",
          "GT10PC_P10_REPORT")
    phase = report.get("phase")
    _need(phase in ("gt08a", "catalog", "all"), "GT10PC_P10_PHASE")
    expected_rows = {"gt08a": {"GT08A_PC"}, "catalog": {"K8_K10"},
                     "all": {"GT08A_PC", "K8_K10"}}[phase]
    _need(isinstance(report.get("rows"), dict)
          and set(report["rows"]) == expected_rows, "GT10PC_P10_ROW_SET")
    _need(isinstance(report.get("active_release"), str)
          and len(report["active_release"]) == 64
          and all(c in "0123456789abcdef" for c in report["active_release"]),
          "GT10PC_P10_ACTIVE_RELEASE")
    _need(isinstance(report.get("manifest_sha256"), str)
          and len(report["manifest_sha256"]) == 64
          and all(c in "0123456789abcdef" for c in report["manifest_sha256"]),
          "GT10PC_P10_MANIFEST_DIGEST")
    manifest_path = path / "consumer" / "install" / "releases" / report["active_release"] / "manifest.json"
    _need(manifest_path.is_file() and _sha(manifest_path) == report["manifest_sha256"],
          "GT10PC_P10_MANIFEST_READBACK")
    manifest = _json(manifest_path)
    _need(manifest.get("source_closure_sha256") == report.get("source_closure_sha256"),
          "GT10PC_P10_MANIFEST_SOURCE_BINDING")
    _need(isinstance(report.get("project_before_sha256"), str)
          and report.get("project_before_sha256") == report.get("project_after_sha256")
          and len(report["project_before_sha256"]) == 64,
          "GT10PC_P10_PROJECT_READBACK")
    snapshot = _json(path / "runtime-snapshot.json")
    _need(snapshot.get("schema") == RUNTIME_SCHEMA and snapshot.get("authority") == 0
          and snapshot.get("acceptance") is False and snapshot.get("active_release") == report.get("active_release")
          and snapshot.get("manifest_sha256") == report.get("manifest_sha256")
          and snapshot.get("source_closure_sha256") == report.get("source_closure_sha256"),
          "GT10PC_P10_RUNTIME_REPORT")
    runtime = path / "installed-runtime" / "studio"
    expected_files = snapshot.get("files")
    _need(isinstance(expected_files, dict) and expected_files
          and _runtime_files(runtime) == expected_files,
          "GT10PC_P10_RUNTIME_CLOSURE_READBACK")
    if "GT08A_PC" in report.get("rows", {}):
        gt = _json(path / "gt08a.json")
        _need(gt.get("status") == "DIAGNOSTIC_PASS" and gt.get("authority") == 0
              and gt.get("acceptance") is False
              and [row.get("id") for row in gt.get("rows", [])] == ["W01", "W02", "W03"]
              and all(row.get("status") == "PASS" for row in gt["rows"])
              and gt.get("installed_manifest_sha256") == report["manifest_sha256"]
              and gt.get("installed_source_closure_sha256") == report["source_closure_sha256"],
              "GT10PC_P10_GT08A_REPORT")
        _need(isinstance(gt.get("runtime_gt08a_module_sha256"), str)
              and _sha(runtime / "build/ci/gt08a_matrix.py") == gt["runtime_gt08a_module_sha256"],
              "GT10PC_P10_GT08A_BINDING")
        for row in gt["rows"][1:]:
            process = row.get("process")
            _need(isinstance(process, dict) and process.get("status") == "PASS"
                  and process.get("exit_code") == 0 and process.get("timed_out") is False
                  and process.get("tree_verified") is True,
                  "GT10PC_P10_GT08A_PROCESS")
    if "K8_K10" in report.get("rows", {}):
        row = report["rows"]["K8_K10"]
        _need(row.get("status") == "DIAGNOSTIC_PASS" and row.get("authority") == 0
              and row.get("acceptance") is False and _json(path / "k10-conformance.json").get("status") == "CANDIDATE_PASS",
              "GT10PC_P10_K8_K10_REPORT")
        children = path / "children"
        receipts = row.get("receipts")
        _need(isinstance(receipts, dict)
              and set(receipts) == {"blender", "registered-arena", "registered-room",
                                    "publication-arena", "publication-room", "conformance"},
              "GT10PC_P10_RECEIPT_SET")
        for receipt in receipts.values():
            _verify_child_receipt(children, receipt)
        runtime_root = path / "installed-runtime"
        blender_root = Path(row.get("blender", ""))
        _need(_under(blender_root, runtime_root)
              and _json(blender_root / "result.json").get("status") == "DIAGNOSTIC_PASS"
              and _json(blender_root / "result.json").get("public_ack") is False,
              "GT10PC_P10_BLENDER_BINDING")
        for fixture in ("arena", "room"):
            registered_root = Path(row["registered"][fixture])
            _need(_under(registered_root, runtime_root), "GT10PC_P10_REGISTERED_ROOT")
            registered_doc = _json(registered_root / "registered-owner-result.json")
            _need(registered_doc.get("status") == "DIAGNOSTIC_PASS"
                  and registered_doc.get("public_ack") is False
                  and registered_doc.get("receipt", {}).get("native_process", {}).get("exit_code") == 0,
                  "GT10PC_P10_REGISTERED_BINDING")
        for name in ("arena", "room"):
            root = Path(row["publications"][name])
            _need(_under(root, runtime_root), "GT10PC_P10_PUBLICATION_ROOT")
            result = _json(root / "result.json")
            _need(result.get("status") == "DIAGNOSTIC_PASS" and result.get("authority") == 0
                  and result.get("public_ack") is False and result.get("native_fixture_observed") is True,
                  "GT10PC_P10_PUBLICATION_BINDING")
        conformance = path / "k10-conformance.json"
        _need(_sha(conformance) == row.get("conformance_sha256"),
              "GT10PC_P10_CONFORMANCE_HASH")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--trust", type=Path, required=True)
    parser.add_argument("--trust-sha256", required=True)
    parser.add_argument("--tooling", type=Path, required=True)
    parser.add_argument("--godot-console", type=Path, required=True)
    parser.add_argument("--godot-gui", type=Path, required=True)
    parser.add_argument("--blender", type=Path, required=True)
    parser.add_argument("--phase", choices=("all", "gt08a", "catalog"), default="all")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(argv)
    if args.verify_only:
        verify(args.output)
        return 0
    result = run_p10(args.output, args.artifact, trust=args.trust, trust_sha256=args.trust_sha256,
                     tooling=args.tooling, godot_console=args.godot_console, godot_gui=args.godot_gui,
                     blender=args.blender, phase=args.phase)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
