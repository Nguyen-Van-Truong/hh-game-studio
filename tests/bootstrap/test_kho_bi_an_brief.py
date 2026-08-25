#!/usr/bin/env python3
"""R8-WP1: lock Kho Bí Ẩn brief + acceptance (does not tick the plan).

Does not tick the 20-8 plan. Does not change CURRENT_VALID_WP.
Keep R8-WP1 [ ]; while unticked CURRENT_VALID_WP=R8-WP1; after tick allow R8-WP2+.
Does not start R8-WP2 graybox. Does not fake G5 human dogfood. Does not touch GX.
No snake demo. No driver scripts for the snake demo. No secret material.
--provider plan stays unused here.
Pin 4.7.1-stable only. No skip-PASS.

Verify (encoded here; this file is the official harness):
  - godot/dogfood/kho-bi-an/PROJECT_BRIEF.md is complete and parseable
  - brief compiler harness emits an acyclic DAG with status=ready and zero blockers
  - TRACE is compiler task_ids from the R7 keyword mapper (honest tautology;
    not a slice compiler; do not sell TRACE as proof a bad game is rejected)
  - asset/license budget is finite, original/CC0/MIT, OFL only for the Godot
    bundled default font, one named font, no spend, no secret
    - SCOPE proves only: distinct slice phrases (not substring key/win) +
      graybox/release split + exclusive relic-reached win. SCOPE does not
      prove a game is rich enough to reject. TRACE is not a slice compiler.
  - quality bar allows required WP2 graybox; color-rect reject is release/G5 only
  - assumption policy uses plan E1–E3 wording (API key / paid quota / code signing)

Labels: COMPILE, ACYCLIC, NO_BLOCKER, TRACE, LICENSE_BUDGET, SCOPE
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
PLAN = REPO_ROOT / "zdocs" / "20-8-godot-agent-autopilot-plan.txt"
BRIEF = REPO_ROOT / "godot" / "dogfood" / "kho-bi-an" / "PROJECT_BRIEF.md"
DOGFOOD = BRIEF.parent
BRIDGE = REPO_ROOT / "bridge"
PLUGIN_PROJECT = REPO_ROOT / "godot" / "plugin-project"
HARNESS = BRIDGE / "dist" / "planner" / "harness.js"
RUN_ID = "01R8WP1BRF00000000KBA00001"
PINNED = "4.7.1-stable"
LABELS = ("COMPILE", "ACYCLIC", "NO_BLOCKER", "TRACE", "LICENSE_BUDGET", "SCOPE")

REQUIRED_HEADINGS = (
    "genre",
    "camera",
    "resolution",
    "input",
    "platform",
    "art",
    "audio",
    "ui",
    "save",
    "content / license",
    "performance",
    "asset budget",
    "forbidden",
    "quality bar",
    "acceptance",
    "assumption policy",
)

REQUIRED_FIELD_LINES = (
    r"\*\*value:\*\*\s*top-down 2D",
    r"\*\*mode:\*\*\s*follow",
    r"\*\*base design resolution:\*\*\s*1280x720",
    r"\*\*devices:\*\*\s*keyboard and gamepad",
    r"\*\*ship target:\*\*\s*Windows desktop",
    r"\*\*needed:\*\*\s*yes",
    r"\*\*bus layout:\*\*\s*Master / Music / SFX",
    r"\*\*placeholder policy:\*\*.*PLACEHOLDER",
    r"\*\*spend:\*\*\s*none",
)

# B9: do not substring-match `key` or `win` (keyboard / Windows / API key).
SLICE_NEEDLES = (
    "key pickup",
    "relic-reached",
    "warden contact",
    "4-dir",
    "interact",
)

REQUIRED_WIN = (
    "relic-reached is win",
    "door-open is not win",
    "key pickup is not win",
)

FORBIDDEN_WIN = (
    "wins when the door opens",
    "door-open is win",
    "open door, then wins",
    "one predicate: obtain key, open door, reach relic",
)

ART_SFX_ACC_RE = re.compile(
    r"\b(art|sprite|png|palette|portrait|audio|sfx|sound|music|wav)\b",
    re.I,
)
GATE_RE = re.compile(r"r8-wp3\+|g5 polish", re.I)
FONT_FIELD_RE = re.compile(r"^\s*[-*]\s+\*\*font:\*\*\s*(.+)$", re.I | re.M)
WP2_VERIFY_PATH = "start→key→door→relic→win"
WP2_VERIFY_OLD = "start→key→door→win"

E1_RE = re.compile(
    r"\b(api key|apikey|openai key|anthropic key|steamworks secret|"
    r"account password|oauth token)\b",
    re.I,
)
E2_RE = re.compile(
    r"\b(must buy|purchase a|paid asset|paid license|paid quota|unity asset store)\b"
    r"|costs\s*\$",
    re.I,
)
E3_RE = re.compile(
    r"\b(code sign|signing certificate|upload to steam|publish to the store|"
    r"public publish|itch\.io upload)\b"
    r"|send (project |player )?data off",
    re.I,
)
CAP_RE = re.compile(
    r"^\s*[-*]\s+\*\*(art count cap|audio count cap|font count cap|"
    r"rooms cap|actors cap|keys cap|doors cap):\*\*\s*(\d+)\s*$",
    re.I,
)
INV_RE = re.compile(
    r"^\s*[-*]\s+\*\*(art inventory|audio inventory):\*\*\s*(.+)$",
    re.I,
)
LICENSE_OK = re.compile(r"\b(original|procedural|cc0|mit|ofl)\b", re.I)


def headingKey(raw: str) -> str:
    return re.sub(r"\s+", " ", raw.strip().lower())


def heading_body(text: str, heading: str) -> str:
    key = headingKey(heading)
    chunks: list[str] = []
    current = ""
    for line in text.replace("\r\n", "\n").split("\n"):
        matched = re.match(r"^##\s+(.+?)\s*$", line)
        if matched:
            current = headingKey(matched.group(1))
            continue
        if current == key:
            chunks.append(line)
    return "\n".join(chunks)


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def emit(text: str) -> None:
    stream = sys.stdout
    encoding = getattr(stream, "encoding", None) or "utf-8"
    stream.write(text.encode(encoding, errors="replace").decode(encoding, errors="replace"))
    stream.write("\n")


def npm() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def node() -> str:
    return "node.exe" if os.name == "nt" else "node"


def strip_assumption_policy(text: str) -> str:
    lines = text.replace("\r\n", "\n").split("\n")
    kept: list[str] = []
    skip = False
    for line in lines:
        if re.match(r"^##\s+assumption policy\s*$", line, re.I):
            skip = True
            continue
        if skip and re.match(r"^##\s+", line):
            skip = False
        if not skip:
            kept.append(line)
    return "\n".join(kept)


def plan_errors(text: str) -> list[str]:
    """Keep R8-WP1 [ ]; while unticked require CURRENT_VALID_WP=R8-WP1."""
    errors: list[str] = []
    current = ""
    wp1 = None
    wp2 = None
    g4 = None
    g5 = None
    gx = None
    total = None
    r8_row = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R8-WP1\b", stripped):
            wp1 = stripped
        if re.match(r"^R8-WP2\b", stripped):
            wp2 = stripped
        if "G4 AUTONOMY" in stripped or stripped.startswith("G4 "):
            if g4 is None:
                g4 = stripped
        if "G5 DOGFOOD" in stripped or stripped.startswith("G5 "):
            if g5 is None:
                g5 = stripped
        if "GX FORK" in stripped or stripped.startswith("GX "):
            if gx is None:
                gx = stripped
        if stripped.startswith("Tiến độ tổng:") or stripped.startswith("Tien do tong:"):
            total = stripped
        if "| 8 |" in stripped and "G5" in stripped:
            r8_row = stripped
    if wp1 is None:
        return ["plan missing R8-WP1 heading"]
    ticked = bool(re.search(r"\[x\]", wp1, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp1:
            errors.append("R8-WP1 heading must keep [ ] until coordinator tick")
        if current != "R8-WP1":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R8-WP1 while WP1 is unticked)")
        if wp2 and re.search(r"\[x\]", wp2, re.IGNORECASE):
            errors.append("R8-WP2 must stay unticked; this WP does not start graybox")
        if WP2_VERIFY_PATH not in text:
            errors.append("R8-WP2 verify path must be start→key→door→relic→win")
        if WP2_VERIFY_OLD in text:
            errors.append("R8-WP2 verify must not use start→key→door→win without relic")
        if total and "50/60" not in total:
            errors.append(f"progress must stay 50/60 while R8-WP1 is unticked: {total}")
        if r8_row and not re.search(r"\[ \]\s*0/6", r8_row):
            errors.append(f"R8 row must stay 0/6 while WP1 is unticked: {r8_row}")
    elif not re.match(r"^R8-WP([2-9]|\d{2,})$|^R9-WP\d+$|^RX-WP\d+$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R8-WP2+ after R8-WP1 tick)")
    if g4 is None or not re.search(r"\[x\]", g4, re.IGNORECASE):
        errors.append("R8-WP1 depends on G4; plan G4 must stay ticked")
    if g5 is not None and re.search(r"\[x\]", g5, re.IGNORECASE):
        errors.append("official harness must not tick G5")
    if gx is not None and re.search(r"\[x\]", gx, re.IGNORECASE):
        errors.append("official harness must not touch GX")
    return errors


def src_scan_errors() -> list[str]:
    errors: list[str] = []
    self_text = Path(__file__).read_text(encoding="utf-8")
    for label in LABELS:
        if label not in self_text:
            errors.append(f"official test must label {label}")
    if "No skip-PASS" not in self_text and "skip-PASS" not in self_text:
        errors.append("official test must refuse skip-PASS")
    if "does not fake G5" not in self_text.lower() and "Does not fake G5" not in self_text:
        errors.append("official test must refuse to fake G5 human dogfood")
    if "does not touch GX" not in self_text.lower() and "Does not touch GX" not in self_text:
        errors.append("official test must refuse to touch GX")
    if "4.7." + "2" in self_text:
        errors.append("official test must refuse Godot 4.7." + "2 pin")
    if ("drive_" + "snake") in self_text:
        errors.append("official test must not include drive_" + "snake scripts")
    if "--provider" in self_text and "unused" not in self_text:
        errors.append("official test must not invoke a model provider")
    if ("HH_" + "OPENAI") in self_text or ("ANTHROPIC_" + "API_KEY") in self_text:
        errors.append("official test must not mention provider secrets")
    return errors


def dogfood_tree_errors(wp1_ticked: bool) -> list[str]:
    errors: list[str] = []
    if not BRIEF.is_file():
        return [f"missing {rel(BRIEF)}"]
    if not wp1_ticked:
        extras: list[str] = []
        for path in DOGFOOD.rglob("*"):
            if not path.is_file():
                continue
            if path.resolve() == BRIEF.resolve():
                continue
            extras.append(rel(path))
        if extras:
            errors.append(f"R8-WP1 must not start graybox extras: {extras[:8]}")
        for name in ("project.godot",):
            if (DOGFOOD / name).exists():
                errors.append(f"R8-WP2 theater: {rel(DOGFOOD / name)} exists")
        for path in DOGFOOD.rglob("*"):
            if path.suffix.lower() in {".tscn", ".gd", ".import"}:
                errors.append(f"R8-WP2 theater: {rel(path)}")
    return errors


def brief_body_errors(text: str) -> list[str]:
    errors: list[str] = []
    headings = {
        headingKey(m.group(1))
        for m in re.finditer(r"^##\s+(.+?)\s*$", text, re.M)
    }
    for heading in REQUIRED_HEADINGS:
        if heading not in headings:
            errors.append(f"brief missing ## {heading}")
    for pattern in REQUIRED_FIELD_LINES:
        if not re.search(pattern, text, re.I):
            errors.append(f"brief missing required field /{pattern}/")
    low = text.lower()
    for needle in SLICE_NEEDLES:
        if needle not in low:
            errors.append(f"brief missing slice needle {needle!r}")
    for needle in ("palette", "16px", "title", "pause", "user data", "60 fps"):
        if needle not in low:
            errors.append(f"brief missing product needle {needle!r}")
    if "keyboard" not in low or "gamepad" not in low:
        errors.append("brief must require keyboard and gamepad")
    if "1280x720" not in low.replace("×", "x"):
        errors.append("brief must lock 1280x720")
    if "windows" not in low:
        errors.append("brief must target Windows")
    if "placeholder" not in low:
        errors.append("brief must name PLACEHOLDER policy")
    if re.search(r"\b(g5\s*pass|human played|dogfood signed)\b", low):
        errors.append("brief must not fake G5 human dogfood")
    scan = strip_assumption_policy(text)
    if E1_RE.search(scan):
        errors.append("brief product text trips E1 secret wording")
    if E2_RE.search(scan):
        errors.append("brief product text trips E2 spend wording")
    if E3_RE.search(scan):
        errors.append("brief product text trips E3 publish wording")
    if " | " in "".join(re.findall(r"^\s*[-*]\s+\*\*[^*]+:\*\*\s*(.*)$", text, re.M)):
        short_pipes = [
            val
            for val in re.findall(r"^\s*[-*]\s+\*\*[^*]+:\*\*\s*(.*)$", text, re.M)
            if " | " in val and len(val) < 64
        ]
        if short_pipes:
            errors.append(f"brief field looks like a template placeholder: {short_pipes[:3]}")
    return errors


def graybox_release_errors(text: str) -> list[str]:
    """B1/B6: WP2 graybox is required and legal; color-rect reject is release/G5 only."""
    errors: list[str] = []
    qb = heading_body(text, "quality bar").lower()
    acc = heading_body(text, "acceptance").lower()
    blob = f"{qb}\n{acc}"
    if "r8-wp2 graybox" not in blob or "required and legal" not in blob:
        errors.append("quality bar / acceptance must say R8-WP2 graybox is required and legal")
    if "colored rectangles" not in blob and "color-rect" not in blob:
        errors.append("must name colored-rectangle graybox")
    if "applies at release / g5 only" not in qb:
        errors.append("quality bar must say color-rect reject applies at release / G5 only")
    if re.search(r"a build that is only colored rectangles", qb) and "release" not in qb:
        errors.append("quality bar forbids the required WP2 graybox")
    return errors


def unique_win_errors(text: str) -> list[str]:
    """B8: exclusive win flag is relic-reached only; door-open and key pickup are not win."""
    errors: list[str] = []
    low = text.lower()
    for phrase in REQUIRED_WIN:
        if phrase not in low:
            errors.append(f"win lock missing {phrase!r}")
    for phrase in FORBIDDEN_WIN:
        if phrase in low:
            errors.append(f"win lock forbids {phrase!r}")
    return errors


def assumption_table_errors(text: str) -> list[str]:
    """B4/B6: plan/template E1–E3 wording lives in assumption policy."""
    errors: list[str] = []
    ap = heading_body(text, "assumption policy").lower()
    if "api key" not in ap:
        errors.append("assumption policy missing API key")
    if "paid quota" not in ap:
        errors.append("assumption policy missing paid quota")
    if "code signing" not in ap:
        errors.append("assumption policy missing code signing")
    return errors


def named_font_errors(text: str) -> list[str]:
    """B5/B12: every **font:** field must name Open Sans. Decoy elsewhere does not count."""
    errors: list[str] = []
    fields = FONT_FIELD_RE.findall(text)
    if not fields:
        errors.append("brief must name one font")
        return errors
    for raw in fields:
        val = raw.strip()
        if not val or re.search(r"\b(tbd|todo|unknown|none|n/?a)\b", val, re.I):
            errors.append("font field is not a named font")
        if not re.search(r"open sans", val, re.I):
            errors.append("**font:** must name Open Sans (decoy elsewhere does not count)")
        if re.search(r"comic sans", val, re.I):
            errors.append("**font:** must not be Comic Sans")
    if not re.search(r"\bofl\b", text, re.I):
        errors.append("brief must name the font license OFL")
    return errors


def art_sfx_acceptance_errors(text: str) -> list[str]:
    """B10/B12: art/SFX in acceptance without WP3+/G5 polish is current-slice produce."""
    errors: list[str] = []
    acc = heading_body(text, "acceptance")
    for line in acc.splitlines():
        if not re.match(r"^\s*[-*]\s+", line):
            continue
        if ART_SFX_ACC_RE.search(line) and not GATE_RE.search(line):
            errors.append(
                "acceptance art/SFX is current-slice "
                f"(need WP3+/G5 polish gate): {line.strip()[:80]}"
            )
    return errors


def scope_needle_collision_errors() -> list[str]:
    """B9: keyboard / Windows / API key must not satisfy SCOPE needles."""
    decoy = "keyboard and gamepad on Windows desktop; E1 API key"
    hits = [n for n in SLICE_NEEDLES if n.lower() in decoy.lower()]
    if hits:
        return [f"SCOPE needles collide with keyboard/Windows/API key: {hits}"]
    return []


def _inject_acceptance(brief: str, extra: str) -> str:
    return re.sub(
        r"(^##\s+acceptance\s*$)",
        r"\1\n" + extra.rstrip(),
        brief,
        count=1,
        flags=re.M | re.I,
    )


def mutation_lock_errors(brief: str) -> list[str]:
    """B12: official harness must FAIL the three in-process brief mutations."""
    errors: list[str] = []
    mut_a = brief + "\nplayer wins when the door opens\n"
    if not unique_win_errors(mut_a):
        errors.append("harness must FAIL a brief that adds 'wins when the door opens'")

    mut_b = FONT_FIELD_RE.sub(r"- **font:** Comic Sans MS", brief)
    if "open sans" not in mut_b.lower():
        mut_b += "\n\nWe considered Open Sans but rejected it.\n"
    if not named_font_errors(mut_b):
        errors.append("harness must FAIL Comic Sans as **font:** with Open Sans decoy")

    mut_c = _inject_acceptance(
        brief,
        "- art sprites follow the art bible palette and 16px tile scale\n"
        "- audio SFX play on key pickup",
    )
    if not art_sfx_acceptance_errors(mut_c):
        errors.append("harness must FAIL art/SFX in acceptance without WP3+/G5 gate")
    return errors


def budget_errors(text: str) -> tuple[list[str], dict[str, int], dict[str, list[str]]]:
    errors: list[str] = []
    caps: dict[str, int] = {}
    inventories: dict[str, list[str]] = {}
    for line in text.splitlines():
        cap = CAP_RE.match(line)
        if cap:
            caps[cap.group(1).lower()] = int(cap.group(2))
            continue
        inv = INV_RE.match(line)
        if inv:
            items = [part.strip() for part in inv.group(2).split(",") if part.strip()]
            inventories[inv.group(1).lower()] = items
    limits = {
        "art count cap": (1, 32),
        "audio count cap": (1, 16),
        "font count cap": (1, 2),
        "rooms cap": (1, 4),
        "actors cap": (1, 2),
        "keys cap": (1, 1),
        "doors cap": (1, 1),
    }
    for key, (lo, hi) in limits.items():
        if key not in caps:
            errors.append(f"LICENSE_BUDGET missing {key}")
            continue
        if caps[key] < lo or caps[key] > hi:
            errors.append(f"{key}={caps[key]} outside {lo}..{hi}")
    art_items = inventories.get("art inventory", [])
    audio_items = inventories.get("audio inventory", [])
    if len(art_items) < 6:
        errors.append(f"art inventory too thin: {art_items}")
    if len(audio_items) < 4:
        errors.append(f"audio inventory too thin: {audio_items}")
    if art_items and caps.get("art count cap", 0) < len(art_items):
        errors.append("art inventory exceeds art count cap")
    if audio_items and caps.get("audio count cap", 0) < len(audio_items):
        errors.append("audio inventory exceeds audio count cap")
    license_blob = "\n".join(
        line
        for line in text.splitlines()
        if re.search(r"license", line, re.I)
    )
    if not LICENSE_OK.search(license_blob):
        errors.append("license set must be original / procedural / CC0 / MIT / OFL")
    if re.search(
        r"\*\*(allowed licenses[^:]*|license set):\*\*.*\b(unknown|unlicensed|all rights reserved)\b",
        text,
        re.I,
    ):
        errors.append("license set is not feasible")
    spend_m = re.search(r"^\s*[-*]\s+\*\*spend:\*\*\s*(\S+)", text, re.I | re.M)
    if spend_m is None or spend_m.group(1).lower() != "none":
        errors.append("spend must be none")
    return errors, caps, inventories


def detect_cycle(tasks: list[object]) -> list[str]:
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


def compile_errors(plan: dict) -> list[str]:
    errors: list[str] = []
    if plan.get("ok") is not True:
        return [f"COMPILE failed: {plan}"]
    if plan.get("status") != "ready":
        errors.append(f"status={plan.get('status')!r} (need ready)")
    if plan.get("complete") is not True:
        errors.append("complete brief must compile as complete")
    assumptions = plan.get("assumptions") if isinstance(plan.get("assumptions"), list) else []
    if assumptions:
        errors.append(f"complete brief must not invent assumptions: {assumptions}")
    blockers = plan.get("blockers") if isinstance(plan.get("blockers"), list) else []
    if blockers:
        errors.append(f"NO_BLOCKER failed: {blockers}")
    tasks = plan.get("tasks") if isinstance(plan.get("tasks"), list) else []
    if not tasks:
        errors.append("empty DAG")
        return errors
    if plan.get("acyclic") is not True or detect_cycle(tasks):
        errors.append("ACYCLIC failed")
    kinds = [str(t.get("kind") or "") for t in tasks if isinstance(t, dict)]
    if kinds and kinds[0] != "test":
        errors.append(f"tests-first violated; first kind={kinds[0]!r}")
    if "blocker" in kinds:
        errors.append("DAG contains blocker nodes")
    acceptance = plan.get("acceptance") if isinstance(plan.get("acceptance"), list) else []
    traces = plan.get("traces") if isinstance(plan.get("traces"), list) else []
    if len(acceptance) < 8:
        errors.append(f"acceptance too thin: {len(acceptance)}")
    traced = 0
    for item in acceptance:
        if not isinstance(item, dict):
            continue
        ids = item.get("task_ids") if isinstance(item.get("task_ids"), list) else []
        if ids:
            traced += 1
        else:
            errors.append(f"TRACE missing tasks for {item.get('id')}")
    if traced != len(acceptance) or len(traces) != len(acceptance):
        errors.append(f"TRACE failed acc={len(acceptance)} traces={len(traces)} traced={traced}")
    produce_files: list[str] = []
    produce_accs: list[set[str]] = []
    acc_ids = [str(a.get("id")) for a in acceptance if isinstance(a, dict) and a.get("id")]
    for task in tasks:
        if not isinstance(task, dict):
            continue
        if str(task.get("kind") or "") == "test" and not str(task.get("criterion") or "").strip():
            errors.append(f"test {task.get('id')} has no acceptance criterion")
        if str(task.get("kind") or "") == "produce":
            files = task.get("files") if isinstance(task.get("files"), list) else []
            produce_files.extend(str(f) for f in files)
            produce_accs.append({str(x) for x in (task.get("acceptance") or [])})
    if "res://art/overworld/key.png" not in produce_files:
        errors.append(f"compiler must map Kho Bí Ẩn to topdown produce, got {produce_files}")
    if any(name in "".join(produce_files) for name in ("memory", "farm", "match3", "tower", "platformer")):
        errors.append(f"wrong produce family: {produce_files}")
    if len(acc_ids) > 1 and produce_accs and all(s == set(acc_ids) for s in produce_accs):
        errors.append("every produce stamps every acceptance")
    for task in tasks:
        if not isinstance(task, dict):
            continue
        tid = str(task.get("id") or "")
        if tid in ("produce_art", "produce_audio"):
            inherited = task.get("acceptance") if isinstance(task.get("acceptance"), list) else []
            if inherited:
                errors.append(
                    f"WP2 graybox must not inherit {tid} from acceptance {inherited}"
                )
    return errors


def run_harness() -> dict:
    proc = subprocess.run(
        [
            node(),
            str(HARNESS),
            "--brief",
            str(BRIEF),
            "--project",
            str(PLUGIN_PROJECT),
            "--run-id",
            RUN_ID,
        ],
        cwd=str(BRIDGE),
        text=True,
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        return {
            "ok": False,
            "error": {"message": (proc.stderr or proc.stdout or "")[:800], "code": "E_UNVERIFIED"},
        }
    line = (proc.stdout or "").strip().splitlines()[-1] if proc.stdout else "{}"
    try:
        parsed = json.loads(line)
    except json.JSONDecodeError:
        return {"ok": False, "error": {"message": line[:400], "code": "E_UNVERIFIED"}}
    return parsed if isinstance(parsed, dict) else {"ok": False}


def cleanup_evidence() -> None:
    ev = PLUGIN_PROJECT / "r7w1" / "evidence" / RUN_ID
    if ev.exists():
        shutil.rmtree(ev, ignore_errors=True)


def wp1_is_ticked(plan_text: str) -> bool:
    for line in plan_text.splitlines():
        if re.match(r"^R8-WP1\b", line.strip()):
            return bool(re.search(r"\[x\]", line, re.I))
    return False


def main() -> int:
    errors: list[str] = []
    errors.extend(src_scan_errors())
    if not PLAN.is_file():
        errors.append(f"missing {rel(PLAN)}")
        emit("FAIL: R8-WP1 Kho Bi An brief")
        for item in errors:
            emit(f"  - {item}")
        return 1
    plan_text = PLAN.read_text(encoding="utf-8")
    errors.extend(plan_errors(plan_text))
    ticked = wp1_is_ticked(plan_text)
    errors.extend(dogfood_tree_errors(ticked))

    compile_l = "unproven"
    acyclic_l = "unproven"
    blocker_l = "unproven"
    trace_l = "unproven"
    budget_l = "unproven"
    scope_l = "unproven"

    if BRIEF.is_file():
        brief = BRIEF.read_text(encoding="utf-8")
        errors.extend(brief_body_errors(brief))
        errors.extend(scope_needle_collision_errors())
        g_errs = graybox_release_errors(brief)
        w_errs = unique_win_errors(brief)
        a_errs = art_sfx_acceptance_errors(brief)
        errors.extend(g_errs)
        errors.extend(w_errs)
        errors.extend(a_errs)
        errors.extend(assumption_table_errors(brief))
        errors.extend(named_font_errors(brief))
        errors.extend(mutation_lock_errors(brief))
        b_errs, caps, inventories = budget_errors(brief)
        errors.extend(b_errs)
        if not b_errs:
            budget_l = "proven"
        low = brief.lower()
        needles_ok = all(needle in low for needle in SLICE_NEEDLES)
        # SCOPE proves only distinct needles + graybox/release split + exclusive win.
        # It does not prove a game is rich enough to reject.
        if not g_errs and not w_errs and needles_ok:
            scope_l = "proven"
        if "kho bí ẩn" not in low and "kho bi an" not in low:
            errors.append("brief must name Kho Bí Ẩn")
        if inventories and budget_l == "proven":
            pass
    else:
        errors.append("LICENSE_BUDGET unproven: missing brief")

    built = subprocess.run(
        [npm(), "run", "build"],
        cwd=str(BRIDGE),
        text=True,
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )
    if built.returncode != 0:
        errors.append(f"bridge build failed:\n{built.stdout}\n{built.stderr}")
        emit("FAIL: R8-WP1 Kho Bi An brief")
        for item in errors:
            emit(f"  - {item}")
        return 1
    if not HARNESS.is_file():
        errors.append("planner harness missing after bridge build")
    else:
        try:
            plan = run_harness()
            c_errs = compile_errors(plan)
            errors.extend(c_errs)
            if plan.get("ok") is True:
                compile_l = "proven"
            if plan.get("acyclic") is True and not any("ACYCLIC" in e for e in c_errs):
                acyclic_l = "proven"
            if not plan.get("blockers") and not any("NO_BLOCKER" in e or "blocker" in e.lower() for e in c_errs):
                blocker_l = "proven"
            # TRACE: compiler task_ids. Honest tautology of the R7 keyword mapper.
            if not any(e.startswith("TRACE") or "TRACE" in e for e in c_errs):
                if isinstance(plan.get("traces"), list) and plan.get("traces"):
                    trace_l = "proven"
        finally:
            cleanup_evidence()

    if compile_l != "proven":
        errors.append("COMPILE not proven")
    if acyclic_l != "proven":
        errors.append("ACYCLIC not proven")
    if blocker_l != "proven":
        errors.append("NO_BLOCKER not proven")
    if trace_l != "proven":
        errors.append("TRACE not proven")
    if budget_l != "proven":
        errors.append("LICENSE_BUDGET not proven")
    if scope_l != "proven":
        errors.append("SCOPE not proven")

    banner = (
        f"COMPILE={compile_l}; ACYCLIC={acyclic_l}; NO_BLOCKER={blocker_l}; "
        f"TRACE={trace_l}; LICENSE_BUDGET={budget_l}; SCOPE={scope_l}"
    )
    if errors:
        emit(f"FAIL: R8-WP1 Kho Bi An brief; {banner}")
        for item in errors:
            emit(f"  - {item}")
        return 1
    emit(f"PASS: R8-WP1 Kho Bi An brief; {banner}")
    emit(f"  brief={rel(BRIEF)} pin={PINNED} run_id={RUN_ID}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
