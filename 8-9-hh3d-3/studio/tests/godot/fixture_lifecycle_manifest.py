"""Fail-closed packer for delegated fixture lifecycle evidence.

Godot's stdout is untrusted child observation.  A candidate package requires
the matching host receipt (actual exit, Job/tree and handle cleanup), the
frozen source closure and a non-empty host captured video.  No child field can
replace a host observation or create an acceptance signature.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

SCHEMA = "hh-fixture-lifecycle-evidence-2"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$")
_PREFIXES = {
    "input": "HH_FIXTURE_LIFECYCLE_INPUT ",
    "state": "HH_FIXTURE_LIFECYCLE_STATE ",
    "summary": "HH_FIXTURE_LIFECYCLE_SUMMARY ",
}
_COMMANDS = ("start", "pause", "resume", "restart", "quit")
_STATE_SUMMARY_BINDING_TOLERANCE_MS = 100
_PHASES = {"menu": "MENU", "start": "PLAYING", "pause": "PAUSED",
           "resume": "PLAYING", "restart": "PLAYING", "quit": "QUIT"}
_KEYS = {"start": {4194309}, "pause": {80, 4194305},
         "resume": {4194309, 80, 4194305}, "restart": {82}, "quit": {81}}


def _read_json(raw: bytes | str) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("duplicate_key")
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite")))


def _sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


class LifecycleEvidenceError(ValueError):
    """Raised when evidence cannot be bound without guessing."""


def _json_line(raw: str, prefix: str, line_no: int) -> dict[str, Any]:
    try:
        value = _read_json(raw[len(prefix):])
    except (TypeError, ValueError) as exc:
        raise LifecycleEvidenceError(f"line_{line_no}:invalid_json") from exc
    if type(value) is not dict:
        raise LifecycleEvidenceError(f"line_{line_no}:object_required")
    return value


def parse_log(log: str) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    summary: dict[str, Any] | None = None
    states: list[dict[str, Any]] = []
    inputs: list[dict[str, Any]] = []
    for line_no, line in enumerate(log.splitlines(), 1):
        for kind, prefix in _PREFIXES.items():
            if not line.startswith(prefix):
                continue
            value = _json_line(line, prefix, line_no)
            if kind == "summary":
                if summary is not None:
                    raise LifecycleEvidenceError("duplicate_summary")
                summary = value
            elif kind == "state":
                states.append(value)
            else:
                inputs.append(value)
            break
    if summary is None:
        raise LifecycleEvidenceError("summary_missing")
    if not states:
        raise LifecycleEvidenceError("state_readback_missing")
    return summary, states, inputs


def _require_sha(value: Any, field: str) -> str:
    if type(value) is not str or not _SHA256.fullmatch(value):
        raise LifecycleEvidenceError(f"{field}:sha256_required")
    return value


def _required_lifecycle(summary: dict[str, Any], states: list[dict[str, Any]],
                        inputs: list[dict[str, Any]], *, min_seconds: float) -> list[str]:
    errors: list[str] = []
    if summary.get("schema") != "hh-fixture-lifecycle-1":
        errors.append("summary_schema")
    if summary.get("authority") != 0:
        errors.append("summary_authority")
    if summary.get("acceptance") is not False:
        errors.append("summary_acceptance")
    if summary.get("playtest_claim") is not False:
        errors.append("summary_playtest_claim")
    counts = summary.get("counts")
    if type(counts) is not dict:
        errors.append("summary_counts")
    else:
        for command in _COMMANDS:
            if type(counts.get(command)) is not int or counts[command] < 1:
                errors.append(f"count_{command}")
    if type(summary.get("freeze_errors")) is not int or summary["freeze_errors"] != 0:
        errors.append("pause_freeze_errors")
    if type(summary.get("pause_frames")) is not int or summary["pause_frames"] < 2:
        errors.append("pause_freeze_samples")
    if summary.get("lifecycle_complete") is not True:
        errors.append("lifecycle_complete")
    elapsed = summary.get("elapsed_ms")
    if type(elapsed) is not int or elapsed < int(min_seconds * 1000):
        errors.append("duration_too_short")
    if type(summary.get("input_edges")) is not int or summary["input_edges"] != len(inputs):
        errors.append("input_edge_count")
    if len(states) < len(_COMMANDS) + 1:
        errors.append("state_readback_count")
    events = {state.get("event") for state in states}
    for event in ("menu", *_COMMANDS):
        if event not in events:
            errors.append(f"state_event_{event}")
    if states[-1].get("phase") != "QUIT":
        errors.append("final_phase")
    if summary.get("mode") != "scripted" or summary.get("reason") != "input_quit":
        errors.append("scripted_input_quit_required")
    if type(summary.get("state_observations")) is not int or summary["state_observations"] != len(states):
        errors.append("state_observation_count")
    state_transitions = [state.get("event") for state in states if state.get("event") in _COMMANDS]
    if summary.get("transitions") != state_transitions:
        errors.append("transition_sequence")
    if summary.get("seed") != 90127:
        errors.append("seed")
    pressed: set[int] = set()
    input_previous_ms = -1
    for index, edge in enumerate(inputs, 1):
        if edge.get("edge") != index or type(edge.get("key")) is not int:
            errors.append("input_sequence")
            break
        if type(edge.get("elapsed_ms")) is not int or edge["elapsed_ms"] < input_previous_ms:
            errors.append("input_time_sequence")
            break
        input_previous_ms = edge["elapsed_ms"]
        key = edge["key"]
        if edge.get("state") == "pressed" and key not in pressed:
            pressed.add(key)
        elif edge.get("state") == "released" and key in pressed:
            pressed.remove(key)
        else:
            errors.append("input_edge_pair")
            break
    previous_ms = -1
    pause_world: dict[str, Any] | None = None
    frozen_samples = 0
    for state in states:
        event, phase, wall_tick, observed_ms = state.get("event"), state.get("phase"), state.get("wall_tick"), state.get("elapsed_ms")
        if type(observed_ms) is not int or observed_ms < previous_ms or type(wall_tick) is not int or wall_tick < 0:
            errors.append("state_time_sequence")
            break
        previous_ms = observed_ms
        world = state.get("world")
        if type(world) is not dict or not world or world.get("readback_failed") is True:
            errors.append("world_readback")
            break
        if world.get("avatar_asset_loaded") is not True or world.get("sprite_asset_loaded") is not True:
            errors.append("asset_readback")
        if event in _PHASES and phase != _PHASES[event]:
            errors.append("transition_phase")
        if state.get("seed") != 90127 or state.get("freeze_errors") != 0:
            errors.append("state_seed_or_freeze")
        if state.get("tree_paused") is not (phase in ("MENU", "PAUSED", "QUIT")):
            errors.append("state_tree_pause")
        if state.get("menu_visible") is not (phase != "PLAYING"):
            errors.append("state_menu")
        if event in _COMMANDS:
            candidates = [edge for edge in inputs if edge.get("state") == "pressed"
                          and edge.get("key") in _KEYS[event] and edge.get("elapsed_ms", -1) <= observed_ms]
            if not candidates or observed_ms - candidates[-1]["elapsed_ms"] > 250:
                errors.append("transition_input_binding")
        simulation = {key: value for key, value in world.items() if not key.startswith("input_")}
        if phase == "PAUSED":
            if pause_world is None:
                pause_world = simulation
            elif simulation != pause_world:
                errors.append("pause_readback_changed")
            else:
                frozen_samples += 1
        elif event == "resume":
            if pause_world is not None and simulation != pause_world:
                errors.append("resume_readback_changed")
            pause_world = None
    if frozen_samples < 1:
        errors.append("pause_readback_samples")
    summary_elapsed = summary.get("elapsed_ms")
    state_elapsed = states[-1].get("elapsed_ms")
    if (states[0].get("event") != "menu" or
            type(state_elapsed) is not int or type(summary_elapsed) is not int or
            abs(state_elapsed - summary_elapsed) > _STATE_SUMMARY_BINDING_TOLERANCE_MS):
        errors.append("state_summary_binding")
    return errors


def _host_errors(host: dict[str, Any], *, run_id: str, fixture: str,
                 source_hash: str, log_hash: str,
                 minimum_duration_seconds: float) -> list[str]:
    errors: list[str] = []
    if host.get("schema") != "hh-gt09-delegated-playtest-host-2":
        errors.append("host_schema")
    if host.get("run_id") != run_id or host.get("fixture") != fixture:
        errors.append("host_identity")
    if host.get("authority") != 0 or host.get("acceptance") is not False:
        errors.append("host_authority")
    if host.get("performed_by") != "agent" or host.get("delegated_by") != "owner":
        errors.append("host_attribution")
    if host.get("source_closure_sha256") != source_hash:
        errors.append("host_source_hash")
    if host.get("godot_pin") != "4.7.2-stable":
        errors.append("host_godot_pin")
    if host.get("status") != "HOST_RUN_CAPTURED":
        errors.append("host_status")
    if type(host.get("actual_process_exit")) is not int or host["actual_process_exit"] != 0:
        errors.append("host_actual_exit")
    if host.get("timed_out") is not False:
        errors.append("host_timeout")
    duration = host.get("duration_seconds")
    if type(duration) not in (int, float) or not math.isfinite(duration) or duration < minimum_duration_seconds:
        errors.append("host_duration_too_short")
    if host.get("errors") != [] or host.get("source_unchanged") is not True:
        errors.append("host_errors_or_source_drift")
    if host.get("probe_closed") is not True:
        errors.append("host_probe_handle")
    observed = host.get("engine_exit_observation")
    if type(observed) is not dict or observed.get("provider") != "WaitForSingleObject+GetExitCodeProcess" or observed.get("exit_code") != 0:
        errors.append("host_engine_exit_observation")
    samples = host.get("handle_samples")
    if type(samples) is not list or len(samples) < 2 or any(type(sample.get("held_handles")) is not int for sample in samples):
        errors.append("host_handle_samples")
    if type(host.get("stdout_sha256")) is not str or not _SHA256.fullmatch(host["stdout_sha256"]):
        errors.append("host_stdout_hash")
    if type(host.get("stderr_sha256")) is not str or not _SHA256.fullmatch(host["stderr_sha256"]):
        errors.append("host_stderr_hash")
    if host.get("stdout_sha256") != log_hash:
        errors.append("host_stdout_log_binding")
    handles = host.get("process_handle")
    if type(handles) is not dict or handles != {"required": True, "closed": True,
                                                 "close_uncertain": False, "handle_retained": False}:
        errors.append("host_process_handle")
    tree = host.get("tree")
    if type(tree) is not dict or tree.get("verified") is not True:
        errors.append("host_tree")
    else:
        if tree.get("active_before_close") != 0 or tree.get("active_after_close") != 0:
            errors.append("host_tree_active")
    job = host.get("job")
    if type(job) is not dict:
        errors.append("host_job")
    else:
        for key, expected in (("configured", True), ("assigned", True), ("closed", True),
                              ("handle_retained", False), ("tainted", False)):
            if job.get(key) is not expected:
                errors.append(f"host_job_{key}")
        if job.get("failed_operations") != []:
            errors.append("host_job_failures")
    return errors


def build_manifest(*, fixture: str, run_id: str, log_path: Path,
                   source_closure_sha256: str, performed_by: str = "agent",
                   delegated_by: str = "owner", video_path: Path | None = None,
                   host_result_path: Path | None = None,
                   minimum_duration_seconds: float = 900.0) -> dict[str, Any]:
    """Build an evidence record; READY requires all independently captured proofs."""
    if not fixture or not _RUN_ID.fullmatch(fixture):
        raise LifecycleEvidenceError("fixture_invalid")
    if not _RUN_ID.fullmatch(run_id):
        raise LifecycleEvidenceError("run_id_invalid")
    source_hash = _require_sha(source_closure_sha256, "source_closure_sha256")
    if performed_by != "agent" or delegated_by != "owner":
        raise LifecycleEvidenceError("delegated_attribution_required")
    if not log_path.is_file():
        raise LifecycleEvidenceError("log_missing")
    raw = log_path.read_bytes()
    log_hash = hashlib.sha256(raw).hexdigest()
    try:
        summary, states, inputs = parse_log(raw.decode("utf-8", errors="strict"))
    except UnicodeDecodeError as exc:
        raise LifecycleEvidenceError("log_invalid_utf8") from exc
    errors = _required_lifecycle(summary, states, inputs, min_seconds=minimum_duration_seconds)
    if not math.isfinite(minimum_duration_seconds) or minimum_duration_seconds < 900:
        raise LifecycleEvidenceError("minimum_duration_below_owner_gate")
    if re.search(r"(?im)^(?:ERROR|WARNING|SCRIPT ERROR|USER ERROR):", raw.decode("utf-8")):
        errors.append("godot_log_error_or_warning")
    trace_bytes = ("\n".join(json.dumps(edge, sort_keys=True, separators=(",", ":"))
                   for edge in inputs)).encode("utf-8")
    trace_hash = hashlib.sha256(trace_bytes).hexdigest()

    host: dict[str, Any] | None = None
    if host_result_path is None:
        errors.append("host_result_missing")
        host_record = {"status": "missing", "path": None, "sha256": None}
    elif not host_result_path.is_file():
        errors.append("host_result_missing")
        host_record = {"status": "missing", "path": str(host_result_path), "sha256": None}
    else:
        host_raw = host_result_path.read_bytes()
        try:
            host = _read_json(host_raw)
        except (UnicodeDecodeError, ValueError) as exc:
            raise LifecycleEvidenceError("host_result_invalid_json") from exc
        if type(host) is not dict:
            raise LifecycleEvidenceError("host_result_object_required")
        errors.extend(_host_errors(host, run_id=run_id, fixture=fixture,
                                   source_hash=source_hash, log_hash=log_hash,
                                   minimum_duration_seconds=minimum_duration_seconds))
        host_record = {"status": "captured", "path": str(host_result_path),
                       "sha256": hashlib.sha256(host_raw).hexdigest()}
        root = host_result_path.parent
        metadata_path = root / "metadata.json"
        if not metadata_path.is_file():
            errors.append("freeze_metadata_missing")
        else:
            try:
                freeze = _read_json(metadata_path.read_bytes())
                project = root / "project"
                from . import run_delegated_playtest as runner
            except ImportError:
                import run_delegated_playtest as runner
            try:
                project_files = runner._source_files(project)
                if (freeze.get("source_files") != project_files or
                    runner._full_closure(project_files, freeze.get("host_files", {}), freeze.get("binary_pins", {})) != source_hash):
                    errors.append("freeze_source_binding")
            except (ValueError, OSError, TypeError) as error:
                errors.append("freeze_invalid")
        stderr_path = root / "godot.stderr.log"
        if not stderr_path.is_file() or _sha(stderr_path) != host.get("stderr_sha256"):
            errors.append("stderr_host_binding")
        elif stderr_path.read_bytes().strip():
            errors.append("stderr_not_empty")
        capture_path = root / "native" / "capture.json"
        capture_binding = host.get("native_capture")
        if type(capture_binding) is not dict or not capture_path.is_file() or _sha(capture_path) != capture_binding.get("sha256"):
            errors.append("native_capture_binding")
        else:
            try:
                from studio.pipeline.native_job import verify_captured_stage
                verify_captured_stage(root / "native", capture_binding["sha256"])
            except (ValueError, RuntimeError, OSError, KeyError):
                errors.append("native_capture_invalid")
        import_result = host.get("import")
        import_capture_path = root / "import" / "capture.json"
        if type(import_result) is not dict:
            errors.append("import_result_missing")
        else:
            import_capture = import_result.get("capture")
            actual_import_exit = (import_capture.get("actual_process_exit", {}).get("exit_code")
                                  if type(import_capture) is dict else None)
            if actual_import_exit != 0:
                errors.append("import_actual_exit")
            import_capture_sha = import_result.get("capture_sha256")
            if (type(import_capture) is not dict or type(import_capture_sha) is not str
                    or not _SHA256.fullmatch(import_capture_sha)
                    or not import_capture_path.is_file()
                    or _sha(import_capture_path) != import_capture_sha):
                errors.append("import_capture_binding")
            else:
                try:
                    from studio.pipeline.native_job import verify_captured_stage
                    verify_captured_stage(root / "import", import_capture_sha)
                except (ValueError, RuntimeError, OSError, KeyError):
                    errors.append("import_capture_invalid")
            cache = import_result.get("cache")
            if (type(cache) is not dict or type(cache.get("files")) is not dict
                    or not cache["files"] or type(cache.get("sha256")) is not str
                    or not _SHA256.fullmatch(cache["sha256"])):
                errors.append("import_cache_binding")

    if video_path is None:
        video = {"status": "not_captured", "path": None, "sha256": None, "bytes": 0}
        errors.append("video_missing")
    elif not video_path.is_file() or video_path.stat().st_size <= 0:
        video = {"status": "missing", "path": str(video_path), "sha256": None, "bytes": 0}
        errors.append("video_missing")
    else:
        video = {"status": "captured", "path": str(video_path),
                 "sha256": _sha(video_path),
                 "bytes": video_path.stat().st_size}
        if host is None or type(host.get("video")) is not dict or host["video"].get("status") != "decoded":
            errors.append("video_host_binding")
        elif host["video"].get("sha256") != video["sha256"]:
            errors.append("video_hash_mismatch")
        else:
            media = host["video"]
            media_duration = media.get("duration_seconds")
            if (type(media_duration) not in (int, float) or not math.isfinite(media_duration)
                    or media_duration < minimum_duration_seconds or type(media.get("decoded_frames")) is not int
                    or media["decoded_frames"] < int(minimum_duration_seconds * 8)):
                errors.append("video_duration_or_frames")
            decode_root = host_result_path.parent / "video-verify"
            if not (decode_root / "capture.json").is_file() or _sha(decode_root / "capture.json") != media.get("capture_sha256"):
                errors.append("video_decode_capture")
            else:
                try:
                    from studio.pipeline.native_job import verify_captured_stage
                    verify_captured_stage(decode_root, media["capture_sha256"])
                except (ValueError, RuntimeError, OSError, KeyError):
                    errors.append("video_decode_invalid")

    return {
        "schema": SCHEMA, "authority": 0, "acceptance": False, "playtest_claim": False,
        "fixture": fixture, "run_id": run_id, "performed_by": performed_by,
        "delegated_by": delegated_by, "source_closure_sha256": source_hash,
        "raw_log": {"path": str(log_path), "sha256": log_hash, "bytes": len(raw)},
        "host_result": host_record,
        "input_trace": {"sha256": trace_hash, "edges": len(inputs)},
        "state_readback": {"events": len(states), "final_phase": states[-1].get("phase"),
                            "freeze_errors": summary.get("freeze_errors")},
        "duration_ms": summary.get("elapsed_ms"), "summary": summary, "video": video,
        "status": "PLAYTEST_EVIDENCE_READY" if not errors else "INCOMPLETE", "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--source-closure-sha256", required=True)
    parser.add_argument("--host-result", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--minimum-duration-seconds", type=float, default=900.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        report = build_manifest(fixture=args.fixture, run_id=args.run_id, log_path=args.log,
                                source_closure_sha256=args.source_closure_sha256,
                                host_result_path=args.host_result, video_path=args.video,
                                minimum_duration_seconds=args.minimum_duration_seconds)
    except LifecycleEvidenceError as exc:
        print(json.dumps({"schema": SCHEMA, "status": "REJECTED", "error": str(exc)}, sort_keys=True))
        return 2
    encoded = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8", newline="\n")
    print(encoded, end="")
    return 0 if report["status"] == "PLAYTEST_EVIDENCE_READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
