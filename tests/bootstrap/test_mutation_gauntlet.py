#!/usr/bin/env python3
"""R3-WP8: transaction coordinator, restorable checkpoint, mutation gauntlet.

Does not tick the 20-8 plan. Does not start R4-WP1.
Pin missing is a hard FAIL. No skip-PASS.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
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
import test_scene_lifecycle as life
import test_session as sess

BRIDGE = REPO_ROOT / "bridge"
PLAN = REPO_ROOT / "zdocs" / "20-8-godot-agent-autopilot-plan.txt"
PLUGIN_PROJECT = REPO_ROOT / "godot" / "plugin-project"
ADDON = PLUGIN_PROJECT / "addons" / "hh_agent"
PINNED_VERSION = plug.PINNED_VERSION
TEMP_DIR = PLUGIN_PROJECT / "r3w8"
SEED = 20260821
CLEAN_RUNS = 50
RANDOM_OPS = 200
VENDOR_NEEDLES = plug.VENDOR_NEEDLES
SCHEMA = "hh-godot-variant/1"
SCRIPT_A = "extends Node2D\n\nfunc speed() -> int:\n	return 8\n"
SCRIPT_B = "extends Node2D\n\nfunc speed() -> int:\n	return 16\n"


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def plan_errors(text: str) -> list[str]:
    """Keep R3-WP8 [ ] while unticked; after coordinator tick allow R4-WP1+."""
    errors: list[str] = []
    current = ""
    wp8 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R3-WP8\b", stripped):
            wp8 = stripped
    if wp8 is None:
        return ["plan missing R3-WP8 heading"]
    ticked = bool(re.search(r"\[x\]", wp8, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp8:
            errors.append("R3-WP8 heading must keep [ ] until coordinator tick")
        if current != "R3-WP8":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R3-WP8 while WP8 is unticked)")
    elif not re.match(r"^R4-WP\d+$|^R[5-9]-WP\d+$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R4-WP1+ after R3-WP8 tick)")
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


def attack_human_edit(path: Path) -> None:
    """Isolated concurrent-edit helper. The only Python write of dest product files."""
    blob = path.read_bytes()
    if path.suffix == ".tscn":
        path.write_bytes(blob + b"\n; human-edit\n")
    else:
        path.write_bytes(blob + b"\n# human-edit\n")


def sha256_file(path: Path) -> str:
    if not path.is_file():
        return "missing"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fingerprint(paths: list[Path]) -> dict[str, str]:
    return {str(path): sha256_file(path) for path in paths}


def variant_bool(value: bool) -> dict:
    return {"schema": SCHEMA, "type": "bool", "value": value}


def valid_tscn(path: Path) -> bool:
    if not path.is_file():
        return True
    text = path.read_text(encoding="utf-8", errors="replace")
    return text.startswith("[gd_scene") and "\x00" not in text and "[node" in text


def valid_gd(path: Path) -> bool:
    if not path.is_file():
        return True
    text = path.read_text(encoding="utf-8", errors="replace")
    return "extends " in text and "\x00" not in text


def src_scan_errors() -> list[str]:
    errors: list[str] = []
    for path in (BRIDGE / "src").rglob("*.ts"):
        text = path.read_text(encoding="utf-8", errors="replace")
        posix = rel(path)
        if re.search(r"writeFile(?:Sync)?\([^)]*\.tscn", text):
            errors.append(f"{posix} writes a .tscn from the sidecar")
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
        if re.search(r"os_global_atomic\s*:\s*true|is OS-global atomic|globally atomic", text):
            errors.append(f"{posix} claims OS-global atomicity")
    self_text = Path(__file__).read_text(encoding="utf-8")
    if "CLEAN_RUNS = 50" not in self_text or "for run_i in range(CLEAN_RUNS)" not in self_text:
        errors.append("official test must actually loop CLEAN_RUNS with a reset each iteration")
    if "RANDOM_OPS = 200" not in self_text:
        errors.append("official test must declare 200 random mutations")
    if "attack_human_edit" not in self_text:
        errors.append("official test must isolate human-edit writes")
    if re.search(r"\.write_text\([^\n]*\.(tscn|gd)", self_text) and "attack_human_edit" not in self_text:
        errors.append("official test writes dest product files outside the helper")
    if "proc.kill" not in self_text and "godot.kill" not in self_text:
        errors.append("official test must kill a real PID")
    if "play.input" not in self_text:
        errors.append("official test must keep the play.input inject sentinel")
    router = (ADDON / "core" / "hh_router.gd").read_text(encoding="utf-8")
    if "hh_transaction_adapter" not in router:
        errors.append("router must dispatch the transaction adapter")
    if "play.input inject must stay" not in router:
        errors.append("unproven-mutate sentinel must stay on play.input inject")
    tx = ADDON / "core" / "hh_transaction_adapter.gd"
    if not tx.is_file():
        errors.append("missing transaction adapter")
    else:
        text = tx.read_text(encoding="utf-8")
        if "create_action" not in text or "UNDO_ACTION_PREFIX" not in text:
            errors.append("transaction adapter must create one Agent UndoRedo action")
        if "os_global_atomic" not in text or "false" not in text:
            errors.append("transaction adapter must deny OS-global atomicity")
        if "script.write" not in text:
            errors.append("transaction adapter must stage script.write as file compensation")
    ckpt = (BRIDGE / "src" / "policy" / "checkpoint.ts").read_text(encoding="utf-8")
    if "function restoreCheckpoint" not in ckpt:
        errors.append("checkpoint restore primitive missing")
    if "unlinkSync" not in ckpt:
        errors.append("restore must delete files that were missing at checkpoint time")
    catalog = (BRIDGE / "src" / "registry" / "catalog.ts").read_text(encoding="utf-8")
    if '"transaction"' not in catalog:
        errors.append("catalog must include job.transaction")
    return errors


def mcp_call(proc: subprocess.Popen[str], req_id: int, name: str, arguments: dict, timeout: float = 45.0) -> dict:
    return life.mcp_call(proc, req_id, name, arguments, timeout)


def body_of(resp: dict) -> dict:
    return life.body_of(resp)


def tool_call(
    proc: subprocess.Popen[str],
    req_id: int,
    name: str,
    action: str,
    params: dict,
    timeout: float = 45.0,
) -> tuple[int, dict]:
    cid = life.new_ulid()
    resp = mcp_call(
        proc,
        req_id,
        name,
        {"action": action, "params": params, "command_id": cid},
        timeout,
    )
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
    code = str((body.get("error") or {}).get("code") or "")
    if code not in codes:
        errors.append(f"{label} expected {codes}, got {body}")


def resync(proc: subprocess.Popen[str], req_id: int, scene: str) -> int:
    req_id, _ = tool_call(proc, req_id, "godot.scene", "close", {"path": scene})
    req_id, opened = tool_call(proc, req_id, "godot.scene", "open", {"path": scene})
    if opened.get("ok") is not True:
        req_id, opened = tool_call(proc, req_id, "godot.scene", "open", {"path": scene})
    return req_id


def run_selftest(exe: Path) -> list[str]:
    errors: list[str] = []
    out_dir = Path(os.environ.get("TEMP") or os.environ.get("TMP") or ".") / "hh-r3w8-selftest"
    out_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.pop("HH_AGENT_RELOAD_N", None)
    env.pop("HH_AGENT_RELOAD_OUT", None)
    env["HH_AGENT_SELFTEST"] = "1"
    env["HH_AGENT_SELFTEST_OUT"] = str(out_dir)
    try:
        selftest = subprocess.run(
            [str(exe), "--headless", "--editor", "--path", str(PLUGIN_PROJECT), "--quit-after", "20"],
            cwd=str(REPO_ROOT),
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return ["plugin selftest timed out"]
    out = (selftest.stdout or "") + (selftest.stderr or "")
    marker = out_dir / "hh_agent_selftest.txt"
    marker_text = marker.read_text(encoding="utf-8") if marker.is_file() else ""
    if "HH_AGENT_SELFTEST=PASS" not in out and "HH_AGENT_SELFTEST=PASS" not in marker_text:
        errors.append(f"existing plugin selftest failed (exit {selftest.returncode}): {out[-2000:]}")
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
    scene = "res://r3w8/main.tscn"
    script = "res://r3w8/player.gd"
    spare = "res://r3w8/spare.gd"
    scene_abs = life.res_to_abs(scene)
    script_abs = life.res_to_abs(script)
    spare_abs = life.res_to_abs(spare)
    req_id = 2
    ckpt_ref = ""
    clean_done = 0
    used: set[str] = set()
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
                "godot.job",
                {
                    "action": "transaction",
                    "params": {
                        "steps": [
                            {
                                "action": "scene.create",
                                "params": {"path": "res://../escape.tscn", "root_class": "Node2D"},
                            }
                        ]
                    },
                },
            )
        )
        req_id += 1
        expect_code(jail, ("E_PATH",), errors, "escaped transaction path")

        sentinel = body_of(
            mcp_call(
                proc,
                req_id,
                "godot.input",
                {"action": "action", "params": {"action_name": "interact", "phase": "press"}},
            )
        )
        req_id += 1
        expect_code(sentinel, ("E_UNVERIFIED",), errors, "play.input inject must stay")

        req_id, created = tool_call(
            proc,
            req_id,
            "godot.job",
            "transaction",
            {
                "steps": [
                    {"action": "scene.create", "params": {"path": scene, "root_class": "Node2D"}},
                    {
                        "action": "node.add",
                        "params": {
                            "scene": scene,
                            "parent": ".",
                            "class_name": "Node2D",
                            "name": "Player",
                        },
                    },
                    {
                        "action": "property.set",
                        "params": {
                            "scene": scene,
                            "node_path": "Player",
                            "property": "visible",
                            "value": variant_bool(True),
                        },
                    },
                    {"action": "script.write", "params": {"path": script, "contents": SCRIPT_A}},
                    {"action": "scene.save", "params": {"path": scene}},
                ],
                "save": True,
            },
        )
        if not ack_ok(created, errors, "job.transaction"):
            return errors
        undo = str(created.get("undo_action") or "")
        if not undo.startswith("Agent:"):
            errors.append(f"job.transaction missing Agent undo_action: {created}")
        after = created.get("after") or {}
        if after.get("os_global_atomic") is True:
            errors.append("job.transaction claimed OS-global atomicity")
        if after.get("script_file_compensated") is not True:
            errors.append("job.transaction must document script.write file compensation")
        if not after.get("checkpoint_id"):
            errors.append(f"job.transaction missing checkpoint_id: {after}")
        if not scene_abs.is_file() or not script_abs.is_file():
            errors.append("transaction did not leave plugin-written dest files")
            return errors
        if "Player" not in scene_abs.read_text(encoding="utf-8"):
            errors.append("transaction save missing Player node")

        req_id, ckpt = tool_call(
            proc,
            req_id,
            "godot.git",
            "checkpoint",
            {"message": "r3w8-baseline", "paths": [scene, script]},
        )
        if not ack_ok(ckpt, errors, "git.checkpoint"):
            return errors
        ckpt_ref = str((ckpt.get("after") or {}).get("checkpoint_id") or "")
        if len(ckpt_ref) < 7:
            errors.append(f"git.checkpoint missing checkpoint_id: {ckpt}")
            return errors
        baseline = fingerprint([scene_abs, script_abs])

        req_id, mutated = tool_call(
            proc,
            req_id,
            "godot.node",
            "add",
            {"scene": scene, "parent": ".", "class_name": "Label", "name": "Scratch"},
        )
        if not ack_ok(mutated, errors, "checkpoint-probe node.add"):
            return errors
        req_id, saved = tool_call(proc, req_id, "godot.scene", "save", {"path": scene})
        if not ack_ok(saved, errors, "checkpoint-probe save"):
            return errors
        if fingerprint([scene_abs, script_abs]) == baseline:
            errors.append("checkpoint-probe mutate did not change disk")
        req_id, restored = tool_call(proc, req_id, "godot.git", "revert_checkpoint", {"ref": ckpt_ref})
        if not ack_ok(restored, errors, "git.revert_checkpoint"):
            return errors
        recovery = (restored.get("after") or {}).get("recovery") or {}
        if recovery.get("restored") is not True:
            errors.append(f"revert missing recovery report: {restored}")
        req_id = resync(proc, req_id, scene)
        if fingerprint([scene_abs, script_abs]) != baseline:
            errors.append("checkpoint create→mutate→restore did not match baseline bytes")

        for run_i in range(CLEAN_RUNS):
            req_id, rev = tool_call(proc, req_id, "godot.git", "revert_checkpoint", {"ref": ckpt_ref})
            if rev.get("ok") is not True:
                errors.append(f"clean run {run_i} revert failed: {rev}")
                break
            req_id = resync(proc, req_id, scene)
            run_baseline = fingerprint([scene_abs, script_abs])
            req_id, add = tool_call(
                proc,
                req_id,
                "godot.node",
                "add",
                {"scene": scene, "parent": ".", "class_name": "Node2D", "name": f"C{run_i}"},
            )
            if add.get("ok") is not True:
                errors.append(f"clean run {run_i} mutate failed: {add}")
                break
            req_id, _ = tool_call(proc, req_id, "godot.scene", "save", {"path": scene})
            req_id, rev2 = tool_call(proc, req_id, "godot.git", "revert_checkpoint", {"ref": ckpt_ref})
            if rev2.get("ok") is not True:
                errors.append(f"clean run {run_i} restore failed: {rev2}")
                break
            if fingerprint([scene_abs, script_abs]) != run_baseline:
                errors.append(f"clean run {run_i} leftover dirty after restore")
                break
            clean_done += 1
        print(f"CLEAN_RUN={clean_done}", flush=True)
        if clean_done != CLEAN_RUNS:
            errors.append(f"CLEAN_RUN={clean_done} (need {CLEAN_RUNS} clean resets)")

        req_id, _ = tool_call(proc, req_id, "godot.git", "revert_checkpoint", {"ref": ckpt_ref})
        req_id = resync(proc, req_id, scene)
        mix_baseline = fingerprint([scene_abs, script_abs])
        rng = random.Random(SEED)
        for op_i in range(RANDOM_OPS):
            kind = rng.choice(["node", "property", "script", "scene"])
            used.add(kind)
            if kind == "node":
                req_id, body = tool_call(
                    proc,
                    req_id,
                    "godot.node",
                    "add",
                    {
                        "scene": scene,
                        "parent": ".",
                        "class_name": rng.choice(["Node2D", "Node", "Label"]),
                        "name": f"R{op_i}",
                    },
                )
                if body.get("ok") is not True:
                    errors.append(f"random node.add {op_i} failed: {body}")
                    break
            elif kind == "property":
                req_id, body = tool_call(
                    proc,
                    req_id,
                    "godot.property",
                    "set",
                    {
                        "scene": scene,
                        "node_path": "Player",
                        "property": "visible",
                        "value": variant_bool(bool(rng.getrandbits(1))),
                    },
                )
                if body.get("ok") is not True:
                    errors.append(f"random property.set {op_i} failed: {body}")
                    break
            elif kind == "script":
                req_id, body = tool_call(
                    proc,
                    req_id,
                    "godot.script",
                    "write",
                    {"path": script, "contents": SCRIPT_B if op_i % 2 else SCRIPT_A},
                )
                if body.get("ok") is not True:
                    errors.append(f"random script.write {op_i} failed: {body}")
                    break
            else:
                req_id, body = tool_call(proc, req_id, "godot.scene", "save", {"path": scene})
                if body.get("ok") is not True:
                    errors.append(f"random scene.save {op_i} failed: {body}")
                    break
        if not {"node", "property"}.issubset(used) or not ({"script", "scene"} & used):
            errors.append(f"200 random mix too narrow: {sorted(used)}")
        req_id, mix_restore = tool_call(proc, req_id, "godot.git", "revert_checkpoint", {"ref": ckpt_ref})
        if not ack_ok(mix_restore, errors, "200-op checkpoint restore"):
            return errors
        req_id = resync(proc, req_id, scene)
        if fingerprint([scene_abs, script_abs]) != mix_baseline:
            errors.append(
                "200 mixed mutations + checkpoint restore did not match baseline "
                "(script.write is file-not-UndoRedo; compensation is checkpoint restore)"
            )

        if scene_abs.is_file():
            attack_human_edit(scene_abs)
            req_id, conflict = tool_call(
                proc,
                req_id,
                "godot.node",
                "add",
                {"scene": scene, "parent": ".", "class_name": "Node2D", "name": "Human"},
            )
            expect_code(conflict, ("E_CONFLICT",), errors, "human-edit .tscn")
        req_id, _ = tool_call(proc, req_id, "godot.git", "revert_checkpoint", {"ref": ckpt_ref})
        req_id = resync(proc, req_id, scene)
        if script_abs.is_file():
            attack_human_edit(script_abs)
            req_id, gd_conflict = tool_call(
                proc,
                req_id,
                "godot.script",
                "write",
                {"path": script, "contents": SCRIPT_B},
            )
            expect_code(gd_conflict, ("E_CONFLICT",), errors, "human-edit .gd")
        req_id, _ = tool_call(proc, req_id, "godot.git", "revert_checkpoint", {"ref": ckpt_ref})
        req_id = resync(proc, req_id, scene)

        req_id, spare_w = tool_call(
            proc, req_id, "godot.script", "write", {"path": spare, "contents": SCRIPT_A}
        )
        if not ack_ok(spare_w, errors, "spare script.write"):
            return errors
        req_id, deleted = tool_call(proc, req_id, "godot.asset", "delete", {"path": spare})
        if not ack_ok(deleted, errors, "asset.delete"):
            return errors
        del_after = deleted.get("after") or {}
        if not del_after.get("checkpoint_id"):
            errors.append(f"destructive asset.delete missing checkpoint_id: {deleted}")
        evidence = deleted.get("evidence")
        if not evidence and not del_after.get("manifest_path"):
            errors.append(f"destructive asset.delete missing restore evidence: {deleted}")
        del_ckpt = str(del_after.get("checkpoint_id") or "")
        if del_ckpt:
            req_id, del_rev = tool_call(proc, req_id, "godot.git", "revert_checkpoint", {"ref": del_ckpt})
            if del_rev.get("ok") is True and not spare_abs.is_file():
                errors.append("destructive restore did not return the deleted file")

        paused = body_of(mcp_call(proc, req_id, "hh.pause", {}))
        req_id += 1
        if paused.get("ok") is not True and (paused.get("error") or {}).get("code"):
            errors.append(f"hh.pause failed: {paused}")
        req_id, blocked = tool_call(
            proc,
            req_id,
            "godot.job",
            "transaction",
            {
                "steps": [
                    {
                        "action": "node.add",
                        "params": {"scene": scene, "parent": ".", "class_name": "Node2D", "name": "Paused"},
                    }
                ]
            },
        )
        expect_code(blocked, ("E_PAUSED",), errors, "paused job.transaction")
        mcp_call(proc, req_id, "hh.resume", {})
        req_id += 1

        if godot is not None and godot.poll() is None:
            killer = threading.Thread(target=lambda: (time.sleep(0.2), godot.kill()), daemon=True)
            killer.start()
            try:
                req_id, killed = tool_call(
                    proc,
                    req_id,
                    "godot.job",
                    "transaction",
                    {
                        "steps": [
                            {
                                "action": "node.add",
                                "params": {
                                    "scene": scene,
                                    "parent": ".",
                                    "class_name": "Node2D",
                                    "name": "KillGodot",
                                },
                            },
                            {"action": "script.write", "params": {"path": script, "contents": SCRIPT_B}},
                            {"action": "scene.save", "params": {"path": scene}},
                        ]
                    },
                    timeout=20.0,
                )
            except Exception as exc:  # noqa: BLE001
                killed = {"ok": False, "error": {"code": "E_UNCERTAIN", "message": str(exc)}}
            killer.join(timeout=5)
            if killed.get("ok") is True:
                print("KILL_GODOT=completed-before-kill", flush=True)
            else:
                code = str((killed.get("error") or {}).get("code") or "")
                if code not in ("E_UNCERTAIN", "E_UNVERIFIED", "E_BUSY", ""):
                    errors.append(f"kill Godot mid-command unexpected: {killed}")
                print("KILL_GODOT=ran", flush=True)
            if not valid_tscn(scene_abs):
                errors.append("Godot kill left a corrupt .tscn")
            if not valid_gd(script_abs):
                errors.append("Godot kill left a corrupt .gd")
            life.stop_proc(godot)
            godot, godot_lines = life.start_godot(exe)
            hello2 = False
            last2: dict = {}
            try:
                req_id, hello2, last2 = life.wait_hello(proc, godot, req_id)
            except Exception as exc:  # noqa: BLE001
                last2 = {"error": {"code": "E_UNCERTAIN", "message": str(exc)}}
            if not hello2:
                print(f"reopen hello after Godot kill failed (sidecar may be wedged): {last2}", flush=True)
            else:
                try:
                    req_id, reopened = tool_call(proc, req_id, "godot.scene", "open", {"path": scene})
                    if reopened.get("ok") is not True:
                        req_id, _ = tool_call(proc, req_id, "godot.git", "revert_checkpoint", {"ref": ckpt_ref})
                        req_id, reopened = tool_call(proc, req_id, "godot.scene", "open", {"path": scene})
                    if reopened.get("ok") is not True:
                        errors.append(f"scene unreadable after Godot kill: {reopened}")
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"reopen after Godot kill raised: {type(exc).__name__}")
            if not valid_tscn(scene_abs) or not valid_gd(script_abs):
                errors.append("reopen after Godot kill still corrupt")

        if proc is not None and proc.poll() is None:
            killer2 = threading.Thread(target=lambda: (time.sleep(0.15), proc.kill()), daemon=True)
            killer2.start()
            try:
                mcp_call(
                    proc,
                    req_id,
                    "godot.job",
                    {
                        "action": "transaction",
                        "params": {
                            "steps": [
                                {
                                    "action": "node.add",
                                    "params": {
                                        "scene": scene,
                                        "parent": ".",
                                        "class_name": "Node2D",
                                        "name": "KillSidecar",
                                    },
                                },
                                {"action": "scene.save", "params": {"path": scene}},
                            ]
                        },
                    },
                    timeout=15.0,
                )
                print("KILL_SIDECAR=completed-before-kill", flush=True)
            except Exception:  # noqa: BLE001
                print("KILL_SIDECAR=ran", flush=True)
            killer2.join(timeout=5)
            if not valid_tscn(scene_abs):
                errors.append("sidecar kill left a corrupt .tscn")
            if not valid_gd(script_abs):
                errors.append("sidecar kill left a corrupt .gd")

        if secret and secret in "".join(err_lines):
            errors.append("session secret appeared in sidecar logs")
        if secret and secret in "".join(godot_lines):
            errors.append("session secret appeared in Godot logs")
    except Exception as exc:  # noqa: BLE001
        errors.append(sess.redact(f"live mutation gauntlet failed: {type(exc).__name__}: {exc}", secret))
    finally:
        life.stop_proc(godot)
        life.stop_proc(proc)
        if desc_path and desc_path.is_file():
            try:
                desc_path.unlink()
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
        print("FAIL: mutation gauntlet", file=sys.stderr)
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
        errors.extend(run_selftest(exe))
    if not errors:
        errors.extend(live_errors(exe))

    if errors:
        print("FAIL: mutation gauntlet", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print(
        "PASS: job.transaction + restorable checkpoint; CLEAN_RUN=50; "
        "200 mixed mutations restored via checkpoint (script.write is file compensation); "
        "human-edit E_CONFLICT; real kill matrix; Pause; play.input inject stays unproven; "
        "R3-WP8 stays unticked."
    )
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
