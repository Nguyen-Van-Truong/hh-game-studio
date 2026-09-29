"""Run the disposable pinned Blender O2 authoring diagnostic."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

STUDIO = Path(__file__).resolve().parents[2]
BLENDER_SHA256 = "8f7a131ad8bc148edc218b334f07d92a57f5a357fa66d913b290537fd8353c06"


def _load(path: Path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("o2_blender_bootstrap", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sources(root: Path) -> dict[str, str]:
    names = [
        "build/bootstrap/run_fixture.py",
        "toolchain.lock.json",
        "contracts/blender-authoring-schema-v1.json",
        "tests/blender/authoring_native_probe.py",
        "tests/blender/sprite_sheet_pixels.py",
        "tests/blender/run_authoring_native_probe.py",
    ]
    return {name: _sha(root / name) for name in names}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blender", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or output.is_relative_to(STUDIO):
        raise ValueError("OUTPUT_SCOPE")
    output.mkdir(parents=True)
    binary = args.blender.resolve(strict=True)
    if _sha(binary) != BLENDER_SHA256:
        raise ValueError("PIN_HASH")
    original = _sources(STUDIO)
    snapshot = output / "source" / "studio"
    for name in original:
        target = snapshot / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(STUDIO / name, target)
    if _sources(snapshot) != original:
        raise ValueError("SOURCE_SNAPSHOT")
    bootstrap = _load(snapshot / "build/bootstrap/run_fixture.py")
    env = {key: value for key, value in __import__("os").environ.items()
           if not key.upper().startswith(("PYTHON", "BLENDER_"))}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["BLENDER_USER_RESOURCES"] = str(output / "blender-user")
    env["TEMP"] = str(output / "temp")
    env["TMP"] = str(output / "temp")
    (output / "blender-user").mkdir()
    (output / "temp").mkdir()
    closure = bootstrap.source_closure_sha256(original)
    native = bootstrap.run_process(
        [str(binary), "--factory-startup", "--disable-autoexec", "--offline-mode",
         "--threads", "1", "--python-exit-code", "17", "--python",
         str(snapshot / "tests/blender/authoring_native_probe.py"), "--",
         "--output", str(output), "--source-root", str(snapshot)],
        cwd=snapshot, output=output, timeout=90, label="native", env=env)
    reopen = bootstrap.run_process(
        [str(binary), "--factory-startup", "--disable-autoexec", "--offline-mode",
         "--threads", "1", "--python-exit-code", "17", "--python",
         str(snapshot / "tests/blender/authoring_native_probe.py"), "--",
         "--output", str(output), "--source-root", str(snapshot), "--reopen"],
        cwd=snapshot, output=output, timeout=60, label="reopen", env=env)
    report = json.loads((output / "native.json").read_text(encoding="utf-8")) if (output / "native.json").is_file() else None
    reopened = json.loads((output / "reopen.json").read_text(encoding="utf-8")) if (output / "reopen.json").is_file() else None
    stdout = (output / native["stdout"]).read_text(encoding="utf-8", errors="replace") if native.get("stdout") else ""
    stderr = (output / native["stderr"]).read_text(encoding="utf-8", errors="replace") if native.get("stderr") else ""
    reopen_stdout = (output / reopen["stdout"]).read_text(encoding="utf-8", errors="replace") if reopen.get("stdout") else ""
    reopen_stderr = (output / reopen["stderr"]).read_text(encoding="utf-8", errors="replace") if reopen.get("stderr") else ""
    combined_logs = stdout + "\n" + reopen_stdout + "\n" + stderr + "\n" + reopen_stderr
    known_startup_warnings = [line for line in combined_logs.splitlines()
                              if "reports          | WARNING Path" in line
                              and "datafiles" in line and "assets\\brushes" in line]
    unexplained_log_lines = [line for line in combined_logs.splitlines()
                             if any(token in line for token in ("Traceback", "Error: script failed", "ERROR:"))]
    logs_clean = not stderr.strip() and not reopen_stderr.strip() and not unexplained_log_lines
    source_unchanged = _sources(STUDIO) == original
    source_snapshot_unchanged = _sources(snapshot) == original
    passed = bool(
        report and not report.get("failures") and report.get("runtime_authorized") is False
        and report.get("formal_acceptance") is False
        and native.get("exit_code") == 0 and native.get("wrapper_exit_code") == 0
        and native.get("timed_out") is False and native.get("tree_verified") is True
        and reopen and reopened and reopened.get("reopened") is True
        and reopen.get("exit_code") == 0 and reopen.get("wrapper_exit_code") == 0
        and reopen.get("timed_out") is False and reopen.get("tree_verified") is True
        and source_unchanged and source_snapshot_unchanged
        and logs_clean
    )
    result = {"schema": "hh-o2-blender-native-capture-1", "run_id": args.run_id,
              "passed": passed, "authority": 0, "formal_acceptance": False,
              "binary_sha256": BLENDER_SHA256, "source_closure_sha256": closure,
              "native": native, "reopen": reopen, "probe": report, "reopened": reopened,
              "source_unchanged": source_unchanged,
              "source_snapshot_unchanged": source_snapshot_unchanged,
              "stdout_clean": logs_clean,
              "known_startup_warnings": known_startup_warnings,
              "unexplained_log_lines": unexplained_log_lines}
    (output / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"run_id": args.run_id, "passed": passed,
                      "failures": (report or {}).get("failures", [])}, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
