"""Strict-warning selftest: every type-2 GDScript warning is an error, including res://addons.

``directory_rules`` value 0 excludes a directory (the engine default for ``res://addons``).
Value 1 includes it, so an untyped script under ``res://addons`` fails ``hh check``.
"""

from __future__ import annotations

import argparse

from .. import bot as B
from .. import common as C
from .. import inputmap as IM
from .. import kit as K
from .. import perf as Perf
from .. import play as Play
from .. import scene as S
from .. import shot
from . import Ctx

# Godot 4.7 WarningDirectoryRule: 0 = Exclude, 1 = Include. 2 is out of range.
_ADDONS_INCLUDE = 1

_TYPE2 = (
    "unassigned_variable",
    "unassigned_variable_op_assign",
    "unused_variable",
    "unused_local_constant",
    "unused_private_class_variable",
    "unused_parameter",
    "unused_signal",
    "shadowed_variable",
    "shadowed_variable_base_class",
    "shadowed_global_identifier",
    "unreachable_code",
    "unreachable_pattern",
    "standalone_expression",
    "standalone_ternary",
    "incompatible_ternary",
    "untyped_declaration",
    "inferred_declaration",
    "unsafe_property_access",
    "unsafe_method_access",
    "unsafe_cast",
    "unsafe_call_argument",
    "unsafe_void_return",
    "return_value_discarded",
    "static_called_on_instance",
    "missing_tool",
    "redundant_static_unload",
    "redundant_await",
    "missing_await",
    "assert_always_true",
    "assert_always_false",
    "integer_division",
    "narrowing_conversion",
    "int_as_enum_without_cast",
    "int_as_enum_without_match",
    "enum_variable_without_default",
    "empty_file",
    "deprecated_keyword",
    "confusable_identifier",
    "confusable_local_declaration",
    "confusable_local_usage",
    "confusable_capture_reassignment",
    "confusable_temporary_modification",
    "inference_on_variant",
    "native_method_override",
    "get_node_default_without_onready",
    "onready_with_export",
    "property_used_as_function",
    "constant_used_as_function",
    "function_used_as_property",
)

_SETTINGS = """
[display]

window/size/viewport_width=320
window/size/viewport_height=180
window/vsync/vsync_mode=0

[debug]

gdscript/warnings/enable=true
"""

_CANARY = "extends Node\nvar speed = 10\n"

_PLAYER = """extends CharacterBody2D

const SPEED: float = 200.0


func _physics_process(_delta: float) -> void:
	var axis: float = Input.get_axis("move_left", "move_right")
	velocity = Vector2(axis * SPEED, 0.0)
	@warning_ignore("return_value_discarded") # the probe only needs the slide side effect
	move_and_slide()


func _on_hit(_body: Node2D) -> void:
	pass
"""

_MAIN = """[gd_scene load_steps=3 format=3 uid="uid://bstrictmain001"]

[ext_resource type="Script" path="res://player.gd" id="1_player"]

[sub_resource type="RectangleShape2D" id="player_shape"]
size = Vector2(16, 16)

[node name="Main" type="Node2D"]

[node name="Label" type="Label" parent="."]
offset_left = 8.0
offset_top = 8.0
offset_right = 120.0
offset_bottom = 32.0
text = "Vault"

[node name="Mark" type="Sprite2D" parent="."]
position = Vector2(24, 24)

[node name="Player" type="CharacterBody2D" parent="."]
motion_mode = 1
position = Vector2(40, 40)
script = ExtResource("1_player")

[node name="Shape" type="CollisionShape2D" parent="Player"]
shape = SubResource("player_shape")
"""

_ACTIONS = {
    "move_left": {"deadzone": 0.5, "events": [{"key": "A"}]},
    "move_right": {"deadzone": 0.5, "events": [{"key": "D"}]},
}

_TRACE = {
    "fps": 60,
    "events": [
        {"frame": 0, "action": "move_right", "pressed": True, "strength": 1.0},
        {"frame": 30, "action": "move_right", "pressed": False, "strength": 1.0},
    ],
}

_APPLY = [
    {"op": "node.create", "parent": ".", "name": "Watcher", "type": "CharacterBody2D"},
    {"op": "script.attach", "path": "Watcher", "script": "res://player.gd", "props": {}},
    {"op": "node.create", "parent": ".", "name": "Hitbox", "type": "Area2D"},
    {"op": "signal.connect", "from": "Hitbox", "signal": "body_entered", "to": "Watcher", "method": "_on_hit"},
]

_CANARIES = ("canary.gd", "addons/canary/canary.gd")


def _strict_settings() -> str:
    lines = [_SETTINGS.strip("\n")]
    for name in _TYPE2:
        lines.append(f"gdscript/warnings/{name}=2")
    lines.append(f'gdscript/warnings/directory_rules={{ "res://addons": {_ADDONS_INCLUDE} }}')
    return "\n".join(lines) + "\n"


def _addons_included(text: str) -> bool:
    at = text.find("directory_rules")
    if at < 0:
        return False
    chunk = "".join(text[at:at + 500].split())
    return f'"res://addons":{_ADDONS_INCLUDE}' in chunk


def _blob(result: dict | None) -> str:
    if not isinstance(result, dict):
        return ""
    parts = [str(result.get("problems")), str(result.get("godot_errors")), str(result.get("godot_warnings"))]
    return "\n".join(parts)


def _write_canaries(project) -> None:
    for rel in _CANARIES:
        path = project.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_CANARY, encoding="utf-8", newline="\n")


def _delete_canaries(project) -> None:
    for rel in _CANARIES:
        path = project.root / rel
        if path.is_file():
            path.unlink()
        uid = path.parent / (path.name + ".uid")
        if uid.is_file():
            uid.unlink()


def _canary(ctx: Ctx, project) -> None:
    text = (project.root / "project.godot").read_text(encoding="utf-8")
    ctx.check(
        "project sets every type-2 warning and includes res://addons",
        all(f"gdscript/warnings/{name}=2" for name in _TYPE2)
        and "gdscript/warnings/enable=true" in text
        and _addons_included(text),
        warnings=len(_TYPE2),
    )
    _write_canaries(project)
    dirty = ctx.guard("canary check", lambda: S.check(project))
    blob = _blob(dirty if isinstance(dirty, dict) else None)
    ctx.check(
        "untyped res://canary.gd and res://addons/canary/canary.gd are errors",
        isinstance(dirty, dict)
        and dirty.get("clean") is False
        and "res://canary.gd" in blob
        and "res://addons/canary/canary.gd" in blob,
        blob=blob[:900],
    )
    _delete_canaries(project)
    clean = ctx.guard("check after deleting canaries", lambda: S.check(project))
    ctx.check(
        "check clean after canaries are removed",
        isinstance(clean, dict) and clean.get("clean") is True and not clean.get("godot_errors") and not clean.get("godot_warnings"),
        problems=None if not isinstance(clean, dict) else clean.get("problems"),
        errors=None if not isinstance(clean, dict) else (clean.get("godot_errors") or [])[:8],
        warnings=None if not isinstance(clean, dict) else (clean.get("godot_warnings") or [])[:8],
    )


def _scenes(ctx: Ctx, project) -> None:
    created = ctx.guard(
        "scene new",
        lambda: S.apply(
            project,
            "res://extra.tscn",
            [],
            "strict.new.1",
            create={"root_type": "Node2D", "root_name": "Extra", "props": {}},
        ),
    )
    ctx.check(
        "scene new committed",
        isinstance(created, dict) and created.get("status") == "COMMITTED" and created.get("created") is True and created.get("ok") is True,
        status=None if not isinstance(created, dict) else created.get("status"),
    )
    applied = ctx.guard(
        "scene apply",
        lambda: S.apply(project, "res://main.tscn", _APPLY, "strict.apply.1"),
    )
    ctx.check(
        "scene apply committed",
        isinstance(applied, dict) and applied.get("status") == "COMMITTED" and applied.get("readback") == "FRESH_PROCESS_MATCH",
        status=None if not isinstance(applied, dict) else applied.get("status"),
        readback=None if not isinstance(applied, dict) else applied.get("readback"),
    )
    view = ctx.guard(
        "scene inspect --sha",
        lambda: S._cmd_inspect(argparse.Namespace(project=project.project_id, scene="res://main.tscn", sha=True)),
    )
    sha = "" if not isinstance(view, dict) else str(view.get("sha256") or "")
    nodes = {} if not isinstance(view, dict) else {n.get("path"): n for n in view.get("nodes") or []}
    connections = [] if not isinstance(view, dict) else view.get("connections") or []
    ctx.check(
        "scene inspect --sha matches the file and shows the applied nodes",
        isinstance(view, dict)
        and view.get("ok") is True
        and len(sha) == 64
        and sha == C.sha256_file(project.res_to_path("res://main.tscn"))
        and "Watcher" in nodes
        and "Hitbox" in nodes
        and any(c.get("signal") == "body_entered" and c.get("method") == "_on_hit" for c in connections),
        sha=sha,
        paths=sorted(nodes),
    )
    undone = ctx.guard("scene undo", lambda: S.undo(project, "strict.apply.1"))
    ctx.check(
        "scene undo committed",
        isinstance(undone, dict) and undone.get("ok") is True and undone.get("status") == "UNDONE",
        status=None if not isinstance(undone, dict) else undone.get("status"),
    )


def _runtime(ctx: Ctx, project) -> None:
    receipt = ctx.guard("input set", lambda: IM.set_actions(project, _ACTIONS, "strict.input.1"))
    names = set()
    if isinstance(receipt, dict):
        names = {item.get("name") for item in receipt.get("actions") or []}
    ctx.check(
        "input set committed",
        isinstance(receipt, dict)
        and receipt.get("status") == "COMMITTED"
        and receipt.get("readback") == "FRESH_PROCESS_MATCH"
        and {"move_left", "move_right"} <= names,
        status=None if not isinstance(receipt, dict) else receipt.get("status"),
        names=sorted(names),
    )
    listed = ctx.guard("input list", lambda: IM.list_actions(project))
    listed_names = set()
    if isinstance(listed, dict):
        listed_names = {item.get("name") for item in listed.get("actions") or []}
    ctx.check(
        "input list shows the actions",
        isinstance(listed, dict) and listed.get("ok") is True and listed_names == {"move_left", "move_right"},
        names=sorted(listed_names),
    )
    played = ctx.guard(
        "play",
        lambda: Play.play(
            project,
            scene="res://main.tscn",
            trace=_TRACE,
            frames=30,
            seed=1,
            observe="Player:position",
            every=30,
        ),
    )
    digest = None if not isinstance(played, dict) else played.get("trace_hash")
    ctx.check(
        "play 30 frames ok",
        isinstance(played, dict)
        and played.get("ok") is True
        and played.get("frames") == 30
        and isinstance(digest, str)
        and len(digest) == 64
        and played.get("observations"),
        frames=None if not isinstance(played, dict) else played.get("frames"),
        errors=None if not isinstance(played, dict) else (played.get("errors") or [])[:6],
        hash=digest,
    )
    boxed = ctx.guard(
        "bot",
        lambda: B.run_bot(
            project,
            scene="res://main.tscn",
            frames=120,
            seed=1,
            actions="move_left,move_right",
            track="Player",
        ),
    )
    bot_hash = None if not isinstance(boxed, dict) else boxed.get("trace_hash")
    ctx.check(
        "bot 120 frames ok",
        isinstance(boxed, dict)
        and boxed.get("ok") is True
        and boxed.get("crashed") is False
        and boxed.get("frames") == 120
        and isinstance(bot_hash, str)
        and len(bot_hash) == 64,
        errors=None if not isinstance(boxed, dict) else (boxed.get("errors") or [])[:6],
        hash=bot_hash,
        coverage=None if not isinstance(boxed, dict) else boxed.get("coverage"),
    )
    image = ctx.root / "strict-shot.png"
    captured = ctx.guard(
        "shot",
        lambda: shot.capture(
            project,
            image,
            scene="res://main.tscn",
            frames=2,
            resolution=(160, 90),
            expect=["Label"],
        ),
    )
    presence = [] if not isinstance(captured, dict) else captured.get("presence") or []
    label = next((row for row in presence if row.get("path") == "Label"), {})
    ctx.check(
        "shot windowed ok",
        isinstance(captured, dict)
        and captured.get("ok") is True
        and captured.get("status") == "CAPTURED"
        and label.get("exists") is True
        and image.is_file(),
        status=None if not isinstance(captured, dict) else captured.get("status"),
        errors=None if not isinstance(captured, dict) else (captured.get("errors") or [])[:6],
        presence=label,
    )
    report = ctx.guard(
        "perf",
        lambda: Perf.run_report(
            project,
            scene="res://main.tscn",
            frames=60,
            warmup=10,
            resolution="320x180",
        ),
    )
    ctx.check(
        "perf 60 frames ok",
        isinstance(report, dict) and report.get("ok") is True and report.get("frames") == 60 and report.get("warmup") == 10,
        fps=None if not isinstance(report, dict) else report.get("fps"),
        violations=None if not isinstance(report, dict) else report.get("violations"),
        errors=None if not isinstance(report, dict) else ((report.get("process") or {}).get("errors") or [])[:6],
    )


def _kits(ctx: Ctx, project) -> None:
    for name in ("save", "settings", "rebind", "pause", "audio"):
        receipt = ctx.guard(
            f"kit add {name}",
            lambda name=name: K.add_kit(project, name, f"strict.add.{name}"),
        )
        ctx.check(
            f"kit {name} committed",
            isinstance(receipt, dict) and receipt.get("status") == "COMMITTED" and receipt.get("readback") == "FRESH_PROCESS_MATCH",
            status=None if not isinstance(receipt, dict) else receipt.get("status"),
        )
    text = (project.root / "project.godot").read_text(encoding="utf-8")
    ctx.check("addons stay included after kit add", _addons_included(text), excerpt=text[text.find("directory_rules"):text.find("directory_rules") + 180])
    clean = ctx.guard("check with kits", lambda: S.check(project))
    ctx.check(
        "check clean with kits installed",
        isinstance(clean, dict) and clean.get("clean") is True and not clean.get("godot_errors") and not clean.get("godot_warnings"),
        problems=None if not isinstance(clean, dict) else clean.get("problems"),
        errors=None if not isinstance(clean, dict) else (clean.get("godot_errors") or [])[:8],
        warnings=None if not isinstance(clean, dict) else (clean.get("godot_warnings") or [])[:8],
    )


def run(ctx: Ctx) -> None:
    project = ctx.project(
        "strict",
        {"player.gd": _PLAYER, "main.tscn": _MAIN},
        main_scene="res://main.tscn",
        settings=_strict_settings(),
    )
    _canary(ctx, project)
    _scenes(ctx, project)
    _runtime(ctx, project)
    _kits(ctx, project)
