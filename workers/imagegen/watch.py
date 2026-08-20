#!/usr/bin/env python3
"""Imagegen watcher (MASTER 8.2 / T6.1).

Writes ONLY:
  <root>/.gs/staging/jobs/<job_id>/out.png
  <root>/.gs/staging/jobs/<job_id>/result.json

Never writes assets/. dest_rel_hint is not a write path.
Never reads .gs/runtime/endpoint.json (no bus token).
Never reads the remote-C config (no API key in this process).

Claim / heartbeat / finish go through `gs-cli` (Rust gs-jobs).

GS_IMAGEGEN_STUB=1 writes a 1x1 PNG for local tests. That is a test fixture,
not a real provider result.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

STUB_PNG = bytes(
    [
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
        0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
        0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
        0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41, 0x54,
        0x08, 0xD7, 0x63, 0xF8, 0xCF, 0xC0, 0x00, 0x00,
        0x00, 0x03, 0x00, 0x01, 0x00, 0x05, 0xFE, 0xD4,
        0xEF, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44,
        0xAE, 0x42, 0x60, 0x82,
    ]
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_cli() -> list[str]:
    env = os.environ.get("GS_CLI")
    if env and Path(env).is_file():
        return [env]
    root = repo_root()
    for rel in ("gs-cli.exe", "target/release/gs-cli.exe", "target/debug/gs-cli.exe",
                "target/release/gs-cli", "target/debug/gs-cli"):
        cand = root / rel
        if cand.is_file():
            return [str(cand)]
    return ["cargo", "run", "-q", "-p", "gs-cli", "--"]


def run_cli(root: Path, args: list[str]) -> dict:
    cmd = resolve_cli() + ["--root", str(root), *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(repo_root()))
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "gs-cli failed").strip()
        raise RuntimeError(err.splitlines()[-1] if err else "gs-cli failed")
    line = (proc.stdout or "").strip().splitlines()
    if not line:
        return {}
    return json.loads(line[-1])


def staging_dir(root: Path, job_id: str) -> Path:
    return (root / ".gs" / "staging" / "jobs" / job_id).resolve()


def jail_write(root: Path, job_id: str, name: str, data: bytes) -> None:
    if name not in ("out.png", "result.json"):
        raise SystemExit("worker may only write out.png and result.json")
    if ".." in job_id or "/" in job_id or "\\" in job_id:
        raise SystemExit("unsafe job_id")
    staging = staging_dir(root, job_id)
    staging.mkdir(parents=True, exist_ok=True)
    dest = (staging / name).resolve()
    if dest.parent != staging:
        raise SystemExit("canonicalize+prefix jail: dest left staging")
    parts = {p.lower() for p in dest.parts}
    if "assets" in parts:
        raise SystemExit("worker must not write assets/")
    dest.write_bytes(data)


def try_comfy(url: str) -> dict:
    probe = url.rstrip("/") + "/system_stats"
    try:
        req = urllib.request.Request(probe, method="GET")
        urllib.request.urlopen(req, timeout=2)
        return {
            "ok": False,
            "provider": "comfyui",
            "error": "comfyui reachable but generate is not wired (M6-1)",
        }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            "ok": False,
            "provider": "comfyui",
            "error": f"comfyui unreachable: {exc}",
        }


def run_job(root: Path, job: dict, worker_id: str) -> None:
    job_id = job.get("job_id") or job.get("command_id")
    if not job_id:
        return
    hb = run_cli(root, ["jobs-heartbeat", "--job-id", job_id, "--worker-id", worker_id])
    if hb.get("cancelled"):
        payload = {"ok": False, "provider": "none", "error": "cancelled"}
        jail_write(root, job_id, "result.json", json.dumps(payload).encode("utf-8"))
        run_cli(
            root,
            ["jobs-finish", "--job-id", job_id, "--result-file",
             str(staging_dir(root, job_id) / "result.json")],
        )
        return

    stub = os.environ.get("GS_IMAGEGEN_STUB") == "1"
    if stub:
        jail_write(root, job_id, "out.png", STUB_PNG)
        payload = {"ok": True, "provider": "stub"}
    else:
        payload = try_comfy(os.environ.get("GS_COMFY_URL", "http://127.0.0.1:8188"))
    jail_write(root, job_id, "result.json", (json.dumps(payload) + "\n").encode("utf-8"))
    run_cli(
        root,
        ["jobs-finish", "--job-id", job_id, "--result-file",
         str(staging_dir(root, job_id) / "result.json")],
    )


def main() -> int:
    root = os.environ.get("GS_ROOT")
    if not root:
        print("GS_ROOT is required (project root)", file=sys.stderr)
        return 2
    root_path = Path(root)
    worker_id = os.environ.get("GS_WORKER_ID") or f"imagegen-{os.getpid()}"
    poll = float(os.environ.get("GS_POLL_SEC", "2"))
    print(f"imagegen watcher root={root_path} worker_id={worker_id}", flush=True)
    while True:
        try:
            claimed = run_cli(root_path, ["jobs-claim", "--worker-id", worker_id])
            if claimed.get("job_id"):
                run_job(root_path, claimed, worker_id)
            else:
                time.sleep(poll)
        except KeyboardInterrupt:
            return 0
        except Exception as exc:
            print(f"watch error: {exc}", file=sys.stderr, flush=True)
            time.sleep(poll)


if __name__ == "__main__":
    raise SystemExit(main())
