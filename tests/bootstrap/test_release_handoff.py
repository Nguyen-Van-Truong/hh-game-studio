#!/usr/bin/env python3
"""R9-WP4: release gate G6 operations handoff — disaster drill + runbook.

Does not tick the 20-8 plan. Does not change CURRENT_VALID_WP.
Keep R9-WP4 [ ]; CURRENT_VALID_WP=R9-WP4; progress stays 59/60.
Does not start Superfighter. Does not tick G6 or GX.
Does not invent an API key. --provider plan stays.
Does not poke relic_reached. Does not regress kho-bi-an or R9-WP1/WP2/WP3 honesty.
No snake demo. No r7w6 trial. No secret material. No skip-PASS.
Does not invent Hyper-V. Does not stamp CLEAN_VM=proven on this Godot/Node machine.

Official verify (plan R9-WP4 Verify, Godot §7.3 sequential):
  kill leftover Godot first
  disaster drill + fresh reviewer follow runbook
  all gates/artifacts resolve
  CLEAN_VM stays unproven; this Godot/Node machine is not a clean VM.
  not_g6=1
  unsigned internal only; sign/upload/publish is E3
  do not copy the exe into a folder named clean-vm

Honest PASS (P1): do not stamp GATES=proven while G6 is unresolved.
Do not stamp REVIEWER=proven from the same PID / same argv.
Do not stamp DRILL=proven for mkdir+copytree+planted bytes (only a live
Godot/sidecar kill + recover would prove DRILL).
Do not stamp EVIDENCE=proven for heading-only markdown.
RUNBOOK may be proven when the runbook files are real.
leftover session tokens must be 0. backup must not ship raw tokens.
rotate-token --live must target the live leftover path.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

PLAN = REPO_ROOT / "zdocs" / "20-8-godot-agent-autopilot-plan.txt"
DOGFOOD = REPO_ROOT / "godot" / "dogfood" / "kho-bi-an"
PLUGIN_PROJECT = REPO_ROOT / "godot" / "plugin-project"
MINIMAL = REPO_ROOT / "godot" / "test-projects" / "minimal-2d"
TOOLS = REPO_ROOT / "tools" / "godot"
OPS_PY = TOOLS / "ops.py"
GATES_JSON = TOOLS / "release_gates.json"
EXPORT_TOOL = TOOLS / "export_job.py"
RELEASE_MD = REPO_ROOT / "docs" / "godot-agent" / "RELEASE.md"
OPS_MD = REPO_ROOT / "docs" / "godot-agent" / "OPERATIONS.md"
EVIDENCE_MD = REPO_ROOT / "docs" / "godot-agent" / "EVIDENCE_REVIEW.md"
LIMITS_MD = REPO_ROOT / "docs" / "godot-agent" / "KNOWN_LIMITATIONS.md"
MATRIX_MD = REPO_ROOT / "docs" / "godot-agent" / "CAPABILITY_MATRIX.md"
DECISIONS_MD = REPO_ROOT / "docs" / "DECISIONS.md"
PINNED = "4.7.1-stable"
PINNED_VERSION = "4.7.1.stable.official.a13da4feb"
LABELS = ("EVIDENCE", "RUNBOOK", "DRILL", "REVIEWER", "GATES", "CLEAN_VM")
REQUIRED_PROVEN = ("RUNBOOK",)
HONEST_UNPROVEN = ("EVIDENCE", "DRILL", "REVIEWER", "GATES", "CLEAN_VM")
DRILL_CMD = 'python tools/godot/ops.py drill --home "$env:LOCALAPPDATA\\HHGodotAgent\\release\\r9-wp4"'


def official_home() -> Path:
    local = os.environ.get("LOCALAPPDATA", "")
    if not local:
        raise RuntimeError("LOCALAPPDATA missing")
    return Path(local) / "HHGodotAgent" / "release" / "r9-wp4"


def hh_agent_root() -> Path | None:
    local = os.environ.get("LOCALAPPDATA", "")
    if not local:
        return None
    return Path(local) / "HHGodotAgent"


def live_sessions_root() -> Path | None:
    root = hh_agent_root()
    return root / "sessions" if root is not None else None


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def emit(text: str) -> None:
    stream = sys.stdout
    encoding = getattr(stream, "encoding", None) or "utf-8"
    stream.write(text.encode(encoding, errors="replace").decode(encoding, errors="replace"))
    stream.write("\n")


def load_export_job():
    spec = importlib.util.spec_from_file_location("export_job", EXPORT_TOOL)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load export_job.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_ops():
    spec = importlib.util.spec_from_file_location("hh_ops", OPS_PY)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load ops.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def plan_errors(text: str) -> list[str]:
    errors: list[str] = []
    current = ""
    wp4 = None
    g6 = None
    gx = None
    total = None
    r9_row = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R9-WP4\b", stripped):
            wp4 = stripped
        if "G6 RELEASE" in stripped or stripped.startswith("G6 "):
            if g6 is None:
                g6 = stripped
        if "GX FORK" in stripped or stripped.startswith("GX "):
            if gx is None:
                gx = stripped
        if stripped.startswith("Tiến độ tổng:") or stripped.startswith("Tien do tong:"):
            total = stripped
        if "| 9 |" in stripped and "G6" in stripped:
            r9_row = stripped
    if current != "R9-WP4":
        errors.append(f"CURRENT_VALID_WP={current!r} (must stay R9-WP4)")
    if wp4 is None:
        errors.append("plan missing R9-WP4 heading")
    elif re.search(r"\[x\]", wp4, re.I):
        errors.append("R9-WP4 must stay unticked")
    if total and "59/60" not in total:
        errors.append(f"progress must stay 59/60 while R9-WP4 is unticked: {total}")
    if r9_row and not re.search(r"\[\s*\]\s*3/4", r9_row):
        errors.append(f"R9 row must stay 3/4 while WP4 is unticked: {r9_row}")
    if g6 is not None and re.search(r"\[x\]", g6, re.I):
        errors.append("official harness must not tick G6")
    if gx is not None and re.search(r"\[x\]", gx, re.I):
        errors.append("official harness must not touch GX")
    return errors


def src_scan_errors() -> list[str]:
    errors: list[str] = []
    self_text = Path(__file__).read_text(encoding="utf-8")
    for label in LABELS:
        if label not in self_text:
            errors.append(f"official test must label {label}")
    if "skip-PASS" not in self_text:
        errors.append("official test must refuse skip-PASS")
    if "Does not tick G6" not in self_text:
        errors.append("official test must refuse to tick G6")
    if "Does not tick GX" not in self_text:
        errors.append("official test must refuse to touch GX")
    if "does not start superfighter" not in self_text.lower():
        errors.append("official test must refuse Superfighter")
    if "does not invent an api key" not in self_text.lower():
        errors.append("official test must refuse invented API keys")
    if "--provider plan stays" not in self_text:
        errors.append("official test must keep --provider plan")
    if "does not poke relic_reached" not in self_text.lower():
        errors.append("official test must refuse to poke relic_reached")
    if "does not invent hyper-v" not in self_text.lower():
        errors.append("official test must refuse invented Hyper-V")
    if ("labels[\"CLEAN_VM\"]" + " = \"proven\"") in self_text or ("labels['CLEAN_VM']" + " = 'proven'") in self_text:
        errors.append("official test must not assign CLEAN_VM=proven")
    for label in ("GATES", "DRILL", "REVIEWER", "EVIDENCE"):
        assign_d = "labels[\"" + label + "\"]" + " = \"proven\""
        assign_s = "labels['" + label + "']" + " = 'proven'"
        if assign_d in self_text or assign_s in self_text:
            errors.append(f"official test must not assign {label}=proven")
    if "CLEAN_VM stays unproven" not in self_text:
        errors.append("official test must keep CLEAN_VM=unproven")
    if "GATES stays unproven" not in self_text:
        errors.append("official test must keep GATES stays unproven")
    if "REVIEWER stays unproven" not in self_text:
        errors.append("official test must keep REVIEWER stays unproven")
    if "DRILL stays unproven" not in self_text:
        errors.append("official test must keep DRILL stays unproven")
    if "EVIDENCE stays unproven" not in self_text:
        errors.append("official test must keep EVIDENCE stays unproven")
    if "same PID" not in self_text and "same argv" not in self_text:
        errors.append("official test must say REVIEWER is the same PID / same argv")
    if "heading-only" not in self_text.lower():
        errors.append("official test must treat heading-only evidence as unproven")
    if "kill a live Godot/sidecar" not in self_text:
        errors.append("official test must refuse DRILL=proven without a live Godot/sidecar kill")
    if "leftover session tokens" not in self_text.lower():
        errors.append("official test must check leftover session tokens")
    if "backup must not ship raw tokens" not in self_text:
        errors.append("official test must refuse a backup that ships raw tokens")
    if "rotate-token --live" not in self_text:
        errors.append("official test must exercise rotate-token --live")
    if "kill leftover Godot first" not in self_text:
        errors.append("official test must kill leftover Godot first")
    if "disaster drill" not in self_text.lower():
        errors.append("official test must run a disaster drill")
    if "fresh reviewer follow runbook" not in self_text.lower():
        errors.append("official test must follow the runbook as a fresh reviewer")
    if "all gates/artifacts resolve" not in self_text.lower():
        errors.append("official test must resolve all gates/artifacts")
    if "not_g6=1" not in self_text:
        errors.append("official test must keep not_g6=1")
    if "do not copy the exe into a folder named clean-vm" not in self_text.lower():
        errors.append("official test must refuse a clean-vm folder stamp")
    if "4.7." + "2" in self_text:
        errors.append("official test must refuse Godot 4.7." + "2 pin")
    if ("relic_reached" + " =") in self_text:
        errors.append("official test must not assign relic_reached")
    if not OPS_PY.is_file():
        errors.append("missing tools/godot/ops.py")
    else:
        ops_text = OPS_PY.read_text(encoding="utf-8")
        for needle in (
            "CLEAN_VM stays unproven",
            "Does not stamp CLEAN_VM as proven",
            "Does not stamp GATES as proven",
            "Does not invent Hyper-V",
            "do not invent Hyper-V",
            "unsigned internal only",
            "--provider plan stays",
            "Does not tick G6",
            "Does not start Superfighter",
            "not a clean VM",
            "E_UNCERTAIN",
            "committed_durable",
            "clean-vm",
            "backup must not ship raw tokens",
            "wipe-tokens",
            "--live",
        ):
            if needle not in ops_text:
                errors.append(f"ops.py must mention {needle}")
        if "CLEAN_VM=proven" in ops_text:
            errors.append("ops.py must not stamp CLEAN_VM=proven")
        if "GATES=proven" in ops_text:
            errors.append("ops.py must not stamp GATES=proven")
        if 'clean_vm": "proven"' in ops_text or "clean_vm': 'proven'" in ops_text:
            errors.append("ops.py must not assign clean_vm proven")
    if not GATES_JSON.is_file():
        errors.append("missing tools/godot/release_gates.json")
    else:
        gates_text = GATES_JSON.read_text(encoding="utf-8")
        if "GATES=proven" in gates_text:
            errors.append("release_gates.json must not stamp GATES=proven")
        gates = json.loads(gates_text)
        if gates.get("clean_vm") == "proven":
            errors.append("release_gates.json must not stamp CLEAN_VM proven")
        if int(gates.get("not_g6") or 0) != 1:
            errors.append("release_gates.json must keep not_g6=1")
        g6 = next((g for g in gates.get("gates") or [] if g.get("id") == "G6"), None)
        gx = next((g for g in gates.get("gates") or [] if g.get("id") == "GX"), None)
        if not g6 or g6.get("status") != "unresolved":
            errors.append("catalog G6 must stay unresolved")
        if not gx or gx.get("status") != "locked":
            errors.append("catalog GX must stay locked")
    if (REPO_ROOT / "godot" / "superfighter").exists() or (REPO_ROOT / "godot" / "dogfood" / "superfighter").exists():
        errors.append("must not start a Superfighter folder")
    return errors


def docs_errors() -> list[str]:
    errors: list[str] = []
    required = {
        RELEASE_MD: (
            "E3",
            "CLEAN_VM stays unproven",
            "not_g6=1",
            "Do not invent a cert",
            "--provider plan stays",
            "python tests/bootstrap/test_release_handoff.py",
            "Do not tick G6",
            "GATES stays unproven",
        ),
        OPS_MD: (
            "disaster drill",
            DRILL_CMD,
            "python tools/godot/ops.py backup",
            "python tools/godot/ops.py restore",
            "python tools/godot/ops.py collect-logs",
            "python tools/godot/ops.py rotate-token",
            "python tools/godot/ops.py rotate-token --live",
            "python tools/godot/ops.py wipe-tokens",
            "python tools/godot/ops.py recover",
            "python tools/godot/ops.py catalog",
            "python tools/godot/ops.py sign",
            "python tools/godot/ops.py upload",
            "CLEAN_VM stays unproven",
            "fresh-reviewer",
            "E_UNCERTAIN",
            "not_g6=1",
            "backup must not ship raw tokens",
        ),
        EVIDENCE_MD: (
            "Security",
            "Privacy",
            "License / SBOM",
            "Clean VM",
            "Autonomy (G4)",
            "Dogfood (G5)",
            "CLEAN_VM stays unproven",
            "--provider plan stays",
            "Do not invent an API key",
            "EVIDENCE stays unproven",
        ),
        LIMITS_MD: (
            "Capability Matrix",
            "CM-018",
            "CM-148",
            "CM-142",
            "CM-158",
            "CLEAN_VM stays unproven",
            "every Godot button",
        ),
    }
    for path, needles in required.items():
        if not path.is_file():
            errors.append(f"missing {rel(path)}")
            continue
        text = path.read_text(encoding="utf-8")
        for needle in needles:
            if needle not in text:
                errors.append(f"{rel(path)} must mention {needle}")
        if "CLEAN_VM=proven" in text:
            errors.append(f"{rel(path)} must not stamp CLEAN_VM=proven")
        if "GATES=proven" in text:
            errors.append(f"{rel(path)} must not stamp GATES=proven")
    if MATRIX_MD.is_file():
        matrix = MATRIX_MD.read_text(encoding="utf-8")
        if "Official clean-VM verify" in matrix:
            errors.append("CAPABILITY_MATRIX.md must not claim Official clean-VM verify")
    else:
        errors.append("missing docs/godot-agent/CAPABILITY_MATRIX.md")
    if DECISIONS_MD.is_file():
        decisions = DECISIONS_MD.read_text(encoding="utf-8")
        if "honest gate/artifact catalog" in decisions or "honest catalog" in decisions:
            errors.append("DECISIONS must not redefine all-gates-resolve as honest catalog")
        if "WP4 ships the product/ops side" in decisions:
            errors.append("DECISIONS must not split WP4 from G6")
        if "GODOT-R9-WP4-OPS-2026-08-26" not in decisions:
            errors.append("DECISIONS must keep GODOT-R9-WP4-OPS-2026-08-26")
    else:
        errors.append("missing docs/DECISIONS.md")
    return errors


def banner_for(labels: dict[str, str]) -> str:
    return "; ".join(f"{k}={labels[k]}" for k in LABELS)


def leftover_count(export_job, project: Path | None) -> int:
    return int(export_job.leftover_godot_count(project))


def kill_project(export_job, project: Path) -> int:
    export_job.kill_godot_for_project(project)
    n = leftover_count(export_job, project)
    if n != 0:
        export_job.kill_godot_for_project(project)
        n = leftover_count(export_job, project)
    return n


def kill_known(export_job, extra: list[Path] | None = None) -> int:
    leftover = 0
    leftover += kill_project(export_job, DOGFOOD)
    leftover += kill_project(export_job, PLUGIN_PROJECT)
    leftover += kill_project(export_job, MINIMAL)
    for path in extra or []:
        leftover += kill_project(export_job, path)
    export_job.kill_leftover_game()
    return leftover


def drain_leftover(export_job, extra: list[Path] | None = None, attempts: int = 8) -> int:
    leftover = 0
    for _ in range(attempts):
        leftover = kill_known(export_job, extra)
        for pid, cmd in export_job._godot_cmdlines():
            if "godot" not in export_job._norm(cmd):
                continue
            export_job.kill_pid_tree(pid)
        leftover = leftover_count(export_job, None)
        if leftover == 0:
            return 0
        time.sleep(0.35)
    return leftover


def run_ops(args: list[str], timeout: float = 300.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(OPS_PY), *args],
        cwd=str(REPO_ROOT),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def session_token_of(path: Path) -> str:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(data, dict):
        return ""
    return str(data.get("token") or "")


def leftover_session_token_count(root: Path | None = None) -> int:
    base = root if root is not None else hh_agent_root()
    if base is None or not base.is_dir():
        return 0
    count = 0
    for path in base.rglob("session.json"):
        if session_token_of(path):
            count += 1
    return count


def wipe_session_tokens(root: Path | None = None) -> tuple[int, int]:
    """Wipe plaintext tokens. Returns (remaining, unwritable). Never prints tokens."""
    base = root if root is not None else hh_agent_root()
    if base is None or not base.is_dir():
        return 0, 0
    unwritable = 0
    for path in list(base.rglob("session.json")):
        old = session_token_of(path)
        if not old:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
            data["token"] = ""
            data["token_redacted"] = True
            data["note"] = "token wiped after official; not an API key"
            path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            if old in path.read_text(encoding="utf-8"):
                unwritable += 1
        except OSError:
            unwritable += 1
    return leftover_session_token_count(base), unwritable


def plant_live_rotate_fixture() -> tuple[Path, str]:
    root = live_sessions_root()
    if root is None:
        raise RuntimeError("LOCALAPPDATA missing")
    dest = root / "r9wp4honesty000000000000000001"
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / "session.json"
    token = secrets.token_hex(32)
    path.write_text(
        json.dumps(
            {
                "schema": "hh-godot-session/1",
                "project_id": "r9wp4honesty000000000000000001",
                "token": token,
                "bind": "127.0.0.1",
                "note": "official live-rotate fixture; wiped after; not an API key",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path, token


def backup_shipped_raw_tokens(home: Path) -> list[str]:
    errors: list[str] = []
    backup = home / "backup"
    if not backup.is_dir():
        errors.append("disaster drill did not write a backup")
        return errors
    for path in backup.rglob("session.json"):
        if session_token_of(path):
            errors.append("backup must not ship raw tokens")
            break
    log = backup / "logs-raw" / "sidecar.log"
    if log.is_file():
        text = log.read_text(encoding="utf-8", errors="replace")
        if "sk-drillfixture" in text or "ghp_drillfixture" in text:
            errors.append("backup shipped planted credential prefixes")
        if re.search(r"HH_TOKEN=[0-9a-fA-F]{16,}", text):
            errors.append("backup shipped a raw HH_TOKEN")
    return errors


def main() -> int:
    labels = {key: "unproven" for key in LABELS}
    labels["CLEAN_VM"] = "unproven"
    # Heading-only EVIDENCE_REVIEW.md is not a real review (P1).
    labels["EVIDENCE"] = "unproven"
    # mkdir+copytree+planted bytes is not a live Godot/sidecar kill (P1).
    labels["DRILL"] = "unproven"
    # Same PID / same argv as official is not a fresh reviewer (P1).
    labels["REVIEWER"] = "unproven"
    # G6 unresolved: GATES stays unproven (P1).
    labels["GATES"] = "unproven"
    errors: list[str] = []
    leftover = -1
    leftover_tokens = -1
    unwritable_tokens = 0
    official_cmd = f"python {rel(Path(__file__))}"
    if not PLAN.is_file():
        emit("FAIL: R9-WP4 release handoff; missing plan")
        return 1
    plan_text = PLAN.read_text(encoding="utf-8")
    errors.extend(plan_errors(plan_text))
    errors.extend(src_scan_errors())
    errors.extend(docs_errors())
    if not os.environ.get("LOCALAPPDATA"):
        errors.append("LOCALAPPDATA missing; official home cannot be LocalAppData release")
    if errors:
        leftover_tokens, unwritable_tokens = wipe_session_tokens()
        emit(f"FAIL: R9-WP4 release handoff; {banner_for(labels)}")
        emit(f"  leftover_session_tokens={leftover_tokens} unwritable={unwritable_tokens}")
        for item in errors:
            emit(f"  - {item}")
        return 1

    try:
        export_job = load_export_job()
    except (OSError, RuntimeError) as exc:
        leftover_tokens, unwritable_tokens = wipe_session_tokens()
        emit(f"FAIL: R9-WP4 release handoff; {banner_for(labels)}")
        emit(f"  - load export_job: {exc}")
        return 1

    home = official_home()
    leftover = drain_leftover(export_job, [home / "user-project"] if (home / "user-project").exists() else None)
    if leftover != 0:
        leftover_tokens, unwritable_tokens = wipe_session_tokens()
        emit(f"FAIL: R9-WP4 release handoff; {banner_for(labels)}")
        emit(f"  leftover_godot={leftover} leftover_session_tokens={leftover_tokens} not_g6=1 official={official_cmd}")
        emit(f"  - leftover Godot before start={leftover}")
        return 1

    runbook_text = OPS_MD.read_text(encoding="utf-8")
    if DRILL_CMD in runbook_text and "fresh-reviewer" in runbook_text.lower():
        labels["RUNBOOK"] = "proven"
    else:
        errors.append("OPERATIONS.md is not a followable fresh-reviewer runbook")

    refused_sign = run_ops(["sign"])
    refused_upload = run_ops(["upload"])
    refused_vm = run_ops(["catalog", "--clean-vm-proven"])
    refused_hv = run_ops(["catalog", "--hyperv"])
    if refused_sign.returncode == 0 or "E3" not in ((refused_sign.stdout or "") + (refused_sign.stderr or "")):
        errors.append("ops.py sign must refuse E3")
    if refused_upload.returncode == 0:
        errors.append("ops.py upload must refuse E3")
    if refused_vm.returncode == 0 or "unproven" not in ((refused_vm.stdout or "") + (refused_vm.stderr or "")).lower():
        errors.append("ops.py --clean-vm-proven must refuse")
    if refused_hv.returncode == 0:
        errors.append("ops.py --hyperv must refuse invented Hyper-V")

    live_root = live_sessions_root()
    live_before: dict[str, str] = {}
    if live_root is not None and live_root.is_dir():
        for path in live_root.rglob("session.json"):
            token = session_token_of(path)
            if token:
                live_before[str(path)] = token
    planted: Path | None = None
    planted_token = ""
    if not live_before:
        planted, planted_token = plant_live_rotate_fixture()
        live_before[str(planted)] = planted_token
    rotated_live = run_ops(["rotate-token", "--live", "--home", str(home)])
    rot_out = (rotated_live.stdout or "") + (rotated_live.stderr or "")
    if rotated_live.returncode != 0:
        errors.append(f"rotate-token --live exit {rotated_live.returncode}: {rot_out[-400:]}")
    else:
        changed = 0
        for raw_path, old in live_before.items():
            path = Path(raw_path)
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            new = session_token_of(path)
            if new and new != old and old not in text:
                changed += 1
        if changed == 0:
            errors.append("rotate-token --live did not rotate the live leftover path")

    try:
        drilled = run_ops(["drill", "--home", str(home)], timeout=420.0)
    except subprocess.TimeoutExpired:
        leftover = drain_leftover(export_job, [home / "user-project"])
        leftover_tokens, unwritable_tokens = wipe_session_tokens()
        emit(f"FAIL: R9-WP4 release handoff; {banner_for(labels)}")
        emit(
            f"  leftover_godot={leftover} leftover_session_tokens={leftover_tokens} "
            f"not_g6=1 official={official_cmd}"
        )
        emit("  - disaster drill timed out")
        return 1

    drill_out = (drilled.stdout or "") + (drilled.stderr or "")
    report_path = home / "drill-report.json"
    if drilled.returncode != 0:
        errors.append(f"disaster drill exit {drilled.returncode}: {drill_out[-800:]}")
    elif "CLEAN_VM stays unproven" not in drill_out or "not_g6=1" not in drill_out:
        errors.append("disaster drill banner must keep CLEAN_VM stays unproven and not_g6=1")
    elif not report_path.is_file():
        errors.append("disaster drill did not write drill-report.json")
    else:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("clean_vm") == "proven":
            errors.append("drill-report must not stamp CLEAN_VM proven")
        elif report.get("ok") is not True:
            errors.append(f"drill-report incomplete: {report}")
        errors.extend(backup_shipped_raw_tokens(home))

    cataloged = run_ops(["catalog", "--home", str(home), "--repo", str(REPO_ROOT)])
    cat_out = (cataloged.stdout or "") + (cataloged.stderr or "")
    if cataloged.returncode != 0:
        errors.append(f"catalog exit {cataloged.returncode}: {cat_out[-600:]}")
    elif "G6=unresolved" not in cat_out or "GX=locked" not in cat_out:
        errors.append("catalog must say G6=unresolved GX=locked")
    else:
        cat_path = home / "catalog-report.json"
        if cat_path.is_file():
            cat = json.loads(cat_path.read_text(encoding="utf-8"))
            if cat.get("clean_vm") == "proven" or cat.get("g6") != "unresolved":
                errors.append("catalog-report must keep G6 unresolved / CLEAN_VM unproven")
            elif cat.get("ok") is not True:
                errors.append(f"catalog-report errors: {cat.get('errors')}")
        else:
            errors.append("catalog-report.json missing")

    wiped = run_ops(["wipe-tokens", "--live", "--home", str(home)])
    if wiped.returncode != 0:
        wipe_out = (wiped.stdout or "") + (wiped.stderr or "")
        errors.append(f"wipe-tokens exit {wiped.returncode}: {wipe_out[-400:]}")
    leftover_tokens, unwritable_tokens = wipe_session_tokens()
    if leftover_tokens != 0 or unwritable_tokens != 0:
        errors.append(
            f"leftover session tokens={leftover_tokens} unwritable={unwritable_tokens} "
            "(could not wipe others)"
        )

    if (home / "clean-vm").exists() or (home / "clean_vm").exists():
        errors.append("must not create a clean-vm folder")
    if labels["CLEAN_VM"] == "proven":
        errors.append("must not stamp CLEAN_VM=proven on this Godot/Node machine")
    for key in HONEST_UNPROVEN:
        if labels[key] != "unproven":
            errors.append(f"must not stamp {key}=proven on this Godot/Node machine")

    leftover = drain_leftover(export_job, [home / "user-project"])
    if leftover != 0:
        errors.append(f"leftover Godot after verify={leftover}")

    leftover_tokens = leftover_session_token_count()
    if (
        errors
        or any(labels[key] != "proven" for key in REQUIRED_PROVEN)
        or any(labels[key] != "unproven" for key in HONEST_UNPROVEN)
        or leftover_tokens != 0
    ):
        leftover = drain_leftover(export_job, [home / "user-project"])
        leftover_tokens, unwritable_tokens = wipe_session_tokens()
        emit(f"FAIL: R9-WP4 release handoff; {banner_for(labels)}")
        emit(
            f"  leftover_godot={leftover} leftover_session_tokens={leftover_tokens} "
            f"unwritable={unwritable_tokens} not_g6=1 official={official_cmd}"
        )
        for item in errors:
            emit(f"  - {item}")
        return 1

    leftover = drain_leftover(export_job, [home / "user-project"])
    leftover_tokens = leftover_session_token_count()
    if leftover != 0 or leftover_tokens != 0:
        emit(f"FAIL: R9-WP4 release handoff; {banner_for(labels)}")
        emit(f"  leftover_godot={leftover} leftover_session_tokens={leftover_tokens}")
        return 1

    emit(f"PASS: R9-WP4 release handoff; {banner_for(labels)}")
    emit(f"  official={official_cmd}")
    emit(f"  pin={PINNED} godot={PINNED_VERSION} leftover_godot=0 leftover_session_tokens=0 signing=unsigned")
    emit(f"  home={home} smoke!=VM not_g6=1 HUMAN=unproven CLEAN_VM stays unproven")
    emit("  GATES stays unproven REVIEWER stays unproven DRILL stays unproven EVIDENCE stays unproven")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
