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
COMPENSATION_OPS = 20
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
    if "AC-05" not in self_text or '"undo"' not in self_text or '"redo"' not in self_text:
        errors.append("official test must undo-all/redo the 200 node+property ops (AC-05)")
    if "COMPENSATION_OPS" not in self_text or "compensation" not in self_text:
        errors.append("official test must keep a labeled checkpoint-compensation mix")
    if "still on disk" not in self_text:
        errors.append("official test must assert human-edit bytes still on disk")
    if self_text.count("life.start_sidecar") < 2:
        errors.append("crash recovery must restart the sidecar (old sidecar wedges)")
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
        if "_abandon_open_action" not in text or "commit_action(false)" not in text:
            errors.append("transaction adapter must cancel an abandoned create_action")
        if "os_global_atomic" not in text or "false" not in text:
            errors.append("transaction adapter must deny OS-global atomicity")
        if "script.write" not in text:
            errors.append("transaction adapter must stage script.write as file compensation")
    ckpt = (BRIDGE / "src" / "policy" / "checkpoint.ts").read_text(encoding="utf-8")
    if "function restoreCheckpoint" not in ckpt:
        errors.append("checkpoint restore primitive missing")
    if "unlinkSync" not in ckpt:
        errors.append("restore must delete files that were missing at checkpoint time")
    if "restore hash mismatch" not in ckpt:
        errors.append("restoreCheckpoint must SHA dest files vs the snapshot")
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


def scene_fingerprint(
    proc: subprocess.Popen[str], req_id: int, scene: str
) -> tuple[int, str, dict]:
    req_id, body = tool_call(proc, req_id, "godot.scene", "read", {"path": scene, "detail": "short"})
    after = body.get("after") or {}
    return req_id, str(after.get("fingerprint") or ""), body


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


def human_marker(path: Path) -> bytes:
    return b"; human-edit" if path.suffix == ".tscn" else b"# human-edit"


def restart_stack(
    proc: subprocess.Popen[str] | None,
    desc_path: Path | None,
    godot: subprocess.Popen[str] | None,
    exe: Path,
) -> tuple[subprocess.Popen[str], Path, str, list[str], subprocess.Popen[str], list[str]]:
    life.stop_proc(godot)
    life.stop_proc(proc)
    if desc_path is not None and desc_path.is_file():
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
    new_proc, new_desc, new_secret, new_err = life.start_sidecar()
    new_godot, new_lines = life.start_godot(exe)
    return new_proc, new_desc, new_secret, new_err, new_godot, new_lines


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
        errors.extend(checkpoint_sha_errors(ckpt_ref, [scene_abs, script_abs]))
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
        print(f"CLEAN_RUN={clean_done} (reset-via-checkpoint, not OS clones)", flush=True)
        if clean_done != CLEAN_RUNS:
            errors.append(f"CLEAN_RUN={clean_done} (need {CLEAN_RUNS} clean resets)")

        req_id, _ = tool_call(proc, req_id, "godot.git", "revert_checkpoint", {"ref": ckpt_ref})
        req_id = resync(proc, req_id, scene)
        req_id, saved0 = tool_call(proc, req_id, "godot.scene", "save", {"path": scene})
        if not ack_ok(saved0, errors, "AC-05 baseline save"):
            return errors
        pre_sha = sha256_file(scene_abs)
        req_id, pre_fp, pre_read = scene_fingerprint(proc, req_id, scene)
        if not pre_fp:
            errors.append(f"AC-05 missing pre-200 fingerprint: {pre_read}")
            return errors
        rng = random.Random(SEED)
        success_200 = 0
        for op_i in range(RANDOM_OPS):
            kind = "node" if op_i == 0 else "property" if op_i == 1 else rng.choice(["node", "property"])
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
            else:
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
            success_200 += 1
        if not {"node", "property"}.issubset(used):
            errors.append(f"200 node+property mix too narrow: {sorted(used)}")
        if success_200 != RANDOM_OPS:
            errors.append(f"AC-05 only {success_200}/{RANDOM_OPS} node+property ops ACK")
            return errors
        req_id, saved200 = tool_call(proc, req_id, "godot.scene", "save", {"path": scene})
        if not ack_ok(saved200, errors, "AC-05 post-200 save"):
            return errors
        post_sha = sha256_file(scene_abs)
        req_id, post_fp, post_read = scene_fingerprint(proc, req_id, scene)
        if not post_fp:
            errors.append(f"AC-05 missing post-200 fingerprint: {post_read}")
            return errors
        if post_fp == pre_fp or post_sha == pre_sha:
            errors.append("AC-05 200 ops left SHA/fingerprint unchanged")
        req_id, undone = tool_call(
            proc,
            req_id,
            "godot.node",
            "undo",
            {"scene": scene, "count": success_200},
            timeout=90.0,
        )
        if not ack_ok(undone, errors, "AC-05 undo-all"):
            return errors
        req_id, saved_undo = tool_call(proc, req_id, "godot.scene", "save", {"path": scene})
        if not ack_ok(saved_undo, errors, "AC-05 save after undo-all"):
            return errors
        req_id, undo_fp, undo_read = scene_fingerprint(proc, req_id, scene)
        if sha256_file(scene_abs) != pre_sha or undo_fp != pre_fp:
            errors.append(
                "AC-05 undo-all SHA/fingerprint != pre-200 baseline; "
                f"sha={sha256_file(scene_abs)} want={pre_sha}; fp={undo_fp} want={pre_fp}; "
                f"read={undo_read.get('after')}"
            )
        req_id, redone = tool_call(
            proc,
            req_id,
            "godot.node",
            "redo",
            {"scene": scene, "count": success_200},
            timeout=90.0,
        )
        if not ack_ok(redone, errors, "AC-05 redo-all"):
            return errors
        req_id, saved_redo = tool_call(proc, req_id, "godot.scene", "save", {"path": scene})
        if not ack_ok(saved_redo, errors, "AC-05 save after redo-all"):
            return errors
        req_id, redo_fp, redo_read = scene_fingerprint(proc, req_id, scene)
        if sha256_file(scene_abs) != post_sha or redo_fp != post_fp:
            errors.append(
                "AC-05 redo-all SHA/fingerprint != post-200; "
                f"sha={sha256_file(scene_abs)} want={post_sha}; fp={redo_fp} want={post_fp}; "
                f"read={redo_read.get('after')}"
            )

        # Separate compensation mix: script.write is file-not-UndoRedo. NOT a substitute for AC-05.
        req_id, comp_rev = tool_call(proc, req_id, "godot.git", "revert_checkpoint", {"ref": ckpt_ref})
        if not ack_ok(comp_rev, errors, "compensation setup revert"):
            return errors
        errors.extend(checkpoint_sha_errors(ckpt_ref, [scene_abs, script_abs]))
        req_id = resync(proc, req_id, scene)
        comp_baseline = fingerprint([scene_abs, script_abs])
        comp_used: set[str] = set()
        for op_i in range(COMPENSATION_OPS):
            kind = "script" if op_i % 3 == 0 else rng.choice(["node", "property", "script"])
            comp_used.add(kind)
            if kind == "script":
                req_id, body = tool_call(
                    proc,
                    req_id,
                    "godot.script",
                    "write",
                    {"path": script, "contents": SCRIPT_B if op_i % 2 else SCRIPT_A},
                )
            elif kind == "node":
                req_id, body = tool_call(
                    proc,
                    req_id,
                    "godot.node",
                    "add",
                    {
                        "scene": scene,
                        "parent": ".",
                        "class_name": "Node2D",
                        "name": f"Comp{op_i}",
                    },
                )
            else:
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
                errors.append(f"compensation {kind} {op_i} failed: {body}")
                break
        if "script" not in comp_used:
            errors.append(f"compensation mix missing script.write: {sorted(comp_used)}")
        req_id, mix_restore = tool_call(proc, req_id, "godot.git", "revert_checkpoint", {"ref": ckpt_ref})
        if not ack_ok(mix_restore, errors, "compensation checkpoint restore"):
            return errors
        errors.extend(checkpoint_sha_errors(ckpt_ref, [scene_abs, script_abs]))
        req_id = resync(proc, req_id, scene)
        if fingerprint([scene_abs, script_abs]) != comp_baseline:
            errors.append(
                "compensation mix + checkpoint restore did not match baseline "
                "(script.write is file compensation, not UndoRedo)"
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
            if human_marker(scene_abs) not in scene_abs.read_bytes():
                errors.append("human-edit .tscn bytes not still on disk after E_CONFLICT")
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
            if human_marker(script_abs) not in script_abs.read_bytes():
                errors.append("human-edit .gd bytes not still on disk after E_CONFLICT")
        paused_human = body_of(mcp_call(proc, req_id, "hh.pause", {}))
        req_id += 1
        if paused_human.get("ok") is not True and (paused_human.get("error") or {}).get("code"):
            errors.append(f"hh.pause after human-edit failed: {paused_human}")
        if scene_abs.is_file() and human_marker(scene_abs) not in scene_abs.read_bytes():
            errors.append("human-edit .tscn bytes lost after hh.pause")
        if script_abs.is_file() and human_marker(script_abs) not in script_abs.read_bytes():
            errors.append("human-edit .gd bytes lost after hh.pause")
        mcp_call(proc, req_id, "hh.resume", {})
        req_id += 1
        req_id, human_rev = tool_call(proc, req_id, "godot.git", "revert_checkpoint", {"ref": ckpt_ref})
        if not ack_ok(human_rev, errors, "human-edit revert after asserts"):
            return errors
        errors.extend(checkpoint_sha_errors(ckpt_ref, [scene_abs, script_abs]))
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
            killer = threading.Thread(target=lambda: (time.sleep(0.05), godot.kill()), daemon=True)
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
                                    "name": "KillGodotA",
                                },
                            },
                            {
                                "action": "node.add",
                                "params": {
                                    "scene": scene,
                                    "parent": ".",
                                    "class_name": "Node2D",
                                    "name": "KillGodotB",
                                },
                            },
                            {
                                "action": "node.add",
                                "params": {
                                    "scene": scene,
                                    "parent": ".",
                                    "class_name": "Label",
                                    "name": "KillGodotC",
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
            if godot.poll() is None:
                godot.kill()
            if killed.get("ok") is True:
                errors.append("in-flight transaction must not ACK {ok:true} after Godot kill")
            else:
                code = str((killed.get("error") or {}).get("code") or "")
                if code not in ("E_UNCERTAIN", "E_UNVERIFIED", "E_BUSY", ""):
                    errors.append(f"kill Godot mid-command unexpected: {killed}")
            if not valid_tscn(scene_abs):
                errors.append("Godot kill left a corrupt .tscn")
            if not valid_gd(script_abs):
                errors.append("Godot kill left a corrupt .gd")
            try:
                proc, desc_path, secret, err_lines, godot, godot_lines = restart_stack(
                    proc, desc_path, godot, exe
                )
                req_id = 2
                hello2 = False
                last2: dict = {}
                req_id, hello2, last2 = life.wait_hello(proc, godot, req_id)
            except Exception as exc:  # noqa: BLE001
                hello2 = False
                last2 = {"error": {"code": "E_UNCERTAIN", "message": str(exc)}}
            if not hello2:
                errors.append(
                    "reopen hello after Godot kill failed: "
                    f"{sess.redact(json.dumps(last2), secret)}"
                )
            else:
                print("KILL_GODOT=ran", flush=True)
                try:
                    req_id, reopened = tool_call(proc, req_id, "godot.scene", "open", {"path": scene})
                    if reopened.get("ok") is not True:
                        req_id, rev_kill = tool_call(
                            proc, req_id, "godot.git", "revert_checkpoint", {"ref": ckpt_ref}
                        )
                        if rev_kill.get("ok") is True:
                            errors.extend(checkpoint_sha_errors(ckpt_ref, [scene_abs, script_abs]))
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
        "PASS: job.transaction + restorable checkpoint; CLEAN_RUN=50 via checkpoint "
        "(not OS clones); AC-05 undo-all/redo 200 node+property; "
        "compensation mix uses checkpoint restore; human-edit bytes stay on disk; "
        "kill Godot restarts sidecar+Godot and hello must succeed; "
        "play.input inject stays unproven; R3-WP8 stays unticked."
    )
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
