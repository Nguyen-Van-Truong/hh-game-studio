"""Short native canary: input/kit mutations preserve real project settings."""

from .. import common as C
from .. import inputmap as IM
from .. import kit as K
from .. import project_config as PC
from . import Ctx

_SETTINGS = '''[display]
window/size/viewport_width=1280
window/size/viewport_height=720
window/stretch/mode="canvas_items"

[internationalization]
locale/fallback="vi"

[physics]
common/physics_ticks_per_second=60

[autoload]
HHState="*res://state.gd"

[hh_game]
custom/data={
"title": "Làng Việt",
"coords": [1, 2, 3]
}
'''

_PROBE = '''extends SceneTree
func _initialize() -> void:
\tvar keys: Array[String] = ["display/window/size/viewport_width", "display/window/size/viewport_height", "display/window/stretch/mode", "internationalization/locale/fallback", "physics/common/physics_ticks_per_second", "autoload/HHState", "hh_game/custom/data"]
\tvar values: Dictionary = {}
\tfor key: String in keys:
\t\tvalues[key] = ProjectSettings.get_setting(key)
\tprint("HHGK_RESULT " + JSON.stringify({"ok": true, "values": values}))
\tquit(0)
'''


def run(ctx: Ctx) -> None:
    project = ctx.project("config", {"state.gd": "extends Node\n", "probe.gd": _PROBE}, settings=_SETTINGS)
    path = project.root / "project.godot"
    before = path.read_bytes()
    expected = {
        "display/window/size/viewport_width": 1280,
        "display/window/size/viewport_height": 720,
        "display/window/stretch/mode": "canvas_items",
        "internationalization/locale/fallback": "vi",
        "physics/common/physics_ticks_per_second": 60,
        "autoload/HHState": "*res://state.gd",
        "hh_game/custom/data": {"title": "Làng Việt", "coords": [1, 2, 3]},
    }
    writes = {"input/jump", "input/move", "input/ui_accept", "autoload/HHSave", K.AUDIO_SETTING}
    commands = [
        ("input add", lambda: IM.set_actions(project, {"jump": {"events": [{"key": "Space"}]}}, "config.input.1")),
        ("kit save add", lambda: K.add_kit(project, "save", "config.kit.save.add")),
        ("kit audio add", lambda: K.add_kit(project, "audio", "config.kit.audio.add")),
        ("input replace", lambda: IM.set_actions(project, {"move": {"events": [{"key": "A"}]}, "ui_accept": {"events": [{"key": "J"}]}}, "config.input.2", replace=True)),
        ("kit save remove", lambda: K.remove_kit(project, "save", "config.kit.save.remove")),
        ("kit audio remove", lambda: K.remove_kit(project, "audio", "config.kit.audio.remove")),
    ]
    for name, operation in commands:
        receipt = ctx.guard(name, operation)
        ctx.check(name + " committed", isinstance(receipt, dict) and receipt.get("status") == "COMMITTED", receipt=receipt)
        ctx.check(name + " preserved source", PC.preserved_entries(before, writes) == PC.preserved_entries(path.read_bytes(), writes))
    native = ctx.guard("fresh native settings probe", lambda: C.run_godot(project.root, project.root / "probe.gd", timeout=30))
    result = native.result if isinstance(native, C.ProcessRun) else None
    ctx.check("fresh process reads every preserved setting", isinstance(native, C.ProcessRun) and native.exit_code == 0 and not native.errors and not native.warnings and isinstance(result, dict) and result.get("values") == expected, result=result, process=native.summary() if isinstance(native, C.ProcessRun) else None)
    actions = IM.list_actions(project, include_all=True).get("actions", [])
    by_name = {item["name"]: item for item in actions}
    ctx.check("replace removed only old action and stored explicit UI binding", "jump" not in by_name and "move" in by_name and by_name.get("ui_accept", {}).get("events") == [{"key": "J"}])
    ctx.check("audio removal clears project pointer", b"buses/default_bus_layout=" not in path.read_bytes())
