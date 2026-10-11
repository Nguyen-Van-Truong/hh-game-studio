"""Run the pinned native Blender GT-09 content producer once.

The final matrix owns this producer through a subprocess so its host exit,
Job cleanup and protected publication path are recorded with the K8 row.  The
recipe and Blender binary are host-owned; no caller supplied Blend or script
is accepted.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import importlib
import json
from pathlib import Path
import sys
import time

STUDIO = Path(__file__).resolve().parents[2]
REPO_ROOT = STUDIO.parent
# The installed package has sibling ``host`` and ``studio`` namespaces.  Add
# the payload root explicitly so the native Blender producer works when run
# from an installed snapshot, not only from the repository checkout.
if str(STUDIO) not in sys.path:
    sys.path.insert(0, str(STUDIO))


def _load(name: str, relative: str):
    if relative.startswith("host/blender/"):
        if str(STUDIO) not in sys.path:
            sys.path.insert(0, str(STUDIO))
        return importlib.import_module("host.blender." + Path(relative).stem)
    path = STUDIO / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("GT09_CONTENT_IMPORT")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_case():
    fixtures = _load("gt09_content_fixtures", "tests/godot/linux_probe_fixtures.py")
    probe = _load("gt09_content_probe", "tests/godot/run_linux_probe.py")
    owner = _load("gt09_content_owner", "godot-addon/gameplay_source_owner.py")
    case = {**fixtures.FIXTURES["gameplay_source_room_3d_native"],
            "scene": fixtures.SCENE,
            "project": owner._load("gameplay_source_profile").PROJECT_TEMPLATE}
    files = probe.case_files(case)
    files.pop("project.godot", None)
    return owner, files


def run(*, run_id: str, output: Path, binary: Path) -> dict:
    if not run_id.startswith("gt09-content-"):
        raise ValueError("GT09_CONTENT_RUN_ID")
    output = output.resolve()
    binary = binary.resolve(strict=True)
    if output.exists() or not binary.is_file():
        raise ValueError("GT09_CONTENT_OUTPUT_OR_BINARY")
    output.mkdir(parents=True)
    owner, source_files = _source_case()
    closure = owner.runtime_source_closure()[1]
    owner_parent = output / "lease-owner"
    owner_parent.mkdir()
    source_owner = owner.GameplaySourcePublicationOwner.create(
        owner_parent, project_id="project.gt09.blender",
        source_files=source_files, entrypoint=owner.ENTRYPOINT,
        source_closure_sha256=closure)
    credential = source_owner.issue()
    grant = source_owner.authorize("Bearer " + credential.bearer, "scene.save")
    session_lease = source_owner.lease(grant, ttl_ms=90_000)
    # The Blender host consumes the journal Lease shape while the gameplay
    # owner keeps the session-specific GodotLease for its own check routine.
    from host.core.journal import Lease as HostLease
    lease = HostLease(source_owner.project_id, "scene.save", "gt09-content",
                      session_lease.fencing_epoch, session_lease.expires_ms)

    def check(current):
        deadline = min(current.expires_ms, int(time.time() * 1000) + 5_000)
        source_owner._session.check(grant, session_lease, deadline_ms=deadline,
                                    operation="scene.save")

    job = _load("gt09_content_job", "host/blender/fixture_content_job.py")
    try:
        report = job.run_content(run_id=run_id, binary=binary, parent=output,
                                 lease=lease, lease_checker=check,
                                 source_root=STUDIO)
        publication = report.get("_publication_handle")
        wire = {key: value for key, value in report.items()
                if key != "_publication_handle"}
        published_root = Path(wire["publication"]["published_root"])
        if publication is not None:
            publication.close()
            publication = None
        observed = job.inspect_publication(published_root)
        wire.update({"schema": "hh-gt09-content-run-1", "status": "DIAGNOSTIC_PASS",
                     "authority": 0, "acceptance": False,
                     "source_closure_sha256": closure,
                     "published_root": str(published_root),
                     "publication_readback": observed,
                     "public_ack": False})
        (output / "result.json").write_text(
            json.dumps(wire, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return wire
    finally:
        source_owner.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--binary", type=Path,
                        default=STUDIO / ".local" / "tooling" /
                        "blender-5.2.1-windows-x64" / "blender.exe")
    args = parser.parse_args(argv)
    try:
        report = run(run_id=args.run_id, output=args.output, binary=args.binary)
    except Exception as error:
        args.output.mkdir(parents=True, exist_ok=True)
        failure = {"schema": "hh-gt09-content-run-1", "run_id": args.run_id,
                   "status": "DIAGNOSTIC_FAIL", "authority": 0,
                   "acceptance": False, "public_ack": False,
                   "error_code": str(error) if str(error).isupper()
                   else type(error).__name__}
        (args.output / "result.json").write_text(
            json.dumps(failure, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(failure, sort_keys=True))
        return 2
    print(json.dumps({"schema": report["schema"], "run_id": report["run_id"],
                      "status": report["status"], "authority": 0}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
