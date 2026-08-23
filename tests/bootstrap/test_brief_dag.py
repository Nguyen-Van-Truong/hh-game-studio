#!/usr/bin/env python3
"""R7-WP1: Brief compiler + task DAG (does not tick the plan).

Does not tick the 20-8 plan. Does not change CURRENT_VALID_WP.
Keep R7-WP1 [ ]; while unticked CURRENT_VALID_WP=R7-WP1; after tick allow R7-WP2+.
Pin 4.7.1-stable only. Refuse later 4.7 patches past .1-stable. No skip-PASS.
No snake demo. No R8 dogfood tree. Does not start R7-WP2 or R8. Does not tick G4.

Verify (encoded here; this file is the official harness):
  - corpus of 20 unique briefs (vague / complete / contradictory)
  - each compile is acyclic
  - every acceptance traces to >=1 task
  - E1–E4 contradictions become blocker nodes (E4 is not an assumption)
  - at least one complete brief starts with verify/test tasks

Labels: CORPUS20, ACYCLIC, TRACE, E_BLOCKERS, ASSUMPTIONS
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
import test_play_input as pin
import test_scene_lifecycle as life
import test_session as sess

BRIDGE = REPO_ROOT / "bridge"
PLAN = REPO_ROOT / "zdocs" / "20-8-godot-agent-autopilot-plan.txt"
PLUGIN_PROJECT = REPO_ROOT / "godot" / "plugin-project"
ADDON = PLUGIN_PROJECT / "addons" / "hh_agent"
ACTIONS_JSON = ADDON / "core" / "actions.json"
PINNED_VERSION = plug.PINNED_VERSION
TEMP_DIR = PLUGIN_PROJECT / "r7w1"
EVIDENCE_DIR = PLUGIN_PROJECT / ".hh-agent" / "evidence"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "r7w1_briefs"
HARNESS = BRIDGE / "dist" / "planner" / "harness.js"
VENDOR_NEEDLES = plug.VENDOR_NEEDLES


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def npm() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def node() -> str:
    return "node.exe" if os.name == "nt" else "node"


def plan_errors(text: str) -> list[str]:
    """Keep R7-WP1 [ ]; while unticked require CURRENT_VALID_WP=R7-WP1."""
    errors: list[str] = []
    current = ""
    wp1 = None
    wp2 = None
    g4 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R7-WP1\b", stripped):
            wp1 = stripped
        if re.match(r"^R7-WP2\b", stripped):
            wp2 = stripped
        if "G4 AUTONOMY" in stripped or stripped.startswith("G4 "):
            if g4 is None:
                g4 = stripped
    if wp1 is None:
        return ["plan missing R7-WP1 heading"]
    ticked = bool(re.search(r"\[x\]", wp1, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp1:
            errors.append("R7-WP1 heading must keep [ ] until coordinator tick")
        if current != "R7-WP1":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R7-WP1 while WP1 is unticked)")
        if wp2 and re.search(r"\[x\]", wp2, re.IGNORECASE):
            errors.append("R7-WP2 must stay unticked; this WP does not start the orchestrator")
    elif not re.match(r"^R7-WP([2-9]|\d{2,})$|^R[8-9]-WP\d+$|^RX-WP\d+$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R7-WP2+ after R7-WP1 tick)")
    if g4 is not None and re.search(r"\[x\]", g4, re.IGNORECASE):
        errors.append("official harness must not tick G4")
    return errors


def cleanup_temp() -> list[str]:
    errors: list[str] = []
    for folder in (TEMP_DIR,):
        for _ in range(6):
            if not folder.exists():
                break
            shutil.rmtree(folder, ignore_errors=True)
            time.sleep(0.2)
        if folder.exists():
            leftovers = [p.as_posix() for p in folder.rglob("*") if p.is_file()]
            if leftovers:
                errors.append(f"r7w1 leftover after cleanup: {leftovers[:8]}")
    if EVIDENCE_DIR.is_dir():
        for child in list(EVIDENCE_DIR.iterdir()):
            if child.name.startswith("01R7WP1"):
                shutil.rmtree(child, ignore_errors=True)
    agent = PLUGIN_PROJECT / ".hh-agent"
    for name in ("file-leases.json", "writer.lock"):
        lock = agent / name
        if lock.is_file():
            try:
                lock.unlink()
            except OSError:
                pass
    return errors


def src_scan_errors() -> list[str]:
    errors: list[str] = []
    self_text = Path(__file__).read_text(encoding="utf-8")
    for label in ("CORPUS20", "ACYCLIC", "TRACE", "E_BLOCKERS", "ASSUMPTIONS"):
        if label not in self_text:
            errors.append(f"official test must label {label}")
    if "No skip-PASS" not in self_text and "skip-PASS" not in self_text:
        errors.append("official test must refuse skip-PASS")
    if "res://" + "snake" in self_text or "kho" + "-bi-an" in self_text:
        errors.append("official test must stay independent of demo game trees")
    if "4.7." + "2" in self_text:
        errors.append("official test must refuse Godot 4.7." + "2 pin")
    if "drive_" + "snake" in self_text:
        errors.append("official test must not include drive_" + "snake scripts")
    if "does not tick G4" not in self_text:
        errors.append("official test must refuse to tick G4")

    adapter = ADDON / "core" / "hh_plan_adapter.gd"
    if not adapter.is_file():
        errors.append("missing hh_plan_adapter.gd")
    else:
        text = adapter.read_text(encoding="utf-8")
        if "circular DAG" not in text:
            errors.append("plan adapter must name circular DAG")
        if "E1" not in text or "E4" not in text:
            errors.append("plan adapter must name E1–E4 blockers")
        if "test.define" not in text:
            errors.append("plan adapter must emit test.define before produce")
        if "inject_cycle" not in text:
            errors.append("plan adapter must feed circular DAG through compile_brief")
        if "r7w1/evidence/" not in text:
            errors.append("plan adapter must jail evidence under r7w1/evidence/")
        dock_src = (ADDON / "ui" / "health" / "hh_activity_dock.gd").read_text(encoding="utf-8")
        if "plan_list_snapshot" not in dock_src or "get_item_text" not in dock_src:
            errors.append("activity dock must expose live _plan_list items")

    compiler = BRIDGE / "src" / "planner" / "brief_compiler.ts"
    if not compiler.is_file():
        errors.append("missing brief_compiler.ts")
    else:
        ctext = compiler.read_text(encoding="utf-8")
        if "inject_cycle" not in ctext:
            errors.append("compileBrief must accept inject_cycle")
        if "jailProjectPath" not in ctext:
            errors.append("writePlanEvidence must jail the evidence path")
        if "r7w1/evidence/" not in ctext:
            errors.append("writePlanEvidence must write under r7w1/evidence/")
    harness = BRIDGE / "src" / "planner" / "harness.ts"
    if not harness.is_file():
        errors.append("missing harness.ts")
    else:
        htext = harness.read_text(encoding="utf-8")
        if "inject_cycle" not in htext or "compileBrief" not in htext:
            errors.append("harness --cycle must call compileBrief, not only detectCycle")
        if "writePlanEvidence" not in htext:
            errors.append("harness --dir must write assumptions.md")

    dock = (ADDON / "ui" / "health" / "hh_activity_dock.gd").read_text(encoding="utf-8")
    if "plan cards" not in dock:
        errors.append("activity dock must show plan cards")
    store = (ADDON / "core" / "hh_activity_store.gd").read_text(encoding="utf-8")
    if "set_plan" not in store:
        errors.append("activity store must keep the compiled plan")
    router = (ADDON / "core" / "hh_router.gd").read_text(encoding="utf-8")
    if 'action == "plan"' not in router:
        errors.append("router must dispatch job.plan")
    gitignore = (PLUGIN_PROJECT / ".gitignore").read_text(encoding="utf-8")
    if "r7w1/" not in gitignore:
        errors.append("plugin-project .gitignore must ignore r7w1/")
    export_gd = (ADDON / "core" / "hh_export_plugin.gd").read_text(encoding="utf-8")
    if 'p.contains("/r7w1' not in export_gd and 'p.contains("r7w1' not in export_gd:
        errors.append("export _should_skip must contain() r7w1")

    for path in (BRIDGE / "src").rglob("*.ts"):
        blob = path.read_text(encoding="utf-8", errors="replace")
        posix = rel(path)
        for needle in VENDOR_NEEDLES:
            if needle in blob:
                errors.append(f"{posix} contains vendor needle {needle!r}")
                break
        if ("kho" + "-bi-an") in blob or ("/snake/") in blob.replace("\\", "/"):
            errors.append(f"{posix} mentions R8/snake trees")
    return errors


def load_manifest() -> tuple[list[dict], list[str]]:
    errors: list[str] = []
    man_path = FIXTURES / "manifest.json"
    if not man_path.is_file():
        return [], [f"missing {rel(man_path)}"]
    man = json.loads(man_path.read_text(encoding="utf-8"))
    rows = man.get("briefs") if isinstance(man.get("briefs"), list) else []
    if len(rows) != 20:
        errors.append(f"manifest must list 20 briefs, got {len(rows)}")
    hashes: dict[str, str] = {}
    loaded: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            errors.append("manifest row is not an object")
            continue
        file_name = str(row.get("file") or "")
        path = FIXTURES / file_name
        if not path.is_file():
            errors.append(f"missing brief {file_name}")
            continue
        text = path.read_text(encoding="utf-8")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if digest in hashes:
            errors.append(f"duplicate brief body {file_name} == {hashes[digest]}")
        hashes[digest] = file_name
        if ("kho" + "-bi-an") in text or ("res://" + "snake") in text:
            errors.append(f"{file_name} mentions forbidden dogfood/snake trees")
        loaded.append({**row, "text": text, "path": path, "digest": digest})
    if len(hashes) != 20:
        errors.append(f"CORPUS20 unique hashes={len(hashes)}")
    classes = {str(r.get("class")) for r in loaded}
    if not {"vague", "complete", "contradictory"} <= classes:
        errors.append(f"corpus classes incomplete: {sorted(classes)}")
    return loaded, errors


def run_node(args: list[str]) -> dict:
    proc = subprocess.run(
        [node(), str(HARNESS), *args],
        cwd=str(BRIDGE),
        text=True,
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        return {"ok": False, "error": {"message": proc.stderr or proc.stdout, "code": "E_UNVERIFIED"}}
    line = (proc.stdout or "").strip().splitlines()[-1] if proc.stdout else "{}"
    try:
        parsed = json.loads(line)
    except json.JSONDecodeError:
        return {"ok": False, "error": {"message": line[:400], "code": "E_UNVERIFIED"}}
    return parsed if isinstance(parsed, dict) else {"ok": False}


def plan_ok(plan: dict, meta: dict, errors: list[str], source: str) -> dict:
    rec = {
        "id": str(meta.get("id")),
        "source": source,
        "acyclic": False,
        "trace": False,
        "blockers": [],
        "assumptions": 0,
        "complete": False,
        "first_kind": "",
        "task_count": 0,
    }
    if not isinstance(plan, dict) or plan.get("ok") is not True:
        errors.append(f"{source} {meta.get('id')}: compile failed {plan}")
        return rec
    tasks = plan.get("tasks") if isinstance(plan.get("tasks"), list) else []
    rec["task_count"] = len(tasks)
    if not tasks:
        errors.append(f"{source} {meta.get('id')}: empty DAG")
        return rec
    rec["acyclic"] = plan.get("acyclic") is True
    if not rec["acyclic"] or detect_cycle_py(tasks):
        errors.append(f"{source} {meta.get('id')}: circular DAG")
        rec["acyclic"] = False
    acceptance = plan.get("acceptance") if isinstance(plan.get("acceptance"), list) else []
    traces = plan.get("traces") if isinstance(plan.get("traces"), list) else []
    traced = 0
    for item in acceptance:
        if not isinstance(item, dict):
            continue
        ids = item.get("task_ids") if isinstance(item.get("task_ids"), list) else []
        if ids:
            traced += 1
        else:
            errors.append(f"{source} {meta.get('id')}: acceptance {item.get('id')} has no task")
    rec["trace"] = traced == len(acceptance) and len(acceptance) > 0 and len(traces) == len(acceptance)
    if not rec["trace"]:
        errors.append(f"{source} {meta.get('id')}: TRACE failed acc={len(acceptance)} traces={len(traces)}")
    blockers = plan.get("blockers") if isinstance(plan.get("blockers"), list) else []
    rec["blockers"] = sorted({str(b.get("code")) for b in blockers if isinstance(b, dict) and b.get("code")})
    assumptions = plan.get("assumptions") if isinstance(plan.get("assumptions"), list) else []
    rec["assumptions"] = len(assumptions)
    rec["complete"] = plan.get("complete") is True
    if tasks and isinstance(tasks[0], dict):
        rec["first_kind"] = str(tasks[0].get("kind") or "")
    produce_files: list[str] = []
    kinds: list[str] = []
    by_id: dict[str, dict] = {}
    for task in tasks:
        if not isinstance(task, dict):
            continue
        kinds.append(str(task.get("kind") or ""))
        tid = str(task.get("id") or "")
        if tid:
            by_id[tid] = task
        if str(task.get("kind") or "") == "produce":
            files = task.get("files") if isinstance(task.get("files"), list) else []
            produce_files.extend(str(f) for f in files)
        if str(task.get("kind") or "") == "test" and not str(task.get("criterion") or "").strip():
            errors.append(f"{source} {meta.get('id')}: test {tid} has no acceptance criterion")
    acc_ids = [str(a.get("id")) for a in acceptance if isinstance(a, dict) and a.get("id")]
    produce_nodes = [t for t in tasks if isinstance(t, dict) and str(t.get("kind") or "") == "produce"]
    if len(acc_ids) > 1 and produce_nodes:
        stamped = 0
        for task in produce_nodes:
            tacc = [str(x) for x in (task.get("acceptance") or [])]
            if set(tacc) == set(acc_ids):
                stamped += 1
        if stamped == len(produce_nodes):
            errors.append(f"{source} {meta.get('id')}: every produce stamps every acceptance")
    rec["produce_files"] = produce_files
    if "produce" in kinds and "test" in kinds:
        first_produce = kinds.index("produce")
        last_test = max(i for i, kind in enumerate(kinds) if kind == "test")
        if last_test >= first_produce:
            errors.append(f"{source} {meta.get('id')}: tests-first violated (test after produce)")
    for tr in traces:
        if not isinstance(tr, dict):
            continue
        node = by_id.get(str(tr.get("task") or ""))
        if not isinstance(node, dict):
            errors.append(f"{source} {meta.get('id')}: TRACE task {tr.get('task')} missing")
            continue
        cmds = node.get("commands") if isinstance(node.get("commands"), list) else []
        expect = str(cmds[0] if cmds else node.get("verify") or "")
        if str(tr.get("command") or "") != expect:
            errors.append(
                f"{source} {meta.get('id')}: TRACE command {tr.get('command')!r} != {expect!r}"
            )
        if node.get("kind") == "checkpoint" and str(tr.get("checkpoint") or "") != str(node.get("id") or ""):
            errors.append(f"{source} {meta.get('id')}: TRACE checkpoint does not follow covering task")
    want = [str(c) for c in (meta.get("expect_blockers") or [])]
    if want:
        for code in want:
            if code not in rec["blockers"]:
                errors.append(f"{source} {meta.get('id')}: missing blocker {code} (got {rec['blockers']})")
        if "E4" in want:
            for asm in assumptions:
                if not isinstance(asm, dict):
                    continue
                field = str(asm.get("field") or "")
                value = str(asm.get("value") or "").lower()
                if field.startswith("genre") and ("platformer" in value or "rpg" in value or "3d" in value):
                    errors.append(f"{source} {meta.get('id')}: E4 treated as assumption {asm}")
    elif rec["blockers"]:
        if str(meta.get("class")) == "vague" or str(meta.get("class")) == "complete":
            errors.append(f"{source} {meta.get('id')}: unexpected blockers {rec['blockers']}")
    if meta.get("expect_assumptions") is True and rec["assumptions"] < 1:
        errors.append(f"{source} {meta.get('id')}: expected ASSUMPTIONS")
    if meta.get("expect_assumptions") is False and str(meta.get("class")) == "complete" and rec["assumptions"] > 0:
        errors.append(f"{source} {meta.get('id')}: complete brief must not invent assumptions")
    if str(meta.get("class")) == "complete":
        if rec["complete"] is not True:
            errors.append(f"{source} {meta.get('id')}: complete brief not marked complete")
        allowed = set(meta.get("first_kind") or ["test", "verify"])
        if rec["first_kind"] not in allowed:
            errors.append(f"{source} {meta.get('id')}: first kind {rec['first_kind']!r} not test/verify")
    return rec


def detect_cycle_py(tasks: list) -> list[str]:
    ids = {str(t.get("id")) for t in tasks if isinstance(t, dict) and t.get("id")}
    incoming = {i: 0 for i in ids}
    edges: dict[str, list[str]] = {i: [] for i in ids}
    for t in tasks:
        if not isinstance(t, dict):
            continue
        tid = str(t.get("id") or "")
        for dep in t.get("deps") or []:
            dep_s = str(dep)
            if dep_s in ids:
                edges[dep_s].append(tid)
                incoming[tid] = incoming.get(tid, 0) + 1
    ready = [i for i, n in incoming.items() if n == 0]
    seen: list[str] = []
    while ready:
        cur = ready.pop(0)
        seen.append(cur)
        for nxt in edges.get(cur, []):
            incoming[nxt] -= 1
            if incoming[nxt] == 0:
                ready.append(nxt)
    return [i for i in ids if i not in seen]


def start_sidecar() -> tuple[subprocess.Popen[str], Path, str, list[str]]:
    """Same as scene lifecycle, but decode sidecar stdio as UTF-8 (no cp1252 hang)."""
    proc = subprocess.Popen(
        [sess.node(), str(BRIDGE / "dist" / "main.js"), "--project", str(PLUGIN_PROJECT)],
        cwd=str(BRIDGE),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
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
                    "clientInfo": {"name": "test-brief-dag", "version": "0"},
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


def sidecar_corpus(rows: list[dict]) -> tuple[list[str], list[dict], str, str, bool]:
    errors: list[str] = []
    cycle = run_node(["--cycle"])
    err = cycle.get("error") if isinstance(cycle.get("error"), dict) else {}
    if cycle.get("ok") is not False or cycle.get("acyclic") is True:
        errors.append("cycle fixture must fail through compileBrief")
        acyclic_label = "unproven"
    elif str(err.get("code") or "") != "E_CONFLICT" or "circular" not in str(err.get("message") or "").lower():
        errors.append(f"cycle fixture must be E_CONFLICT circular DAG, got {cycle}")
        acyclic_label = "unproven"
    else:
        acyclic_label = "proven"
    batch = run_node(["--dir", str(FIXTURES), "--project", str(PLUGIN_PROJECT)])
    plans = batch.get("plans") if isinstance(batch.get("plans"), list) else []
    if len(plans) != 20:
        errors.append(f"harness --dir returned {len(plans)} plans")
    by_file = {str(item.get("file")): item.get("plan") for item in plans if isinstance(item, dict)}
    recs: list[dict] = []
    opened_md = False
    for meta in rows:
        plan = by_file.get(str(meta.get("file")), {})
        recs.append(plan_ok(plan if isinstance(plan, dict) else {}, meta, errors, "sidecar"))
        if str(meta.get("class")) != "vague":
            continue
        ev = {}
        for item in plans:
            if isinstance(item, dict) and str(item.get("file")) == str(meta.get("file")):
                ev = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
                break
        rel = str(ev.get("assumptions") or "")
        md_path = (PLUGIN_PROJECT / rel) if rel else None
        if md_path is None or not md_path.is_file():
            errors.append(f"sidecar {meta.get('id')}: assumptions.md missing on disk")
            continue
        text = md_path.read_text(encoding="utf-8")
        assumptions = plan.get("assumptions") if isinstance(plan, dict) else []
        if not isinstance(assumptions, list):
            assumptions = []
        for asm in assumptions:
            if not isinstance(asm, dict):
                continue
            field = str(asm.get("field") or "")
            value = str(asm.get("value") or "")
            if field and field in text and value and value in text:
                opened_md = True
                break
        if "E1–E4 are blockers" not in text and "E1-E4 are blockers" not in text:
            errors.append(f"sidecar {meta.get('id')}: assumptions.md must say E1–E4 are blockers")
    if not opened_md:
        errors.append("ASSUMPTIONS: official test never opened assumptions.md")
    complete_scenes: list[str] = []
    for meta, rec in zip(rows, recs, strict=False):
        if str(meta.get("class")) != "complete":
            continue
        scenes = [f for f in rec.get("produce_files", []) if str(f).endswith(".tscn")]
        complete_scenes.append(scenes[0] if scenes else "")
    if len({s for s in complete_scenes if s}) < 5:
        errors.append(f"complete briefs share one produce template: {complete_scenes}")
    corpus = "proven" if len(recs) == 20 and not any("sidecar" in e for e in errors) else "unproven"
    if len(recs) == 20 and all(r.get("task_count", 0) > 0 for r in recs):
        corpus = "proven"
        if any("sidecar" in e for e in errors):
            corpus = "unproven"
    return errors, recs, corpus, acyclic_label, opened_md


def live_errors(exe: Path, rows: list[dict]) -> tuple[list[str], str, list[dict]]:
    errors: list[str] = []
    live = "unrun"
    recs: list[dict] = []
    pin.kill_plugin_project_holders()
    time.sleep(1.0)
    if pin.plugin_godot_busy():
        errors.append("LIVE_UNRUN: Godot already open on plugin-project (exclusive; no second instance)")
        return errors, "unrun", recs
    errors.extend(cleanup_temp())
    proc = None
    godot = None
    desc_path = None
    secret = ""
    err_lines: list[str] = []
    godot_lines: list[str] = []
    req_id = 2
    try:
        proc, desc_path, secret, err_lines = start_sidecar()
        godot, godot_lines = pin.start_godot(exe, headless=True)
        req_id, hello, last = life.wait_hello(proc, godot, req_id)
        if not hello:
            errors.append(
                "live plugin hello/noop failed: "
                f"{sess.redact(json.dumps(last), secret)}; godot={''.join(godot_lines)[-1500:]}"
            )
            return errors, "failed", recs
        live = "ran"
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        for i, meta in enumerate(rows):
            run_id = f"01R7WP1BRF{i:016d}"
            req_id, body = pin.tool_call(
                proc,
                req_id,
                "godot.job",
                "plan",
                {"brief": meta["text"], "run_id": run_id},
                timeout=30.0,
            )
            after = pin.after_of(body)
            plan = after.get("plan") if isinstance(after.get("plan"), dict) else {}
            if body.get("ok") is not True:
                errors.append(f"plugin {meta.get('id')}: {sess.redact(json.dumps(body), secret)}")
            rec = plan_ok(plan, meta, errors, "plugin")
            recs.append(rec)
            if rec["task_count"] < 1:
                errors.append(f"plugin {meta.get('id')}: paper-ACK empty DAG")
            if str(meta.get("class")) == "vague":
                ev = after.get("evidence") if isinstance(after.get("evidence"), dict) else {}
                rel = str(ev.get("assumptions") or f"r7w1/evidence/{run_id}/assumptions.md")
                md_path = PLUGIN_PROJECT / rel
                if not md_path.is_file():
                    errors.append(f"plugin {meta.get('id')}: assumptions.md missing on disk")
                else:
                    text = md_path.read_text(encoding="utf-8")
                    if "genre.value" not in text and "camera.mode" not in text:
                        errors.append(f"plugin {meta.get('id')}: assumptions.md missing §6.2 field")
        req_id, timeline = pin.tool_call(
            proc, req_id, "godot.observer", "timeline", {"detail": "short", "limit": 50}, timeout=20.0
        )
        timeline_after = pin.after_of(timeline) if timeline.get("ok") is True else {}
        dock = timeline_after.get("dock") if isinstance(timeline_after.get("dock"), dict) else {}
        plan_dock = dock.get("plan") if isinstance(dock.get("plan"), dict) else {}
        dock_cards = plan_dock.get("cards") if isinstance(plan_dock.get("cards"), list) else []
        plan_list = timeline_after.get("plan_list") if isinstance(timeline_after.get("plan_list"), dict) else {}
        list_items = plan_list.get("items") if isinstance(plan_list.get("items"), list) else []
        list_count = int(plan_list.get("count") or 0)
        if not dock_cards:
            errors.append("observer.timeline dock.plan.cards empty — dock store, not only job.plan after.cards")
        if plan_list.get("bound") is not True or list_count < 1 or not list_items:
            errors.append("observer.timeline plan_list did not read the live dock ItemList")
        elif list_count != len(dock_cards):
            errors.append(
                f"dock ItemList count {list_count} != store cards {len(dock_cards)}"
            )
        elif not any(
            ("produce_" in str(it) or "verify_define" in str(it) or "blocker_" in str(it))
            for it in list_items
        ):
            errors.append(f"dock ItemList texts are not plan cards: {list_items[:4]}")
        req_id, cyc = pin.tool_call(
            proc,
            req_id,
            "godot.job",
            "plan",
            {
                "brief": rows[0]["text"],
                "run_id": f"01R7WP1BRF{998:016d}",
                "inject_cycle": True,
            },
            timeout=30.0,
        )
        if cyc.get("ok") is True:
            errors.append("plugin inject_cycle must fail through compile_brief")
        else:
            cerr = cyc.get("error") if isinstance(cyc.get("error"), dict) else {}
            if str(cerr.get("code") or "") != "E_CONFLICT" or "circular" not in str(
                cerr.get("message") or ""
            ).lower():
                errors.append(f"plugin inject_cycle must be E_CONFLICT circular DAG, got {cyc}")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"live brief compile failed: {type(exc).__name__}: {exc}")
        live = "failed"
    finally:
        if godot is not None:
            life.stop_proc(godot)
        if proc is not None:
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
        errors.extend(cleanup_temp())
        errors.extend(pin.project_godot_leak_errors("after suite cleanup"))
    return errors, live, recs


def labels_from(sidecar: list[dict], plugin: list[dict], corpus: str, acyclic: str) -> tuple[str, str, str, str, str]:
    rows = sidecar + plugin
    acyclic_ok = acyclic == "proven" and all(r.get("acyclic") for r in rows if r.get("task_count"))
    trace_ok = all(r.get("trace") for r in sidecar if r.get("task_count"))
    if plugin:
        trace_ok = trace_ok and all(r.get("trace") for r in plugin if r.get("task_count"))
    e_ok = True
    asm_ok = any(r.get("assumptions", 0) > 0 for r in sidecar)
    return (
        corpus,
        "proven" if acyclic_ok else "unproven",
        "proven" if trace_ok else "unproven",
        "proven" if e_ok else "unproven",
        "proven" if asm_ok else "unproven",
    )


def main() -> int:
    errors: list[str] = []
    errors.extend(hh_agent_only_addon_errors(PLUGIN_PROJECT, REPO_ROOT))
    errors.extend(src_scan_errors())
    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.is_file() else None
    if plan_text is None:
        errors.append(f"missing {rel(PLAN)}")
    else:
        errors.extend(plan_errors(plan_text))
        if re.search(r"^R7-WP1\b.*\[x\]", plan_text, re.M | re.I):
            errors.append("official harness must not tick R7-WP1")

    rows, man_errs = load_manifest()
    errors.extend(man_errs)

    built = subprocess.run(
        [npm(), "run", "generate"],
        cwd=str(BRIDGE),
        text=True,
        capture_output=True,
        check=False,
    )
    if built.returncode != 0:
        errors.append(f"bridge generate failed:\n{built.stdout}\n{built.stderr}")
        print("FAIL")
        for item in errors:
            print(f"  - {item}")
        return 1

    catalog = json.loads(ACTIONS_JSON.read_text(encoding="utf-8")) if ACTIONS_JSON.is_file() else {}
    actions = catalog.get("actions") if isinstance(catalog.get("actions"), dict) else {}
    spec = actions.get("job.plan") if isinstance(actions.get("job.plan"), dict) else {}
    if spec.get("method") != "godot.job":
        errors.append("actions.json missing job.plan")
    if spec.get("side_effect") != "read":
        errors.append("job.plan must be a read compile/display verb")

    sidecar_recs: list[dict] = []
    corpus = "unproven"
    acyclic = "unproven"
    opened_md = False
    if HARNESS.is_file() and rows:
        s_errs, sidecar_recs, corpus, acyclic, opened_md = sidecar_corpus(rows)
        errors.extend(s_errs)
    else:
        errors.append("planner harness missing after generate/build")

    exe, pin_reason = plug.find_pinned_godot()
    live = "unrun"
    plugin_recs: list[dict] = []
    if exe is None:
        errors.append(f"pinned Godot required: {pin_reason}")
    else:
        version = plug.godot_version(exe)
        if version != PINNED_VERSION:
            errors.append(f"Godot --version {version!r} != {PINNED_VERSION}")
        else:
            live_errs, live, plugin_recs = live_errors(exe, rows)
            errors.extend(live_errs)

    corpus20, acyclic_l, trace_l, e_l, asm_l = labels_from(sidecar_recs, plugin_recs, corpus, acyclic)
    if corpus20 != "proven":
        errors.append("CORPUS20 not proven")
    if acyclic_l != "proven":
        errors.append("ACYCLIC not proven")
    if trace_l != "proven":
        errors.append("TRACE not proven")
    if not any("E1" in r.get("blockers", []) for r in sidecar_recs):
        errors.append("E_BLOCKERS missing E1 in sidecar corpus")
        e_l = "unproven"
    if not any("E2" in r.get("blockers", []) for r in sidecar_recs):
        errors.append("E_BLOCKERS missing E2 in sidecar corpus")
        e_l = "unproven"
    if not any("E3" in r.get("blockers", []) for r in sidecar_recs):
        errors.append("E_BLOCKERS missing E3 in sidecar corpus")
        e_l = "unproven"
    if not any("E4" in r.get("blockers", []) for r in sidecar_recs):
        errors.append("E_BLOCKERS missing E4 in sidecar corpus")
        e_l = "unproven"
    if e_l == "unproven" and any("E_BLOCKERS missing" in e for e in errors):
        pass
    elif any("missing blocker" in e for e in errors):
        e_l = "unproven"
        errors.append("E_BLOCKERS not proven")
    else:
        e_l = "proven"
    if asm_l != "proven" or not opened_md:
        errors.append("ASSUMPTIONS not proven")
        asm_l = "unproven"
    if plugin_recs and sidecar_recs and len(plugin_recs) == len(sidecar_recs):
        for s, p in zip(sidecar_recs, plugin_recs, strict=True):
            if s.get("blockers") != p.get("blockers"):
                errors.append(f"sidecar/plugin blocker drift {s.get('id')}: {s.get('blockers')} vs {p.get('blockers')}")
            if s.get("produce_files") != p.get("produce_files"):
                errors.append(
                    f"sidecar/plugin produce drift {s.get('id')}: {s.get('produce_files')} vs {p.get('produce_files')}"
                )

    errors.extend(pin.project_godot_leak_errors("after official test"))
    pin.kill_plugin_project_holders(godot=True, node=True)
    time.sleep(1.0)
    errors.extend(cleanup_temp())
    banner = (
        f"LIVE={live}; CORPUS20={corpus20}; ACYCLIC={acyclic_l}; TRACE={trace_l}; "
        f"E_BLOCKERS={e_l}; ASSUMPTIONS={asm_l}"
    )
    if errors:
        print(f"FAIL: brief DAG; {banner}")
        for item in errors:
            print(f"  - {item}")
        return 1
    print(f"PASS: brief DAG; {banner}")
    print(f"  sidecar={len(sidecar_recs)} plugin={len(plugin_recs)} unique_briefs=20")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
