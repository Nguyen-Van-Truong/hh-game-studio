"""S137 D1: one unchanged profile run with a read-only Docker event observer.

This is authority-0 diagnostic evidence. It does not alter the executor,
profile, source closure, resource envelope, timeout, or GT06 gates.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STUDIO = ROOT / "studio"
sys.path.insert(0, str(ROOT))


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


validation = load("s137_validation_owner", STUDIO / "godot-addon" / "validation_owner.py")
executor = validation.executor
factory = validation.factory
from studio.host.replay import native_runner as native

DOCKER = executor.DOCKER
CONTEXT = executor.EXECUTOR_CONTEXT
RUN_ID = "gt06-s137-d1-observer-01"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    root = HERE / RUN_ID
    root.mkdir(parents=False, exist_ok=False)
    config = native.configuration("0.0")
    bundle = factory.compose(factory.DEFAULT_SCENE, config,
                             scene_revision="sha256:" + sha(factory.DEFAULT_SCENE),
                             engine_sha256=executor.BINARY_SHA256)
    factory.qualify(bundle)
    project = root / "input"
    for name, raw in bundle.files.items():
        target = project / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    (root / "manifest.json").write_bytes(bundle.manifest_bytes)

    events_cmd = [DOCKER, "--context", "desktop-linux", "events",
                  "--filter", "label=hh.gt03.executor=" + CONTEXT,
                  "--format", "{{json .}}"]
    observer = subprocess.Popen(events_cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True,
                                encoding="utf-8", errors="replace")
    started = datetime.now(timezone.utc).isoformat()
    result = None
    observer_error = None
    try:
        result = executor.run(project, mode="profile-validate", output=root / "executor",
                              timeout_seconds=20)
    except BaseException as exc:
        observer_error = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        try:
            observer.terminate()
            observer.wait(timeout=5)
        except BaseException:
            try:
                observer.kill()
                observer.wait(timeout=5)
            except BaseException:
                pass
    finished = datetime.now(timezone.utc).isoformat()
    event_stdout, event_stderr = observer.communicate(timeout=5)
    (root / "docker-events.stdout.jsonl").write_text(event_stdout, encoding="utf-8")
    (root / "docker-events.stderr.txt").write_text(event_stderr, encoding="utf-8")
    result_path = root / "executor" / "result.json"
    probe = {
        "schema": "hh-gt06-s137-d1-observed-profile-1",
        "authority": 0,
        "run_id": RUN_ID,
        "started_utc": started,
        "finished_utc": finished,
        "mode": "profile-validate",
        "deadline_seconds": 20,
        "source_closure_sha256": validation._IMPORT_RELEASE[1],
        "bundle_manifest_sha256": sha(bundle.manifest_bytes),
        "input_files": {name: sha(raw) for name, raw in bundle.files.items()},
        "executor_result_sha256": sha(result_path.read_bytes()) if result_path.exists() else None,
        "executor_result": result,
        "docker_events_sha256": sha(event_stdout.encode()),
        "docker_events_stderr_sha256": sha(event_stderr.encode()),
        "observer_command": events_cmd,
        "observer_error": observer_error,
        "formal_acceptance": False,
        "public_ack": False,
        "diagnostic_only": True,
        "interpretation": "pending sealed evidence review; do not infer sender from missing Docker events",
    }
    write_json(root / "probe.json", probe)
    print(json.dumps({
        "run_id": RUN_ID,
        "exit": (result or {}).get("container_state", {}).get("ExitCode") if result else None,
        "elapsed_seconds": (result or {}).get("command_host", {}).get("elapsed_seconds") if result else None,
        "diagnostic_process_clean": (result or {}).get("diagnostic_process_clean") if result else None,
        "observer_exit": observer.returncode,
        "formal_acceptance": False,
    }, sort_keys=True), flush=True)
    return 0 if result and result.get("diagnostic_process_clean") else 1


if __name__ == "__main__":
    raise SystemExit(main())
