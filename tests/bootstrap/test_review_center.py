#!/usr/bin/env python3
"""R4-WP5: Review Center — card, paged diff, replay, checkpoint revert.

Does not tick the 20-8 plan. Does not start R4-WP6. Does not tick G2 VISIBLE.
Pin missing is a hard FAIL. No skip-PASS. Review is async (no per-action approve).
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
TEMP_DIR = PLUGIN_PROJECT / "r4w5"
REVIEW_DIR = PLUGIN_PROJECT / ".hh-agent" / "review"
VENDOR_NEEDLES = plug.VENDOR_NEEDLES
PAGE_CAP = 100
DIFF_LINES = 2000


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def plan_errors(text: str) -> list[str]:
    """Keep R4-WP5 [ ] while unticked; after coordinator tick allow R4-WP6+."""
    errors: list[str] = []
    current = ""
    wp5 = None
    wp6 = None
    g2 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R4-WP5\b", stripped):
            wp5 = stripped
        if re.match(r"^R4-WP6\b", stripped):
            wp6 = stripped
        if stripped.startswith("G2 VISIBLE") and ("[x]" in stripped or "[ ]" in stripped):
            if g2 is None:
                g2 = stripped
    if wp5 is None:
        return ["plan missing R4-WP5 heading"]
    ticked = bool(re.search(r"\[x\]", wp5, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp5:
            errors.append("R4-WP5 heading must keep [ ] until coordinator tick")
        if current != "R4-WP5":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R4-WP5 while WP5 is unticked)")
        if wp6 and re.search(r"\[x\]", wp6, re.IGNORECASE):
            errors.append("R4-WP6 must stay unticked; this WP does not start visible E2E")
    elif not re.match(r"^R4-WP([6-9]|\d{2,})$|^R[5-9]-WP\d+$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R4-WP6+ after R4-WP5 tick)")
    return errors


def cleanup_temp() -> None:
    if TEMP_DIR.is_dir():
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
    if REVIEW_DIR.is_dir():
        shutil.rmtree(REVIEW_DIR, ignore_errors=True)
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
    dock = ADDON / "ui" / "review" / "hh_review_dock.gd"
    store = ADDON / "core" / "hh_review_store.gd"
    plugin = ADDON / "plugin.gd"
    reads = ADDON / "core" / "hh_read_adapters.gd"
    router = ADDON / "core" / "hh_router.gd"
    overlay = ADDON / "ui" / "overlay" / "hh_overlay.gd"
    if not dock.is_file():
        errors.append("missing ui/review/hh_review_dock.gd")
    else:
        text = dock.read_text(encoding="utf-8")
        for label in ("Before", "After", "Diff", "Replay", "Revert"):
            if label not in text:
                errors.append(f"review dock missing {label} control")
        if "token" in text.lower() and "never" not in text.lower():
            errors.append("review dock must not display the session token")
        if re.search(r'_add_button\([^)]*"Approve"|text = "Approve"|human signoff|Sign G2', text):
            errors.append("review dock must not add a per-action or G2 signoff gate")
    if not store.is_file():
        errors.append("missing core/hh_review_store.gd")
    else:
        text = store.read_text(encoding="utf-8")
        if "artifact_ok" not in text:
            errors.append("review store must expose artifact_ok")
        if "REVIEW_DIR" not in text and ".hh-agent/review" not in text:
            errors.append("review store must read .hh-agent/review/")
        if "approve_required" not in text:
            errors.append("review store must declare review is not a per-action approve gate")
    if plugin.is_file():
        text = plugin.read_text(encoding="utf-8")
        if "hh_review" not in text:
            errors.append("plugin must host the Review Center dock")
        if "remove_control_from_docks" not in text:
            errors.append("plugin must still clean docks on exit")
        if "view_changed.connect" not in text:
            errors.append("plugin must connect review dock view_changed")
        if "revert_requested.connect" not in text:
            errors.append("plugin must connect review dock revert_requested")
        if "git.revert_checkpoint" not in text and "revert_checkpoint" not in text:
            errors.append("plugin revert must reach git.revert_checkpoint / local restore")
    if reads.is_file():
        text = reads.read_text(encoding="utf-8")
        if "_review_card" not in text:
            errors.append("godot.review card adapter missing")
        if "_review_diff" not in text:
            errors.append("godot.review diff adapter missing")
        if "_review_write_card" not in text and "write_card" not in text:
            errors.append("godot.review write_card adapter missing")
        if "_observer_review" not in text:
            errors.append("godot.observer review adapter missing")
    if router.is_file():
        text = router.read_text(encoding="utf-8")
        if "godot.review" not in text or "replay" not in text:
            errors.append("router must dispatch review.replay to the overlay")
    if overlay.is_file():
        text = overlay.read_text(encoding="utf-8")
        if "godot.review" not in text:
            errors.append("overlay must accept review.replay")
        if "HHAgentNodeAdapter" in text or "create_action" in text:
            errors.append("review replay must stay presentation-only")
        if "fallback_last" not in text and "strict_id" not in text:
            errors.append("overlay must not fall back to last record on review.replay miss")
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
) -> tuple[int, str, dict]:
    cid = life.new_ulid()
    resp = mcp_call(
        proc,
        req_id,
        method,
        {"action": action, "params": params, "command_id": cid},
        timeout,
    )
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


def unproven_card_errors(body: dict, after: dict, label: str) -> list[str]:
    errors: list[str] = []
    post = body.get("postcondition") if isinstance(body.get("postcondition"), dict) else {}
    checks = post.get("checks") if isinstance(post.get("checks"), list) else []
    if post.get("verified") is True:
        errors.append(f"{label} must not stamp verified=true: {post}")
    if "review_card_snapshot" in checks and post.get("verified") is True:
        errors.append(f"{label} must not stamp review_card_snapshot as proven: {post}")
    if body.get("ok") is True:
        if after.get("artifact_ok") is not False:
            errors.append(f"{label} ok envelope must still set artifact_ok=false: {after}")
    else:
        err = body.get("error") if isinstance(body.get("error"), dict) else {}
        after_err = after.get("error") if isinstance(after.get("error"), dict) else {}
        if not (err.get("code") or after_err.get("code")):
            errors.append(f"{label} must carry a typed error: {sess.redact(json.dumps(body), '')}")
    if after.get("artifact_ok") is not False:
        errors.append(f"{label} artifact_ok must be false: {after}")
    return errors


def write_card(payload: dict, name: str = "card.json") -> Path:
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    dest = REVIEW_DIR / name
    dest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return dest


def write_large_diff(n: int = DIFF_LINES) -> Path:
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    dest = REVIEW_DIR / "large.diff"
    lines = ["--- a/r4w5/review.tscn", "+++ b/r4w5/review.tscn"]
    for i in range(n):
        lines.append(f"+line-{i:04d} " + ("x" * 8))
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest


def checkpoint_sha_errors(ckpt_id: str, dests: list[Path]) -> list[str]:
    man_path = PLUGIN_PROJECT / ".hh-agent" / "checkpoints" / ckpt_id / "manifest.json"
    if not man_path.is_file():
        return [f"checkpoint manifest missing after revert: {ckpt_id}"]
    try:
        man = json.loads(man_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"checkpoint manifest unreadable: {exc}"]
    by_rel = {
        str(row.get("rel") or ""): row
        for row in (man.get("files") or [])
        if isinstance(row, dict)
    }
    errors: list[str] = []
    root = PLUGIN_PROJECT.resolve()
    for dest in dests:
        rel_s = dest.resolve().relative_to(root).as_posix()
        row = by_rel.get(rel_s)
        if row is None:
            continue
        if row.get("missing") is True:
            if dest.is_file():
                errors.append(f"revert left unexpected dest {rel_s}")
            continue
        want = str(row.get("sha256") or "")
        got = sha256_file(dest)
        if got != want:
            errors.append(f"revert SHA mismatch {rel_s}: dest={got} snapshot={want}")
    return errors


def exclusive_green_errors() -> list[str]:
    errors: list[str] = []
    for name, script in (
        ("test_g1_base.py", REPO_ROOT / "tests" / "bootstrap" / "test_g1_base.py"),
        ("test_registry.py", REPO_ROOT / "tests" / "bootstrap" / "test_registry.py"),
        ("test_plugin_router.py", REPO_ROOT / "tests" / "bootstrap" / "test_plugin_router.py"),
    ):
        ran = subprocess.run(
            [sys.executable, str(script)],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if ran.returncode != 0:
            errors.append(
                f"keep-green {name} failed (exit {ran.returncode}):\n"
                f"{ran.stdout[-1500:]}\n{ran.stderr[-1500:]}"
            )
    return errors


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
    scene = "res://r4w5/review.tscn"
    scene_abs = PLUGIN_PROJECT / "r4w5" / "review.tscn"
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

        req_id, _miss_id, missing = call_tool(
            proc, req_id, "godot.review", "card", {"detail": "short"}
        )
        miss_after = after_of(missing)
        errors.extend(unproven_card_errors(missing, miss_after, "missing artifact"))
        if miss_after.get("goal"):
            errors.append("missing artifact must not fake a green goal")
        if token_in(missing, secret):
            errors.append("missing-artifact snapshot leaked the session token")

        req_id, _obs_id, obs_miss = call_tool(
            proc, req_id, "godot.observer", "review", {"detail": "short"}
        )
        errors.extend(unproven_card_errors(obs_miss, after_of(obs_miss), "observer.review missing"))

        REVIEW_DIR.mkdir(parents=True, exist_ok=True)
        (REVIEW_DIR / "card.json").write_text("{not-json", encoding="utf-8")
        req_id, _bad_id, corrupt = call_tool(
            proc, req_id, "godot.review", "card", {"detail": "short"}
        )
        bad_after = after_of(corrupt)
        errors.extend(unproven_card_errors(corrupt, bad_after, "corrupt JSON"))
        bad_err = bad_after.get("error") if isinstance(bad_after.get("error"), dict) else {}
        top_err = corrupt.get("error") if isinstance(corrupt.get("error"), dict) else {}
        if str(bad_err.get("code") or top_err.get("code") or "") not in ("E_INVALID_TYPE", "E_UNVERIFIED"):
            errors.append(f"corrupt JSON must be a typed error: {bad_after}")
        if bad_after.get("goal"):
            errors.append("corrupt artifact must not fake a green goal")

        write_card({})
        req_id, _empty_id, empty = call_tool(
            proc, req_id, "godot.review", "card", {"detail": "short"}
        )
        errors.extend(unproven_card_errors(empty, after_of(empty), "empty {} card"))

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
            {"scene": scene, "parent": ".", "class_name": "Node2D", "name": "ReviewSprite"},
        )
        if added.get("ok") is not True:
            errors.append(f"node.add must ACK: {sess.redact(json.dumps(added), secret)}")
        req_id, _save_id, saved = call_tool(proc, req_id, "godot.scene", "save", {"path": scene})
        if saved.get("ok") is not True:
            errors.append(f"scene.save must ACK: {sess.redact(json.dumps(saved), secret)}")
        if not scene_abs.is_file():
            errors.append(f"saved scene missing: {scene}")
            return errors

        req_id, _ckpt_id, ckpt = call_tool(
            proc,
            req_id,
            "godot.git",
            "checkpoint",
            {"message": "r4w5-review-baseline", "paths": [scene]},
        )
        if ckpt.get("ok") is not True:
            errors.append(f"git.checkpoint must ACK: {sess.redact(json.dumps(ckpt), secret)}")
        ckpt_ref = str((ckpt.get("after") or {}).get("checkpoint_id") or "")
        if len(ckpt_ref) < 7:
            errors.append(f"git.checkpoint missing checkpoint_id: {ckpt}")
            return errors
        req_id, _w1_id, written = call_tool(
            proc,
            req_id,
            "godot.review",
            "write_card",
            {
                "goal": "Ship Review Center evidence without per-action approve",
                "auto": True,
                "checkpoint_id": ckpt_ref,
                "screenshots": [".hh-agent/review/missing-shot.png"],
                "diff_path": "large.diff",
                "tests": ["tests/bootstrap/test_review_center.py"],
                "before": "empty scene",
                "after": "sprite added",
            },
        )
        wrote_after = after_of(written)
        if wrote_after.get("artifact_ok") is not True:
            errors.append(f"write_card must produce a live card: {wrote_after}")
        if wrote_after.get("writer") != "godot.review.write_card" and wrote_after.get("written") is not True:
            errors.append(f"write_card must mark a product writer: {wrote_after}")
        if not str(wrote_after.get("goal") or ""):
            errors.append("write_card goal empty")
        if not (
            wrote_after.get("files") or wrote_after.get("scenes") or wrote_after.get("tests")
        ):
            errors.append(f"write_card must include files/scenes/tests: {wrote_after}")
        if wrote_after.get("diff_ok") is True:
            errors.append("diff_ok must be false when listed large.diff is missing")
        if wrote_after.get("screenshots_ok") is True:
            errors.append("screenshots_ok must be false when a listed shot is missing")
        shots = wrote_after.get("screenshots") if isinstance(wrote_after.get("screenshots"), list) else []
        if not shots or all(isinstance(row, dict) and row.get("ok") is True for row in shots if isinstance(row, dict)):
            errors.append(f"missing screenshot must be listed as missing, not OK: {shots}")
        if wrote_after.get("approve_required") is True:
            errors.append("review must stay async; no per-action approve_required")
        if token_in(written, secret):
            errors.append("write_card leaked the session token")

        req_id, _ckcard_id, ck_card = call_tool(
            proc, req_id, "godot.review", "card", {"detail": "short"}
        )
        ck_after = after_of(ck_card)
        ckpt_snap = ck_after.get("checkpoint") if isinstance(ck_after.get("checkpoint"), dict) else {}
        if str(ckpt_snap.get("id") or "") != ckpt_ref:
            errors.append(f"card checkpoint id drifted: {ckpt_snap}")
        dest_sha = str(ckpt_snap.get("dest_sha") or "")
        if not dest_sha or dest_sha == "pending":
            errors.append(f"card checkpoint dest_sha missing vs snapshot: {ckpt_snap}")

        req_id, _obs2_id, obs_ok = call_tool(
            proc, req_id, "godot.observer", "review", {"detail": "short"}
        )
        if after_of(obs_ok).get("artifact_ok") is not True:
            errors.append(f"observer.review valid card must ACK: {after_of(obs_ok)}")

        req_id, _mut_id, mutated = call_tool(
            proc,
            req_id,
            "godot.node",
            "add",
            {"scene": scene, "parent": ".", "class_name": "Label", "name": "Scratch"},
        )
        if mutated.get("ok") is not True:
            errors.append(f"checkpoint-probe node.add must ACK: {sess.redact(json.dumps(mutated), secret)}")
        req_id, _save2_id, saved2 = call_tool(proc, req_id, "godot.scene", "save", {"path": scene})
        if saved2.get("ok") is not True:
            errors.append(f"checkpoint-probe save must ACK: {sess.redact(json.dumps(saved2), secret)}")
        if sha256_file(scene_abs) == dest_sha:
            errors.append("checkpoint-probe mutate did not change dest SHA")
        req_id, _press_rev_id, dock_rev = call_tool(
            proc, req_id, "godot.review", "card", {"detail": "short", "press": "revert"}
        )
        dock_rev_after = after_of(dock_rev)
        last_rev = dock_rev_after.get("last_revert") if isinstance(dock_rev_after.get("last_revert"), dict) else {}
        if dock_rev_after.get("dock_pressed") != "revert" and last_rev.get("action") != "git.revert_checkpoint":
            errors.append(f"dock Revert must run git.revert_checkpoint / local restore: {dock_rev_after}")
        if last_rev.get("ok") is not True and dock_rev.get("ok") is not True:
            errors.append(f"dock revert path must restore: {sess.redact(json.dumps(dock_rev), secret)}")
        errors.extend(checkpoint_sha_errors(ckpt_ref, [scene_abs]))
        if dest_sha and sha256_file(scene_abs) != dest_sha:
            errors.append(
                f"dock revert dest SHA {sha256_file(scene_abs)} != card/checkpoint snapshot {dest_sha}"
            )

        write_large_diff(DIFF_LINES)
        req_id, _d1_id, page1 = call_tool(
            proc, req_id, "godot.review", "diff", {"offset": 0, "limit": 50}
        )
        d1 = after_of(page1)
        diff1 = d1.get("diff") if isinstance(d1.get("diff"), dict) else {}
        items1 = diff1.get("items") if isinstance(diff1.get("items"), list) else []
        if int(diff1.get("total") or 0) < DIFF_LINES:
            errors.append(f"large diff total={diff1.get('total')} (need >= {DIFF_LINES})")
        if len(items1) > PAGE_CAP:
            errors.append(f"diff page dumped {len(items1)} lines (cap {PAGE_CAP})")
        if int(diff1.get("limit") or 0) > PAGE_CAP:
            errors.append(f"diff limit {diff1.get('limit')} exceeds {PAGE_CAP}")
        if len(items1) != 50:
            errors.append(f"first diff page size {len(items1)} != 50")
        if diff1.get("has_more") is not True:
            errors.append("first page of 2000-line diff must has_more")
        if token_in(page1, secret):
            errors.append("diff page leaked the session token")
        req_id, _d2_id, page2 = call_tool(
            proc, req_id, "godot.review", "diff", {"offset": 50, "limit": 50}
        )
        items2 = ((after_of(page2).get("diff") or {}).get("items") or [])
        if items1 and items2 and items1 == items2:
            errors.append("diff offset=50 returned the same page as offset=0")
        req_id, _open_id, opened = call_tool(
            proc, req_id, "godot.review", "open", {"view": "diff", "offset": 0, "limit": 40}
        )
        open_after = after_of(opened)
        if str(open_after.get("view") or open_after.get("opened") or "") != "diff":
            errors.append(f"review.open diff must report view=diff: {open_after}")
        open_items = ((open_after.get("diff") or {}).get("items") or [])
        if len(open_items) > PAGE_CAP:
            errors.append(f"review.open dumped {len(open_items)} diff lines")
        if not open_items:
            errors.append("review.open / Diff must populate a live paged diff, not an empty ItemList")
        if open_after.get("dock_pressed") not in ("diff", None) and not open_items:
            errors.append(f"dock Diff press must populate the live view: {open_after}")

        for view_name in ("before", "after"):
            req_id, _pv_id, pressed = call_tool(
                proc, req_id, "godot.review", "card", {"detail": "short", "press": view_name}
            )
            press_after = after_of(pressed)
            press_items = ((press_after.get("diff") or {}).get("items") or [])
            if press_after.get("dock_pressed") != view_name and str(press_after.get("view") or "") != view_name:
                errors.append(f"dock {view_name} must run the view_changed path: {press_after}")
            if not press_items and not str(press_after.get("opened_text") or press_after.get("opened") or ""):
                errors.append(f"dock {view_name} must populate a live view: {press_after}")

        req_id, _pd_id, press_diff = call_tool(
            proc, req_id, "godot.review", "card", {"detail": "short", "press": "diff"}
        )
        pd_after = after_of(press_diff)
        pd_items = ((pd_after.get("diff") or {}).get("items") or [])
        if pd_after.get("dock_pressed") != "diff" and str(pd_after.get("view") or "") != "diff":
            errors.append(f"dock Diff must run view_changed: {pd_after}")
        if not pd_items:
            errors.append("dock Diff must fill the ItemList with paged diff lines")

        before_sha = sha256_file(scene_abs)
        req_id, _rep_id, replayed = call_tool(
            proc, req_id, "godot.review", "replay", {"command_id": add_id}
        )
        if replayed.get("ok") is not True:
            errors.append(f"review.replay must ACK: {sess.redact(json.dumps(replayed), secret)}")
        if replayed.get("changed") is True:
            errors.append("review.replay must not report a document change")
        replay_after = after_of(replayed)
        if str(replay_after.get("replayed_command_id") or "") != add_id:
            errors.append(f"dock/review.replay selected id must be {add_id}: {replay_after}")
        if sha256_file(scene_abs) != before_sha:
            errors.append("review.replay changed scene SHA")
        if token_in(replayed, secret):
            errors.append("review.replay leaked the session token")

        miss_ulid = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
        req_id, _miss_rep_id, miss_replay = call_tool(
            proc, req_id, "godot.review", "replay", {"command_id": miss_ulid}
        )
        miss_rep_after = after_of(miss_replay)
        miss_post = miss_replay.get("postcondition") if isinstance(miss_replay.get("postcondition"), dict) else {}
        miss_err = miss_replay.get("error") if isinstance(miss_replay.get("error"), dict) else {}
        if miss_replay.get("ok") is True and miss_post.get("verified") is True:
            errors.append(f"review.replay missing command_id must not ok_read replay_started: {miss_replay}")
        if "replay_started" in (miss_post.get("checks") or []) and miss_post.get("verified") is True:
            errors.append("missing review.replay must not stamp replay_started")
        if str(miss_err.get("code") or "") != "E_UNVERIFIED" and miss_rep_after.get("presentation_failed") is not True:
            errors.append(
                f"review.replay miss must be E_UNVERIFIED / presentation_failed: {sess.redact(json.dumps(miss_replay), secret)}"
            )

        req_id, _press_rep_id, press_replay = call_tool(
            proc,
            req_id,
            "godot.review",
            "card",
            {"detail": "short", "press": "replay", "command_id": add_id},
        )
        press_rep_after = after_of(press_replay)
        if str(press_rep_after.get("replayed_command_id") or "") not in ("", add_id):
            errors.append(f"dock Replay of a selected row must use that id: {press_rep_after}")
        if press_rep_after.get("dock_pressed") not in ("replay", None) and str(
            press_rep_after.get("replayed_command_id") or ""
        ) not in ("", add_id):
            errors.append(f"dock Replay press must target the selected command_id: {press_rep_after}")
    except Exception as exc:  # noqa: BLE001
        errors.append(sess.redact(f"live review center failed: {type(exc).__name__}: {exc}", secret))
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
        print("FAIL: review center", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1
    version = plug.godot_version(exe)
    if any(bad in version for bad in ("4.7.2", "4.8")):
        errors.append(f"refused Godot --version {version!r}")
        print("FAIL: review center", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1
    if version != PINNED_VERSION:
        errors.append(f"Godot --version {version!r} != {PINNED_VERSION}")
        print("FAIL: review center", file=sys.stderr)
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
        print("FAIL: review center", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    errors.extend(live_errors(exe))
    if not errors:
        errors.extend(exclusive_green_errors())

    if errors:
        print("FAIL: review center", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print(
        "PASS: review center; missing/corrupt/empty fail honestly; write_card product path; "
        "dock Before/After/Diff/Revert wired; selected replay; missing replay E_UNVERIFIED; "
        "checkpoint dest SHA restored; 2000-line diff paged; R4-WP5 and G2 stay unticked."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
