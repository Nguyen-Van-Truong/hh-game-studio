#!/usr/bin/env python3
"""R7-WP6: 90 min zero-touch + Gate G4 stamp (does not tick the plan).

Does not tick the 20-8 plan. Does not change CURRENT_VALID_WP.
Keep R7-WP6 [ ]; while unticked CURRENT_VALID_WP=R7-WP6; after tick allow R8+.
Must NOT lock [x] forever. Pin 4.7.1-stable only. Refuse later 4.7 patches past .1-stable.
No skip-PASS. Does not start R8 or G5. Does not tick G4.
No demo game tree. No R8 dogfood tree. No driver scripts for the demo.
No FakeExecutor mutate ACK. No job.run fixture: ok_slice as the product.
No F6 / human Play / OS inject. No pin kill of plugin-project holders.
HH_ZERO_TOUCH_FAST must not prove DURATION90. Sleep with no process is not duration.
G4_READY is a stamp only — this file must not flip plan G4 [ ].
screenshots=SKIP must not stamp VIDEO=proven.
Official (HH_ZERO_TOUCH_FAST unset) writes tests/bootstrap/.zero_touch_official.log
(gitignored) with ticks + PASS/FAIL. FAST writes only tests/bootstrap/.zero_touch_fast.log.
Cursor TTY/job GC is not the only record. Official child detaches (CREATE_BREAKAWAY_FROM_JOB /
CREATE_NEW_PROCESS_GROUP) so a lost controlling TTY does not instantly kill the scorer.
The official child is the only process that may write PASS: zero-touch / FAIL: zero-touch
into the official log (fast=0). Parent waiter may tee spawn/heartbeat lines, never a PASS
banner, and must wait for the child. Leftover FAST PASS is wiped/rotated off the official path.

Verify (encoded here; this file is the official harness):
  - LIVE: trial Godot + sidecar + Host McpStdioExecutor (src_scan is not enough)
  - DURATION90: elapsed>=5400 AND host+Godot+sidecar PIDs up AND last successful
    observe scene.read is recent (heartbeat_age gated, not print-only).
    sidecar_pid==0 is not a skip that proves liveness. Do not re-prove LIVE
    from job.plan when live_up is now false. HH_ZERO_TOUCH_FAST must not prove
    DURATION90. Sleep with no process is not duration.
  - ZERO_TOUCH: after T0 only plugin/MCP/Host write .tscn/.gd; no human input
  - SELF_PLAN: job.plan ok + tasks with acceptance that later test/script use
    (not merely /memory/ in outputs; not a recorded playbook)
  - SELF_PLAY: hh_agent_runtime + real Play process
  - REPAIR: fail then godot.test repair then pass in the Host tool log
    (fail then patch then pass / fail then pass; not Host increment; kind may be logged).
    Or unused: no test.run logic fail after the game exists, defined tests green,
    Host still has maybeQueueRepair / godot.test repair, and no planted hole.
    Do not test.define matches/won if you will skip their test.run.
    Unused stamp requires all_defined_green AND zero defined-but-unrun keys.
    G4_NEED treats proven OR unused as satisfied. Do not drop REPAIR from G4_NEED.
  - TEST_GREEN: one godot.test.run or one play-session after-blob where
    matches>=2 AND won==true on that same run (not a collage of isolated
    flips>=1 / matches>=1 / won=true tapes). Defined keys may still include
    flips and matches and won (not flips-only). ready_ok-only / Fixture fail.
    Host pair-walk tapes fail, including the short one-pair tape
    (ui_accept, ui_down, ui_accept). walk_is_produced_oracle /
    steps_are_host_pair_walk also inspect the godot.input press stream
    (not only define JSON). walk_plays_produced_board is not a
    whitelist; a tape that is the mechanical solution of the produced
    PackedInt32Array is a FAIL. Self-play from visible ColorRect / screenshot
    colors is allowed. if only flips can be honest, that is not enough here
  - VIDEO: two tick-distinct screenshot ACKs, hash-different, with
    ui_accept (or play test accept) between them. Stamp is screenshot pair
    only.     Require two session PNGs plus tile-area / tile area (or equivalent visual)
    change (not cursor-chrome only) between the two screenshot ACKs.
    flips>=1 or got on flips in the ACK after is not enough without those PNGs.
    Count PNGs from this
    session's screenshot ACKs with existing abs_path, not leftover
    .hh-agent piles. A later test.run flips>=1 is not board-change proof
    when ACK paths are missing. Do not stamp on movie_ok
    name-contains-movie alone. Refuse the plant pair {2160f75bd0b2,
    e3181596b785}. Do not refuse first-hash 2160f75bd0b2 alone.
    Do not hardcode-allow {2160f75bd0b2, 51799480eff2}.
    Do not hardcode-allow or hardcode-refuse 51799480eff2.
    Require shot B at or after a second distinct accept or after
    matches>=1 / flips>=2, not only the first flip.
    Refuse if the only change is cursor highlight.
    write-movie name-contains-movie is not enough.
  - CHECKPOINT/GIT: nested-git commit after a passing game test.run
    (count >= 2; do not stamp because params.message says after green)
  - PAUSE_RESUME: mutating tool between pause and resume, or resume then later work
  - G4_NEED must include REVIEW_PKG
  - ZERO_TOUCH: T0 is brief+project.godot+addon only; after T0, trial
    .tscn/.gd come from Godot/sidecar/Host (refuse pre-placed board.tscn/board.gd)
  - REPAIR / PAUSE_RESUME / CHECKPOINT/GIT / LEDGER / TIMELINE / VIDEO /
    REVIEW_PKG / E_INPUT / OUTPUT_RUNS / TEST_GREEN / HOST / G4_READY
  - Do not require memoryBoardScript in src_scan
  - HH_ZERO_TOUCH_FAST must not prove DURATION90/G4_READY
  - HOST is state.executor==mcp-stdio or report.executor==mcp-stdio after
    waitForPlugin or the first MCP ACK, not a context_summary substring.
    Refuse scored play/test tools with source fake-executor.
    Official 5400s kill reads durable report.json written during observe hold.
    FAST must not exit early because report.json exists.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hh_agent_allow import hh_agent_only_addon_errors
import test_plugin_router as plug
import test_scene_lifecycle as life

BRIDGE = REPO_ROOT / "bridge"
HOST = REPO_ROOT / "host"
PLAN = REPO_ROOT / "zdocs" / "20-8-godot-agent-autopilot-plan.txt"
PLUGIN_PROJECT = REPO_ROOT / "godot" / "plugin-project"
ADDON = PLUGIN_PROJECT / "addons" / "hh_agent"
ACTIONS_JSON = ADDON / "core" / "actions.json"
PRODUCT_RUNTIME = ADDON / "runtime" / "hh_agent_runtime.gd"
PINNED_VERSION = plug.PINNED_VERSION
VENDOR_NEEDLES = plug.VENDOR_NEEDLES
SLUG = "tileflip"
TRIAL = REPO_ROOT / "godot" / "trials" / f"r7w6-{SLUG}"
BRIEF_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "r7w6_tileflip" / "PROJECT_BRIEF.md"
SCREENSHOTS = "runtime.screenshot"
ZERO_TOUCH_WALL_SEC = 5400
OBSERVE_STALE_SEC = 90
OFFICIAL_LOG = REPO_ROOT / "tests" / "bootstrap" / ".zero_touch_official.log"
FAST_LOG = REPO_ROOT / "tests" / "bootstrap" / ".zero_touch_fast.log"
OFFICIAL_CHILD_ENV = "HH_ZERO_TOUCH_OFFICIAL_CHILD"
CREATE_BREAKAWAY_FROM_JOB = getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0x01000000)
CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
DETACHED_PROCESS = getattr(subprocess, "DETACHED_PROCESS", 0)
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_IO_HOLD: list[object] = []
_CTRL_HANDLER = None
LABELS = (
    "LIVE",
    "DURATION90",
    "ZERO_TOUCH",
    "SELF_PLAN",
    "SELF_PLAY",
    "REPAIR",
    "PAUSE_RESUME",
    "CHECKPOINT/GIT",
    "LEDGER",
    "TIMELINE",
    "VIDEO",
    "REVIEW_PKG",
    "E_INPUT",
    "OUTPUT_RUNS",
    "TEST_GREEN",
    "HOST",
    "G4_READY",
)
G4_NEED = (
    "LIVE",
    "DURATION90",
    "ZERO_TOUCH",
    "SELF_PLAN",
    "SELF_PLAY",
    "REPAIR",
    "PAUSE_RESUME",
    "CHECKPOINT/GIT",
    "LEDGER",
    "TIMELINE",
    "VIDEO",
    "REVIEW_PKG",
    "E_INPUT",
    "OUTPUT_RUNS",
    "TEST_GREEN",
    "HOST",
)

PROJECT_GODOT = """; Engine configuration file.
config_version=5

[application]

config/name="R7-WP6 Tile Flip"
config/description="Zero-touch memory tile-flip trial. Independent of R8 dogfood."
config/features=PackedStringArray("4.7", "Forward Plus")

[debug]

file_logging/enable_file_logging=true
gdscript/warnings/untyped_declaration=1
gdscript/warnings/inferred_declaration=1

[display]

window/size/viewport_width=1280
window/size/viewport_height=720

[editor_plugins]

enabled=PackedStringArray("res://addons/hh_agent/plugin.cfg")
"""

TRIAL_GITIGNORE = """.godot/
.hh-agent/
addons/
*.uid
"""


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def npm() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def node() -> str:
    return "node.exe" if os.name == "nt" else "node"


def git_bin() -> str:
    return "git.exe" if os.name == "nt" else "git"


def plan_errors(text: str) -> list[str]:
    """Keep R7-WP6 [ ]; while unticked require CURRENT_VALID_WP=R7-WP6."""
    errors: list[str] = []
    current = ""
    wp6 = None
    r8 = None
    g4 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R7-WP6\b", stripped):
            wp6 = stripped
        if re.match(r"^R8-WP1\b", stripped):
            r8 = stripped
        if "G4 AUTONOMY" in stripped or stripped.startswith("G4 "):
            if g4 is None:
                g4 = stripped
    if wp6 is None:
        return ["plan missing R7-WP6 heading"]
    ticked = bool(re.search(r"\[x\]", wp6, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp6:
            errors.append("R7-WP6 heading must keep [ ] until coordinator tick")
        if current != "R7-WP6":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R7-WP6 while WP6 is unticked)")
        if r8 and re.search(r"\[x\]", r8, re.IGNORECASE):
            errors.append("R8 must stay unticked; this WP does not start dogfood")
    elif not re.match(r"^R8-WP\d+$|^R9-WP\d+$|^RX-WP\d+$|^R7-WP([7-9]|\d{2,})$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R8+ after R7-WP6 tick)")
    if g4 is not None and re.search(r"\[x\]", g4, re.IGNORECASE):
        errors.append("official harness must not tick G4")
    return errors


def _unlock_and_remove(func, path, _exc) -> None:
    try:
        os.chmod(path, 0o700)
        func(path)
    except OSError:
        pass


def wipe_dir(folder: Path) -> None:
    if not folder.exists():
        return
    for child in folder.rglob("*"):
        try:
            if child.is_file() or child.is_symlink():
                os.chmod(child, 0o700)
                child.unlink()
        except OSError:
            pass
    try:
        shutil.rmtree(folder, onexc=_unlock_and_remove)
    except TypeError:
        shutil.rmtree(folder, onerror=_unlock_and_remove)


def src_scan_errors() -> list[str]:
    errors: list[str] = []
    self_text = Path(__file__).read_text(encoding="utf-8")
    for label in LABELS:
        if label not in self_text:
            errors.append(f"official test must label {label}")
    if "No skip-PASS" not in self_text and "skip-PASS" not in self_text:
        errors.append("official test must refuse skip-PASS")
    if "HH_ZERO_TOUCH_FAST must not prove DURATION90" not in self_text:
        errors.append("official test must encode that HH_ZERO_TOUCH_FAST must not prove DURATION90")
    if "Sleep with no process is not duration" not in self_text:
        errors.append("sleep without processes is not duration")
    if "does not tick G4" not in self_text:
        errors.append("official test must refuse to tick G4")
    if ("res://" + "snake") in self_text or ("kho" + "-bi-an") in self_text:
        errors.append("official test must stay independent of demo game trees")
    if ("4.7." + "2") in self_text:
        errors.append("official test must refuse Godot 4.7." + "2 pin")
    if ("drive_" + "snake") in self_text:
        errors.append("official test must not include drive_" + "snake scripts")
    if ("kill_" + "plugin_project_holders") in self_text:
        errors.append("official test must not kill plugin-project holders")
    if ("Send" + "Input") in self_text or ("win32" + "api") in self_text:
        errors.append("official test must not OS-inject input")
    if re.search(r"time\.sleep\(\s*5400", self_text):
        errors.append("must not fake DURATION90 with a 90-minute idle sleep and no live processes")
    if ("SCREENSHOTS = " + '"SKIP"') in self_text:
        errors.append("screenshots=SKIP must not stamp VIDEO=proven")
    if "hh_agent_runtime" not in self_text:
        errors.append("SELF_PLAY must require hh_agent_runtime")
    if "ok_slice" in self_text and "job.run fixture" not in self_text:
        errors.append("official must refuse job.run fixture ok_slice as the product")
    if ("cpu" + "Work") in self_text or ("busy-" + "flag") in self_text:
        errors.append("must not sign G4 with WP4 schedule lane")
    host_text = (HOST / "src" / "host.ts").read_text(encoding="utf-8")
    if "McpStdioExecutor" not in host_text or "wireExecutor" not in host_text:
        errors.append("Host.create must wire McpStdioExecutor for real MCP")
    if "new FakeExecutor()" not in host_text or "mcpProject" not in host_text:
        errors.append("Host.create without --mcp-project must still use FakeExecutor")
    if "mcpProject" not in host_text:
        errors.append("Host.create must take mcpProject to attach real MCP")
    if "DURATION90 requires host still live" not in host_text:
        errors.append("observeUntilDeadline must keep host alive past deadline_at for DURATION90")
    if 'phase = "observing"' not in host_text:
        errors.append("host must persist phase=observing during the 90-min hold")
    observe_body = ""
    if "observeUntilDeadline" in host_text:
        observe_body = host_text.split("observeUntilDeadline", 1)[1]
    if "result.ok" not in observe_body:
        errors.append("observeUntilDeadline must check scene.read result.ok (McpStdioExecutor does not throw)")
    if "consecutive observe" not in observe_body and "failedTicks" not in observe_body:
        errors.append("consecutive failed observe ticks must fail the hold")
    session_text = (HOST / "src" / "session.ts").read_text(encoding="utf-8")
    if 'phase !== "observing"' not in session_text:
        errors.append("assertRunnable deadline must not kill the observe pump")
    if 'executor?: "mcp-stdio" | "fake"' not in session_text and 'executor: "mcp-stdio" | "fake"' not in session_text:
        errors.append("HostState must have a dedicated executor field")
    compact_body = ""
    if "export function compactState" in session_text:
        compact_body = session_text.split("export function compactState", 1)[1].split("export function", 1)[0]
    if "state.executor" not in compact_body:
        errors.append("compactState must copy the dedicated executor field")
    if r"\bexecutor=(mcp-stdio|fake)\b" in compact_body:
        errors.append("compactState must not invent executor from a context_summary token")
    if "last_observe_ok_at" not in host_text:
        errors.append("host must persist last successful observe scene.read time")
    if "observeHasPayload" not in host_text:
        errors.append("host must require a real scene.read after payload, not ACK husk")
    if 'typeof rec.path === "string" && rec.path.length > 0' in host_text:
        errors.append("observeHasPayload must not accept a nonempty path + empty tree")
    if "stampHostExecutor" not in host_text:
        errors.append("Host must stamp a dedicated executor field, not instanceof at create")
    create_body = host_text.split("static create(", 1)[1].split("static resume(", 1)[0] if "static create(" in host_text else ""
    if 'stampHostExecutor("mcp-stdio")' in create_body or 'executor = "mcp-stdio"' in create_body:
        errors.append("Host.create must not stamp mcp-stdio before waitForPlugin")
    wait_body = ""
    if "private async waitForPlugin" in host_text:
        wait_body = host_text.split("private async waitForPlugin", 1)[1].split(
            "private async observeUntilDeadline", 1
        )[0]
    if 'stampHostExecutor("mcp-stdio")' not in wait_body:
        errors.append("waitForPlugin success must stamp HostState.executor=mcp-stdio")
    if "writeReportFile" not in observe_body:
        errors.append("observeUntilDeadline must write report.json for a 5400s kill")
    if "this.executorKind()" in host_text:
        errors.append("report.executor must not use instanceof executorKind")
    if 'this.state.executor === "mcp-stdio"' not in host_text:
        errors.append("report.executor must read the dedicated HostState field")
    persist_body = ""
    if "private persist():" in host_text:
        persist_body = host_text.split("private persist():", 1)[1].split("private ", 1)[0]
    if "heartbeat_at" in persist_body or "last_observe_ok_at" in persist_body:
        errors.append("persist() must not refresh heartbeat_at / last_observe_ok_at on every write")
    follow = HOST / "src" / "providers" / "plan_follow.ts"
    if not follow.is_file():
        errors.append("missing plan_follow.ts deciding path")
    else:
        ftext = follow.read_text(encoding="utf-8")
        if "godot.job" not in ftext or '"plan"' not in ftext:
            errors.append("PlanFollowProvider must call job.plan")
        if ("class Fake" + "Provider") in ftext:
            errors.append("plan follow must not be a recorded playbook of the game")
        if "memoryBoardScript" in ftext:
            errors.append("src_scan must not require memoryBoardScript; delete the frozen dump")
        if "compilePlanScript" not in ftext and "compileGameScript" not in ftext:
            errors.append("plan follow must compile GDScript from the live job.plan DAG + brief")
        if "pair_bug" in ftext:
            errors.append("pair_bug toggle of a frozen game is forbidden")
        if "patchFromFailEvidence" in ftext:
            errors.append("answer-key patchFromFailEvidence is forbidden")
        if re.search(r"if same:\s*\n\t\tpass\b", ftext) or "if same:\\n\\t\\tpass" in ftext:
            errors.append("planted if same: pass hole is forbidden")
        if "flipSequence" in ftext:
            errors.append("flipSequence Host pair-walk oracle is forbidden")
        if "genericCellPairs" in ftext:
            errors.append("genericCellPairs Host pair-walk oracle is forbidden")
        if "pathToIndex" in ftext:
            errors.append("pathToIndex Host pair-walk oracle is forbidden")
        if "pairIndices(spec.tiles" in ftext:
            errors.append("pairIndices(spec.tiles closed-loop oracle is forbidden")
        if "function playObserveTurns" in ftext:
            play_fn = ftext.split("function playObserveTurns", 1)[1].split("class DagWalker", 1)[0]
            if "ui_accept" not in play_fn:
                errors.append("playObserveTurns must screenshot after ui_accept, not a cursor nudge")
            if "acceptActionsFromTiles" in play_fn or "spec.tiles" in play_fn:
                errors.append("playObserveTurns must not click spec.tiles / acceptActionsFromTiles")
        if "acceptActionsFromTiles" in ftext:
            errors.append("acceptActionsFromTiles Host pair-walk oracle is forbidden")
        if "live ColorRect" not in ftext and "faces" not in ftext:
            errors.append("play must discover pairs from live ColorRect faces")
        if "ASSET_TEST_NAME" in ftext:
            errors.append("ASSET_TEST_NAME tripwire is forbidden")
        if "asset_ok = FileAccess" in ftext:
            errors.append("asset_ok = FileAccess tripwire is forbidden")
        if "plannedArtAssert" in ftext or "planned_art" in ftext or "PlannedArt" in ftext:
            errors.append("planned_art / PlannedArt Host inject is forbidden")
        if 'actionId === "asset.import" && !this.didPause' in ftext:
            errors.append("must not sandwich pause around asset.import")
        if "ctx.last_results" not in ftext:
            errors.append("DagWalker.next must read ctx.last_results")
        if 'tool("godot.test", "repair"' not in ftext:
            errors.append("plan follow must emit godot.test repair after a failing test.run")
        if "verifyQueue" in ftext:
            errors.append("DagWalker must not inject verifyQueue to paper over test-before-make")
        if "playCaptureTurns" in ftext:
            errors.append("DagWalker must not inject playCaptureTurns as a win-sequence oracle")
        if 'assert_key: "ready_ok"' in ftext or "assert_key: 'ready_ok'" in ftext:
            errors.append("plan follow must not hardcode ready_ok theater asserts")
        if re.search(r"if \(/\\bwon\\b/[\s\S]{0,120}return undefined", ftext):
            errors.append("must not compile brief won lines out to undefined")
        if re.search(r"if \(/\\bmatch/[\s\S]{0,120}return undefined", ftext):
            errors.append("must not compile brief match lines out to undefined")
        if 'key: "matches"' not in ftext:
            errors.append("assertFromAcceptance must define matches from the brief")
        if "isQueuedAssert" not in ftext:
            errors.append("plan follow must share one queue gate for define and run")
        if "Still define those keys" in ftext:
            errors.append("must not define matches/won while skipping their test.run")
        if "peek_a" in ftext:
            errors.append("mismatch must hide before the next Host observe (no peek_a stay-visible)")
        if "Do not read properties.tiles" not in ftext:
            errors.append("play must not read properties.tiles / board.gd / spec.tiles")
        if "not flips-only" not in self_text:
            errors.append("TEST_GREEN must require defined flips+matches+won, not flips-only")
        if "matches>=2 AND won" not in self_text and "matches >= 2 AND won" not in self_text:
            errors.append("TEST_GREEN must require one-run matches>=2 AND won")
        if ("and not walk_" + "plays_produced_board") in self_text:
            errors.append("walk_plays_produced_board must not whitelist Host pair-walk tapes")
        if "assert_node_path" not in ftext:
            errors.append("plan follow test.define must assert the scene root, not Fixture")
        if (
            'actionId === "test.run" || actionId === "git.checkpoint" || actionId === "script.patch"'
            in ftext
        ):
            errors.append("plan follow must not skip DAG test.run / script.patch / git.checkpoint")
        if re.search(r"function buildQueue\(", ftext) and re.search(
            r'actionId === "test\.run".{0,120}continue', ftext, re.S
        ):
            errors.append("buildQueue must not continue past test.run")
        if 'tool("godot.test", "run"' not in ftext:
            errors.append("plan follow must emit test.run from the DAG")
        if "git.checkpoint" not in ftext:
            errors.append("plan follow must not skip DAG git.checkpoint")
        if ftext.count('tool("godot.runtime", "screenshot"') < 2:
            errors.append("plan follow must capture 2 screenshots at different ticks")
    g4_blob = ""
    if "G4_NEED = (" in self_text:
        g4_blob = self_text.split("G4_NEED = (", 1)[1].split(")", 1)[0]
    if "REVIEW_PKG" not in g4_blob:
        errors.append("G4_NEED must include REVIEW_PKG")
    fixture_game = [
        p.name
        for p in BRIEF_FIXTURE.parent.rglob("*")
        if p.suffix in {".tscn", ".gd"} and "addons" not in p.parts
    ]
    if fixture_game:
        errors.append(f"r7w6 fixture must not pre-place board.tscn/board.gd: {fixture_game[:8]}")
    if "memoryBoardScript" in self_text and "Do not require memoryBoardScript" not in self_text:
        errors.append("official harness must not require memoryBoardScript")
    if "ready_ok-only" not in self_text:
        errors.append("official harness must refuse ready_ok-only TEST_GREEN")
    if "fail then patch then pass" not in self_text and "fail then pass" not in self_text:
        errors.append("official harness must require REPAIR fail then pass")
    if "unused" not in self_text or "maybeQueueRepair" not in self_text:
        errors.append("official harness must allow REPAIR unused when capable and nothing failed")
    if "defined-but-unrun" not in self_text:
        errors.append("unused stamp must require zero defined-but-unrun keys")
    if "G4_NEED treats proven OR unused" not in self_text:
        errors.append("G4_NEED must treat REPAIR proven OR unused as satisfied")
    if "different ticks" not in self_text:
        errors.append("official harness must require 2 screenshots at different ticks")
    if "hash-different" not in self_text:
        errors.append("official harness must require hash-different VIDEO frames")
    if "after ui_accept" not in self_text:
        errors.append("official harness must require VIDEO frames after ui_accept")
    if "between the two screenshot ACKs" not in self_text:
        errors.append("VIDEO must bind flips/got to the interval between the two screenshot ACKs")
    if "this session's screenshot ACKs" not in self_text:
        errors.append("VIDEO must count PNGs from this session's screenshot ACKs")
    if "later test.run" not in self_text:
        errors.append("VIDEO must not use a later test.run as the only board-change proof")
    if "first-hash 2160f75bd0b2 alone" not in self_text:
        errors.append("VIDEO must not ban first-hash 2160f75bd0b2 alone")
    if "second distinct accept" not in self_text:
        errors.append("VIDEO must require shot B after a second distinct accept or matches>=1 / flips>=2")
    if ('rglob("' + '*.png")') in self_text or ("rglob('" + "*.png')") in self_text:
        errors.append("VIDEO must not count leftover .hh-agent PNG piles")
    if ("tools[" + "acc_idx:]") in self_text:
        errors.append("host_flips_after_accept must not walk past the second screenshot ACK")
    if "steps_are_host_pair_walk" not in self_text:
        errors.append("official harness must refuse Host pair-walk TEST_GREEN tapes")
    if "walk_is_produced_oracle" not in self_text:
        errors.append("official harness must fail a tape that is the produced-board oracle")
    if "play_stream_is_pair_walk" not in self_text:
        errors.append("pair-walk detectors must inspect the godot.input press stream")
    if not steps_are_host_pair_walk(["ui_accept", "ui_down", "ui_accept"]):
        errors.append("steps_are_host_pair_walk must catch the short one-pair tape")
    if steps_are_host_pair_walk(["ui_accept"]):
        errors.append("steps_are_host_pair_walk must not flag a single ui_accept")
    if "walk_is_produced_oracle" not in self_text:
        errors.append("official harness must fail a tape that is the produced-board oracle")
    errors.extend(pair_walk_self_check())
    if "video_pair_after_accept" not in self_text:
        errors.append("critic must require hash-different VIDEO frames after ui_accept")
    if "PLANT_NUDGE_HASHES" not in self_text:
        errors.append("critic must refuse the plant-era cursor-nudge VIDEO pair")
    if "name-contains-movie" not in self_text:
        errors.append("VIDEO must refuse movie_ok name-contains-movie alone")
    if "cursor highlight" not in self_text:
        errors.append("VIDEO must refuse cursor highlight as the only change")
    if "tile area" not in self_text:
        errors.append("VIDEO must read PNG region/mean on the tile area")
    if "flips>=1" not in self_text or "got on flips" not in self_text:
        errors.append("VIDEO must require Host/runtime flips>=1 or got on flips")
    if re.search(r"labels\[\"VIDEO\"\].*movie_ok|movie_ok or \(", self_text):
        errors.append("VIDEO must not stamp on movie_ok name-contains-movie alone")
    errors.extend(video_rule_self_check())
    if "after green" not in self_text:
        errors.append("official harness must require a commit after green")
    if "between pause" not in self_text and "between pause and resume" not in self_text:
        errors.append("official harness must require work between pause and resume or later work")
    if "HH_ZERO_TOUCH_FAST must not prove DURATION90/G4_READY" not in self_text:
        errors.append("HH_ZERO_TOUCH_FAST must not prove DURATION90/G4_READY")
    if 'state.get("executor") == "mcp-stdio"' not in self_text:
        errors.append("HOST scorer must require state.executor == mcp-stdio")
    if 'report.get("executor") == "mcp-stdio"' not in self_text:
        errors.append("HOST scorer must require report.executor == mcp-stdio")
    if ('"executor=' + 'mcp-stdio" in str(state.get("context_summary")') in self_text:
        errors.append("HOST must not be proven from a context_summary substring")
    if "HOST refused: FakeExecutor play/test" not in self_text:
        errors.append("HOST must refuse scored play/test tools with source fake-executor")
    if "FAST must not exit early because report.json exists" not in self_text:
        errors.append("FAST must not exit early because report.json exists")
    if ("or (host_dir(session_id) / " + '"report.json").is_file()') in self_text:
        errors.append("FAST must not treat report.json as a done signal")
    if ".zero_touch_official.log" not in self_text:
        errors.append("official must write a durable .zero_touch_official.log")
    if ".zero_touch_fast.log" not in self_text:
        errors.append("FAST must write a FAST/debug log, not the official log")
    if "fast=0" not in self_text:
        errors.append("official verdict must include fast=0")
    if "wipe_official_fast_decoy" not in self_text:
        errors.append("official log must wipe leftover FAST PASS")
    if ("if sidecar_pid and not" + " pid_alive") in self_text:
        errors.append("sidecar_pid==0 must not skip liveness")
    if ("if live_up or labels" + '["LIVE"]') in self_text:
        errors.append("must not re-prove LIVE from job.plan when live_up is false")
    if "CREATE_BREAKAWAY_FROM_JOB" not in self_text or "CREATE_NEW_PROCESS_GROUP" not in self_text:
        errors.append("official must detach from the controlling TTY/job")
    if not PRODUCT_RUNTIME.is_file():
        errors.append("missing addons/hh_agent/runtime/hh_agent_runtime.gd")
    if not BRIEF_FIXTURE.is_file():
        errors.append("missing r7w6 tileflip PROJECT_BRIEF.md")
    else:
        brief = BRIEF_FIXTURE.read_text(encoding="utf-8").lower()
        if ("kho" + "-bi-an/") in brief or ("res://" + "snake") in brief or "r7w1_briefs" in brief:
            errors.append("r7w6 brief must not reuse dogfood / demo / R7-WP1 corpus trees")
        if "memory" not in brief and "tile" not in brief:
            errors.append("r7w6 brief must be the new one-screen memory/tile-flip task")
        if "1280x720" not in brief:
            errors.append("r7w6 brief must pin 1280x720")
        if "keyboard" not in brief:
            errors.append("r7w6 brief must be keyboard")
    compiler = (BRIDGE / "src" / "planner" / "brief_compiler.ts").read_text(encoding="utf-8")
    if 'slug: "memory"' not in compiler:
        errors.append("brief_compiler must emit a memory produceSpec (not topdown fallback)")
    adapter = (ADDON / "core" / "hh_plan_adapter.gd").read_text(encoding="utf-8")
    if "scenes/memory/board.tscn" not in adapter:
        errors.append("plugin job.plan must emit memory board paths (live compile is GDScript)")
    constants = (ADDON / "core" / "hh_constants.gd").read_text(encoding="utf-8")
    if "r7w6" not in constants:
        errors.append("hh_constants must name r7w6")
    if not (HOST / "src" / "mcp_child.ts").is_file():
        errors.append("missing host mcp_child.ts")
    runtime_text = PRODUCT_RUNTIME.read_text(encoding="utf-8") if PRODUCT_RUNTIME.is_file() else ""
    if "TYPE_PACKED_INT32_ARRAY" not in runtime_text:
        errors.append("_jsonable must type-only PackedInt32Array (no tile values)")
    if "_is_answer_map_name" not in runtime_text:
        errors.append("runtime.node must omit tiles/revealed answer-map properties")
    for path in (HOST / "src").rglob("*.ts"):
        blob = path.read_text(encoding="utf-8", errors="replace")
        posix = rel(path)
        for needle in VENDOR_NEEDLES:
            if needle in blob:
                errors.append(f"{posix} contains vendor needle {needle!r}")
                break
        if ("kho" + "-bi-an") in blob or ("/snake/") in blob.replace("\\", "/"):
            errors.append(f"{posix} mentions R8/snake trees")
        if "patchFromFailEvidence" in blob:
            errors.append(f"{posix} still has answer-key patchFromFailEvidence")
        if "memoryBoardScript" in blob:
            errors.append(f"{posix} still has memoryBoardScript")
        if "pair_bug" in blob:
            errors.append(f"{posix} still has pair_bug")
        if re.search(r"if same:\s*\n\t\tpass\b", blob):
            errors.append(f"{posix} still has planted if same: pass")
        if "flipSequence" in blob:
            errors.append(f"{posix} still has flipSequence")
        if "genericCellPairs" in blob:
            errors.append(f"{posix} still has genericCellPairs")
        if "pathToIndex" in blob:
            errors.append(f"{posix} still has pathToIndex")
        if "pairIndices(spec.tiles" in blob:
            errors.append(f"{posix} still has pairIndices(spec.tiles")
        if "ASSET_TEST_NAME" in blob:
            errors.append(f"{posix} still has ASSET_TEST_NAME")
        if "asset_ok = FileAccess" in blob:
            errors.append(f"{posix} still has asset_ok = FileAccess")
        if "plannedArtAssert" in blob or "PlannedArt" in blob:
            errors.append(f"{posix} still has planned_art / PlannedArt Host inject")
    return errors


def trial_project_id(root: Path) -> str:
    text = str(root.resolve())
    if os.name == "nt" and len(text) >= 2 and text[1] == ":":
        text = text[0].upper() + text[1:]
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


class _Tee:
    def __init__(self, *streams: object) -> None:
        self.streams = streams

    def write(self, data: str) -> int:
        for stream in self.streams:
            write = getattr(stream, "write", None)
            if write is None:
                continue
            write(data)
            flush = getattr(stream, "flush", None)
            if flush is not None:
                flush()
        return len(data)

    def flush(self) -> None:
        for stream in self.streams:
            flush = getattr(stream, "flush", None)
            if flush is not None:
                flush()


def win_survive_flags(*, hide_window: bool) -> int:
    if os.name != "nt":
        return 0
    flags = CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB | DETACHED_PROCESS
    if hide_window:
        flags |= CREATE_NO_WINDOW
    return flags


def _stdio_file(path: Path) -> object:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("ab")
    _IO_HOLD.append(handle)
    return handle


def _ignore_console_close() -> None:
    global _CTRL_HANDLER
    if os.name != "nt":
        return
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handler_type = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_uint)

        def _handler(_ctrl: int) -> int:
            return 1

        _CTRL_HANDLER = handler_type(_handler)
        kernel32.SetConsoleCtrlHandler(_CTRL_HANDLER, True)
        kernel32.FreeConsole()
    except OSError:
        return


def official_is_fast_decoy(text: str) -> bool:
    if "fast=1" in text:
        return True
    if "PASS: zero-touch" in text and "fast=0" not in text:
        return True
    return False


def wipe_official_fast_decoy() -> None:
    if not OFFICIAL_LOG.is_file():
        return
    try:
        text = OFFICIAL_LOG.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    if not official_is_fast_decoy(text):
        return
    try:
        OFFICIAL_LOG.unlink()
    except OSError:
        try:
            OFFICIAL_LOG.write_text("", encoding="utf-8")
        except OSError:
            return


def attach_run_log() -> None:
    fast = os.environ.get("HH_ZERO_TOUCH_FAST") == "1"
    child = os.environ.get(OFFICIAL_CHILD_ENV) == "1"
    utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if fast:
        FAST_LOG.parent.mkdir(parents=True, exist_ok=True)
        log_f = FAST_LOG.open("a", encoding="utf-8")
        _IO_HOLD.append(log_f)
        sys.stdout = _Tee(sys.__stdout__, log_f)  # type: ignore[assignment]
        sys.stderr = _Tee(sys.__stderr__, log_f)  # type: ignore[assignment]
        print(
            f"zero-touch fast log start utc={utc} pid={os.getpid()} fast=1 "
            f"child={int(child)} argv={sys.argv!r}\n",
            end="",
            flush=True,
        )
        return
    if child:
        print(
            f"zero-touch official log start utc={utc} pid={os.getpid()} fast=0 "
            f"child=1 argv={sys.argv!r}\n",
            end="",
            flush=True,
        )
        _ignore_console_close()
        return
    wipe_official_fast_decoy()
    print(
        f"zero-touch official parent utc={utc} pid={os.getpid()} fast=0 child=0 "
        f"(tee spawn/heartbeat only; not a scorer)\n",
        end="",
        flush=True,
    )


def should_spawn_survivor() -> bool:
    if os.environ.get("HH_ZERO_TOUCH_FAST") == "1":
        return False
    if os.environ.get(OFFICIAL_CHILD_ENV) == "1":
        return False
    return True


def _relay_log(log_path: Path, pos: int) -> int:
    if not log_path.is_file():
        return pos
    try:
        with log_path.open("r", encoding="utf-8", errors="replace") as handle:
            handle.seek(pos)
            chunk = handle.read()
            new_pos = handle.tell()
    except OSError:
        return pos
    if chunk:
        sys.__stdout__.write(chunk)
        sys.__stdout__.flush()
    return new_pos


def _popen_official_child(env: dict[str, str], log_f: object, flags: int) -> subprocess.Popen[bytes]:
    kwargs: dict = {
        "cwd": str(REPO_ROOT),
        "env": env,
        "stdin": subprocess.DEVNULL,
        "stdout": log_f,
        "stderr": subprocess.STDOUT,
    }
    if os.name == "nt":
        kwargs["creationflags"] = flags
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen([sys.executable, "-u", str(Path(__file__).resolve()), *sys.argv[1:]], **kwargs)


def spawn_official_survivor() -> int:
    wipe_official_fast_decoy()
    env = os.environ.copy()
    env.pop("HH_ZERO_TOUCH_FAST", None)
    env[OFFICIAL_CHILD_ENV] = "1"
    flags = win_survive_flags(hide_window=True)
    OFFICIAL_LOG.parent.mkdir(parents=True, exist_ok=True)
    log_f = OFFICIAL_LOG.open("a", encoding="utf-8")
    _IO_HOLD.append(log_f)
    utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    log_f.write(
        f"zero-touch official parent spawn utc={utc} parent_pid={os.getpid()} fast=0\n"
    )
    log_f.flush()
    try:
        child = _popen_official_child(env, log_f, flags)
    except OSError:
        flags = flags & ~CREATE_BREAKAWAY_FROM_JOB
        try:
            child = _popen_official_child(env, log_f, flags)
        except OSError as exc:
            print(f"zero-touch: official detach spawn failed: {exc}", flush=True)
            return 1
    print(f"zero-touch: official child pid={child.pid} log={OFFICIAL_LOG} fast=0", flush=True)
    try:
        log_f.write(f"zero-touch official child pid={child.pid} fast=0\n")
        log_f.flush()
    except OSError:
        pass
    pos = OFFICIAL_LOG.stat().st_size if OFFICIAL_LOG.is_file() else 0
    while child.poll() is None:
        pos = _relay_log(OFFICIAL_LOG, pos)
        time.sleep(2.0)
    _relay_log(OFFICIAL_LOG, pos)
    return int(child.returncode or 0)


def kill_trial_holders() -> None:
    needle = "r7w6-tileflip"
    alt = "godot/trials/r7w6"
    if os.name == "nt":
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    "Get-CimInstance Win32_Process | "
                    "Where-Object { "
                    "($_.Name -match 'Godot' -or $_.Name -match '^node') -and "
                    "$_.CommandLine -and "
                    f"((($_.CommandLine -replace '\\\\','/') -match '{needle}') -or "
                    f"(($_.CommandLine -replace '\\\\','/') -match '{alt}')) "
                    "} | ForEach-Object { "
                    "Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue "
                    "}"
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
        return
    proc = subprocess.run(["ps", "-ax", "-o", "pid=,args="], capture_output=True, text=True, check=False)
    for line in (proc.stdout or "").splitlines():
        lower = line.lower().replace("\\", "/")
        if needle not in lower and alt not in lower:
            continue
        if "godot" in lower or "node" in lower:
            pid = line.strip().split(None, 1)[0]
            if pid.isdigit():
                subprocess.run(["kill", "-9", pid], capture_output=True, check=False)


def trial_busy() -> bool:
    needle = "r7w6-tileflip"
    if os.name == "nt":
        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    "Get-CimInstance Win32_Process | "
                    "Where-Object { $_.Name -match 'Godot' } | "
                    "Select-Object -ExpandProperty CommandLine"
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
        blob = ((proc.stdout or "") + (proc.stderr or "")).replace("\\", "/").lower()
        return needle in blob
    proc = subprocess.run(["ps", "-ax", "-o", "args="], capture_output=True, text=True, check=False)
    return needle in (proc.stdout or "").lower() and "godot" in (proc.stdout or "").lower()


def run_git(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [git_bin(), "-c", "core.autocrlf=false", "-c", "user.email=r7w6@local", "-c", "user.name=r7w6", "-C", str(repo), *args],
        cwd=str(repo),
        text=True,
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )


def scaffold_t0() -> list[str]:
    errors: list[str] = []
    if not BRIEF_FIXTURE.is_file():
        return ["missing brief fixture"]
    TRIAL.parent.mkdir(parents=True, exist_ok=True)
    if TRIAL.exists():
        wipe_dir(TRIAL)
    TRIAL.mkdir(parents=True, exist_ok=True)
    (TRIAL / "project.godot").write_text(PROJECT_GODOT, encoding="utf-8")
    (TRIAL / "PROJECT_BRIEF.md").write_text(BRIEF_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    (TRIAL / ".gitignore").write_text(TRIAL_GITIGNORE, encoding="utf-8")
    dest_addon = TRIAL / "addons" / "hh_agent"
    dest_addon.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ADDON, dest_addon)
    init = run_git(TRIAL, ["init"])
    if init.returncode != 0:
        errors.append(f"nested git init failed: {init.stderr}")
        return errors
    run_git(TRIAL, ["add", "PROJECT_BRIEF.md", "project.godot", ".gitignore"])
    commit = run_git(TRIAL, ["commit", "-m", "T0 scaffold: brief + project.godot"])
    if commit.returncode != 0:
        errors.append(f"T0 git commit failed: {commit.stderr}")
    leftover = [p.as_posix() for p in TRIAL.rglob("*") if p.suffix in {".tscn", ".gd"} and "addons" not in p.parts]
    if leftover:
        errors.append(f"T0 must not include game .tscn/.gd: {leftover[:8]}")
    if (TRIAL / "scenes" / "memory" / "board.tscn").is_file() or (TRIAL / "scripts" / "memory" / "board.gd").is_file():
        errors.append("T0 must refuse pre-placed board.tscn/board.gd")
    return errors


def start_godot(exe: Path, headless: bool) -> tuple[subprocess.Popen[bytes], list[str]]:
    env = os.environ.copy()
    env.pop("HH_AGENT_SELFTEST", None)
    env.pop("HH_AGENT_SELFTEST_OUT", None)
    args = [str(exe)]
    if headless:
        args.append("--headless")
    args.extend(["--editor", "--path", str(TRIAL)])
    log_f = _stdio_file(TRIAL / ".hh-agent" / "godot.stdio.log")
    kwargs: dict = {
        "cwd": str(REPO_ROOT),
        "stdout": log_f,
        "stderr": log_f,
        "stdin": subprocess.DEVNULL,
        "env": env,
    }
    if os.name == "nt":
        kwargs["creationflags"] = win_survive_flags(hide_window=headless)
    else:
        kwargs["start_new_session"] = True
    try:
        godot = subprocess.Popen(args, **kwargs)
    except OSError:
        if os.name != "nt":
            raise
        kwargs["creationflags"] = win_survive_flags(hide_window=headless) & ~CREATE_BREAKAWAY_FROM_JOB
        godot = subprocess.Popen(args, **kwargs)
    return godot, []


def import_trial(exe: Path) -> None:
    subprocess.run(
        [str(exe), "--headless", "--path", str(TRIAL), "--import"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )


def start_host(session_id: str, env: dict[str, str], fast: bool) -> subprocess.Popen[bytes]:
    args = [
        node(),
        str(HOST / "dist" / "main.js"),
        "--provider",
        "plan",
        "--mode",
        "persistent",
        "--mcp-project",
        str(TRIAL),
        "--brief",
        str(TRIAL / "PROJECT_BRIEF.md"),
        "--session-id",
        session_id,
        "--budget",
        "400",
    ]
    if fast:
        args.append("--fast")
    else:
        args.append("--hold-until-deadline")
    out_f = _stdio_file(host_dir(session_id) / "host.stdout.log")
    err_f = _stdio_file(host_dir(session_id) / "host.stderr.log")
    kwargs: dict = {
        "cwd": str(HOST),
        "stdin": subprocess.DEVNULL,
        "stdout": out_f,
        "stderr": err_f,
        "env": env,
    }
    if os.name == "nt":
        kwargs["creationflags"] = win_survive_flags(hide_window=True)
    else:
        kwargs["start_new_session"] = True
    try:
        return subprocess.Popen(args, **kwargs)
    except OSError:
        if os.name == "nt":
            kwargs["creationflags"] = win_survive_flags(hide_window=True) & ~CREATE_BREAKAWAY_FROM_JOB
            return subprocess.Popen(args, **kwargs)
        raise


def host_state(session_id: str) -> dict:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return {}
    path = Path(local) / "HHGodotAgent" / "hosts" / session_id / "state.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def host_dir(session_id: str) -> Path:
    local = os.environ.get("LOCALAPPDATA") or ""
    return Path(local) / "HHGodotAgent" / "hosts" / session_id


def last_json(stdout: str) -> dict:
    parsed: dict = {}
    for line in (stdout or "").splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
    return parsed


def after_of(result: dict) -> dict:
    after = result.get("after") if isinstance(result.get("after"), dict) else {}
    return after if isinstance(after, dict) else {}


def params_of(row: dict) -> dict:
    params = row.get("params") if isinstance(row.get("params"), dict) else {}
    return params if isinstance(params, dict) else {}


def defined_test_rows() -> list[dict]:
    rows: list[dict] = []
    for folder in (TRIAL / "r7w6", TRIAL / ".hh-agent" / "r6w6" / "manifests"):
        if not folder.is_dir():
            continue
        for path in folder.glob("*.hh-test.json"):
            try:
                body = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(body, dict):
                rows.append(body)
    return rows


def game_assert_keys(keys: list[str]) -> list[str]:
    out: list[str] = []
    for key in keys:
        low = key.lower()
        if low in {"won", "matches", "flips", "pair", "score"} or "match" in low or "won" in low or "flip" in low:
            out.append(key)
    return out


def res_to_trial(res: str) -> Path:
    rel_s = res.replace("res://", "").replace("\\", "/").lstrip("/")
    return TRIAL / Path(rel_s)


def live_game_paths(plan: dict) -> tuple[Path, Path]:
    scene = TRIAL / "scenes" / "memory" / "board.tscn"
    script = TRIAL / "scripts" / "memory" / "board.gd"
    tasks = plan.get("tasks") if isinstance(plan.get("tasks"), list) else []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        outs = [x for x in (task.get("outputs") or []) if isinstance(x, str)]
        if task.get("id") == "produce_scene" and outs:
            scene = res_to_trial(outs[0])
        if task.get("id") == "produce_script" and outs:
            script = res_to_trial(outs[0])
    if not scene.is_file():
        found = [p for p in TRIAL.glob("scenes/**/*.tscn") if "addons" not in p.parts]
        if found:
            scene = found[0]
    if not script.is_file():
        found = [p for p in TRIAL.glob("scripts/**/*.gd") if "addons" not in p.parts]
        if found:
            script = found[0]
    return scene, script


def blob_matches_and_won(blob: object) -> bool:
    """True only when one after-blob has matches>=2 AND won==true (no collage)."""
    if not isinstance(blob, dict):
        return False
    matches: int | None = None
    won: bool | None = None

    def take(node: object) -> None:
        nonlocal matches, won
        if not isinstance(node, dict):
            return
        raw_m = node.get("matches")
        if isinstance(raw_m, (int, float)) and raw_m >= 2:
            matches = int(raw_m)
        raw_w = node.get("won")
        if raw_w is True or raw_w == 1 or raw_w == "true":
            won = True
        for nested_key in ("observe", "state", "runtime", "after"):
            take(node.get(nested_key))

    take(blob)
    return matches is not None and matches >= 2 and won is True


def one_run_matches_and_won(tools: list[dict]) -> bool:
    for row in tools:
        result = row.get("result") if isinstance(row.get("result"), dict) else {}
        after = after_of(result)
        if blob_matches_and_won(after):
            return True
        if blob_matches_and_won(result):
            return True
    return False


def after_key_matched(after: dict, key: str) -> bool:
    got = after.get("got", after.get(key))
    if after.get("matched") is True and str(after.get("assert_key") or key) == key:
        if key == "won":
            return got is True or got == 1 or got == "true"
        if key in {"matches", "flips", "score", "pair"}:
            return (isinstance(got, (int, float)) and got >= 1) or got is True
        return True
    if key == "won":
        return got is True or got == 1 or got == "true"
    if key in {"matches", "flips", "score", "pair"}:
        return isinstance(got, (int, float)) and got >= 1
    return False


MUTATE_TOOLS = {
    ("godot.script", "write"),
    ("godot.script", "patch"),
    ("godot.script", "attach"),
    ("godot.scene", "create"),
    ("godot.scene", "save"),
    ("godot.node", "add"),
    ("godot.test", "run"),
    ("godot.test", "define"),
    ("godot.play", "start"),
}


def screenshot_ticks(after: dict) -> int:
    time_v = after.get("time") if isinstance(after.get("time"), dict) else {}
    for key in ("ticks_msec", "frames", "physics_frames"):
        raw = time_v.get(key, after.get(key))
        if isinstance(raw, (int, float)) and raw > 0:
            return int(raw)
    return 0


PLANT_NUDGE_HASHES = {"2160f75bd0b2", "e3181596b785"}
VIDEO_DIR_ACTIONS = {"ui_left", "ui_right", "ui_up", "ui_down", "left", "right", "up", "down"}
VIDEO_ACCEPT_ACTIONS = {"ui_accept", "accept"}
# ColorRect board from compileMemoryDraft (1280x720). Not editor chrome.
TILE_ORIGIN = (360, 200)
TILE_STRIDE = 140
TILE_SIZE = 120
TILE_COLS = 2
TILE_ROWS = 2
CHROME_TOP = 80
CURSOR_SAT_MAX = 0.18
FLIP_SAT_MIN = 0.25


def tool_action_name(row: dict) -> str:
    raw = params_of(row).get("action_name", params_of(row).get("action", ""))
    return str(raw or "").strip()


def steps_are_host_pair_walk(steps: object) -> bool:
    if not isinstance(steps, list):
        return False
    tokens = [str(s) for s in steps]
    accepts = sum(1 for s in tokens if s in VIDEO_ACCEPT_ACTIONS)
    dirs = sum(1 for s in tokens if s in VIDEO_DIR_ACTIONS)
    if tokens == ["ui_accept", "ui_down", "ui_accept"]:
        return True
    if accepts == 2 and dirs >= 1 and 3 <= len(tokens) <= 5:
        return True
    if len(tokens) >= 8 and accepts >= 4 and dirs >= 2 and accepts <= 4:
        return True
    return False


def oracle_accept_walk(tiles: list[int], cols: int, pair_limit: int | None = None) -> list[str]:
    by_kind: dict[int, list[int]] = {}
    for idx, kind in enumerate(tiles):
        by_kind.setdefault(kind, []).append(idx)
    limit = pair_limit if pair_limit is not None else len(by_kind)
    actions: list[str] = []
    cursor = 0
    pairs = 0
    for cells in by_kind.values():
        if len(cells) < 2 or pairs >= limit:
            continue
        a, b = cells[0], cells[1]
        ac, ar = a % cols, a // cols
        cc, cr = cursor % cols, cursor // cols
        dc, dr = ac - cc, ar - cr
        actions.extend(["ui_right" if dc > 0 else "ui_left"] * abs(dc))
        actions.extend(["ui_down" if dr > 0 else "ui_up"] * abs(dr))
        actions.append("ui_accept")
        cursor = a
        bc, br = b % cols, b // cols
        cc, cr = cursor % cols, cursor // cols
        dc, dr = bc - cc, br - cr
        actions.extend(["ui_right" if dc > 0 else "ui_left"] * abs(dc))
        actions.extend(["ui_down" if dr > 0 else "ui_up"] * abs(dr))
        actions.append("ui_accept")
        cursor = b
        pairs += 1
    return actions


def walk_is_produced_oracle(steps: object, script_text: str) -> bool:
    parsed = packed_tiles_from_script(script_text)
    if parsed is None or not isinstance(steps, list):
        return False
    tiles, cols = parsed
    tokens = [str(s) for s in steps]
    full = oracle_accept_walk(tiles, cols)
    one = oracle_accept_walk(tiles, cols, 1)
    return tokens == full or tokens == one


def input_press_names(tools: list[dict], start: int = -1, end: int | None = None) -> list[str]:
    lo = start + 1 if start >= 0 else 0
    hi = len(tools) if end is None else end
    names: list[str] = []
    for idx in range(lo, hi):
        if idx < 0 or idx >= len(tools):
            continue
        row = tools[idx]
        if row.get("tool") != "godot.input":
            continue
        result = row.get("result") if isinstance(row.get("result"), dict) else {}
        if result.get("ok") is not True:
            continue
        if str(params_of(row).get("phase") or "") == "release":
            continue
        name = tool_action_name(row)
        if name:
            names.append(name)
    return names


def play_stream_is_pair_walk(tools: list[dict], script_text: str) -> bool:
    presses = input_press_names(tools)
    return steps_are_host_pair_walk(presses) or walk_is_produced_oracle(presses, script_text)


def pair_walk_self_check() -> list[str]:
    errors: list[str] = []
    script = "var cols: int = 2\nvar tiles: PackedInt32Array = PackedInt32Array([1, 0, 1, 0])\n"
    hidden = [
        {
            "tool": "godot.test",
            "action": "define",
            "params": {"name": "flips_only", "assert_key": "flips", "steps": ["ui_accept"]},
            "result": {"ok": True},
        },
        {
            "tool": "godot.input",
            "action": "action",
            "params": {"action_name": "ui_accept", "phase": "press"},
            "result": {"ok": True},
        },
        {
            "tool": "godot.input",
            "action": "action",
            "params": {"action_name": "ui_down", "phase": "press"},
            "result": {"ok": True},
        },
        {
            "tool": "godot.input",
            "action": "action",
            "params": {"action_name": "ui_accept", "phase": "press"},
            "result": {"ok": True},
        },
    ]
    if not play_stream_is_pair_walk(hidden, script):
        errors.append("pair-walk detectors must see a packed walk in the godot.input press stream")
    memory = []
    for name in [
        "ui_accept",
        "ui_right",
        "ui_accept",
        "ui_left",
        "ui_down",
        "ui_accept",
        "ui_up",
        "ui_accept",
        "ui_right",
        "ui_accept",
        "ui_down",
        "ui_accept",
    ]:
        memory.append(
            {
                "tool": "godot.input",
                "action": "action",
                "params": {"action_name": name, "phase": "press"},
                "result": {"ok": True},
            }
        )
    if play_stream_is_pair_walk(memory, script):
        errors.append("pair-walk detectors must not flag a memory-play press stream")
    return errors


def packed_tiles_from_script(script_text: str) -> tuple[list[int], int] | None:
    match = re.search(r"PackedInt32Array\(\[([0-9,\s]*)\]\)", script_text)
    if not match:
        return None
    nums = [int(part) for part in match.group(1).split(",") if part.strip().isdigit()]
    cols_m = re.search(r"var cols:\s*int\s*=\s*(\d+)", script_text)
    cols = int(cols_m.group(1)) if cols_m else 2
    if not nums:
        return None
    return nums, cols


def walk_plays_produced_board(steps: object, script_text: str) -> bool:
    parsed = packed_tiles_from_script(script_text)
    if parsed is None or not isinstance(steps, list):
        return False
    tiles, cols = parsed
    cursor = 0
    first = -1
    matches = 0
    revealed = [0] * len(tiles)
    for raw in steps:
        token = str(raw)
        nxt = cursor
        if token in {"ui_left", "left"}:
            nxt = cursor - 1
        elif token in {"ui_right", "right"}:
            nxt = cursor + 1
        elif token in {"ui_up", "up"}:
            nxt = cursor - cols
        elif token in {"ui_down", "down"}:
            nxt = cursor + cols
        elif token in VIDEO_ACCEPT_ACTIONS:
            if cursor < 0 or cursor >= len(tiles) or revealed[cursor] == 1:
                continue
            revealed[cursor] = 1
            if first < 0:
                first = cursor
                continue
            if tiles[first] == tiles[cursor]:
                matches += 1
            else:
                revealed[first] = 0
                revealed[cursor] = 0
            first = -1
            continue
        if 0 <= nxt < len(tiles):
            cursor = nxt
    return matches >= 1


def video_input_names(tools: list[dict], start: int, end: int) -> list[str]:
    names: list[str] = []
    for idx in range(start + 1, end):
        if idx < 0 or idx >= len(tools):
            continue
        row = tools[idx]
        if row.get("tool") != "godot.input":
            continue
        result = row.get("result") if isinstance(row.get("result"), dict) else {}
        if result.get("ok") is not True:
            continue
        name = tool_action_name(row)
        if name:
            names.append(name)
    return names


def video_nudge_only(names: list[str]) -> bool:
    if not names:
        return True
    if any(n in VIDEO_ACCEPT_ACTIONS for n in names):
        return False
    return all(n in VIDEO_DIR_ACTIONS for n in names)


def video_row_is_accept(row: dict) -> bool:
    result = row.get("result") if isinstance(row.get("result"), dict) else {}
    if row.get("tool") == "godot.input":
        return tool_action_name(row) in VIDEO_ACCEPT_ACTIONS and result.get("ok") is True
    if row.get("tool") != "godot.test":
        return False
    params = params_of(row)
    after = after_of(result)
    steps = params.get("steps") or params.get("inputs") or after.get("steps") or after.get("inputs") or []
    if not isinstance(steps, list):
        return False
    return any(str(s) in VIDEO_ACCEPT_ACTIONS for s in steps)


def video_has_accept_between(tools: list[dict], start: int, end: int) -> bool:
    names = video_input_names(tools, start, end)
    if any(n in VIDEO_ACCEPT_ACTIONS for n in names) and not video_nudge_only(names):
        return True
    for idx in range(start + 1, end):
        if 0 <= idx < len(tools) and video_row_is_accept(tools[idx]):
            return True
    return False


def after_flips_count(after: dict) -> int | None:
    if not isinstance(after, dict):
        return None
    raw = after.get("flips")
    if isinstance(raw, (int, float)) and raw >= 1:
        return int(raw)
    if after_key_matched(after, "flips"):
        got = after.get("got", after.get("flips"))
        if isinstance(got, (int, float)):
            return int(got)
        return 1
    for key in ("observe", "state", "runtime"):
        nested = after.get(key)
        if isinstance(nested, dict):
            hit = after_flips_count(nested)
            if hit is not None:
                return hit
    return None


def after_matches_count(after: dict) -> int | None:
    if not isinstance(after, dict):
        return None
    raw = after.get("matches")
    if isinstance(raw, (int, float)) and raw >= 1:
        return int(raw)
    for key in ("observe", "state", "runtime"):
        nested = after.get(key)
        if isinstance(nested, dict):
            hit = after_matches_count(nested)
            if hit is not None:
                return hit
    return None


def video_shot_b_progress(tools: list[dict], start: int, end: int, after_b: dict) -> bool:
    presses = input_press_names(tools, start, end)
    if sum(1 for name in presses if name in VIDEO_ACCEPT_ACTIONS) >= 2:
        return True
    matches = after_matches_count(after_b)
    if matches is not None and matches >= 1:
        return True
    flips = after_flips_count(after_b)
    if flips is not None and flips >= 2:
        return True
    last = min(end, len(tools) - 1)
    for idx in range(start + 1, last + 1):
        row = tools[idx]
        result = row.get("result") if isinstance(row.get("result"), dict) else {}
        after = after_of(result)
        mid_m = after_matches_count(after)
        if mid_m is not None and mid_m >= 1:
            return True
        mid_f = after_flips_count(after)
        if mid_f is not None and mid_f >= 2:
            return True
    return False


def host_flips_after_accept(tools: list[dict], start: int, end: int) -> bool:
    acc_idx: int | None = None
    for idx in range(start + 1, min(end, len(tools))):
        if video_row_is_accept(tools[idx]):
            acc_idx = idx
            break
    if acc_idx is None:
        return False
    last = min(end, len(tools) - 1)
    if last < acc_idx:
        return False
    for idx in range(acc_idx, last + 1):
        row = tools[idx]
        result = row.get("result") if isinstance(row.get("result"), dict) else {}
        count = after_flips_count(after_of(result))
        if count is not None and count >= 1:
            return True
    return False


def session_screenshot_pngs(tools: list[dict]) -> list[Path]:
    found: list[Path] = []
    seen: set[str] = set()
    for row in tools:
        if row.get("tool") != "godot.runtime" or row.get("action") != "screenshot":
            continue
        result = row.get("result") if isinstance(row.get("result"), dict) else {}
        if result.get("ok") is not True:
            continue
        path = shot_disk_path(after_of(result))
        if path is None:
            continue
        try:
            key = str(path.resolve())
        except OSError:
            key = str(path)
        if key in seen:
            continue
        seen.add(key)
        found.append(path)
    return found


def shot_disk_path(after: dict) -> Path | None:
    if not isinstance(after, dict):
        return None
    for key in ("abs_path", "path"):
        raw = after.get(key)
        if not raw:
            continue
        text = str(raw)
        path = res_to_trial(text) if text.startswith("res://") else Path(text)
        try:
            if path.is_file() and path.stat().st_size >= 32:
                return path
        except OSError:
            continue
    return None


def _rgb_sat(rgb: tuple[float, float, float]) -> float:
    return max(rgb) - min(rgb)


def _png_region_mean(path: Path, x: int, y: int, w: int, h: int) -> tuple[float, float, float] | None:
    try:
        from PIL import Image
        from PIL import ImageStat
    except ImportError:
        return None
    try:
        with Image.open(path) as img:
            rgb = img.convert("RGB")
            x0 = max(0, min(int(x), rgb.width - 1))
            y0 = max(0, min(int(y), rgb.height - 1))
            x1 = max(x0 + 1, min(int(x + w), rgb.width))
            y1 = max(y0 + 1, min(int(y + h), rgb.height))
            crop = rgb.crop((x0, y0, x1, y1))
            mean = ImageStat.Stat(crop).mean
    except OSError:
        return None
    return float(mean[0]) / 255.0, float(mean[1]) / 255.0, float(mean[2]) / 255.0


def png_tile_cells(path: Path) -> list[tuple[float, float, float]] | None:
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        with Image.open(path) as img:
            width, height = img.size
    except OSError:
        return None
    sx = width / 1280.0
    sy = height / 720.0
    cells: list[tuple[float, float, float]] = []
    for row in range(TILE_ROWS):
        for col in range(TILE_COLS):
            x = TILE_ORIGIN[0] * sx + col * TILE_STRIDE * sx
            y = TILE_ORIGIN[1] * sy + row * TILE_STRIDE * sy
            mean = _png_region_mean(path, x, y, TILE_SIZE * sx, TILE_SIZE * sy)
            if mean is None:
                return None
            cells.append(mean)
    return cells


def png_cursor_highlight_only(path_a: Path, path_b: Path) -> bool:
    cells_a = png_tile_cells(path_a)
    cells_b = png_tile_cells(path_b)
    if not cells_a or not cells_b or len(cells_a) != len(cells_b):
        return False
    if any(_rgb_sat(c) >= FLIP_SAT_MIN for c in cells_a + cells_b):
        return False
    if any(_rgb_sat(c) > CURSOR_SAT_MAX for c in cells_a + cells_b):
        return False
    moved = False
    for ca, cb in zip(cells_a, cells_b):
        delta = sum(abs(ca[i] - cb[i]) for i in range(3)) / 3.0
        if delta >= 0.04:
            moved = True
    return moved


def png_tile_area_changed(path_a: Path, path_b: Path) -> bool:
    cells_a = png_tile_cells(path_a)
    cells_b = png_tile_cells(path_b)
    if not cells_a or not cells_b:
        return False
    if png_cursor_highlight_only(path_a, path_b):
        return False
    for ca, cb in zip(cells_a, cells_b):
        if _rgb_sat(ca) < FLIP_SAT_MIN and _rgb_sat(cb) >= FLIP_SAT_MIN:
            return True
        if _rgb_sat(cb) < FLIP_SAT_MIN and _rgb_sat(ca) >= FLIP_SAT_MIN:
            return True
    try:
        from PIL import Image
    except ImportError:
        return False
    try:
        with Image.open(path_a) as img:
            width, height = img.size
    except OSError:
        return False
    sx = width / 1280.0
    sy = height / 720.0
    tw = (TILE_COLS * TILE_STRIDE - (TILE_STRIDE - TILE_SIZE)) * sx
    th = (TILE_ROWS * TILE_STRIDE - (TILE_STRIDE - TILE_SIZE)) * sy
    tile_a = _png_region_mean(path_a, TILE_ORIGIN[0] * sx, TILE_ORIGIN[1] * sy, tw, th)
    tile_b = _png_region_mean(path_b, TILE_ORIGIN[0] * sx, TILE_ORIGIN[1] * sy, tw, th)
    chrome_a = _png_region_mean(path_a, 0, 0, width, CHROME_TOP * sy)
    chrome_b = _png_region_mean(path_b, 0, 0, width, CHROME_TOP * sy)
    if tile_a is None or tile_b is None:
        return False
    tile_delta = sum(abs(tile_a[i] - tile_b[i]) for i in range(3)) / 3.0
    chrome_delta = 0.0
    if chrome_a is not None and chrome_b is not None:
        chrome_delta = sum(abs(chrome_a[i] - chrome_b[i]) for i in range(3)) / 3.0
    if chrome_delta > tile_delta and tile_delta < 0.02:
        return False
    return tile_delta >= 0.03


def video_pair_after_accept(tools: list[dict], shot_rows: list[tuple[int, str]]) -> bool:
    for i, (ia, ha) in enumerate(shot_rows):
        for ib, hb in shot_rows[i + 1 :]:
            if ha == hb:
                continue
            if {ha[:12], hb[:12]} == PLANT_NUDGE_HASHES:
                continue
            if not video_has_accept_between(tools, ia, ib):
                continue
            after_a = after_of((tools[ia].get("result") if isinstance(tools[ia].get("result"), dict) else {}))
            after_b = after_of((tools[ib].get("result") if isinstance(tools[ib].get("result"), dict) else {}))
            path_a = shot_disk_path(after_a)
            path_b = shot_disk_path(after_b)
            cursor_only = bool(path_a and path_b and png_cursor_highlight_only(path_a, path_b))
            if cursor_only:
                continue
            tick_a = screenshot_ticks(after_a)
            tick_b = screenshot_ticks(after_b)
            if tick_a and tick_b and tick_a == tick_b:
                continue
            if not video_shot_b_progress(tools, ia, ib, after_b):
                continue
            png_ok = bool(path_a and path_b and png_tile_area_changed(path_a, path_b))
            if png_ok:
                return True
    return False


def _synth_board_png(path: Path, cursor: int, revealed: list[int]) -> None:
    from PIL import Image
    from PIL import ImageDraw

    img = Image.new("RGB", (1280, 720), (76, 76, 76))
    draw = ImageDraw.Draw(img)
    for index in range(TILE_COLS * TILE_ROWS):
        col = index % TILE_COLS
        row = index // TILE_COLS
        x = TILE_ORIGIN[0] + col * TILE_STRIDE
        y = TILE_ORIGIN[1] + row * TILE_STRIDE
        if index < len(revealed) and revealed[index] == 1:
            color = (229, 153, 51)
        elif index == cursor:
            color = (89, 89, 115)
        else:
            color = (38, 38, 51)
        draw.rectangle([x, y, x + TILE_SIZE - 1, y + TILE_SIZE - 1], fill=color)
    img.save(path)


def video_rule_self_check() -> list[str]:
    errors: list[str] = []
    plant_tools = [
        {
            "tool": "godot.runtime",
            "action": "screenshot",
            "result": {"ok": True, "after": {"hash": "2160f75bd0b2aaaa"}},
        },
        {
            "tool": "godot.input",
            "action": "action",
            "params": {"action_name": "ui_accept"},
            "result": {"ok": True},
        },
        {
            "tool": "godot.runtime",
            "action": "screenshot",
            "result": {"ok": True, "after": {"hash": "e3181596b785bbbb", "flips": 1}},
        },
    ]
    if video_pair_after_accept(plant_tools, [(0, "2160f75bd0b2aaaa"), (2, "e3181596b785bbbb")]):
        errors.append("VIDEO must refuse the plant pair {2160f75bd0b2, e3181596b785}")
    movie_only = [
        {"tool": "godot.runtime", "action": "write-movie", "result": {"ok": True, "after": {"name": "movie_ok"}}},
    ]
    if video_pair_after_accept(movie_only, []):
        errors.append("VIDEO must not stamp on movie_ok name-contains-movie alone")
    late_run_tools = [
        {
            "tool": "godot.runtime",
            "action": "screenshot",
            "result": {"ok": True, "after": {"hash": "aaa111aaa111"}},
        },
        {
            "tool": "godot.input",
            "action": "action",
            "params": {"action_name": "ui_accept"},
            "result": {"ok": True},
        },
        {
            "tool": "godot.runtime",
            "action": "screenshot",
            "result": {"ok": True, "after": {"hash": "bbb222bbb222"}},
        },
        {
            "tool": "godot.test",
            "action": "run",
            "params": {"name": "keyboard_cursor_plus_accept_flips_a_tile", "steps": ["ui_accept"]},
            "result": {"ok": True, "after": {"assert_key": "flips", "flips": 1, "got": 1, "matched": True, "status": "pass"}},
        },
    ]
    if host_flips_after_accept(late_run_tools, 0, 2) or video_pair_after_accept(
        late_run_tools, [(0, "aaa111aaa111"), (2, "bbb222bbb222")]
    ):
        errors.append("VIDEO must not use a later test.run flips>=1 when ACK paths are missing")
    good_tools = [
        {
            "tool": "godot.play",
            "action": "start",
            "result": {"ok": True},
        },
        {
            "tool": "godot.runtime",
            "action": "screenshot",
            "result": {"ok": True, "after": {"hash": "aaa111aaa111"}},
        },
        {
            "tool": "godot.input",
            "action": "action",
            "params": {"action_name": "ui_accept"},
            "result": {"ok": True},
        },
        {
            "tool": "godot.runtime",
            "action": "screenshot",
            "result": {"ok": True, "after": {"hash": "bbb222bbb222", "flips": 1}},
        },
    ]
    if video_pair_after_accept(good_tools, [(1, "aaa111aaa111"), (3, "bbb222bbb222")]):
        errors.append("VIDEO must not stamp hash-different frames without tile-area PNG change")
    bless_pair = [
        {
            "tool": "godot.runtime",
            "action": "screenshot",
            "result": {"ok": True, "after": {"hash": "2160f75bd0b2cccc"}},
        },
        {
            "tool": "godot.input",
            "action": "action",
            "params": {"action_name": "ui_accept"},
            "result": {"ok": True},
        },
        {
            "tool": "godot.runtime",
            "action": "screenshot",
            "result": {"ok": True, "after": {"hash": "51799480eff2dddd", "flips": 1}},
        },
    ]
    if video_pair_after_accept(bless_pair, [(0, "2160f75bd0b2cccc"), (2, "51799480eff2dddd")]):
        errors.append("VIDEO must not hardcode-allow {2160f75bd0b2, 51799480eff2}")
    mid_flips_tools = [
        {
            "tool": "godot.runtime",
            "action": "screenshot",
            "result": {"ok": True, "after": {"hash": "ccc111ccc111"}},
        },
        {
            "tool": "godot.input",
            "action": "action",
            "params": {"action_name": "ui_accept"},
            "result": {"ok": True},
        },
        {
            "tool": "godot.runtime",
            "action": "tree",
            "result": {"ok": True, "after": {"flips": 1, "got": 1}},
        },
        {
            "tool": "godot.runtime",
            "action": "screenshot",
            "result": {"ok": True, "after": {"hash": "ddd222ddd222"}},
        },
    ]
    if not host_flips_after_accept(mid_flips_tools, 0, 3):
        errors.append("VIDEO must count flips immediately after accept before shot B")
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        errors.append("VIDEO PNG tile-area check needs Pillow")
        return errors
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        cursor_a = root / "cursor_a.png"
        cursor_b = root / "cursor_b.png"
        flip_b = root / "flip_b.png"
        _synth_board_png(cursor_a, 0, [0, 0, 0, 0])
        _synth_board_png(cursor_b, 1, [0, 0, 0, 0])
        _synth_board_png(flip_b, 0, [1, 0, 0, 0])
        if not png_cursor_highlight_only(cursor_a, cursor_b):
            errors.append("VIDEO must treat cursor highlight as the only PNG change")
        if png_tile_area_changed(cursor_a, cursor_b):
            errors.append("VIDEO must refuse cursor-chrome-only tile-area change")
        if not png_tile_area_changed(cursor_a, flip_b):
            errors.append("VIDEO must see PNG region/mean change on the tile area after a flip")
        cursor_tools = [
            {
                "tool": "godot.runtime",
                "action": "screenshot",
                "result": {"ok": True, "after": {"hash": "ccc333ccc333", "abs_path": str(cursor_a)}},
            },
            {
                "tool": "godot.input",
                "action": "action",
                "params": {"action_name": "ui_accept"},
                "result": {"ok": True},
            },
            {
                "tool": "godot.runtime",
                "action": "screenshot",
                "result": {"ok": True, "after": {"hash": "ddd444ddd444", "abs_path": str(cursor_b), "flips": 1}},
            },
        ]
        if video_pair_after_accept(cursor_tools, [(0, "ccc333ccc333"), (2, "ddd444ddd444")]):
            errors.append("VIDEO must refuse a pair whose only change is cursor highlight")
        flip_tools = [
            {
                "tool": "godot.runtime",
                "action": "screenshot",
                "result": {"ok": True, "after": {"hash": "eee555eee555", "abs_path": str(cursor_a)}},
            },
            {
                "tool": "godot.input",
                "action": "action",
                "params": {"action_name": "ui_accept", "phase": "press"},
                "result": {"ok": True},
            },
            {
                "tool": "godot.input",
                "action": "action",
                "params": {"action_name": "ui_accept", "phase": "press"},
                "result": {"ok": True},
            },
            {
                "tool": "godot.runtime",
                "action": "screenshot",
                "result": {"ok": True, "after": {"hash": "fff666fff666", "abs_path": str(flip_b), "flips": 2, "matches": 1}},
            },
        ]
        if not video_pair_after_accept(flip_tools, [(0, "eee555eee555"), (3, "fff666fff666")]):
            errors.append("VIDEO must stamp a hash-different accept pair with tile-area flip")
        first_hash_png = [
            {
                "tool": "godot.runtime",
                "action": "screenshot",
                "result": {"ok": True, "after": {"hash": "2160f75bd0b2cccc", "abs_path": str(cursor_a)}},
            },
            {
                "tool": "godot.input",
                "action": "action",
                "params": {"action_name": "ui_accept", "phase": "press"},
                "result": {"ok": True},
            },
            {
                "tool": "godot.input",
                "action": "action",
                "params": {"action_name": "ui_accept", "phase": "press"},
                "result": {"ok": True},
            },
            {
                "tool": "godot.runtime",
                "action": "screenshot",
                "result": {"ok": True, "after": {"hash": "ab12cd34ef56aaaa", "abs_path": str(flip_b), "flips": 2}},
            },
        ]
        if not video_pair_after_accept(first_hash_png, [(0, "2160f75bd0b2cccc"), (3, "ab12cd34ef56aaaa")]):
            errors.append("VIDEO must not refuse first-hash 2160f75bd0b2 alone")
        first_flip_only = [
            {
                "tool": "godot.runtime",
                "action": "screenshot",
                "result": {"ok": True, "after": {"hash": "2160f75bd0b2cccc", "abs_path": str(cursor_a)}},
            },
            {
                "tool": "godot.input",
                "action": "action",
                "params": {"action_name": "ui_accept", "phase": "press"},
                "result": {"ok": True},
            },
            {
                "tool": "godot.runtime",
                "action": "screenshot",
                "result": {"ok": True, "after": {"hash": "51799480eff2dddd", "abs_path": str(flip_b), "flips": 1}},
            },
        ]
        if video_pair_after_accept(first_flip_only, [(0, "2160f75bd0b2cccc"), (2, "51799480eff2dddd")]):
            errors.append("VIDEO must not stamp only the first flip")
        no_path_acks = [
            {
                "tool": "godot.runtime",
                "action": "screenshot",
                "result": {"ok": True, "after": {"hash": "pileaaa111111"}},
            },
            {
                "tool": "godot.runtime",
                "action": "screenshot",
                "result": {"ok": True, "after": {"hash": "pilebbb222222"}},
            },
        ]
        if session_screenshot_pngs(no_path_acks):
            errors.append("VIDEO must not count leftover .hh-agent PNG piles")
        session_acks = [
            {
                "tool": "godot.runtime",
                "action": "screenshot",
                "result": {"ok": True, "after": {"hash": "sessaaa111111", "abs_path": str(cursor_a)}},
            },
            {
                "tool": "godot.runtime",
                "action": "screenshot",
                "result": {"ok": True, "after": {"hash": "sessbbb222222", "abs_path": str(flip_b)}},
            },
        ]
        if len(session_screenshot_pngs(session_acks)) != 2:
            errors.append("VIDEO must count this session's screenshot ACK abs_path")
    return errors


def acceptance_texts(plan: dict) -> list[str]:
    texts: list[str] = []
    for item in plan.get("acceptance") or []:
        if isinstance(item, dict) and isinstance(item.get("text"), str):
            texts.append(item["text"])
        elif isinstance(item, str):
            texts.append(item)
    for task in plan.get("tasks") or []:
        if not isinstance(task, dict):
            continue
        crit = task.get("criterion")
        if isinstance(crit, str) and crit.strip():
            texts.append(crit)
        for acc in task.get("acceptance") or []:
            if isinstance(acc, str) and acc.strip() and not acc.startswith("acc"):
                texts.append(acc)
    return texts


def tools_of(state: dict) -> list[dict]:
    rows = state.get("tools") if isinstance(state.get("tools"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        proc = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
        return str(pid) in (proc.stdout or "")
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def processes_up(godot: subprocess.Popen[bytes] | None, host: subprocess.Popen[bytes] | None, sidecar_pid: int) -> bool:
    if godot is None or godot.poll() is not None:
        return False
    if host is None or host.poll() is not None:
        return False
    if sidecar_pid <= 0 or not pid_alive(sidecar_pid):
        return False
    return True


def observe_ok_age_s(state: dict) -> float:
    raw = state.get("last_observe_ok_at")
    if not isinstance(raw, (int, float)) or raw <= 0:
        return -1.0
    return (time.time() * 1000.0 - float(raw)) / 1000.0


def repair_capable() -> bool:
    follow = HOST / "src" / "providers" / "plan_follow.ts"
    if not follow.is_file():
        return False
    text = follow.read_text(encoding="utf-8")
    if "maybeQueueRepair" not in text:
        return False
    if 'tool("godot.test", "repair"' not in text:
        return False
    if "pair_bug" in text or "planned_art" in text or "asset_ok" in text:
        return False
    if "if same:\\n\\t\\tpass" in text or re.search(r"if same:\s*\n\t\tpass\b", text):
        return False
    return True


def g4_need_ok(labels: dict[str, str]) -> bool:
    for key in G4_NEED:
        if key == "REPAIR" and labels.get(key) in {"proven", "unused"}:
            continue
        if labels.get(key) != "proven":
            return False
    return True


def critic(
    state: dict,
    report: dict,
    skip_wait: bool,
    elapsed: float,
    live_up: bool,
    live_label: str = "unproven",
    extra: dict | None = None,
) -> tuple[list[str], dict[str, str]]:
    labels = {key: "unproven" for key in LABELS}
    if live_label in {"proven", "plugin"}:
        labels["LIVE"] = "proven"
    errors: list[str] = []
    extra = extra if isinstance(extra, dict) else {}
    tools = tools_of(state) or tools_of(report)
    if report.get("executor") == "mcp-stdio" or state.get("executor") == "mcp-stdio":
        fake_mutate = False
        fake_play_test = False
        for row in tools:
            result = row.get("result") if isinstance(row.get("result"), dict) else {}
            after = after_of(result)
            if after.get("source") != "fake-executor":
                continue
            tool = str(row.get("tool") or "")
            action = str(row.get("action") or "")
            if action in {"add", "create", "write", "attach"}:
                fake_mutate = True
            if tool in {"godot.play", "godot.test"}:
                fake_play_test = True
        if fake_mutate:
            errors.append("HOST refused: FakeExecutor mutate ACK")
        elif fake_play_test:
            errors.append("HOST refused: FakeExecutor play/test")
        else:
            labels["HOST"] = "proven"
    else:
        errors.append("HOST unproven: Host.create did not use McpStdioExecutor")

    plan_after: dict = {}
    for row in tools:
        if row.get("tool") == "godot.job" and row.get("action") == "plan":
            result = row.get("result") if isinstance(row.get("result"), dict) else {}
            if result.get("ok") is True:
                plan_after = after_of(result)
    plan = plan_after.get("plan") if isinstance(plan_after.get("plan"), dict) else {}
    tasks = plan.get("tasks") if isinstance(plan.get("tasks"), list) else []
    outputs: list[str] = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        for item in task.get("outputs") or []:
            if isinstance(item, str):
                outputs.append(item)
    acc_texts = acceptance_texts(plan)
    tasks_have_acc = False
    for task in tasks:
        if isinstance(task, dict) and any(isinstance(x, str) and x.strip() for x in (task.get("acceptance") or [])):
            tasks_have_acc = True
            break
    script_text = ""
    live_scene, live_script = live_game_paths(plan)
    if live_script.is_file():
        script_text = live_script.read_text(encoding="utf-8", errors="replace")
    used_acc = False
    for text in acc_texts:
        low = text.lower()
        if "match" in low and "matches" in script_text:
            used_acc = True
        if ("won" in low or "win" in low) and "won" in script_text:
            used_acc = True
        if "flip" in low and "flips" in script_text:
            used_acc = True
        if "score" in low and "score" in script_text:
            used_acc = True
    define_keys: list[str] = []
    define_nodes: list[str] = []
    for row in tools:
        if row.get("tool") == "godot.test" and row.get("action") == "define":
            params = params_of(row)
            if isinstance(params.get("assert_key"), str):
                define_keys.append(params["assert_key"])
            if isinstance(params.get("assert_node_path"), str):
                define_nodes.append(params["assert_node_path"])
    for body in defined_test_rows():
        if isinstance(body.get("assert_key"), str):
            define_keys.append(body["assert_key"])
        if isinstance(body.get("assert_node_path"), str):
            define_nodes.append(body["assert_node_path"])
    if (
        plan_after
        and tasks
        and tasks_have_acc
        and acc_texts
        and used_acc
        and game_assert_keys(define_keys)
        and not any("overworld" in o for o in outputs)
    ):
        labels["SELF_PLAN"] = "proven"
    else:
        errors.append(
            f"SELF_PLAN needs job.plan ok + acceptance used by test/script, "
            f"outputs={outputs[:6]} acc={acc_texts[:3]} keys={define_keys[:6]}"
        )

    def has_ok(tool: str, action: str) -> bool:
        for row in tools:
            if row.get("tool") != tool or row.get("action") != action:
                continue
            result = row.get("result") if isinstance(row.get("result"), dict) else {}
            if result.get("ok") is True:
                return True
        return False

    runtime_src = ""
    for row in tools:
        if row.get("tool") == "godot.runtime" and row.get("action") == "tree":
            result = row.get("result") if isinstance(row.get("result"), dict) else {}
            runtime_src = str(after_of(result).get("source") or runtime_src)
    if has_ok("godot.play", "start") and runtime_src == "hh_agent_runtime":
        labels["SELF_PLAY"] = "proven"
    else:
        errors.append(f"SELF_PLAY needs play.start + hh_agent_runtime, source={runtime_src!r}")

    patch_idx: int | None = None
    fail_before = False
    pass_after = False
    repair_kind = ""
    canned_repair = False
    banned_repair = {
        "patch",
        "golden",
        "golden_patch",
        "exact_fix",
        "fix_map",
        "patch_map",
        "contents",
        "bug_id",
        "find",
        "replace",
    }
    for idx, row in enumerate(tools):
        if row.get("tool") != "godot.test" or row.get("action") != "repair":
            continue
        result = row.get("result") if isinstance(row.get("result"), dict) else {}
        params = params_of(row)
        if banned_repair & set(params):
            canned_repair = True
            continue
        if result.get("ok") is True and patch_idx is None:
            patch_idx = idx
            repair_kind = str(after_of(result).get("kind") or "")
    for idx, row in enumerate(tools):
        if row.get("tool") != "godot.test" or row.get("action") != "run":
            continue
        result = row.get("result") if isinstance(row.get("result"), dict) else {}
        after = after_of(result)
        failed = result.get("ok") is not True or after.get("status") == "fail"
        passed = result.get("ok") is True and after.get("status") != "fail"
        if failed and (patch_idx is None or idx < patch_idx):
            fail_before = True
        if passed and patch_idx is not None and idx > patch_idx:
            pass_after = True
    if fail_before and pass_after and patch_idx is not None and not canned_repair:
        labels["REPAIR"] = "proven"
    else:
        errors.append(
            f"REPAIR needs fail then godot.test repair then pass "
            f"(fail then pass; not Host increment) "
            f"or unused when capable and nothing failed "
            f"(fail_before={fail_before} patch_idx={patch_idx} pass_after={pass_after} "
            f"kind={repair_kind!r} canned={canned_repair} capable={repair_capable()})"
        )

    pause_idx = None
    resume_idx = None
    for idx, row in enumerate(tools):
        result = row.get("result") if isinstance(row.get("result"), dict) else {}
        if result.get("ok") is not True:
            continue
        if row.get("tool") in {"hh.pause", "godot.editor"} and row.get("action") == "pause":
            if pause_idx is None:
                pause_idx = idx
        if row.get("tool") == "hh.resume" and row.get("action") == "resume":
            if resume_idx is None:
                resume_idx = idx
    between_pause = False
    later_work = False
    if pause_idx is not None and resume_idx is not None:
        for idx, row in enumerate(tools):
            pair = (str(row.get("tool") or ""), str(row.get("action") or ""))
            if pair not in MUTATE_TOOLS:
                continue
            result = row.get("result") if isinstance(row.get("result"), dict) else {}
            if result.get("ok") is not True:
                continue
            if pause_idx < idx < resume_idx:
                between_pause = True
            if idx > resume_idx:
                later_work = True
    if pause_idx is not None and resume_idx is not None and (between_pause or later_work):
        labels["PAUSE_RESUME"] = "proven"
    else:
        errors.append(
            "PAUSE_RESUME needs hh.pause/editor.pause ACK and a distinct hh.resume "
            "with a mutating tool between pause and resume, or resume then later work"
        )

    git_ok = has_ok("godot.git", "checkpoint")
    log = run_git(TRIAL, ["log", "--oneline"])
    commits = [ln for ln in (log.stdout or "").splitlines() if ln.strip()]
    ckpt_after_pass = False
    for idx, row in enumerate(tools):
        if row.get("tool") != "godot.git" or row.get("action") != "checkpoint":
            continue
        result = row.get("result") if isinstance(row.get("result"), dict) else {}
        if result.get("ok") is not True:
            continue
        if any(
            i < idx
            and r.get("tool") == "godot.test"
            and r.get("action") == "run"
            and isinstance(r.get("result"), dict)
            and r["result"].get("ok") is True
            and after_of(r["result"]).get("status") != "fail"
            for i, r in enumerate(tools)
        ):
            ckpt_after_pass = True
    if git_ok and (TRIAL / ".git").exists() and len(commits) >= 2 and ckpt_after_pass:
        labels["CHECKPOINT/GIT"] = "proven"
    else:
        errors.append(
            f"CHECKPOINT/GIT nested git commits={len(commits)} checkpoint_ok={git_ok} "
            f"after_pass={ckpt_after_pass} "
            "(need count >= 2 and a checkpoint after a green test.run; "
            "do not stamp because params.message says after green)"
        )

    local = os.environ.get("LOCALAPPDATA") or ""
    ledger = Path(local) / "HHGodotAgent" / "projects" / trial_project_id(TRIAL) / "ledger.sqlite"
    ledger_rows = 0
    if ledger.is_file():
        try:
            con = sqlite3.connect(str(ledger))
            ledger_rows = int(con.execute("SELECT COUNT(*) FROM commands").fetchone()[0])
            con.close()
        except sqlite3.Error:
            try:
                con = sqlite3.connect(str(ledger))
                tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
                if tables:
                    ledger_rows = int(con.execute(f"SELECT COUNT(*) FROM {tables[0]}").fetchone()[0])
                con.close()
            except sqlite3.Error:
                ledger_rows = 0
    if ledger.is_file() and ledger_rows > 0:
        labels["LEDGER"] = "proven"
    else:
        errors.append(f"LEDGER missing LocalAppData sqlite rows path={ledger}")

    if has_ok("godot.observer", "timeline"):
        labels["TIMELINE"] = "proven"
    else:
        errors.append("TIMELINE needs observer.timeline ACK")

    session_png = session_screenshot_pngs(tools)
    shot_acks = 0
    ticks: list[int] = []
    hashes: list[str] = []
    shot_idxs: list[int] = []
    shot_rows: list[tuple[int, str]] = []
    play_start_idx = None
    for idx, row in enumerate(tools):
        result = row.get("result") if isinstance(row.get("result"), dict) else {}
        if row.get("tool") == "godot.play" and row.get("action") == "start" and result.get("ok") is True:
            if play_start_idx is None:
                play_start_idx = idx
        if row.get("tool") != "godot.runtime" or row.get("action") != "screenshot":
            continue
        if result.get("ok") is not True:
            continue
        shot_acks += 1
        shot_idxs.append(idx)
        after = after_of(result)
        tick = screenshot_ticks(after)
        if tick:
            ticks.append(tick)
        digest = after.get("hash")
        if isinstance(digest, str) and digest:
            hashes.append(digest)
            shot_rows.append((idx, digest))
    during_play = play_start_idx is not None and any(i > play_start_idx for i in shot_idxs)
    after_accept = video_pair_after_accept(tools, shot_rows)
    plant_nudge = {h[:12] for h in hashes} == PLANT_NUDGE_HASHES
    tick_distinct = len(set(ticks)) >= 2 or (len(ticks) < 2 and len(set(hashes)) >= 2)
    if SCREENSHOTS == "SKIP":
        errors.append("screenshots=SKIP must not stamp VIDEO=proven")
    elif (
        len(session_png) >= 2
        and shot_acks >= 2
        and after_accept
        and during_play
        and tick_distinct
        and not plant_nudge
    ):
        labels["VIDEO"] = "proven"
    else:
        errors.append(
            f"VIDEO needs two tick-distinct hash-different screenshot ACKs with ui_accept "
            f"(or play test accept) plus tile-area PNG change "
            f"(png={len(session_png)} acks={shot_acks} ticks={ticks[:4]} hashes={len(set(hashes))} "
            f"during_play={during_play} after_accept={after_accept} tick_distinct={tick_distinct} "
            f"plant_nudge={plant_nudge}; name-contains-movie alone is not enough)"
        )

    card = TRIAL / ".hh-agent" / "review" / "card.json"
    if card.is_file() or has_ok("godot.review", "write_card"):
        labels["REVIEW_PKG"] = "proven"
    else:
        errors.append("REVIEW_PKG needs review.write_card / card.json")

    asks = host_dir(str(state.get("session_id") or report.get("session_id") or "")) / "asks.jsonl"
    if asks.is_file():
        bad = False
        for line in asks.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and row.get("e_gate") is False and str(row.get("code") or "") not in {"LOG", ""}:
                if "missing brief" in str(row.get("message") or ""):
                    bad = True
        if not bad:
            labels["E_INPUT"] = "proven"
        else:
            errors.append("E_INPUT: non-E1–E4 ask stopped the run")
    else:
        errors.append(f"E_INPUT needs ask log at {asks}")

    if live_scene.is_file() and live_script.is_file() and has_ok("godot.play", "start"):
        labels["OUTPUT_RUNS"] = "proven"
    else:
        errors.append(f"OUTPUT_RUNS scene={live_scene.is_file()} script={live_script.is_file()}")

    ready_only = bool(define_keys) and all(key == "ready_ok" for key in define_keys)
    fixture_assert = any(node == "Fixture" for node in define_nodes)
    game_keys = game_assert_keys(define_keys)
    defined_names: list[str] = []
    defined_by_name: dict[str, str] = {}
    pair_walk_tape = play_stream_is_pair_walk(tools, script_text)
    for row in tools:
        if row.get("tool") == "godot.test" and row.get("action") == "define":
            params = params_of(row)
            name = params.get("name")
            key = params.get("assert_key")
            steps = params.get("steps") or params.get("inputs")
            if steps_are_host_pair_walk(steps) or walk_is_produced_oracle(steps, script_text):
                pair_walk_tape = True
            if isinstance(name, str) and isinstance(key, str) and key in game_keys:
                defined_names.append(name)
                defined_by_name[name] = key
    for body in defined_test_rows():
        name = body.get("name")
        key = body.get("assert_key")
        body_steps = body.get("steps") or body.get("inputs")
        if steps_are_host_pair_walk(body_steps) or walk_is_produced_oracle(body_steps, script_text):
            pair_walk_tape = True
        if isinstance(name, str) and isinstance(key, str) and key in game_assert_keys([key]):
            if name not in defined_by_name:
                defined_names.append(name)
                defined_by_name[name] = key
    passed_after: dict[str, dict] = {}
    ran_names: set[str] = set()
    for _idx, row in enumerate(tools):
        if row.get("tool") != "godot.test" or row.get("action") != "run":
            continue
        result = row.get("result") if isinstance(row.get("result"), dict) else {}
        after = after_of(result)
        name = str(after.get("name") or params_of(row).get("name") or "")
        if name:
            ran_names.add(name)
        key = defined_by_name.get(name) or str(after.get("assert_key") or "")
        passed = result.get("ok") is True and after.get("status") != "fail"
        if passed and key and after_key_matched(after, key):
            passed_after[name or key] = after
    keys_needed = set(defined_by_name.values())
    keys_passed = set()
    for name, after in passed_after.items():
        key = defined_by_name.get(name) or str(after.get("assert_key") or "")
        if key:
            keys_passed.add(key)
    all_defined_green = bool(keys_needed) and keys_needed <= keys_passed
    defined_unrun = [name for name in defined_names if name not in ran_names]
    one_run = one_run_matches_and_won(tools)
    if (
        one_run
        and game_keys
        and not ready_only
        and not fixture_assert
        and not pair_walk_tape
    ):
        labels["TEST_GREEN"] = "proven"
    else:
        errors.append(
            f"TEST_GREEN needs one-run matches>=2 AND won==true on the same after-blob, "
            f"not ready_ok-only / Fixture / pair-walk tape / flips-only / collage "
            f"(keys={define_keys[:6]} passed={list(passed_after)[:6]} ready_only={ready_only} "
            f"fixture={fixture_assert} pair_walk={pair_walk_tape} "
            f"one_run={one_run} collage={all_defined_green and not one_run})"
        )

    if (
        labels.get("REPAIR") != "proven"
        and not fail_before
        and patch_idx is None
        and not canned_repair
        and repair_capable()
        and labels.get("TEST_GREEN") == "proven"
        and all_defined_green
        and not defined_unrun
    ):
        labels["REPAIR"] = "unused"
        errors[:] = [item for item in errors if not str(item).startswith("REPAIR needs")]
    elif labels.get("REPAIR") not in {"proven", "unused"} and not fail_before and patch_idx is None:
        errors.append(
            f"REPAIR unused needs all_defined_green and zero defined-but-unrun keys "
            f"(all_defined_green={all_defined_green} defined-but-unrun={defined_unrun[:6]})"
        )

    observe_age = observe_ok_age_s(state)
    sidecar_pid = extra.get("sidecar_pid")
    sidecar_ok = isinstance(sidecar_pid, int) and sidecar_pid > 0
    if (
        not skip_wait
        and elapsed >= ZERO_TOUCH_WALL_SEC
        and live_up
        and sidecar_ok
        and 0 <= observe_age <= OBSERVE_STALE_SEC
    ):
        labels["DURATION90"] = "proven"
    elif skip_wait:
        labels["DURATION90"] = "unproven"
    else:
        errors.append(
            f"DURATION90 live_wall={elapsed:.1f}s live_up={live_up} skip_wait={skip_wait} "
            f"observe_age={observe_age:.1f}s sidecar_pid={sidecar_pid} "
            "(HH_ZERO_TOUCH_FAST must not prove DURATION90)"
        )

    t0_ok = (TRIAL / "PROJECT_BRIEF.md").is_file() and (TRIAL / "project.godot").is_file()
    t0_game = extra.get("t0_game_files") if isinstance(extra.get("t0_game_files"), list) else []
    t0_stamp = float(extra.get("t0_stamp") or 0.0)
    writers_ok = has_ok("godot.scene", "create") and has_ok("godot.script", "write")
    after_t0 = True
    if t0_stamp > 0:
        for path in (live_scene, live_script):
            if path.is_file() and path.stat().st_mtime + 1 < t0_stamp:
                after_t0 = False
    if t0_ok and not t0_game and writers_ok and live_scene.is_file() and live_script.is_file() and after_t0:
        labels["ZERO_TOUCH"] = "proven"
    else:
        errors.append(
            f"ZERO_TOUCH needs T0 brief+project.godot+addon only and after-T0 "
            f"Godot/sidecar/Host writers (t0_game={t0_game} writers={writers_ok} after_t0={after_t0})"
        )

    if g4_need_ok(labels):
        labels["G4_READY"] = "proven"
    elif skip_wait:
        labels["G4_READY"] = "unproven"
    else:
        errors.append(
            "G4_READY stamp only; missing "
            + ",".join(
                k
                for k in G4_NEED
                if not (k == "REPAIR" and labels.get(k) in {"proven", "unused"})
                and labels.get(k) != "proven"
            )
        )
    return errors, labels


def live_errors(exe: Path | None) -> tuple[list[str], dict[str, str]]:
    labels = {key: "unrun" if key == "LIVE" else "unproven" for key in LABELS}
    errors: list[str] = []
    if exe is None:
        errors.append("pinned Godot required for LIVE zero-touch")
        return errors, labels
    kill_trial_holders()
    time.sleep(1.0)
    if trial_busy():
        errors.append("LIVE_UNRUN: Godot already open on r7w6 trial (no second instance)")
        return errors, labels
    errors.extend(scaffold_t0())
    if errors:
        return errors, labels
    t0_stamp = time.time()
    t0_game_files = [
        p.as_posix()
        for p in TRIAL.rglob("*")
        if p.suffix in {".tscn", ".gd"} and "addons" not in p.parts
    ]
    skip_wait = os.environ.get("HH_ZERO_TOUCH_FAST") == "1"
    session_id = life.new_ulid()
    env = os.environ.copy()
    env.pop("HH_AGENT_SELFTEST", None)
    if skip_wait:
        env["HH_ZERO_TOUCH_FAST"] = "1"
    proc_host: subprocess.Popen[bytes] | None = None
    godot: subprocess.Popen[bytes] | None = None
    host_err: list[str] = []
    t0 = 0.0
    report: dict = {}
    try:
        import_trial(exe)
        godot, _glines = start_godot(exe, headless=False)
        time.sleep(4.0)
        if godot.poll() is not None:
            godot, _glines = start_godot(exe, headless=True)
        proc_host = start_host(session_id, env, skip_wait)
        host_out: list[str] = []
        t0 = time.time()
        deadline_hello = time.time() + 180.0
        state: dict = {}
        while time.time() < deadline_hello:
            state = host_state(session_id)
            if any(
                row.get("tool") == "godot.job" and row.get("action") == "plan" for row in tools_of(state)
            ):
                break
            if proc_host.poll() is not None:
                break
            time.sleep(1.0)
        if godot.poll() is None and proc_host.poll() is None:
            labels["LIVE"] = "proven"
        else:
            err_path = host_dir(session_id) / "host.stderr.log"
            out_path = host_dir(session_id) / "host.stdout.log"
            try:
                err_txt = err_path.read_text(encoding="utf-8", errors="replace") if err_path.is_file() else "".join(host_err)
            except OSError:
                err_txt = "".join(host_err)
            try:
                out = out_path.read_text(encoding="utf-8", errors="replace") if out_path.is_file() else ""
            except OSError:
                out = ""
            errors.append(
                f"live host/godot died before job.plan host_rc={proc_host.poll()} "
                f"godot_rc={godot.poll()} stderr={err_txt[-1500:]} stdout={out[-800:]}"
            )
            return errors, labels

        sidecar_pid = 0
        mcp_pid_file = host_dir(session_id) / "mcp.pid"

        def read_sidecar_pid() -> int:
            if not mcp_pid_file.is_file():
                return 0
            try:
                return int(mcp_pid_file.read_text(encoding="utf-8").strip() or "0")
            except ValueError:
                return 0

        sidecar_pid = read_sidecar_pid()

        if not skip_wait:
            print(
                f"zero-touch official identity utc={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} "
                f"pid={os.getpid()} fast=0 session={session_id}",
                flush=True,
            )
        tick = 0
        while True:
            elapsed = time.time() - t0
            state = host_state(session_id)
            if skip_wait:
                # FAST must not exit early because report.json exists
                # (official observe writes that file during hold; FAST already
                # writes report at done).
                if state.get("phase") == "done":
                    break
                if proc_host.poll() is not None or (godot is not None and godot.poll() is not None):
                    break
                if elapsed > 480:
                    break
                tick += 1
                if tick % 4 == 0:
                    print(
                        f"zero-touch: tick={tick} elapsed={elapsed:.1f}s tools={len(tools_of(state))} "
                        f"phase={state.get('phase')} sidecar_pid={sidecar_pid}",
                        flush=True,
                    )
                time.sleep(2.0)
                continue
            if sidecar_pid <= 0:
                sidecar_pid = read_sidecar_pid()
            if not processes_up(godot, proc_host, sidecar_pid):
                errors.append("live sidecar+Godot+host died before DURATION90")
                break
            tick += 1
            observe_age = observe_ok_age_s(state)
            if tick % 4 == 0:
                hb = state.get("heartbeat_at")
                age = (time.time() * 1000 - float(hb)) / 1000 if isinstance(hb, (int, float)) else -1
                print(
                    f"zero-touch: tick={tick} elapsed={elapsed:.1f}s tools={len(tools_of(state))} "
                    f"phase={state.get('phase')} heartbeat_age={age:.1f}s "
                    f"observe_age={observe_age:.1f}s sidecar_pid={sidecar_pid}",
                    flush=True,
                )
            if str(state.get("phase") or "") == "observing":
                hb = state.get("heartbeat_at")
                hb_age = (time.time() * 1000 - float(hb)) / 1000 if isinstance(hb, (int, float)) else -1
                stale = observe_age > OBSERVE_STALE_SEC or (
                    observe_age < 0 and (hb_age < 0 or hb_age > OBSERVE_STALE_SEC)
                )
                if stale:
                    errors.append(
                        f"observe scene.read heartbeat went stale observe_age={observe_age:.1f}s "
                        f"heartbeat_age={hb_age:.1f}s elapsed={elapsed:.1f}s (not print-only)"
                    )
                    break
            if elapsed >= ZERO_TOUCH_WALL_SEC:
                break
            time.sleep(30.0)

        elapsed = time.time() - t0
        if proc_host.poll() is None and skip_wait:
            try:
                proc_host.wait(timeout=300)
            except subprocess.TimeoutExpired:
                pass
        report_path = host_dir(session_id) / "report.json"
        if report_path.is_file():
            try:
                loaded = json.loads(report_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    report = loaded
            except (OSError, json.JSONDecodeError):
                report = {}
        if not report:
            report = last_json("".join(host_out))
        state = host_state(session_id)
        live_up = processes_up(godot, proc_host if proc_host.poll() is None else None, sidecar_pid)
        if skip_wait:
            live_up = labels["LIVE"] in {"proven", "plugin"}
        crit_errs, crit_labels = critic(
            state,
            report,
            skip_wait,
            elapsed,
            live_up and not skip_wait,
            labels["LIVE"],
            {
                "t0_stamp": t0_stamp,
                "t0_game_files": t0_game_files,
                "godot_pid": godot.pid if godot is not None else 0,
                "host_pid": proc_host.pid if proc_host is not None else 0,
                "sidecar_pid": sidecar_pid,
            },
        )
        labels.update(crit_labels)
        if skip_wait:
            if labels["LIVE"] in {"proven", "plugin"}:
                labels["LIVE"] = "proven"
        elif live_up:
            labels["LIVE"] = "proven"
        else:
            labels["LIVE"] = "unproven"
            errors.append("LIVE revoked: processes or MCP observe not alive at score time")
        errors.extend(crit_errs)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"zero-touch live failed: {type(exc).__name__}: {exc}")
    finally:
        if proc_host is not None and proc_host.poll() is None:
            proc_host.terminate()
            try:
                proc_host.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc_host.kill()
        if godot is not None:
            life.stop_proc(godot)
        kill_trial_holders()
    return errors, labels


def main() -> int:
    attach_run_log()
    if should_spawn_survivor():
        return spawn_official_survivor()
    errors: list[str] = []
    errors.extend(hh_agent_only_addon_errors(PLUGIN_PROJECT, REPO_ROOT))
    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.is_file() else None
    if plan_text is None:
        errors.append(f"missing {rel(PLAN)}")
    else:
        errors.extend(plan_errors(plan_text))
        if re.search(r"G4 AUTONOMY\s+\[x\]", plan_text):
            errors.append("official harness must not tick G4")
    errors.extend(src_scan_errors())

    for pkg in (BRIDGE, HOST):
        build = subprocess.run(
            [npm(), "run", "build"],
            cwd=str(pkg),
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
        if build.returncode != 0:
            errors.append(f"{rel(pkg)} build failed: {build.stderr[-800:]}")

    catalog = json.loads(ACTIONS_JSON.read_text(encoding="utf-8")) if ACTIONS_JSON.is_file() else {}
    actions = catalog.get("actions") if isinstance(catalog.get("actions"), dict) else {}
    if "job.plan" not in actions:
        errors.append("actions.json missing job.plan")

    exe, pin_reason = plug.find_pinned_godot()
    if exe is None:
        errors.append(f"pinned Godot required: {pin_reason}")
    else:
        version = plug.godot_version(exe)
        if version != PINNED_VERSION:
            errors.append(f"Godot --version {version!r} != {PINNED_VERSION}")

    live_errs, labels = live_errors(exe)
    errors.extend(live_errs)
    if labels["LIVE"] not in {"proven", "plugin"}:
        errors.append("LIVE path through plugin (Godot+sidecar+Host MCP) is required (src_scan is not enough)")
    skip_wait = os.environ.get("HH_ZERO_TOUCH_FAST") == "1"
    for key in LABELS:
        if skip_wait and key in {"DURATION90", "G4_READY"}:
            if labels[key] == "proven":
                errors.append(f"{key} must stay unproven under HH_ZERO_TOUCH_FAST")
            continue
        if key == "LIVE" and labels[key] == "plugin":
            continue
        if key == "REPAIR" and labels[key] == "unused":
            continue
        if labels[key] != "proven":
            errors.append(f"{key} not proven")
    banner = "; ".join(f"{key}={labels[key]}" for key in LABELS)
    fast_flag = 1 if skip_wait else 0
    if errors:
        print(f"FAIL: zero-touch; fast={fast_flag}; {banner}")
        for item in errors:
            print(f"  - {item}")
        return 1
    print(f"PASS: zero-touch; fast={fast_flag}; {banner}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
