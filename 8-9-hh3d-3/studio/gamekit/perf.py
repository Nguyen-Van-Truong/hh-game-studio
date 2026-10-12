"""hh perf: frame, GPU and memory report plus a short instantiate/free leak check.

Read-only on the game project. The only file this command writes is ``--out``, and that path
has to sit outside the project. Textures still need an import pass first (``hh project import``
or ``scene.refresh_import``); this command does not run one.

Godot 4.7.2 freezes ``Performance.TIME_PROCESS``, ``TIME_PHYSICS_PROCESS`` and ``TIME_FPS`` after
the first frame when a SceneTree script overrides ``_process``. ``process_ms`` is the time from
that callback to a last-priority sentinel node, ``physics_ms`` is the time from ``physics_frame``
to the same sentinel, and ``fps`` is ``1000 / mean(frame_ms)``. The raw monitors are still
sampled and returned under ``monitors`` (they are not compared to the budget). GPU time comes
from the viewport render-time query and is ``not_measured`` under ``--headless``.
Node-leak growth is the larger of the ``OBJECT_NODE_COUNT`` slope and the orphan-node slope:
this Godot build does not count orphans in ``OBJECT_NODE_COUNT``.
"""

from __future__ import annotations

import math
import os
import re
from pathlib import Path
from typing import Any

from . import common as C

DEFAULT_BUDGET_PATH = C.GAMEKIT_DIR / "perf_budget_default.json"
SCHEMA = "hh-gamekit-perf-1"
_MB = 1024.0 * 1024.0
_MAIN_SCENE_RE = re.compile(r'(?m)^[ \t]*run/main_scene="([^"]+)"')
_RES_RE = re.compile(r"^(\d+)x(\d+)$")

BUDGET_KEYS = (
    "frame_ms_p95",
    "gpu_ms_p95",
    "process_ms_p95",
    "physics_ms_p95",
    "draw_calls_max",
    "primitives_max",
    "vram_mb_max",
    "nodes_max",
    "orphan_nodes_max",
    "leak_nodes_per_cycle_max",
    "leak_objects_per_cycle_max",
    "memory_static_mb_max",
)

# Arrays the runner always returns, renamed into the series judge() consumes.
_MEASURED_RENAME = {
    "process_measured_ms": "process_ms",
    "physics_measured_ms": "physics_ms",
}
_DIRECT_SAMPLES = (
    "frame_ms",
    "render_cpu_ms",
    "render_gpu_ms",
    "draw_calls",
    "primitives",
    "vram_bytes",
    "objects",
    "nodes",
    "orphans",
    "memory_static",
    "physics_2d",
    "physics_3d",
)
_MONITOR_SAMPLES = ("process_monitor_ms", "physics_monitor_ms")
_SAMPLE_KEYS = _DIRECT_SAMPLES + tuple(_MEASURED_RENAME) + _MONITOR_SAMPLES


# ---------------------------------------------------------------- budgets, traces, percentiles


def default_budget() -> dict[str, float]:
    raw = C.read_json(DEFAULT_BUDGET_PATH)
    if not isinstance(raw, dict):
        raise C.GamekitError("STATE_CORRUPT", "default perf budget is not an object")
    unknown = sorted(set(raw) - set(BUDGET_KEYS))
    missing = sorted(set(BUDGET_KEYS) - set(raw))
    if unknown or missing:
        raise C.GamekitError("STATE_CORRUPT", "default perf budget keys do not match", unknown=unknown, missing=missing)
    out: dict[str, float] = {}
    for key in BUDGET_KEYS:
        out[key] = _budget_number(key, raw[key], corrupt=True)
    return out


def merge_budget(override: dict[str, Any] | None = None, base: dict[str, float] | None = None) -> dict[str, float]:
    """Copy ``base`` (or the packaged defaults) and replace any subset of known keys."""
    merged = dict(base if base is not None else default_budget())
    if override is None:
        return merged
    if not isinstance(override, dict):
        raise C.GamekitError("BAD_REQUEST", "budget must be a JSON object")
    unknown = sorted(set(override) - set(BUDGET_KEYS))
    if unknown:
        raise C.GamekitError("BAD_REQUEST", "unknown budget keys: " + ", ".join(unknown))
    for key in BUDGET_KEYS:
        if key not in override:
            continue
        merged[key] = _budget_number(key, override[key], corrupt=False)
    return merged


def load_budget(path: Path | None) -> dict[str, float]:
    if path is None:
        return default_budget()
    raw = C.read_json(Path(path))
    if not isinstance(raw, dict):
        raise C.GamekitError("BAD_REQUEST", "budget file must be a JSON object")
    return merge_budget(raw)


def _budget_number(key: str, value: Any, *, corrupt: bool) -> float:
    code = "STATE_CORRUPT" if corrupt else "BAD_REQUEST"
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise C.GamekitError(code, f"budget {key} must be a finite number")
    number = float(value)
    if number < 0:
        raise C.GamekitError(code, f"budget {key} must be >= 0")
    return number


def load_trace(path: Path) -> dict[str, Any]:
    """Validate ``{"fps": 60, "events": [{"frame": 0, "action": "x", "pressed": true}]}``."""
    data = C.read_json(Path(path))
    if not isinstance(data, dict):
        raise C.GamekitError("BAD_REQUEST", "trace must be a JSON object")
    fps = data.get("fps")
    events = data.get("events")
    if isinstance(fps, bool) or not isinstance(fps, (int, float)) or not math.isfinite(float(fps)) or float(fps) <= 0:
        raise C.GamekitError("BAD_REQUEST", "trace.fps must be a positive number")
    if not isinstance(events, list):
        raise C.GamekitError("BAD_REQUEST", "trace.events must be a list")
    if len(events) > 100_000:
        raise C.GamekitError("BAD_REQUEST", "trace has too many events")
    clean: list[dict[str, Any]] = []
    for i, ev in enumerate(events):
        where = f"trace.events[{i}]"
        if not isinstance(ev, dict):
            raise C.GamekitError("BAD_REQUEST", f"{where} must be an object")
        frame = ev.get("frame")
        action = ev.get("action")
        pressed = ev.get("pressed")
        if isinstance(frame, bool) or not isinstance(frame, int) or frame < 0 or frame > 1_000_000:
            raise C.GamekitError("BAD_REQUEST", f"{where}.frame must be an integer >= 0")
        if not isinstance(action, str) or action == "" or len(action) > 128 or "\x00" in action:
            raise C.GamekitError("BAD_REQUEST", f"{where}.action must be a non-empty string")
        if not isinstance(pressed, bool):
            raise C.GamekitError("BAD_REQUEST", f"{where}.pressed must be a bool")
        clean.append({"frame": frame, "action": action, "pressed": pressed})
    return {"fps": float(fps), "events": clean}


def percentile(values: list[float], p: float) -> float:
    """Linear percentile. Rank is ``p/100 * (n - 1)`` (the common interpolated definition)."""
    if not values:
        raise ValueError("percentile of an empty series")
    if isinstance(p, bool) or not isinstance(p, (int, float)) or not math.isfinite(float(p)) or p < 0 or p > 100:
        raise ValueError("percentile p must be between 0 and 100")
    xs = sorted(float(v) for v in values)
    if len(xs) == 1:
        return xs[0]
    rank = (float(p) / 100.0) * (len(xs) - 1)
    lo = int(math.floor(rank))
    hi = int(math.ceil(rank))
    if lo == hi:
        return xs[lo]
    weight = rank - lo
    return xs[lo] * (1.0 - weight) + xs[hi] * weight


def least_squares_slope(values: list[float]) -> float | None:
    """Slope per step of ``values`` against x = 0, 1, 2, ... Needs at least two points."""
    n = len(values)
    if n < 2:
        return None
    mean_x = (n - 1) / 2.0
    mean_y = sum(values) / n
    num = 0.0
    den = 0.0
    for i, y in enumerate(values):
        dx = i - mean_x
        num += dx * (float(y) - mean_y)
        den += dx * dx
    if den == 0:
        return None
    return num / den


def _q(value: float) -> float:
    return round(float(value), 6)


def _timing(values: list[float]) -> dict[str, float]:
    return {
        "p50": _q(percentile(values, 50)),
        "p95": _q(percentile(values, 95)),
        "p99": _q(percentile(values, 99)),
        "max": _q(max(values)),
    }


def _peak(values: list[float]) -> float:
    return _q(max(values))


def _peak_mb(values: list[float]) -> float:
    return _q(max(values) / _MB)


# ---------------------------------------------------------------- sample normalization and verdict


def _as_floats(values: Any, name: str) -> list[float]:
    if not isinstance(values, list) or not values:
        raise C.GamekitError("GODOT_FAILED", f"perf samples missing {name}")
    out: list[float] = []
    for item in values:
        if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(float(item)):
            raise C.GamekitError("GODOT_FAILED", f"perf sample {name} is not a finite number")
        out.append(float(item))
    return out


def _as_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise C.GamekitError("GODOT_FAILED", f"perf field {name} is not an integer")
    if int(value) != float(value):
        raise C.GamekitError("GODOT_FAILED", f"perf field {name} is not an integer")
    return int(value)


def normalize_result(result: dict[str, Any], *, frames: int, leak_cycles: int) -> dict[str, Any]:
    """Turn the runner payload into equal-length series. Raises GODOT_FAILED when the shape is wrong."""
    if not isinstance(result, dict):
        raise C.GamekitError("GODOT_FAILED", "perf result is not an object")
    raw = result.get("samples")
    if not isinstance(raw, dict):
        raise C.GamekitError("GODOT_FAILED", "perf result has no samples")
    if not isinstance(result.get("gpu_measured"), bool):
        raise C.GamekitError("GODOT_FAILED", "perf result has no gpu_measured flag")
    if _as_int(result.get("sample_frames"), "sample_frames") != frames:
        raise C.GamekitError("GODOT_FAILED", f"perf measured {result.get('sample_frames')} frames, expected {frames}")
    series: dict[str, list[float]] = {}
    for key in _SAMPLE_KEYS:
        series[key] = _as_floats(raw.get(key), key)
        if len(series[key]) != frames:
            raise C.GamekitError("GODOT_FAILED", f"perf sample {key} has {len(series[key])} frames, expected {frames}")
    leak_raw = result.get("leak_samples")
    if not isinstance(leak_raw, list) or len(leak_raw) != leak_cycles:
        raise C.GamekitError("GODOT_FAILED", "perf leak sample count does not match leak_cycles")
    leak_samples: list[dict[str, Any]] = []
    for i, row in enumerate(leak_raw):
        if not isinstance(row, dict):
            raise C.GamekitError("GODOT_FAILED", f"leak sample {i} is not an object")
        cleaned: dict[str, Any] = {"cycle": _as_int(row.get("cycle"), f"leak_samples[{i}].cycle")}
        for key in ("objects", "nodes", "orphans", "memory_static"):
            if key not in row:
                raise C.GamekitError("GODOT_FAILED", f"leak sample {i} missing {key}")
            cleaned[key] = _as_floats([row[key]], f"leak_samples[{i}].{key}")[0]
        leak_samples.append(cleaned)
    cycles = [int(row["cycle"]) for row in leak_samples]
    if cycles != list(range(1, leak_cycles + 1)):
        raise C.GamekitError("GODOT_FAILED", f"leak cycles are {cycles}, expected 1..{leak_cycles}")
    samples = {key: series[key] for key in _DIRECT_SAMPLES}
    samples["process_ms"] = series["process_measured_ms"]
    samples["physics_ms"] = series["physics_measured_ms"]
    return {
        "samples": samples,
        "monitors": {
            "process_ms": _timing(series["process_monitor_ms"]),
            "physics_ms": _timing(series["physics_monitor_ms"]),
        },
        "leak_samples": leak_samples,
        "gpu_measured": result["gpu_measured"],
        "trace_applied": _as_int(result.get("trace_applied", 0), "trace_applied"),
    }


def _higher(left: float | None, right: float | None) -> float | None:
    vals = [v for v in (left, right) if v is not None]
    if not vals:
        return None
    return max(vals)


def _leak_slope(rows: list[dict[str, Any]], key: str) -> float | None:
    """Least-squares slope of cycles 2..N (cycle 1 is warmup and is left out)."""
    tail = [float(row[key]) for row in rows if int(row["cycle"]) >= 2]
    slope = least_squares_slope(tail)
    if slope is None:
        return None
    return _q(slope)


def judge(
    samples: dict[str, list[float]],
    leak_samples: list[dict[str, Any]],
    budget: dict[str, float],
    *,
    gpu_measured: bool,
) -> dict[str, Any]:
    """Percentiles, peaks, leak slopes and budget violations. ``ok`` is false when anything exceeds."""
    frame = _timing(samples["frame_ms"])
    process = _timing(samples["process_ms"])
    physics = _timing(samples["physics_ms"])
    draw_calls = _peak(samples["draw_calls"])
    primitives = _peak(samples["primitives"])
    vram_mb = _peak_mb(samples["vram_bytes"])
    nodes = _peak(samples["nodes"])
    orphans = _peak(samples["orphans"])
    objects = _peak(samples["objects"])
    memory_mb = _peak_mb(samples["memory_static"])
        # Godot 4.7.2 keeps orphan nodes out of OBJECT_NODE_COUNT, so a Node.new()
    # held off the tree shows up only as orphan growth. Node growth is whichever
    # of those two slopes is larger.
    nodes_slope = _higher(_leak_slope(leak_samples, "nodes"), _leak_slope(leak_samples, "orphans"))
    objects_slope = _leak_slope(leak_samples, "objects")
    gpu_stats = _timing(samples["render_gpu_ms"]) if gpu_measured else None
    cpu_stats = _timing(samples["render_cpu_ms"]) if gpu_measured else None
    compared: dict[str, float | None] = {
        "frame_ms_p95": frame["p95"],
        "gpu_ms_p95": None if gpu_stats is None else gpu_stats["p95"],
        "process_ms_p95": process["p95"],
        "physics_ms_p95": physics["p95"],
        "draw_calls_max": draw_calls,
        "primitives_max": primitives,
        "vram_mb_max": vram_mb,
        "nodes_max": nodes,
        "orphan_nodes_max": orphans,
        "leak_nodes_per_cycle_max": nodes_slope,
        "leak_objects_per_cycle_max": objects_slope,
        "memory_static_mb_max": memory_mb,
    }
    violations: list[dict[str, Any]] = []
    for key in BUDGET_KEYS:
        value = compared[key]
        if value is None:
            continue
        limit = float(budget[key])
        if value > limit:
            violations.append({"metric": key, "value": value, "limit": limit})
    suspected = any(item["metric"] in ("leak_nodes_per_cycle_max", "leak_objects_per_cycle_max") for item in violations)
    mean_frame = sum(samples["frame_ms"]) / len(samples["frame_ms"])
    fps = None if mean_frame <= 1e-9 else _q(1000.0 / mean_frame)
    return {
        "ok": not violations,
        "fps": fps,
        "frame_ms": frame,
        "process_ms": process,
        "physics_ms": physics,
        "cpu_render_ms": cpu_stats if cpu_stats is not None else "not_measured",
        "gpu_ms": gpu_stats["p95"] if gpu_stats is not None else "not_measured",
        "gpu_ms_stats": gpu_stats if gpu_stats is not None else "not_measured",
        "draw_calls": draw_calls,
        "primitives": primitives,
        "vram_mb": vram_mb,
        "nodes": nodes,
        "orphan_nodes": orphans,
        "objects": objects,
        "memory_static_mb": memory_mb,
        "physics_2d_active": _peak(samples["physics_2d"]),
        "physics_3d_active": _peak(samples["physics_3d"]),
        "leak_suspected": suspected,
        "leak": {
            "cycles": len(leak_samples),
            "nodes_per_cycle": nodes_slope,
            "objects_per_cycle": objects_slope,
            "suspected": suspected,
            "samples": leak_samples,
        },
        "violations": violations,
    }


# ---------------------------------------------------------------- command


def parse_resolution(text: str) -> tuple[int, int]:
    if not isinstance(text, str):
        raise C.GamekitError("BAD_REQUEST", "resolution must be WxH")
    match = _RES_RE.fullmatch(text.strip())
    if not match:
        raise C.GamekitError("BAD_REQUEST", "resolution must be WxH, for example 1280x720")
    width, height = int(match.group(1)), int(match.group(2))
    if width < 16 or height < 16 or width > 8192 or height > 8192:
        raise C.GamekitError("BAD_REQUEST", "resolution must be between 16x16 and 8192x8192")
    return width, height


def _coerce_resolution(value: str | tuple[int, int]) -> tuple[int, int]:
    if isinstance(value, str):
        return parse_resolution(value)
    if isinstance(value, tuple) and len(value) == 2 and not isinstance(value[0], bool) and not isinstance(value[1], bool):
        return parse_resolution(f"{value[0]}x{value[1]}")
    raise C.GamekitError("BAD_REQUEST", "resolution must be WxH")


def _bounded_int(name: str, value: Any, lo: int, hi: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise C.GamekitError("BAD_REQUEST", f"{name} must be an integer")
    if value < lo or value > hi:
        raise C.GamekitError("BAD_REQUEST", f"{name} must be {lo}..{hi}")
    return value


def main_scene_of(root: Path) -> str | None:
    text = (Path(root) / "project.godot").read_text(encoding="utf-8")
    match = _MAIN_SCENE_RE.search(text)
    if not match:
        return None
    value = match.group(1)
    if not value.startswith("res://"):
        raise C.GamekitError("BAD_REQUEST", "project main_scene is not a res:// path; pass --scene")
    return value


def resolve_scene(project: C.Project, scene: str | None) -> str:
    chosen = scene if scene else main_scene_of(project.root)
    if not chosen:
        raise C.GamekitError("BAD_REQUEST", "no --scene and the project has no main scene")
    if not chosen.endswith(".tscn"):
        raise C.GamekitError("BAD_PATH", "perf scene must be a .tscn file")
    project.res_to_path(chosen, must_exist=True)
    return chosen


def _outside_project(project: C.Project, out: Path) -> Path:
    path = Path(out)
    if not path.is_absolute():
        path = Path(os.path.abspath(str(path)))
    if C.is_within(path, project.root) or os.path.normcase(os.path.abspath(str(path))) == os.path.normcase(os.path.abspath(str(project.root))):
        raise C.GamekitError("BAD_REQUEST", "--out must be outside the project")
    return path


def _timeout_for(frames: int, warmup: int, leak_cycles: int) -> float:
    steps = frames + warmup + leak_cycles * 16
    return float(min(150, max(90, 45 + steps // 15)))


def run_report(
    project: C.Project,
    *,
    scene: str | None = None,
    frames: int = 300,
    warmup: int = 60,
    resolution: str | tuple[int, int] = "1280x720",
    headless: bool = False,
    budget_path: Path | None = None,
    leak_cycles: int = 5,
    trace_path: Path | None = None,
    out_path: Path | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    frames_i = _bounded_int("frames", frames, 1, 5000)
    warmup_i = _bounded_int("warmup", warmup, 0, 5000)
    leak_i = _bounded_int("leak_cycles", leak_cycles, 3, 30)
    res = _coerce_resolution(resolution)
    budget = load_budget(Path(budget_path) if budget_path else None)
    trace = load_trace(Path(trace_path)) if trace_path else None
    scene_res = resolve_scene(project, scene)
    out = _outside_project(project, Path(out_path)) if out_path else None
    request: dict[str, Any] = {
        "scene": scene_res,
        "frames": frames_i,
        "warmup": warmup_i,
        "leak_cycles": leak_i,
        "headless": bool(headless),
    }
    if trace is not None:
        request["trace"] = trace
    limit = float(timeout) if timeout is not None else _timeout_for(frames_i, warmup_i, leak_i)
    with C.project_lock(project, "perf", wait_seconds=30):
        run = C.run_godot_tool(
            project.root,
            "perf_runner.gd",
            request,
            headless=bool(headless),
            windowed=not bool(headless),
            resolution=None if headless else res,
            timeout=limit,
        )
    result = C.require_result(run, "perf")
    norm = normalize_result(result, frames=frames_i, leak_cycles=leak_i)
    judged = judge(norm["samples"], norm["leak_samples"], budget, gpu_measured=bool(norm["gpu_measured"]))
    report: dict[str, Any] = {
        "ok": judged["ok"],
        "schema": SCHEMA,
        "kind": "perf",
        "project": project.project_id,
        "scene": scene_res,
        "headless": bool(headless),
        "resolution": None if headless else [res[0], res[1]],
        "frames": frames_i,
        "warmup": warmup_i,
        "leak_cycles": leak_i,
        "fps": judged["fps"],
        "frame_ms": judged["frame_ms"],
        "process_ms": judged["process_ms"],
        "physics_ms": judged["physics_ms"],
        "cpu_render_ms": judged["cpu_render_ms"],
        "gpu_ms": judged["gpu_ms"],
        "gpu_ms_stats": judged["gpu_ms_stats"],
        "draw_calls": judged["draw_calls"],
        "primitives": judged["primitives"],
        "vram_mb": judged["vram_mb"],
        "nodes": judged["nodes"],
        "orphan_nodes": judged["orphan_nodes"],
        "objects": judged["objects"],
        "memory_static_mb": judged["memory_static_mb"],
        "physics_2d_active": judged["physics_2d_active"],
        "physics_3d_active": judged["physics_3d_active"],
        "leak_suspected": judged["leak_suspected"],
        "leak": judged["leak"],
        "violations": judged["violations"],
        "budget": budget,
        "timing_source": {
            "frame_ms": "ticks_usec",
            "process_ms": "sentinel",
            "physics_ms": "physics_frame",
            "fps": "1000/mean(frame_ms)",
            "gpu_ms": "viewport" if norm["gpu_measured"] else "not_measured",
        },
        "monitors": norm["monitors"],
        "trace_applied": norm["trace_applied"],
        "process": run.summary(),
        "at": C.now_iso(),
    }
    if trace is not None:
        report["trace_fps"] = trace["fps"]
    if out is not None:
        C.atomic_write_json(out, report)
        report["out"] = str(out)
    return report


def handler(args: Any) -> dict[str, Any]:
    return run_report(
        C.get_project(args.project),
        scene=args.scene,
        frames=args.frames,
        warmup=args.warmup,
        resolution=args.resolution,
        headless=args.headless,
        budget_path=Path(args.budget) if args.budget else None,
        leak_cycles=args.leak_cycles,
        trace_path=Path(args.trace) if args.trace else None,
        out_path=Path(args.out) if args.out else None,
    )


def register(sub: Any) -> None:
    parser = sub.add_parser("perf", help="measure a scene against a budget and run a short leak check")
    parser.add_argument("project", help="registered project id or path")
    parser.add_argument("--scene", default=None, help="res:// scene; default is the project main scene")
    parser.add_argument("--frames", type=int, default=300, help="frames sampled after warmup (default 300)")
    parser.add_argument("--warmup", type=int, default=60, help="frames discarded before sampling (default 60)")
    parser.add_argument("--resolution", default="1280x720", help="window size WxH (default 1280x720)")
    parser.add_argument("--headless", action="store_true", help="no window; GPU time is reported as not_measured")
    parser.add_argument("--budget", default=None, help="JSON file overriding any subset of the default budget")
    parser.add_argument("--leak-cycles", type=int, default=5, help="instantiate/free cycles after sampling (min 3)")
    parser.add_argument("--trace", default=None, help="input trace JSON {fps, events:[{frame, action, pressed}]}")
    parser.add_argument("--out", default=None, help="write the report JSON here (outside the project)")
    parser.set_defaults(func=handler)
