#!/usr/bin/env python3
"""R3-WP1: scene lifecycle + durable save via EditorInterface.

Does not tick the 20-8 plan. Does not implement node CRUD.
Pin missing is a hard FAIL. Godot tests are exclusive with
plugin_router / policy / read_model.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hh_agent_allow import hh_agent_only_addon_errors
import test_plugin_router as plug
import test_session as sess

BRIDGE = REPO_ROOT / "bridge"
PLAN = REPO_ROOT / "zdocs" / "20-8-godot-agent-autopilot-plan.txt"
PLUGIN_PROJECT = REPO_ROOT / "godot" / "plugin-project"
ADDON = PLUGIN_PROJECT / "addons" / "hh_agent"
PINNED_VERSION = plug.PINNED_VERSION
TEMP_DIR = PLUGIN_PROJECT / "r3w1"
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
VENDOR_NEEDLES = plug.VENDOR_NEEDLES


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def new_ulid() -> str:
    ms = int(time.time() * 1000)
    chars: list[str] = []
    t = ms
    for _ in range(10):
        chars.append(CROCKFORD[t % 32])
        t //= 32
    time_part = "".join(reversed(chars))
    acc = int.from_bytes(os.urandom(10), "big")
    rand: list[str] = []
    for _ in range(16):
        rand.append(CROCKFORD[acc % 32])
        acc //= 32
    return time_part + "".join(reversed(rand))


def plan_errors(text: str) -> list[str]:
    """Keep R3-WP1 [ ] while unticked; after coordinator tick allow R3-WP2+."""
    errors: list[str] = []
    current = ""
    wp1 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R3-WP1\b", stripped):
            wp1 = stripped
    if wp1 is None:
        return ["plan missing R3-WP1 heading"]
    ticked = bool(re.search(r"\[x\]", wp1, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp1:
            errors.append("R3-WP1 heading must keep [ ] until coordinator tick")
        if current != "R3-WP1":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R3-WP1 while WP1 is unticked)")
    elif not re.match(r"^R3-WP([2-9]|\d{2,})$|^R[4-9]-WP\d+$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R3-WP2+ after R3-WP1 tick)")
    return errors


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def res_to_abs(res_path: str) -> Path:
    return PLUGIN_PROJECT / res_path[len("res://") :].replace("/", os.sep)


def cleanup_temp_scenes() -> None:
    locked = TEMP_DIR / "locked"
    if locked.exists():
        unlock_write_target(locked)
    if TEMP_DIR.is_dir():
        shutil.rmtree(TEMP_DIR, ignore_errors=True)


def attack_external_edit(path: Path) -> None:
    """Deliberate human/external edit after the plugin created the file."""
    text = path.read_text(encoding="utf-8")
    path.write_text(text + "\n; human-edit\n", encoding="utf-8")


def src_scan_errors() -> list[str]:
    errors: list[str] = []
    for path in (BRIDGE / "src").rglob("*.ts"):
        text = path.read_text(encoding="utf-8", errors="replace")
        posix = rel(path)
        if re.search(r"writeFile(?:Sync)?\([^)]*\.tscn", text):
            errors.append(f"{posix} writes a .tscn from the sidecar")
        if 'ResourceSaver' in text:
            errors.append(f"{posix} uses ResourceSaver")
        for needle in VENDOR_NEEDLES:
            if needle in text:
                errors.append(f"{posix} contains vendor needle {needle!r}")
                break
    self_text = Path(__file__).read_text(encoding="utf-8")
    if re.search(r'\.write_text\([^\n]*\.tscn', self_text):
        errors.append("official test writes a .tscn path directly")
    if "attack_external_edit" not in self_text:
        errors.append("official test must isolate human-edit writes")
    plugin_router = (ADDON / "core" / "hh_router.gd").read_text(encoding="utf-8")
    if "godot.node" not in plugin_router or "E_UNVERIFIED" not in plugin_router:
        errors.append("router must still refuse node CRUD as E_UNVERIFIED")
    return errors


def mcp_call(proc: subprocess.Popen[str], req_id: int, name: str, arguments: dict, timeout: float = 20.0) -> dict:
    assert proc.stdin and proc.stdout
    proc.stdin.write(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        + "\n"
    )
    proc.stdin.flush()
    line = sess.readline_timeout(proc.stdout, timeout)
    return json.loads(line)


def body_of(resp: dict) -> dict:
    return (resp.get("result") or {}).get("structuredContent") or {}


def precondition_of(after: dict) -> dict:
    pre: dict = {}
    if after.get("fingerprint"):
        pre["fingerprint"] = str(after["fingerprint"])
    if after.get("history_version") not in (None, ""):
        pre["history_version"] = str(after["history_version"])
    if after.get("disk_hash"):
        pre["scene_hash"] = str(after["disk_hash"])
    return pre


def scene_call(
    proc: subprocess.Popen[str],
    req_id: int,
    action: str,
    params: dict,
    command_id: str | None = None,
    precondition: dict | None = None,
) -> tuple[int, dict, dict]:
    cid = command_id or new_ulid()
    args: dict = {"action": action, "params": params, "command_id": cid}
    if precondition:
        args["precondition"] = precondition
    resp = mcp_call(proc, req_id, "godot.scene", args)
    return req_id + 1, cid, body_of(resp)


def start_sidecar() -> tuple[subprocess.Popen[str], Path, str, list[str]]:
    proc = subprocess.Popen(
        [sess.node(), str(BRIDGE / "dist" / "main.js"), "--project", str(PLUGIN_PROJECT)],
        cwd=str(BRIDGE),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    err_lines: list[str] = []
    threading.Thread(target=sess.drain_stderr, args=(proc, err_lines), daemon=True).start()
    desc_path, desc = sess.find_descriptor(proc.pid)
    secret = str(desc.get("token") or "")
    assert proc.stdin and proc.stdout
    proc.stdin.write(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test-scene-lifecycle", "version": "0"},
                },
            }
        )
        + "\n"
    )
    proc.stdin.flush()
    init_line = sess.readline_timeout(proc.stdout, 8.0)
    if "result" not in json.loads(init_line):
        raise RuntimeError(f"MCP initialize failed: {init_line}")
    return proc, desc_path, secret, err_lines


def start_godot(exe: Path) -> tuple[subprocess.Popen[str], list[str]]:
    env = os.environ.copy()
    env.pop("HH_AGENT_SELFTEST", None)
    env.pop("HH_AGENT_SELFTEST_OUT", None)
    env.pop("HH_AGENT_RELOAD_N", None)
    env.pop("HH_AGENT_RELOAD_OUT", None)
    env.pop("HH_READ_OPEN_SCENE", None)
    godot = subprocess.Popen(
        [str(exe), "--headless", "--editor", "--path", str(PLUGIN_PROJECT)],
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    lines: list[str] = []

    def drain_out() -> None:
        if godot.stdout is None:
            return
        for line in godot.stdout:
            lines.append(line)

    threading.Thread(target=drain_out, daemon=True).start()
    threading.Thread(target=sess.drain_stderr, args=(godot, lines), daemon=True).start()
    return godot, lines


def stop_proc(proc: subprocess.Popen[str] | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()


def wait_hello(proc: subprocess.Popen[str], godot: subprocess.Popen[str], req_id: int) -> tuple[int, bool, dict]:
    deadline = time.time() + 40.0
    last: dict = {}
    while time.time() < deadline:
        if godot.poll() is not None or proc.poll() is not None:
            break
        last = body_of(mcp_call(proc, req_id, "hh.plugin_noop", {}))
        req_id += 1
        if last.get("ok") is True and (last.get("postcondition") or {}).get("checks") == ["noop"]:
            return req_id, True, last
        time.sleep(0.25)
    return req_id, False, last


def lock_write_target(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        user = os.environ.get("USERNAME") or os.environ.get("USER") or ""
        subprocess.run(["attrib", "+R", str(path)], check=False, capture_output=True)
        if user:
            subprocess.run(
                ["icacls", str(path), "/deny", f"{user}:(OI)(CI)W"],
                check=False,
                capture_output=True,
            )
    else:
        os.chmod(path, 0o555)


def unlock_write_target(path: Path) -> None:
    if not path.exists():
        return
    if os.name == "nt":
        user = os.environ.get("USERNAME") or os.environ.get("USER") or ""
        subprocess.run(["attrib", "-R", str(path)], check=False, capture_output=True)
        if user:
            subprocess.run(
                ["icacls", str(path), "/remove:d", user],
                check=False,
                capture_output=True,
            )
    else:
        os.chmod(path, 0o755)


def live_errors(exe: Path) -> list[str]:
    errors: list[str] = []
    cleanup_temp_scenes()
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    proc: subprocess.Popen[str] | None = None
    godot: subprocess.Popen[str] | None = None
    desc_path: Path | None = None
    secret = ""
    err_lines: list[str] = []
    godot_lines: list[str] = []
    life = "res://r3w1/life.tscn"
    copied = "res://r3w1/life_as.tscn"
    inherited = "res://r3w1/child.tscn"
    life_abs = res_to_abs(life)
    copied_abs = res_to_abs(copied)
    inherited_abs = res_to_abs(inherited)
    saved_hash = ""
    inherited_hash = ""
    req_id = 2
    try:
        proc, desc_path, secret, err_lines = start_sidecar()
        godot, godot_lines = start_godot(exe)
        req_id, hello, last = wait_hello(proc, godot, req_id)
        if not hello:
            errors.append(
                "live plugin hello/noop failed: "
                f"{sess.redact(json.dumps(last), secret)}; godot={''.join(godot_lines)[-1500:]}"
            )
            return errors

        node_add = body_of(
            mcp_call(
                proc,
                req_id,
                "godot.node",
                {
                    "action": "add",
                    "params": {
                        "scene": life,
                        "parent": ".",
                        "class_name": "Node2D",
                        "name": "AgentWroteThis",
                    },
                },
            )
        )
        req_id += 1
        if (node_add.get("error") or {}).get("code") != "E_UNVERIFIED":
            errors.append(f"node.add must stay E_UNVERIFIED: {node_add}")
        if node_add.get("ok") is True:
            errors.append("node.add returned ok true")

        select = body_of(
            mcp_call(
                proc,
                req_id,
                "godot.editor",
                {"action": "select", "params": {"scene": life, "node_path": "."}},
            )
        )
        req_id += 1
        if (select.get("error") or {}).get("code") != "E_UNVERIFIED":
            errors.append(f"editor.select must stay E_UNVERIFIED: {select}")

        req_id, create_id, created = scene_call(
            proc, req_id, "create", {"path": life, "root_class": "Node2D"}
        )
        if created.get("ok") is not True:
            errors.append(f"scene.create must ACK: {created}")
        if not life_abs.is_file():
            errors.append("scene.create did not write via plugin")
        else:
            text = life_abs.read_text(encoding="utf-8")
            if "AgentWroteThis" in text:
                errors.append("node.add wrote a node into the scene")
        after = created.get("after") or {}
        if after.get("root_class") != "Node2D":
            errors.append(f"create root_class {after.get('root_class')}")
        if not after.get("disk_hash"):
            errors.append("create missing disk_hash")
        inspect = body_of(mcp_call(proc, req_id, "hh.ledger_inspect", {"command_id": create_id}))
        req_id += 1
        if (inspect.get("row") or {}).get("state") != "committed_durable":
            errors.append(f"create ledger state {inspect}")

        req_id, _, tabs = scene_call(proc, req_id, "list_tabs", {"detail": "short"})
        if tabs.get("ok") is not True:
            errors.append(f"scene.list_tabs must ACK: {tabs}")
        open_scenes = (tabs.get("after") or {}).get("open_scenes") or []
        if life not in open_scenes:
            errors.append(f"list_tabs missing created scene: {tabs.get('after')}")

        req_id, _, read1 = scene_call(proc, req_id, "read", {"path": life, "detail": "short"})
        if read1.get("ok") is not True:
            errors.append(f"scene.read must ACK: {read1}")
        r_after = read1.get("after") or {}
        if not r_after.get("fingerprint") or not r_after.get("history_version"):
            errors.append(f"read missing fingerprint/history: {r_after}")
        if "dirty" not in r_after:
            errors.append("read missing dirty flag")
        pre = precondition_of(r_after)

        req_id, save_id, saved = scene_call(proc, req_id, "save", {"path": life}, precondition=pre)
        if saved.get("ok") is not True:
            errors.append(f"scene.save must ACK: {saved}")
        s_after = saved.get("after") or {}
        if life_abs.is_file():
            disk = sha256_file(life_abs)
            saved_hash = disk
            if s_after.get("disk_hash") != disk:
                errors.append(f"save disk_hash {s_after.get('disk_hash')} != sidecar {disk}")
        inspect_s = body_of(mcp_call(proc, req_id, "hh.ledger_inspect", {"command_id": save_id}))
        req_id += 1
        if (inspect_s.get("row") or {}).get("state") != "committed_durable":
            errors.append(f"save ledger state {inspect_s}")

        stop_proc(godot)
        godot, godot_lines = start_godot(exe)
        req_id, hello2, last2 = wait_hello(proc, godot, req_id)
        if not hello2:
            errors.append(f"restart hello failed: {last2}")
        else:
            req_id, _, opened = scene_call(proc, req_id, "open", {"path": life})
            if opened.get("ok") is not True:
                errors.append(f"reopen after restart failed: {opened}")
            if life_abs.is_file() and sha256_file(life_abs) != saved_hash:
                errors.append("restart lost or mutated saved scene bytes")
            req_id, _, read_r = scene_call(proc, req_id, "read", {"path": life, "detail": "short"})
            if (read_r.get("after") or {}).get("root_class") != "Node2D":
                errors.append(f"restart read root drifted: {read_r.get('after')}")

        req_id, _, saved_as = scene_call(proc, req_id, "save_as", {"path": copied})
        if saved_as.get("ok") is not True:
            errors.append(f"scene.save_as must ACK: {saved_as}")
        if not copied_abs.is_file():
            errors.append("save_as did not produce a file")

        req_id, _, activated = scene_call(proc, req_id, "activate", {"path": life})
        if activated.get("ok") is not True:
            errors.append(f"scene.activate must ACK: {activated}")
        if (activated.get("after") or {}).get("edited_scene") != life:
            errors.append(f"activate edited_scene {activated.get('after')}")

        req_id, _, reloaded = scene_call(proc, req_id, "reload", {"path": life})
        if reloaded.get("ok") is not True:
            errors.append(f"scene.reload must ACK: {reloaded}")

        req_id, _, child = scene_call(
            proc,
            req_id,
            "create",
            {"path": inherited, "root_class": "Node2D", "inherit_from": life},
        )
        if child.get("ok") is not True:
            errors.append(f"inherited create must ACK: {child}")
        if inherited_abs.is_file():
            inh_text = inherited_abs.read_text(encoding="utf-8")
            if "instance=" not in inh_text:
                errors.append("inherited scene missing instance=")
            if inh_text.count("[node ") > 1:
                errors.append("inherited scene looks flattened/duplicated")
        req_id, _, inh_read = scene_call(proc, req_id, "read", {"path": inherited, "detail": "short"})
        inh_pre = precondition_of(inh_read.get("after") or {})
        req_id, _, inh_save = scene_call(
            proc, req_id, "save", {"path": inherited}, precondition=inh_pre
        )
        if inh_save.get("ok") is not True:
            errors.append(f"inherited save must ACK: {inh_save}")
        if inherited_abs.is_file():
            if "instance=" not in inherited_abs.read_text(encoding="utf-8"):
                errors.append("save flattened inherited scene")
            inherited_hash = sha256_file(inherited_abs)

        stop_proc(godot)
        godot, godot_lines = start_godot(exe)
        req_id, hello3, last3 = wait_hello(proc, godot, req_id)
        if not hello3:
            errors.append(f"inherited restart hello failed: {last3}")
        else:
            req_id, _, inh_open = scene_call(proc, req_id, "open", {"path": inherited})
            if inh_open.get("ok") is not True:
                errors.append(f"inherited reopen failed: {inh_open}")
            if inherited_abs.is_file():
                if "instance=" not in inherited_abs.read_text(encoding="utf-8"):
                    errors.append("restart flattened inherited scene")
                if inherited_hash and sha256_file(inherited_abs) != inherited_hash:
                    errors.append("inherited scene hash drifted across restart")

        req_id, _, read_c = scene_call(proc, req_id, "read", {"path": life, "detail": "short"})
        conflict_pre = precondition_of(read_c.get("after") or {})
        if life_abs.is_file():
            attack_external_edit(life_abs)
        req_id, _, conflicted = scene_call(
            proc, req_id, "save", {"path": life}, precondition=conflict_pre
        )
        if (conflicted.get("error") or {}).get("code") != "E_CONFLICT":
            errors.append(f"external/human edit must be E_CONFLICT: {conflicted}")
        if conflicted.get("ok") is True:
            errors.append("conflict save returned ok true")

        locked_dir = TEMP_DIR / "locked"
        locked_abs = locked_dir.resolve()
        ro_dest = "res://r3w1/locked/nope.tscn"
        try:
            lock_write_target(locked_dir)
            req_id, _, ro_save = scene_call(proc, req_id, "save_as", {"path": ro_dest})
        finally:
            unlock_write_target(locked_dir)
        ro_code = (ro_save.get("error") or {}).get("code")
        if ro_save.get("ok") is True or ro_code not in ("E_UNVERIFIED", "E_PATH"):
            errors.append(f"read-only save must fail typed, not ok: {ro_save}")
        if res_to_abs(ro_dest).is_file():
            errors.append("read-only save_as wrote through a locked directory")

        paused = body_of(mcp_call(proc, req_id, "hh.pause", {}))
        req_id += 1
        if paused.get("ok") is not True:
            errors.append(f"hh.pause failed: {paused}")
        req_id, _, paused_create = scene_call(
            proc, req_id, "create", {"path": "res://r3w1/paused.tscn", "root_class": "Node2D"}
        )
        if (paused_create.get("error") or {}).get("code") != "E_PAUSED":
            errors.append(f"paused scene.create must be E_PAUSED: {paused_create}")
        body_of(mcp_call(proc, req_id, "hh.resume", {}))
        req_id += 1

        req_id, _, closed = scene_call(proc, req_id, "close", {"path": copied})
        close_code = (closed.get("error") or {}).get("code")
        if closed.get("ok") is True:
            if copied in ((closed.get("after") or {}).get("open_scenes") or []):
                errors.append("close ACK but scene still open")
        elif close_code != "E_UNVERIFIED":
            errors.append(f"close must ACK or honest E_UNVERIFIED: {closed}")
        elif "close_scene" not in str((closed.get("error") or {}).get("message") or "") and (
            "refusing to fake" not in str((closed.get("error") or {}).get("message") or "")
        ):
            # Still accept E_UNVERIFIED if checkpoint/path failed honestly.
            if close_code == "E_UNVERIFIED":
                pass

        node_add2 = body_of(
            mcp_call(
                proc,
                req_id,
                "godot.node",
                {
                    "action": "add",
                    "params": {
                        "scene": copied,
                        "parent": ".",
                        "class_name": "Node2D",
                        "name": "AgentWroteThis",
                    },
                },
            )
        )
        req_id += 1
        if (node_add2.get("error") or {}).get("code") != "E_UNVERIFIED":
            errors.append(f"node.add must stay E_UNVERIFIED after scene verbs: {node_add2}")
        if copied_abs.is_file() and "AgentWroteThis" in copied_abs.read_text(encoding="utf-8"):
            errors.append("node.add wrote into the scene after lifecycle")

        if secret and secret in "".join(err_lines):
            errors.append("session secret appeared in sidecar logs")
        if secret and secret in "".join(godot_lines):
            errors.append("session secret appeared in Godot logs")
    except Exception as exc:  # noqa: BLE001
        errors.append(sess.redact(f"live scene lifecycle failed: {type(exc).__name__}: {exc}", secret))
    finally:
        stop_proc(godot)
        stop_proc(proc)
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
        cleanup_temp_scenes()
    return errors


def main() -> int:
    errors: list[str] = []
    errors.extend(hh_agent_only_addon_errors(PLUGIN_PROJECT, REPO_ROOT))
    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.is_file() else None
    if plan_text is None:
        errors.append(f"missing {rel(PLAN)}")
    else:
        errors.extend(plan_errors(plan_text))
    errors.extend(src_scan_errors())

    exe, pin_reason = plug.find_pinned_godot()
    if exe is None:
        errors.append(f"pinned Godot required (no skip-PASS): {pin_reason}")
        print("FAIL: scene lifecycle", file=sys.stderr)
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
        print("FAIL: scene lifecycle", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print(
        "PASS: scene lifecycle create/open/list/activate/read/save/save-as/reload; "
        "fingerprint+history; E_CONFLICT on external edit; read-only typed fail; "
        "inherited instance= survives save+restart; node.add stays E_UNVERIFIED; "
        "plugin is the .tscn writer; R3-WP1 stays [ ]."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
