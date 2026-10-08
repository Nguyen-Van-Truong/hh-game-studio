from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

try:
    from .fixture_lifecycle_manifest import LifecycleEvidenceError, build_manifest
except ImportError:  # direct unittest discovery from this directory
    from fixture_lifecycle_manifest import LifecycleEvidenceError, build_manifest


def _log(*, elapsed_ms: int = 900_000, freeze_errors: int = 0,
         playtest_claim: bool = False, include_quit: bool = True,
         final_state_elapsed: int | None = None) -> str:
    states = [
        {"event": "menu", "phase": "MENU", "wall_tick": 0, "elapsed_ms": 0},
        {"event": "start", "phase": "PLAYING", "wall_tick": 10, "elapsed_ms": 100},
        {"event": "pause", "phase": "PAUSED", "wall_tick": 20, "elapsed_ms": 200},
        {"event": "sample", "phase": "PAUSED", "wall_tick": 25, "elapsed_ms": 250},
        {"event": "resume", "phase": "PLAYING", "wall_tick": 30, "elapsed_ms": 300},
        {"event": "restart", "phase": "PLAYING", "wall_tick": 40, "elapsed_ms": 400},
    ]
    if include_quit:
        states.append({"event": "quit", "phase": "QUIT", "wall_tick": 90,
                       "elapsed_ms": elapsed_ms if final_state_elapsed is None else final_state_elapsed})
    for state in states:
        state.update({"seed": 90127,
                      "tree_paused": state["phase"] in ("MENU", "PAUSED", "QUIT"),
                      "menu_visible": state["phase"] != "PLAYING",
                      "freeze_errors": freeze_errors,
                      "world": {"tick": 1, "fixture": "synthetic",
                                "avatar_asset_loaded": True,
                                "sprite_asset_loaded": True}})
    edges = [
        {"edge": 1, "wall_tick": 1, "elapsed_ms": 90, "key": 4194309, "state": "pressed"},
        {"edge": 2, "wall_tick": 2, "elapsed_ms": 91, "key": 4194309, "state": "released"},
        {"edge": 3, "wall_tick": 3, "elapsed_ms": 190, "key": 80, "state": "pressed"},
        {"edge": 4, "wall_tick": 4, "elapsed_ms": 191, "key": 80, "state": "released"},
        {"edge": 5, "wall_tick": 5, "elapsed_ms": 290, "key": 80, "state": "pressed"},
        {"edge": 6, "wall_tick": 6, "elapsed_ms": 291, "key": 80, "state": "released"},
        {"edge": 7, "wall_tick": 7, "elapsed_ms": 390, "key": 82, "state": "pressed"},
        {"edge": 8, "wall_tick": 8, "elapsed_ms": 391, "key": 82, "state": "released"},
        {"edge": 9, "wall_tick": 9, "elapsed_ms": max(0, elapsed_ms - 100),
         "key": 81, "state": "pressed"},
    ]
    counts = {key: 1 for key in ("start", "pause", "resume", "restart", "quit")}
    return "\n".join([
        *("HH_FIXTURE_LIFECYCLE_INPUT " + json.dumps(edge) for edge in edges),
        *("HH_FIXTURE_LIFECYCLE_STATE " + json.dumps(state) for state in states),
        "HH_FIXTURE_LIFECYCLE_SUMMARY " + json.dumps({
            "schema": "hh-fixture-lifecycle-1", "authority": 0,
            "acceptance": False, "playtest_claim": playtest_claim,
            "elapsed_ms": elapsed_ms, "counts": counts,
            "input_edges": len(edges), "pause_frames": 4,
            "freeze_errors": freeze_errors, "lifecycle_complete": True,
            "mode": "scripted", "reason": "input_quit", "seed": 90127,
            "state_observations": len(states),
            "transitions": ["start", "pause", "resume", "restart", "quit"],
        }),
        "",
    ])


def _host(root: Path, *, run_id: str, fixture: str, source_hash: str,
          video: Path, log_hash: str, duration_seconds: float = 900.0) -> Path:
    # Keep this a complete synthetic host receipt.  The packer deliberately
    # requires independently bound engine/process/capture records; a small
    # host dictionary that only mirrors the child summary must stay rejected.
    try:
        from . import run_delegated_playtest as runner
    except ImportError:
        import run_delegated_playtest as runner

    project = root / "project"
    project.mkdir()
    (project / "project.godot").write_text("[application]\nconfig/name=\"fixture\"\n",
                                            encoding="utf-8")
    project_files = runner._source_files(project)
    host_files = {"tests/fixture_host.py": "c" * 64}
    binary_pins = {"godot_console": "d" * 64, "godot_gui": "e" * 64,
                   "ffmpeg": "f" * 64}
    source_hash = runner._full_closure(project_files, host_files, binary_pins)

    def capture(directory: Path, pid: int) -> str:
        directory.mkdir(parents=True)
        (directory / "stdout.txt").write_bytes(b"")
        (directory / "stderr.txt").write_bytes(b"")
        (directory / "process-start.json").write_text(json.dumps({"pid": pid}), encoding="utf-8")
        (directory / "process-exit.json").write_text(
            json.dumps({"pid": pid, "exit_code": 0}), encoding="utf-8")
        artifacts = {name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
                     for name in ("stdout.txt", "stderr.txt", "process-start.json", "process-exit.json")}
        report = {"artifacts": artifacts, "actual_process_exit": {"pid": pid, "exit_code": 0},
                  "wrapper_exit_code": 0, "completed": True, "natural_tree_exit": True,
                  "active_before_cleanup": 0,
                  "job": {"closed": True, "zero_observed": True, "tainted": False,
                          "handle_retained": False}}
        raw = json.dumps(report, sort_keys=True).encode("utf-8")
        (directory / "capture.json").write_bytes(raw)
        return hashlib.sha256(raw).hexdigest()

    native_sha = capture(root / "native", 101)
    imported = project / ".godot" / "imported"
    imported.mkdir(parents=True)
    imported_files = {
        "avatar.glb-fixture.scn": b"avatar",
        "sprite_sheet.png-fixture.ctex": b"sprite",
    }
    for name, payload in imported_files.items():
        (imported / name).write_bytes(payload)
    import_sha = capture(root / "import", 100)
    decoded_sha = capture(root / "video-verify", 202)
    (root / "metadata.json").write_text(json.dumps({
        "source_files": project_files, "host_files": host_files,
        "binary_pins": binary_pins,
    }), encoding="utf-8")
    (root / "godot.stderr.log").write_bytes(b"")
    value = {
        "schema": "hh-gt09-delegated-playtest-host-2", "run_id": run_id,
        "fixture": fixture, "authority": 0, "acceptance": False,
        "performed_by": "agent", "delegated_by": "owner",
        "source_closure_sha256": source_hash, "godot_pin": "4.7.2-stable",
        "status": "HOST_RUN_CAPTURED",
        "actual_process_exit": 0, "timed_out": False, "duration_seconds": duration_seconds,
        "stdout_sha256": log_hash,
        "stderr_sha256": hashlib.sha256(b"").hexdigest(),
        "errors": [], "source_unchanged": True, "probe_closed": True,
        "engine_exit_observation": {
            "provider": "WaitForSingleObject+GetExitCodeProcess", "exit_code": 0},
        "handle_samples": [{"held_handles": 4}, {"held_handles": 4}],
        "process_handle": {"required": True, "closed": True,
                           "close_uncertain": False, "handle_retained": False},
        "tree": {"verified": True, "active_before_close": 0, "active_after_close": 0},
        "job": {"configured": True, "assigned": True, "closed": True,
                "handle_retained": False, "tainted": False, "failed_operations": []},
        "native_capture": {"path": str(root / "native" / "capture.json"),
                           "sha256": native_sha},
        "import": {"actual_process_exit": 0,
                    "capture": {"path": str(root / "import" / "capture.json"),
                                 "actual_process_exit": {"exit_code": 0}},
                    "capture_sha256": import_sha,
                    "cache": {"files": {name: hashlib.sha256((imported / name).read_bytes()).hexdigest()
                                         for name in imported_files},
                              "sha256": "a" * 64}},
        "video": {"status": "decoded", "sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
                  "bytes": video.stat().st_size, "duration_seconds": duration_seconds,
                  "decoded_frames": int(duration_seconds * 8),
                  "capture_sha256": decoded_sha},
    }
    path = root / "host-result.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path, source_hash


class FixtureLifecycleManifestTests(unittest.TestCase):
    def test_delegated_record_requires_video_and_stays_incomplete_without_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log = root / "stdout.log"
            log.write_text(_log(), encoding="utf-8")
            report = build_manifest(fixture="arena_2d", run_id="run-01",
                                    log_path=log, source_closure_sha256="a" * 64)
            self.assertEqual(report["status"], "INCOMPLETE")
            self.assertIn("video_missing", report["errors"])
            self.assertEqual(report["performed_by"], "agent")
            self.assertEqual(report["delegated_by"], "owner")
            self.assertFalse(report["playtest_claim"])

    def test_video_and_full_trace_make_candidate_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log = root / "stdout.log"
            video = root / "capture.mkv"
            log.write_text(_log(), encoding="utf-8")
            video.write_bytes(b"captured-by-host")
            host, source_hash = _host(root, run_id="run-02", fixture="room_3d",
                                     source_hash="b" * 64, video=video,
                                     log_hash=hashlib.sha256(log.read_bytes()).hexdigest())
            report = build_manifest(fixture="room_3d", run_id="run-02",
                                    log_path=log, source_closure_sha256=source_hash,
                                    video_path=video, host_result_path=host)
            self.assertEqual(report["status"], "PLAYTEST_EVIDENCE_READY")
            self.assertEqual(report["video"]["sha256"],
                             hashlib.sha256(video.read_bytes()).hexdigest())

    def test_short_or_forged_child_record_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log = root / "stdout.log"
            log.write_text(_log(elapsed_ms=10, playtest_claim=True), encoding="utf-8")
            report = build_manifest(fixture="arena_2d", run_id="run-03",
                                    log_path=log, source_closure_sha256="c" * 64)
            self.assertEqual(report["status"], "INCOMPLETE")
            self.assertIn("summary_playtest_claim", report["errors"])
            self.assertIn("duration_too_short", report["errors"])

    def test_pause_freeze_error_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log = root / "stdout.log"
            log.write_text(_log(freeze_errors=1), encoding="utf-8")
            report = build_manifest(fixture="arena_2d", run_id="run-04",
                                    log_path=log, source_closure_sha256="d" * 64)
            self.assertIn("pause_freeze_errors", report["errors"])

    def test_final_state_allows_small_clock_jitter(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log = root / "stdout.log"
            log.write_text(_log(elapsed_ms=900_001, final_state_elapsed=900_000), encoding="utf-8")
            summary, states, inputs = __import__(
                "studio.tests.godot.fixture_lifecycle_manifest",
                fromlist=["parse_log"],
            ).parse_log(log.read_text(encoding="utf-8"))
            errors = __import__(
                "studio.tests.godot.fixture_lifecycle_manifest",
                fromlist=["_required_lifecycle"],
            )._required_lifecycle(summary, states, inputs, min_seconds=0)
            self.assertNotIn("state_summary_binding", errors)

    def test_final_state_rejects_large_clock_gap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log = root / "stdout.log"
            log.write_text(_log(elapsed_ms=900_201, final_state_elapsed=900_000), encoding="utf-8")
            module = __import__(
                "studio.tests.godot.fixture_lifecycle_manifest",
                fromlist=["parse_log", "_required_lifecycle"],
            )
            summary, states, inputs = module.parse_log(log.read_text(encoding="utf-8"))
            errors = module._required_lifecycle(summary, states, inputs, min_seconds=0)
            self.assertIn("state_summary_binding", errors)


if __name__ == "__main__":
    unittest.main()
