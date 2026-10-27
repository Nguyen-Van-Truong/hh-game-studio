"""Run the existing authenticated GT04 writer client for the pilot asset.

The probe owns the Blender process, transport and export job. This adapter only
verifies its terminal packet and selects the protected GLB/Blend artifacts for
the pilot input; it never manufactures a fallback mesh.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

STUDIO = Path(__file__).resolve().parents[1] / "studio"
sys.path.insert(0, str(STUDIO.parent))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--binary", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", args.run_id):
        parser.error("invalid run ID")
    output = args.output.resolve()
    if output.exists():
        raise RuntimeError("output already exists")
    output.mkdir(parents=True)
    lock = json.loads((STUDIO / "toolchain.lock.json").read_text(encoding="utf-8"))
    expected = lock["blender"]["executable_sha256"]
    if sha(args.binary) != expected:
        raise RuntimeError("GT04 Blender binary pin mismatch")

    runner_path = STUDIO / "build/bootstrap/run_fixture.py"
    import importlib.util
    spec = importlib.util.spec_from_file_location("pilot_gt04_runner", runner_path)
    runner = importlib.util.module_from_spec(spec); assert spec.loader
    spec.loader.exec_module(runner)
    nested = output / "gt04"
    outer = output / "outer"
    outer.mkdir()
    host = runner.run_process([
        sys.executable, "-B", str(STUDIO / "tests/blender/run_writer_client_probe.py"),
        "--output", str(nested), "--run-id", args.run_id,
        "--binary", str(args.binary.resolve()), "--publication-profile", "export.publish",
    ], cwd=STUDIO, output=outer, timeout=180, label="gt04-author")
    # Persist the owned host result before interpreting any native artifact.
    write(output / "outer-result.json", host)
    try:
        return collect(output, args.run_id, args.binary, host)
    except Exception as error:
        write(output / "author-failure.json", {"run_id": args.run_id, "authority": 0,
            "host": host, "error_type": type(error).__name__, "error": str(error)})
        raise


def collect(output: Path, run_id: str, binary: Path, host: dict) -> int:
    from collect_existing import verify_blender, safe
    nested = output / "gt04"
    capture_path = nested / "capture.json"
    publication_path = nested / "publication.json"
    if not capture_path.is_file() or not publication_path.is_file():
        write(output / "author-result.json", {"schema": 1, "run_id": run_id,
            "authority": 0, "formal_acceptance": False, "host": host,
            "error": "GT04 terminal packets missing"})
        return 1
    capture = json.loads(capture_path.read_text(encoding="utf-8"))
    binding = verify_blender(output)
    if binding['run_id'] != run_id:
        raise RuntimeError("GT04 run ID mismatch")
    publication = json.loads(publication_path.read_text(encoding="utf-8"))
    export_rel = publication.get("export_directory")
    if not isinstance(export_rel, str):
        raise RuntimeError("publication export directory missing")
    safe(nested, export_rel)
    roots_files = publication.get("roots", {}).get("files")
    if not isinstance(roots_files, str):
        raise RuntimeError("protected files root missing")
    files_root = safe(nested, roots_files)
    artifacts = publication.get("publication", {}).get("receipt", {}).get("artifacts", {})
    if set(artifacts) != {"checkpoint.blend", "scene.glb"}:
        raise RuntimeError("protected GT04 artifact set incomplete")
    selected = {}
    for name in ("scene.glb", "checkpoint.blend"):
        source = files_root / name
        if not source.is_file():
            raise RuntimeError(f"protected artifact missing: {name}")
        target = output / name
        shutil.copyfile(source, target)
        selected[name] = {"path": name, "sha256": sha(target), "bytes": target.stat().st_size}
        if (artifacts[name]['sha256'] != selected[name]["sha256"]
                or artifacts[name]['size_bytes'] != selected[name]['bytes']):
            raise RuntimeError(f"protected artifact hash mismatch: {name}")
    result = {"schema": 1, "run_id": run_id, "authority": 0,
        "formal_acceptance": False, "gt04_acceptance": False,
        "host": host, "probe_capture": capture, "publication_sha256": sha(publication_path),
        "selected_artifacts": selected, "source_profile_unchanged": True,
        "blender_binary": {"path": str(binary), "sha256": sha(binary)},
        "cleanup": {"probe_native_completion": capture.get("native_completion"),
                     "logs_clean": capture.get("logs_clean"),
                     "host_tree_verified": host.get("tree_verified")}}
    result["passed"] = bool(host.get("exit_code") == 0 and host.get("wrapper_exit_code") == 0
        and host.get("tree_verified") and not host.get("timed_out")
        and capture.get("passed") is True and capture.get("formal_acceptance") is False
        and capture.get("logs_clean") is True and set(selected) == {"checkpoint.blend", "scene.glb"})
    write(output / "author-result.json", result)
    print("HH_CONSUMER_GT04_AUTHOR_COMPLETE" if result["passed"] else "HH_CONSUMER_GT04_AUTHOR_FAIL", flush=True)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
