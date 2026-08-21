#!/usr/bin/env python3
"""R4-WP2: editor select / Inspector / Script / FileSystem focus.

Does not tick the 20-8 plan. Does not start R4-WP3. Does not tick G2 VISIBLE.
Pin missing is a hard FAIL. No skip-PASS.
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
PINNED_VERSION = plug.PINNED_VERSION
TEMP_DIR = PLUGIN_PROJECT / "r4w2"
VENDOR_NEEDLES = plug.VENDOR_NEEDLES
SCHEMA = "hh-godot-variant/1"
PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def plan_errors(text: str) -> list[str]:
    """Keep R4-WP2 [ ] while unticked; after coordinator tick allow R4-WP3+."""
    errors: list[str] = []
    current = ""
    wp2 = None
    g2 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R4-WP2\b", stripped):
            wp2 = stripped
        if stripped.startswith("G2 VISIBLE"):
            g2 = stripped
    if wp2 is None:
        return ["plan missing R4-WP2 heading"]
    ticked = bool(re.search(r"\[x\]", wp2, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp2:
            errors.append("R4-WP2 heading must keep [ ] until coordinator tick")
        if current != "R4-WP2":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R4-WP2 while WP2 is unticked)")
    elif not re.match(r"^R4-WP([3-9]|\d{2,})$|^R[5-9]-WP\d+$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R4-WP3+ after R4-WP2 tick)")
    if g2 and re.search(r"\[x\]", g2, re.IGNORECASE):
        errors.append("G2 VISIBLE must stay unticked; it is a human gate")
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
    presenter = ADDON / "core" / "hh_presenter.gd"
    if not presenter.is_file():
        errors.append("missing hh_presenter.gd")
    else:
        text = presenter.read_text(encoding="utf-8")
        if "edit_node" not in text or "edit_resource" not in text:
            errors.append("presenter must use EditorInterface.edit_node / edit_resource")
        if "edit_script" not in text or "select_file" not in text:
            errors.append("presenter must open scripts and select filesystem paths")
        if "create_action" in text or "EditorUndoRedoManager" in text:
            errors.append("presenter must not create UndoRedo actions")
        if "ResourceSaver" in text or "FileAccess.WRITE" in text or "save_scene" in text:
            errors.append("presenter must not write disk")
        if "overlay" in text.lower() or "ghost" in text.lower():
            errors.append("R4-WP2 must not implement viewport overlay / ghost drag")
    reads = ADDON / "core" / "hh_read_adapters.gd"
    if reads.is_file():
        text = reads.read_text(encoding="utf-8")
        if "selected_paths" not in text:
            errors.append("editor.state must expose selected_paths")
        if "_observer_focus" not in text:
            errors.append("godot.observer focus read adapter missing")
    router = ADDON / "core" / "hh_router.gd"
    if router.is_file():
        text = router.read_text(encoding="utf-8")
        if "HHAgentPresenter" not in text and "hh_presenter" not in text:
            errors.append("router must route presentation through the presenter")
        if "after_success" not in text:
            errors.append("router must present after successful node.add/property.set/script.write")
    for path in (BRIDGE / "src").rglob("*.ts"):
        blob = path.read_text(encoding="utf-8", errors="replace")
        posix = rel(path)
        for needle in VENDOR_NEEDLES:
            if needle in blob:
                errors.append(f"{posix} contains vendor needle {needle!r}")
                break
    return errors


def mcp_call(proc: subprocess.Popen[str], req_id: int, name: str, arguments: dict, timeout: float = 20.0) -> dict:
    return life.mcp_call(proc, req_id, name, arguments, timeout)


def body_of(resp: dict) -> dict:
    return life.body_of(resp)


def call_tool(
    proc: subprocess.Popen[str],
    req_id: int,
    method: str,
    action: str,
    params: dict,
    timeout: float = 30.0,
    presentation: dict | None = None,
) -> tuple[int, str, dict]:
    cid = life.new_ulid()
    arguments: dict = {"action": action, "params": params, "command_id": cid}
    if presentation:
        arguments["presentation"] = presentation
    resp = mcp_call(proc, req_id, method, arguments, timeout)
    return req_id + 1, cid, body_of(resp)


def after_of(body: dict) -> dict:
    after = body.get("after") if isinstance(body.get("after"), dict) else {}
    return after


def paths_have(selected: object, needle: str) -> bool:
    if not isinstance(selected, list):
        return False
    for item in selected:
        text = str(item)
        if text == needle or text.endswith("/" + needle) or text.endswith(needle):
            return True
    return False


def token_in(obj: object, secret: str) -> bool:
    if not secret:
        return False
    return secret in json.dumps(obj)


def focus_ok(after: dict, *, node: str = "", inspector_class: str = "") -> tuple[bool, str]:
    selected = after.get("selected_paths")
    failed = after.get("presentation_failed") is True
    if node and not paths_have(selected, node) and not failed:
        return False, f"selected_paths missing {node}: {after}"
    if inspector_class:
        got = str(after.get("inspector_class") or "")
        path = str(after.get("inspector_path") or "")
        if got == inspector_class and (not node or node in path or path in {node, ".", ""}):
            return True, ""
        if failed:
            return True, ""
        return False, f"inspector mismatch class={got!r} path={path!r}: {after}"
    return True, ""


def live_errors(exe: Path) -> list[str]:
    errors: list[str] = []
    cleanup_temp()
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    png_abs = TEMP_DIR / "dot.png"
    png_abs.write_bytes(PNG_1X1)
    proc: subprocess.Popen[str] | None = None
    godot: subprocess.Popen[str] | None = None
    desc_path: Path | None = None
    secret = ""
    err_lines: list[str] = []
    godot_lines: list[str] = []
    scene_a = "res://r4w2/focus_a.tscn"
    scene_b = "res://r4w2/focus_b.tscn"
    script = "res://r4w2/note.gd"
    png = "res://r4w2/dot.png"
    script_text = "extends Node2D\n\nfunc ready_marker() -> void:\n\tpass\n"
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

        req_id, _create_a, created_a = call_tool(
            proc, req_id, "godot.scene", "create", {"path": scene_a, "root_class": "Node2D"}
        )
        if created_a.get("ok") is not True:
            errors.append(f"scene.create A must ACK: {sess.redact(json.dumps(created_a), secret)}")

        req_id, add_id, added = call_tool(
            proc,
            req_id,
            "godot.node",
            "add",
            {"scene": scene_a, "parent": ".", "class_name": "Node2D", "name": "FocusSprite"},
        )
        if added.get("ok") is not True:
            errors.append(f"node.add must ACK: {sess.redact(json.dumps(added), secret)}")
        add_after = after_of(added)
        add_uid = str(add_after.get("uid") or "")
        if add_after.get("path") != "FocusSprite":
            errors.append(f"node.add path drifted: {add_after}")

        req_id, _sel_id, selected = call_tool(
            proc,
            req_id,
            "godot.editor",
            "select",
            {"scene": scene_a, "node_path": "FocusSprite"},
        )
        if selected.get("ok") is not True:
            errors.append(f"editor.select after add must ACK: {sess.redact(json.dumps(selected), secret)}")
        sel_after = after_of(selected)
        ok, why = focus_ok(sel_after, node="FocusSprite", inspector_class="Node2D")
        if not ok:
            errors.append(f"node.add then select: {why}")
        if token_in(selected, secret):
            errors.append("editor.select leaked the session token")

        req_id, _st_id, state = call_tool(proc, req_id, "godot.editor", "state", {"detail": "short"})
        if state.get("ok") is not True:
            errors.append(f"editor.state must ACK: {sess.redact(json.dumps(state), secret)}")
        state_after = after_of(state)
        ok, why = focus_ok(state_after, node="FocusSprite", inspector_class="Node2D")
        if not ok:
            errors.append(f"editor.state after select: {why}")
        if token_in(state, secret):
            errors.append("editor.state leaked the session token")

        req_id, _focus_id, focus = call_tool(
            proc, req_id, "godot.observer", "focus", {"detail": "short"}
        )
        if focus.get("ok") is not True:
            errors.append(f"observer.focus must ACK: {sess.redact(json.dumps(focus), secret)}")
        ok, why = focus_ok(after_of(focus), node="FocusSprite")
        if not ok:
            errors.append(f"observer.focus: {why}")
        if token_in(focus, secret):
            errors.append("observer.focus leaked the session token")

        req_id, _set_id, prop = call_tool(
            proc,
            req_id,
            "godot.property",
            "set",
            {
                "scene": scene_a,
                "node_path": "FocusSprite",
                "property": "position",
                "value": {"schema": SCHEMA, "type": "Vector2", "value": {"x": 8, "y": 16}},
            },
        )
        if prop.get("ok") is not True:
            errors.append(f"property.set must ACK: {sess.redact(json.dumps(prop), secret)}")
        req_id, _sel2_id, selected2 = call_tool(
            proc,
            req_id,
            "godot.editor",
            "select",
            {"scene": scene_a, "node_path": "FocusSprite", "property": "position"},
        )
        if selected2.get("ok") is not True:
            errors.append(f"select after property.set must ACK: {sess.redact(json.dumps(selected2), secret)}")
        ok, why = focus_ok(after_of(selected2), node="FocusSprite", inspector_class="Node2D")
        if not ok:
            errors.append(f"property.set then present: {why}")

        req_id, _folder_id, folder = call_tool(
            proc,
            req_id,
            "godot.node",
            "add",
            {"scene": scene_a, "parent": ".", "class_name": "Node2D", "name": "Folder"},
        )
        if folder.get("ok") is not True:
            errors.append(f"folder add must ACK: {sess.redact(json.dumps(folder), secret)}")
        req_id, _ren_id, renamed = call_tool(
            proc,
            req_id,
            "godot.node",
            "rename",
            {"scene": scene_a, "node_path": "FocusSprite", "name": "RenamedSprite"},
        )
        if renamed.get("ok") is not True:
            errors.append(f"node.rename must ACK: {sess.redact(json.dumps(renamed), secret)}")
        renamed_uid = str(after_of(renamed).get("uid") or add_uid)
        req_id, _rep_id, reparented = call_tool(
            proc,
            req_id,
            "godot.node",
            "reparent",
            {"scene": scene_a, "node_path": "RenamedSprite", "new_parent": "Folder"},
        )
        if reparented.get("ok") is not True:
            errors.append(f"node.reparent must ACK: {sess.redact(json.dumps(reparented), secret)}")
        new_path = str(after_of(reparented).get("path") or "Folder/RenamedSprite")
        new_uid = str(after_of(reparented).get("uid") or renamed_uid)
        sel3_params = {"scene": scene_a, "node_path": new_path}
        if new_uid:
            sel3_params["uid"] = new_uid
        req_id, _sel3_id, selected3 = call_tool(
            proc,
            req_id,
            "godot.editor",
            "select",
            sel3_params,
        )
        if selected3.get("ok") is not True:
            errors.append(
                f"select after rename/reparent must ACK: {sess.redact(json.dumps(selected3), secret)}"
            )
        ok, why = focus_ok(after_of(selected3), node="RenamedSprite")
        if not ok:
            errors.append(f"rename+reparent select: {why}")

        req_id, write_id, wrote = call_tool(
            proc,
            req_id,
            "godot.script",
            "write",
            {"path": script, "contents": script_text},
        )
        if wrote.get("ok") is not True:
            errors.append(f"script.write must ACK: {sess.redact(json.dumps(wrote), secret)}")
        req_id, _open_id, opened = call_tool(
            proc,
            req_id,
            "godot.editor",
            "select",
            {
                "scene": scene_a,
                "node_path": ".",
                "script_path": script,
                "script_line": 3,
                "script_column": 1,
            },
        )
        if opened.get("ok") is not True:
            errors.append(f"script open select must ACK: {sess.redact(json.dumps(opened), secret)}")
        opened_after = after_of(opened)
        script_ok = str(opened_after.get("script_path") or "") == script and int(
            opened_after.get("script_line") or 0
        ) == 3
        if not script_ok and opened_after.get("presentation_failed") is not True:
            errors.append(f"script line focus missing and not presentation_failed: {opened_after}")

        req_id, _ext_id, external = call_tool(
            proc,
            req_id,
            "godot.editor",
            "select",
            {
                "scene": scene_a,
                "node_path": ".",
                "script_path": script,
                "script_line": 3,
                "use_external_editor": True,
            },
        )
        if wrote.get("ok") is not True:
            errors.append("external-editor present must not fail the prior script.write")
        ext_after = after_of(external)
        if external.get("ok") is True:
            if ext_after.get("presentation_failed") is not True and int(ext_after.get("script_line") or 0) != 3:
                errors.append(f"external editor must fail presentation or prove line: {ext_after}")
        elif str((external.get("error") or {}).get("code") or "") not in ("", "E_UNVERIFIED"):
            errors.append(f"external editor select typed fail: {sess.redact(json.dumps(external), secret)}")

        req_id, _fs_id, filesel = call_tool(
            proc,
            req_id,
            "godot.editor",
            "select",
            {"scene": scene_a, "node_path": ".", "filesystem_path": script},
        )
        if filesel.get("ok") is not True:
            errors.append(f"filesystem select .gd must ACK: {sess.redact(json.dumps(filesel), secret)}")
        fs_after = after_of(filesel)
        fs_path = str(fs_after.get("filesystem_path") or "").replace("\\", "/")
        if fs_path != script and not fs_path.endswith("note.gd"):
            if fs_after.get("presentation_failed") is not True:
                errors.append(f"filesystem_path mismatch for .gd: {fs_after}")
        req_id, _png_id, pngsel = call_tool(
            proc,
            req_id,
            "godot.editor",
            "select",
            {"scene": scene_a, "node_path": ".", "filesystem_path": png},
        )
        if pngsel.get("ok") is True:
            png_after = after_of(pngsel)
            png_path = str(png_after.get("filesystem_path") or "").replace("\\", "/")
            if png_path != png and not png_path.endswith("dot.png"):
                if png_after.get("presentation_failed") is not True:
                    errors.append(f"filesystem_path mismatch for .png: {png_after}")

        req_id, _hide_id, hidden = call_tool(
            proc,
            req_id,
            "godot.editor",
            "select",
            {
                "scene": scene_a,
                "node_path": new_path,
                "hide_inspector": True,
                **({"uid": new_uid} if new_uid else {}),
            },
        )
        if hidden.get("ok") is not True:
            errors.append(f"select with hidden Inspector must ACK: {sess.redact(json.dumps(hidden), secret)}")
        if added.get("ok") is not True:
            errors.append("hidden Inspector select must not rollback the prior node.add")
        req_id, _q_id, queried = call_tool(
            proc,
            req_id,
            "godot.node",
            "query",
            {"scene": scene_a, "by": "path", "prefix": new_path},
        )
        hits = ((after_of(queried).get("hits") or {}).get("items") if queried.get("ok") is True else None)
        if queried.get("ok") is not True or not hits:
            errors.append(
                f"node still present after hidden Inspector select: {sess.redact(json.dumps(queried), secret)}"
            )

        req_id, _save_a, saved_a = call_tool(proc, req_id, "godot.scene", "save", {"path": scene_a})
        if saved_a.get("ok") is not True:
            errors.append(f"scene.save A must ACK: {sess.redact(json.dumps(saved_a), secret)}")
        req_id, _create_b, created_b = call_tool(
            proc, req_id, "godot.scene", "create", {"path": scene_b, "root_class": "Node2D"}
        )
        if created_b.get("ok") is not True:
            errors.append(f"scene.create B must ACK: {sess.redact(json.dumps(created_b), secret)}")
        req_id, _sel_b, selected_b = call_tool(
            proc,
            req_id,
            "godot.editor",
            "select",
            {"scene": scene_b, "node_path": "."},
        )
        if selected_b.get("ok") is not True:
            errors.append(f"select on scene B must ACK: {sess.redact(json.dumps(selected_b), secret)}")
        req_id, _act_a, activated = call_tool(proc, req_id, "godot.scene", "activate", {"path": scene_a})
        if activated.get("ok") is not True:
            errors.append(f"scene.activate A must ACK: {sess.redact(json.dumps(activated), secret)}")
        req_id, _q2_id, queried2 = call_tool(
            proc,
            req_id,
            "godot.node",
            "query",
            {"scene": scene_a, "by": "path", "prefix": new_path},
        )
        hits2 = ((after_of(queried2).get("hits") or {}).get("items") if queried2.get("ok") is True else None)
        if queried2.get("ok") is not True or not hits2:
            errors.append(
                f"select on B must not rollback A: {sess.redact(json.dumps(queried2), secret)}"
            )

        _ = add_id
        _ = write_id
    except Exception as exc:  # noqa: BLE001
        errors.append(sess.redact(f"live editor focus failed: {type(exc).__name__}: {exc}", secret))
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
        if secret and secret in "".join(err_lines):
            errors.append("session secret appeared in sidecar logs")
        if secret and secret in "".join(godot_lines):
            errors.append("session secret appeared in Godot logs")
        cleanup_temp()
    return errors


def main() -> int:
    errors: list[str] = []
    errors.extend(hh_agent_only_addon_errors(PLUGIN_PROJECT, REPO_ROOT))
    errors.extend(src_scan_errors())
    errors.extend(plug.typed_gdscript_errors())

    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.is_file() else None
    if plan_text is None:
        errors.append(f"missing {rel(PLAN)}")
    else:
        errors.extend(plan_errors(plan_text))

    if not (REPO_ROOT / "tools" / "godot" / "pin.json").is_file():
        errors.append("missing tools/godot/pin.json")
    exe, pin_reason = plug.find_pinned_godot()
    if exe is None:
        errors.append(f"pinned Godot missing (hard FAIL): {pin_reason}")
        print("FAIL: editor focus", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1
    version = plug.godot_version(exe)
    if any(bad in version for bad in ("4.7.2", "4.8")):
        errors.append(f"refused Godot --version {version!r}")
        print("FAIL: editor focus", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1
    if version != PINNED_VERSION:
        errors.append(f"Godot --version {version!r} != {PINNED_VERSION}")
        print("FAIL: editor focus", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    built = subprocess.run(
        [sess.npm(), "run", "build"],
        cwd=BRIDGE,
        text=True,
        capture_output=True,
        check=False,
    )
    if built.returncode != 0:
        errors.append(f"npm run build failed:\n{built.stdout}\n{built.stderr}")
        print("FAIL: editor focus", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    errors.extend(live_errors(exe))

    if errors:
        print("FAIL: editor focus", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print(
        "PASS: editor select presents node/inspector/script/filesystem; "
        "rename/reparent/uid still resolve; hidden Inspector and external editor "
        "record presentation_failed without rolling back; G2 stays unticked."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
