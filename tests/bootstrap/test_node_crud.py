#!/usr/bin/env python3
"""R3-WP2: node CRUD, identity, owner, UndoRedo.

Does not tick the 20-8 plan. Does not start R3-WP3.
Pin missing is a hard FAIL. No skip-PASS.
"""

from __future__ import annotations

import random
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
TEMP_DIR = PLUGIN_PROJECT / "r3w2"
SEED = 20260821
OP_COUNT = 200
VENDOR_NEEDLES = plug.VENDOR_NEEDLES
XFORM_CLASSES = {"Node2D", "Control", "Node3D", "Sprite2D", "Label"}
ADD_CLASSES = ["Node", "Node2D", "Control", "Node3D", "Sprite2D", "Label"]


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def plan_errors(text: str) -> list[str]:
    """Keep R3-WP2 [ ] while unticked; after coordinator tick allow R3-WP3+."""
    errors: list[str] = []
    current = ""
    wp2 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R3-WP2\b", stripped):
            wp2 = stripped
    if wp2 is None:
        return ["plan missing R3-WP2 heading"]
    ticked = bool(re.search(r"\[x\]", wp2, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp2:
            errors.append("R3-WP2 heading must keep [ ] until coordinator tick")
        if current != "R3-WP2":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R3-WP2 while WP2 is unticked)")
    elif not re.match(r"^R3-WP([3-9]|\d{2,})$|^R[4-9]-WP\d+$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R3-WP3+ after R3-WP2 tick)")
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


def src_scan_errors() -> list[str]:
    errors: list[str] = []
    for path in (BRIDGE / "src").rglob("*.ts"):
        text = path.read_text(encoding="utf-8", errors="replace")
        posix = rel(path)
        if re.search(r"writeFile(?:Sync)?\([^)]*\.tscn", text):
            errors.append(f"{posix} writes a .tscn from the sidecar")
        if "ResourceSaver" in text:
            errors.append(f"{posix} uses ResourceSaver")
        for needle in VENDOR_NEEDLES:
            if needle in text:
                errors.append(f"{posix} contains vendor needle {needle!r}")
                break
    self_text = Path(__file__).read_text(encoding="utf-8")
    if re.search(r"\.write_text\([^\n]*\.tscn", self_text):
        errors.append("official test writes a .tscn path directly")
    router = (ADDON / "core" / "hh_router.gd").read_text(encoding="utf-8")
    if "hh_node_adapter" not in router:
        errors.append("router must dispatch through hh_node_adapter")
    adapter = ADDON / "core" / "hh_node_adapter.gd"
    if not adapter.is_file():
        errors.append("missing node adapter")
    else:
        text = adapter.read_text(encoding="utf-8")
        if "create_action" not in text or "Agent:" not in text and "UNDO_ACTION_PREFIX" not in text:
            errors.append("node adapter must create Agent UndoRedo actions")
        if "set_owner" not in text:
            errors.append("node adapter must set owner")
        if "NODE_UID_META" not in text and "hh_agent_uid" not in text:
            errors.append("node adapter must persist hh_agent_uid")
    constants = (ADDON / "core" / "hh_constants.gd").read_text(encoding="utf-8")
    if "hh_agent_uid" not in constants:
        errors.append("constants must name persistable hh_agent_uid")
    return errors


def mcp_call(proc: subprocess.Popen[str], req_id: int, name: str, arguments: dict, timeout: float = 30.0) -> dict:
    return life.mcp_call(proc, req_id, name, arguments, timeout)


def body_of(resp: dict) -> dict:
    return life.body_of(resp)


def node_call(
    proc: subprocess.Popen[str],
    req_id: int,
    action: str,
    params: dict,
    method: str = "godot.node",
    timeout: float = 30.0,
) -> tuple[int, dict]:
    cid = life.new_ulid()
    resp = mcp_call(
        proc,
        req_id,
        method,
        {"action": action, "params": params, "command_id": cid},
        timeout,
    )
    return req_id + 1, body_of(resp)


def scene_call(proc: subprocess.Popen[str], req_id: int, action: str, params: dict) -> tuple[int, dict]:
    req_id, _cid, body = life.scene_call(proc, req_id, action, params)
    return req_id, body


def query_all(proc: subprocess.Popen[str], req_id: int, scene: str) -> tuple[int, list[dict], dict]:
    items: list[dict] = []
    cursor = ""
    last: dict = {}
    while True:
        params: dict = {"scene": scene, "by": "path", "limit": 100}
        if cursor:
            params["cursor"] = cursor
        req_id, last = node_call(proc, req_id, "query", params)
        if last.get("ok") is not True:
            return req_id, items, last
        hits = ((last.get("after") or {}).get("hits") or {})
        page = hits.get("items") if isinstance(hits.get("items"), list) else []
        for row in page:
            if isinstance(row, dict):
                items.append(row)
        cursor = str(hits.get("next_cursor") or "")
        if not cursor:
            break
    return req_id, items, last


def fingerprint_of(proc: subprocess.Popen[str], req_id: int, scene: str) -> tuple[int, str, dict]:
    req_id, body = scene_call(proc, req_id, "read", {"path": scene, "detail": "short"})
    after = body.get("after") or {}
    return req_id, str(after.get("fingerprint") or ""), body


def identities(items: list[dict]) -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    for row in items:
        uid = str(row.get("uid") or "")
        path = str(row.get("path") or "")
        owner = str(row.get("owner") or "")
        if not uid:
            continue
        if path not in ("", ".") and owner != ".":
            continue
        out[uid] = (path, owner)
    return out


def non_root(items: list[dict]) -> list[dict]:
    return [row for row in items if str(row.get("path") or "") not in ("", ".")]


def edited_owned(items: list[dict]) -> list[dict]:
    return [row for row in non_root(items) if str(row.get("owner") or "") in ("", ".")]


def path_is_under(ancestor: str, path: str) -> bool:
    if ancestor in ("", "."):
        return path not in ("", ".")
    return path == ancestor or path.startswith(ancestor + "/")


def pick_add(rng: random.Random, items: list[dict], seq: int) -> dict:
    parent = rng.choice(items)
    return {
        "parent": str(parent.get("path") or "."),
        "class_name": rng.choice(ADD_CLASSES),
        "name": f"N{seq}",
    }


def pick_remove(rng: random.Random, items: list[dict]) -> dict | None:
    kids = edited_owned(items)
    if len(kids) < 2:
        return None
    node = rng.choice(kids)
    return {"node_path": str(node.get("path") or "")}


def pick_rename(rng: random.Random, items: list[dict], seq: int) -> dict | None:
    kids = edited_owned(items)
    if not kids:
        return None
    node = rng.choice(kids)
    return {"node_path": str(node.get("path") or ""), "name": f"R{seq}"}


def pick_reparent(rng: random.Random, items: list[dict]) -> dict | None:
    kids = edited_owned(items)
    if len(items) < 3 or not kids:
        return None
    node = rng.choice(kids)
    node_path = str(node.get("path") or "")
    candidates = [
        row
        for row in items
        if str(row.get("path") or "") != node_path
        and not path_is_under(node_path, str(row.get("path") or ""))
    ]
    if not candidates:
        return None
    new_parent = rng.choice(candidates)
    params: dict = {
        "node_path": node_path,
        "new_parent": str(new_parent.get("path") or "."),
    }
    if str(node.get("class_name") or "") in XFORM_CLASSES:
        params["keep_global_transform"] = bool(rng.getrandbits(1))
    return params


def pick_reorder(rng: random.Random, items: list[dict]) -> dict | None:
    kids = edited_owned(items)
    if not kids:
        return None
    node = rng.choice(kids)
    parent_path = str(node.get("path") or "").rsplit("/", 1)[0] if "/" in str(node.get("path") or "") else "."
    siblings = [
        row
        for row in kids
        if (str(row.get("path") or "").rsplit("/", 1)[0] if "/" in str(row.get("path") or "") else ".")
        == parent_path
    ]
    if len(siblings) < 2:
        return None
    return {
        "node_path": str(node.get("path") or ""),
        "index": rng.randrange(0, len(siblings)),
    }


def pick_duplicate(rng: random.Random, items: list[dict]) -> dict | None:
    kids = [
        row
        for row in edited_owned(items)
        if "@" not in str(row.get("path") or "") and "@" not in str(row.get("name") or "")
    ]
    if not kids:
        return None
    node = rng.choice(kids)
    return {"node_path": str(node.get("path") or "")}


def pick_group(rng: random.Random, items: list[dict]) -> dict | None:
    kids = edited_owned(items)
    if not kids:
        return None
    node = rng.choice(kids)
    groups = node.get("groups") if isinstance(node.get("groups"), list) else []
    if groups and rng.getrandbits(1):
        return {
            "node_path": str(node.get("path") or ""),
            "group": str(rng.choice(groups)),
            "op": "remove",
        }
    return {
        "node_path": str(node.get("path") or ""),
        "group": f"g{rng.randrange(0, 8)}",
        "op": "add",
    }


def pick_instantiate(rng: random.Random, items: list[dict], packed: str) -> dict:
    parent = rng.choice(items)
    return {"packed": packed, "parent": str(parent.get("path") or ".")}


def ack_ok(body: dict, errors: list[str], verb: str) -> bool:
    if body.get("ok") is not True:
        errors.append(f"{verb} must ACK: {body}")
        return False
    post = body.get("postcondition") or {}
    if post.get("verified") is not True or not post.get("checks"):
        errors.append(f"{verb} paper postcondition: {body}")
        return False
    if verb not in ("undo", "redo", "query", "read", "create", "save", "open"):
        undo = str(body.get("undo_action") or "")
        if not undo.startswith("Agent:"):
            errors.append(f"{verb} missing Agent undo_action: {body}")
            return False
        after = body.get("after") or {}
        if verb != "remove" and (not after.get("uid") or not after.get("path")):
            errors.append(f"{verb} missing uid/path: {after}")
            return False
        if verb == "remove" and after.get("absent") is not True:
            errors.append(f"remove missing absent: {after}")
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
    main = "res://r3w2/main.tscn"
    prefab = "res://r3w2/prefab.tscn"
    main_abs = life.res_to_abs(main)
    req_id = 2
    try:
        proc, desc_path, secret, err_lines = life.start_sidecar()
        godot, godot_lines = life.start_godot(exe)
        req_id, hello, last = life.wait_hello(proc, godot, req_id)
        if not hello:
            errors.append(
                "live plugin hello/noop failed: "
                f"{sess.redact(json_dumps(last), secret)}; godot={''.join(godot_lines)[-1500:]}"
            )
            return errors

        jail = body_of(
            mcp_call(
                proc,
                req_id,
                "godot.node",
                {
                    "action": "add",
                    "params": {
                        "scene": "res://../escape.tscn",
                        "parent": ".",
                        "class_name": "Node2D",
                        "name": "X",
                    },
                },
            )
        )
        req_id += 1
        if (jail.get("error") or {}).get("code") != "E_PATH":
            errors.append(f"escaped scene path must be E_PATH: {jail}")

        req_id, created_prefab = scene_call(
            proc, req_id, "create", {"path": prefab, "root_class": "Node2D"}
        )
        if not ack_ok(created_prefab, errors, "create"):
            return errors
        req_id, prefab_child = node_call(
            proc,
            req_id,
            "add",
            {"scene": prefab, "parent": ".", "class_name": "Sprite2D", "name": "Icon"},
        )
        if not ack_ok(prefab_child, errors, "add"):
            return errors
        req_id, saved_prefab = scene_call(proc, req_id, "save", {"path": prefab})
        if not ack_ok(saved_prefab, errors, "save"):
            return errors

        req_id, created = scene_call(proc, req_id, "create", {"path": main, "root_class": "Node2D"})
        if not ack_ok(created, errors, "create"):
            return errors
        for name, cls in (("A", "Node2D"), ("B", "Control"), ("C", "Node"), ("D", "Node3D")):
            req_id, added = node_call(
                proc,
                req_id,
                "add",
                {"scene": main, "parent": ".", "class_name": cls, "name": name},
            )
            if not ack_ok(added, errors, "add"):
                return errors

        req_id, start_fp, start_read = fingerprint_of(proc, req_id, main)
        if not start_fp:
            errors.append(f"baseline fingerprint missing: {start_read}")
            return errors
        req_id, items, qbody = query_all(proc, req_id, main)
        if qbody.get("ok") is not True or len(items) < 5:
            errors.append(f"seed query failed: {qbody} items={len(items)}")
            return errors

        rng = random.Random(SEED)
        verbs = [
            "add",
            "remove",
            "rename",
            "reparent",
            "reorder",
            "duplicate",
            "instantiate",
            "group",
        ]
        used: set[str] = set()
        success = 0
        seq = 0
        for _ in range(OP_COUNT):
            if len(items) > 70:
                weights = [8, 28, 10, 12, 10, 8, 8, 16]
            elif len(items) < 6:
                weights = [30, 4, 12, 10, 8, 16, 10, 10]
            else:
                weights = [18, 12, 12, 14, 12, 12, 8, 12]
            verb = rng.choices(verbs, weights=weights, k=1)[0]
            seq += 1
            params: dict | None
            method = "godot.node"
            if verb == "add":
                params = pick_add(rng, items, seq)
            elif verb == "remove":
                params = pick_remove(rng, items)
            elif verb == "rename":
                params = pick_rename(rng, items, seq)
            elif verb == "reparent":
                params = pick_reparent(rng, items)
            elif verb == "reorder":
                params = pick_reorder(rng, items)
            elif verb == "duplicate":
                params = pick_duplicate(rng, items)
            elif verb == "instantiate":
                params = pick_instantiate(rng, items, prefab)
                method = "godot.scene"
            else:
                params = pick_group(rng, items)
            if params is None:
                params = pick_add(rng, items, seq)
                verb = "add"
                method = "godot.node"
            params["scene"] = main
            req_id, body = node_call(proc, req_id, verb, params, method=method)
            if not ack_ok(body, errors, verb):
                if len(errors) > 12:
                    return errors
                continue
            used.add(verb)
            success += 1
            req_id, items, qbody = query_all(proc, req_id, main)
            if qbody.get("ok") is not True:
                errors.append(f"query after {verb} failed: {qbody}")
                return errors

        if success < OP_COUNT:
            errors.append(f"only {success}/{OP_COUNT} random ops ACK")
        if len(used) < 6:
            errors.append(f"random mix too narrow: {sorted(used)}")
        if used <= {"add", "remove"}:
            errors.append("200 random ops were only add/remove")

        req_id, end_fp, end_read = fingerprint_of(proc, req_id, main)
        if not end_fp:
            errors.append(f"final fingerprint missing: {end_read}")
        if end_fp == start_fp:
            errors.append("200 ops left the fingerprint unchanged")

        req_id, undone = node_call(
            proc, req_id, "undo", {"scene": main, "count": success}, timeout=90.0
        )
        if not ack_ok(undone, errors, "undo"):
            return errors
        req_id, undo_fp, undo_read = fingerprint_of(proc, req_id, main)
        if undo_fp != start_fp:
            errors.append(
                f"undo-all fingerprint {undo_fp} != baseline {start_fp}; read={undo_read.get('after')}"
            )

        req_id, redone = node_call(
            proc, req_id, "redo", {"scene": main, "count": success}, timeout=90.0
        )
        if not ack_ok(redone, errors, "redo"):
            return errors
        req_id, redo_fp, redo_read = fingerprint_of(proc, req_id, main)
        if redo_fp != end_fp:
            errors.append(
                f"redo-all fingerprint {redo_fp} != final {end_fp}; read={redo_read.get('after')}"
            )

        req_id, before_items, _ = query_all(proc, req_id, main)
        before_ids = identities(before_items)
        if not before_ids:
            errors.append("no persisted uids before save")
        req_id, saved = scene_call(proc, req_id, "save", {"path": main})
        if not ack_ok(saved, errors, "save"):
            return errors
        if main_abs.is_file() and "hh_agent_uid" not in main_abs.read_text(encoding="utf-8"):
            errors.append("save did not persist hh_agent_uid")
        if main_abs.is_file() and "AgentWroteRaw" in main_abs.read_text(encoding="utf-8"):
            errors.append("raw node write leaked into the scene")

        life.stop_proc(godot)
        godot, godot_lines = life.start_godot(exe)
        req_id, hello2, last2 = life.wait_hello(proc, godot, req_id)
        if not hello2:
            errors.append(f"reopen hello failed: {last2}")
            return errors
        req_id, opened = scene_call(proc, req_id, "open", {"path": main})
        if not ack_ok(opened, errors, "open"):
            return errors
        req_id, after_items, _ = query_all(proc, req_id, main)
        after_ids = identities(after_items)
        if before_ids != after_ids:
            errors.append(f"save/reopen identity drift: before={before_ids} after={after_ids}")
        for row in after_items:
            path = str(row.get("path") or "")
            owner = str(row.get("owner") or "")
            if path not in ("", ".") and owner == "":
                errors.append(f"dangling owner on {row}")
                break

        req_id, plain = node_call(
            proc,
            req_id,
            "add",
            {"scene": main, "parent": ".", "class_name": "Node", "name": "PlainKeep"},
        )
        if not ack_ok(plain, errors, "add"):
            return errors
        req_id, typed = node_call(
            proc,
            req_id,
            "reparent",
            {
                "scene": main,
                "node_path": str((plain.get("after") or {}).get("path") or "PlainKeep"),
                "new_parent": ".",
                "keep_global_transform": True,
            },
        )
        if typed.get("ok") is True or (typed.get("error") or {}).get("code") != "E_INVALID_TYPE":
            errors.append(f"keep_global_transform on Node must be E_INVALID_TYPE: {typed}")

        req_id, local = node_call(
            proc, req_id, "make_local", {"scene": main, "node_path": "."}
        )
        if local.get("ok") is True or (local.get("error") or {}).get("code") != "E_UNVERIFIED":
            errors.append(f"make_local must be honest E_UNVERIFIED: {local}")

        paused = body_of(mcp_call(proc, req_id, "hh.pause", {}))
        req_id += 1
        if paused.get("ok") is not True:
            errors.append(f"hh.pause failed: {paused}")
        req_id, blocked = node_call(
            proc,
            req_id,
            "add",
            {"scene": main, "parent": ".", "class_name": "Node2D", "name": "Paused"},
        )
        if (blocked.get("error") or {}).get("code") != "E_PAUSED":
            errors.append(f"paused node.add must be E_PAUSED: {blocked}")
        body_of(mcp_call(proc, req_id, "hh.resume", {}))
        req_id += 1

        if secret and secret in "".join(err_lines):
            errors.append("session secret appeared in sidecar logs")
        if secret and secret in "".join(godot_lines):
            errors.append("session secret appeared in Godot logs")
    except Exception as exc:  # noqa: BLE001
        errors.append(sess.redact(f"live node CRUD failed: {type(exc).__name__}: {exc}", secret))
    finally:
        life.stop_proc(godot)
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
        cleanup_temp()
    return errors


def json_dumps(value: object) -> str:
    import json

    return json.dumps(value)


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
        print("FAIL: node CRUD", file=sys.stderr)
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
        print("FAIL: node CRUD", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print(
        "PASS: node CRUD add/remove/rename/duplicate/reparent/reorder/instantiate/groups; "
        "200 seeded random then Undo ALL = baseline and Redo = final; "
        "save/reopen uid/path/owner; Pause blocks; make-local E_UNVERIFIED; "
        "R3-WP2 stays [ ]."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
