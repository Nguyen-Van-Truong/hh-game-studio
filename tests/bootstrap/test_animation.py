#!/usr/bin/env python3
"""R5-WP3: Animation/SpriteFrames/AnimationTree workflow.

Does not tick the 20-8 plan. G2 is not involved. Pin missing is a hard FAIL.
No skip-PASS. No dummy screenshot PNG. Do not paper-ACK play.start.
Do not raw-edit .tscn/.tres bytes. Plugin is the only writer.

Verify (encoded here; this file is the official harness):
  - create scene + SpriteFrames idle/walk/interact with >1 frame each
  - AnimationPlayer library + named clips + value tracks + key batch
  - AnimationTree state machine idle→walk with a condition
  - editor preview readback current_animation / is_playing /
    current_animation_position (not a Play process)
  - one UndoRedo key-batch stroke, Agent: prefix
  - save/reopen hash
  - screenshots=SKIP

Honest Alternative: PlaceholderTexture2D stands in for missing painted
sprite art. Headless editor play() may not keep is_playing; assigned
current_animation + length is the honest Alternative. screenshots=SKIP.

Generated plugin-validator.json / mcp-tools.json are coordinator-owned
(`npm run generate`). This WP registers verbs in actions.json + the live
TypeScript catalog. No extra codegen pipeline.
"""

from __future__ import annotations

import json
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
TEMP_DIR = PLUGIN_PROJECT / "r5w3"
VENDOR_NEEDLES = plug.VENDOR_NEEDLES
SCHEMA = "hh-godot-variant/1"
SCREENSHOTS = "SKIP"
ANIMATION_MUTATES = (
    "animation.library",
    "animation.animation",
    "animation.track",
    "animation.key",
    "animation.sprite_frames",
    "animation.state_machine",
)
ANIMATION_VERBS = (
    "library",
    "animation",
    "track",
    "key",
    "sprite_frames",
    "state_machine",
    "preview",
)


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def plan_errors(text: str) -> list[str]:
    """Keep R5-WP3 [ ] while unticked; after coordinator tick allow R5-WP4+."""
    errors: list[str] = []
    current = ""
    wp3 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R5-WP3\b", stripped):
            wp3 = stripped
    if wp3 is None:
        return ["plan missing R5-WP3 heading"]
    ticked = bool(re.search(r"\[x\]", wp3, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp3:
            errors.append("R5-WP3 heading must keep [ ] until coordinator tick")
        if current != "R5-WP3":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R5-WP3 while WP3 is unticked)")
    elif not re.match(r"^R5-WP([4-9]|\d{2,})$|^R[6-9]-WP\d+$|^RX-WP\d+$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R5-WP4+ after R5-WP3 tick)")
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
        errors.append("official test must record PlaceholderTexture2D / Play Alternatives honestly")
    if "play.start" in self_text and "paper-ACK" not in self_text:
        errors.append("official test must refuse to paper-ACK play.start")
    if "current_animation" not in self_text or "is_playing" not in self_text:
        errors.append("official test must encode editor preview readback")
    if "current_animation_position" not in self_text:
        errors.append("official test must encode current_animation_position")
    if "PlaceholderTexture2D" not in self_text:
        errors.append("official test must name PlaceholderTexture2D as the missing-art Alternative")
    if "add_transition" not in self_text and "state_machine" not in self_text:
        errors.append("official test must encode AnimationTree state machine")
    if "g2_" + "signed" in self_text or "G2" + " VISIBLE" in self_text:
        errors.append("official test must stay independent of the visible gate")
    if "res://" + "snake" in self_text or "kho" + "-bi-an" in self_text:
        errors.append("official test must stay independent of demo game trees")
    if "skip-PASS" not in self_text and "No skip-PASS" not in self_text:
        errors.append("official test must refuse skip-PASS")
    if re.search(r"int\([^)]+\bor\b[^)]+\)", self_text):
        errors.append("official test must use .get for track/frame that can be 0")

    router = (ADDON / "core" / "hh_router.gd").read_text(encoding="utf-8")
    if "hh_animation_adapter" not in router:
        errors.append("router must dispatch through hh_animation_adapter")
    if "godot.animation" not in router:
        errors.append("router must name godot.animation")

    adapter = ADDON / "core" / "hh_animation_adapter.gd"
    if not adapter.is_file():
        errors.append("missing hh_animation_adapter.gd")
    else:
        text = adapter.read_text(encoding="utf-8")
        for needle in (
            "add_animation",
            "add_frame",
            "set_animation_speed",
            "set_animation_loop",
            "get_frame_count",
            "add_animation_library",
            "get_animation_library",
            "add_track",
            "track_set_path",
            "track_insert_key",
            "track_get_key_value",
            "TYPE_VALUE",
            "TYPE_METHOD",
            "TYPE_AUDIO",
            "TYPE_BEZIER",
            "add_node",
            "add_transition",
            "current_animation",
            "is_playing",
            "current_animation_position",
            "UNDO_ACTION_PREFIX",
            "create_action",
        ):
            if needle not in text:
                errors.append(f"animation adapter must use {needle}")
        if re.search(r"\bcallv\b", text) or "Object.call" in text or "evaluate_expression" in text:
            errors.append("animation adapter has a generic invoke path")
        if "Vector2(32, 32)" in text:
            errors.append("animation adapter must not invent a 32px box")
        if "get_start_node" in text or "set_start_node" in text:
            errors.append("AnimationNodeStateMachine must not call removed 4.7 start-node APIs")
        if "plugin-validator" not in text and "coordinator" not in text:
            errors.append("animation adapter must note coordinator-owned generated catalog")
        if "Alternative" not in text:
            errors.append("animation adapter must label headless is_playing Alternative honestly")

    reads = (ADDON / "core" / "hh_read_adapters.gd").read_text(encoding="utf-8")
    if "no proven playback getter" in reads:
        errors.append("animation.preview stub must be replaced with engine readback")
    if "hh_animation_adapter" not in reads and "current_animation" not in reads:
        errors.append("read adapter must keep a real animation.preview getter")

    overlay = (ADDON / "ui" / "overlay" / "hh_overlay.gd").read_text(encoding="utf-8")
    if "godot.animation" not in overlay or 'action == "key"' not in overlay:
        errors.append("overlay must treat godot.animation key/track as presentable")

    if not ACTIONS_JSON.is_file():
        errors.append("missing actions.json")
    else:
        catalog = json.loads(ACTIONS_JSON.read_text(encoding="utf-8"))
        actions = catalog.get("actions") if isinstance(catalog.get("actions"), dict) else {}
        for action_id, method, verb in (
            ("animation.library", "godot.animation", "library"),
            ("animation.animation", "godot.animation", "animation"),
            ("animation.track", "godot.animation", "track"),
            ("animation.key", "godot.animation", "key"),
            ("animation.sprite_frames", "godot.animation", "sprite_frames"),
            ("animation.state_machine", "godot.animation", "state_machine"),
            ("animation.preview", "godot.animation", "preview"),
        ):
            spec = actions.get(action_id) if isinstance(actions.get(action_id), dict) else {}
            if spec.get("method") != method or spec.get("verb") != verb:
                errors.append(f"actions.json missing {action_id}")

    lifecycle = (BRIDGE / "src" / "ledger" / "scene_lifecycle.ts").read_text(encoding="utf-8")
    if "ANIMATION_APPLY" not in lifecycle or "isAnimationApply" not in lifecycle:
        errors.append("scene_lifecycle must export ANIMATION_APPLY / isAnimationApply")
    if "isAnimationApply(actionId)" not in lifecycle:
        errors.append("isProvenEditorApply must include isAnimationApply")
    for action_id in ANIMATION_MUTATES:
        if action_id not in lifecycle:
            errors.append(f"isProvenEditorApply must list {action_id}")

    execute = (BRIDGE / "src" / "ledger" / "execute.ts").read_text(encoding="utf-8")
    if "function animationApplyOk" not in execute:
        errors.append("execute.ts must postcondition-check animation apply")
    if "const animationFail = animationApplyOk" not in execute:
        errors.append("execute.ts must call animationApplyOk from applyMutateOnce")
    if "animation node_path bind mismatch" not in execute:
        errors.append("execute.ts must bind animation node_path")
    if "animation name bind mismatch" not in execute:
        errors.append("execute.ts must bind animation name")
    if "animation track index bind mismatch" not in execute:
        errors.append("execute.ts must bind track index")
    if "animation key time bind mismatch" not in execute:
        errors.append("execute.ts must bind key time")
    if "animation key count mismatch" not in execute:
        errors.append("execute.ts must bind key count")

    resources = (BRIDGE / "src" / "resources" / "mcp_resources.ts").read_text(encoding="utf-8")
    if "isAnimationApply(def.id)" not in resources or '"animation"' not in resources:
        errors.append("mcp_resources.ts must label animation apply as the animation adapter")

    validator = json.loads((BRIDGE / "generated" / "plugin-validator.json").read_text(encoding="utf-8"))
    validator_actions = validator.get("actions") if isinstance(validator.get("actions"), dict) else {}
    for action_id, method, verb in (
        ("animation.library", "godot.animation", "library"),
        ("animation.animation", "godot.animation", "animation"),
        ("animation.track", "godot.animation", "track"),
        ("animation.key", "godot.animation", "key"),
        ("animation.sprite_frames", "godot.animation", "sprite_frames"),
        ("animation.state_machine", "godot.animation", "state_machine"),
        ("animation.preview", "godot.animation", "preview"),
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
    domain = tool_enums.get("godot.animation", [])
    for verb in ANIMATION_VERBS:
        if verb not in domain:
            errors.append(f"mcp-tools.json godot.animation must enum {verb}")
    if "godot.animation" not in tool_enums:
        errors.append("mcp-tools.json must expose godot.animation as a domain tool")

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


def live_errors(exe: Path) -> list[str]:
    errors: list[str] = []
    cleanup_temp()
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    proc: subprocess.Popen[str] | None = None
    godot: subprocess.Popen[str] | None = None
    desc_path: Path | None = None
    secret = ""
    err_lines: list[str] = []
    godot_lines: list[str] = []
    scene = "res://r5w3/actor.tscn"
    frames = "res://r5w3/frames.tres"
    tex_a = "res://r5w3/frame_a.tres"
    tex_b = "res://r5w3/frame_b.tres"
    req_id = 2
    # Honest Alternative: missing painted sprite art uses PlaceholderTexture2D.
    # Preview is editor AnimationPlayer readback, not Play.
    # screenshots=SKIP — do not write a fake PNG. Do not paper-ACK play.start.
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

        req_id, created = tool_call(proc, req_id, "godot.scene", "create", {"path": scene, "root_class": "Node2D"})
        if not ack_ok(created, errors, "scene.create"):
            return errors

        for class_name, name in (
            ("AnimatedSprite2D", "Sprite"),
            ("AnimationPlayer", "Anim"),
            ("AnimationTree", "Tree"),
        ):
            req_id, added = tool_call(
                proc,
                req_id,
                "godot.node",
                "add",
                {"scene": scene, "parent": ".", "class_name": class_name, "name": name},
            )
            if not ack_ok(added, errors, f"node.add {name} {class_name}"):
                return errors

        for tex in (tex_a, tex_b):
            req_id, tex_created = tool_call(
                proc, req_id, "godot.resource", "create", {"path": tex, "class_name": "PlaceholderTexture2D"}
            )
            if not ack_ok(tex_created, errors, "resource.create PlaceholderTexture2D"):
                return errors
            req_id, tex_sized = tool_call(
                proc,
                req_id,
                "godot.resource",
                "edit",
                {"path": tex, "property": "size", "value": variant("Vector2", {"x": 16, "y": 16})},
            )
            if not ack_ok(tex_sized, errors, "resource.edit PlaceholderTexture2D.size"):
                return errors

        for clip in ("idle", "walk", "interact"):
            req_id, framed = tool_call(
                proc,
                req_id,
                "godot.animation",
                "sprite_frames",
                {
                    "scene": scene,
                    "node_path": "Sprite",
                    "animation": clip,
                    "path": frames,
                    "op": "add_animation",
                    "speed": 8,
                    "loop": True,
                    "frames": [
                        {"texture": tex_a, "duration": 1.0},
                        {"texture": tex_b, "duration": 1.0},
                    ],
                },
            )
            if not ack_ok(framed, errors, f"animation.sprite_frames {clip}"):
                return errors
            fa = framed.get("after") or {}
            if fa.get("has_animation") is not True:
                errors.append(f"sprite_frames {clip} has_animation: {fa}")
            if int(fa.get("frame_count", -1)) < 2:
                errors.append(f"sprite_frames {clip} needs >1 frame: {fa}")
            if not str(framed.get("undo_action") or "").startswith("Agent: "):
                errors.append(f"sprite_frames missing Agent undo: {framed}")

        req_id, lib = tool_call(
            proc,
            req_id,
            "godot.animation",
            "library",
            {"scene": scene, "node_path": "Anim", "library": "player"},
        )
        if not ack_ok(lib, errors, "animation.library"):
            return errors
        if (lib.get("after") or {}).get("library") != "player":
            errors.append(f"animation.library bind: {lib}")

        for clip, length in (("idle", 0.4), ("walk", 0.4), ("interact", 0.4)):
            req_id, clip_body = tool_call(
                proc,
                req_id,
                "godot.animation",
                "animation",
                {
                    "scene": scene,
                    "node_path": "Anim",
                    "name": clip,
                    "length_sec": length,
                    "library": "player",
                    "loop": True,
                },
            )
            if not ack_ok(clip_body, errors, f"animation.animation {clip}"):
                return errors
            if (clip_body.get("after") or {}).get("has_animation") is not True:
                errors.append(f"animation.animation {clip}: {clip_body}")

        req_id, tracked = tool_call(
            proc,
            req_id,
            "godot.animation",
            "track",
            {
                "scene": scene,
                "node_path": "Anim",
                "animation": "walk",
                "library": "player",
                "track_path": "Sprite:position",
                "track_type": "value",
            },
        )
        if not ack_ok(tracked, errors, "animation.track"):
            return errors
        track_after = tracked.get("after") or {}
        if track_after.get("track") != 0:
            errors.append(f"animation.track index bind: {track_after}")
        if track_after.get("track_path") != "Sprite:position":
            errors.append(f"animation.track path bind: {track_after}")

        req_id, keyed = tool_call(
            proc,
            req_id,
            "godot.animation",
            "key",
            {
                "scene": scene,
                "node_path": "Anim",
                "animation": "walk",
                "library": "player",
                "track": 0,
                "time_sec": 0.0,
                "value": variant("Vector2", {"x": 0, "y": 0}),
                "keys": [
                    {"time_sec": 0.0, "value": variant("Vector2", {"x": 0, "y": 0})},
                    {"time_sec": 0.2, "value": variant("Vector2", {"x": 16, "y": 0})},
                ],
            },
        )
        if not ack_ok(keyed, errors, "animation.key batch"):
            return errors
        key_after = keyed.get("after") or {}
        if key_after.get("track") != 0:
            errors.append(f"animation.key track bind: {key_after}")
        if int(key_after.get("key_count", -1)) < 2:
            errors.append(f"animation.key count bind: {key_after}")
        if key_after.get("readback_equals") is not True:
            errors.append(f"animation.key readback: {key_after}")
        if not str(keyed.get("undo_action") or "").startswith("Agent: "):
            errors.append(f"animation.key missing Agent undo: {keyed}")
        if "animation.key" not in str(keyed.get("undo_action") or ""):
            errors.append(f"key batch must be one Agent UndoRedo: {keyed}")
        before_keys = int(key_after.get("key_count", -1))

        req_id, previewed = tool_call(
            proc,
            req_id,
            "godot.animation",
            "preview",
            {"scene": scene, "node_path": "Anim", "animation": "walk", "library": "player"},
        )
        if not ack_ok(previewed, errors, "animation.preview"):
            return errors
        prv = previewed.get("after") or {}
        current = str(prv.get("current_animation") or "")
        if current != "walk" and not current.endswith("/walk"):
            errors.append(f"preview current_animation bind: {prv}")
        if "is_playing" not in prv:
            errors.append(f"preview missing is_playing readback: {prv}")
        if "current_animation_position" not in prv:
            errors.append(f"preview missing current_animation_position: {prv}")
        if float(prv.get("length") or 0) <= 0:
            errors.append(f"preview missing animation length: {prv}")
        if prv.get("is_playing") is True:
            pass
        elif prv.get("playing_alternative") is True or "Alternative" in str(prv.get("alternative") or ""):
            pass
        else:
            errors.append(f"headless is_playing Alternative must be labeled honestly: {prv}")
        if prv.get("is_playing") is True and prv.get("playing_alternative") is True:
            errors.append(f"must not invent playing=true Alternative: {prv}")

        req_id, undone = tool_call(proc, req_id, "godot.node", "undo", {"scene": scene, "count": 1})
        if not ack_ok(undone, errors, "node.undo after key batch"):
            errors.append(f"one-undo after key batch must ACK: {undone}")
        req_id, after_undo = tool_call(
            proc,
            req_id,
            "godot.animation",
            "preview",
            {
                "scene": scene,
                "node_path": "Anim",
                "animation": "walk",
                "library": "player",
                "include_keys": True,
            },
        )
        if ack_ok(after_undo, errors, "preview after key undo"):
            undo_after = after_undo.get("after") or {}
            if int(undo_after.get("key_count", before_keys)) >= before_keys:
                errors.append(f"one UndoRedo key batch undo did not drop keys: {after_undo}")

        req_id, redone = tool_call(proc, req_id, "godot.node", "redo", {"scene": scene, "count": 1})
        if not ack_ok(redone, errors, "node.redo after key undo"):
            errors.append(f"one-redo after key undo must ACK: {redone}")

        req_id, machine = tool_call(
            proc,
            req_id,
            "godot.animation",
            "state_machine",
            {
                "scene": scene,
                "node_path": "Tree",
                "from": "idle",
                "to": "walk",
                "condition": "is_walking",
                "switch_mode": "immediate",
                "anim_player": "Anim",
            },
        )
        if not ack_ok(machine, errors, "animation.state_machine"):
            return errors
        sm_after = machine.get("after") or {}
        if sm_after.get("from") != "idle" or sm_after.get("to") != "walk":
            errors.append(f"state_machine from/to bind: {sm_after}")
        if sm_after.get("has_transition") is not True:
            errors.append(f"state_machine transition missing: {sm_after}")
        if sm_after.get("condition") != "is_walking":
            errors.append(f"state_machine condition bind: {sm_after}")

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

        req_id, q_after = tool_call(
            proc,
            req_id,
            "godot.animation",
            "preview",
            {"scene": scene, "node_path": "Anim", "animation": "walk", "library": "player", "include_keys": True},
        )
        if ack_ok(q_after, errors, "preview after reload"):
            reopened = q_after.get("after") or {}
            if int(reopened.get("key_count", -1)) < 2:
                errors.append(f"save/reopen lost walk keys: {reopened}")
            current2 = str(reopened.get("current_animation") or "")
            if current2 != "walk" and not current2.endswith("/walk"):
                errors.append(f"save/reopen preview current_animation: {reopened}")

        if _screenshots != "SKIP":
            errors.append("animation screenshot Alternative must stay screenshots=SKIP")
        if secret and secret in "".join(err_lines):
            errors.append("session secret appeared in sidecar logs")
        if secret and secret in "".join(godot_lines):
            errors.append("session secret appeared in Godot logs")
    except Exception as exc:  # noqa: BLE001
        errors.append(sess.redact(f"live animation failed: {type(exc).__name__}: {exc}", secret))
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
        print("FAIL: animation", file=sys.stderr)
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
        print("FAIL: animation", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print(
        "PASS: SpriteFrames/AnimationPlayer/AnimationTree adapters; idle/walk/interact, "
        f"value keys, state-machine condition, editor preview, one-undo; screenshots={SCREENSHOTS} Alternative; "
        "plan progress consistent."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
