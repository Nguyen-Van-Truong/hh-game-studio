#!/usr/bin/env python3
"""R6-WP4: Play-process freeze/step/step-until (not editor time_scale paper).

Does not tick the 20-8 plan. Does not change CURRENT_VALID_WP.
Keep R6-WP4 [ ]; while unticked CURRENT_VALID_WP=R6-WP4; after tick allow R6-WP5+.
Pin 4.7.1-stable only. Refuse later 4.7 patches past .1-stable. No skip-PASS.
No dummy screenshot PNG. No desktop OS inject / pixel RPA. No eval of user predicates.

Verify (encoded here; this file is the official harness):
  - freeze frame 0 / seed / fixed physics ticks; step N / ms / until predicate
  - ACK only when Play is proven (is_playing_scene + run_id) AND a fixture
    observes frozen/stepped state (counter increments only when unfrozen)
  - idle / no-Play freeze/step stay E_UNVERIFIED
  - 10-run same seed + same input + freeze/step → canonical logic state equal
  - step-until a predicate that never happens → E_TIMEOUT (missed event), no hang
  - screenshot/perf may ACK when Play is proven; idle/no-Play stay E_UNVERIFIED
  - screenshots=SKIP
  - tests do not use sleep 2s as the observation strategy (setup waits of ~1s
    for Play attach are labeled)

If headless --editor never freezes: label Alternative, do not invent ok=true.
Try exclusive GUI Godot (same pin exe, --editor --path godot/plugin-project).
Do not start a second Godot if one is already on plugin-project.
Kill leftover Godot/Node on plugin-project first.
CPU load variance: Alternative if we cannot isolate a CPU-load injector —
do not invent a number.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hh_agent_allow import hh_agent_only_addon_errors
import test_plugin_router as plug
import test_play_input as pin
import test_scene_lifecycle as life
import test_session as sess

BRIDGE = REPO_ROOT / "bridge"
PLAN = REPO_ROOT / "zdocs" / "20-8-godot-agent-autopilot-plan.txt"
PLUGIN_PROJECT = REPO_ROOT / "godot" / "plugin-project"
ADDON = PLUGIN_PROJECT / "addons" / "hh_agent"
ACTIONS_JSON = ADDON / "core" / "actions.json"
PINNED_VERSION = plug.PINNED_VERSION
TEMP_DIR = PLUGIN_PROJECT / "r6w4"
VENDOR_NEEDLES = plug.VENDOR_NEEDLES
SCREENSHOTS = "SKIP"
PRODUCT_RUNTIME = ADDON / "runtime" / "hh_agent_runtime.gd"
MAX_PAGE = 100
SEED = 4242
STEP_N = 4
CANON_STEPS = STEP_N * 2
# Setup wait for Play debugger attach. Not the freeze/step observation strategy.
PLAY_ATTACH_SETUP_S = 1.0

FIXTURE_SCRIPT = """extends Node2D

var physics_ticks: int = 0
var process_ticks: int = 0
var accept_held_ticks: int = 0
var rng_draw: int = 0
var never_flag: bool = false
var events: int = 0

func _ready() -> void:
	set_process(true)
	set_physics_process(true)
	if not InputMap.has_action("ui_accept"):
		InputMap.add_action("ui_accept")

func _physics_process(_delta: float) -> void:
	physics_ticks += 1
	rng_draw = randi() % 10000
	if Input.is_action_pressed("ui_accept"):
		accept_held_ticks += 1

func _process(_delta: float) -> void:
	process_ticks += 1

func agent_observe() -> Dictionary:
	return {
		"physics_ticks": physics_ticks,
		"process_ticks": process_ticks,
		"accept_held_ticks": accept_held_ticks,
		"rng_draw": rng_draw,
		"never_flag": never_flag,
		"events": events,
	}
"""


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def plan_errors(text: str) -> list[str]:
    """Keep R6-WP4 [ ]; while unticked require CURRENT_VALID_WP=R6-WP4."""
    errors: list[str] = []
    current = ""
    wp4 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R6-WP4\b", stripped):
            wp4 = stripped
    if wp4 is None:
        return ["plan missing R6-WP4 heading"]
    ticked = bool(re.search(r"\[x\]", wp4, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp4:
            errors.append("R6-WP4 heading must keep [ ] until coordinator tick")
        if current != "R6-WP4":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R6-WP4 while WP4 is unticked)")
    elif not re.match(r"^R6-WP([5-9]|\d{2,})$|^R[7-9]-WP\d+$|^RX-WP\d+$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R6-WP5+ after R6-WP4 tick)")
    return errors


def cleanup_temp() -> list[str]:
    errors: list[str] = []
    for _ in range(6):
        if not TEMP_DIR.exists():
            break
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
        time.sleep(0.2)
    if TEMP_DIR.exists():
        for path in TEMP_DIR.rglob("*"):
            if path.is_file():
                try:
                    path.unlink()
                except OSError:
                    pass
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
    if TEMP_DIR.exists():
        leftovers = [p.as_posix() for p in TEMP_DIR.rglob("*")]
        errors.append(f"r6w4 fixture leftover after cleanup: {leftovers[:8]}")
    agent = PLUGIN_PROJECT / ".hh-agent"
    for name in ("file-leases.json", "writer.lock"):
        lock = agent / name
        if lock.is_file():
            try:
                lock.unlink()
            except OSError:
                pass
    return errors


def src_scan_errors() -> list[str]:
    errors: list[str] = []
    self_text = Path(__file__).read_text(encoding="utf-8")
    prefix = self_text.split("def src_scan_errors")[0]
    if re.search(r"\.write_text\([^\n]*\.(?:tscn|tres|res|png)", self_text):
        errors.append("official test writes a .tscn/.tres/.png path directly")
    if re.search(r"\.write_bytes\(|Image\.new\b", self_text):
        errors.append("official test must not bless dummy screenshot PNGs")
    if "screenshots=SKIP" not in self_text and 'SCREENSHOTS = "SKIP"' not in self_text:
        errors.append("official test must record screenshots=SKIP")
    if "Alternative" not in self_text:
        errors.append("official test must record headless/CPU Alternative honestly")
    if "paper-ACK" not in self_text and "paper" not in self_text:
        errors.append("official test must refuse to paper-ACK editor-only freeze")
    if "skip-PASS" not in self_text and "No skip-PASS" not in self_text:
        errors.append("official test must refuse skip-PASS")
    if "sleep 2s" not in self_text and "sleep 2" not in self_text:
        errors.append("official test must refuse sleep-2s observation")
    if "E_TIMEOUT" not in self_text or "missed event" not in self_text:
        errors.append("official test must encode timeout / missed event")
    if "10-run" not in self_text and "10 run" not in self_text:
        errors.append("official test must encode 10-run canonical equality")
    if "res://" + "snake" in self_text or "kho" + "-bi-an" in self_text:
        errors.append("official test must stay independent of demo game trees")
    if "4.7." + "2" in self_text:
        errors.append("official test must refuse Godot 4.7." + "2 pin")
    if "time.sleep(2)" in self_text.split("def src_scan_errors")[0]:
        errors.append("official harness prefix must not use time.sleep(2)")
    for needle in ("Send" + "Input", "mouse_" + "event", "user" + "32"):
        if needle in prefix:
            errors.append("official test must not name a desktop inject API in the harness prefix")

    for path in ADDON.rglob("*.gd"):
        blob = path.read_text(encoding="utf-8", errors="replace")
        posix = rel(path)
        for needle in ("Send" + "Input", "mouse_" + "event", "keybd_" + "event"):
            if needle in blob:
                errors.append(f"{posix} contains desktop inject needle {needle!r}")
        if ("user" + "32") in blob.lower():
            errors.append(f"{posix} contains user32")
        if "evaluate_" + "expression" in blob:
            errors.append(f"{posix} evaluates expressions")
        if "Expression.new" in blob:
            errors.append(f"{posix} constructs Expression")
        if re.search(r"(?<![A-Za-z_])eval\s*\(", blob):
            errors.append(f"{posix} calls eval(")

    runtime_gd = PRODUCT_RUNTIME
    if not runtime_gd.is_file():
        errors.append("missing addons/hh_agent/runtime/hh_agent_runtime.gd")
    else:
        rtext = runtime_gd.read_text(encoding="utf-8")
        if "_time_op" not in rtext or "_eval_predicate" not in rtext:
            errors.append("product runtime must own freeze/step + allowlisted predicate")
        if "Engine" + "Debugger" not in rtext:
            errors.append("game-side autoload must use debugger send_message")
        if re.search(r"Engine\.time_scale\s*=", rtext):
            errors.append("product runtime must not assign Engine.time_scale as freeze")
        if "value_int" not in rtext or "value_bool" not in rtext:
            errors.append("predicate DSL must allowlist typed compares, not eval")

    adapter = ADDON / "core" / "hh_runtime_adapter.gd"
    if not adapter.is_file():
        errors.append("missing hh_runtime_adapter.gd")
    else:
        atext = adapter.read_text(encoding="utf-8")
        if "begin_time" not in atext:
            errors.append("runtime adapter must own begin_time")
        if "Engine" + "Debugger" in atext:
            errors.append("do not use the game-side debugger singleton in the editor runtime adapter")
        if re.search(r"Engine\.time_scale\s*=", atext):
            errors.append("runtime adapter must not assign editor Engine.time_scale")
        if ("Send" + "Input") in atext:
            errors.append("runtime adapter must not call a desktop inject API")

    router = (ADDON / "core" / "hh_router.gd").read_text(encoding="utf-8")
    if "_time_apply" not in router:
        errors.append("router must dispatch freeze/step when Play can be proven")
    if "runtime freeze/step idle must stay E_UNVERIFIED" not in router:
        errors.append("router self-test must keep idle/no-Play freeze/step E_UNVERIFIED")

    reads = (ADDON / "core" / "hh_read_adapters.gd").read_text(encoding="utf-8")
    if "runtime screenshot/perf must use Play capture apply" not in reads:
        errors.append("screenshot/perf must use Play apply (idle/no-Play stays E_UNVERIFIED)")

    for dbg_name in ("hh_play_debugger.gd", "hh_runtime_debugger.gd"):
        dbg = ADDON / "core" / dbg_name
        if not dbg.is_file():
            errors.append(f"missing {dbg_name}")
            continue
        dtext = dbg.read_text(encoding="utf-8")
        if re.search(r"return true", dtext):
            errors.append(f"{dbg_name} must not contain return true")
        if "Engine" + "Debugger" in dtext:
            errors.append(f"do not use the game-side debugger singleton in {dbg_name}")

    execute = (BRIDGE / "src" / "ledger" / "execute.ts").read_text(encoding="utf-8")
    if "function runtimeApplyOk" not in execute:
        errors.append("execute.ts must postcondition-check freeze/step apply")
    if "const runtimeFail = runtimeApplyOk" not in execute:
        errors.append("execute.ts must call runtimeApplyOk from apply path")
    lifecycle = (BRIDGE / "src" / "ledger" / "scene_lifecycle.ts").read_text(encoding="utf-8")
    if "RUNTIME_APPLY" not in lifecycle or "isRuntimeApply" not in lifecycle:
        errors.append("scene_lifecycle must export RUNTIME_APPLY / isRuntimeApply")
    proven = lifecycle.split("export function isProvenEditorApply")[-1]
    if "isRuntimeApply" in proven.split("{", 1)[-1].split("}", 1)[0]:
        errors.append("isRuntimeApply must NOT be inside isProvenEditorApply")
    play_apply = lifecycle.split("PLAY_APPLY")[1].split("]")[0] if "PLAY_APPLY" in lifecycle else ""
    if "runtime.freeze" in play_apply or "runtime.step" in play_apply:
        errors.append("do not dump freeze/step verbs into PLAY_APPLY")

    plugin = (ADDON / "plugin.gd").read_text(encoding="utf-8")
    if "add_autoload_singleton(" in plugin:
        errors.append("plugin.gd must not call add_autoload_singleton")
    export_gd = (ADDON / "core" / "hh_export_plugin.gd").read_text(encoding="utf-8")
    if "r6w4" not in export_gd or "hh_agent_runtime" not in export_gd:
        errors.append("export skip() must cover r6w4 fixture and hh_agent_runtime")

    for path in (BRIDGE / "src").rglob("*.ts"):
        blob = path.read_text(encoding="utf-8", errors="replace")
        posix = rel(path)
        for needle in VENDOR_NEEDLES:
            if needle in blob:
                errors.append(f"{posix} contains vendor needle {needle!r}")
                break
    return errors


def tool_call(
    proc,
    req_id: int,
    method: str,
    action: str,
    params: dict,
    timeout: float = 60.0,
) -> tuple[int, dict]:
    return pin.tool_call(proc, req_id, method, action, params, timeout)


def ack_ok(body: dict, errors: list[str], verb: str) -> bool:
    return pin.ack_ok(body, errors, verb)


def after_of(body: dict) -> dict:
    return pin.after_of(body)


def err_code(body: dict) -> str:
    return pin.err_code(body)


def err_msg(body: dict) -> str:
    return pin.err_msg(body)


def play_start(proc, req_id: int, scene: str, mode: str = "debug") -> tuple[int, dict]:
    return pin.play_start(proc, req_id, scene, mode)


def play_stop(proc, req_id: int, reason: str = "test", run_id: str | None = None) -> tuple[int, dict]:
    return pin.play_stop(proc, req_id, reason, run_id)


def wait_runtime_ready(proc, req_id: int, run_id: str) -> tuple[int, bool, dict]:
    return pin.wait_runtime_ready(proc, req_id, run_id)


def observe(proc, req_id: int, run_id: str) -> tuple[int, dict]:
    """Fixture agent_observe only. Never fall back to HHAgentTickProbe."""
    for path in ("Fixture", "/root/freeze/Fixture"):
        req_id, node_body = tool_call(
            proc, req_id, "godot.runtime", "node", {"node_path": path, "run_id": run_id}, timeout=20.0
        )
        after = after_of(node_body)
        obs = after.get("observe")
        if (
            isinstance(obs, dict)
            and "physics_ticks" in obs
            and "process_ticks" in obs
            and "accept_held_ticks" in obs
        ):
            return req_id, obs
        props = after.get("properties")
        if (
            isinstance(props, dict)
            and "physics_ticks" in props
            and "accept_held_ticks" in props
        ):
            merged = dict(props)
            if isinstance(obs, dict):
                merged.update(obs)
            return req_id, merged
    return req_id, {}


def setup_scene(proc, req_id: int, errors: list[str]) -> tuple[int, str]:
    scene = "res://r6w4/freeze.tscn"
    runtime_script = "res://r6w4/runtime.gd"
    fixture_script = "res://r6w4/fixture.gd"
    if not PRODUCT_RUNTIME.is_file():
        errors.append("missing addons/hh_agent/runtime/hh_agent_runtime.gd")
        return req_id, scene
    product = PRODUCT_RUNTIME.read_text(encoding="utf-8")
    if "_time_op" not in product:
        errors.append("product runtime script must own freeze/step")
        return req_id, scene
    req_id, created = tool_call(proc, req_id, "godot.scene", "create", {"path": scene, "root_class": "Node2D"})
    if not ack_ok(created, errors, "scene.create"):
        return req_id, scene
    req_id = pin.write_script(proc, req_id, runtime_script, product, errors)
    req_id = pin.write_script(proc, req_id, fixture_script, FIXTURE_SCRIPT, errors)
    req_id, opened = tool_call(proc, req_id, "godot.scene", "open", {"path": scene})
    if opened.get("ok") is not True:
        errors.append(f"scene.open {scene}: {opened}")
        return req_id, scene
    req_id, attached = tool_call(
        proc, req_id, "godot.script", "attach", {"scene": scene, "node_path": ".", "path": runtime_script}
    )
    if not ack_ok(attached, errors, "script.attach runtime"):
        return req_id, scene
    req_id, added = tool_call(
        proc,
        req_id,
        "godot.node",
        "add",
        {"scene": scene, "parent": ".", "class_name": "Node2D", "name": "Fixture"},
    )
    if not ack_ok(added, errors, "node.add Fixture"):
        return req_id, scene
    req_id, fat = tool_call(
        proc, req_id, "godot.script", "attach", {"scene": scene, "node_path": "Fixture", "path": fixture_script}
    )
    if not ack_ok(fat, errors, "script.attach Fixture"):
        return req_id, scene
    req_id, saved = tool_call(proc, req_id, "godot.scene", "save", {"path": scene})
    ack_ok(saved, errors, "scene.save")
    return req_id, scene


def verify_later_wps(proc, req_id: int, errors: list[str]) -> int:
    for method, action, params, label in (
        ("godot.runtime", "screenshot", {"scale": 1}, "runtime.screenshot"),
        ("godot.runtime", "perf", {"detail": "short"}, "runtime.perf"),
    ):
        req_id, later = tool_call(proc, req_id, method, action, params)
        if later.get("ok") is True:
            after = after_of(later)
            if after.get("is_playing_scene") is not True or after.get("source") != "hh_agent_runtime":
                errors.append(f"{label} ACK requires proven Play: {later}")
        elif err_code(later) not in ("E_UNVERIFIED", "E_TIMEOUT", "E_BUSY"):
            errors.append(f"{label} may ACK when Play is proven; idle stays E_UNVERIFIED: {later}")
    return req_id


def freeze_call(proc, req_id: int, run_id: str, frozen: bool = True) -> tuple[int, dict]:
    return tool_call(
        proc,
        req_id,
        "godot.runtime",
        "freeze",
        {
            "frozen": frozen,
            "reason": "test",
            "seed": SEED,
            "physics_ticks": 60,
            "frame": 0,
            "run_id": run_id,
        },
        timeout=40.0,
    )


def step_call(proc, req_id: int, run_id: str, frames: int, extra: dict | None = None) -> tuple[int, dict]:
    params: dict = {"frames": frames, "run_id": run_id}
    if extra:
        params.update(extra)
    return tool_call(proc, req_id, "godot.runtime", "step", params, timeout=40.0)


def canon_of(before: dict, after: dict) -> dict:
    return {
        "delta_physics": int(after.get("physics_ticks") or 0) - int(before.get("physics_ticks") or 0),
        "rng_draw": int(after.get("rng_draw") or 0),
        "accept_held_ticks": int(after.get("accept_held_ticks") or 0)
        - int(before.get("accept_held_ticks") or 0),
    }


def prove_freeze_ack(body: dict, errors: list[str], verb: str) -> bool:
    if not ack_ok(body, errors, verb):
        return False
    after = after_of(body)
    if after.get("source") != "hh_agent_runtime":
        errors.append(f"{verb} must come from Play hh_agent_runtime: {body}")
        return False
    if after.get("is_playing_scene") is not True or after.get("playing") is not True:
        errors.append(f"{verb} ACK requires proven Play: {body}")
        return False
    if after.get("editor_time_scale") is True:
        errors.append(f"{verb} paper-ACK editor time_scale: {body}")
        return False
    return True


def drive_once(proc, req_id: int, run_id: str, errors: list[str]) -> tuple[int, dict | None]:
    req_id, _ = tool_call(
        proc, req_id, "godot.input", "release_all", {"scope": "all", "run_id": run_id}, timeout=30.0
    )
    req_id, fr = freeze_call(proc, req_id, run_id, True)
    if not prove_freeze_ack(fr, errors, "runtime.freeze"):
        return req_id, None
    after_fr = after_of(fr)
    if after_fr.get("frozen") is not True or after_fr.get("observed_frozen") is not True:
        errors.append(f"runtime.freeze must observe paused Play ticks: {fr}")
        return req_id, None
    if after_fr.get("events_subscribed") is not True:
        errors.append(f"event subscription must happen before drive: {fr}")
        return req_id, None
    req_id, before = observe(proc, req_id, run_id)
    if "physics_ticks" not in before:
        errors.append(f"fixture observe missing physics_ticks: {before}")
        return req_id, None
    req_id, held = tool_call(
        proc,
        req_id,
        "godot.input",
        "action",
        {"action_name": "ui_accept", "phase": "press", "run_id": run_id},
        timeout=30.0,
    )
    if not ack_ok(held, errors, "input.action ui_accept"):
        return req_id, None
    req_id, st1 = step_call(proc, req_id, run_id, STEP_N)
    if not prove_freeze_ack(st1, errors, "runtime.step hold"):
        return req_id, None
    if int(after_of(st1).get("frames_advanced") or 0) < 1:
        errors.append(f"runtime.step must advance observed frames: {st1}")
        return req_id, None
    req_id, rel_body = tool_call(
        proc, req_id, "godot.input", "release_all", {"scope": "all", "run_id": run_id}, timeout=30.0
    )
    if not ack_ok(rel_body, errors, "input.release_all after held step"):
        return req_id, None
    req_id, st2 = step_call(proc, req_id, run_id, STEP_N)
    if not prove_freeze_ack(st2, errors, "runtime.step rest"):
        return req_id, None
    req_id, after = observe(proc, req_id, run_id)
    return req_id, canon_of(before, after)


def verify_freeze_suite(
    proc, req_id: int, errors: list[str], scene: str
) -> tuple[int, bool, dict[str, str]]:
    labels = {
        "freeze_step": "unproven",
        "equality": "unproven",
        "timeout": "unproven",
        "cpu": "Alternative",
    }
    req_id, idle = tool_call(
        proc, req_id, "godot.runtime", "freeze", {"frozen": True, "reason": "test"}
    )
    if idle.get("ok") is True:
        errors.append("runtime.freeze must stay E_UNVERIFIED when Play is not running (paper-ACK)")
    if err_code(idle) != "E_UNVERIFIED":
        errors.append(f"idle/no-Play freeze must be E_UNVERIFIED: {idle}")
    req_id, idle_step = tool_call(proc, req_id, "godot.runtime", "step", {"frames": 1})
    if idle_step.get("ok") is True or err_code(idle_step) != "E_UNVERIFIED":
        errors.append(f"idle/no-Play step must be E_UNVERIFIED: {idle_step}")
    for method, action, params, label in (
        ("godot.runtime", "screenshot", {"scale": 1}, "runtime.screenshot"),
        ("godot.runtime", "perf", {"detail": "short"}, "runtime.perf"),
    ):
        req_id, idle_cap = tool_call(proc, req_id, method, action, params)
        if idle_cap.get("ok") is True or err_code(idle_cap) != "E_UNVERIFIED":
            errors.append(f"idle/no-Play {label} must be E_UNVERIFIED: {idle_cap}")

    req_id, start_body = play_start(proc, req_id, scene, mode="debug")
    if start_body.get("ok") is not True or after_of(start_body).get("playing") is not True:
        errors.append(f"play.start must ACK with playing=true after proven Play: {start_body}")
        return req_id, False, labels
    run_id = str(after_of(start_body).get("run_id") or "")
    if len(run_id) != 26:
        errors.append(f"play.start must mint run_id: {start_body}")
        return req_id, False, labels
    time.sleep(PLAY_ATTACH_SETUP_S)
    req_id, ready, tree_body = wait_runtime_ready(proc, req_id, run_id)
    if not ready:
        errors.append(f"runtime.tree must ACK from hh_agent_runtime before freeze: {tree_body}")
        req_id, _ = play_stop(proc, req_id, run_id=run_id)
        return req_id, False, labels

    req_id, fr = freeze_call(proc, req_id, run_id, True)
    if not prove_freeze_ack(fr, errors, "runtime.freeze first"):
        req_id, _ = play_stop(proc, req_id, run_id=run_id)
        return req_id, False, labels
    req_id, t0 = observe(proc, req_id, run_id)
    req_id, t1 = observe(proc, req_id, run_id)
    if "accept_held_ticks" not in t0 or "accept_held_ticks" not in t1:
        errors.append(f"frozen observe must be Fixture, not TickProbe: {t0} vs {t1}")
    elif int(t0.get("physics_ticks") or -1) != int(t1.get("physics_ticks") or -2):
        errors.append(f"frozen fixture physics_ticks must stay still across observes: {t0} vs {t1}")
    elif int(t0.get("process_ticks") or -1) != int(t1.get("process_ticks") or -2):
        errors.append(f"frozen fixture process_ticks must stay still across observes: {t0} vs {t1}")
    req_id, st = step_call(proc, req_id, run_id, 3)
    if not prove_freeze_ack(st, errors, "runtime.step 3"):
        req_id, _ = play_stop(proc, req_id, run_id=run_id)
        return req_id, False, labels
    req_id, t2 = observe(proc, req_id, run_id)
    delta = int(t2.get("physics_ticks") or 0) - int(t1.get("physics_ticks") or 0)
    if delta < 3:
        errors.append(f"freeze then step must advance fixture physics_ticks, got delta={delta} {t1}->{t2}")
    else:
        labels["freeze_step"] = "proven"

    req_id, until_ok = step_call(
        proc,
        req_id,
        run_id,
        1,
        {
            "until": {
                "key": "physics_ticks",
                "op": "gte",
                "value_int": int(t2.get("physics_ticks") or 0) + 2,
                "node_path": "Fixture",
            },
            "timeout_ms": 4000,
        },
    )
    if not prove_freeze_ack(until_ok, errors, "runtime.step until"):
        pass
    elif after_of(until_ok).get("matched") is not True:
        errors.append(f"step-until reachable predicate must match: {until_ok}")

    req_id, ms_step = step_call(proc, req_id, run_id, 1, {"ms": 50})
    if not prove_freeze_ack(ms_step, errors, "runtime.step ms"):
        pass

    t_miss = time.time()
    req_id, missed = step_call(
        proc,
        req_id,
        run_id,
        1,
        {
            "until": {
                "key": "never_flag",
                "op": "eq",
                "value_bool": True,
                "node_path": "Fixture",
            },
            "timeout_ms": 600,
        },
    )
    elapsed = time.time() - t_miss
    if missed.get("ok") is True:
        errors.append(f"step-until missed event must not paper-ACK: {missed}")
    elif err_code(missed) != "E_TIMEOUT":
        errors.append(f"step-until missed event must be E_TIMEOUT: {missed}")
    elif elapsed > 12.0:
        errors.append(f"step-until timeout hung ({elapsed:.1f}s): {missed}")
    elif "missed event" in err_msg(missed).lower() or after_of(missed).get("missed_event") is True:
        labels["timeout"] = "proven"
    else:
        errors.append(f"timeout must name missed event: {missed}")

    req_id = verify_later_wps(proc, req_id, errors)

    # Equality is same seed + same input + freeze/step on equivalent Play
    # starts — not one dirty session after the timeout suite plus nine fresh.
    canons: list[dict] = []
    for _i in range(10):
        req_id, _ = play_stop(proc, req_id, run_id=run_id)
        time.sleep(0.3)
        req_id, start_body = play_start(proc, req_id, scene, mode="debug")
        if start_body.get("ok") is not True or after_of(start_body).get("playing") is not True:
            errors.append(f"10-run play.start failed: {start_body}")
            break
        run_id = str(after_of(start_body).get("run_id") or "")
        time.sleep(PLAY_ATTACH_SETUP_S)
        req_id, ready, tree_body = wait_runtime_ready(proc, req_id, run_id)
        if not ready:
            errors.append(f"10-run runtime.tree not ready: {tree_body}")
            break
        req_id, one = drive_once(proc, req_id, run_id, errors)
        if one is None:
            break
        canons.append(one)
    if len(canons) == 10 and all(item == canons[0] for item in canons):
        if canons[0].get("delta_physics", 0) < CANON_STEPS:
            errors.append(f"10-run canonical delta_physics too small: {canons[0]}")
        elif canons[0].get("accept_held_ticks", 0) < STEP_N:
            errors.append(f"10-run must see held input ticks during step, got {canons[0]}")
        else:
            labels["equality"] = "proven"
    elif len(canons) == 10:
        errors.append(f"10-run canonical state mismatch: {canons}")
    else:
        errors.append(f"10-run produced {len(canons)} states (need 10)")

    req_id, _ = play_stop(proc, req_id, run_id=run_id)
    time.sleep(0.3)
    errors.extend(pin.project_godot_leak_errors("after play.stop"))
    req_id, after_stop = tool_call(
        proc, req_id, "godot.runtime", "freeze", {"frozen": True, "reason": "test"}
    )
    if after_stop.get("ok") is True:
        errors.append("runtime.freeze must return to E_UNVERIFIED after play.stop")
    if err_code(after_stop) != "E_UNVERIFIED":
        errors.append(f"freeze after play.stop must be E_UNVERIFIED: {after_stop}")
    proven = labels["freeze_step"] == "proven" and labels["equality"] == "proven" and labels["timeout"] == "proven"
    return req_id, proven, labels


def live_errors(exe: Path) -> tuple[list[str], str, str, str, dict[str, str]]:
    errors: list[str] = []
    live = "unrun"
    headless_freeze = "unproven"
    gui_freeze = "unrun"
    labels = {
        "freeze_step": "unproven",
        "equality": "unproven",
        "timeout": "unproven",
        "cpu": "Alternative",
    }
    pin.kill_plugin_project_holders()
    time.sleep(1.0)
    if pin.plugin_godot_busy():
        errors.append("LIVE_UNRUN: Godot already open on plugin-project (exclusive; no second instance)")
        return errors, "unrun", "unproven", "unrun", labels
    errors.extend(cleanup_temp())
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    proc = None
    godot = None
    desc_path = None
    secret = ""
    err_lines: list[str] = []
    godot_lines: list[str] = []
    req_id = 2
    try:
        proc, desc_path, secret, err_lines = life.start_sidecar()
        godot, godot_lines = pin.start_godot(exe, headless=True)
        req_id, hello, last = life.wait_hello(proc, godot, req_id)
        if not hello:
            errors.append(
                "live plugin hello/noop failed: "
                f"{sess.redact(json.dumps(last), secret)}; godot={''.join(godot_lines)[-1500:]}"
            )
            return errors, "failed", "unproven", "unrun", labels
        live = "ran"
        req_id, idle = tool_call(
            proc, req_id, "godot.runtime", "freeze", {"frozen": True, "reason": "test"}
        )
        if idle.get("ok") is True or err_code(idle) != "E_UNVERIFIED":
            errors.append(f"headless idle freeze must stay E_UNVERIFIED: {idle}")
        req_id, scene = setup_scene(proc, req_id, errors)
        if errors:
            return errors, live, headless_freeze, gui_freeze, labels
        req_id, start_body = play_start(proc, req_id, scene)
        playing = start_body.get("ok") is True and after_of(start_body).get("playing") is True
        if playing:
            run_id = str(after_of(start_body).get("run_id") or "")
            time.sleep(PLAY_ATTACH_SETUP_S)
            req_id, ready, _tree = wait_runtime_ready(proc, req_id, run_id)
            if ready:
                req_id, fr = freeze_call(proc, req_id, run_id, True)
                req_id, t0 = observe(proc, req_id, run_id)
                req_id, t1 = observe(proc, req_id, run_id)
                still = (
                    "accept_held_ticks" in t0
                    and int(t0.get("physics_ticks") or -1) == int(t1.get("physics_ticks") or -2)
                    and int(t0.get("process_ticks") or -1) == int(t1.get("process_ticks") or -2)
                )
                req_id, st = step_call(proc, req_id, run_id, 2)
                req_id, t2 = observe(proc, req_id, run_id)
                delta = int(t2.get("physics_ticks") or 0) - int(t1.get("physics_ticks") or 0)
                if (
                    fr.get("ok") is True
                    and after_of(fr).get("observed_frozen") is True
                    and still
                    and st.get("ok") is True
                    and delta >= 2
                    and "accept_held_ticks" in t2
                ):
                    headless_freeze = "proven"
                else:
                    headless_freeze = "Alternative"
            req_id, _ = play_stop(proc, req_id)
            errors.extend(pin.project_godot_leak_errors("after headless play.stop"))
        elif start_body.get("ok") is True:
            errors.append(f"headless play.start paper-ACK playing=true: {start_body}")
            return errors, live, "unproven", gui_freeze, labels
        else:
            headless_freeze = "unproven"
        life.stop_proc(godot)
        godot = None
        time.sleep(1.0)
        pin.kill_plugin_project_holders(godot=True, node=False)
        agent = PLUGIN_PROJECT / ".hh-agent"
        for name in ("file-leases.json", "writer.lock"):
            lock = agent / name
            if lock.is_file():
                try:
                    lock.unlink()
                except OSError:
                    pass
        time.sleep(1.0)
        if pin.plugin_godot_busy():
            errors.append("exclusive GUI Godot unavailable (plugin-project already held)")
            return errors, live, headless_freeze, "unrun", labels
        godot, godot_lines = pin.start_godot(exe, headless=False)
        req_id, hello, last = life.wait_hello(proc, godot, req_id)
        if not hello:
            errors.append(
                "GUI Godot hello/noop failed: "
                f"{sess.redact(json.dumps(last), secret)}; godot={''.join(godot_lines)[-1500:]}"
            )
            return errors, live, headless_freeze, "failed", labels
        req_id, suite_ok, labels = verify_freeze_suite(proc, req_id, errors, scene)
        if suite_ok:
            gui_freeze = "proven"
        else:
            gui_freeze = "unproven"
        errors.extend(pin.project_godot_leak_errors("after GUI suite"))
    except Exception as exc:  # noqa: BLE001
        errors.append(f"live play freeze failed: {type(exc).__name__}: {exc}")
        live = "failed"
    finally:
        if godot is not None:
            try:
                tool_call(proc, req_id, "godot.play", "stop", {"reason": "test"}, timeout=10.0)
            except Exception:
                pass
            life.stop_proc(godot)
        if proc is not None:
            life.stop_proc(proc)
        if desc_path and desc_path.is_file():
            try:
                desc_path.unlink()
            except OSError:
                pass
            lock = desc_path.with_name("sidecar.lock")
            if lock.is_file():
                try:
                    lock.unlink()
                except OSError:
                    pass
        if secret and secret in "".join(err_lines):
            errors.append("session secret appeared in sidecar logs")
        errors.extend(cleanup_temp())
        errors.extend(pin.project_godot_leak_errors("after suite cleanup"))
    return errors, live, headless_freeze, gui_freeze, labels


def main() -> int:
    errors: list[str] = []
    errors.extend(hh_agent_only_addon_errors(PLUGIN_PROJECT, REPO_ROOT))
    errors.extend(src_scan_errors())
    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.is_file() else None
    if plan_text is None:
        errors.append(f"missing {rel(PLAN)}")
    else:
        errors.extend(plan_errors(plan_text))

    built = subprocess.run(
        ["npm.cmd" if os.name == "nt" else "npm", "run", "generate"],
        cwd=str(BRIDGE),
        text=True,
        capture_output=True,
        check=False,
    )
    if built.returncode != 0:
        errors.append(f"bridge generate failed:\n{built.stdout}\n{built.stderr}")
        print("FAIL")
        for item in errors:
            print(f"  - {item}")
        return 1

    catalog = json.loads(ACTIONS_JSON.read_text(encoding="utf-8")) if ACTIONS_JSON.is_file() else {}
    actions = catalog.get("actions") if isinstance(catalog.get("actions"), dict) else {}
    for action_id in ("runtime.freeze", "runtime.step"):
        spec = actions.get(action_id) if isinstance(actions.get(action_id), dict) else {}
        if spec.get("method") != "godot.runtime":
            errors.append(f"actions.json missing {action_id}")
        if spec.get("side_effect") != "external":
            errors.append(f"{action_id} must stay EXTERNAL")
    validator_path = BRIDGE / "generated" / "plugin-validator.json"
    validator = json.loads(validator_path.read_text(encoding="utf-8")) if validator_path.is_file() else {}
    step_schema = ((validator.get("actions") or {}).get("runtime.step") or {}) if isinstance(validator, dict) else {}
    if "until" not in json.dumps(step_schema):
        errors.append("runtime.step schema must include allowlisted until predicate")

    exe, pin_reason = plug.find_pinned_godot()
    live = "unrun"
    headless_freeze = "unproven"
    gui_freeze = "unrun"
    labels: dict[str, str] = {}
    if exe is None:
        errors.append(f"pinned Godot required: {pin_reason}")
    else:
        version = plug.godot_version(exe)
        if version != PINNED_VERSION:
            errors.append(f"Godot --version {version!r} != {PINNED_VERSION}")
        else:
            live_errs, live, headless_freeze, gui_freeze, labels = live_errors(exe)
            errors.extend(live_errs)

    errors.extend(pin.project_godot_leak_errors("after official test"))
    errors.extend(cleanup_temp())
    cpu = labels.get("cpu", "Alternative")
    if errors:
        print(
            f"FAIL: play freeze; LIVE={live}; HEADLESS_FREEZE={headless_freeze}; "
            f"GUI_FREEZE={gui_freeze}; FREEZE_STEP={labels.get('freeze_step', 'unrun')}; "
            f"EQUALITY={labels.get('equality', 'unrun')}; TIMEOUT={labels.get('timeout', 'unrun')}; "
            f"CPU={cpu}; screenshots={SCREENSHOTS}"
        )
        for item in errors:
            print(f"  - {item}")
        return 1
    print(
        f"PASS: Play-process freeze/step + 10-run equality + timeout; "
        f"LIVE={live}; HEADLESS_FREEZE={headless_freeze}; GUI_FREEZE={gui_freeze}; "
        f"FREEZE_STEP={labels.get('freeze_step')}; EQUALITY={labels.get('equality')}; "
        f"TIMEOUT={labels.get('timeout')}; CPU={cpu}; screenshots={SCREENSHOTS}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
