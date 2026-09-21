"""S137 D2: inert same-envelope Docker control, diagnostic only.

The control uses the pinned image and the executor's resource/mount envelope,
but an inert shell sentinel instead of Godot. It is never acceptance evidence.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid
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


executor = load("s137_d2_executor", STUDIO / "godot-addon" / "linux_executor.py")
DOCKER = executor.DOCKER
CONTEXT = executor.EXECUTOR_CONTEXT
RUN_ID = "gt06-s137-d2-inert-control-02"


def run(args, timeout=30):
    return subprocess.run([DOCKER, "--context", "desktop-linux", *args],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout)


def main() -> int:
    root = HERE / RUN_ID
    root.mkdir(parents=False, exist_ok=False)
    snapshot = root / "snapshot"
    snapshot.mkdir()
    # Match the stock executor's writable tmpfs mountpoint under the read-only
    # project bind; without this, runc fails before any control process starts.
    (snapshot / ".godot").mkdir()
    tool = executor._binary().parent
    name = "hh-gt03-" + uuid.uuid4().hex
    args = ["create", "--pull=never", "--name", name,
            "--label", "hh.gt03.owner=" + name,
            "--label", "hh.gt03.executor=" + CONTEXT,
            "--platform", "linux/amd64", "--read-only", "--network", "none",
            "--ipc", "private", "--cgroupns", "private", "--user", "65532:65532",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges=true",
            "--security-opt", "seccomp=builtin", "--memory", "1g",
            "--memory-swap", "1g", "--cpus", "1", "--pids-limit", "64",
            "--log-driver", "none", "--restart", "no", "--no-healthcheck",
            "--stop-timeout", "2", "--shm-size", "16m", "--workdir", "/project"]
    for key, limit in executor.ULIMITS.items():
        args += ["--ulimit", f"{key}={limit}:{limit}"]
    for key, value in executor.ENVIRONMENT.items():
        args += ["--env", f"{key}={value}"]
    for dest, options in executor.TMPFS.items():
        args += ["--tmpfs", f"{dest}:{options}"]
    for source, dest in ((tool, "/tool"), (snapshot, "/project")):
        args += ["--mount", f"type=bind,src={source},dst={dest},readonly,bind-propagation=rprivate"]
    args += ["--entrypoint", "/usr/bin/timeout", executor.IMAGE_ID,
             "--signal=TERM", "--kill-after=1s", "19s", "/bin/sh", "-c",
             "printf 'HH_S137_D2_START\\n'; printf 'HH_S137_D2_END\\n'"]
    started = datetime.now(timezone.utc).isoformat()
    events_cmd = [DOCKER, "--context", "desktop-linux", "events",
                  "--filter", "label=hh.gt03.executor=" + CONTEXT,
                  "--format", "{{json .}}"]
    observer = subprocess.Popen(events_cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True,
                                encoding="utf-8", errors="replace")
    create = start = wait = inspect_before = inspect_after = remove = None
    cid = None
    try:
        create = run(args)
        cid = create.stdout.strip() or None
        if cid:
            inspect_before = run(["inspect", cid, "--format", "{{json .}}"])
            start = run(["start", "--attach", cid], timeout=30)
            wait = run(["wait", cid], timeout=10)
            inspect_after = run(["inspect", cid, "--format", "{{json .}}"])
    finally:
        if cid:
            remove = run(["rm", "-f", cid], timeout=10)
        try:
            observer.terminate()
            observer.wait(timeout=5)
        except BaseException:
            try:
                observer.kill()
                observer.wait(timeout=5)
            except BaseException:
                pass
    event_stdout, event_stderr = observer.communicate(timeout=5)
    finished = datetime.now(timezone.utc).isoformat()
    def rec(p):
        return None if p is None else {"returncode": p.returncode, "stdout": p.stdout, "stderr": p.stderr}
    (root / "create-args.json").write_text(json.dumps(args, indent=2) + "\n", encoding="utf-8")
    (root / "docker-events.stdout.jsonl").write_text(event_stdout, encoding="utf-8")
    (root / "docker-events.stderr.txt").write_text(event_stderr, encoding="utf-8")
    probe = {
        "schema": "HH-GT06-S137-D2-INERT-CONTROL-1",
        "authority": 0, "formal_acceptance": False, "diagnostic_only": True,
        "run_id": RUN_ID, "started_utc": started, "finished_utc": finished,
        "container_name": name, "container_id": cid, "resource_envelope": {
            "image": executor.IMAGE_ID, "memory": "1g", "memory_swap": "1g",
            "cpus": "1", "pids_limit": 64, "shm_size": "16m",
            "network": "none", "ipc": "private", "cgroupns": "private",
            "ulimits": executor.ULIMITS, "wall_supervisor": "TERM19/KILL20"
        },
        "create": rec(create), "inspect_before": rec(inspect_before),
        "start": rec(start), "wait": rec(wait),
        "inspect_after": rec(inspect_after), "remove": rec(remove),
        "docker_events_stdout": event_stdout, "docker_events_stderr": event_stderr,
        "sentinel_expected": ["HH_S137_D2_START", "HH_S137_D2_END"],
        "interpretation": "pending sealed review; inert control is not a Godot or GT06 acceptance run"
    }
    (root / "probe.json").write_text(json.dumps(probe, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"run_id": RUN_ID, "container_id": cid,
                      "create_exit": create.returncode if create else None,
                      "start_exit": start.returncode if start else None,
                      "wait": wait.stdout.strip() if wait else None,
                      "remove_exit": remove.returncode if remove else None,
                      "formal_acceptance": False}, sort_keys=True), flush=True)
    return 0 if create and start and start.returncode == 0 and remove and remove.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
