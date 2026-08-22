#!/usr/bin/env python3
"""R4-WP4: Watch/Fast/Replay presentation scheduler and backpressure.

Does not tick the 20-8 plan. Does not start R4-WP5. Does not tick G2 VISIBLE.
Pin missing is a hard FAIL. No skip-PASS. No Review Center.
"""

from __future__ import annotations

import hashlib
import json
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
import test_scene_lifecycle as life
import test_session as sess

BRIDGE = REPO_ROOT / "bridge"
PLAN = REPO_ROOT / "zdocs" / "20-8-godot-agent-autopilot-plan.txt"
PLUGIN_PROJECT = REPO_ROOT / "godot" / "plugin-project"
ADDON = PLUGIN_PROJECT / "addons" / "hh_agent"
PINNED_VERSION = plug.PINNED_VERSION
TEMP_DIR = PLUGIN_PROJECT / "r4w4"
VENDOR_NEEDLES = plug.VENDOR_NEEDLES
SCHEMA = "hh-godot-variant/1"
MIN_LIVE = 200
TARGET_LIVE = 5000
FALLBACK_LIVE = 500
LIVE_BUDGET_S = 110.0
STRESS_CELLS = 5000


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def plan_errors(text: str) -> list[str]:
    """Keep R4-WP4 [ ] while unticked; after coordinator tick allow R4-WP5+."""
    errors: list[str] = []
    current = ""
    wp4 = None
    wp5 = None
    g2 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R4-WP4\b", stripped):
            wp4 = stripped
        if re.match(r"^R4-WP5\b", stripped):
            wp5 = stripped
        if stripped.startswith("G2 VISIBLE") and ("[x]" in stripped or "[ ]" in stripped):
            if g2 is None:
                g2 = stripped
    if wp4 is None:
        return ["plan missing R4-WP4 heading"]
    ticked = bool(re.search(r"\[x\]", wp4, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp4:
            errors.append("R4-WP4 heading must keep [ ] until coordinator tick")
        if current != "R4-WP4":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R4-WP4 while WP4 is unticked)")
        if wp5 and re.search(r"\[x\]", wp5, re.IGNORECASE):
            errors.append("R4-WP5 must stay unticked; this WP does not start Review Center")
    elif not re.match(r"^R4-WP([5-9]|\d{2,})$|^R[5-9]-WP\d+$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R4-WP5+ after R4-WP4 tick)")
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
    scheduler = ADDON / "core" / "hh_scheduler.gd"
    overlay = ADDON / "ui" / "overlay" / "hh_overlay.gd"
    router = ADDON / "core" / "hh_router.gd"
    plugin = ADDON / "plugin.gd"
    reads = ADDON / "core" / "hh_read_adapters.gd"
    if not scheduler.is_file():
        errors.append("missing core/hh_scheduler.gd")
    else:
        text = scheduler.read_text(encoding="utf-8")
        for needle in ("coalesce", "dropped_present", "dropped_audit", "backpressure", "PRESENT_QUEUE"):
            if needle not in text and needle.lower() not in text.lower():
                if needle == "backpressure" and "drop" not in text:
                    errors.append("scheduler must implement present-frame backpressure")
        if "dropped_present" not in text:
            errors.append("scheduler must count dropped_present")
        if "dropped_audit" not in text:
            errors.append("scheduler must expose dropped_audit (stay 0)")
        if "coalesce" not in text:
            errors.append("scheduler must coalesce spam property/cell presents")
        if "create_action" in text or "EditorUndoRedoManager" in text:
            errors.append("scheduler must not create UndoRedo / mutate the document")
        if "dispatch(" in text:
            errors.append("scheduler replay must not call the command router")
        if "review" in text.lower() and "center" in text.lower():
            errors.append("R4-WP4 must not implement Review Center")
    if overlay.is_file():
        text = overlay.read_text(encoding="utf-8")
        if "HHAgentNodeAdapter" in text or "HHAgentPropertyAdapter" in text:
            errors.append("overlay must not call mutate adapters")
        if "dispatch(" in text:
            errors.append("overlay replay must not call dispatch()")
    if router.is_file():
        text = router.read_text(encoding="utf-8")
        if "after_success" not in text:
            errors.append("router must still call after_success after mutates")
        if "hh_scheduler" not in text and "HHAgentScheduler" not in text:
            errors.append("router must queue present work through the scheduler")
        if "_presenter.after_success" in text:
            errors.append("mutate ACK must not await presenter on the ACK path")
    if plugin.is_file():
        text = plugin.read_text(encoding="utf-8")
        if "hh_scheduler" not in text and "HHAgentScheduler" not in text:
            errors.append("plugin must host HHAgentScheduler")
        if "_scheduler.tick" not in text:
            errors.append("plugin must tick the scheduler off the inbound drain")
    if reads.is_file():
        text = reads.read_text(encoding="utf-8")
        if "_observer_scheduler" not in text:
            errors.append("godot.observer scheduler read adapter missing")
    review = ADDON / "ui" / "review"
    if review.exists():
        errors.append("R4-WP4 must not add Review Center UI")
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


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def vec2(x: float, y: float) -> dict:
    return {"schema": SCHEMA, "type": "Vector2", "value": {"x": x, "y": y}}


def tree_total(body: dict) -> int:
    after = after_of(body)
    tree = after.get("tree") if isinstance(after.get("tree"), dict) else {}
    return int(tree.get("total") or 0)


def scheduler_of(body: dict) -> dict:
    after = after_of(body)
    sched = after.get("scheduler") if isinstance(after.get("scheduler"), dict) else after
    return sched if isinstance(sched, dict) else {}


def live_errors(exe: Path) -> tuple[list[str], str]:
    errors: list[str] = []
    banner_note = "live Fast count unknown"
    cleanup_temp()
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    proc: subprocess.Popen[str] | None = None
    godot: subprocess.Popen[str] | None = None
    desc_path: Path | None = None
    secret = ""
    err_lines: list[str] = []
    godot_lines: list[str] = []
    scene = "res://r4w4/sched.tscn"
    scene_abs = PLUGIN_PROJECT / "r4w4" / "sched.tscn"
    req_id = 2
    live_fast = 0
    try:
        proc, desc_path, secret, err_lines = life.start_sidecar()
        godot, godot_lines = life.start_godot(exe)
        req_id, hello, last = life.wait_hello(proc, godot, req_id)
        if not hello:
            errors.append(
                "live plugin hello/noop failed: "
                f"{sess.redact(json.dumps(last), secret)}; godot={''.join(godot_lines)[-1500:]}"
            )
            return errors, banner_note

        req_id, _create_id, created = call_tool(
            proc, req_id, "godot.scene", "create", {"path": scene, "root_class": "Node2D"}
        )
        if created.get("ok") is not True:
            errors.append(f"scene.create must ACK: {sess.redact(json.dumps(created), secret)}")

        req_id, _add_id, added = call_tool(
            proc,
            req_id,
            "godot.node",
            "add",
            {"scene": scene, "parent": ".", "class_name": "Node2D", "name": "Cell"},
            presentation={"mode": "fast"},
        )
        if added.get("ok") is not True:
            errors.append(f"node.add must ACK: {sess.redact(json.dumps(added), secret)}")

        req_id, _save_id, saved = call_tool(proc, req_id, "godot.scene", "save", {"path": scene})
        if saved.get("ok") is not True:
            errors.append(f"scene.save must ACK: {sess.redact(json.dumps(saved), secret)}")
        if not scene_abs.is_file():
            errors.append(f"saved scene missing: {scene}")
            return errors, banner_note

        t0 = time.time()
        last_fast_id = ""
        probe = 20
        for i in range(probe):
            req_id, last_fast_id, body = call_tool(
                proc,
                req_id,
                "godot.property",
                "set",
                {
                    "scene": scene,
                    "node_path": "Cell",
                    "property": "position",
                    "value": vec2(float(i), 0.0),
                },
                presentation={"mode": "fast"},
            )
            if body.get("ok") is not True:
                errors.append(f"Fast property.set {i} must ACK: {sess.redact(json.dumps(body), secret)}")
                break
            live_fast += 1
        probe_s = max(0.001, time.time() - t0)
        ms_each = (probe_s / max(1, live_fast)) * 1000.0
        remaining = LIVE_BUDGET_S - (time.time() - t0)
        if live_fast >= probe and ms_each * TARGET_LIVE < 100_000:
            want = TARGET_LIVE
        elif live_fast >= probe and ms_each * FALLBACK_LIVE < remaining * 1000.0:
            want = FALLBACK_LIVE
        else:
            want = MIN_LIVE
        for i in range(live_fast, want):
            if time.time() - t0 > LIVE_BUDGET_S and live_fast >= MIN_LIVE:
                break
            req_id, last_fast_id, body = call_tool(
                proc,
                req_id,
                "godot.property",
                "set",
                {
                    "scene": scene,
                    "node_path": "Cell",
                    "property": "position",
                    "value": vec2(float(i), 1.0),
                },
                presentation={"mode": "fast"},
            )
            if body.get("ok") is not True:
                errors.append(f"Fast property.set {i} must ACK: {sess.redact(json.dumps(body), secret)}")
                break
            live_fast += 1
        fast_wall = time.time() - t0
        if live_fast < MIN_LIVE:
            errors.append(f"Fast live ACKs={live_fast} (need >={MIN_LIVE})")
        if fast_wall > 20 * 60:
            errors.append(f"Fast {live_fast} property.set took {fast_wall:.1f}s (>= 20 minutes)")

        req_id, _tl_id, timeline = call_tool(
            proc,
            req_id,
            "godot.observer",
            "timeline",
            {"detail": "short", "limit": 100},
            presentation={"mode": "fast"},
        )
        if timeline.get("ok") is not True:
            errors.append(f"observer.timeline must ACK: {sess.redact(json.dumps(timeline), secret)}")
        dock = after_of(timeline).get("dock") if isinstance(after_of(timeline).get("dock"), dict) else {}
        rows = dock.get("rows") if isinstance(dock.get("rows"), dict) else {}
        total_rows = int(rows.get("total") or 0)
        if total_rows < live_fast:
            errors.append(f"Fast must still record timeline rows: total={total_rows} live={live_fast}")
        if token_in(timeline, secret):
            errors.append("observer.timeline leaked the session token")

        req_id, _ov_id, fast_ov = call_tool(
            proc,
            req_id,
            "godot.observer",
            "overlay",
            {"detail": "short"},
            presentation={"mode": "fast"},
        )
        if fast_ov.get("ok") is not True:
            errors.append(f"observer.overlay Fast must ACK: {sess.redact(json.dumps(fast_ov), secret)}")
        if after_of(fast_ov).get("enabled") is not False:
            errors.append(f"Fast overlay drawn/enabled must be false: {after_of(fast_ov)}")
        if token_in(fast_ov, secret):
            errors.append("Fast observer.overlay leaked the session token")

        req_id, _sch_id, fast_sch = call_tool(
            proc, req_id, "godot.observer", "scheduler", {"detail": "short"}
        )
        if fast_sch.get("ok") is not True:
            errors.append(f"observer.scheduler must ACK: {sess.redact(json.dumps(fast_sch), secret)}")
        fast_sched = scheduler_of(fast_sch)
        if int(fast_sched.get("dropped_audit") or 0) != 0:
            errors.append(f"dropped_audit must stay 0: {fast_sched}")
        if token_in(fast_sch, secret):
            errors.append("observer.scheduler leaked the session token")
        lanes = fast_sched.get("lanes")
        if not isinstance(lanes, list):
            errors.append(f"scheduler snapshot missing lanes: {fast_sched}")

        t_watch = time.time()
        for i in range(50):
            req_id, _wid, wbody = call_tool(
                proc,
                req_id,
                "godot.property",
                "set",
                {
                    "scene": scene,
                    "node_path": "Cell",
                    "property": "position",
                    "value": vec2(float(i), 8.0),
                },
                presentation={"mode": "watch"},
            )
            if wbody.get("ok") is not True:
                errors.append(f"Watch property.set {i} must ACK: {sess.redact(json.dumps(wbody), secret)}")
                break
        if time.time() - t_watch > 20 * 60:
            errors.append("Watch 50 property.set took >= 20 minutes")

        req_id, _wsch_id, watch_sch = call_tool(
            proc, req_id, "godot.observer", "scheduler", {"detail": "short"}
        )
        watch_sched = scheduler_of(watch_sch)
        coalesced = int(watch_sched.get("coalesced") or 0)
        dropped_present = int(watch_sched.get("dropped_present") or 0)
        applied_present = int(watch_sched.get("applied_present") or 0)
        queue_depth = int(watch_sched.get("queue_depth") or 0)
        present_frames = applied_present + queue_depth
        if coalesced < 1 and dropped_present < 1 and present_frames >= 50:
            errors.append(
                "Watch 50 property.set on the same property must coalesce or drop present frames: "
                f"{watch_sched}"
            )
        if int(watch_sched.get("dropped_audit") or 0) != 0:
            errors.append(f"Watch dropped_audit must stay 0: {watch_sched}")
        if token_in(watch_sch, secret):
            errors.append("Watch observer.scheduler leaked the session token")

        for i in range(24):
            mode = "fast" if i % 2 == 0 else "watch"
            req_id, _sid, sbody = call_tool(
                proc,
                req_id,
                "godot.property",
                "set",
                {
                    "scene": scene,
                    "node_path": "Cell",
                    "property": "position",
                    "value": vec2(float(i), 16.0),
                },
                presentation={"mode": mode},
            )
            if sbody.get("ok") is not True:
                errors.append(
                    f"mid-loop {mode} property.set must still ACK: "
                    f"{sess.redact(json.dumps(sbody), secret)}"
                )
                break

        req_id, _save2_id, saved2 = call_tool(proc, req_id, "godot.scene", "save", {"path": scene})
        if saved2.get("ok") is not True:
            errors.append(f"scene.save before replay must ACK: {sess.redact(json.dumps(saved2), secret)}")
        before_sha = sha256_file(scene_abs)
        req_id, _read_id, before_read = call_tool(proc, req_id, "godot.scene", "read", {"path": scene})
        before_nodes = tree_total(before_read)

        req_id, _rep_id, replayed = call_tool(
            proc,
            req_id,
            "godot.editor",
            "replay",
            {"command_id": last_fast_id},
            presentation={"mode": "fast"},
        )
        if replayed.get("ok") is not True:
            errors.append(f"Fast editor.replay must ACK: {sess.redact(json.dumps(replayed), secret)}")
        if replayed.get("changed") is True:
            errors.append("replay must not change the document")
        fast_last = after_of(replayed).get("last_replay")
        if not isinstance(fast_last, dict) or fast_last.get("drawn") is not False:
            errors.append(f"Fast replay drawn must be false: {fast_last}")
        if sha256_file(scene_abs) != before_sha:
            errors.append("replay after Fast changed .tscn SHA")
        req_id, _read2_id, after_read = call_tool(proc, req_id, "godot.scene", "read", {"path": scene})
        if tree_total(after_read) != before_nodes:
            errors.append(f"replay added a node: {before_nodes} -> {tree_total(after_read)}")

        req_id, _st_id, stressed = call_tool(
            proc,
            req_id,
            "godot.observer",
            "scheduler",
            {"detail": "short", "stress": STRESS_CELLS, "unique_keys": True},
        )
        if stressed.get("ok") is not True:
            errors.append(f"scheduler.stress must ACK: {sess.redact(json.dumps(stressed), secret)}")
        stress_after = scheduler_of(stressed)
        if int(stress_after.get("dropped_audit") or 0) != 0:
            errors.append(f"stress dropped_audit must stay 0: {stress_after}")
        if int(stress_after.get("event_count") or 0) < STRESS_CELLS:
            errors.append(f"stress must record {STRESS_CELLS} cell events: {stress_after}")
        if int(stress_after.get("dropped_present") or 0) < 1 and int(stress_after.get("coalesced") or 0) < 1:
            errors.append(f"5000 cell stress must drop or coalesce present frames: {stress_after}")
        if token_in(stressed, secret):
            errors.append("stress snapshot leaked the session token")
        lanes2 = stress_after.get("lanes")
        if not isinstance(lanes2, list) or len(lanes2) < 1:
            errors.append(f"multi-agent lanes missing after stress: {stress_after}")

        banner_note = (
            f"live Fast property.set={live_fast} in {fast_wall:.1f}s "
            f"(~{ms_each:.0f}ms/op probe); stress {STRESS_CELLS} cell events without UndoRedo"
        )
        if live_fast >= TARGET_LIVE:
            banner_note = f"live Fast 5000 property.set in {fast_wall:.1f}s; stress {STRESS_CELLS} also recorded"
        elif live_fast >= FALLBACK_LIVE:
            banner_note = (
                f"live Fast {live_fast} property.set in {fast_wall:.1f}s "
                f"(5000 live would exceed ~2 min at ~{ms_each:.0f}ms/op); "
                f"scheduler.stress recorded {STRESS_CELLS} cell events without UndoRedo"
            )
        else:
            banner_note = (
                f"live Fast {live_fast} property.set in {fast_wall:.1f}s "
                f"(>=200 required); scheduler.stress recorded {STRESS_CELLS} cell events without UndoRedo"
            )
    except Exception as exc:  # noqa: BLE001
        errors.append(sess.redact(f"live presentation scheduler failed: {type(exc).__name__}: {exc}", secret))
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
    return errors, banner_note


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
        print("FAIL: presentation scheduler", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1
    version = plug.godot_version(exe)
    if any(bad in version for bad in ("4.7.2", "4.8")):
        errors.append(f"refused Godot --version {version!r}")
        print("FAIL: presentation scheduler", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1
    if version != PINNED_VERSION:
        errors.append(f"Godot --version {version!r} != {PINNED_VERSION}")
        print("FAIL: presentation scheduler", file=sys.stderr)
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
        print("FAIL: presentation scheduler", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    live, banner_note = live_errors(exe)
    errors.extend(live)

    if errors:
        print("FAIL: presentation scheduler", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print(
        "PASS: Watch coalesces spam presents; Fast ACKs without draw and still writes timeline; "
        "replay walks the event log (no command router); backpressure drops PRESENT only "
        f"(dropped_audit=0); G2 stays unticked. {banner_note}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
