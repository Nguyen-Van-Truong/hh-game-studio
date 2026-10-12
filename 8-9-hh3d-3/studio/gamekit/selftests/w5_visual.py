"""W5 selftest: windowed shots, blank/presence checks, baseline write and vcheck."""

from __future__ import annotations

from pathlib import Path

from .. import common as C
from .. import pngio
from .. import scene as scene_mod
from .. import shot
from .. import vcheck
from ..hh import build_parser
from . import Ctx

EXPECT = ["Backdrop", "Mark", "Score", "Pin", "Away", "Sparks", "Marker", "Behind", "Nope"]

DRIVER = """extends Node

func _process(_delta: float) -> void:
	if Input.is_action_pressed("paint"):
		var backdrop: ColorRect = get_node_or_null("Backdrop") as ColorRect
		if backdrop != null:
			backdrop.color = Color(0.95, 0.2, 0.15, 1)
"""

STAGE = """[gd_scene load_steps=3 format=3 uid="uid://bshotw5stage1"]

[ext_resource type="Texture2D" path="res://art/mark.png" id="1_mark"]
[ext_resource type="Script" path="res://driver.gd" id="2_drv"]

[node name="Stage" type="Node"]
script = ExtResource("2_drv")

[node name="Backdrop" type="ColorRect" parent="."]
offset_right = 320.0
offset_bottom = 180.0
color = Color(0.12, 0.35, 0.55, 1)

[node name="Mark" type="Sprite2D" parent="."]
position = Vector2(160, 90)
texture = ExtResource("1_mark")

[node name="Score" type="Label" parent="."]
offset_left = 8.0
offset_top = 8.0
offset_right = 160.0
offset_bottom = 40.0
theme_override_font_sizes/font_size = 24
text = "Score 12"

[node name="Pin" type="Marker2D" parent="."]
position = Vector2(4, 4)

[node name="Away" type="Sprite2D" parent="."]
position = Vector2(5000, 5000)
texture = ExtResource("1_mark")

[node name="Sparks" type="GPUParticles2D" parent="."]
position = Vector2(30, 40)
emitting = false
amount = 1

[node name="Cam" type="Camera3D" parent="."]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 5)
current = true

[node name="Marker" type="Marker3D" parent="."]

[node name="Behind" type="Marker3D" parent="."]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 12)
"""

EMPTY = """[gd_scene format=3 uid="uid://bshotw5empty01"]

[node name="Empty" type="Node2D"]
"""

SETTINGS = """
[display]

window/size/viewport_width=320
window/size/viewport_height=180
window/size/window_width_override=320
window/size/window_height_override=180
window/dpi/allow_hidpi=false
window/stretch/mode="disabled"

[rendering]

environment/defaults/default_clear_color=Color(0.15, 0.16, 0.18, 1)

[input]

paint={
"deadzone": 0.5,
"events": []
}
"""


def _checker(size: int = 48) -> bytes:
    raw = bytearray()
    for y in range(size):
        for x in range(size):
            if ((x // 4) + (y // 4)) % 2 == 0:
                raw.extend((255, 40, 180, 255))
            else:
                raw.extend((255, 220, 40, 255))
    image = pngio.Image(size, size, "RGBA", bytes(raw))
    return pngio.encode(image)


def _by_path(receipt: dict) -> dict:
    return {row["path"]: row for row in receipt.get("presence", [])}


def run(ctx: Ctx) -> None:
    mark = _checker()
    project = ctx.project(
        "vis",
        {
            "art/mark.png": mark,
            "driver.gd": DRIVER,
            "stage.tscn": STAGE,
            "empty.tscn": EMPTY,
        },
        main_scene="res://stage.tscn",
        settings=SETTINGS,
    )
    imported = ctx.guard("import textures", lambda: scene_mod.refresh_import(project.root, force=True))
    if not ctx.check("mark.png imported", (project.root / "art" / "mark.png.import").is_file(), import_result=imported):
        return

    shots = ctx.root / "shots"
    shots.mkdir()
    out = shots / "stage.png"
    common = dict(
        scene="res://stage.tscn",
        frames=10,
        resolution=(320, 180),
        seed=7,
        expect=EXPECT,
        baseline="res://tests/visual/stage.png",
        threshold=0.01,
        pixel_tolerance=8,
    )
    wrote = ctx.guard("baseline write", lambda: shot.capture(project, out, command_id="w5.base.1", **common))
    if not ctx.check(
        "baseline written",
        isinstance(wrote, dict) and wrote.get("ok") is True and wrote.get("status") == "BASELINE_WRITTEN",
        status=None if not isinstance(wrote, dict) else wrote.get("status"),
        blank=None if not isinstance(wrote, dict) else wrote.get("blank"),
        size=None if not isinstance(wrote, dict) else wrote.get("size"),
        errors=None if not isinstance(wrote, dict) else wrote.get("process", {}).get("errors", [])[:8],
    ):
        return

    png = pngio.read(out)
    ctx.check("png exists at the requested size", png.width == 320 and png.height == 180 and out.is_file(),
              size=[png.width, png.height])
    ctx.check("stage is not blank", wrote["blank"] is False, metrics=wrote.get("blank_metrics"))
    baseline = project.res_to_path("res://tests/visual/stage.png")
    ctx.check("baseline bytes match the shot", baseline.is_file() and C.sha256_file(baseline) == wrote["files"][0]["sha256"])
    same = vcheck.compare_files(out, out, threshold=0.01, pixel_tolerance=8)
    ctx.check("vcheck against itself is PASS", same.get("ok") is True and same.get("changed_ratio") == 0.0
              and same.get("status") == "PASS" and same.get("max_diff") == 0)

    presence = _by_path(wrote)
    ctx.check("backdrop and score on screen",
              presence["Backdrop"]["exists"] and presence["Backdrop"]["on_screen"] and presence["Backdrop"]["visible_in_tree"]
              and presence["Score"]["on_screen"] and presence["Score"]["class"] == "Label")
    ctx.check("sprite on screen", presence["Mark"]["exists"] and presence["Mark"]["on_screen"] is True
              and presence["Mark"]["class"] == "Sprite2D", row=presence["Mark"])
    ctx.check("marker2d point on screen", presence["Pin"]["exists"] and presence["Pin"]["on_screen"] is True)
    ctx.check("node at 5000,5000 is off screen", presence["Away"]["exists"] and presence["Away"]["on_screen"] is False,
              row=presence["Away"])
    ctx.check("particles report emitting", presence["Sparks"]["exists"] and presence["Sparks"]["emitting"] is False
              and presence["Sparks"]["on_screen"] is True, row=presence["Sparks"])
    ctx.check("node3d in front of camera is on screen", presence["Marker"]["exists"] and presence["Marker"]["on_screen"] is True,
              row=presence["Marker"])
    ctx.check("node3d behind camera is off screen", presence["Behind"]["exists"] and presence["Behind"]["on_screen"] is False,
              row=presence["Behind"])
    ctx.check("missing node", presence["Nope"]["exists"] is False and presence["Nope"]["on_screen"] is False)
    script_errors = [err for err in wrote.get("process", {}).get("errors", []) if "SCRIPT ERROR" in err or "Parse Error" in err]
    ctx.check("no script errors", not script_errors, errors=script_errors[:8])

    replay = shot.capture(project, out, command_id="w5.base.1", **common)
    ctx.check("same command replays the receipt", replay.get("replayed") is True and replay.get("status") == "BASELINE_WRITTEN"
              and replay.get("files", [{}])[0].get("sha256") == wrote["files"][0]["sha256"])

    rgba = png.to_rgba()
    spec = "0,0,#{:02x}{:02x}{:02x},0".format(rgba[0], rgba[1], rgba[2])
    parser = build_parser()

    def _cli(argv: list[str]) -> dict:
        parsed = parser.parse_args(argv)
        return parsed.func(parsed)

    cli = _cli(["vcheck", str(out), str(out), "--threshold", "0.01", "--pixel-tolerance", "8"])
    ctx.check("vcheck cli self-compare", cli.get("status") == "PASS" and cli.get("changed_ratio") == 0.0)
    color_cli = _cli(["vcheck", "--blank", str(out), "--expect-color", spec])
    ctx.check("expect-color matches the corner pixel", color_cli.get("expect_color", [{}])[0].get("ok") is True,
              got=color_cli.get("expect_color"))
    ctx.check("stage blank verdict is false", color_cli.get("blank") is False)
    wrong = _cli(["vcheck", str(out), str(out), "--expect-color", "0,0,#00ff00,0"])
    ctx.check("wrong expect-color fails", wrong.get("ok") is False and wrong.get("expect_color", [{}])[0].get("ok") is False)
    warnings = wrote.get("process", {}).get("warnings", [])
    ctx.check("shot log has no warnings", not warnings, warnings=warnings[:8])

    again = ctx.guard("baseline compare", lambda: shot.capture(project, shots / "stage-again.png", **common))
    ctx.check("second shot matches the baseline", isinstance(again, dict) and again.get("status") == "PASS"
              and again.get("ok") is True and again.get("compare", {}).get("changed_ratio") == 0.0,
              status=None if not isinstance(again, dict) else again.get("status"),
              compare=None if not isinstance(again, dict) else again.get("compare"),
              errors=None if not isinstance(again, dict) else again.get("process", {}).get("errors", [])[:6])

    trace_path = shots / "trace.json"
    C.atomic_write_json(trace_path, {"fps": 60, "events": [{"frame": 0, "action": "paint", "pressed": True}]})
    painted = ctx.guard(
        "trace shot",
        lambda: shot.capture(
            project, shots / "trace.png", scene="res://stage.tscn", frames=10, resolution=(320, 180), seed=7,
            trace=shot.validate_trace(C.read_json(trace_path)), baseline="res://tests/visual/stage.png",
            threshold=0.01, pixel_tolerance=8,
        ),
    )
    trace_ratio = None if not isinstance(painted, dict) else painted.get("compare", {}).get("changed_ratio")
    ctx.check("input trace changes the picture", isinstance(painted, dict) and painted.get("status") == "FAIL"
              and isinstance(trace_ratio, float) and trace_ratio > 0.01, ratio=trace_ratio,
              status=None if not isinstance(painted, dict) else painted.get("status"))

    scene_path = project.res_to_path("res://stage.tscn")
    original = scene_path.read_text(encoding="utf-8")
    scene_path.write_text(original.replace("Color(0.12, 0.35, 0.55, 1)", "Color(0.9, 0.15, 0.1, 1)", 1), encoding="utf-8")
    diff = shots / "changed_diff.png"
    changed = ctx.guard(
        "recolored shot",
        lambda: shot.capture(
            project, shots / "changed.png", scene="res://stage.tscn", frames=10, resolution=(320, 180), seed=7,
            baseline="res://tests/visual/stage.png", threshold=0.01, pixel_tolerance=8, diff_out=diff,
        ),
    )
    ratio = None if not isinstance(changed, dict) else changed.get("compare", {}).get("changed_ratio")
    kept = C.sha256_file(baseline)
    ctx.check(
        "recolored shot fails the baseline",
        isinstance(changed, dict) and changed.get("ok") is False and changed.get("status") == "FAIL"
        and isinstance(ratio, float) and ratio > 0.01 and diff.is_file() and kept == wrote["files"][0]["sha256"],
        ratio=ratio,
        diff=diff.is_file(),
        bbox=None if not isinstance(changed, dict) else changed.get("compare", {}).get("bbox"),
    )
    if diff.is_file():
        diff_img = pngio.read(diff)
        ctx.check("diff image has changes", diff_img.width == 320 and diff_img.height == 180 and any(diff_img.pixels))

    empty_out = shots / "empty.png"
    empty = ctx.guard(
        "empty shot",
        lambda: shot.capture(
            project, empty_out, scene="res://empty.tscn", frames=8, at=[6, 8], resolution=(320, 180), seed=1,
        ),
    )
    names = [] if not isinstance(empty, dict) else [Path(row["path"]).name for row in empty.get("files", [])]
    ctx.check(
        "empty scene is blank",
        isinstance(empty, dict) and empty.get("status") == "CAPTURED" and empty.get("blank") is True
        and empty.get("size") == [320, 180] and names == ["empty_f6.png", "empty_f8.png"] and not empty_out.exists(),
        status=None if not isinstance(empty, dict) else empty.get("status"),
        blank=None if not isinstance(empty, dict) else empty.get("blank_metrics"),
        size=None if not isinstance(empty, dict) else empty.get("size"),
        files=names,
    )
    early = shots / "empty_f6.png"
    if early.is_file():
        ctx.check("earlier empty frame is blank", vcheck.blank_file(early).get("blank") is True)
