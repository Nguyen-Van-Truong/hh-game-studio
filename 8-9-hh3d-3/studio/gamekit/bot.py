"""hh bot: build a seeded hold/release trace and report stuck time, coverage, and bbox.

The trace is replayable through ``hh play``. ``ok`` means the scene did not crash and reported no
script errors. A stuck interval is a finding, not a failure: the tracked body stayed within
``stuck_dist`` of the interval start for at least ``stuck_frames`` physics frames while an action
was held. Coverage and stuck distance use XY for Vector2 and the XZ ground plane for Vector3;
``--plane`` can select a different projection for a side-view 3D game.
"""

from __future__ import annotations

import argparse
import math
import random
import re
from typing import Any

from . import common as C
from . import play as P

_NAME_RE_OK = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
_PLANES = {"xy": (0, 1), "xz": (0, 2), "yz": (1, 2)}


def _fail(detail: str) -> None:
    raise C.GamekitError("VALIDATION_FAILED", detail)


def _actions(text: str) -> list[str]:
    names = [part.strip() for part in str(text).split(",") if part.strip()]
    if not names:
        _fail("actions must list at least one action name")
    if len(names) > 32:
        _fail("at most 32 actions")
    if len(set(names)) != len(names):
        _fail("duplicate action names")
    for name in names:
        if not _NAME_RE_OK.match(name):
            _fail(f"bad action name {name!r}")
    return names


def _hold(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > 10_000:
        _fail(f"{name} must be an integer 1..10000")
    return value


def build_trace(actions: list[str], frames: int, seed: int, hold_min: int, hold_max: int) -> dict[str, Any]:
    """Seeded trace that holds one action at a time. A re-roll of the same action extends the hold."""
    rng = random.Random(seed)
    events: list[dict[str, Any]] = []
    frame = 0
    held: str | None = None
    while frame < frames:
        action = rng.choice(actions)
        hold = rng.randint(hold_min, hold_max)
        if held != action:
            if held is not None:
                events.append({"frame": frame, "action": held, "pressed": False, "strength": 1.0})
            events.append({"frame": frame, "action": action, "pressed": True, "strength": 1.0})
            held = action
        frame += hold
    if held is not None:
        events.append({"frame": frames, "action": held, "pressed": False, "strength": 1.0})
    return {"fps": 60, "events": events}


def held_during(trace: dict[str, Any], frames: int) -> list[dict[str, float]]:
    """Action strengths after the events of each physics frame 0..frames-1 have been applied."""
    by_frame: dict[int, list[dict[str, Any]]] = {}
    for event in trace.get("events", []):
        by_frame.setdefault(int(event["frame"]), []).append(event)
    state: dict[str, float] = {}
    out: list[dict[str, float]] = []
    for frame in range(frames):
        for event in by_frame.get(frame, []):
            if event.get("pressed"):
                state[str(event["action"])] = float(event.get("strength", 1.0))
            else:
                state.pop(str(event["action"]), None)
        out.append(dict(state))
    return out


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _plane(observations: list[dict[str, Any]], label: str, plane: str) -> str:
    if plane not in ("auto", *_PLANES):
        _fail("plane must be auto, xy, xz, or yz")
    if plane != "auto":
        return plane
    for row in observations:
        values = row.get("values") if isinstance(row, dict) else None
        value = values.get(label) if isinstance(values, dict) else None
        if isinstance(value, list) and len(value) in (2, 3) and all(
            not isinstance(v, bool) and isinstance(v, (int, float)) and math.isfinite(float(v)) for v in value
        ):
            return "xz" if len(value) == 3 else "xy"
    return "xy"


def _positions(observations: list[dict[str, Any]], label: str, plane: str = "xy") -> dict[int, tuple[float, float]]:
    found: dict[int, tuple[float, float]] = {}
    axes = _PLANES[plane]
    for row in observations:
        if not isinstance(row, dict):
            continue
        values = row.get("values")
        if not isinstance(values, dict) or label not in values:
            continue
        value = values[label]
        if not isinstance(value, list) or len(value) not in (2, 3) or len(value) <= max(axes):
            continue
        x, y = value[axes[0]], value[axes[1]]
        if isinstance(x, bool) or isinstance(y, bool) or not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            continue
        if not math.isfinite(float(x)) or not math.isfinite(float(y)):
            continue
        frame = row.get("frame")
        if isinstance(frame, bool) or not isinstance(frame, int) or frame < 0:
            continue
        found[frame] = (float(x), float(y))
    return found


def find_stuck(
    positions: dict[int, tuple[float, float]],
    held: list[dict[str, float]],
    stuck_frames: int,
    stuck_dist: float,
) -> list[dict[str, Any]]:
    """Intervals whose samples stay within ``stuck_dist`` of the start while an action is held."""
    if not positions or not held:
        return []
    intervals = []
    frame = 0
    limit = len(held)
    while frame < limit:
        if frame not in positions or not held[frame]:
            frame += 1
            continue
        origin = positions[frame]
        last = frame
        step = frame
        while step < limit and held[step]:
            nxt = step + 1
            if nxt in positions and _dist(origin, positions[nxt]) >= stuck_dist:
                break
            if nxt in positions:
                last = nxt
            step += 1
        if last - frame >= stuck_frames:
            actions = sorted({name for index in range(frame, last) if index < limit for name in held[index]})
            intervals.append({
                "start": frame,
                "end": last,
                "frames": last - frame,
                "moved": round(_dist(origin, positions[last]), 4),
                "actions": actions,
            })
            frame = max(last, frame + 1)
        else:
            frame += 1
    return intervals


def analyze(
    observations: list[dict[str, Any]],
    trace: dict[str, Any],
    label: str,
    frames: int,
    stuck_frames: int,
    stuck_dist: float,
    cell: int,
    plane: str = "auto",
) -> dict[str, Any]:
    selected_plane = _plane(observations, label, plane)
    positions = _positions(observations, label, selected_plane)
    held = held_during(trace, frames)
    stuck = find_stuck(positions, held, stuck_frames, stuck_dist)
    cells: set[tuple[int, int]] = set()
    xs: list[float] = []
    ys: list[float] = []
    for x, y in positions.values():
        cells.add((math.floor(x / cell), math.floor(y / cell)))
        xs.append(x)
        ys.append(y)
    bbox = None if not xs else {"min": [min(xs), min(ys)], "max": [max(xs), max(ys)]}
    return {"stuck": stuck, "coverage": len(cells), "bbox": bbox, "samples": len(positions), "plane": selected_plane}


def run_bot(
    project: C.Project,
    *,
    scene: str | None = None,
    frames: int = 1800,
    seed: int = 1,
    actions: str | list[str] = "",
    track: str = "",
    hold_min: int = 6,
    hold_max: int = 30,
    stuck_frames: int = 120,
    stuck_dist: float = 4.0,
    cell: int = 32,
    plane: str = "auto",
    out: str | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    frames_n = P._frames(frames)
    seed_n = P._seed(seed)
    names = _actions(",".join(actions) if isinstance(actions, list) else actions)
    low = _hold(hold_min, "hold-min")
    high = _hold(hold_max, "hold-max")
    if low > high:
        _fail("hold-min cannot exceed hold-max")
    if isinstance(stuck_frames, bool) or not isinstance(stuck_frames, int) or stuck_frames < 1 or stuck_frames > P.MAX_FRAMES:
        _fail(f"stuck-frames must be an integer 1..{P.MAX_FRAMES}")
    if isinstance(stuck_dist, bool) or not isinstance(stuck_dist, (int, float)) or not math.isfinite(float(stuck_dist)):
        _fail("stuck-dist must be a finite number > 0")
    if float(stuck_dist) <= 0.0 or float(stuck_dist) > 1e7:
        _fail("stuck-dist must be a finite number > 0")
    if isinstance(cell, bool) or not isinstance(cell, int) or cell < 1 or cell > 1_000_000:
        _fail("cell must be an integer 1..1000000")
    _plane([], "", plane)
    out = P._checked_out(project, out)
    probes = P.parse_observe(f"{track}:global_position")
    label = probes[0]["label"]
    trace = build_trace(names, frames_n, seed_n, low, high)
    played = P.play(
        project,
        scene=scene,
        trace=trace,
        frames=frames_n,
        seed=seed_n,
        observe=label,
        every=1,
        timeout=timeout,
    )
    observations = played.get("observations") if isinstance(played.get("observations"), list) else []
    report = analyze(observations, trace, label, frames_n, stuck_frames, float(stuck_dist), cell, plane)
    errors = list(played.get("errors") or [])
    if report["samples"] == 0:
        errors.append(f"no positions observed for {label}")
    crashed = bool(played.get("crashed"))
    result = {
        "ok": bool(played.get("ok")) and (not crashed) and not errors,
        "crashed": crashed,
        "errors": errors,
        "stuck": report["stuck"],
        "coverage": report["coverage"],
        "bbox": report["bbox"],
        "plane": report["plane"],
        "trace": trace,
        "frames": frames_n,
        "seed": seed_n,
        "track": track,
        "scene": scene or "",
        "trace_hash": played.get("trace_hash"),
        "observation_count": len(observations),
        "params": {
            "hold_min": low,
            "hold_max": high,
            "stuck_frames": stuck_frames,
            "stuck_dist": float(stuck_dist),
            "cell": cell,
            "plane": plane,
        },
        "process": played.get("process"),
    }
    return P._finish(result, out, project)


def _cmd_bot(args: argparse.Namespace) -> dict[str, Any]:
    return run_bot(
        C.get_project(args.project),
        scene=args.scene,
        frames=args.frames,
        seed=args.seed,
        actions=args.actions,
        track=args.track,
        hold_min=args.hold_min,
        hold_max=args.hold_max,
        stuck_frames=args.stuck_frames,
        stuck_dist=args.stuck_dist,
        cell=args.cell,
        plane=args.plane,
        out=args.out,
    )


def register(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("bot", help="drive a scene with a seeded random input trace and report coverage")
    parser.add_argument("project")
    parser.add_argument("--scene", default=None)
    parser.add_argument("--frames", type=int, default=1800)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--actions", required=True, help="comma-separated action names, e.g. move_left,move_right,jump")
    parser.add_argument("--track", required=True, help="node whose global_position is sampled")
    parser.add_argument("--hold-min", type=int, default=6)
    parser.add_argument("--hold-max", type=int, default=30)
    parser.add_argument("--stuck-frames", type=int, default=120)
    parser.add_argument("--stuck-dist", type=float, default=4.0)
    parser.add_argument("--cell", type=int, default=32)
    parser.add_argument("--plane", choices=("auto", "xy", "xz", "yz"), default="auto",
                        help="coverage/stuck plane: auto uses XY for 2D, XZ for 3D")
    parser.add_argument("--out", default=None, help="also write the bot report JSON outside the project")
    parser.set_defaults(func=_cmd_bot)
