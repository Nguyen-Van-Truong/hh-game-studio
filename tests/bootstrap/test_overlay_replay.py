#!/usr/bin/env python3
"""R4-WP3: viewport overlay model and semantic drag replay.

Does not tick the 20-8 plan. Does not start R4-WP4. Does not tick G2 VISIBLE.
Pin missing is a hard FAIL. No skip-PASS. No pixel mutation / RPA.
"""

from __future__ import annotations

import hashlib
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
PINNED_VERSION = plug.PINNED_VERSION
TEMP_DIR = PLUGIN_PROJECT / "r4w3"
VENDOR_NEEDLES = plug.VENDOR_NEEDLES


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def plan_errors(text: str) -> list[str]:
    """Keep R4-WP3 [ ] while unticked; after coordinator tick allow R4-WP4+."""
    errors: list[str] = []
    current = ""
    wp3 = None
    g2 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R4-WP3\b", stripped):
            wp3 = stripped
        if stripped.startswith("G2 VISIBLE"):
            g2 = stripped
    if wp3 is None:
        return ["plan missing R4-WP3 heading"]
    ticked = bool(re.search(r"\[x\]", wp3, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp3:
            errors.append("R4-WP3 heading must keep [ ] until coordinator tick")
        if current != "R4-WP3":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R4-WP3 while WP3 is unticked)")
    elif not re.match(r"^R4-WP([4-9]|\d{2,})$|^R[5-9]-WP\d+$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R4-WP4+ after R4-WP3 tick)")
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
    overlay = ADDON / "ui" / "overlay" / "hh_overlay.gd"
    plugin = ADDON / "plugin.gd"
    presenter = ADDON / "core" / "hh_presenter.gd"
    router = ADDON / "core" / "hh_router.gd"
    reads = ADDON / "core" / "hh_read_adapters.gd"
    if not overlay.is_file():
        errors.append("missing ui/overlay/hh_overlay.gd")
    else:
        text = overlay.read_text(encoding="utf-8")
        if "R1-WP4 stock POC" in text or "hh_stock_poc" in text:
            errors.append("overlay must not copy the stock-poc Control")
        for needle in ("ResourceSaver", "FileAccess.WRITE", "save_scene", "create_action"):
            if needle in text:
                errors.append(f"overlay must not mutate disk/UndoRedo ({needle})")
        if "HHAgentNodeAdapter" in text or "HHAgentPropertyAdapter" in text:
            errors.append("overlay must not call mutate adapters")
        if "backpressure" in text or "coalesce" in text:
            errors.append("R4-WP3 must not implement scheduler/backpressure")
    if plugin.is_file():
        text = plugin.read_text(encoding="utf-8")
        if "_forward_canvas_draw_over_viewport" not in text:
            errors.append("plugin must implement _forward_canvas_draw_over_viewport")
        if "set_force_draw_over_forwarding_enabled" not in text:
            errors.append("plugin must enable canvas overlay forwarding")
        if "hh_overlay" not in text:
            errors.append("plugin must host HHAgentOverlay")
    if presenter.is_file():
        text = presenter.read_text(encoding="utf-8")
        if "ghost" in text.lower() or "forward_canvas" in text:
            errors.append("presenter must stay select/focus only; overlay lives elsewhere")
    if router.is_file():
        text = router.read_text(encoding="utf-8")
        if "frame_view" not in text or "replay" not in text:
            errors.append("router must dispatch editor.frame_view / editor.replay")
        if "after_success" not in text:
            errors.append("router must still present after successful mutates")
    if reads.is_file():
        text = reads.read_text(encoding="utf-8")
        if "_observer_overlay" not in text:
            errors.append("godot.observer overlay read adapter missing")
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


def token_in(obj: object, secret: str) -> bool:
    if not secret:
        return False
    return secret in json.dumps(obj)


def highlight_has(overlay: dict, node: str) -> bool:
    highlights = overlay.get("highlights")
    if not isinstance(highlights, list):
        return False
    for item in highlights:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "")
        label = str(item.get("label") or "")
        if node == path or path.endswith("/" + node) or node in label:
            return True
    return False


def world_rects(overlay: dict) -> list[tuple[float, float, float, float]]:
    out: list[tuple[float, float, float, float]] = []
    highlights = overlay.get("highlights")
    if not isinstance(highlights, list):
        return out
    for item in highlights:
        if not isinstance(item, dict):
            continue
        rect = item.get("rect") if isinstance(item.get("rect"), dict) else {}
        out.append(
            (
                float(rect.get("x") or 0.0),
                float(rect.get("y") or 0.0),
                float(rect.get("w") or 0.0),
                float(rect.get("h") or 0.0),
            )
        )
    return out


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    scene = "res://r4w3/overlay.tscn"
    scene_abs = PLUGIN_PROJECT / "r4w3" / "overlay.tscn"
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

        req_id, _create_id, created = call_tool(
            proc, req_id, "godot.scene", "create", {"path": scene, "root_class": "Node2D"}
        )
        if created.get("ok") is not True:
            errors.append(f"scene.create must ACK: {sess.redact(json.dumps(created), secret)}")

        req_id, add_id, added = call_tool(
            proc,
            req_id,
            "godot.node",
            "add",
            {"scene": scene, "parent": ".", "class_name": "Node2D", "name": "OverlaySprite"},
            presentation={"mode": "watch"},
        )
        if added.get("ok") is not True:
            errors.append(f"node.add must ACK: {sess.redact(json.dumps(added), secret)}")
        if after_of(added).get("path") != "OverlaySprite":
            errors.append(f"node.add path drifted: {after_of(added)}")

        req_id, _save_id, saved = call_tool(proc, req_id, "godot.scene", "save", {"path": scene})
        if saved.get("ok") is not True:
            errors.append(f"scene.save must ACK: {sess.redact(json.dumps(saved), secret)}")
        if not scene_abs.is_file():
            errors.append(f"saved scene missing: {scene}")
            return errors

        req_id, _read_id, before_read = call_tool(proc, req_id, "godot.scene", "read", {"path": scene})
        before_hist = str(after_of(before_read).get("history_version") or "")
        before_sha = sha256_file(scene_abs)

        req_id, _ov_id, watch_ov = call_tool(
            proc,
            req_id,
            "godot.observer",
            "overlay",
            {"detail": "short"},
            presentation={"mode": "watch"},
        )
        if watch_ov.get("ok") is not True:
            errors.append(f"observer.overlay Watch must ACK: {sess.redact(json.dumps(watch_ov), secret)}")
        watch_after = after_of(watch_ov)
        if token_in(watch_ov, secret):
            errors.append("observer.overlay leaked the session token")
        if not highlight_has(watch_after, "OverlaySprite"):
            errors.append(
                "Watch present must populate a highlight for OverlaySprite "
                f"(honest model): {watch_after}"
            )
        view = watch_after.get("view") if isinstance(watch_after.get("view"), dict) else {}
        if str(view.get("space") or "") != "world":
            errors.append(f"overlay model must be world-space (DPI/zoom independent): {view}")
        if "zoom" not in view or "dpi_scale" not in view:
            errors.append(f"overlay view missing zoom/dpi_scale: {view}")
        enabled = watch_after.get("enabled")
        headless = enabled is False
        if enabled not in (True, False):
            errors.append(f"overlay.enabled must be a bool: {watch_after}")
        if enabled is True and headless:
            errors.append("headless overlay must stay disabled")

        req_id, _ov2_id, watch_ov2 = call_tool(
            proc,
            req_id,
            "godot.observer",
            "overlay",
            {"detail": "full"},
            presentation={"mode": "watch"},
        )
        if world_rects(after_of(watch_ov2)) != world_rects(watch_after):
            errors.append("overlay world rects drifted across snapshot/detail (must be zoom/DPI independent)")

        req_id, _rep_id, replayed = call_tool(
            proc,
            req_id,
            "godot.editor",
            "replay",
            {"command_id": add_id},
            presentation={"mode": "watch"},
        )
        if replayed.get("ok") is not True:
            errors.append(f"editor.replay must ACK: {sess.redact(json.dumps(replayed), secret)}")
        if replayed.get("changed") is True:
            errors.append("editor.replay must not change the document")
        if token_in(replayed, secret):
            errors.append("editor.replay leaked the session token")
        replay_after = after_of(replayed)
        last_replay = replay_after.get("last_replay") if isinstance(replay_after.get("last_replay"), dict) else {}
        drawn = last_replay.get("drawn") is True
        if headless and drawn:
            errors.append(f"headless replay must ACK drawn=false: {last_replay}")
        if not headless and not drawn:
            errors.append(f"visible Watch replay must set drawn=true: {last_replay}")
        if drawn:
            ms = int(last_replay.get("ms") or 0)
            if ms < 200 or ms > 400:
                errors.append(f"replay ms must be 200–400 when drawn: {last_replay}")
        elif int(last_replay.get("ms") or 0) != 0:
            errors.append(f"undrawn replay must be a no-op ms=0: {last_replay}")
        if "add" not in str(last_replay.get("action") or ""):
            errors.append(f"last_replay.action should name the add: {last_replay}")

        after_sha = sha256_file(scene_abs)
        if after_sha != before_sha:
            errors.append("replay changed .tscn SHA")
        req_id, _read2_id, after_read = call_tool(proc, req_id, "godot.scene", "read", {"path": scene})
        after_hist = str(after_of(after_read).get("history_version") or "")
        if after_hist != before_hist:
            errors.append(f"replay changed UndoRedo history {before_hist!r} -> {after_hist!r}")
        overlay_hist = replay_after.get("history_count", replay_after.get("history_version"))
        watch_hist = watch_after.get("history_count", watch_after.get("history_version"))
        if overlay_hist != watch_hist:
            errors.append(f"replay overlay history drifted {watch_hist!r} -> {overlay_hist!r}")

        req_id, _fast_ov_id, fast_ov = call_tool(
            proc,
            req_id,
            "godot.observer",
            "overlay",
            {"detail": "short"},
            presentation={"mode": "fast"},
        )
        if fast_ov.get("ok") is not True:
            errors.append(f"observer.overlay Fast must ACK: {sess.redact(json.dumps(fast_ov), secret)}")
        fast_after = after_of(fast_ov)
        if fast_after.get("enabled") is not False:
            errors.append(f"Fast overlay enabled must be false: {fast_after}")
        if token_in(fast_ov, secret):
            errors.append("Fast observer.overlay leaked the session token")

        req_id, _fast_rep_id, fast_replay = call_tool(
            proc,
            req_id,
            "godot.editor",
            "replay",
            {"command_id": add_id},
            presentation={"mode": "fast"},
        )
        if fast_replay.get("ok") is not True:
            errors.append(f"Fast editor.replay must ACK no-op: {sess.redact(json.dumps(fast_replay), secret)}")
        fast_last = after_of(fast_replay).get("last_replay")
        if not isinstance(fast_last, dict) or fast_last.get("drawn") is not False:
            errors.append(f"Fast replay drawn must be false: {fast_last}")
        if sha256_file(scene_abs) != before_sha:
            errors.append("Fast replay changed .tscn SHA")
    except Exception as exc:  # noqa: BLE001
        errors.append(sess.redact(f"live overlay replay failed: {type(exc).__name__}: {exc}", secret))
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
        print("FAIL: overlay replay", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1
    version = plug.godot_version(exe)
    if any(bad in version for bad in ("4.7.2", "4.8")):
        errors.append(f"refused Godot --version {version!r}")
        print("FAIL: overlay replay", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1
    if version != PINNED_VERSION:
        errors.append(f"Godot --version {version!r} != {PINNED_VERSION}")
        print("FAIL: overlay replay", file=sys.stderr)
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
        print("FAIL: overlay replay", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    errors.extend(live_errors(exe))

    if errors:
        print("FAIL: overlay replay", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print(
        "PASS: overlay model populated after Watch present; Fast/headless drawn=false; "
        "replay leaves .tscn SHA and UndoRedo history unchanged; G2 stays unticked. "
        "No pixel golden claimed."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
