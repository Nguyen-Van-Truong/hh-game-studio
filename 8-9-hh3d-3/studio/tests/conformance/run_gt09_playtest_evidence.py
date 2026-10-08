"""Pack one delegated GT-09 playtest into immutable lifecycle evidence.

The delegated host owns the native process, import, recorder, and process-tree
receipts.  This entry point only reads those outputs and runs the existing
fail-closed lifecycle verifier.  It derives the run directory from the
validated run id and fixture, so a caller cannot point the packer at a
different run or overwrite an unrelated evidence directory.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any

STUDIO = Path(__file__).resolve().parents[2]
RAW_ROOT = STUDIO / ".local" / "reviews"
RUN_ID = re.compile(r"^gt09-playtest-[0-9]{8}-[0-9]{2}$")
FIXTURES = {"arena", "room"}


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError(f"invalid_json:{path.name}") from error
    if type(value) is not dict:
        raise ValueError(f"json_object_required:{path.name}")
    return value


def _run_root(run_id: str, fixture: str) -> Path:
    if not RUN_ID.fullmatch(run_id):
        raise ValueError("invalid_run_id")
    if fixture not in FIXTURES:
        raise ValueError("invalid_fixture")
    root = (RAW_ROOT / run_id / fixture).resolve()
    try:
        root.relative_to(RAW_ROOT.resolve())
    except ValueError as error:
        raise ValueError("run_root_outside_reviews") from error
    return root


def pack(*, run_id: str, fixture: str, minimum_duration_seconds: float = 900.0) -> dict[str, Any]:
    """Verify one host run and create its manifest exactly once."""
    root = _run_root(run_id, fixture)
    metadata_path = root / "metadata.json"
    host_path = root / "host-result.json"
    log_path = root / "godot.stdout.log"
    video_path = root / "video" / "capture.mkv"
    if not root.is_dir():
        raise FileNotFoundError(root)
    if (root / "manifest.json").exists():
        raise FileExistsError("PLAYTEST_MANIFEST_EXISTS")
    metadata = _read_object(metadata_path)
    if metadata.get("run_id") != run_id or metadata.get("fixture") != fixture:
        raise ValueError("metadata_identity")
    # K15 is accepted only from the immutable native publication snapshot.
    # The runner still supports a legacy copy mode for diagnostics, but that
    # mode must never be packable as final-closure evidence.
    if (metadata.get("source_mode") != "native-publication-snapshot"
            or metadata.get("legacy_unaccepted") is not False):
        raise ValueError("native_publication_snapshot_required")
    provenance = metadata.get("publication_provenance")
    if (type(provenance) is not dict
            or provenance.get("selected_matches_executed_snapshot") is not True
            or not isinstance(provenance.get("executed_snapshot"), str)
            or not isinstance(provenance.get("native_run_id"), str)):
        raise ValueError("publication_provenance_missing")
    source_closure = metadata.get("source_closure_sha256")
    if not isinstance(source_closure, str):
        raise ValueError("metadata_source_closure_missing")
    try:
        from ..godot.fixture_lifecycle_manifest import build_manifest
    except ImportError:
        from tests.godot.fixture_lifecycle_manifest import build_manifest
    report = build_manifest(
        fixture=fixture,
        run_id=run_id,
        log_path=log_path,
        source_closure_sha256=source_closure,
        host_result_path=host_path,
        video_path=video_path,
        minimum_duration_seconds=minimum_duration_seconds,
    )
    encoded = json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    # The host and recorder are complete before this command starts.  Refuse a
    # pre-existing manifest and use exclusive creation so retries cannot
    # replace a prior result.
    with (root / "manifest.json").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(encoded)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--fixture", choices=sorted(FIXTURES), required=True)
    parser.add_argument("--minimum-duration-seconds", type=float, default=900.0)
    args = parser.parse_args(argv)
    try:
        report = pack(run_id=args.run_id, fixture=args.fixture,
                      minimum_duration_seconds=args.minimum_duration_seconds)
    except (FileExistsError, FileNotFoundError, OSError, ValueError) as error:
        print(json.dumps({"schema": "hh-gt09-playtest-pack-1", "status": "REJECTED",
                          "error": str(error)}, sort_keys=True))
        return 2
    print(json.dumps({"schema": report["schema"], "status": report["status"],
                      "run_id": report["run_id"], "fixture": report["fixture"],
                      "manifest": str(_run_root(args.run_id, args.fixture) / "manifest.json"),
                      "errors": report["errors"]}, sort_keys=True))
    return 0 if report["status"] == "PLAYTEST_EVIDENCE_READY" and report["errors"] == [] else 2


if __name__ == "__main__":
    raise SystemExit(main())
