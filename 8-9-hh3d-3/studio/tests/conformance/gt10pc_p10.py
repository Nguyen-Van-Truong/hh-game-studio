"""GT-10-PC P10 installed-artifact regression producer.

P10 is deliberately separate from the historical GT-09 matrix.  It installs
the signed package into a disposable consumer, snapshots the exact installed
``payload/studio`` tree, and executes the GT-08A PC rows plus fresh K8/K10
catalog publications from that snapshot.  Phase ``linux`` is a second start of
the pinned GT-10-PC container (``purpose=p10``) for L01/L02 and the K10 smoke
trace.  No retained GT-09 evidence is used
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


def verify_engine_host(directory: Path, label: str, code: str = "GT10PC_P10_ENGINE_HOST") -> dict[str, Any]:
    """Re-read ``*-host.json`` and rehash the streams named by the receipt."""
    host = _json(directory / (label + "-host.json"))
    receipt = _json(directory / (label + "-receipt.json"))
    pid = host.get("target_pid")
    _need(type(pid) is int and pid > 0 and receipt.get("target_pid") == pid, code)
    _need(host.get("exit_code") == 0 and receipt.get("exit_code") == 0, code)
    _need(receipt.get("wrapper_exit_code") == 0 and receipt.get("timed_out") is False
          and receipt.get("tree_verified") is True, code)
    for field in ("stdout", "stderr"):
        name = receipt.get(field)
        _need(isinstance(name, str) and name == label + "-" + field + ".txt", code)
        stream = directory / name
        _need(stream.is_file() and _sha(stream) == receipt.get(field + "_sha256"), code)
    _need(not (directory / (label + "-stderr.txt")).read_bytes(), code + "_STDERR")
    return host


def _simulation_world(world: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in world.items() if not str(key).startswith("input_")}


def _held_interval(inputs: list[dict[str, Any]], states: list[dict[str, Any]], key: int,
                   *, require_sample: bool) -> None:
    press = next((edge for edge in inputs if edge.get("key") == key and edge.get("state") == "pressed"), None)
    release = next((edge for edge in inputs
                    if edge.get("key") == key and edge.get("state") == "released"
                    and press is not None and type(edge.get("wall_tick")) is int
                    and type(press.get("wall_tick")) is int and edge["wall_tick"] > press["wall_tick"]), None)
    _need(press is not None and release is not None, "GT10PC_P10_K10_HELD_EDGE")
    start, stop = press["wall_tick"], release["wall_tick"]
    middles = [state for state in states if type(state.get("wall_tick")) is int
               and start < state["wall_tick"] < stop]
    if require_sample:
        _need(bool(middles), "GT10PC_P10_K10_HELD_SAMPLE")
    for state in middles:
        held = state.get("held_keys")
        _need(isinstance(held, list) and key in held, "GT10PC_P10_K10_HELD_KEYS")


def verify_k10_trace(stdout_text: str) -> None:
    """Check a fixture-lifecycle smoke log. Does not accept a 15-minute playtest pack."""
    from studio.tests.godot.fixture_lifecycle_manifest import parse_log
    summary, states, inputs = parse_log(stdout_text)
    _need(summary.get("seed") == 90127, "GT10PC_P10_K10_SEED")
    _need(summary.get("mode") == "smoke", "GT10PC_P10_K10_MODE")
    _need(summary.get("freeze_errors") == 0, "GT10PC_P10_K10_FREEZE")
    _need(type(summary.get("pause_frames")) is int and summary["pause_frames"] > 1,
          "GT10PC_P10_K10_PAUSE_FRAMES")
    _need(summary.get("lifecycle_complete") is True, "GT10PC_P10_K10_COMPLETE")
    counts = summary.get("counts")
    _need(isinstance(counts, dict), "GT10PC_P10_K10_COUNTS")
    for command in ("start", "pause", "resume", "restart", "quit"):
        _need(type(counts.get(command)) is int and counts[command] >= 1, "GT10PC_P10_K10_COUNTS")
    for state in states:
        _need(state.get("seed") == 90127, "GT10PC_P10_K10_STATE_SEED")
    pressed: set[int] = set()
    for edge in inputs:
        key = edge.get("key")
        state_name = edge.get("state")
        _need(type(key) is int and state_name in ("pressed", "released"), "GT10PC_P10_K10_EDGE")
        if state_name == "pressed" and key not in pressed:
            pressed.add(key)
        elif state_name == "released" and key in pressed:
            pressed.remove(key)
        else:
            _need(False, "GT10PC_P10_K10_EDGE_PAIR")
    # KEY_D is held across many physics ticks. KEY_E is a one-tick press/release.
    _held_interval(inputs, states, 68, require_sample=True)
    _held_interval(inputs, states, 69, require_sample=False)
    events = [state.get("event") for state in states]
    for name in ("menu", "start", "pause", "resume", "quit"):
        _need(name in events, "GT10PC_P10_K10_EVENT")
    pauses = [state for state in states if state.get("event") == "pause"]
    _need(pauses, "GT10PC_P10_K10_PAUSE")
    pause = pauses[0]
    resumes = [state for state in states[states.index(pause) + 1:] if state.get("event") == "resume"]
    _need(resumes, "GT10PC_P10_K10_RESUME")
    resume = resumes[0]
    _need(pause.get("tree_paused") is True and resume.get("tree_paused") is False,
          "GT10PC_P10_K10_TREE_PAUSED")
    _need(type(pause.get("wall_tick")) is int and type(resume.get("wall_tick")) is int
          and resume["wall_tick"] > pause["wall_tick"], "GT10PC_P10_K10_WALL_TICK")
    pause_world = pause.get("world")
    resume_world = resume.get("world")
    _need(isinstance(pause_world, dict) and isinstance(resume_world, dict)
          and _simulation_world(pause_world) == _simulation_world(resume_world),
          "GT10PC_P10_K10_PAUSE_WORLD")


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
    imported = _child(import_dir, [str(win), "--headless", "--path", str(project), "--editor", "--quit"],
                      cwd=project, env=env, timeout=90, label="w02")
    _need(_clean(imported), "GT10PC_P10_GT08A_W02")
    verify_engine_host(import_dir, "w02", "GT10PC_P10_GT08A_W02_HOST")
    rows.append({"id": "W02", "status": "PASS", "source_closure": source, "process": imported,
                 "cache_key": mod.cache_key(source, tools, "Windows")})
    export_dir = output / "gt08a" / "W03"; export_dir.mkdir(parents=True)
    export = export_dir / "fixture.exe"
    exported = _child(export_dir, [str(win), "--headless", "--path", str(project), "--export-release",
                                   "Windows Desktop", str(export)],
                      cwd=project, env=env, timeout=180, label="w03")
    _need(_clean(exported) and export.is_file() and export.stat().st_size > 0,
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
    # Blender/OpenImageIO canonicalizes output paths on Windows, so its fresh
    # content producer uses a short sibling root.  The registered authoring
    # and gameplay probes deliberately write through the installed runtime's
    # public `.local/reviews` route; keep that root explicit instead of reading
    # a guessed sibling path after the producer succeeds.
    blender_review = runtime.parent / "reviews"
    blender_review.mkdir(parents=True, exist_ok=True)
    review = runtime / ".local" / "reviews"
    review.mkdir(parents=True, exist_ok=True)
    content_id = "gt09-content-p10-" + output.name[-12:]
    content = blender_review / content_id
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
                   "--run-id", rid, "--godot", str(godot_gui),
                   "--blender-published", str(content_publication),
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
            "k10_trace": "linux-phase", "receipts": receipts}


def _extract_sample_game(artifact: Path, trust: Path, trust_sha256: str, dest: Path) -> None:
    """Write the package's sample-game bytes so verify can hash them itself."""
    from studio.package.trust import load_trust
    from studio.package.release_contract import verify_package
    keys = load_trust(trust, expected_sha256=trust_sha256)
    package = verify_package(artifact, trusted_keys=keys, target="Linux-headless", expected_version="0.1.0")
    prefix = "payload/studio/fixtures/sample-game/"
    wrote = False
    for name, data in package["members"].items():
        if not name.startswith(prefix):
            continue
        relative = name[len(prefix):]
        _need(relative and ".." not in Path(relative).parts and "\\" not in relative,
              "GT10PC_P10_SAMPLE_GAME_PATH")
        target = dest / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        wrote = True
    _need(wrote, "GT10PC_P10_SAMPLE_GAME_MISSING")


def _run_linux_phase(output: Path, artifact: Path, trust: Path, trust_sha256: str) -> dict[str, Any]:
    from studio.tests.conformance.gt10pc_linux_producer import run_linux
    _need(not output.exists(), "GT10PC_P10_OUTPUT_EXISTS")
    output.mkdir(parents=True)
    _extract_sample_game(artifact, trust, trust_sha256, output / "sample-game")
    started = time.time()
    receipt = run_linux(output / "linux", artifact=artifact, trust=trust, trust_sha256=trust_sha256,
                        purpose="p10")
    result = {"schema": SCHEMA, "authority": 0, "acceptance": False, "mode": "DIAGNOSTIC",
              "status": "DIAGNOSTIC_PASS", "phase": "linux",
              "active_release": receipt["manifest_sha256"],
              "manifest_sha256": receipt["manifest_sha256"],
              "source_closure_sha256": receipt["source_closure_sha256"],
              "rows": {"GT08A_LINUX": {"status": "DIAGNOSTIC_PASS", "authority": 0, "acceptance": False,
                                       "container": "linux",
                                       "duration_s": round(time.time() - started, 3)}}}
    (output / "p10.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def run_p10(output: Path, artifact: Path, *, trust: Path, trust_sha256: str,
            tooling: Path, godot_console: Path, godot_gui: Path, blender: Path,
            phase: str = "all") -> dict[str, Any]:
    if phase == "linux":
        return _run_linux_phase(output, artifact, trust, trust_sha256)
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


def _verify_linux_phase(path: Path, report: dict[str, Any]) -> None:
    from studio.tests.conformance.gt10pc_linux_verify import verify_p10_container
    digest = report.get("manifest_sha256")
    _need(isinstance(digest, str) and len(digest) == 64 and digest == report.get("active_release")
          and all(c in "0123456789abcdef" for c in digest), "GT10PC_P10_LINUX_MANIFEST")
    linux = path / "linux"
    verify_p10_container(linux)
    native = linux / "native"
    closure = _json(native / "gt08a" / "closure.json")
    module = _load("gt10pc_p10_closure", ROOT / "build/ci/gt08a_matrix.py")
    tree = module.checked_tree(path / "sample-game")
    _need(closure.get("files") == tree and module.closure_hash(tree) == closure.get("source_closure"),
          "GT10PC_P10_LINUX_CLOSURE")
    document = _json(native / "linux.json")
    _need(document.get("schema") == "hh-gt10pc-linux-p10-1" and document.get("purpose") == "p10"
          and document.get("artifact_sha256") == _json(linux / "producer.json").get("artifact_sha256"),
          "GT10PC_P10_LINUX_NATIVE")
    rows = document.get("rows")
    _need(isinstance(rows, list) and [row.get("id") for row in rows] == ["L01", "L02"]
          and all(row.get("status") == "PASS" and row.get("source_closure") == closure.get("source_closure")
                  for row in rows), "GT10PC_P10_LINUX_ROWS")
    verify_engine_host(native / "gt08a" / "L01", "l01", "GT10PC_P10_L01_HOST")
    l01_argv = _json(native / "gt08a" / "L01" / "l01-receipt.json").get("argv")
    _need(isinstance(l01_argv, list) and l01_argv[:1] == ["Godot_v4.7.2-stable_linux.x86_64"]
          and "--quit-after" in l01_argv and "1" in l01_argv, "GT10PC_P10_L01_ARGV")
    l02_dir = native / "gt08a" / "L02"
    verify_engine_host(l02_dir, "l02", "GT10PC_P10_L02_HOST")
    l02_argv = _json(l02_dir / "l02-receipt.json").get("argv")
    _need(isinstance(l02_argv, list) and l02_argv[:1] == ["Godot_v4.7.2-stable_linux.x86_64"]
          and "--export-release" in l02_argv and "Linux/X11" in l02_argv, "GT10PC_P10_L02_ARGV")
    _need(rows[1].get("editor_os") == "linux" and "Windows editor" in str(rows[1].get("delta")),
          "GT10PC_P10_L02_DELTA")
    artifact = l02_dir / "fixture.x86_64"
    _need(artifact.is_file() and artifact.stat().st_size > 0
          and _sha(artifact) == rows[1].get("artifact_sha256"), "GT10PC_P10_L02_ARTIFACT")
    _need(document.get("k10_fixtures") == ["gt09-arena", "gt09-room"], "GT10PC_P10_K10_FIXTURES")
    for fixture in ("gt09-arena", "gt09-room"):
        folder = native / "k10" / fixture
        verify_engine_host(folder, "godot", "GT10PC_P10_K10_HOST")
        argv = _json(folder / "godot-receipt.json").get("argv")
        _need(isinstance(argv, list) and "--max-fps" in argv and "60" in argv
              and "--fixture-lifecycle-smoke" in argv, "GT10PC_P10_K10_ARGV")
        verify_k10_trace((folder / "godot-stdout.txt").read_text(encoding="utf-8"))


def verify(path: Path) -> dict[str, Any]:
    path = path.resolve(); report = _json(path / "p10.json")
    _need(report.get("schema") == SCHEMA and report.get("authority") == 0
          and report.get("acceptance") is False and report.get("status") == "DIAGNOSTIC_PASS",
          "GT10PC_P10_REPORT")
    phase = report.get("phase")
    _need(phase in ("gt08a", "catalog", "all", "linux"), "GT10PC_P10_PHASE")
    expected_rows = {"gt08a": {"GT08A_PC"}, "catalog": {"K8_K10"}, "linux": {"GT08A_LINUX"},
                     "all": {"GT08A_PC", "K8_K10"}}[phase]
    _need(isinstance(report.get("rows"), dict)
          and set(report["rows"]) == expected_rows, "GT10PC_P10_ROW_SET")
    if phase == "linux":
        _verify_linux_phase(path, report)
        return report
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
        verify_engine_host(path / "gt08a" / "W02", "w02", "GT10PC_P10_GT08A_W02_HOST")
        w03_dir = path / "gt08a" / "W03"
        verify_engine_host(w03_dir, "w03", "GT10PC_P10_GT08A_W03_HOST")
        executable = w03_dir / "fixture.exe"
        _need(executable.is_file() and executable.stat().st_size > 0
              and _sha(executable) == gt["rows"][2].get("artifact_sha256"),
              "GT10PC_P10_GT08A_W03_ARTIFACT")
    if "K8_K10" in report.get("rows", {}):
        # The accepted GT-09 K8/K9/K10 validators, applied to the fresh installed-copy run.
        from studio.tests.conformance.run_gt09_matrix import (
            _conformance_semantics, _publication_semantics, _registered_semantics)
        row = report["rows"]["K8_K10"]
        _need(row.get("status") == "DIAGNOSTIC_PASS" and row.get("authority") == 0
              and row.get("acceptance") is False and row.get("k10_trace") == "linux-phase",
              "GT10PC_P10_K8_K10_REPORT")
        children = path / "children"
        receipts = row.get("receipts")
        labels = {"blender": "blender-content", "registered-arena": "registered-arena",
                  "registered-room": "registered-room", "publication-arena": "publication-arena",
                  "publication-room": "publication-room", "conformance": "k10-conformance"}
        _need(isinstance(receipts, dict) and set(receipts) == set(labels), "GT10PC_P10_RECEIPT_SET")
        for key, label in labels.items():
            _need(isinstance(receipts[key], dict) and receipts[key].get("label") == label
                  and _json(children / (label + "-receipt.json")) == receipts[key],
                  "GT10PC_P10_CATALOG_RECEIPT")
            verify_engine_host(children, label, "GT10PC_P10_CATALOG_HOST")
        runtime_root = path / "installed-runtime"
        blender_root = Path(row.get("blender", ""))
        _need(_under(blender_root, runtime_root)
              and _json(blender_root / "result.json").get("status") == "DIAGNOSTIC_PASS"
              and _json(blender_root / "result.json").get("public_ack") is False,
              "GT10PC_P10_BLENDER_BINDING")
        closures = set()
        for fixture in ("arena", "room"):
            registered_root = Path(row["registered"][fixture])
            publication_root = Path(row["publications"][fixture])
            _need(_under(registered_root, runtime_root) and _under(publication_root, runtime_root),
                  "GT10PC_P10_CATALOG_ROOT")
            _need(_publication_semantics(publication_root, fixture=fixture),
                  "GT10PC_P10_PUBLICATION_SEMANTICS")
            _need(_registered_semantics(publication_root, fixture=fixture),
                  "GT10PC_P10_REGISTERED_SEMANTICS")
            result = _json(publication_root / "result.json")
            handoff = result["catalog_handoff" if fixture == "arena" else "catalog_room_handoff"]
            _need(Path(handoff["registered_root"]).resolve() == registered_root.resolve(),
                  "GT10PC_P10_REGISTERED_HANDOFF")
            closures.add(result.get("source_closure_sha256"))
        conformance = path / "k10-conformance.json"
        _need(len(closures) == 1 and _conformance_semantics(conformance, closure=next(iter(closures))),
              "GT10PC_P10_K8_K10_CONFORMANCE")
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
    parser.add_argument("--phase", choices=("all", "gt08a", "catalog", "linux"), default="all")
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
