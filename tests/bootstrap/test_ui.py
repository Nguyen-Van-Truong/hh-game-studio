#!/usr/bin/env python3
"""R5-WP4: UI/Control/theme/layout/accessibility.

Does not tick the 20-8 plan. G2 is not involved. Pin missing is a hard FAIL.
No skip-PASS. No dummy screenshot PNG. Do not paper-ACK play.start.
Do not raw-edit .tscn/.tres bytes. Plugin is the only writer.

Verify (encoded here; this file is the official harness):
  - HUD/menu/dialog/settings scene via plugin (node.add + ui.* + property.set)
  - Theme + StyleBoxFlat + SystemFont assigned and read back
  - VBox/HBox/Grid/Margin layout + three parent sizes, no overlap/cutoff
  - long + localized text overflow structured check
  - focus neighbor graph + find_next_valid_focus
  - accessibility_name readback
  - one UndoRedo stroke, Agent: prefix
  - scene.save + reopen hash
  - screenshots=SKIP

Honest Alternatives named here:
  - screenshots=SKIP (R6)
  - editor grab_focus may not keep has_focus — neighbor graph +
    find_next_valid_focus is the Alternative
  - play.start is not paper-ACK'd
  - SystemFont if no licensed FontFile
  - ProjectSettings window size ≠ editor viewport

Generated plugin-validator.json / mcp-tools.json are coordinator-owned
(`npm run generate`). This WP registers verbs in actions.json + the live
TypeScript catalog. No extra codegen pipeline.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hh_agent_allow import hh_agent_only_addon_errors
import test_plugin_router as plug
import test_scene_lifecycle as life
import test_session as sess

BRIDGE = REPO_ROOT / "bridge"
PLAN = REPO_ROOT / "zdocs" / "20-8-godot-agent-autopilot-plan.txt"
PLUGIN_PROJECT = REPO_ROOT / "godot" / "plugin-project"
ADDON = PLUGIN_PROJECT / "addons" / "hh_agent"
ACTIONS_JSON = ADDON / "core" / "actions.json"
PINNED_VERSION = plug.PINNED_VERSION
TEMP_DIR = PLUGIN_PROJECT / "r5w4"
VENDOR_NEEDLES = plug.VENDOR_NEEDLES
SCHEMA = "hh-godot-variant/1"
SCREENSHOTS = "SKIP"
SIZE_EXPAND_FILL = 3
FOCUS_ALL = 2
UI_MUTATES = ("ui.control", "ui.theme", "ui.layout", "ui.anchor")
UI_VERBS = ("control", "theme", "layout", "anchor", "focus", "accessibility")
VIEWPORTS = ((1280, 720), (1920, 1080), (1920, 1200))
LONG_TEXT = "Settings overflow fixture — " + ("lorem ipsum dolor sit amet " * 12)
LOCAL_TEXT = "Cài đặt ngôn ngữ và trợ năng: văn bản dài để kiểm tra tràn khung hiển thị."


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def plan_errors(text: str) -> list[str]:
    """Keep R5-WP4 [ ]; while unticked require CURRENT_VALID_WP=R5-WP4."""
    errors: list[str] = []
    current = ""
    wp4 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R5-WP4\b", stripped):
            wp4 = stripped
    if wp4 is None:
        return ["plan missing R5-WP4 heading"]
    ticked = bool(re.search(r"\[x\]", wp4, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp4:
            errors.append("R5-WP4 heading must keep [ ] until coordinator tick")
        if current != "R5-WP4":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R5-WP4 while WP4 is unticked)")
    elif not re.match(r"^R5-WP([5-9]|\d{2,})$|^R[6-9]-WP\d+$|^RX-WP\d+$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R5-WP5+ after R5-WP4 tick)")
    return errors


def cleanup_temp() -> None:
    if TEMP_DIR.is_dir():
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
    agent = PLUGIN_PROJECT / ".hh-agent"
    for name in ("file-leases.json", "writer.lock"):
        lock = agent / name
        if lock.is_file():
            try:
                lock.unlink()
            except OSError:
                pass


def variant(typ: str, value) -> dict:
    return {"schema": SCHEMA, "type": typ, "value": value}


def color(r: float, g: float, b: float, a: float = 1.0) -> dict:
    return variant("Color", {"r": r, "g": g, "b": b, "a": a})


def rel_lum(c: dict) -> float:
    def chan(v: float) -> float:
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    return 0.2126 * chan(float(c.get("r", 0))) + 0.7152 * chan(float(c.get("g", 0))) + 0.0722 * chan(
        float(c.get("b", 0))
    )


def contrast_ratio(fg: dict, bg: dict) -> float:
    L1 = rel_lum(fg)
    L2 = rel_lum(bg)
    lighter = max(L1, L2)
    darker = min(L1, L2)
    return (lighter + 0.05) / (darker + 0.05)


def plugin_godot_busy() -> bool:
    """True when an existing Godot process already holds plugin-project."""
    needle = "plugin-project"
    if os.name == "nt":
        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    "Get-CimInstance Win32_Process | "
                    "Where-Object { $_.Name -match 'Godot' } | "
                    "Select-Object -ExpandProperty CommandLine"
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
        blob = (proc.stdout or "") + (proc.stderr or "")
        return needle in blob.replace("\\", "/").lower()
    proc = subprocess.run(["ps", "-ax", "-o", "args="], capture_output=True, text=True, check=False)
    return needle in (proc.stdout or "").lower() and "godot" in (proc.stdout or "").lower()


def src_scan_errors() -> list[str]:
    errors: list[str] = []
    self_text = Path(__file__).read_text(encoding="utf-8")
    if re.search(r"\.write_text\([^\n]*\.(?:tscn|tres|res|png)", self_text):
        errors.append("official test writes a .tscn/.tres/.png path directly")
    if re.search(r"\.write_bytes\(|Image\.new\b", self_text):
        errors.append("official test must not bless dummy screenshot PNGs")
    if "screenshots=SKIP" not in self_text and 'SCREENSHOTS = "SKIP"' not in self_text:
        errors.append("official test must record screenshots=SKIP")
    if "Alternative" not in self_text:
        errors.append("official test must record focus/SystemFont/screenshot Alternatives honestly")
    if "play.start" in self_text and "paper-ACK" not in self_text:
        errors.append("official test must refuse to paper-ACK play.start")
    if "find_next_valid_focus" not in self_text:
        errors.append("official test must encode find_next_valid_focus")
    if "accessibility_name" not in self_text:
        errors.append("official test must encode accessibility_name")
    if "SystemFont" not in self_text:
        errors.append("official test must name SystemFont as the missing-FontFile Alternative")
    if "ProjectSettings" not in self_text:
        errors.append("official test must name ProjectSettings window size Alternative")
    if "g2_" + "signed" in self_text or "G2" + " VISIBLE" in self_text:
        errors.append("official test must stay independent of the visible gate")
    if "res://" + "snake" in self_text or "kho" + "-bi-an" in self_text:
        errors.append("official test must stay independent of demo game trees")
    if "skip-PASS" not in self_text and "No skip-PASS" not in self_text:
        errors.append("official test must refuse skip-PASS")
    if "DisplayServer." + "window_set_size" in self_text:
        errors.append("official test must not treat DisplayServer window resize as the viewport matrix")

    router = (ADDON / "core" / "hh_router.gd").read_text(encoding="utf-8")
    if "hh_ui_adapter" not in router:
        errors.append("router must dispatch through hh_ui_adapter")
    if "godot.ui" not in router:
        errors.append("router must name godot.ui")

    adapter = ADDON / "core" / "hh_ui_adapter.gd"
    if not adapter.is_file():
        errors.append("missing hh_ui_adapter.gd")
    else:
        text = adapter.read_text(encoding="utf-8")
        for needle in (
            "set_anchors_and_offsets_preset",
            "queue_sort",
            "get_global_rect",
            "gui_get_focus_owner",
            "accessibility_name",
            "UNDO_ACTION_PREFIX",
            "create_action",
            "PRESET_TOP_LEFT",
            "PRESET_CENTER",
            "PRESET_FULL_RECT",
            "PRESET_BOTTOM_WIDE",
            "add_theme_constant_override",
            "get_combined_minimum_size",
        ):
            if needle not in text:
                errors.append(f"ui adapter must use {needle}")
        if "set_stylebox" not in text and "add_theme_stylebox_override" not in text:
            errors.append("ui adapter must use Theme.set_stylebox or add_theme_stylebox_override")
        if re.search(r"(?<!gui_)get_focus_owner", text):
            errors.append("ui adapter must not call the removed Control focus-owner getter")
        if "rect_min_size" in text:
            errors.append("ui adapter must not use Godot 3 rect_min_size")
        if "Vector2(32, 32)" in text:
            errors.append("ui adapter must not invent a 32px box")
        if "get_start_node" in text:
            errors.append("ui adapter must not call removed start-node APIs")
        if re.search(r"\bcallv\b", text) or "Object.call" in text or "evaluate_expression" in text:
            errors.append("ui adapter has a generic invoke path")
        if "ThemeDB.get_default_theme" in text:
            errors.append("ui adapter must not mutate the stock ThemeDB default theme")
        if "DisplayServer." + "window_set_size" in text:
            errors.append("ui adapter must not use DisplayServer window resize as the matrix")
        if "plugin-validator" not in text and "coordinator" not in text:
            errors.append("ui adapter must note coordinator-owned generated catalog")
        if "Alternative" not in text:
            errors.append("ui adapter must label grab_focus / SystemFont Alternatives honestly")

    reads = (ADDON / "core" / "hh_read_adapters.gd").read_text(encoding="utf-8")
    if "focus owner getter not proven" in reads:
        errors.append("ui.focus stub must be replaced with engine readback")
    if "accessibility_name" not in reads and "hh_ui_adapter" not in reads:
        errors.append("read adapter must keep a real ui.accessibility getter")
    if re.search(r"(?<!gui_)get_focus_owner", reads):
        errors.append("read adapter must not call the removed Control focus-owner getter")

    overlay = (ADDON / "ui" / "overlay" / "hh_overlay.gd").read_text(encoding="utf-8")
    if "godot.ui" not in overlay:
        errors.append("overlay must treat godot.ui as presentable")
    if "get_global_rect" not in overlay and "engine_world_rect" not in overlay:
        errors.append("overlay must use engine get_global_rect, invented_box=false")

    if not ACTIONS_JSON.is_file():
        errors.append("missing actions.json")
    else:
        catalog = json.loads(ACTIONS_JSON.read_text(encoding="utf-8"))
        actions = catalog.get("actions") if isinstance(catalog.get("actions"), dict) else {}
        for action_id, method, verb in (
            ("ui.control", "godot.ui", "control"),
            ("ui.theme", "godot.ui", "theme"),
            ("ui.layout", "godot.ui", "layout"),
            ("ui.anchor", "godot.ui", "anchor"),
            ("ui.focus", "godot.ui", "focus"),
            ("ui.accessibility", "godot.ui", "accessibility"),
        ):
            spec = actions.get(action_id) if isinstance(actions.get(action_id), dict) else {}
            if spec.get("method") != method or spec.get("verb") != verb:
                errors.append(f"actions.json missing {action_id}")

    lifecycle = (BRIDGE / "src" / "ledger" / "scene_lifecycle.ts").read_text(encoding="utf-8")
    if "UI_APPLY" not in lifecycle or "isUiApply" not in lifecycle:
        errors.append("scene_lifecycle must export UI_APPLY / isUiApply")
    if "isUiApply(actionId)" not in lifecycle:
        errors.append("isProvenEditorApply must include isUiApply")
    for action_id in UI_MUTATES:
        if action_id not in lifecycle:
            errors.append(f"isProvenEditorApply must list {action_id}")

    execute = (BRIDGE / "src" / "ledger" / "execute.ts").read_text(encoding="utf-8")
    if "function uiApplyOk" not in execute:
        errors.append("execute.ts must postcondition-check ui apply")
    if "const uiFail = uiApplyOk" not in execute:
        errors.append("execute.ts must call uiApplyOk from applyMutateOnce")
    if '"ui"' not in execute:
        errors.append("execute.ts after_summary must use kind ui")

    resources = (BRIDGE / "src" / "resources" / "mcp_resources.ts").read_text(encoding="utf-8")
    if "isUiApply(def.id)" not in resources or '"ui"' not in resources:
        errors.append("mcp_resources.ts must label ui apply as the ui adapter")

    validator = json.loads((BRIDGE / "generated" / "plugin-validator.json").read_text(encoding="utf-8"))
    validator_actions = validator.get("actions") if isinstance(validator.get("actions"), dict) else {}
    for action_id, method, verb in (
        ("ui.control", "godot.ui", "control"),
        ("ui.theme", "godot.ui", "theme"),
        ("ui.layout", "godot.ui", "layout"),
        ("ui.anchor", "godot.ui", "anchor"),
        ("ui.focus", "godot.ui", "focus"),
        ("ui.accessibility", "godot.ui", "accessibility"),
    ):
        spec = validator_actions.get(action_id) if isinstance(validator_actions.get(action_id), dict) else {}
        if spec.get("method") != method or spec.get("verb") != verb:
            errors.append(f"plugin-validator.json missing dotted id {action_id}")

    mcp_tools = json.loads((BRIDGE / "generated" / "mcp-tools.json").read_text(encoding="utf-8"))
    tool_enums: dict[str, list[str]] = {}
    for tool in mcp_tools.get("tools") if isinstance(mcp_tools.get("tools"), list) else []:
        if not isinstance(tool, dict):
            continue
        name = str(tool.get("name") or "")
        schema = tool.get("inputSchema") if isinstance(tool.get("inputSchema"), dict) else {}
        props = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        action = props.get("action") if isinstance(props.get("action"), dict) else {}
        enum = action.get("enum") if isinstance(action.get("enum"), list) else []
        tool_enums[name] = [str(item) for item in enum]
    domain = tool_enums.get("godot.ui", [])
    for verb in UI_VERBS:
        if verb not in domain:
            errors.append(f"mcp-tools.json godot.ui must enum {verb}")
    if "godot.ui" not in tool_enums:
        errors.append("mcp-tools.json must expose godot.ui as a domain tool")

    for path in (BRIDGE / "src").rglob("*.ts"):
        blob = path.read_text(encoding="utf-8", errors="replace")
        posix = rel(path)
        for needle in VENDOR_NEEDLES:
            if needle in blob:
                errors.append(f"{posix} contains vendor needle {needle!r}")
                break
        if re.search(r"\bcallv\b", blob) or "evaluate_expression" in blob:
            errors.append(f"{posix} has a generic invoke path")
    return errors


def mcp_call(proc: subprocess.Popen[str], req_id: int, name: str, arguments: dict, timeout: float = 45.0) -> dict:
    return life.mcp_call(proc, req_id, name, arguments, timeout)


def body_of(resp: dict) -> dict:
    return life.body_of(resp)


def tool_call(
    proc: subprocess.Popen[str],
    req_id: int,
    method: str,
    action: str,
    params: dict,
    timeout: float = 45.0,
) -> tuple[int, dict]:
    cid = life.new_ulid()
    resp = mcp_call(proc, req_id, method, {"action": action, "params": params, "command_id": cid}, timeout)
    return req_id + 1, body_of(resp)


def ack_ok(body: dict, errors: list[str], verb: str) -> bool:
    if body.get("ok") is not True:
        errors.append(f"{verb} must ACK: {body}")
        return False
    post = body.get("postcondition") or {}
    if post.get("verified") is not True or not post.get("checks"):
        errors.append(f"{verb} paper postcondition: {body}")
        return False
    return True


def rects_overlap(rows: list) -> bool:
    parsed: list[tuple[float, float, float, float]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        r = row.get("rect") if isinstance(row.get("rect"), dict) else {}
        parsed.append((float(r.get("x", 0)), float(r.get("y", 0)), float(r.get("w", 0)), float(r.get("h", 0))))
    i = 0
    while i < len(parsed):
        ax, ay, aw, ah = parsed[i]
        j = i + 1
        while j < len(parsed):
            bx, by, bw, bh = parsed[j]
            ix = max(ax, bx)
            iy = max(ay, by)
            iw = min(ax + aw, bx + bw) - ix
            ih = min(ay + ah, by + bh) - iy
            if iw > 0.5 and ih > 0.5:
                return True
            j += 1
        i += 1
    return False


def live_errors(exe: Path) -> list[str]:
    errors: list[str] = []
    if plugin_godot_busy():
        errors.append("LIVE_UNRUN: Godot already open on plugin-project (exclusive; no second instance)")
        return errors
    cleanup_temp()
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    proc: subprocess.Popen[str] | None = None
    godot: subprocess.Popen[str] | None = None
    desc_path: Path | None = None
    secret = ""
    err_lines: list[str] = []
    godot_lines: list[str] = []
    scene = "res://r5w4/ui.tscn"
    theme_p = "res://r5w4/theme.tres"
    box_p = "res://r5w4/panel.tres"
    font_p = "res://r5w4/font.tres"
    req_id = 2
    # Honest Alternative: SystemFont if no licensed FontFile.
    # editor grab_focus may not keep has_focus — neighbor graph is the Alternative.
    # screenshots=SKIP — do not write a fake PNG. Do not paper-ACK play.start.
    # ProjectSettings window size ≠ editor viewport. Do not resize the OS window and claim that is the matrix.
    _screenshots = SCREENSHOTS
    try:
        proc, desc_path, secret, err_lines = life.start_sidecar()
        godot, godot_lines = life.start_godot(exe)
        req_id, hello, last = life.wait_hello(proc, godot, req_id)
        if not hello:
            errors.append(
                "live plugin hello/noop failed: "
                f"{sess.redact(json.dumps(last), secret)}; godot={''.join(godot_lines)[-1500:]}"
            )
            return errors

        req_id, created = tool_call(proc, req_id, "godot.scene", "create", {"path": scene, "root_class": "Control"})
        if not ack_ok(created, errors, "scene.create"):
            return errors

        for class_name, parent, name in (
            ("VBoxContainer", ".", "MainBox"),
            ("HBoxContainer", "MainBox", "HUD"),
            ("Label", "MainBox/HUD", "ScoreLabel"),
            ("Label", "MainBox/HUD", "HealthLabel"),
            ("VBoxContainer", "MainBox", "Menu"),
            ("Button", "MainBox/Menu", "StartButton"),
            ("Button", "MainBox/Menu", "OptionsButton"),
            ("Button", "MainBox/Menu", "QuitButton"),
            ("MarginContainer", "MainBox", "Dialog"),
            ("VBoxContainer", "MainBox/Dialog", "DialogBox"),
            ("Label", "MainBox/Dialog/DialogBox", "DialogTitle"),
            ("Label", "MainBox/Dialog/DialogBox", "DialogBody"),
            ("Button", "MainBox/Dialog/DialogBox", "DialogOk"),
            ("GridContainer", "MainBox", "Settings"),
            ("Label", "MainBox/Settings", "LangLabel"),
            ("Label", "MainBox/Settings", "LangValue"),
            ("Label", "MainBox/Settings", "A11yLabel"),
            ("Label", "MainBox/Settings", "A11yValue"),
        ):
            req_id, added = tool_call(
                proc,
                req_id,
                "godot.node",
                "add",
                {"scene": scene, "parent": parent, "class_name": class_name, "name": name},
            )
            if not ack_ok(added, errors, f"node.add {name} {class_name}"):
                return errors

        for node_path, text in (
            ("MainBox/HUD/ScoreLabel", "Score 0"),
            ("MainBox/HUD/HealthLabel", "HP 3"),
            ("MainBox/Menu/StartButton", "Start"),
            ("MainBox/Menu/OptionsButton", "Options"),
            ("MainBox/Menu/QuitButton", "Quit"),
            ("MainBox/Dialog/DialogBox/DialogTitle", "Confirm"),
            ("MainBox/Dialog/DialogBox/DialogBody", "Apply these settings?"),
            ("MainBox/Dialog/DialogBox/DialogOk", "OK"),
            ("MainBox/Settings/LangLabel", "Language"),
            ("MainBox/Settings/LangValue", "Tiếng Việt"),
            ("MainBox/Settings/A11yLabel", "Accessibility"),
            ("MainBox/Settings/A11yValue", "On"),
        ):
            req_id, set_text = tool_call(
                proc,
                req_id,
                "godot.property",
                "set",
                {"scene": scene, "node_path": node_path, "property": "text", "value": variant("string", text)},
            )
            if not ack_ok(set_text, errors, f"property.set {node_path}.text"):
                return errors

        req_id, clip = tool_call(
            proc,
            req_id,
            "godot.property",
            "set",
            {
                "scene": scene,
                "node_path": "MainBox/Dialog/DialogBox/DialogBody",
                "property": "clip_contents",
                "value": variant("bool", True),
            },
        )
        if not ack_ok(clip, errors, "property.set DialogBody.clip_contents"):
            return errors

        req_id, a11y_name = tool_call(
            proc,
            req_id,
            "godot.property",
            "set",
            {
                "scene": scene,
                "node_path": "MainBox/Menu/StartButton",
                "property": "accessibility_name",
                "value": variant("string", "Start game"),
            },
        )
        if not ack_ok(a11y_name, errors, "property.set accessibility_name"):
            return errors
        req_id, a11y_desc = tool_call(
            proc,
            req_id,
            "godot.property",
            "set",
            {
                "scene": scene,
                "node_path": "MainBox/Menu/StartButton",
                "property": "accessibility_description",
                "value": variant("string", "Begins the match"),
            },
        )
        if not ack_ok(a11y_desc, errors, "property.set accessibility_description"):
            return errors
        req_id, tip = tool_call(
            proc,
            req_id,
            "godot.property",
            "set",
            {
                "scene": scene,
                "node_path": "MainBox/Menu/StartButton",
                "property": "tooltip_text",
                "value": variant("string", "Start hint"),
            },
        )
        if not ack_ok(tip, errors, "property.set tooltip_text"):
            return errors

        for node_path, neighbor, target in (
            ("MainBox/Menu/StartButton", "focus_neighbor_bottom", "../OptionsButton"),
            ("MainBox/Menu/OptionsButton", "focus_neighbor_top", "../StartButton"),
            ("MainBox/Menu/OptionsButton", "focus_neighbor_bottom", "../QuitButton"),
            ("MainBox/Menu/QuitButton", "focus_neighbor_top", "../OptionsButton"),
        ):
            req_id, neigh = tool_call(
                proc,
                req_id,
                "godot.property",
                "set",
                {
                    "scene": scene,
                    "node_path": node_path,
                    "property": neighbor,
                    "value": variant("NodePath", target),
                },
            )
            if not ack_ok(neigh, errors, f"property.set {node_path}.{neighbor}"):
                return errors
        for node_path in ("MainBox/Menu/StartButton", "MainBox/Menu/OptionsButton", "MainBox/Menu/QuitButton"):
            req_id, mode = tool_call(
                proc,
                req_id,
                "godot.property",
                "set",
                {
                    "scene": scene,
                    "node_path": node_path,
                    "property": "focus_mode",
                    "value": variant("int", FOCUS_ALL),
                },
            )
            if not ack_ok(mode, errors, f"property.set {node_path}.focus_mode"):
                return errors

        req_id, theme_created = tool_call(
            proc, req_id, "godot.resource", "create", {"path": theme_p, "class_name": "Theme"}
        )
        if not ack_ok(theme_created, errors, "resource.create Theme"):
            return errors
        req_id, box_created = tool_call(
            proc, req_id, "godot.resource", "create", {"path": box_p, "class_name": "StyleBoxFlat"}
        )
        if not ack_ok(box_created, errors, "resource.create StyleBoxFlat"):
            return errors
        req_id, box_color = tool_call(
            proc,
            req_id,
            "godot.resource",
            "edit",
            {"path": box_p, "property": "bg_color", "value": color(0.08, 0.08, 0.10)},
        )
        if not ack_ok(box_color, errors, "resource.edit StyleBoxFlat.bg_color"):
            return errors
        req_id, font_created = tool_call(
            proc, req_id, "godot.resource", "create", {"path": font_p, "class_name": "SystemFont"}
        )
        if not ack_ok(font_created, errors, "resource.create SystemFont"):
            return errors

        req_id, rooted = tool_call(
            proc,
            req_id,
            "godot.ui",
            "control",
            {
                "scene": scene,
                "node_path": ".",
                "preset": "full_rect",
                "size": {"x": 1280, "y": 720},
                "custom_minimum_size": {"x": 1280, "y": 720},
            },
        )
        if not ack_ok(rooted, errors, "ui.control root full_rect"):
            return errors
        root_after = rooted.get("after") or {}
        if root_after.get("preset") != "full_rect":
            errors.append(f"ui.control preset bind: {root_after}")
        if root_after.get("invented_box") is True:
            errors.append(f"ui.control invented_box: {root_after}")
        if not str(rooted.get("undo_action") or "").startswith("Agent: "):
            errors.append(f"ui.control missing Agent undo: {rooted}")
        for key in (
            "offset_left",
            "offset_top",
            "offset_right",
            "offset_bottom",
            "anchor_left",
            "anchor_top",
            "anchor_right",
            "anchor_bottom",
        ):
            if not isinstance(root_after.get(key), (int, float)):
                errors.append(f"ui.control missing {key}: {root_after}")

        req_id, themed = tool_call(
            proc,
            req_id,
            "godot.ui",
            "theme",
            {
                "scene": scene,
                "node_path": ".",
                "theme": theme_p,
                "add_type": "Label",
                "styleboxes": [{"name": "panel", "theme_type": "Panel", "resource": box_p}],
                "fonts": [{"name": "font", "theme_type": "Label", "resource": font_p}],
                "font_sizes": [{"name": "font_size", "theme_type": "Label", "size": 16}],
                "colors": [{"name": "font_color", "theme_type": "Label", "color": color(0.95, 0.95, 0.96)}],
                "constants": [{"name": "outline_size", "theme_type": "Label", "value": 0}],
                "overrides": [
                    {"kind": "constant", "name": "separation", "value": 8},
                ],
            },
        )
        if not ack_ok(themed, errors, "ui.theme"):
            return errors
        th = themed.get("after") or {}
        if th.get("theme") != theme_p or th.get("theme_assigned") is not True:
            errors.append(f"ui.theme assign bind: {th}")
        if th.get("font_class") != "SystemFont":
            errors.append(f"ui.theme font readback (SystemFont Alternative): {th}")
        if th.get("has_stylebox") is not True or th.get("stylebox_class") != "StyleBoxFlat":
            errors.append(f"ui.theme StyleBoxFlat readback: {th}")
        colors = th.get("colors") if isinstance(th.get("colors"), dict) else {}
        fg = colors.get("fg") if isinstance(colors.get("fg"), dict) else {}
        bg = colors.get("bg") if isinstance(colors.get("bg"), dict) else {}
        if not fg or not bg:
            errors.append(f"ui.theme missing encoded contrast colors: {th}")
        elif contrast_ratio(fg, bg) < 4.5:
            errors.append(f"ui.theme contrast {contrast_ratio(fg, bg):.2f} < 4.5: {colors}")
        if len(str(th.get("disk_hash") or "")) < 16:
            errors.append(f"ui.theme Theme .tres missing disk_hash: {th}")
        if not str(themed.get("undo_action") or "").startswith("Agent: "):
            errors.append(f"ui.theme missing Agent undo: {themed}")

        req_id, boxed = tool_call(
            proc,
            req_id,
            "godot.ui",
            "control",
            {"scene": scene, "node_path": "MainBox", "preset": "full_rect"},
        )
        if not ack_ok(boxed, errors, "ui.control MainBox full_rect"):
            return errors

        first_child_y = None
        baseline_y = None
        baseline_gy = None
        for w, h in VIEWPORTS:
            req_id, sized = tool_call(
                proc,
                req_id,
                "godot.ui",
                "control",
                {
                    "scene": scene,
                    "node_path": ".",
                    "preset": "full_rect",
                    "size": {"x": w, "y": h},
                    "custom_minimum_size": {"x": w, "y": h},
                },
            )
            if not ack_ok(sized, errors, f"ui.control viewport {w}x{h}"):
                return errors
            sz = (sized.get("after") or {}).get("size") if isinstance((sized.get("after") or {}).get("size"), dict) else {}
            if abs(float(sz.get("x", 0)) - w) > 1.0 or abs(float(sz.get("y", 0)) - h) > 1.0:
                errors.append(f"viewport fixture {w}x{h} size readback: {sized}")

            req_id, laid = tool_call(
                proc,
                req_id,
                "godot.ui",
                "layout",
                {
                    "scene": scene,
                    "node_path": "MainBox",
                    "separation": 8,
                    "children": [
                        {
                            "node_path": "MainBox/HUD",
                            "size_flags_horizontal": SIZE_EXPAND_FILL,
                            "size_flags_vertical": 0,
                        },
                        {
                            "node_path": "MainBox/Menu",
                            "size_flags_horizontal": SIZE_EXPAND_FILL,
                            "size_flags_vertical": SIZE_EXPAND_FILL,
                            "stretch_ratio": 1.0,
                        },
                        {
                            "node_path": "MainBox/Dialog",
                            "size_flags_horizontal": SIZE_EXPAND_FILL,
                            "size_flags_vertical": SIZE_EXPAND_FILL,
                            "stretch_ratio": 1.2,
                        },
                        {
                            "node_path": "MainBox/Settings",
                            "size_flags_horizontal": SIZE_EXPAND_FILL,
                            "size_flags_vertical": SIZE_EXPAND_FILL,
                            "stretch_ratio": 1.0,
                        },
                    ],
                },
            )
            if not ack_ok(laid, errors, f"ui.layout MainBox {w}x{h}"):
                return errors
            la = laid.get("after") or {}
            if la.get("queue_sort") is not True:
                errors.append(f"ui.layout missing queue_sort: {la}")
            if la.get("separation") != 8:
                errors.append(f"ui.layout separation bind: {la}")
            if la.get("overlap") is True:
                errors.append(f"ui.layout overlap at {w}x{h}: {la}")
            if la.get("cutoff") is True:
                errors.append(f"ui.layout cutoff at {w}x{h}: {la}")
            rows = la.get("rects") if isinstance(la.get("rects"), list) else []
            if len(rows) < 4:
                errors.append(f"ui.layout missing HUD/menu/dialog/settings rects at {w}x{h}: {la}")
            if rects_overlap(rows):
                errors.append(f"computed sibling rects overlap at {w}x{h}: {rows}")
            if rows and isinstance(rows[0], dict):
                baseline_y = (rows[0].get("rect") or {}).get("y")
                gr0 = rows[0].get("global_rect") if isinstance(rows[0].get("global_rect"), dict) else {}
                baseline_gy = gr0.get("y")
                if first_child_y is None:
                    first_child_y = baseline_y

        req_id, hud_box = tool_call(
            proc, req_id, "godot.ui", "layout", {"scene": scene, "node_path": "MainBox/HUD", "separation": 12}
        )
        if not ack_ok(hud_box, errors, "ui.layout HUD HBox"):
            return errors
        req_id, menu_box = tool_call(
            proc, req_id, "godot.ui", "layout", {"scene": scene, "node_path": "MainBox/Menu", "separation": 6}
        )
        if not ack_ok(menu_box, errors, "ui.layout Menu VBox"):
            return errors
        req_id, grid = tool_call(
            proc,
            req_id,
            "godot.ui",
            "layout",
            {"scene": scene, "node_path": "MainBox/Settings", "separation": 8, "columns": 2},
        )
        if not ack_ok(grid, errors, "ui.layout Settings Grid"):
            return errors
        if (grid.get("after") or {}).get("columns") != 2:
            errors.append(f"ui.layout grid columns: {grid}")
        req_id, margin = tool_call(
            proc,
            req_id,
            "godot.ui",
            "layout",
            {
                "scene": scene,
                "node_path": "MainBox/Dialog",
                "separation": 0,
                "margin_left": 12,
                "margin_top": 8,
                "margin_right": 12,
                "margin_bottom": 8,
                "clip_contents": True,
            },
        )
        if not ack_ok(margin, errors, "ui.layout Dialog Margin"):
            return errors

        req_id, dialog_inner = tool_call(
            proc, req_id, "godot.ui", "layout", {"scene": scene, "node_path": "MainBox/Dialog/DialogBox", "separation": 6}
        )
        if not ack_ok(dialog_inner, errors, "ui.layout DialogBox VBox"):
            return errors
        req_id, added_host = tool_call(
            proc,
            req_id,
            "godot.node",
            "add",
            {"scene": scene, "parent": ".", "class_name": "Control", "name": "OverflowHost"},
        )
        if not ack_ok(added_host, errors, "node.add OverflowHost"):
            return errors
        req_id, ov_host = tool_call(
            proc,
            req_id,
            "godot.ui",
            "control",
            {
                "scene": scene,
                "node_path": "OverflowHost",
                "preset": "top_left",
                "size": {"x": 280, "y": 48},
                "grow_horizontal": 0,
                "grow_vertical": 0,
                "clip_contents": True,
            },
        )
        if not ack_ok(ov_host, errors, "ui.control OverflowHost"):
            return errors
        req_id, added_lab = tool_call(
            proc,
            req_id,
            "godot.node",
            "add",
            {"scene": scene, "parent": "OverflowHost", "class_name": "Label", "name": "OverflowLabel"},
        )
        if not ack_ok(added_lab, errors, "node.add OverflowLabel"):
            return errors
        req_id, wrap = tool_call(
            proc,
            req_id,
            "godot.property",
            "set",
            {
                "scene": scene,
                "node_path": "OverflowHost/OverflowLabel",
                "property": "autowrap_mode",
                "value": variant("int", 2),
            },
        )
        if not ack_ok(wrap, errors, "property.set OverflowLabel.autowrap_mode"):
            return errors
        req_id, ov_label = tool_call(
            proc,
            req_id,
            "godot.ui",
            "control",
            {
                "scene": scene,
                "node_path": "OverflowHost/OverflowLabel",
                "preset": "full_rect",
                "grow_horizontal": 0,
                "grow_vertical": 0,
                "clip_contents": True,
            },
        )
        if not ack_ok(ov_label, errors, "ui.control OverflowLabel"):
            return errors
        req_id, ov_text = tool_call(
            proc,
            req_id,
            "godot.property",
            "set",
            {
                "scene": scene,
                "node_path": "OverflowHost/OverflowLabel",
                "property": "text",
                "value": variant("string", f"{LONG_TEXT} {LOCAL_TEXT}"),
            },
        )
        if not ack_ok(ov_text, errors, "property.set OverflowLabel.text"):
            return errors
        req_id, ov_host2 = tool_call(
            proc,
            req_id,
            "godot.ui",
            "control",
            {
                "scene": scene,
                "node_path": "OverflowHost",
                "preset": "top_left",
                "size": {"x": 280, "y": 48},
                "grow_horizontal": 0,
                "grow_vertical": 0,
                "clip_contents": True,
            },
        )
        if not ack_ok(ov_host2, errors, "ui.control OverflowHost pin"):
            return errors
        req_id, overflow = tool_call(
            proc,
            req_id,
            "godot.ui",
            "control",
            {
                "scene": scene,
                "node_path": "OverflowHost/OverflowLabel",
                "preset": "full_rect",
                "grow_horizontal": 0,
                "grow_vertical": 0,
                "clip_contents": True,
            },
        )
        if not ack_ok(overflow, errors, "ui.control OverflowLabel"):
            return errors
        ov = overflow.get("after") or {}
        host = ov_host2.get("after") or {}
        min_s = ov.get("min_size") if isinstance(ov.get("min_size"), dict) else {}
        rect = ov.get("rect") if isinstance(ov.get("rect"), dict) else {}
        host_sz = host.get("size") if isinstance(host.get("size"), dict) else {}
        host_rect = host.get("rect") if isinstance(host.get("rect"), dict) else {}
        host_w = float(host_sz.get("x", host_rect.get("w", 0)))
        host_h = float(host_sz.get("y", host_rect.get("h", 0)))
        body_overflow = bool(
            float(min_s.get("x", 0)) > float(rect.get("w", 0)) + 0.5
            or float(min_s.get("y", 0)) > float(rect.get("h", 0)) + 0.5
            or float(min_s.get("x", 0)) > host_w + 0.5
            or float(min_s.get("y", 0)) > host_h + 0.5
        )
        if ov.get("clip_contents") is not True and host.get("clip_contents") is not True:
            errors.append(f"overflow fixture missing clip_contents: host={host} label={ov}")
        if not body_overflow:
            errors.append(
                f"long + localized text overflow was not detected: host={host_sz} label_min={min_s} label_rect={rect}"
            )

        req_id, anchored = tool_call(
            proc,
            req_id,
            "godot.ui",
            "anchor",
            {
                "scene": scene,
                "node_path": ".",
                "anchor_left": 0,
                "anchor_top": 0,
                "anchor_right": 1,
                "anchor_bottom": 1,
                "offset_left": 0,
                "offset_top": 0,
                "offset_right": 0,
                "offset_bottom": 0,
            },
        )
        if not ack_ok(anchored, errors, "ui.anchor root"):
            return errors
        aa = anchored.get("after") or {}
        for key in (
            "anchor_left",
            "anchor_top",
            "anchor_right",
            "anchor_bottom",
            "offset_left",
            "offset_top",
            "offset_right",
            "offset_bottom",
        ):
            if not isinstance(aa.get(key), (int, float)):
                errors.append(f"ui.anchor missing {key}: {aa}")

        req_id, focused = tool_call(
            proc,
            req_id,
            "godot.ui",
            "focus",
            {"scene": scene, "node_path": "MainBox/Menu/StartButton", "grab": True},
        )
        if not ack_ok(focused, errors, "ui.focus"):
            return errors
        fa = focused.get("after") or {}
        neighbors = fa.get("neighbors") if isinstance(fa.get("neighbors"), dict) else {}
        if "OptionsButton" not in str(neighbors.get("bottom") or ""):
            errors.append(f"focus neighbor graph missing bottom OptionsButton: {fa}")
        if not fa.get("next_valid_focus"):
            errors.append(f"find_next_valid_focus missing: {fa}")
        if fa.get("has_focus") is True:
            pass
        elif fa.get("focus_alternative") is True or "Alternative" in str(fa.get("alternative") or ""):
            pass
        else:
            errors.append(f"editor grab_focus Alternative must be labeled honestly: {fa}")

        req_id, access = tool_call(
            proc, req_id, "godot.ui", "accessibility", {"scene": scene, "node_path": "MainBox/Menu/StartButton"}
        )
        if not ack_ok(access, errors, "ui.accessibility"):
            return errors
        acc = access.get("after") or {}
        if acc.get("accessibility_name") != "Start game":
            errors.append(f"accessibility_name readback: {acc}")
        if acc.get("tooltip_text") != "Start hint":
            errors.append(f"tooltip_text readback: {acc}")
        if "focus_mode" not in acc:
            errors.append(f"accessibility missing focus_mode: {acc}")
        if "accessibility_description" not in acc:
            errors.append(f"accessibility_description missing: {acc}")

        req_id, sep_wide = tool_call(
            proc, req_id, "godot.ui", "layout", {"scene": scene, "node_path": "MainBox", "separation": 40}
        )
        if not ack_ok(sep_wide, errors, "ui.layout separation 40"):
            return errors
        if not str(sep_wide.get("undo_action") or "").startswith("Agent: "):
            errors.append(f"ui.layout missing Agent undo: {sep_wide}")
        wide_rows = (sep_wide.get("after") or {}).get("rects") if isinstance((sep_wide.get("after") or {}).get("rects"), list) else []
        wide_gy = None
        if wide_rows and isinstance(wide_rows[0], dict):
            wide_g = wide_rows[0].get("global_rect") if isinstance(wide_rows[0].get("global_rect"), dict) else {}
            wide_gy = wide_g.get("y")
        req_id, undone = tool_call(proc, req_id, "godot.node", "undo", {"scene": scene, "count": 1})
        if not ack_ok(undone, errors, "node.undo after ui.layout"):
            errors.append(f"one-undo after ui.layout must ACK: {undone}")
        req_id, after_undo = tool_call(
            proc, req_id, "godot.canvas", "bounds", {"scene": scene, "node_path": "MainBox/HUD"}
        )
        if ack_ok(after_undo, errors, "canvas.bounds after ui.layout undo"):
            if (after_undo.get("after") or {}).get("invented_box") is True:
                errors.append(f"undo bounds invented_box: {after_undo}")
            undo_rect = (after_undo.get("after") or {}).get("rect") if isinstance((after_undo.get("after") or {}).get("rect"), dict) else {}
            undo_val = undo_rect.get("value") if isinstance(undo_rect.get("value"), dict) else undo_rect
            undo_gy = undo_val.get("y") if isinstance(undo_val, dict) else None
            if wide_gy is not None and undo_gy is not None and baseline_gy is not None:
                if abs(float(undo_gy) - float(baseline_gy)) > abs(float(wide_gy) - float(baseline_gy)) + 0.5:
                    errors.append(f"one UndoRedo layout stroke did not restore separation: {after_undo}")

        req_id, saved = tool_call(proc, req_id, "godot.scene", "save", {"path": scene})
        if not ack_ok(saved, errors, "scene.save"):
            return errors
        hash_before = str((saved.get("after") or {}).get("disk_hash") or "")
        if len(hash_before) < 16:
            errors.append(f"scene.save missing disk_hash: {saved}")

        req_id, reloaded = tool_call(proc, req_id, "godot.scene", "reload", {"path": scene})
        if not ack_ok(reloaded, errors, "scene.reload"):
            return errors
        hash_after = str((reloaded.get("after") or {}).get("disk_hash") or "")
        if hash_before and hash_after and hash_before != hash_after:
            errors.append(f"save/reopen disk_hash drifted: {hash_before} -> {hash_after}")

        req_id, access2 = tool_call(
            proc, req_id, "godot.ui", "accessibility", {"scene": scene, "node_path": "MainBox/Menu/StartButton"}
        )
        if ack_ok(access2, errors, "ui.accessibility after reload"):
            if (access2.get("after") or {}).get("accessibility_name") != "Start game":
                errors.append(f"save/reopen lost accessibility_name: {access2}")

        if _screenshots != "SKIP":
            errors.append("ui screenshot Alternative must stay screenshots=SKIP")
        if secret and secret in "".join(err_lines):
            errors.append("session secret appeared in sidecar logs")
        if secret and secret in "".join(godot_lines):
            errors.append("session secret appeared in Godot logs")
    except Exception as exc:  # noqa: BLE001
        errors.append(sess.redact(f"live ui failed: {type(exc).__name__}: {exc}", secret))
    finally:
        life.stop_proc(godot)
        life.stop_proc(proc)
        if desc_path and desc_path.is_file():
            try:
                desc_path.unlink()
            except OSError:
                pass
        cleanup_temp()
    return errors


def main() -> int:
    errors: list[str] = []
    if not PLAN.is_file():
        print("FAIL: missing authoritative 20-8 plan", file=sys.stderr)
        return 1
    errors.extend(plan_errors(PLAN.read_text(encoding="utf-8")))
    errors.extend(hh_agent_only_addon_errors(PLUGIN_PROJECT, REPO_ROOT))
    errors.extend(src_scan_errors())

    exe, pin_reason = plug.find_pinned_godot()
    if exe is None:
        errors.append(f"pinned Godot required (no skip-PASS): {pin_reason}")
        print("FAIL: ui", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1
    version = plug.godot_version(exe)
    if any(bad in version for bad in ("4.7.2", "4.8")):
        errors.append(f"refused Godot --version {version!r}")
    elif version != PINNED_VERSION:
        errors.append(f"Godot --version {version!r} != {PINNED_VERSION}")

    built = subprocess.run(
        [sess.npm(), "run", "build"],
        cwd=BRIDGE,
        text=True,
        capture_output=True,
        check=False,
    )
    if built.returncode != 0:
        errors.append(f"npm run build failed:\n{built.stdout}\n{built.stderr}")

    if not errors:
        errors.extend(live_errors(exe))

    if errors:
        print("FAIL: ui", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print(
        "PASS: ui control/theme/layout/anchor/focus/accessibility; "
        "viewport 1280x720 + 1920x1080 + 16:10; "
        f"screenshots={SCREENSHOTS}; SystemFont Alternative; "
        "grab_focus Alternative; play.start not paper-ACK'd"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
