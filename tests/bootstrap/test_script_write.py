#!/usr/bin/env python3
"""R3-WP5: script write/patch/validate/attach + dirty-buffer conflict.

Does not tick the 20-8 plan. Does not start R3-WP6.
Pin missing is a hard FAIL. No skip-PASS.
"""

from __future__ import annotations

import hashlib
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
PINNED_VERSION = plug.PINNED_VERSION
TEMP_DIR = PLUGIN_PROJECT / "r3w5"
VENDOR_NEEDLES = plug.VENDOR_NEEDLES

PLAYER = (
    "extends Node2D\n"
    "\n"
    "func speed() -> int:\n"
    "	return 80\n"
    "\n"
    "func ready_hint() -> String:\n"
    "	return \"ok\"\n"
)

NAMED = (
    "class_name R3W5Named\n"
    "extends Node2D\n"
    "\n"
    "func speed() -> int:\n"
    "	return 80\n"
)

NAMED_NEXT = (
    "class_name R3W5Named\n"
    "extends Node2D\n"
    "\n"
    "func speed() -> int:\n"
    "	return 240\n"
)

INVALID = "extends Node2D\n\nfunc broken( -> void:\n	pass\n"

PATCH_LINE = "	return 80\n"
PATCH_NEXT = "	return 120\n"

RANGE_SRC = (
    "extends Node2D\n"
    "\n"
    "func first() -> int:\n"
    "	return 7\n"
    "\n"
    "func second() -> int:\n"
    "	return 7\n"
)


def big_script() -> str:
    parts = [
        "extends Node2D\n",
        "\n",
        "func speed() -> int:\n",
        "	return 80\n",
        "\n",
    ]
    i = 0
    while sum(len(part) for part in parts) <= 4000:
        parts.append("func pad_%d() -> int:\n" % i)
        parts.append("	return %d\n" % i)
        parts.append("\n")
        i += 1
    return "".join(parts)


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def plan_errors(text: str) -> list[str]:
    """Keep R3-WP5 [ ] while unticked; after coordinator tick allow R3-WP6+."""
    errors: list[str] = []
    current = ""
    wp5 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R3-WP5\b", stripped):
            wp5 = stripped
    if wp5 is None:
        return ["plan missing R3-WP5 heading"]
    ticked = bool(re.search(r"\[x\]", wp5, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp5:
            errors.append("R3-WP5 heading must keep [ ] until coordinator tick")
        if current != "R3-WP5":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R3-WP5 while WP5 is unticked)")
    elif not re.match(r"^R3-WP([6-9]|\d{2,})$|^R[4-9]-WP\d+$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R3-WP6+ after R3-WP5 tick)")
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


def attack_concurrent_edit(path: Path) -> None:
    """Deliberate human/external edit after the plugin wrote the file."""
    blob = path.read_bytes()
    path.write_bytes(blob + b"\n# human-edit\n")


def src_scan_errors() -> list[str]:
    errors: list[str] = []
    for path in (BRIDGE / "src").rglob("*.ts"):
        text = path.read_text(encoding="utf-8", errors="replace")
        posix = rel(path)
        if re.search(r"writeFile(?:Sync)?\([^)]*\.gd", text):
            errors.append(f"{posix} writes a .gd from the sidecar")
        if "ResourceSaver" in text:
            errors.append(f"{posix} uses ResourceSaver")
        for needle in VENDOR_NEEDLES:
            if needle in text:
                errors.append(f"{posix} contains vendor needle {needle!r}")
                break
        if re.search(r"\bcallv\b", text) or "Object.call" in text:
            errors.append(f"{posix} has a generic invoke path")
    self_text = Path(__file__).read_text(encoding="utf-8")
    if re.search(r"\.write_text\([^\n]*\.gd", self_text) and "attack_concurrent_edit" not in self_text:
        errors.append("official test writes a .gd path directly")
    if "attack_concurrent_edit" not in self_text:
        errors.append("official test must isolate human-edit writes")
    router = (ADDON / "core" / "hh_router.gd").read_text(encoding="utf-8")
    if "hh_script_adapter" not in router:
        errors.append("router must dispatch the script adapter")
    if "project.settings must stay" not in router:
        errors.append("unproven-mutate sentinel must move off script.write onto project.settings")
    if "script.write must stay" in router:
        errors.append("script.write sentinel must not remain after R3-WP5")
    script = ADDON / "core" / "hh_script_adapter.gd"
    reads = ADDON / "core" / "hh_read_adapters.gd"
    life_ts = BRIDGE / "src" / "ledger" / "scene_lifecycle.ts"
    if not script.is_file():
        errors.append("missing script adapter")
    else:
        text = script.read_text(encoding="utf-8")
        if "validate" not in text or "reload" not in text:
            errors.append("script adapter must validate GDScript with reload before replace")
        write_fn = re.search(r"func _write\b.*?func _patch\b", text, re.S)
        if write_fn is None:
            errors.append("missing _write")
        else:
            body = write_fn.group(0)
            if "_validate_source" not in body and "validate_source" not in body:
                errors.append("_write must validate BEFORE atomic replace")
            if "_validate_source(contents, res_path)" not in body:
                errors.append("_write must validate against dest resource_path")
            if "_atomic_replace" not in body:
                errors.append("_write must atomic-replace via tmp+rename")
            if "_conflict_gate" not in body:
                errors.append("_write must refuse a dirty ScriptEditor buffer")
        atomic_fn = re.search(r"func _atomic_replace\b.*?func _recover_bak\b", text, re.S)
        if atomic_fn is None:
            errors.append("missing _atomic_replace")
        else:
            atom = atomic_fn.group(0)
            if 'FileAccess.open(dest, FileAccess.WRITE)' in atom or 'FileAccess.open(res_path, FileAccess.WRITE)' in atom:
                errors.append("atomic replace must not FileAccess.WRITE the live .gd")
            if ".tmp" not in atom or "rename_absolute" not in atom:
                errors.append("atomic replace must write path.tmp then rename")
            if "flush" not in atom:
                errors.append("atomic replace must flush the tmp file")
        if "add_do_property" not in text or 'script' not in text:
            errors.append("attach/detach must use UndoRedo add_do_property(node, script)")
        if "UNDO_ACTION_PREFIX" not in text:
            errors.append("attach must name Agent UndoRedo actions")
        if "E_CONFLICT" not in text or "buffer" not in text:
            errors.append("dirty ScriptEditor must return E_CONFLICT")
        if "_reject_packed" not in text or "is_packed_internal" not in text:
            errors.append("attach/detach must refuse packed internals via the same packed reject")
        if "any_open_dirty" not in text:
            errors.append("script.rename must refuse when an open scene is dirty")
        patch_fn = re.search(r"func _patch\b.*?func _attach\b", text, re.S)
        if patch_fn is None:
            errors.append("missing _patch")
        else:
            body = patch_fn.group(0)
            constraint = body.find("_patch_constraint_holds")
            replace_at = body.find("_atomic_replace")
            if constraint < 0 or replace_at < 0 or constraint > replace_at:
                errors.append("range/unrelated-lines constraint must run before _atomic_replace")
            if "_validate_source(next_text, res_path)" not in body:
                errors.append("_patch must validate against dest resource_path")
        val_src = re.search(r"func _validate_source\b.*?func _parse_fail\b", text, re.S)
        if val_src is None:
            errors.append("missing _validate_source")
        else:
            probe_body = val_src.group(0)
            rp = probe_body.find("resource_path")
            rl = probe_body.find("reload(")
            if rp < 0 or rl < 0 or rp > rl:
                errors.append("_validate_source must set probe resource_path to dest before reload")
        if "class_name R3W5Named" not in self_text:
            errors.append("official test must write class_name R3W5Named, not only class_name-less fixtures")
        if 'godot.script", "validate", {"path": named}' not in self_text:
            errors.append("official test must script.validate res://r3w5/named.gd after class_name write/rewrite")
        if re.search(r"\bcallv\b", text) or "Object.call" in text:
            errors.append("script adapter has a generic invoke path")
    meta = ADDON / "core" / "hh_scene_meta.gd"
    if meta.is_file():
        meta_text = meta.read_text(encoding="utf-8")
        if "addons/hh_agent" not in meta_text or "_locked_write" not in meta_text:
            errors.append("plugin jail() must refuse writes under res://addons/hh_agent")
    if reads.is_file():
        read_text = reads.read_text(encoding="utf-8")
        val_fn = re.search(r"func _script_validate\b.*?func _script_open_at\b", read_text, re.S)
        if val_fn is None:
            errors.append("missing _script_validate")
        elif "reload" not in val_fn.group(0):
            errors.append("script.validate must parse via GDScript.reload, not paper after write")
        elif "_parse_gdscript(text, res_path)" not in val_fn.group(0):
            errors.append("script.validate must parse against dest resource_path")
        parse_fn = re.search(r"func _parse_gdscript\b.*?func _script_open_at\b", read_text, re.S)
        if parse_fn is None:
            errors.append("missing _parse_gdscript")
        else:
            probe_body = parse_fn.group(0)
            rp = probe_body.find("resource_path")
            rl = probe_body.find("reload(")
            if rp < 0 or rl < 0 or rp > rl:
                errors.append("_parse_gdscript must set probe resource_path to dest before reload")
            if "has_cached" not in probe_body and "CACHE_MODE_REUSE" not in probe_body:
                errors.append("_parse_gdscript must reuse the loaded dest script when present")
        diag_fn = re.search(r"func _script_diagnostics\b.*?func _script_open_at\b", read_text, re.S)
        if diag_fn is None:
            errors.append("missing _script_diagnostics")
        else:
            diag_body = diag_fn.group(0)
            if "E_UNVERIFIED" not in diag_body:
                errors.append("script.diagnostics must return honest E_UNVERIFIED")
            if re.search(r"\b_ok\s*\(", diag_body):
                errors.append("script.diagnostics must not ACK an empty diagnostics list")
    if life_ts.is_file():
        life_text = life_ts.read_text(encoding="utf-8")
        if "script.write" not in life_text or "isScriptApply" not in life_text:
            errors.append("sidecar must treat script.write as a proven apply verb")
        if 'actionId === "script.write"' not in life_text:
            errors.append("mutationNeedsDiskHash must cover script.write")
    execute = (BRIDGE / "src" / "ledger" / "execute.ts").read_text(encoding="utf-8")
    if "scriptApplyOk" not in execute:
        errors.append("ledger must verify script write/attach postconditions")
    shapes = (BRIDGE / "src" / "registry" / "shapes.ts").read_text(encoding="utf-8")
    if "SCRIPT_TEXT" not in shapes or "262144" not in shapes:
        errors.append("shapes.ts must define SCRIPT_TEXT with a 262144-char cap")
    if re.search(r"export const TEXT:[\s\S]*?maxLength:\s*4000", shapes) is None:
        errors.append("short TEXT must stay 4000 for non-script fields")
    actions_ts = (BRIDGE / "src" / "registry" / "actions.ts").read_text(encoding="utf-8")
    write_block = re.search(r'"script\.write":[\s\S]*?"script\.patch":', actions_ts)
    patch_block = re.search(r'"script\.patch":[\s\S]*?"script\.validate":', actions_ts)
    if write_block is None or "SCRIPT_TEXT" not in write_block.group(0):
        errors.append("script.write contents must use SCRIPT_TEXT, not short TEXT")
    if patch_block is None or "SCRIPT_TEXT" not in patch_block.group(0):
        errors.append("script.patch find/replace must use SCRIPT_TEXT, not short TEXT")
    for path in ADDON.rglob("*.gd"):
        text = path.read_text(encoding="utf-8", errors="replace")
        if re.search(r"\bcallv\b", text) or "Object.call" in text:
            errors.append(f"{rel(path)} has a generic invoke path")
            break
    return errors


def mcp_call(proc: subprocess.Popen[str], req_id: int, name: str, arguments: dict, timeout: float = 40.0) -> dict:
    return life.mcp_call(proc, req_id, name, arguments, timeout)


def body_of(resp: dict) -> dict:
    return life.body_of(resp)


def tool_call(
    proc: subprocess.Popen[str],
    req_id: int,
    tool: str,
    action: str,
    params: dict,
    timeout: float = 40.0,
    precondition: dict | None = None,
) -> tuple[int, dict]:
    cid = life.new_ulid()
    args: dict = {"action": action, "params": params, "command_id": cid}
    if precondition:
        args["precondition"] = precondition
    resp = mcp_call(proc, req_id, tool, args, timeout)
    return req_id + 1, body_of(resp)


def ack_ok(body: dict, errors: list[str], verb: str, undo: bool = False) -> bool:
    if body.get("ok") is not True:
        errors.append(f"{verb} must ACK: {body}")
        return False
    post = body.get("postcondition") or {}
    if post.get("verified") is not True or not post.get("checks"):
        errors.append(f"{verb} paper postcondition: {body}")
        return False
    if undo:
        name = str(body.get("undo_action") or "")
        if not name.startswith("Agent:"):
            errors.append(f"{verb} missing Agent undo_action: {body}")
            return False
    return True


def expect_code(body: dict, codes: tuple[str, ...], errors: list[str], label: str) -> None:
    got = str((body.get("error") or {}).get("code") or "")
    if body.get("ok") is True or got not in codes:
        errors.append(f"{label} expected {codes}, got {body}")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def has_bom(path: Path) -> bool:
    blob = path.read_bytes()
    return blob.startswith(b"\xef\xbb\xbf")


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
    player = "res://r3w5/player.gd"
    other = "res://r3w5/other.gd"
    hero = "res://r3w5/hero.gd"
    scene = "res://r3w5/main.tscn"
    player_abs = life.res_to_abs(player)
    other_abs = life.res_to_abs(other)
    hero_abs = life.res_to_abs(hero)
    req_id = 2
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

        jail = body_of(
            mcp_call(
                proc,
                req_id,
                "godot.script",
                {
                    "action": "write",
                    "params": {"path": "res://../escape.gd", "contents": "extends Node"},
                    "command_id": life.new_ulid(),
                },
            )
        )
        req_id += 1
        expect_code(jail, ("E_PATH",), errors, "escaped script path")

        addon_write = body_of(
            mcp_call(
                proc,
                req_id,
                "godot.script",
                {
                    "action": "write",
                    "params": {
                        "path": "res://addons/hh_agent/r3w5_attack.gd",
                        "contents": PLAYER,
                    },
                    "command_id": life.new_ulid(),
                },
            )
        )
        req_id += 1
        expect_code(
            addon_write,
            ("E_PATH", "E_OUT_OF_BOUNDS"),
            errors,
            "script.write into addons/hh_agent",
        )
        attack_abs = ADDON / "r3w5_attack.gd"
        if attack_abs.is_file():
            errors.append("script.write into addons/hh_agent created a file")
            try:
                attack_abs.unlink()
            except OSError:
                pass

        req_id, created = tool_call(
            proc, req_id, "godot.script", "write", {"path": player, "contents": PLAYER}
        )
        if not ack_ok(created, errors, "script.write new"):
            return errors
        if not player_abs.is_file():
            errors.append("script.write did not create player.gd")
            return errors
        disk = player_abs.read_bytes()
        if disk != PLAYER.encode("utf-8"):
            errors.append(f"disk bytes != write contents: {disk!r}")
        if has_bom(player_abs):
            errors.append("script.write left a UTF-8 BOM")
        after_hash = str((created.get("after") or {}).get("disk_hash") or "")
        if after_hash != sha256_file(player_abs) or after_hash != sha256_text(PLAYER):
            errors.append(f"write disk SHA mismatch: {created} vs {sha256_file(player_abs)}")

        named = "res://r3w5/named.gd"
        named_abs = life.res_to_abs(named)
        req_id, named_body = tool_call(
            proc, req_id, "godot.script", "write", {"path": named, "contents": NAMED}
        )
        if not ack_ok(named_body, errors, "script.write class_name R3W5Named"):
            return errors
        if not named_abs.is_file() or named_abs.read_bytes() != NAMED.encode("utf-8"):
            errors.append("class_name R3W5Named write did not persist equal disk bytes")
            return errors
        req_id, named_again = tool_call(
            proc, req_id, "godot.script", "write", {"path": named, "contents": NAMED_NEXT}
        )
        if not ack_ok(named_again, errors, "script.write class_name R3W5Named again"):
            return errors
        if named_abs.read_bytes() != NAMED_NEXT.encode("utf-8"):
            errors.append(f"second class_name write disk mismatch: {named_abs.read_bytes()!r}")
            return errors
        req_id, named_validated = tool_call(
            proc, req_id, "godot.script", "validate", {"path": named}
        )
        if not ack_ok(named_validated, errors, "script.validate class_name R3W5Named"):
            return errors
        req_id, named_patched = tool_call(
            proc,
            req_id,
            "godot.script",
            "patch",
            {"path": named, "find": "	return 240\n", "replace": "	return 241\n"},
        )
        if not ack_ok(named_patched, errors, "script.patch class_name R3W5Named"):
            return errors
        named_disk = named_abs.read_bytes()
        if b"return 241" not in named_disk or b"class_name R3W5Named" not in named_disk:
            errors.append(f"class_name patch did not persist new text: {named_disk!r}")
            return errors

        req_id, validated = tool_call(proc, req_id, "godot.script", "validate", {"path": player})
        if not ack_ok(validated, errors, "script.validate"):
            return errors
        req_id, diags = tool_call(proc, req_id, "godot.script", "diagnostics", {"path": player})
        expect_code(diags, ("E_UNVERIFIED",), errors, "script.diagnostics")

        big = big_script()
        if len(big) <= 4000:
            errors.append("big_script helper is not longer than 4000 chars")
            return errors
        big_path = "res://r3w5/big.gd"
        big_abs = life.res_to_abs(big_path)
        req_id, big_body = tool_call(
            proc, req_id, "godot.script", "write", {"path": big_path, "contents": big}
        )
        if not ack_ok(big_body, errors, "script.write >4000 chars"):
            return errors
        if not big_abs.is_file() or big_abs.read_bytes() != big.encode("utf-8"):
            errors.append("script.write >4000 did not persist equal disk bytes")
            return errors

        before_invalid = player_abs.read_bytes()
        req_id, bad = tool_call(
            proc, req_id, "godot.script", "write", {"path": player, "contents": INVALID}
        )
        expect_code(bad, ("E_INVALID_TYPE", "E_INVALID_VARIANT"), errors, "invalid script.write")
        if player_abs.read_bytes() != before_invalid:
            errors.append("invalid script.write overwrote the previous good file")
        if has_bom(player_abs):
            errors.append("failed write corrupted encoding")

        req_id, opened = tool_call(
            proc, req_id, "godot.script", "open_at", {"path": player, "line": 3}
        )
        if not ack_ok(opened, errors, "script.open_at"):
            return errors

        req_id, staged = tool_call(
            proc,
            req_id,
            "godot.script",
            "patch",
            {"path": player, "find": "return 80", "replace": "return 99", "buffer_only": True},
        )
        if not ack_ok(staged, errors, "script.patch buffer_only"):
            return errors
        if player_abs.read_bytes() != before_invalid:
            errors.append("buffer_only patch wrote the live .gd")
        buffer_hash = str((staged.get("after") or {}).get("buffer_hash") or "")

        req_id, conflict = tool_call(
            proc, req_id, "godot.script", "write", {"path": player, "contents": PLAYER}
        )
        expect_code(conflict, ("E_CONFLICT",), errors, "dirty script.write without buffer hash")
        if player_abs.read_bytes() != before_invalid:
            errors.append("dirty script.write overwrote unsaved / disk contents")

        if buffer_hash:
            req_id, restored = tool_call(
                proc,
                req_id,
                "godot.script",
                "write",
                {"path": player, "contents": PLAYER, "expected_hash": buffer_hash},
            )
            if not ack_ok(restored, errors, "script.write matching buffer hash"):
                return errors
        else:
            errors.append("buffer_only patch did not return buffer_hash")
            return errors

        if player_abs.read_bytes() != PLAYER.encode("utf-8"):
            errors.append("restore write did not put original contents back")

        before_patch = player_abs.read_bytes()
        req_id, patched = tool_call(
            proc,
            req_id,
            "godot.script",
            "patch",
            {"path": player, "find": PATCH_LINE, "replace": PATCH_NEXT},
        )
        if not ack_ok(patched, errors, "script.patch find/replace"):
            return errors
        after_patch = player_abs.read_bytes()
        expected_patch = before_patch.replace(PATCH_LINE.encode("utf-8"), PATCH_NEXT.encode("utf-8"), 1)
        if after_patch != expected_patch:
            errors.append(f"patch was not surgical: {after_patch!r}")
        if b"return \"ok\"" not in after_patch:
            errors.append("patch dropped an unrelated line")
        if has_bom(player_abs):
            errors.append("patch introduced a BOM")

        range_path = "res://r3w5/range.gd"
        range_abs = life.res_to_abs(range_path)
        req_id, range_write = tool_call(
            proc, req_id, "godot.script", "write", {"path": range_path, "contents": RANGE_SRC}
        )
        if not ack_ok(range_write, errors, "script.write range source"):
            return errors
        before_range = range_abs.read_bytes()
        req_id, range_patched = tool_call(
            proc,
            req_id,
            "godot.script",
            "patch",
            {
                "path": range_path,
                "find": "	return 7\n",
                "replace": "	return 9\n",
                "start_line": 7,
                "end_line": 7,
            },
        )
        if not ack_ok(range_patched, errors, "script.patch range second match"):
            return errors
        after_range = range_abs.read_text(encoding="utf-8")
        if after_range.count("return 7") != 1 or after_range.count("return 9") != 1:
            errors.append(f"range patch was not surgical: {after_range!r}")
        if b"func first()" not in after_range.encode("utf-8"):
            errors.append("range patch dropped an unrelated function")
        if before_range == range_abs.read_bytes():
            errors.append("range patch did not change dest")

        req_id, other_body = tool_call(
            proc, req_id, "godot.script", "write", {"path": other, "contents": PLAYER}
        )
        if not ack_ok(other_body, errors, "script.write other"):
            return errors
        other_hash = sha256_file(other_abs)
        attack_concurrent_edit(other_abs)
        attacked = other_abs.read_bytes()
        req_id, raced = tool_call(
            proc,
            req_id,
            "godot.script",
            "write",
            {"path": other, "contents": PLAYER, "expected_hash": other_hash},
        )
        expect_code(raced, ("E_CONFLICT",), errors, "concurrent human edit script.write")
        if other_abs.read_bytes() != attacked:
            errors.append("concurrent-edit write changed disk")

        req_id, scene_body = tool_call(
            proc, req_id, "godot.scene", "create", {"path": scene, "root_class": "Node2D"}
        )
        if not ack_ok(scene_body, errors, "scene.create"):
            return errors
        req_id, added = tool_call(
            proc,
            req_id,
            "godot.node",
            "add",
            {"scene": scene, "parent": ".", "class_name": "Node2D", "name": "Player"},
        )
        if not ack_ok(added, errors, "node.add Player", undo=True):
            return errors

        prefab = "res://r3w5/prefab.tscn"
        req_id, prefab_body = tool_call(
            proc, req_id, "godot.scene", "create", {"path": prefab, "root_class": "Node2D"}
        )
        if not ack_ok(prefab_body, errors, "scene.create prefab"):
            return errors
        req_id, body_added = tool_call(
            proc,
            req_id,
            "godot.node",
            "add",
            {"scene": prefab, "parent": ".", "class_name": "Node2D", "name": "Body"},
        )
        if not ack_ok(body_added, errors, "node.add Body", undo=True):
            return errors
        req_id, prefab_saved = tool_call(proc, req_id, "godot.scene", "save", {"path": prefab})
        if not ack_ok(prefab_saved, errors, "scene.save prefab"):
            return errors
        req_id, opened_main = tool_call(proc, req_id, "godot.scene", "open", {"path": scene})
        if not ack_ok(opened_main, errors, "scene.open main"):
            return errors
        req_id, inst = tool_call(
            proc,
            req_id,
            "godot.scene",
            "instantiate",
            {"scene": scene, "packed": prefab, "parent": "."},
        )
        if not ack_ok(inst, errors, "scene.instantiate prefab", undo=True):
            return errors
        inst_path = str((inst.get("after") or {}).get("path") or "")
        if not inst_path or inst_path == ".":
            errors.append(f"instantiate missing instance path: {inst}")
            return errors
        req_id, packed_attach = tool_call(
            proc,
            req_id,
            "godot.script",
            "attach",
            {"scene": scene, "node_path": f"{inst_path}/Body", "path": player},
        )
        expect_code(packed_attach, ("E_CONFLICT",), errors, "packed script.attach without make_local")

        req_id, attached = tool_call(
            proc,
            req_id,
            "godot.script",
            "attach",
            {"scene": scene, "node_path": "Player", "path": player},
        )
        if not ack_ok(attached, errors, "script.attach", undo=True):
            return errors
        req_id, got = tool_call(
            proc, req_id, "godot.property", "get", {"scene": scene, "node_path": "Player", "property": "script"}
        )
        if not ack_ok(got, errors, "property.get script"):
            return errors
        script_val = ((got.get("after") or {}).get("value") or {}).get("value") or {}
        if not isinstance(script_val, dict) or player not in str(script_val.get("path") or ""):
            errors.append(f"property.get script path mismatch: {got}")

        req_id, undid = tool_call(
            proc, req_id, "godot.node", "undo", {"scene": scene, "count": 1}
        )
        if not ack_ok(undid, errors, "node.undo detach"):
            return errors
        req_id, got2 = tool_call(
            proc, req_id, "godot.property", "get", {"scene": scene, "node_path": "Player", "property": "script"}
        )
        if not ack_ok(got2, errors, "property.get script after undo"):
            return errors
        script_val2 = ((got2.get("after") or {}).get("value") or {}).get("value")
        if script_val2 not in (None, {}) and str((script_val2 or {}).get("path") or ""):
            errors.append(f"undo did not detach script: {got2}")

        req_id, attached2 = tool_call(
            proc,
            req_id,
            "godot.script",
            "attach",
            {"scene": scene, "node_path": "Player", "path": player},
        )
        if not ack_ok(attached2, errors, "script.attach again", undo=True):
            return errors
        req_id, dirty_rename = tool_call(
            proc, req_id, "godot.script", "rename", {"path": player, "name": "hero"}
        )
        expect_code(dirty_rename, ("E_CONFLICT",), errors, "script.rename while scene dirty")
        if not player_abs.is_file() or hero_abs.is_file():
            errors.append("dirty script.rename rewrote paths")
            return errors
        req_id, saved_main = tool_call(proc, req_id, "godot.scene", "save", {"path": scene})
        if not ack_ok(saved_main, errors, "scene.save before rename"):
            return errors
        req_id, renamed = tool_call(
            proc, req_id, "godot.script", "rename", {"path": player, "name": "hero"}
        )
        if not ack_ok(renamed, errors, "script.rename"):
            return errors
        if player_abs.is_file():
            errors.append("rename left the old player.gd")
        if not hero_abs.is_file():
            errors.append("rename did not create hero.gd")
        req_id, got3 = tool_call(
            proc, req_id, "godot.property", "get", {"scene": scene, "node_path": "Player", "property": "script"}
        )
        if ack_ok(got3, errors, "property.get script after rename"):
            script_val3 = ((got3.get("after") or {}).get("value") or {}).get("value") or {}
            path_s = str(script_val3.get("path") or "") if isinstance(script_val3, dict) else ""
            if hero not in path_s and player in path_s:
                scene_abs = life.res_to_abs(scene)
                scene_txt = scene_abs.read_text(encoding="utf-8") if scene_abs.is_file() else ""
                if hero not in scene_txt:
                    errors.append(f"rename did not rewrite refs: get={got3} scene={scene_txt[:400]}")

        req_id, settings = tool_call(
            proc,
            req_id,
            "godot.project",
            "settings",
            {
                "key": "application/config/name",
                "value": {"schema": "hh-godot-variant/1", "type": "int", "value": 1},
            },
        )
        expect_code(settings, ("E_UNVERIFIED",), errors, "unproven project.settings")

        paused = body_of(mcp_call(proc, req_id, "hh.pause", {}))
        req_id += 1
        if paused.get("ok") is not True:
            errors.append(f"hh.pause failed: {paused}")
        req_id, paused_write = tool_call(
            proc, req_id, "godot.script", "write", {"path": "res://r3w5/paused.gd", "contents": PLAYER}
        )
        expect_code(paused_write, ("E_PAUSED",), errors, "paused script.write")

        if secret and secret in "".join(err_lines):
            errors.append("session secret appeared in sidecar logs")
        if secret and secret in "".join(godot_lines):
            errors.append("session secret appeared in Godot logs")
    except Exception as exc:  # noqa: BLE001
        errors.append(sess.redact(f"live script write failed: {type(exc).__name__}: {exc}", secret))
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
        print("FAIL: script write", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1
    version = plug.godot_version(exe)
    if any(bad in version for bad in ("4.7.2", "4.8")):
        errors.append(f"refused Godot --version {version!r}")
    elif version != PINNED_VERSION:
        errors.append(f"Godot --version {version!r} != {PINNED_VERSION}")

    gen = subprocess.run(
        [sess.npm(), "run", "generate"],
        cwd=BRIDGE,
        text=True,
        capture_output=True,
        check=False,
    )
    if gen.returncode != 0:
        errors.append(f"npm run generate failed:\n{gen.stdout}\n{gen.stderr}")
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
        print("FAIL: script write", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print(
        "PASS: script write/validate/patch/attach + dirty E_CONFLICT; "
        "class_name R3W5Named rewrite ACK; SCRIPT_TEXT >4000 ACK; packed attach refuse; "
        "plugin addon jail; diagnostics E_UNVERIFIED; invalid parse keeps old bytes; "
        "Pause; unproven sentinel on project.settings; R3-WP5 stays unticked."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
