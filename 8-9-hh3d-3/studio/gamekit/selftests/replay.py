"""Quick native regressions for save isolation and nested scene creation."""

from pathlib import Path

from .. import play as P
from .. import scene as S
from . import Ctx


_SCRIPT = '''extends Node

var visits: int = 0

func _ready() -> void:
	if FileAccess.file_exists("user://visits.txt"):
		visits = FileAccess.get_file_as_string("user://visits.txt").to_int()
	visits += 1
	var file: FileAccess = FileAccess.open("user://visits.txt", FileAccess.WRITE)
	file.store_string(str(visits))
	file.close()
'''

_SCENE = '''[gd_scene load_steps=2 format=3]
[ext_resource type="Script" path="res://visits.gd" id="1"]
[node name="World" type="Node"]
script = ExtResource("1")
'''


def run(ctx: Ctx) -> None:
    project = ctx.project("replay", {"visits.gd": _SCRIPT, "main.tscn": _SCENE}, main_scene="res://main.tscn")
    settings = project.root / "project.godot"
    settings.write_text(settings.read_text(encoding="utf-8") +
                        'config/use_custom_user_dir=true\nconfig/custom_user_dir_name="HH replay custom"\n', encoding="utf-8")
    before = settings.read_bytes()
    first = P.play(project, frames=4, observe=".:visits", seed=17)
    second = P.play(project, frames=4, observe=".:visits", seed=17)
    ctx.check("both save-writing runs exit cleanly", first.get("ok") is True and second.get("ok") is True,
              errors=[first.get("errors"), second.get("errors")])
    ctx.check("same input and fresh save state have the same hash", first.get("trace_hash") is not None
              and first.get("trace_hash") == second.get("trace_hash"))
    ctx.check("each run starts from an empty save profile", all(
        row["values"].get(".:visits") == 1 for result in (first, second) for row in result["observations"]))
    ctx.check("Godot confirms a different user directory per run", first.get("user_data_isolated") is True
              and second.get("user_data_isolated") is True and first.get("user_data_dir") != second.get("user_data_dir"))
    ctx.check("run profiles are removed after exit", all(result.get("user_data_cleaned") is True
              and not Path(result["user_data_dir"]).exists() for result in (first, second)))
    ctx.check("project settings unchanged by isolation", settings.read_bytes() == before)
    created = S.apply(project, "res://levels/intro/new.tscn", [], "replay.scene.nested.1",
                      create={"root_type": "Node3D", "root_name": "Intro"})
    ctx.check("scene new creates nested parents with fresh readback", created.get("readback") == "FRESH_PROCESS_MATCH"
              and (project.root / "levels/intro/new.tscn").is_file())

