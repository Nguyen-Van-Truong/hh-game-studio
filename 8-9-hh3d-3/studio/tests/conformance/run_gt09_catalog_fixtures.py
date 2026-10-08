"""Fail-closed B5 verifier for the registered GT-09 fixture evidence.

The registered authoring probe and the delegated playtest runner are the
evidence producers.  This module only reads their immutable output; it never
starts Godot/Blender, edits a fixture, or promotes authority-zero diagnostics.
Missing evidence is reported as ``OPEN`` with a concrete reason.  In
particular, a builder-only recipe, a child ``PASS`` field, or a playtest asset
hash cannot stand in for catalog provenance, seeded repair, or performance
readback.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any

STUDIO = Path(__file__).resolve().parents[2]
REVISION = "hh-gt09-catalog-fixtures-1"
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise ValueError(f"JSON_OBJECT_REQUIRED:{path}")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _under_reviews(path: Path) -> bool:
    try:
        path.resolve().relative_to((STUDIO / ".local" / "reviews").resolve())
        return True
    except ValueError:
        return False


def _check_native(root: Path, fixture: str) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    row: dict[str, Any] = {"fixture": fixture, "root": str(root), "observed": False}
    if not _under_reviews(root):
        return row, [f"{fixture}:root_outside_reviews"]
    result_path, receipt_path = root / "result.json", root / "registered-owner-receipt.json"
    if not result_path.is_file() or not receipt_path.is_file():
        return row, [f"{fixture}:registered_result_or_receipt_missing"]
    try:
        result, receipt = _read(result_path), _read(receipt_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return row, [f"{fixture}:native_json_invalid:{type(exc).__name__}"]
    row.update({"result_sha256": _sha(result_path), "receipt_sha256": _sha(receipt_path),
                "source_closure_sha256": receipt.get("source_closure_sha256"),
                "catalog_digest": receipt.get("profile_catalog_digest"),
                "native_process": receipt.get("native_process")})
    if result.get("status") != "DIAGNOSTIC_PASS":
        errors.append(f"{fixture}:result_not_diagnostic_pass")
    if result.get("authority") != 0 or result.get("public_ack") is not False:
        errors.append(f"{fixture}:authority_or_ack")
    if receipt.get("schema") != "hh-godot-registered-authoring-owner-1":
        errors.append(f"{fixture}:receipt_schema")
    if receipt.get("profile") != "hh-godot-gameplay-source-1":
        errors.append(f"{fixture}:catalog_profile")
    digest = receipt.get("profile_catalog_digest")
    if not isinstance(digest, str) or not digest.startswith("sha256:") or not HEX64.fullmatch(digest[7:]):
        errors.append(f"{fixture}:catalog_digest")
    closure = receipt.get("source_closure_sha256")
    if not isinstance(closure, str) or not closure.startswith("sha256:") or not HEX64.fullmatch(closure[7:]):
        errors.append(f"{fixture}:source_closure")
    commands = receipt.get("command_ids")
    if not isinstance(commands, list) or not commands or len(commands) != len(set(commands)):
        errors.append(f"{fixture}:command_ids")
    process = receipt.get("native_process")
    if not isinstance(process, dict) or process.get("exit_code") != 0:
        errors.append(f"{fixture}:native_exit")
    if not (root / "editor-host" / "process-exit.json").is_file():
        errors.append(f"{fixture}:host_exit_missing")
    handoff = receipt.get("blender_handoff")
    if not isinstance(handoff, dict):
        errors.append(f"{fixture}:blender_handoff_missing")
    else:
        published = Path(str(handoff.get("published_root", ""))).resolve()
        row["blender_root"] = str(published)
        blender_errors = _check_blender(published, handoff, fixture)
        errors.extend(blender_errors)
        row["blender_sprite_provenance"] = not any("sprite" in error for error in blender_errors)
        row["blender_glb_provenance"] = not any("glb" in error for error in blender_errors)
    row["observed"] = not errors
    return row, errors


def _check_blender(root: Path, handoff: dict[str, Any], fixture: str) -> list[str]:
    errors: list[str] = []
    if not _under_reviews(root):
        return [f"{fixture}:blender_root_outside_reviews"]
    manifest_path, glb_path = root / "manifest.json", root / "scene.glb"
    if not manifest_path.is_file() or not glb_path.is_file():
        return [f"{fixture}:blender_manifest_or_glb_missing"]
    try:
        manifest = _read(manifest_path)
    except (OSError, ValueError, json.JSONDecodeError):
        return [f"{fixture}:blender_manifest_invalid"]
    if manifest.get("schema") != "HH-BLENDER-PUBLICATION-1" or manifest.get("public_ack") is not False:
        errors.append(f"{fixture}:blender_manifest_schema_or_ack")
    actual = _sha(glb_path)
    declared = manifest.get("native", {}).get("glb_sha256")
    if actual != declared or actual != handoff.get("glb_sha256"):
        errors.append(f"{fixture}:blender_glb_provenance")
    # A sprite is only provenance when the Blender publication itself names
    # and hashes it.  A playtest source copy alone is not a producer receipt.
    sprite = root / "sprite_sheet.png"
    sprite_declared = manifest.get("native", {}).get("sprite_sheet_sha256")
    if not sprite.is_file() or not isinstance(sprite_declared, str) or _sha(sprite) != sprite_declared:
        errors.append(f"{fixture}:blender_sprite_provenance_missing")
    return errors


def _check_playtest(root: Path, fixture: str) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    row = {"fixture": fixture, "root": str(root), "observed": False}
    if not _under_reviews(root):
        return row, [f"{fixture}:playtest_root_outside_reviews"]
    required = [root / "metadata.json", root / "host-result.json", root / "manifest.json"]
    if any(not path.is_file() for path in required):
        return row, [f"{fixture}:playtest_evidence_missing"]
    try:
        metadata, host, manifest = map(_read, required)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return row, [f"{fixture}:playtest_json_invalid:{type(exc).__name__}"]
    duration_ms = metadata.get("duration_ms")
    if not isinstance(duration_ms, (int, float)):
        # The delegated runner records the authoritative wall duration in the
        # host receipt; metadata only carries the 15-minute target.
        duration_ms = float(host.get("duration_seconds", 0)) * 1000
    row.update({"run_id": metadata.get("run_id"), "source_closure_sha256": metadata.get("source_closure_sha256"),
                "duration_ms": duration_ms, "perf": metadata.get("perf")})
    if metadata.get("schema") != "hh-gt09-delegated-playtest-2" or metadata.get("performed_by") != "agent" \
            or metadata.get("delegated_by") != "owner" or metadata.get("playtest_claim") is not False:
        errors.append(f"{fixture}:delegated_metadata")
    if duration_ms < 900_000:
        errors.append(f"{fixture}:duration_under_15m")
    if host.get("status") != "HOST_RUN_CAPTURED" or host.get("actual_process_exit") != 0 \
            or host.get("wrapper_exit_code") != 0 or host.get("tree", {}).get("verified") is not True:
        errors.append(f"{fixture}:host_exit_or_tree")
    if manifest.get("status") != "PLAYTEST_EVIDENCE_READY" or manifest.get("errors") != []:
        errors.append(f"{fixture}:manifest_not_ready")
    state = manifest.get("state_readback", {})
    if state.get("events", 0) <= 0 or state.get("final_phase") != "QUIT" or state.get("freeze_errors") != 0:
        errors.append(f"{fixture}:lifecycle_readback")
    perf = manifest.get("perf") or manifest.get("performance") or metadata.get("perf")
    if not isinstance(perf, dict) or perf.get("samples", 0) <= 0 or perf.get("budget_ms") is None \
            or perf.get("budget_ok") is not True:
        errors.append(f"{fixture}:perf_evidence_missing")
    row["observed"] = not errors
    return row, errors


def _check_repair(path: Path | None, fixtures: tuple[str, ...]) -> tuple[dict[str, Any], list[str]]:
    if path is None or not path.is_file():
        return {"observed": False, "path": str(path) if path else None}, ["seeded_repair_evidence_missing"]
    try:
        value = _read(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return {"observed": False, "path": str(path)}, ["seeded_repair_evidence_invalid"]
    errors: list[str] = []
    if value.get("schema") != "hh-gt09-seeded-repair-1" or value.get("authority") != 0:
        errors.append("seeded_repair_schema_or_authority")
    rows = value.get("fixtures")
    if not isinstance(rows, dict) or set(rows) != set(fixtures):
        errors.append("seeded_repair_fixture_rows")
    else:
        for fixture in fixtures:
            row = rows[fixture]
            if not isinstance(row, dict) or row.get("seeded_observed") is not True \
                    or not row.get("repair_command_ids") or len(row["repair_command_ids"]) != len(set(row["repair_command_ids"])) \
                    or row.get("postcondition_readback") is not True or row.get("replay_equal") is not True \
                    or row.get("checkpoint_verified") is not True:
                errors.append(f"{fixture}:seeded_repair_incomplete")
    return {"observed": not errors, "path": str(path), "sha256": _sha(path)}, errors


def build_report(*, arena: Path, room: Path, arena_playtest: Path | None = None,
                 room_playtest: Path | None = None, repair: Path | None = None) -> dict[str, Any]:
    native: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for fixture, root in (("arena", arena), ("room", room)):
        native[fixture], row_errors = _check_native(root, fixture)
        errors.extend(row_errors)
    playtests: dict[str, dict[str, Any]] = {}
    for fixture, root in (("arena", arena_playtest), ("room", room_playtest)):
        playtests[fixture], row_errors = _check_playtest(root, fixture) if root else ({"observed": False}, [f"{fixture}:playtest_path_missing"])
        errors.extend(row_errors)
    repair_row, repair_errors = _check_repair(repair, ("arena", "room"))
    errors.extend(repair_errors)
    closures = {row.get("source_closure_sha256") for row in native.values()}
    if len(closures) != 1 or None in closures:
        errors.append("native_source_closure_mismatch")
    catalogs = {row.get("catalog_digest") for row in native.values()}
    if len(catalogs) != 1 or None in catalogs:
        errors.append("catalog_digest_mismatch")
    return {"schema": REVISION, "authority": 0, "acceptance": False,
            "status": "CANDIDATE_PASS" if not errors else "OPEN",
            "native": native, "playtests": playtests, "seeded_repair": repair_row,
            "source_closures": sorted(value for value in closures if value),
            "catalog_digests": sorted(value for value in catalogs if value),
            "errors": errors,
            "next": "Provide producer-bound sprite/repair/perf evidence, then rerun on one frozen closure."}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arena", type=Path, required=True)
    parser.add_argument("--room", type=Path, required=True)
    parser.add_argument("--arena-playtest", type=Path)
    parser.add_argument("--room-playtest", type=Path)
    parser.add_argument("--repair", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = build_report(arena=args.arena, room=args.room, arena_playtest=args.arena_playtest,
                          room_playtest=args.room_playtest, repair=args.repair)
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8", newline="\n")
    print(encoded, end="")
    return 0 if report["status"] == "CANDIDATE_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
