"""Prepare a deterministic, fail-closed GT-01 official runtime remint.

This command never starts Godot/Blender and never mutates the product tree.  It
recomputes the frozen source closure, verifies the two pinned Godot binaries,
and briefly claims an exclusive reservation so two operators cannot mint the
same run concurrently.  The emitted plan contains placeholders instead of
host paths; the operator substitutes paths only at the final launch step.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import stat
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

HERE = Path(__file__).resolve().parent
PRODUCT = HERE.parents[2]  # 8-9-hh3d-3
REPO = PRODUCT.parent
DEFAULT_MANIFEST = REPO / "8-9-hh3d-3/zdoc/reviews/20260915-r15-closure/source-closure-manifest.json"
LOCK = PRODUCT / "studio/toolchain.lock.json"
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class RemintGap(ValueError):
    """A required precondition is not proven."""


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _regular(path: Path) -> None:
    try:
        info = os.lstat(path)
    except OSError as exc:
        raise RemintGap(f"required file unavailable ({path.name})") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise RemintGap(f"required file is not a regular file ({path.name})")
    if int(getattr(info, "st_nlink", 1)) != 1:
        raise RemintGap(f"required file has unexpected hard links ({path.name})")


def _load_closure_module() -> Any:
    source = REPO / "8-9-hh3d-3/zdoc/reviews/20260915-r15-closure/closure_manifest.py"
    _regular(source)
    spec = importlib.util.spec_from_file_location("gt01_closure_manifest_r15", source)
    if spec is None or spec.loader is None:
        raise RemintGap("closure verifier could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_json(path: Path) -> dict[str, Any]:
    _regular(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RemintGap(f"invalid JSON ({path.name})") from exc
    if not isinstance(data, dict):
        raise RemintGap(f"JSON root is not an object ({path.name})")
    return data


def _verify_closure(manifest_path: Path) -> tuple[str, int]:
    module = _load_closure_module()
    result = module.verify(manifest_path, module.PRODUCT)
    if result.get("status") != "READY":
        raise RemintGap("source closure verification is not READY")
    closure_hash = result.get("source_closure_sha256")
    if not isinstance(closure_hash, str) or not HEX64.fullmatch(closure_hash):
        raise RemintGap("source closure hash is missing or malformed")
    manifest = _load_json(manifest_path)
    if manifest.get("source_closure_sha256") != closure_hash:
        raise RemintGap("source closure hash changed while loading manifest")
    rows = manifest.get("required_files")
    if not isinstance(rows, list) or not rows:
        raise RemintGap("source closure inventory is empty")
    return closure_hash, len(rows)


def _verify_lock_and_binaries(console: Path, gui: Path) -> dict[str, Any]:
    lock = _load_json(LOCK)
    if lock.get("schema") != "HH-STUDIO-TOOLCHAIN-LOCK-2" or lock.get("status") != "CANDIDATE":
        raise RemintGap("toolchain lock is not a candidate lock")
    godot = lock.get("godot")
    if not isinstance(godot, dict):
        raise RemintGap("godot lock section is missing")
    for key in ("version", "console_executable", "gui_executable", "console_sha256", "gui_sha256", "observed_version"):
        if not isinstance(godot.get(key), str) or not godot[key]:
            raise RemintGap(f"godot lock field missing: {key}")
    if console.name != godot["console_executable"] or gui.name != godot["gui_executable"]:
        raise RemintGap("binary filename differs from toolchain lock")
    for key, path in (("console_sha256", console), ("gui_sha256", gui)):
        expected = godot[key].lower()
        if not HEX64.fullmatch(expected):
            raise RemintGap(f"malformed binary hash in lock: {key}")
        _regular(path)
        actual = _sha(path)
        if actual != expected:
            raise RemintGap(f"binary checksum mismatch: {key}")
    return godot


@contextmanager
def _reservation() -> Iterator[None]:
    """Atomically reserve this remint package; stale reservations fail closed."""
    path = HERE / "one-process.reservation"
    payload = {"schema": "HH3D-GT01-REMINT-RESERVATION-1", "pid": os.getpid(), "purpose": "preflight-only"}
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise RemintGap("one-process reservation is busy (inspect/remove stale reservation)") from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, sort_keys=True)
            stream.write("\n")
        yield
    finally:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def _redacted_plan(closure_hash: str, rows: int, godot: dict[str, Any], manifest_path: Path) -> dict[str, Any]:
    revision = str(LOCK and godot.get("version", "")).replace(".", "")
    stem = closure_hash[:12]
    run_id = f"GT01-R16-{stem}-OFFICIAL-01"
    command_id = f"cmd.gt01.remint.r16.{stem}"
    manifest_rel = manifest_path.resolve().relative_to(REPO.resolve()).as_posix()
    runner = "8-9-hh3d-3/studio/build/bootstrap/run_fixture.py"
    binder = "8-9-hh3d-3/zdoc/reviews/20260915-r15-evidence/evidence_binder.py"
    run_command = (
        f"python {runner} --studio-root <PRODUCT_ROOT>/studio --godot-exe <GODOT_CONSOLE> "
        f"--expected-version {godot['version']} --console-sha256 {godot['console_sha256']} "
        f"--gui-sha256 {godot['gui_sha256']} --run-id {run_id} --command-id {command_id} "
        "--output <NEW_EVIDENCE_DIR>"
    )
    bind_command = (
        f"python {binder} --source-manifest {manifest_rel} "
        "--runner-output <NEW_EVIDENCE_DIR>/official-evidence.json "
        "--repo-root <FROZEN_REPO_ROOT> --output <NEW_EVIDENCE_DIR>/binder-result.json"
    )
    return {
        "schema": "HH3D-GT01-REMINT-PLAN-1",
        "status": "READY_FOR_SERIAL_RUNTIME",
        "source_closure_sha256": closure_hash,
        "source_file_count": rows,
        "toolchain_version": godot["version"],
        "run_id": run_id,
        "command_id": command_id,
        "revision_hint": revision,
        "reservation": "one-process.reservation (atomic O_EXCL, released after preflight)",
        "launch_command_redacted": run_command,
        "post_run_binder_command": bind_command,
        "constraints": [
            "Do not launch a second Godot/Blender process for this fixture path.",
            "Create a new evidence directory; never overwrite a prior run.",
            "Re-run this preflight after any source, lock, or binary change.",
            "READY_FOR_SERIAL_RUNTIME is not acceptance; binder and two critics remain required.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--godot-exe", required=True, type=Path)
    parser.add_argument("--gui-exe", required=True, type=Path)
    parser.add_argument("--output", type=Path, help="optional new JSON plan path (must not already exist)")
    args = parser.parse_args(argv)
    try:
        with _reservation():
            closure_hash, rows = _verify_closure(args.manifest.resolve())
            godot = _verify_lock_and_binaries(args.godot_exe.resolve(), args.gui_exe.resolve())
            plan = _redacted_plan(closure_hash, rows, godot, args.manifest)
            if args.output is not None:
                output = args.output.resolve()
                try:
                    output.relative_to(HERE)
                except ValueError as exc:
                    raise RemintGap("output must stay inside this review package") from exc
                if output.exists():
                    raise RemintGap("output already exists; refusing overwrite")
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(json.dumps(plan, indent=2, sort_keys=True))
            return 0
    except (OSError, RemintGap, ValueError) as exc:
        print(json.dumps({"schema": "HH3D-GT01-REMINT-PLAN-1", "status": "GAP", "failure": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
