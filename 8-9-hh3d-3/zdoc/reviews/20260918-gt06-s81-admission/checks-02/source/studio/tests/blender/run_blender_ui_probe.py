"""Frozen Blender UI proof followed by the unchanged background native checks."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import sys
import importlib.util

STUDIO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("gt04_ui_background_runner", Path(__file__).with_name("run_blender_probe.py"))
bg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bg)
EXPECTED_TESTS = 40
REQUIRED = {
    "edit": ("actual_pinned_gui", "actual_window_event_loop", "automatic_python_disabled", "empty_owned_ui_fixture",
             "native_gui_checkpoint", "enqueue_has_no_native_effect", "timer_create_native_mesh", "create_restores_context",
             "native_undo_removes_mesh", "duplicate_undo_original_receipt", "duplicate_undo_no_second_effect",
             "native_redo_restores_mesh", "duplicate_create_original_receipt", "duplicate_create_no_extra_mesh",
             "create_preserves_active_selection", "transform_native_readback", "transform_restores_context",
             "native_undo_exact_transform", "native_redo_exact_transform", "inspect_keeps_edit_mesh",
             "edit_transform_restores_context", "native_undo_edit_transform", "native_redo_edit_transform",
             "edit_create_restores_context", "native_two_step_edit_undo", "native_two_step_edit_redo", "new_edit_discards_redo_branch",
             "queue_deadline_no_effect", "stale_revision_rejected_no_effect", "native_gui_save_exact_revision",
             "duplicate_save_original_receipt", "save_refuses_overwrite", "stop_cancels_queued_no_effect",
             "stop_preserves_receipt", "no_public_ack", "owned_timer_unregistered"),
    "reopen": ("actual_pinned_gui", "actual_window_event_loop", "automatic_python_disabled", "reopen_exact_file_hash",
               "native_gui_open_finished", "reopen_exact_semantic_revision", "reopen_exact_mesh_transform",
               "reopen_exact_active_selection", "reopen_no_public_ack"),
    "checkpoint": ("actual_pinned_gui", "actual_window_event_loop", "automatic_python_disabled", "reopen_exact_file_hash",
                   "native_gui_open_finished", "checkpoint_exact_empty_scene", "reopen_no_public_ack"),
}


def evaluate(phase, report, stdout):
    if (report.get("schema") != "HH-GT04-UI-PROBE-1" or report.get("phase") != phase or
            report.get("actual_blender_gui") is not True or report.get("version") != "5.2.1 LTS" or
            report.get("ok") is not True or report.get("public_ack") is not False or report.get("acceptance") is not False):
        raise ValueError("wrong native GUI result")
    expected = [{"label": label, "passed": True} for label in REQUIRED[phase]]
    if report.get("checks") != expected:
        raise ValueError("native GUI checks missing/duplicate/false/out of order")
    rows = [json.loads(line.removeprefix("GT04_UI_CHECK ")) for line in stdout.splitlines() if line.startswith("GT04_UI_CHECK ")]
    finals = [json.loads(line.removeprefix("GT04_UI_RESULT ")) for line in stdout.splitlines() if line.startswith("GT04_UI_RESULT ")]
    if rows != expected or finals != [report]:
        raise ValueError("raw GUI markers differ from result")
    if re.search(r"(?i)\b(warning|error|traceback|fatal)\b", stdout):
        raise ValueError("unexpected native GUI diagnostic")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    bootstrap = bg.load(STUDIO / "build/bootstrap/run_fixture.py")
    output = args.output.absolute()
    bootstrap._reject_reparse_ancestors(output)
    if output.parent.resolve() != (STUDIO.parent / "zdoc/reviews").resolve() or not re.fullmatch(r"20260917-gt04-ui-[a-z0-9-]+", output.name):
        raise ValueError("fresh GT04 UI review directory required")
    output.mkdir(exist_ok=False)
    report = {"schema": "HH-GT04-FROZEN-UI-PROBE-1", "started_at": datetime.now(timezone.utc).isoformat(),
              "ok": False, "acceptance": False, "public_ack": False, "runs": []}
    try:
        before = bg.sources(STUDIO)
        snapshot = output / "source/studio"
        for relative in before:
            target = snapshot / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(STUDIO / relative, target)
        if bg.sources(snapshot) != before:
            raise ValueError("snapshot differs")
        frozen = bg.load(snapshot / "build/bootstrap/run_fixture.py")
        report.update(source_files=before, source_closure_sha256=frozen.source_closure_sha256(before))
        binary = STUDIO / ".local/tooling/blender-5.2.1-windows-x64/blender.exe"
        bootstrap._reject_reparse_ancestors(binary)
        if bg.sha(binary) != bg.BINARY_SHA256:
            raise ValueError("Blender executable pin mismatch")
        report["binary_sha256"] = bg.BINARY_SHA256
        env = {key: value for key, value in os.environ.items() if not key.upper().startswith(("PYTHON", "BLENDER_"))}
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        for key, relative in (("BLENDER_USER_RESOURCES", "blender-user"), ("TEMP", "temp"), ("TMP", "temp")):
            folder = output / relative
            folder.mkdir(exist_ok=True)
            env[key] = str(folder)
        unit = frozen.run_process([sys.executable, "-B", "-m", "unittest", "discover", "-s", str(snapshot / "tests/blender"),
                                   "-p", "test_*.py", "-v"], cwd=snapshot, output=output, timeout=30, label="python", env=env)
        report["runs"].append(unit)
        bg.require_host(unit, output)
        unit_log = (output / unit["stderr"]).read_text(encoding="utf-8")
        match = re.search(r"Ran (\d+) tests in [\d.]+s\s+OK\s*\Z", unit_log)
        if not match or int(match[1]) != EXPECTED_TESTS or "skipped" in unit_log:
            raise ValueError("unexpected unit test result")
        report["python_tests"] = int(match[1])
        for lane in ("gui", "background"):
            fixture = output / (lane + "-fixture")
            fixture.mkdir()
            for phase in ("edit", "reopen", "checkpoint"):
                argv = [str(binary)] + (["--background"] if lane == "background" else [])
                argv += ["--factory-startup", "--disable-autoexec", "--offline-mode", "--threads", "1", "--python-exit-code", "17",
                         "--python", str(snapshot / "tests/blender" / ("blender_ui_probe.py" if lane == "gui" else "blender_probe.py")),
                         "--", "--phase", phase, "--owned-root", str(fixture)]
                run = frozen.run_process(argv, cwd=snapshot, output=output, timeout=60, label=lane + "-" + phase, env=env)
                report["runs"].append(run)
                bg.require_host(run, output)
                if (output / run["stderr"]).stat().st_size:
                    raise ValueError("nonempty Blender stderr")
                native = json.loads((fixture / (phase + "-result.json")).read_text(encoding="utf-8"))
                (evaluate if lane == "gui" else bg.evaluate)(phase, native, (output / run["stdout"]).read_text(encoding="utf-8"))
                report.setdefault("native_checks", {})[lane + "-" + phase] = len(native["checks"])
            expected = json.loads((fixture / "expected.json").read_text(encoding="utf-8"))
            for key in ("saved", "checkpoint"):
                artifact = expected[key]
                actual = fixture / artifact["name"]
                if bg.sha(actual) != artifact["sha256"] or actual.stat().st_size != artifact["size_bytes"]:
                    raise ValueError("saved artifact changed")
            report[lane + "_artifacts"] = {key: expected[key] for key in ("saved", "checkpoint")}
        report["source_unchanged"] = bg.sources(STUDIO) == before
        report["snapshot_unchanged"] = bg.sources(snapshot) == before
        report["binary_unchanged"] = bg.sha(binary) == bg.BINARY_SHA256
        if not all(report[key] for key in ("source_unchanged", "snapshot_unchanged", "binary_unchanged")):
            raise ValueError("source or executable changed")
        report["ok"] = True
    except BaseException as exc:
        report["failure"] = type(exc).__name__ + ": " + str(exc)
    finally:
        report["completed_at"] = datetime.now(timezone.utc).isoformat()
        report["artifacts"] = {path.relative_to(output).as_posix(): bg.sha(path) for path in sorted(output.rglob("*"))
                               if path.is_file() and "__pycache__" not in path.parts}
        (output / "result.json").write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report.get(key) for key in ("ok", "failure", "source_closure_sha256", "python_tests", "native_checks")}, sort_keys=True))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
