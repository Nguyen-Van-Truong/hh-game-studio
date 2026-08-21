#!/usr/bin/env python3
"""R3-WP7: project settings, input map, autoload, plugin policy.

Does not tick the 20-8 plan. Does not start R3-WP8.
Pin missing is a hard FAIL. No skip-PASS.
"""

from __future__ import annotations

import hashlib
import json
import re
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
VENDOR_NEEDLES = plug.VENDOR_NEEDLES
SCHEMA = "hh-godot-variant/1"
PROJECT_GODOT = PLUGIN_PROJECT / "project.godot"
SETTING_KEY = "hh_test/r3wp7"
SETTING_VAL = "probe-r3wp7"
INPUT_ACTION = "hh_r3wp7_move"
AUTOLOAD_NAME = "HhSettingsProbe"
AUTOLOAD_PATH = "res://hh_reload_driver.gd"
HH_RELOAD_LINE = 'HhReloadDriver="*res://hh_reload_driver.gd"'


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def plan_errors(text: str) -> list[str]:
    """Keep R3-WP7 [ ] while unticked; after coordinator tick allow R3-WP8+."""
    errors: list[str] = []
    current = ""
    wp7 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R3-WP7\b", stripped):
            wp7 = stripped
    if wp7 is None:
        return ["plan missing R3-WP7 heading"]
    ticked = bool(re.search(r"\[x\]", wp7, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp7:
            errors.append("R3-WP7 heading must keep [ ] until coordinator tick")
        if current != "R3-WP7":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R3-WP7 while WP7 is unticked)")
    elif not re.match(r"^R3-WP([8-9]|\d{2,})$|^R[4-9]-WP\d+$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R3-WP8+ after R3-WP7 tick)")
    return errors


def variant(typ: str, value) -> dict:
    return {"schema": SCHEMA, "type": typ, "value": value}


def parse_godot(text: str) -> dict[str, dict[str, str]]:
    sections: dict[str, dict[str, str]] = {"": {}}
    current = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(";"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1]
            sections.setdefault(current, {})
            continue
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        sections.setdefault(current, {})[key.strip()] = val.strip()
    return sections


def disk_setting(text: str, key: str) -> str | None:
    slash = key.find("/")
    if slash <= 0:
        return None
    section, rest = key[:slash], key[slash + 1 :]
    return parse_godot(text).get(section, {}).get(rest)


def src_scan_errors() -> list[str]:
    errors: list[str] = []
    for path in (BRIDGE / "src").rglob("*.ts"):
        text = path.read_text(encoding="utf-8", errors="replace")
        posix = rel(path)
        if re.search(r"writeFile(?:Sync)?\([^)]*project\.godot", text):
            errors.append(f"{posix} writes project.godot from the sidecar")
        if "FileAccess.WRITE" in text and "project.godot" in text:
            errors.append(f"{posix} FileAccess.WRITE mentions project.godot")
        for needle in VENDOR_NEEDLES:
            if needle in text:
                errors.append(f"{posix} contains vendor needle {needle!r}")
                break
        if re.search(r"\bcallv\b", text) or "Object.call" in text:
            errors.append(f"{posix} has a generic invoke path")
    self_text = Path(__file__).read_text(encoding="utf-8")
    if "ProjectSettings.set_setting" in self_text and "adapter" not in self_text:
        pass
    if "satelliteoflove" not in self_text or "MCPGameBridge" not in self_text:
        errors.append("official test must assert project.godot does not gain vendor MCP strings")
    if "hh.pause" not in self_text:
        errors.append("official test must Pause-block set")
    router = (ADDON / "core" / "hh_router.gd").read_text(encoding="utf-8")
    if "hh_settings_adapter" not in router:
        errors.append("router must dispatch the settings adapter")
    if "play.input inject must stay" not in router:
        errors.append("unproven-mutate sentinel must move off project.settings onto play.input inject")
    if "project.settings must stay" in router:
        errors.append("project.settings sentinel must not remain after R3-WP7")
    if "4.7.2" in router:
        errors.append("router mentions 4.7.2")
    adapter = ADDON / "core" / "hh_settings_adapter.gd"
    if not adapter.is_file():
        errors.append("missing settings adapter")
    else:
        text = adapter.read_text(encoding="utf-8")
        if "ProjectSettings.set_setting" not in text or "ProjectSettings.save" not in text:
            errors.append("settings adapter must use ProjectSettings.set_setting + save")
        if re.search(r"ProjectSettings\.save\s*\(", text):
            errors.append("settings adapter must not persist via in-place ProjectSettings.save()")
        if "save_custom" not in text:
            errors.append("settings adapter must persist via ProjectSettings.save_custom")
        if ".hh-tmp" not in text or "rename_absolute" not in text:
            errors.append("settings adapter must atomically replace project.godot from same-volume tmp")
        if "ProjectSettings.clear" not in text:
            errors.append("settings adapter must remove via ProjectSettings.clear")
        if "ConfigFile" not in text or ".load(" not in text:
            errors.append("settings adapter must parse project.godot via ConfigFile.load")
        if "InputMap.add_action" not in text or "action_add_event" not in text:
            errors.append("settings adapter must use InputMap.add_action / action_add_event")
        if re.search(r"FileAccess\.open\([^)]*project\.(godot|binary)", text) or "FileAccess.WRITE" in text:
            errors.append("settings adapter must not FileAccess.WRITE the project file")
        if "autoload/" not in text or "_reorder_autoload" not in text:
            errors.append("settings adapter must add/remove/reorder autoload")
        if "E_POLICY" not in text or "third-party" not in text:
            errors.append("settings adapter must refuse third-party plugin enable")
        if "hh_agent plugin cannot be disabled" not in text:
            errors.append("settings adapter must refuse disabling hh_agent")
        for prefix in ("input/", "autoload/", "editor_plugins/", "debug/gdscript/warnings/"):
            if prefix not in text:
                errors.append(f"settings adapter must refuse generic key prefix {prefix!r}")
        if re.search(r"\bcallv\b", text) or "Object.call" in text:
            errors.append("settings adapter has a generic invoke path")
        for needle in ("satelliteoflove", "MCPGameBridge", "godot_mcp"):
            if needle in text:
                errors.append(f"settings adapter contains vendor needle {needle!r}")
    read_ad = ADDON / "core" / "hh_read_adapters.gd"
    if not read_ad.is_file():
        errors.append("missing read adapters")
    else:
        read_text = read_ad.read_text(encoding="utf-8")
        inspect_fn = re.search(r"func _project_inspect\b.*?func _", read_text, re.S)
        if inspect_fn is None or "ConfigFile" not in inspect_fn.group(0) or ".load(" not in inspect_fn.group(0):
            errors.append("project.inspect must parse disk ConfigFile")
    jail_ts = (BRIDGE / "src" / "policy" / "jail.ts").read_text(encoding="utf-8")
    extract_fn = re.search(r"export function extractTargetPaths\b.*?\n\}", jail_ts, re.S)
    if extract_fn is None or "res://project.godot" not in extract_fn.group(0):
        errors.append("extractTargetPaths must include res://project.godot for project settings verbs")
    for verb in ("project.settings", "project.input", "project.autoload", "project.plugin"):
        if verb not in jail_ts:
            errors.append(f"extractTargetPaths must treat {verb} as a project.godot target")
    engine_ts = (BRIDGE / "src" / "policy" / "engine.ts").read_text(encoding="utf-8")
    if re.search(r"isProjectSettingsAction\([^)]*\) \? \[\]", engine_ts):
        errors.append("engine must not skip extractTargetPaths for project settings")
    life_ts = (BRIDGE / "src" / "ledger" / "scene_lifecycle.ts").read_text(encoding="utf-8")
    if "PROJECT_SETTINGS_APPLY" not in life_ts or "isProjectSettingsApply" not in life_ts:
        errors.append("sidecar must treat project.settings as a proven apply verb")
    execute = (BRIDGE / "src" / "ledger" / "execute.ts").read_text(encoding="utf-8")
    if "projectSettingsApplyOk" not in execute or "project disk hash" not in execute:
        errors.append("ledger must verify project.godot disk hash after settings save")
    actions_ts = (BRIDGE / "src" / "registry" / "actions.ts").read_text(encoding="utf-8")
    if '"project.settings"' not in actions_ts:
        errors.append("catalog must keep project.settings")
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
) -> tuple[int, dict]:
    cid = life.new_ulid()
    resp = mcp_call(proc, req_id, tool, {"action": action, "params": params, "command_id": cid}, timeout)
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


def expect_code(body: dict, codes: tuple[str, ...], errors: list[str], label: str) -> None:
    got = str((body.get("error") or {}).get("code") or "")
    if body.get("ok") is True or got not in codes:
        errors.append(f"{label} expected {codes}, got {body}")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_reload_driver(disk_text: str, errors: list[str], label: str) -> None:
    if HH_RELOAD_LINE not in disk_text:
        errors.append(f"{label} dropped protected autoload: missing {HH_RELOAD_LINE}")


def live_errors(exe: Path) -> list[str]:
    errors: list[str] = []
    snapshot = PROJECT_GODOT.read_bytes() if PROJECT_GODOT.is_file() else b""
    proc: subprocess.Popen[str] | None = None
    godot: subprocess.Popen[str] | None = None
    desc_path: Path | None = None
    secret = ""
    err_lines: list[str] = []
    godot_lines: list[str] = []
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

        req_id, got = tool_call(
            proc,
            req_id,
            "godot.project",
            "settings",
            {"key": SETTING_KEY, "op": "get"},
        )
        if ack_ok(got, errors, "settings get missing"):
            if (got.get("after") or {}).get("exists") is True:
                errors.append("hh_test/r3wp7 should not exist before set")

        req_id, setted = tool_call(
            proc,
            req_id,
            "godot.project",
            "settings",
            {"key": SETTING_KEY, "op": "set", "value": variant("string", SETTING_VAL)},
        )
        if not ack_ok(setted, errors, "project.settings set"):
            return errors
        after = setted.get("after") or {}
        if after.get("readback_equals") is not True:
            errors.append(f"set missing readback_equals: {setted}")
        if after.get("disk_source") not in ("project.godot", "project.binary"):
            errors.append(f"set missing disk_source: {setted}")
        disk_text = PROJECT_GODOT.read_text(encoding="utf-8") if PROJECT_GODOT.is_file() else ""
        got_disk = disk_setting(disk_text, SETTING_KEY)
        if got_disk is None or SETTING_VAL not in got_disk:
            errors.append(f"disk parse missing {SETTING_KEY}={SETTING_VAL!r}: {got_disk!r}")
        reported = str(after.get("disk_hash") or "")
        if not reported or reported != sha256_file(PROJECT_GODOT):
            errors.append(f"set disk_hash mismatch: {reported}")
        assert_reload_driver(
            PROJECT_GODOT.read_text(encoding="utf-8") if PROJECT_GODOT.is_file() else "",
            errors,
            "settings set",
        )

        req_id, inspect = tool_call(
            proc,
            req_id,
            "godot.project",
            "inspect",
            {"detail": "short"},
        )
        if ack_ok(inspect, errors, "project.inspect"):
            inspect_after = inspect.get("after") or {}
            if inspect_after.get("disk_source") != "project.godot":
                errors.append(f"project.inspect must stamp disk_source from ConfigFile: {inspect}")

        req_id, reserved_input = tool_call(
            proc,
            req_id,
            "godot.project",
            "settings",
            {"key": "input/ui_accept", "op": "set", "value": variant("string", "nope")},
        )
        expect_code(reserved_input, ("E_POLICY", "E_CONFLICT"), errors, "refuse generic input/ui_accept")
        req_id, reserved_warn = tool_call(
            proc,
            req_id,
            "godot.project",
            "settings",
            {
                "key": "debug/gdscript/warnings/untyped_declaration",
                "op": "set",
                "value": variant("int", 0),
            },
        )
        expect_code(
            reserved_warn,
            ("E_POLICY", "E_CONFLICT"),
            errors,
            "refuse generic debug/gdscript/warnings/untyped_declaration",
        )

        req_id, got2 = tool_call(
            proc,
            req_id,
            "godot.project",
            "settings",
            {"key": SETTING_KEY, "op": "get"},
        )
        if ack_ok(got2, errors, "settings get after set"):
            val = ((got2.get("after") or {}).get("value") or {}).get("value")
            if val != SETTING_VAL:
                errors.append(f"get readback {val!r} != {SETTING_VAL!r}")

        req_id, added_in = tool_call(
            proc,
            req_id,
            "godot.project",
            "input",
            {"action_name": INPUT_ACTION, "keycode": "KEY_A", "op": "add"},
        )
        if not ack_ok(added_in, errors, "project.input add"):
            return errors
        disk_text = PROJECT_GODOT.read_text(encoding="utf-8") if PROJECT_GODOT.is_file() else ""
        if disk_setting(disk_text, f"input/{INPUT_ACTION}") is None:
            errors.append("input action missing from project.godot after add")

        req_id, added_al = tool_call(
            proc,
            req_id,
            "godot.project",
            "autoload",
            {"name": AUTOLOAD_NAME, "path": AUTOLOAD_PATH, "op": "add"},
        )
        if not ack_ok(added_al, errors, "project.autoload add"):
            return errors
        disk_text = PROJECT_GODOT.read_text(encoding="utf-8") if PROJECT_GODOT.is_file() else ""
        auto_val = disk_setting(disk_text, f"autoload/{AUTOLOAD_NAME}")
        if auto_val is None or "hh_reload_driver.gd" not in auto_val:
            errors.append(f"autoload missing from disk: {auto_val!r}")
        assert_reload_driver(disk_text, errors, "autoload add")

        req_id, reordered = tool_call(
            proc,
            req_id,
            "godot.project",
            "autoload",
            {"name": AUTOLOAD_NAME, "op": "reorder", "index": 0},
        )
        if not ack_ok(reordered, errors, "project.autoload reorder"):
            return errors
        disk_text = PROJECT_GODOT.read_text(encoding="utf-8") if PROJECT_GODOT.is_file() else ""
        auto_keys = list(parse_godot(disk_text).get("autoload", {}).keys())
        if AUTOLOAD_NAME not in auto_keys or auto_keys[0] != AUTOLOAD_NAME:
            errors.append(f"autoload reorder did not put {AUTOLOAD_NAME} first: {auto_keys}")
        assert_reload_driver(disk_text, errors, "autoload reorder")

        req_id, removed_al = tool_call(
            proc,
            req_id,
            "godot.project",
            "autoload",
            {"name": AUTOLOAD_NAME, "op": "remove"},
        )
        if not ack_ok(removed_al, errors, "project.autoload remove"):
            return errors
        disk_text = PROJECT_GODOT.read_text(encoding="utf-8") if PROJECT_GODOT.is_file() else ""
        if disk_setting(disk_text, f"autoload/{AUTOLOAD_NAME}") is not None:
            errors.append("autoload still on disk after remove")
        assert_reload_driver(disk_text, errors, "autoload remove")
        if "satelliteoflove" in disk_text or "MCPGameBridge" in disk_text:
            errors.append("project.godot gained satelliteoflove / MCPGameBridge")

        req_id, vendor = tool_call(
            proc,
            req_id,
            "godot.project",
            "plugin",
            {"plugin_name": "res://addons/fake_vendor/plugin.cfg", "enabled": True},
        )
        expect_code(vendor, ("E_POLICY", "E_CONFLICT"), errors, "refuse fake vendor plugin path")
        req_id, vendor_name = tool_call(
            proc,
            req_id,
            "godot.project",
            "plugin",
            {"plugin_name": "satelliteoflove", "enabled": True},
        )
        expect_code(vendor_name, ("E_POLICY", "E_CONFLICT"), errors, "refuse vendor plugin name")

        req_id, disabled = tool_call(
            proc,
            req_id,
            "godot.project",
            "plugin",
            {"plugin_name": "hh_agent", "enabled": False},
        )
        expect_code(disabled, ("E_POLICY",), errors, "refuse disable hh_agent")
        disk_after_disable = PROJECT_GODOT.read_text(encoding="utf-8") if PROJECT_GODOT.is_file() else ""
        if "res://addons/hh_agent/plugin.cfg" not in disk_after_disable:
            errors.append("hh_agent plugin was disabled on disk")

        req_id, features = tool_call(
            proc,
            req_id,
            "godot.project",
            "settings",
            {
                "key": "application/config/features",
                "op": "set",
                "value": variant("TypedArray", {"element": "string", "items": ["vendor-mcp"]}),
            },
        )
        expect_code(features, ("E_POLICY", "E_CONFLICT"), errors, "refuse features vendor change")

        req_id, inj = tool_call(
            proc,
            req_id,
            "godot.input",
            "action",
            {"action_name": "interact", "phase": "press"},
        )
        expect_code(inj, ("E_UNVERIFIED",), errors, "unproven play.input inject")

        req_id, removed_set = tool_call(
            proc,
            req_id,
            "godot.project",
            "settings",
            {"key": SETTING_KEY, "op": "remove"},
        )
        if not ack_ok(removed_set, errors, "project.settings remove"):
            return errors
        req_id, removed_in = tool_call(
            proc,
            req_id,
            "godot.project",
            "input",
            {"action_name": INPUT_ACTION, "op": "remove"},
        )
        if not ack_ok(removed_in, errors, "project.input remove"):
            return errors

        paused = body_of(mcp_call(proc, req_id, "hh.pause", {}))
        req_id += 1
        if paused.get("ok") is not True:
            errors.append(f"hh.pause failed: {paused}")
        req_id, paused_set = tool_call(
            proc,
            req_id,
            "godot.project",
            "settings",
            {"key": SETTING_KEY, "op": "set", "value": variant("string", "paused")},
        )
        expect_code(paused_set, ("E_PAUSED",), errors, "paused project.settings set")
        body_of(mcp_call(proc, req_id, "hh.resume", {}))
        req_id += 1

        if secret and secret in "".join(err_lines):
            errors.append("session secret appeared in sidecar logs")
        if secret and secret in "".join(godot_lines):
            errors.append("session secret appeared in Godot logs")
    except Exception as exc:  # noqa: BLE001
        errors.append(sess.redact(f"live project settings failed: {type(exc).__name__}: {exc}", secret))
    finally:
        life.stop_proc(godot)
        life.stop_proc(proc)
        if desc_path and desc_path.is_file():
            try:
                desc_path.unlink()
            except OSError:
                pass
        if snapshot:
            PROJECT_GODOT.write_bytes(snapshot)
        for leftover in (
            PLUGIN_PROJECT / "project.godot.hh-tmp.godot",
            PLUGIN_PROJECT / "project.godot.hh-bak",
        ):
            if leftover.is_file():
                try:
                    leftover.unlink()
                except OSError:
                    pass
        agent = PLUGIN_PROJECT / ".hh-agent"
        for name in ("file-leases.json", "writer.lock"):
            lock = agent / name
            if lock.is_file():
                try:
                    lock.unlink()
                except OSError:
                    pass
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
        print("FAIL: project settings", file=sys.stderr)
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
        print("FAIL: project settings", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print(
        "PASS: project.settings set/get/remove + ConfigFile disk parse; "
        "InputMap add/remove; autoload add/remove; vendor plugin E_POLICY; "
        "Pause; sentinel on play.input inject; R3-WP7 stays unticked."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
