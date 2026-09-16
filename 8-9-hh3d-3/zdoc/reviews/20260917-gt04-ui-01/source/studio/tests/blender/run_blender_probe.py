"""Bounded trusted GT04 fixture capture. Output must be a new review directory."""
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
from datetime import datetime, timezone

STUDIO = Path(__file__).resolve().parents[2]
BINARY_SHA256 = "8f7a131ad8bc148edc218b334f07d92a57f5a357fa66d913b290537fd8353c06"
REQUIRED = {
    "edit": ("actual_pinned_background", "automatic_python_disabled", "empty_owned_fixture", "fresh_checkpoint",
             "create_native_mesh", "create_preserves_empty_selection", "duplicate_create_original_receipt",
             "duplicate_create_no_extra_object", "conflicting_id_no_effect", "stale_revision_no_effect",
             "rejections_preserve_revision", "mode_drift_rejected", "inspect_restores_edit_mode",
             "create_from_edit_restores_context", "transform_from_edit_restores_context", "transform_native_readback",
             "duplicate_transform_original_receipt", "thread_access_rejected_before_bpy",
             "manual_transform_invalidates_revision", "manual_change_preserved", "embedded_text_rejected",
             "duplicate_stable_id_rejected", "stop_rejects_new_mutation", "stop_keeps_original_receipt",
             "no_public_ack", "save_fresh_owned_fixture", "save_preserves_semantic_revision"),
    "reopen": ("actual_pinned_background", "automatic_python_disabled", "reopen_exact_file_hash", "reopen_native_finished",
               "reopen_exact_scene_revision", "reopen_exact_mesh_transform", "reopen_two_stable_meshes",
               "reopen_no_external_dependencies", "reopen_no_public_ack"),
    "checkpoint": ("actual_pinned_background", "automatic_python_disabled", "reopen_exact_file_hash", "reopen_native_finished",
                   "checkpoint_reopens_empty", "reopen_no_external_dependencies", "reopen_no_public_ack"),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    spec = importlib.util.spec_from_file_location("gt04_frozen_bootstrap_" + sha(path), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sources(root):
    paths = []
    for directory in ("blender-addon", "tests/blender"):
        paths.extend(path for path in (root / directory).rglob("*") if path.is_file() and "__pycache__" not in path.parts)
    paths.extend(root / path for path in ("build/bootstrap/run_fixture.py", "toolchain.lock.json"))
    return {path.relative_to(root).as_posix(): sha(path) for path in sorted(paths)}


def require_host(run, output):
    host = json.loads((output / run["host"]).read_text(encoding="utf-8"))
    if (type(host.get("exit_code")) is not int or host["exit_code"] != 0 or
            type(host.get("target_pid")) is not int or host["target_pid"] <= 0 or
            run["exit_code"] != host["exit_code"] or run["target_pid"] != host["target_pid"] or
            run["wrapper_exit_code"] != 0 or run["timed_out"] is not False or run["tree_verified"] is not True):
        raise ValueError("actual host/tree result is not clean")


def evaluate(phase, report, stdout):
    if (report.get("schema") != "HH-GT04-NATIVE-PROBE-1" or report.get("phase") != phase or
            report.get("actual_blender") is not True or report.get("version") != "5.2.1 LTS" or
            report.get("ok") is not True or report.get("public_ack") is not False or report.get("acceptance") is not False):
        raise ValueError("wrong native result")
    expected = [{"label": label, "passed": True} for label in REQUIRED[phase]]
    if report.get("checks") != expected:
        raise ValueError("native checks missing/duplicate/false/out of order")
    rows = [json.loads(line.removeprefix("GT04_CHECK ")) for line in stdout.splitlines() if line.startswith("GT04_CHECK ")]
    finals = [json.loads(line.removeprefix("GT04_RESULT ")) for line in stdout.splitlines() if line.startswith("GT04_RESULT ")]
    if rows != expected or finals != [report]:
        raise ValueError("raw markers differ from result")
    if re.search(r"(?i)\b(warning|error|traceback|fatal)\b", stdout):
        raise ValueError("unexpected native diagnostic")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    bootstrap = load(STUDIO / "build/bootstrap/run_fixture.py")
    output = args.output.absolute()
    bootstrap._reject_reparse_ancestors(output)
    reviews = STUDIO.parent / "zdoc/reviews"
    if output.parent.resolve() != reviews.resolve() or not re.fullmatch(r"20260917-gt04-[a-z0-9-]+", output.name):
        raise ValueError("new GT04 review directory required")
    output.mkdir(exist_ok=False)
    report = {"schema": "HH-GT04-FROZEN-PROBE-1", "started_at": datetime.now(timezone.utc).isoformat(),
              "acceptance": False, "public_ack": False, "ok": False, "runs": []}
    try:
        before = sources(STUDIO)
        snapshot = output / "source/studio"
        for relative in before:
            target = snapshot / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(STUDIO / relative, target)
        if sources(snapshot) != before:
            raise ValueError("snapshot differs")
        frozen = load(snapshot / "build/bootstrap/run_fixture.py")
        report.update(source_files=before, source_closure_sha256=frozen.source_closure_sha256(before))
        binary = STUDIO / ".local/tooling/blender-5.2.1-windows-x64/blender.exe"
        bootstrap._reject_reparse_ancestors(binary)
        if sha(binary) != BINARY_SHA256:
            raise ValueError("Blender executable pin mismatch")
        report["binary_sha256"] = BINARY_SHA256
        fixture = output / "fixture"
        fixture.mkdir()
        env = {key: value for key, value in os.environ.items()
               if not key.upper().startswith(("PYTHON", "BLENDER_"))}
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        for key, relative in (("BLENDER_USER_RESOURCES", "blender-user"), ("TEMP", "temp"), ("TMP", "temp")):
            folder = output / relative
            folder.mkdir(exist_ok=True)
            env[key] = str(folder)
        unit = frozen.run_process([sys.executable, "-B", "-m", "unittest", "discover", "-s", str(snapshot / "tests/blender"),
                                   "-p", "test_*.py", "-v"], cwd=snapshot, output=output, timeout=30, label="python", env=env)
        report["runs"].append(unit)
        require_host(unit, output)
        unit_log = (output / unit["stderr"]).read_text(encoding="utf-8")
        match = re.search(r"Ran (\d+) tests in [\d.]+s\s+OK\s*\Z", unit_log)
        if not match or int(match[1]) != 36 or "skipped" in unit_log:
            raise ValueError("unexpected unit test result")
        report["python_tests"] = int(match[1])
        for phase in ("edit", "reopen", "checkpoint"):
            argv = [str(binary), "--background", "--factory-startup", "--disable-autoexec", "--offline-mode",
                    "--threads", "1", "--python-exit-code", "17", "--python", str(snapshot / "tests/blender/blender_probe.py"),
                    "--", "--phase", phase, "--owned-root", str(fixture)]
            run = frozen.run_process(argv, cwd=snapshot, output=output, timeout=60, label=phase, env=env)
            report["runs"].append(run)
            require_host(run, output)
            if (output / run["stderr"]).stat().st_size:
                raise ValueError("nonempty Blender stderr")
            native = json.loads((fixture / (phase + "-result.json")).read_text(encoding="utf-8"))
            evaluate(phase, native, (output / run["stdout"]).read_text(encoding="utf-8"))
            report.setdefault("native_checks", {})[phase] = len(native["checks"])
        expected = json.loads((fixture / "expected.json").read_text(encoding="utf-8"))
        for key in ("saved", "checkpoint"):
            artifact = expected[key]
            actual = fixture / artifact["name"]
            if sha(actual) != artifact["sha256"] or actual.stat().st_size != artifact["size_bytes"]:
                raise ValueError("saved artifact changed")
        report["source_unchanged"] = sources(STUDIO) == before
        report["snapshot_unchanged"] = sources(snapshot) == before
        report["binary_unchanged"] = sha(binary) == BINARY_SHA256
        if not all(report[key] for key in ("source_unchanged", "snapshot_unchanged", "binary_unchanged")):
            raise ValueError("source or executable changed")
        report["saved"] = expected["saved"]
        report["checkpoint"] = expected["checkpoint"]
        report["ok"] = True
    except BaseException as exc:
        report["failure"] = type(exc).__name__ + ": " + str(exc)
    finally:
        report["completed_at"] = datetime.now(timezone.utc).isoformat()
        report["artifacts"] = {path.relative_to(output).as_posix(): sha(path) for path in sorted(output.rglob("*"))
                               if path.is_file() and "__pycache__" not in path.parts}
        (output / "result.json").write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report.get(key) for key in ("ok", "failure", "source_closure_sha256", "python_tests", "native_checks")}, sort_keys=True))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
