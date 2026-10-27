#!/usr/bin/env python3
"""Small, clean-room Playwright measurement runner.

The runner deliberately exposes only ordinary mouse/keyboard input and the
Chrome DevTools screencast stream.  It does not inspect the page or install
browser hooks.  Run it through ``tools/run_guarded.py`` so that the shared
measurement lock and process containment remain in force.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import sys
import time
from typing import Any
from urllib.parse import urlsplit

from playwright.async_api import BrowserContext, Page, async_playwright


VIEWPORT_WIDTH = 1280
VIEWPORT_HEIGHT = 720
SCHEMA_VERSION = 1
_SAFE_SCHEME = re.compile(r"^(?:https?|file)$", re.IGNORECASE)


def _finite_number(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, ValueError):
        return False


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def monotonic_ns() -> int:
    return time.perf_counter_ns()


def _json_dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    # Never follow a pre-existing temporary symlink while preparing the
    # atomic replacement.  The project lease prevents a concurrent writer;
    # a stale ordinary temp file is safe to replace, but a symlink is not.
    if temporary.is_symlink():
        raise ValueError(f"refusing symlink temporary output: {temporary}")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _require_guard(project_root: Path) -> None:
    """Refuse direct execution; run_guarded owns this lease file."""
    lease = project_root / ".local" / "run_guarded.lock"
    if not lease.is_file():
        raise RuntimeError("y8rig must be invoked through tools/run_guarded.py")
    try:
        marker = json.loads(lease.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("invalid run_guarded lease") from exc
    # ``run_guarded`` writes its own PID, while this runner is its direct
    # child.  Keep this check strict: JSON ``true`` compares equal to 1 in
    # Python, and accepting it would make a malformed lease look owned.
    parent_pid = os.getppid()
    if (
        not isinstance(marker, dict)
        or isinstance(marker.get("pid"), bool)
        or not isinstance(marker.get("pid"), int)
        or marker.get("pid") != parent_pid
    ):
        raise RuntimeError("run_guarded lease is not owned by the parent process")


def _read_scenario(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read scenario {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("scenario must be a JSON object")
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"scenario schema_version must be {SCHEMA_VERSION}")
    url = data.get("url")
    if not isinstance(url, str) or not url.strip():
        raise ValueError("scenario.url must be a non-empty URL")
    parts = urlsplit(url)
    if not parts.scheme or not _SAFE_SCHEME.fullmatch(parts.scheme):
        raise ValueError("scenario.url must use http, https, or file scheme")
    actions = data.get("actions", [])
    if not isinstance(actions, list):
        raise ValueError("scenario.actions must be an array")
    for index, action in enumerate(actions):
        if not isinstance(action, dict) or not isinstance(action.get("type"), str):
            raise ValueError(f"action {index} must be an object with a type")
        kind = action["type"]
        if kind == "wait":
            _duration(action, index)
        elif kind in {"key_down", "key_up", "hold"}:
            if not isinstance(action.get("key"), str) or not action["key"]:
                raise ValueError(f"action {index} requires key")
            if kind == "hold":
                _duration(action, index)
        elif kind == "click":
            x = action.get("x", VIEWPORT_WIDTH // 2)
            y = action.get("y", VIEWPORT_HEIGHT // 2)
            if (
                not _finite_number(x)
                or not 0 <= float(x) <= VIEWPORT_WIDTH
            ):
                raise ValueError(f"action {index}.x must be numeric")
            if (
                not _finite_number(y)
                or not 0 <= float(y) <= VIEWPORT_HEIGHT
            ):
                raise ValueError(f"action {index}.y must be numeric")
        else:
            raise ValueError(f"action {index} has unsupported type {kind!r}")
    focus = data.get("focus_click", True)
    if not isinstance(focus, bool):
        raise ValueError("focus_click must be boolean")
    return data


def _duration(action: dict[str, Any], index: int) -> float:
    value = action.get("duration_ms", 0)
    if (
        not _finite_number(value)
        or value < 0
        or value > 3_600_000
    ):
        raise ValueError(f"action {index}.duration_ms must be in [0, 3600000]")
    return float(value) / 1000.0


@dataclass
class FrameRecorder:
    """Writes CDP screencast frames and gathers observed cadence statistics."""

    cdp: Any
    output_dir: Path
    tasks: set[asyncio.Task[None]] = field(default_factory=set)
    frames: int = 0
    first_timestamp: float | None = None
    last_timestamp: float | None = None
    metadata: list[dict[str, Any]] = field(default_factory=list)
    _sequence: int = 0
    _stopping: bool = False

    def install(self) -> None:
        self.cdp.on("Page.screencastFrame", self._schedule)

    def _schedule(self, payload: dict[str, Any]) -> None:
        if self._stopping:
            return
        self._sequence += 1
        task = asyncio.create_task(self._handle(payload, self._sequence))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def _handle(self, payload: dict[str, Any], sequence: int) -> None:
        session_id = payload.get("sessionId")
        # Page.screencastFrame.sessionId is an integer in the CDP schema.
        # Sending no ACK leaves Chromium's screencast stalled after the first
        # frame, which is easy to miss when running against a real browser.
        if isinstance(session_id, int) and not isinstance(session_id, bool):
            await self.cdp.send("Page.screencastFrameAck", {"sessionId": session_id})
        data = payload.get("data")
        if not isinstance(data, str):
            return
        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        self.frames += 1
        stamp = metadata.get("timestamp")
        if isinstance(stamp, (int, float)) and not isinstance(stamp, bool):
            if self.first_timestamp is None:
                self.first_timestamp = float(stamp)
            self.last_timestamp = float(stamp)
        frame_name = f"frame-{sequence:06d}.png"
        (self.output_dir / "frames" / frame_name).write_bytes(base64.b64decode(data))
        self.metadata.append(
            {
                "frame": sequence,
                "file": f"frames/{frame_name}",
                "cdp_timestamp": stamp,
                "received_monotonic_ns": monotonic_ns(),
                "received_utc": utc_now(),
                "metadata": metadata,
            }
        )

    async def start(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "frames").mkdir(parents=True, exist_ok=True)
        self.install()
        await self.cdp.send(
            "Page.startScreencast",
            {
                "format": "png",
                "quality": 100,
                "maxWidth": VIEWPORT_WIDTH,
                "maxHeight": VIEWPORT_HEIGHT,
                "everyNthFrame": 1,
            },
        )

    async def stop(self) -> dict[str, Any]:
        self._stopping = True
        off = getattr(self.cdp, "off", None)
        if callable(off):
            off("Page.screencastFrame", self._schedule)
        await self.cdp.send("Page.stopScreencast")
        # A stop command can race with an already-dispatched event.  Drain
        # until callbacks have removed every task rather than taking one
        # snapshot of the set and losing the tail frame.
        while self.tasks:
            await asyncio.gather(*tuple(self.tasks), return_exceptions=False)
        ordered = sorted(self.metadata, key=lambda row: int(row["frame"]))
        timestamps = [
            float(row["cdp_timestamp"])
            for row in ordered
            if isinstance(row.get("cdp_timestamp"), (int, float))
            and not isinstance(row.get("cdp_timestamp"), bool)
        ]
        # CDP can deliver a late frame after a newer timestamp.  Preserve the
        # raw frame rows, but never turn a negative interval into a cadence
        # claim.  Keep the longest monotonic subsequence in delivery order;
        # this makes the reported FPS conservative and auditable.
        monotonic_timestamps: list[float] = []
        for timestamp in timestamps:
            if not monotonic_timestamps or timestamp >= monotonic_timestamps[-1]:
                monotonic_timestamps.append(timestamp)
        elapsed = (
            monotonic_timestamps[-1] - monotonic_timestamps[0]
            if len(monotonic_timestamps) >= 2
            else None
        )
        intervals = [
            current - previous
            for previous, current in zip(monotonic_timestamps, monotonic_timestamps[1:])
        ]
        stats: dict[str, Any] = {
            "frames": self.frames,
            "timestamped_frames": len(timestamps),
            "monotonic_timestamped_frames": len(monotonic_timestamps),
            "discarded_nonmonotonic_timestamps": len(timestamps) - len(monotonic_timestamps),
            "cdp_elapsed_seconds": elapsed,
            "observed_fps": (len(monotonic_timestamps) - 1) / elapsed if elapsed and len(monotonic_timestamps) > 1 else None,
            "min_interval_seconds": min(intervals) if intervals else None,
            "max_interval_seconds": max(intervals) if intervals else None,
            "mean_interval_seconds": sum(intervals) / len(intervals) if intervals else None,
        }
        _json_dump(self.output_dir / "frames.json", {"schema_version": 1, "frames": ordered, "stats": stats})
        return stats


async def _wait(page: Page, duration_seconds: float) -> None:
    if duration_seconds:
        await asyncio.sleep(duration_seconds)


async def _run_actions(
    page: Page,
    actions: list[dict[str, Any]],
    output_dir: Path,
    records: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    # Accept the focus-click record from ``run`` so a later action failure
    # cannot overwrite the log with a partial list.
    if records is None:
        records = []
    held: set[str] = set()

    async def record(index: int, action: dict[str, Any], operation) -> None:
        started_ns = monotonic_ns()
        started_utc = utc_now()
        error: str | None = None
        try:
            await operation()
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            records.append(
                {
                    "index": index,
                    "action": action,
                    "started_utc": started_utc,
                    "finished_utc": utc_now(),
                    "started_monotonic_ns": started_ns,
                    "finished_monotonic_ns": monotonic_ns(),
                    "error": error,
                }
            )

    try:
        for index, action in enumerate(actions):
            kind = action["type"]
            if kind == "wait":
                await record(index, action, lambda action=action: _wait(page, _duration(action, index)))
            elif kind == "click":
                x = float(action.get("x", VIEWPORT_WIDTH // 2))
                y = float(action.get("y", VIEWPORT_HEIGHT // 2))
                await record(index, action, lambda x=x, y=y: page.mouse.click(x, y))
            elif kind == "key_down":
                key = action["key"]

                async def down(key=key) -> None:
                    await page.keyboard.down(key)
                    held.add(key)

                await record(index, action, down)
            elif kind == "key_up":
                key = action["key"]

                async def up(key=key) -> None:
                    await page.keyboard.up(key)
                    held.discard(key)

                await record(index, action, up)
            elif kind == "hold":
                key = action["key"]

                async def hold(key=key, action=action, index=index) -> None:
                    await page.keyboard.down(key)
                    held.add(key)
                    try:
                        await _wait(page, _duration(action, index))
                    finally:
                        await page.keyboard.up(key)
                        held.discard(key)

                await record(index, action, hold)
    finally:
        # Release every key we own even when a later action fails.
        release_errors: list[tuple[str, str]] = []
        for key in tuple(held):
            try:
                await page.keyboard.up(key)
            except Exception as exc:
                release_errors.append((key, f"{key}: {type(exc).__name__}: {exc}"))
            finally:
                held.discard(key)
        active_exception = sys.exc_info()[1]
        if release_errors:
            records.append(
                {
                    "index": -2,
                    "action": {"type": "release_all", "keys": sorted(key for key, _ in release_errors)},
                    "started_utc": utc_now(),
                    "finished_utc": utc_now(),
                    "started_monotonic_ns": monotonic_ns(),
                    "finished_monotonic_ns": monotonic_ns(),
                    "error": "; ".join(message for _, message in release_errors),
                }
            )
        _json_dump(output_dir / "actions.json", {"schema_version": 1, "actions": records})
        if release_errors and active_exception is None:
            raise RuntimeError("failed to release one or more held keys")
    return records


async def run(scenario_path: Path, project_root: Path, output_dir: Path) -> dict[str, Any]:
    scenario = _read_scenario(scenario_path)
    run_started_ns = monotonic_ns()
    result: dict[str, Any] = {
        "schema_version": 1,
        "scenario": str(scenario_path),
        "url": scenario["url"],
        "viewport": {"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT, "device_scale_factor": 1},
        "started_utc": utc_now(),
        "started_monotonic_ns": run_started_ns,
    }
    local_entry = project_root / ".local"
    if local_entry.is_symlink():
        raise ValueError("product .local directory must not be a symlink")
    local_root = local_entry.resolve()
    if not local_root.is_dir():
        raise ValueError("product .local directory is missing")
    if output_dir == local_root or local_root not in output_dir.parents:
        raise ValueError("--output must be under the product .local directory")
    if project_root not in scenario_path.parents:
        raise ValueError("--scenario must be under the product root")
    profile = local_root / "y8rig-profile"
    # Check the unresolved entry as well as its target.  ``Path.exists`` is
    # false for a dangling symlink; without this guard mkdir would follow it
    # and place the browser profile outside the product tree.
    if profile.is_symlink():
        raise ValueError("y8rig profile must not be a symlink")
    profile_target = profile.resolve()
    if local_root not in profile_target.parents:
        raise ValueError("y8rig profile must remain under the product .local directory")
    if output_dir == profile_target or profile_target in output_dir.parents:
        raise ValueError("--output must not be inside the y8rig browser profile")
    profile.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        async with async_playwright() as playwright:
            context: BrowserContext | None = None
            try:
                context = await playwright.chromium.launch_persistent_context(
                    user_data_dir=str(profile),
                    headless=False,
                    viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
                    device_scale_factor=1,
                    args=[
                        "--disable-backgrounding-occluded-windows",
                        "--disable-renderer-backgrounding",
                        "--force-device-scale-factor=1",
                    ],
                )
                # Persistent Chromium usually starts with one about:blank
                # page.  Closing that sole target and immediately creating a
                # replacement can race Target.createTarget on Windows.  Reuse
                # it and only trim genuinely extra pages.
                pages = tuple(context.pages)
                if pages:
                    page = pages[0]
                    for extra in pages[1:]:
                        await extra.close()
                else:
                    page = await context.new_page()
                await page.goto(scenario["url"], wait_until="load")
                cdp = await context.new_cdp_session(page)
                recorder = FrameRecorder(cdp, output_dir)
                await recorder.start()
                records: list[dict[str, Any]] = []
                try:
                    if scenario.get("focus_click", True):
                        started_ns = monotonic_ns()
                        started_utc = utc_now()
                        focus_error: str | None = None
                        try:
                            await page.mouse.click(VIEWPORT_WIDTH / 2, VIEWPORT_HEIGHT / 2)
                        except Exception as exc:
                            focus_error = f"{type(exc).__name__}: {exc}"
                            raise
                        finally:
                            records.append(
                                {
                                    "index": -1,
                                    "action": {"type": "focus_click", "x": VIEWPORT_WIDTH / 2, "y": VIEWPORT_HEIGHT / 2},
                                    "started_utc": started_utc,
                                    "finished_utc": utc_now(),
                                    "started_monotonic_ns": started_ns,
                                    "finished_monotonic_ns": monotonic_ns(),
                                    "error": focus_error,
                                }
                            )
                    await _run_actions(page, scenario.get("actions", []), output_dir, records)
                    result.update(actions=len(records), status="OK")
                finally:
                    # ``_run_actions`` also writes this file, but this outer
                    # write preserves the focus record when that helper is
                    # never entered because focus itself failed.
                    _json_dump(output_dir / "actions.json", {"schema_version": 1, "actions": records})
                    frame_stats = await recorder.stop()
                    result["frame_stats"] = frame_stats
            finally:
                if context is not None:
                    await context.close()
    except Exception as exc:
        result.update(status="FAILED", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        result.update(finished_utc=utc_now(), duration_seconds=(monotonic_ns() - run_started_ns) / 1_000_000_000)
        _json_dump(output_dir / "run.json", result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    project_root = args.project_root.resolve()
    _require_guard(project_root)
    try:
        result = asyncio.run(run(args.scenario.resolve(), project_root, args.output.resolve()))
    except Exception as exc:
        print(json.dumps({"schema_version": 1, "status": "FAILED", "error": f"{type(exc).__name__}: {exc}"}))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
