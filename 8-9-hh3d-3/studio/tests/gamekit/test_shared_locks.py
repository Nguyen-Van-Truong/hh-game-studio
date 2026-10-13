"""Process-isolated tests for the physical project lock and the measurement reservation.

No Godot or Blender process is started. Engine entry points are refused or patched
before spawn.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import traceback
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from studio.gamekit import common as C
from studio.gamekit import perf as perf_mod
from studio.gamekit import play as play_mod


def _dead_pid() -> int:
    proc = subprocess.Popen([sys.executable, "-B", "-c", "raise SystemExit(0)"])
    pid = proc.pid
    proc.wait(timeout=15)
    if not C._pid_alive(pid):
        return pid
    if not C._pid_alive(2147483647):
        return 2147483647
    raise AssertionError("no proven-dead pid")


def _stop_child(proc: subprocess.Popen[bytes], release: Path) -> None:
    try:
        release.parent.mkdir(parents=True, exist_ok=True)
        release.write_text("1", encoding="utf-8")
    except OSError:
        pass
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def _child_wait_release() -> None:
    release = Path(os.environ["HH_RELEASE"])
    deadline = time.monotonic() + 40
    while not release.exists():
        if time.monotonic() > deadline:
            raise SystemExit(3)
        time.sleep(0.05)


def _child_main() -> None:
    try:
        mode = os.environ["HH_LOCK_MODE"]
        held = Path(os.environ["HH_HELD"])
        if mode == "measure":
            with C.measure_window("child-measure", wait_seconds=0):
                held.write_text(str(os.getpid()), encoding="utf-8")
                print("measure-held", flush=True)
                _child_wait_release()
            return
        project = C.Project(os.environ["HH_PID"], Path(os.environ["HH_PROJECT"]))
        with C.project_lock(project, "child", wait_seconds=0):
            held.write_text(str(os.getpid()), encoding="utf-8")
            print("project-held", flush=True)
            _child_wait_release()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)


class SharedLockTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.tmp.name)
        self._saved = {
            "HH_GAMEKIT_STATE": os.environ.get("HH_GAMEKIT_STATE"),
            "HH_GAMEKIT_SHARED_LOCK_DIR": os.environ.get("HH_GAMEKIT_SHARED_LOCK_DIR"),
            "HH_GAMEKIT_MEASURE_LOCK": os.environ.get("HH_GAMEKIT_MEASURE_LOCK"),
        }
        os.environ["HH_GAMEKIT_STATE"] = str(self.root / "state")
        os.environ["HH_GAMEKIT_SHARED_LOCK_DIR"] = str(self.root / "shared-locks")
        os.environ["HH_GAMEKIT_MEASURE_LOCK"] = str(self.root / "measure-window.lock")
        self.game = self.root / "game"
        self.game.mkdir()
        (self.game / "project.godot").write_text("config_version=5\n", encoding="utf-8")
        self.project = C.register_project(self.game, "game")
        self._children: list[tuple[subprocess.Popen[bytes], Path]] = []
        self._handles: list[object] = []

    def tearDown(self) -> None:
        for proc, release in self._children:
            _stop_child(proc, release)
        for handle in self._handles:
            handle.close()
        for key, old in self._saved.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old
        self.tmp.cleanup()

    def _spawn(self, mode: str, *, project: Path, project_id: str, state: Path) -> tuple[subprocess.Popen[bytes], Path, Path, Path]:
        token = os.urandom(3).hex()
        held = self.root / f"held-{mode}-{token}"
        release = self.root / f"release-{mode}-{token}"
        log_path = self.root / f"child-{mode}-{token}.log"
        env = os.environ.copy()
        env.update({
            "HH_LOCK_CHILD": "1",
            "HH_LOCK_MODE": mode,
            "HH_HELD": str(held),
            "HH_RELEASE": str(release),
            "HH_PID": project_id,
            "HH_PROJECT": str(project),
            "HH_GAMEKIT_STATE": str(state),
            "PYTHONPATH": str(_REPO) + os.pathsep + env.get("PYTHONPATH", ""),
            "PYTHONIOENCODING": "utf-8",
        })
        handle = open(log_path, "w", encoding="utf-8")
        self._handles.append(handle)
        proc = subprocess.Popen(
            [sys.executable, "-B", str(Path(__file__).resolve())],
            cwd=str(_REPO),
            env=env,
            stdout=handle,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self._children.append((proc, release))
        return proc, held, release, log_path

    def _wait_held(self, proc: subprocess.Popen[bytes], held: Path, log_path: Path) -> None:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if held.is_file():
                return
            if proc.poll() is not None:
                text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.is_file() else ""
                self.fail(f"child exited {proc.returncode} before holding the lock\n{text}")
            time.sleep(0.05)
        text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.is_file() else ""
        self.fail(f"timed out waiting for the child lock\n{text}")

    def test_distinct_states_cannot_lock_one_root_and_distinct_roots_can(self) -> None:
        other = self.root / "other-game"
        other.mkdir()
        (other / "project.godot").write_text("config_version=5\n", encoding="utf-8")
        proc, held, release, log_path = self._spawn(
            "project",
            project=self.game,
            project_id="other",
            state=self.root / "state-other",
        )
        self._wait_held(proc, held, log_path)
        self.assertNotEqual(os.environ["HH_GAMEKIT_STATE"], str(self.root / "state-other"))
        started = time.monotonic()
        with self.assertRaises(C.GamekitError) as blocked:
            with C.project_lock(self.project, "parent", wait_seconds=0.35):
                self.fail("same physical root locked twice")
        elapsed = time.monotonic() - started
        self.assertEqual(blocked.exception.code, "LOCKED")
        self.assertGreaterEqual(elapsed, 0.2)
        self.assertLess(elapsed, 2.0)
        with C.project_lock(C.Project("side", other), "side", wait_seconds=0):
            self.assertNotEqual(
                C.shared_project_lock_path(self.game),
                C.shared_project_lock_path(other),
            )
        release.write_text("1", encoding="utf-8")
        self.assertEqual(proc.wait(timeout=15), 0)
        with C.project_lock(self.project, "after", wait_seconds=0):
            shared = C.shared_project_lock_path(self.project.root)
            self.assertTrue(shared.is_file())
            self.assertFalse(C.is_within(shared, self.project.root))
            self.assertFalse(C.is_within(shared, self.project.state))
            self.assertTrue((self.project.state / "project.lock").is_file())
        self.assertFalse(C.shared_project_lock_path(self.project.root).exists())
        self.assertFalse((self.project.state / "project.lock").exists())

    def test_casefold_and_nested_lock(self) -> None:
        text = str(self.game)
        flipped = Path(text[:1].swapcase() + text[1:])
        self.assertEqual(C.canonical_project_root(self.game), C.canonical_project_root(flipped))
        self.assertEqual(C.canonical_project_root(self.game), C.canonical_project_root(self.game / "."))
        with C.project_lock(C.Project("one", self.game), "a", wait_seconds=0):
            started = time.monotonic()
            with self.assertRaises(C.GamekitError) as cm:
                with C.project_lock(C.Project("two", flipped), "b", wait_seconds=5):
                    self.fail("case-folded root locked twice")
            self.assertEqual(cm.exception.code, "LOCKED")
            self.assertLess(time.monotonic() - started, 1.0)
        with C.project_lock(self.project, "third", wait_seconds=0):
            pass

    def test_release_after_exception_and_foreign_bytes_survive(self) -> None:
        with self.assertRaises(RuntimeError):
            with C.project_lock(self.project, "boom", wait_seconds=0):
                raise RuntimeError("boom")
        with C.project_lock(self.project, "after-exception", wait_seconds=0):
            pass
        shared = C.shared_project_lock_path(self.project.root)
        foreign = (
            json.dumps({
                "schema": "hh-gamekit-lock-1",
                "pid": os.getpid(),
                "purpose": "foreign",
                "nonce": "not-ours",
            })
            + "\n"
        ).encode("utf-8")
        with C.project_lock(self.project, "own", wait_seconds=0):
            shared.write_bytes(foreign)
        self.assertEqual(shared.read_bytes(), foreign)
        with self.assertRaises(C.GamekitError) as cm:
            with C.project_lock(self.project, "next", wait_seconds=0):
                self.fail("live foreign marker was stolen")
        self.assertEqual(cm.exception.code, "LOCKED")
        self.assertEqual(shared.read_bytes(), foreign)

    def test_stale_marker_recovered_and_malformed_not_stolen(self) -> None:
        dead = _dead_pid()
        self.assertFalse(C._pid_alive(dead))
        shared = C.shared_project_lock_path(self.project.root)
        shared.parent.mkdir(parents=True, exist_ok=True)
        legacy = (json.dumps({"pid": dead, "purpose": "old", "at": "then"}) + "\n").encode("utf-8")
        shared.write_bytes(legacy)
        state = self.project.state / "project.lock"
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_bytes(legacy)
        with C.project_lock(self.project, "recovered", wait_seconds=0):
            current = json.loads(shared.read_text(encoding="utf-8"))
            self.assertEqual(current["pid"], os.getpid())
            self.assertEqual(current["purpose"], "recovered")
            self.assertEqual(current["schema"], "hh-gamekit-lock-1")
        self.assertFalse(shared.exists())
        self.assertFalse(state.exists())

        shared.write_bytes(b"{")
        with self.assertRaises(C.GamekitError) as cm:
            with C.project_lock(self.project, "bad", wait_seconds=0):
                self.fail("malformed marker was taken")
        self.assertEqual(cm.exception.code, "LOCK_MALFORMED")
        self.assertEqual(shared.read_bytes(), b"{")
        shared.write_bytes(b'{"pid":"1"}\n')
        with self.assertRaises(C.GamekitError) as cm:
            with C.project_lock(self.project, "bad-pid", wait_seconds=0):
                self.fail("string pid was taken")
        self.assertEqual(cm.exception.code, "LOCK_MALFORMED")
        self.assertEqual(shared.read_bytes(), b'{"pid":"1"}\n')

    def test_stale_replace_rechecks_bytes_before_unlink(self) -> None:
        dead = _dead_pid()
        shared = C.shared_project_lock_path(self.project.root)
        shared.parent.mkdir(parents=True, exist_ok=True)
        original = (json.dumps({"pid": dead, "purpose": "stale"}) + "\n").encode("utf-8")
        shared.write_bytes(original)
        calls = {"n": 0}
        real = C._read_lock_bytes

        def flaky(path: Path, **kwargs: object) -> bytes:
            if Path(path) == shared:
                calls["n"] += 1
                if calls["n"] == 1:
                    return original
                if calls["n"] == 2:
                    return original + b" "
            return real(path, **kwargs)

        with patch.object(C, "_read_lock_bytes", side_effect=flaky):
            with self.assertRaises(C.GamekitError) as cm:
                with C.project_lock(self.project, "race", wait_seconds=0):
                    self.fail("changed stale marker was unlinked")
        self.assertEqual(cm.exception.code, "LOCKED")
        self.assertEqual(shared.read_bytes(), original)

    def test_reparse_lock_paths_fail_closed(self) -> None:
        target = self.root / "junction-target"
        target.mkdir()
        (target / "project.godot").write_text("config_version=5\n", encoding="utf-8")
        link = self.root / "junction-game"
        completed = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        with self.assertRaises(C.GamekitError) as cm:
            C.canonical_project_root(link)
        self.assertEqual(cm.exception.code, "FORBIDDEN_PATH")
        with self.assertRaises(C.GamekitError) as cm:
            with C.project_lock(C.Project("linked", link), "nope", wait_seconds=0):
                self.fail("junction project root was locked")
        self.assertEqual(cm.exception.code, "FORBIDDEN_PATH")

        real_locks = self.root / "locks-real"
        real_locks.mkdir()
        lock_link = self.root / "locks-link"
        completed = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(lock_link), str(real_locks)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        os.environ["HH_GAMEKIT_SHARED_LOCK_DIR"] = str(lock_link)
        with self.assertRaises(C.GamekitError) as cm:
            with C.project_lock(self.project, "dir-link", wait_seconds=0):
                self.fail("junction lock directory was used")
        self.assertEqual(cm.exception.code, "FORBIDDEN_PATH")
        self.assertEqual(list(real_locks.iterdir()), [])

        os.environ["HH_GAMEKIT_SHARED_LOCK_DIR"] = str(self.root / "shared-locks")

    def test_lock_file_symlink_is_not_followed(self) -> None:
        outside = self.root / "outside-target.txt"
        outside.write_text("keep", encoding="utf-8")
        marker = C.shared_project_lock_path(self.project.root)
        marker.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.symlink(outside, marker)
        except OSError as exc:
            self.skipTest(f"file symlink unavailable: {exc}")
        with self.assertRaises(C.GamekitError) as cm:
            with C.project_lock(self.project, "file-link", wait_seconds=0):
                self.fail("symlink lock file was followed")
        self.assertIn(cm.exception.code, {"FORBIDDEN_PATH", "LOCK_UNSAFE"})
        self.assertEqual(outside.read_text(encoding="utf-8"), "keep")

    def test_journal_stays_in_state_dir(self) -> None:
        with C.project_lock(self.project, "journal", wait_seconds=0):
            C.Journal(self.project).append("cmd.lock.1", "digest", {"ok": True})
        journal = self.project.state / "journal.jsonl"
        self.assertTrue(journal.is_file())
        self.assertTrue(C.is_within(journal, self.project.state))
        self.assertFalse(C.is_within(journal, C.shared_lock_dir()))

    def test_held_measure_window_blocks_engines_and_releases(self) -> None:
        proc, held, release, log_path = self._spawn(
            "measure",
            project=self.game,
            project_id="measure-child",
            state=self.root / "state-measure",
        )
        self._wait_held(proc, held, log_path)
        with patch("subprocess.Popen", side_effect=AssertionError("spawned")):
            with self.assertRaises(C.GamekitError) as cm:
                C.run_godot(self.game, timeout=1)
            self.assertEqual(cm.exception.code, "MEASURE_WINDOW")
            with self.assertRaises(C.GamekitError) as cm:
                C.run_blender(self.root / "missing.py", timeout=1)
            self.assertEqual(cm.exception.code, "MEASURE_WINDOW")
        with self.assertRaises(C.GamekitError) as cm:
            with C.measure_window("perf", wait_seconds=0):
                self.fail("second measurement owner")
        self.assertEqual(cm.exception.code, "MEASURE_WINDOW")
        release.write_text("1", encoding="utf-8")
        self.assertEqual(proc.wait(timeout=15), 0)
        self.assertFalse(C.measure_window_lock_path().exists())
        with C.measure_window("perf", wait_seconds=0):
            C.assert_measure_window_clear()
            with patch.object(C, "godot_exe", return_value=self.root / "missing-godot.exe"):
                with patch("subprocess.Popen", side_effect=AssertionError("spawned")):
                    with self.assertRaises(C.GamekitError) as cm:
                        C.run_godot(self.game, timeout=1)
                    self.assertEqual(cm.exception.code, "TOOL_MISSING")
            with self.assertRaises(C.GamekitError) as nested:
                with C.measure_window("perf", wait_seconds=5):
                    self.fail("nested measurement")
            self.assertEqual(nested.exception.code, "MEASURE_WINDOW")
        self.assertFalse(C.measure_window_lock_path().exists())
        self.assertTrue(C.measure_window_lock_path().with_suffix(".guard").is_file())

    def test_measure_exception_stale_malformed_and_live_owner(self) -> None:
        path = C.measure_window_lock_path()
        with self.assertRaises(RuntimeError):
            with C.measure_window("perf", wait_seconds=0):
                self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["pid"], os.getpid())
                raise RuntimeError("boom")
        self.assertFalse(path.exists())
        with C.measure_window("after", wait_seconds=0):
            pass

        dead = _dead_pid()
        legacy = {
            "schema": "HH-MEASURE-WINDOW-1",
            "owner": "hh3d-coordinator",
            "pid": dead,
            "run_id": "old",
            "purpose": "soak",
        }
        path.write_text(json.dumps(legacy) + "\n", encoding="utf-8")
        C.assert_measure_window_clear()
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["owner"], "hh3d-coordinator")
        with C.measure_window("perf", wait_seconds=0):
            current = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(current["pid"], os.getpid())
            self.assertEqual(current["owner"], "hh-gamekit")
            self.assertEqual(current["schema"], "HH-MEASURE-WINDOW-1")
        self.assertFalse(path.exists())

        malformed = b'{"schema":"HH-MEASURE-WINDOW-1"}\n'
        path.write_bytes(malformed)
        with self.assertRaises(C.GamekitError) as cm:
            C.assert_measure_window_clear()
        self.assertEqual(cm.exception.code, "MEASURE_WINDOW")
        with self.assertRaises(C.GamekitError) as cm:
            with C.measure_window("perf", wait_seconds=0):
                self.fail("malformed measurement marker was stolen")
        self.assertEqual(cm.exception.code, "MEASURE_WINDOW")
        self.assertEqual(path.read_bytes(), malformed)

        live = (
            json.dumps({
                "schema": "HH-MEASURE-WINDOW-1",
                "pid": os.getpid(),
                "expires_utc": "2000-01-01T00:00:00+00:00",
                "purpose": "legacy",
                "nonce": "someone-else",
            })
            + "\n"
        ).encode("utf-8")
        path.write_bytes(live)
        with self.assertRaises(C.GamekitError) as cm:
            C.assert_measure_window_clear()
        self.assertEqual(cm.exception.code, "MEASURE_WINDOW")
        with self.assertRaises(C.GamekitError) as cm:
            with C.measure_window("perf", wait_seconds=0):
                self.fail("live expired owner was stolen")
        self.assertEqual(cm.exception.code, "MEASURE_WINDOW")
        self.assertEqual(path.read_bytes(), live)

    def test_measure_guard_matches_legacy_helper(self) -> None:
        from studio.tests.replay.benchmark_job import BenchmarkJobError
        from studio.tests.replay.measure_window import measurement_window

        path = C.measure_window_lock_path()
        with measurement_window("legacy-run", "soak", path=path):
            with patch("subprocess.Popen", side_effect=AssertionError("spawned")):
                with self.assertRaises(C.GamekitError) as cm:
                    C.run_godot(self.game, timeout=1)
                self.assertEqual(cm.exception.code, "MEASURE_WINDOW")
            with self.assertRaises(C.GamekitError) as cm:
                with C.measure_window("perf", wait_seconds=0):
                    self.fail("acquired over a legacy window")
            self.assertEqual(cm.exception.code, "MEASURE_WINDOW")
        with C.measure_window("perf", wait_seconds=0):
            with self.assertRaisesRegex(BenchmarkJobError, "BUSY"):
                with measurement_window("other-run", "soak", path=path):
                    self.fail("legacy helper entered a held gamekit window")
        payload = {
            "schema": "HH-MEASURE-WINDOW-1",
            "owner": "hh-gamekit",
            "pid": os.getpid(),
            "run_id": "format-check",
            "purpose": "perf",
            "claimed_utc": "2026-10-13T00:00:00+00:00",
            "expires_utc": "2026-10-14T00:00:00+00:00",
            "nonce": "abc",
        }
        path.write_bytes((json.dumps(payload, sort_keys=True) + "\n").encode("utf-8"))
        before = path.read_bytes()
        with self.assertRaisesRegex(BenchmarkJobError, "BUSY"):
            with measurement_window("other-run", "soak", path=path):
                self.fail("legacy helper stole a live hh-gamekit marker")
        self.assertEqual(path.read_bytes(), before)

    def test_clear_measure_check_does_not_query_scheduled_tasks(self) -> None:
        with patch("subprocess.run", side_effect=AssertionError("task query")):
            C.assert_measure_window_clear()

    def test_perf_acquires_measure_window_and_releases_on_exception(self) -> None:
        (self.game / "project.godot").write_text(
            'config_version=5\n[application]\nconfig/name="T"\nrun/main_scene="res://main.tscn"\n',
            encoding="utf-8",
        )
        (self.game / "main.tscn").write_text("[gd_scene format=3]\n", encoding="utf-8")
        path = C.measure_window_lock_path()

        def fake_tool(*_args: object, **_kwargs: object) -> C.ProcessRun:
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["schema"], "HH-MEASURE-WINDOW-1")
            self.assertEqual(data["owner"], "hh-gamekit")
            self.assertEqual(data["pid"], os.getpid())
            self.assertEqual(data["purpose"], "perf")
            raise RuntimeError("stop before godot")

        with patch.object(C, "run_godot_tool", side_effect=fake_tool):
            with self.assertRaises(RuntimeError):
                perf_mod.run_report(self.project, frames=1, warmup=0, leak_cycles=3, headless=True, timeout=1)
        self.assertFalse(path.exists())
        with C.project_lock(self.project, "after-perf", wait_seconds=0):
            pass

        proc, held, release, log_path = self._spawn(
            "measure",
            project=self.game,
            project_id="perf-other",
            state=self.root / "state-perf-other",
        )
        self._wait_held(proc, held, log_path)
        requested: list[float] = []
        real_measure = C.measure_window

        def bounded(purpose: str, *, run_id: str | None = None, wait_seconds: float = 0.0) -> object:
            requested.append(wait_seconds)
            return real_measure(purpose, run_id=run_id, wait_seconds=0)

        with patch.object(C, "measure_window", side_effect=bounded):
            with patch.object(C, "run_godot_tool", side_effect=AssertionError("godot started")):
                with self.assertRaises(C.GamekitError) as cm:
                    perf_mod.run_report(self.project, frames=1, warmup=0, leak_cycles=3, headless=True, timeout=1)
        self.assertEqual(requested, [30.0])
        self.assertEqual(cm.exception.code, "MEASURE_WINDOW")
        release.write_text("1", encoding="utf-8")
        self.assertEqual(proc.wait(timeout=15), 0)

    def test_play_refuses_open_editor_and_isolates_user_dir(self) -> None:
        before = set(Path(tempfile.gettempdir()).glob("hh-play-user-*"))
        with patch.object(C, "godot_processes_for", return_value=[{"pid": 9, "command_line": "godot --editor"}]):
            with patch.object(C, "run_godot_tool", side_effect=AssertionError("launched")):
                with self.assertRaises(C.GamekitError) as cm:
                    play_mod.play(self.project, frames=1)
        self.assertEqual(cm.exception.code, "EDITOR_OPEN")
        self.assertNotIn("allow-open-editor", cm.exception.detail)
        self.assertEqual(before, set(Path(tempfile.gettempdir()).glob("hh-play-user-*")))

        seen: dict[str, object] = {}

        def fake_tool(root: Path, tool: str, request: dict[str, object], **kwargs: object) -> C.ProcessRun:
            seen["tool"] = tool
            seen["env"] = kwargs.get("env")
            seen["request"] = request
            profile = Path(str(request["user_profile"]))
            return C.ProcessRun(
                argv=["godot"],
                exit_code=0,
                seconds=0.01,
                stdout="",
                stderr="",
                result={
                    "ok": True,
                    "frames": 1,
                    "observations": [],
                    "errors": [],
                    "user_data_dir": str(profile / "ud"),
                },
            )

        with patch.object(C, "godot_processes_for", return_value=[]) as checked:
            with patch.object(C, "run_godot_tool", side_effect=fake_tool):
                result = play_mod.play(self.project, frames=1, seed=3)
        self.assertTrue(checked.called)
        self.assertEqual(seen["tool"], "play_runner.gd")
        env = seen["env"]
        self.assertIsInstance(env, dict)
        request = seen["request"]
        self.assertIsInstance(request, dict)
        profile = Path(str(request["user_profile"]))  # type: ignore[index]
        assert isinstance(env, dict)
        self.assertTrue(C.is_within(Path(str(env["APPDATA"])), profile))
        self.assertNotEqual(env["LOCALAPPDATA"], os.environ.get("LOCALAPPDATA"))
        self.assertTrue(result["user_data_isolated"])
        self.assertTrue(result["user_data_cleaned"])
        self.assertEqual(result["seed"], 3)
        self.assertFalse(profile.exists())
        self.assertEqual(before, set(Path(tempfile.gettempdir()).glob("hh-play-user-*")))


if __name__ == "__main__":
    if os.environ.get("HH_LOCK_CHILD") == "1":
        _child_main()
    else:
        unittest.main()
