"""W6 selftest: a small 2D scene passes the default budget; a leaking script does not.

Windowed runs use 640x360 (passing scene) or the same project. Frames stay small so the
whole selftest, including the editor import, finishes in a couple of minutes.
"""

from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path

from .. import perf as P
from .. import scene as S
from . import Ctx

_SETTINGS = """
[display]

window/size/viewport_width=640
window/size/viewport_height=360
window/vsync/vsync_mode=0

[rendering]

renderer/rendering_method="forward_plus"
"""

_LEAK_GD = """extends Node2D

static var held: Array[Node] = []


func _ready() -> void:
	var extra: Node = Node.new()
	held.append(extra)
"""

_LEAK_TSCN = """[gd_scene load_steps=2 format=3 uid="uid://bw6perfleak0001"]

[ext_resource type="Script" path="res://leak.gd" id="1_leak"]

[node name="LeakRoot" type="Node2D"]
script = ExtResource("1_leak")
"""


def _png(width: int = 8, height: int = 8, rgb: tuple[int, int, int] = (220, 40, 50)) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = (b"\x00" + bytes(rgb) * width) * height
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


def _main_tscn() -> str:
    lines = [
        '[gd_scene load_steps=2 format=3 uid="uid://bw6perfmain0001"]',
        "",
        '[ext_resource type="Texture2D" path="res://dot.png" id="1_tex"]',
        "",
        '[node name="Main" type="Node2D"]',
        "",
        '[node name="Sky" type="ColorRect" parent="."]',
        "offset_right = 640.0",
        "offset_bottom = 360.0",
        "color = Color(0.12, 0.14, 0.2, 1)",
        "",
        '[node name="Cam" type="Camera2D" parent="."]',
        "position = Vector2(80, 40)",
        "",
    ]
    for i in range(50):
        x = (i % 10) * 16 + 8
        y = (i // 10) * 16 + 8
        lines.extend([
            f'[node name="S{i}" type="Sprite2D" parent="."]',
            f"position = Vector2({x}, {y})",
            'texture = ExtResource("1_tex")',
            "",
        ])
    return "\n".join(lines)


def _brief(report: dict) -> dict:
    frame = report.get("frame_ms") or {}
    leak = report.get("leak") or {}
    return {
        "ok": report.get("ok"),
        "fps": report.get("fps"),
        "frame_ms_p95": frame.get("p95") if isinstance(frame, dict) else frame,
        "process_ms_p95": (report.get("process_ms") or {}).get("p95") if isinstance(report.get("process_ms"), dict) else None,
        "physics_ms_p95": (report.get("physics_ms") or {}).get("p95") if isinstance(report.get("physics_ms"), dict) else None,
        "gpu_ms": report.get("gpu_ms"),
        "draw_calls": report.get("draw_calls"),
        "vram_mb": report.get("vram_mb"),
        "orphan_nodes": report.get("orphan_nodes"),
        "nodes_per_cycle": leak.get("nodes_per_cycle"),
        "objects_per_cycle": leak.get("objects_per_cycle"),
        "violations": report.get("violations"),
        "errors": (report.get("process") or {}).get("errors"),
    }


def _remember(ctx: Ctx, report: dict) -> None:
    path = ctx.root.parent / "w6-metrics.json"
    payload = _brief(report)
    payload["scene"] = report.get("scene")
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run(ctx: Ctx) -> None:
    project = ctx.project(
        "w6perf",
        {
            "dot.png": _png(),
            "main.tscn": _main_tscn(),
            "leak.gd": _LEAK_GD,
            "leak.tscn": _LEAK_TSCN,
        },
        main_scene="res://main.tscn",
        settings=_SETTINGS,
    )
    bad_budget = ctx.root / "bad-budget.json"
    bad_budget.write_text('{"nope": 1}\n', encoding="utf-8")
    ctx.expect_error("unknown budget key rejected", "BAD_REQUEST", P.run_report, project,
                     budget_path=bad_budget, frames=10, warmup=0, leak_cycles=3, resolution="320x180")
    bad_trace = ctx.root / "bad-trace.json"
    bad_trace.write_text('{"fps": 60, "events": [{"frame": 0, "action": "x", "pressed": 1}]}', encoding="utf-8")
    ctx.expect_error("trace pressed must be bool", "BAD_REQUEST", P.run_report, project,
                     trace_path=bad_trace, frames=10, warmup=0, leak_cycles=3, resolution="320x180")
    ctx.expect_error("out inside project rejected", "BAD_REQUEST", P.run_report, project,
                     out_path=project.root / "inside.json", frames=10, warmup=0, leak_cycles=3, resolution="320x180")

    imported = ctx.guard("import textures", lambda: S.refresh_import(project.root))
    ctx.check("png import pass ran", isinstance(imported, dict) and imported.get("imported") is True, imported=imported)
    ctx.check("png import sidecar exists", (project.root / "dot.png.import").is_file())

    trace = ctx.root / "trace.json"
    trace.write_text(json.dumps({
        "fps": 60,
        "events": [
            {"frame": 0, "action": "move_right", "pressed": True},
            {"frame": 2, "action": "move_right", "pressed": False},
            {"frame": 10, "action": "jump", "pressed": True},
        ],
    }), encoding="utf-8")
    out = ctx.root / "pass-report.json"
    report = ctx.guard("perf passing scene", lambda: P.run_report(
        project, scene="res://main.tscn", frames=120, warmup=30, leak_cycles=4,
        resolution="640x360", trace_path=trace, out_path=out,
    ))
    if not isinstance(report, dict):
        return
    _remember(ctx, report)
    brief = _brief(report)
    ctx.check("passing scene meets the default budget", report.get("ok") is True and report.get("leak_suspected") is False,
              fps=brief.get("fps"), frame_ms_p95=brief.get("frame_ms_p95"), process_ms_p95=brief.get("process_ms_p95"),
              physics_ms_p95=brief.get("physics_ms_p95"), gpu_ms=brief.get("gpu_ms"), draw_calls=brief.get("draw_calls"),
              vram_mb=brief.get("vram_mb"), nodes_per_cycle=brief.get("nodes_per_cycle"),
              objects_per_cycle=brief.get("objects_per_cycle"), violations=brief.get("violations"), errors=brief.get("errors"))
    ctx.check("gpu_ms is a number", isinstance(report.get("gpu_ms"), (int, float)) and report["gpu_ms"] > 0, gpu_ms=report.get("gpu_ms"))
    ctx.check("draw_calls is a number", isinstance(report.get("draw_calls"), (int, float)) and report["draw_calls"] > 0,
              draw_calls=report.get("draw_calls"))
    ctx.check("vram_mb is a number", isinstance(report.get("vram_mb"), (int, float)) and report["vram_mb"] > 0,
              vram_mb=report.get("vram_mb"))
    frame = report.get("frame_ms") or {}
    ctx.check("frame percentiles are ordered",
              isinstance(frame, dict) and frame.get("p50", 9) <= frame.get("p95", 0) <= frame.get("p99", 0) <= frame.get("max", 0) + 1e-6,
              frame_ms=frame)
    ctx.check("trace events applied", report.get("trace_applied") == 3, trace_applied=report.get("trace_applied"))
    ctx.check("report written outside the project", out.is_file() and json.loads(out.read_text(encoding="utf-8")).get("ok") is True)
    ctx.check("no godot errors on the passing scene", not (report.get("process") or {}).get("errors"),
              errors=(report.get("process") or {}).get("errors"))

    leaked = ctx.guard("perf leaking scene", lambda: P.run_report(
        project, scene="res://leak.tscn", frames=15, warmup=5, leak_cycles=4,
        resolution="320x180", headless=True,
    ))
    if isinstance(leaked, dict):
        growth = (leaked.get("leak") or {}).get("nodes_per_cycle")
        ctx.check("leaking script is suspected", leaked.get("ok") is False and leaked.get("leak_suspected") is True
                  and isinstance(growth, (int, float)) and growth > 0.5,
                  growth=growth, violations=leaked.get("violations"), leak=leaked.get("leak"))

    tight = ctx.root / "tight-budget.json"
    tight.write_text('{"draw_calls_max": 0}\n', encoding="utf-8")
    budget_run = ctx.guard("perf zero draw-call budget", lambda: P.run_report(
        project, scene="res://main.tscn", frames=20, warmup=8, leak_cycles=3,
        resolution="640x360", budget_path=tight,
    ))
    if isinstance(budget_run, dict):
        hit = [v for v in budget_run.get("violations", []) if v.get("metric") == "draw_calls_max"]
        ctx.check("draw_calls_max 0 is a violation", budget_run.get("ok") is False and len(hit) == 1
                  and hit[0].get("limit") == 0 and hit[0].get("value", 0) > 0,
                  violations=budget_run.get("violations"))

    headless = ctx.guard("perf headless", lambda: P.run_report(
        project, scene="res://main.tscn", frames=20, warmup=8, leak_cycles=3, headless=True,
    ))
    if isinstance(headless, dict):
        head_brief = _brief(headless)
        ctx.check("headless gpu is not_measured and the rest passes",
                  headless.get("gpu_ms") == "not_measured" and headless.get("ok") is True
                  and headless.get("leak_suspected") is False,
                  fps=head_brief.get("fps"), gpu_ms=head_brief.get("gpu_ms"),
                  violations=head_brief.get("violations"), errors=head_brief.get("errors"),
                  nodes_per_cycle=head_brief.get("nodes_per_cycle"))
