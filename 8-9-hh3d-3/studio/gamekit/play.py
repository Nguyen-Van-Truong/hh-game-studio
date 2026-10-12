"""hh play: run a scene for N physics frames at 60 Hz and record a deterministic observation trace.

The runner applies an input trace with InputEventAction on the named physics frame. ``trace_hash``
is the sha256 of the canonical JSON of the observation list, so a second run of the same trace
matches when physics stays deterministic.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from . import common as C

MAX_FRAMES = 36_000
MAX_EVENTS = 100_000
_NODE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_PROP_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SEED_MIN = -9_223_372_036_854_775_808
_SEED_MAX = 9_223_372_036_854_775_807


def _fail(detail: str) -> None:
    raise C.GamekitError("VALIDATION_FAILED", detail)


def _seed(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < _SEED_MIN or value > _SEED_MAX:
        _fail("seed must be a signed 64-bit integer")
    return value


def _frames(value: Any, name: str = "frames") -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > MAX_FRAMES:
        _fail(f"{name} must be an integer 1..{MAX_FRAMES}")
    return value


def parse_observe(text: str) -> list[dict[str, str]]:
    """Parse ``Player:position,Player:velocity`` into runner probe records."""
    if text is None or not str(text).strip():
        return []
    out = []
    for part in str(text).split(","):
        item = part.strip()
        if not item:
            continue
        if ":" not in item:
            _fail(f"observe entry {item!r} must be Node:property")
        node, prop = item.rsplit(":", 1)
        if not node or not prop or not _PROP_RE.match(prop):
            _fail(f"observe entry {item!r} has an empty node or bad property")
        for segment in node.split("/"):
            if not _NODE_RE.match(segment):
                _fail(f"observe node path {node!r} is not safe")
        out.append({"node": node, "prop": prop, "label": f"{node}:{prop}"})
    if len(out) > 32:
        _fail("at most 32 observe entries")
    return out


def validate_trace(trace: Any) -> dict[str, Any]:
    """Accept ``{fps: 60, events: [{frame, action, pressed, strength?}]}``."""
    if trace is None:
        return {"fps": 60, "events": []}
    if not isinstance(trace, dict):
        _fail("trace must be an object")
    extra = set(trace) - {"fps", "events"}
    if extra:
        _fail(f"trace has unknown fields {sorted(extra)}")
    fps = trace.get("fps", 60)
    if isinstance(fps, bool) or not isinstance(fps, int) or fps != 60:
        _fail("trace fps must be 60")
    raw = trace.get("events", [])
    if not isinstance(raw, list):
        _fail("trace events must be a list")
    if len(raw) > MAX_EVENTS:
        _fail(f"at most {MAX_EVENTS} trace events")
    events = []
    for index, item in enumerate(raw):
        where = f"events[{index}]"
        if not isinstance(item, dict):
            _fail(f"{where} must be an object")
        unknown = set(item) - {"frame", "action", "pressed", "strength"}
        if unknown:
            _fail(f"{where} has unknown fields {sorted(unknown)}")
        if isinstance(item.get("frame"), bool) or not isinstance(item.get("frame"), int) or item["frame"] < 0:
            _fail(f"{where} frame must be an integer >= 0")
        if item["frame"] > MAX_FRAMES:
            _fail(f"{where} frame is past {MAX_FRAMES}")
        action = item.get("action")
        if not isinstance(action, str) or not action.strip() or len(action) > 64:
            _fail(f"{where} action must be a non-empty name")
        if not isinstance(item.get("pressed"), bool):
            _fail(f"{where} pressed must be a bool")
        strength = 1.0 if "strength" not in item else item["strength"]
        if isinstance(strength, bool) or not isinstance(strength, (int, float)):
            _fail(f"{where} strength must be a number from 0 to 1")
        strength_f = float(strength)
        if strength_f < 0.0 or strength_f > 1.0:
            _fail(f"{where} strength must be a number from 0 to 1")
        events.append({
            "frame": int(item["frame"]),
            "action": action.strip(),
            "pressed": bool(item["pressed"]),
            "strength": strength_f,
        })
    events.sort(key=lambda ev: ev["frame"])
    return {"fps": 60, "events": events}


def trace_hash(observations: Any) -> str:
    return C.sha256_bytes(C.canonical_json(observations).encode("utf-8"))


def _fmt_error(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()[:400]
    if isinstance(item, dict):
        code = str(item.get("code") or item.get("message") or item.get("detail") or "").strip()
        file = str(item.get("file") or "")
        line = item.get("line")
        text = f"{file}:{line}: {code}" if file else code
        return text.strip()[:400]
    return str(item)[:400]


def merge_errors(*groups: list[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            text = _fmt_error(item)
            if not text or text in seen:
                continue
            seen.add(text)
            out.append(text)
    return out


def _checked_out(project: C.Project, out: str | None) -> str | None:
    """Refuse a junction, ``studio/.local``, ``private.raw``, or an in-project ``--out``."""
    if not out:
        return None
    safe = C.refuse_unsafe_host_path(Path(out), what="--out", project=project, must_be_outside_project=True)
    return str(safe)


def _finish(result: dict[str, Any], out: str | None, project: C.Project) -> dict[str, Any]:
    safe = _checked_out(project, out)
    if safe:
        C.atomic_write_json(Path(safe), result)
    return result


def _crashed(run: C.ProcessRun, errors: list[str]) -> dict[str, Any]:
    return {
        "ok": False,
        "crashed": True,
        "frames": 0,
        "observations": [],
        "errors": errors,
        "trace_hash": trace_hash([]),
        "process": run.summary(),
    }


def play(
    project: C.Project,
    *,
    scene: str | None = None,
    trace: Any = None,
    frames: int = 60,
    seed: int = 0,
    observe: str = "",
    every: int = 1,
    windowed: bool = False,
    out: str | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    frames_n = _frames(frames)
    every_n = _frames(every, "every")
    seed_n = _seed(seed)
    probes = parse_observe(observe)
    body = validate_trace(trace)
    if scene:
        project.res_to_path(scene, must_exist=True)
    out = _checked_out(project, out)
    if timeout is None:
        timeout = max(45.0, 20.0 + frames_n * 0.05)
    request = {
        "scene": scene or "",
        "frames": frames_n,
        "seed": seed_n,
        "every": every_n,
        "observe": probes,
        "events": body["events"],
    }
    with C.project_lock(project, "play", wait_seconds=30):
        run = C.run_godot_tool(
            project.root,
            "play_runner.gd",
            request,
            headless=not windowed,
            windowed=windowed,
            fixed_fps=60,
            timeout=timeout,
        )
    if run.timed_out:
        return _finish(_crashed(run, ["TIMEOUT"]), out, project)
    if not isinstance(run.result, dict):
        errors = merge_errors(run.errors, ["play produced no result"])
        return _finish(_crashed(run, errors), out, project)
    result = run.result
    if result.get("error") and "frames" not in result:
        raise C.GamekitError(str(result.get("error") or "GODOT_FAILED"), str(result.get("detail") or "play failed"),
                             process=run.summary())
    observations = result.get("observations") if isinstance(result.get("observations"), list) else []
    errors = merge_errors(result.get("errors") if isinstance(result.get("errors"), list) else [], run.errors)
    crashed = run.exit_code not in (0, None) and "frames" not in result
    ok = (not crashed) and not errors and bool(result.get("ok")) and run.exit_code == 0
    played = {
        "ok": ok,
        "crashed": crashed,
        "frames": int(result.get("frames") or 0),
        "observations": observations,
        "errors": errors,
        "trace_hash": trace_hash(observations),
        "process": run.summary(),
        "scene": scene or "",
        "seed": seed_n,
    }
    return _finish(played, out, project)


def _load_trace(path: str) -> Any:
    """Read ``--trace`` after refusing junctions, ``studio/.local``, and ``private.raw``."""
    safe = C.refuse_unsafe_host_path(Path(path), what="--trace")
    return C.read_json(safe)


def _cmd_play(args: argparse.Namespace) -> dict[str, Any]:
    trace = _load_trace(args.trace) if args.trace else None
    return play(
        C.get_project(args.project),
        scene=args.scene,
        trace=trace,
        frames=args.frames,
        seed=args.seed,
        observe=args.observe or "",
        every=args.every,
        windowed=args.windowed,
        out=args.out,
    )


def register(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("play", help="play a scene with a 60 Hz input trace and record observations")
    parser.add_argument("project")
    parser.add_argument("--scene", default=None, help="res:// scene (default: the project's main scene)")
    parser.add_argument("--trace", default=None, help="JSON {fps: 60, events: [{frame, action, pressed, strength}]}")
    parser.add_argument("--frames", type=int, default=60)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--observe", default="", help="comma-separated Node:property probes, e.g. Player:position")
    parser.add_argument("--every", type=int, default=1, help="record a probe every K physics frames, plus the last frame")
    parser.add_argument("--windowed", action="store_true")
    parser.add_argument("--out", default=None, help="also write the result JSON to this path")
    parser.set_defaults(func=_cmd_play)
