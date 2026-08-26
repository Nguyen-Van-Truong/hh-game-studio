#!/usr/bin/env python3
"""R9-WP1: export job/preset/validation and clean Windows build.

Does not tick the 20-8 plan. Does not change CURRENT_VALID_WP.
Keep R9-WP1 [ ]; CURRENT_VALID_WP=R9-WP1; progress stays 56/60.
Does not start R9-WP2. Does not start Superfighter.
Does not tick G6 or GX. Does not invent an API key. --provider plan stays.
Does not poke relic_reached. Does not regress kho-bi-an graybox/polish/playtest.
No snake demo. No r7w6 trial. No secret material. No skip-PASS.
Does not invent Hyper-V. Does not stamp CLEAN_VM=proven on this Godot/Node machine.

Official verify (plan R9-WP1 Verify, Godot §7.3 sequential):
  kill leftover Godot and leftover KhoBiAn.exe first
  install/verify exact 4.7.1.stable export templates
  validate Windows preset / assets / main scene / license
  one Godot --path at a time: import, then --export-release
  official player artifact under %LOCALAPPDATA%/HHGodotAgent/exports/
  allowlist also includes repo artifacts/ (inside the studio repo)
  PCK path list scan: fail tests/addons/hh_agent/token/evidence/audit contact_sheet
  8s LocalAppData copy+launch is SMOKE, not a clean VM
  CLEAN_VM stays unproven; real clean VM is G6/AC-20

Labels: TEMPLATES, PRESET, EXPORT, SCAN, CLEAN_VM
Windowed game exe is plan §7.3 launch smoke, not a new G5.
"""

from __future__ import annotations

import importlib.util
import os
import re
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAN = REPO_ROOT / "zdocs" / "20-8-godot-agent-autopilot-plan.txt"
DOGFOOD = REPO_ROOT / "godot" / "dogfood" / "kho-bi-an"
PRESET = DOGFOOD / "export_presets.cfg"
NOTICE = DOGFOOD / "NOTICE.md"
EXPORT_TOOL = REPO_ROOT / "tools" / "godot" / "export_job.py"
ADDON = REPO_ROOT / "godot" / "plugin-project" / "addons" / "hh_agent"
ADAPTER = ADDON / "core" / "hh_export_adapter.gd"
EXPORT_PLUGIN = ADDON / "core" / "hh_export_plugin.gd"
JOB_ID = "01R9WP1EXPORT00000000KBA00001"
PINNED_VERSION = "4.7.1.stable.official.a13da4feb"
PINNED = "4.7.1-stable"
LABELS = ("TEMPLATES", "PRESET", "EXPORT", "SCAN", "CLEAN_VM")
REQUIRED_PROVEN = ("TEMPLATES", "PRESET", "EXPORT", "SCAN")
PATH_NEEDLES = ("kho-bi-an", "kho_bi_an")


def official_out_dir() -> Path:
    local = os.environ.get("LOCALAPPDATA", "")
    if not local:
        raise RuntimeError("LOCALAPPDATA missing")
    return Path(local) / "HHGodotAgent" / "exports" / "r9-wp1-export"


OUT_DIR = official_out_dir() if os.environ.get("LOCALAPPDATA") else REPO_ROOT / "artifacts" / "r9-wp1-export"


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


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


def plan_errors(text: str) -> list[str]:
    errors: list[str] = []
    current = ""
    wp1 = None
    g6 = None
    gx = None
    total = None
    r9_row = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R9-WP1\b", stripped):
            wp1 = stripped
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
    if current != "R9-WP1":
        errors.append(f"CURRENT_VALID_WP={current!r} (must stay R9-WP1)")
    if wp1 is None:
        errors.append("plan missing R9-WP1 heading")
    elif re.search(r"\[x\]", wp1, re.I):
        errors.append("R9-WP1 must stay unticked")
    if total and "56/60" not in total:
        errors.append(f"progress must stay 56/60 while R9-WP1 is unticked: {total}")
    if r9_row and not re.search(r"\[\s*\]\s*0/4", r9_row):
        errors.append(f"R9 row must stay 0/4 while WP1 is unticked: {r9_row}")
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
    if "No skip-PASS" not in self_text and "skip-PASS" not in self_text:
        errors.append("official test must refuse skip-PASS")
    if "does not tick g6" not in self_text.lower() and "Does not tick G6" not in self_text:
        errors.append("official test must refuse to tick G6")
    if "does not touch gx" not in self_text.lower() and "Does not tick GX" not in self_text:
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
    if "CLEAN_VM stays unproven" not in self_text and 'labels["CLEAN_VM"] = "unproven"' not in self_text:
        errors.append("official test must keep CLEAN_VM=unproven")
    if "list_pck_paths" not in self_text and "scan_packed_paths" not in self_text:
        errors.append("official test must list PCK paths")
    if "KhoBiAn.exe" not in self_text or "leftover_game" not in self_text:
        errors.append("official test must kill leftover KhoBiAn.exe")
    if "HHGodotAgent" not in self_text or "LOCALAPPDATA" not in self_text:
        errors.append("official test must use LocalAppData exports")
    if "4.7." + "2" in self_text:
        errors.append("official test must refuse Godot 4.7." + "2 pin")
    if ("relic_reached" + " =") in self_text or ("relic_reached" + "=") in self_text:
        errors.append("official test must not assign relic_reached")
    job_text = EXPORT_TOOL.read_text(encoding="utf-8")
    if "4.7." + "2" in job_text:
        errors.append("export_job.py must refuse Godot 4.7." + "2")
    if "jail_export_out" not in job_text:
        errors.append("export_job.py must jail allowlisted out_dir")
    if "cancel_requested" not in job_text:
        errors.append("export_job.py must keep real cancel state")
    if "list_pck_paths" not in job_text:
        errors.append("export_job.py must list PCK paths")
    if "clean-vm" in job_text.lower() or "clean_vm_dir" in job_text:
        errors.append("export_job.py must not invent a clean-vm folder")
    if "CLEAN_VM=proven" in job_text:
        errors.append("export_job.py must not stamp CLEAN_VM=proven")
    if not ADAPTER.is_file():
        errors.append("missing hh_export_adapter.gd")
    else:
        adapter = ADAPTER.read_text(encoding="utf-8")
        for needle in ("export_preset_present", "export_preset_valid", "export_job_accepted"):
            if needle not in adapter:
                errors.append(f"export adapter must prove {needle}")
        if "contact_sheet" not in adapter:
            errors.append("export adapter strip must include contact_sheet")
    if not EXPORT_PLUGIN.is_file():
        errors.append("missing hh_export_plugin.gd")
    else:
        plugin = EXPORT_PLUGIN.read_text(encoding="utf-8")
        if "skip()" not in plugin:
            errors.append("export plugin must call skip()")
        for needle in ("addons/hh_agent", ".hh-agent", "token", "evidence", "tests/", "audit", "contact_sheet"):
            if needle not in plugin:
                errors.append(f"export skip() must match {needle}")
    router = (ADDON / "core" / "hh_router.gd").read_text(encoding="utf-8")
    if "godot.export" not in router:
        errors.append("router must dispatch godot.export")
    plugin_gd = (ADDON / "plugin.gd").read_text(encoding="utf-8")
    if "hh_export_adapter" not in plugin_gd:
        errors.append("plugin.gd must attach export adapter")
    if "_hh_export_pending" not in plugin_gd:
        errors.append("plugin.gd must poll export job pending")
    return errors


def product_errors() -> list[str]:
    errors: list[str] = []
    if not PRESET.is_file():
        errors.append("kho-bi-an missing export_presets.cfg")
        return errors
    text = PRESET.read_text(encoding="utf-8")
    if 'name="Windows Desktop"' not in text:
        errors.append("Windows Desktop preset missing")
    if 'platform="Windows Desktop"' not in text:
        errors.append("Windows Desktop platform missing")
    for needle in ("addons/", ".hh-agent/", "token", "evidence", "audit", "contact_sheet", "tests/"):
        if needle not in text:
            errors.append(f"kho-bi-an exclude_filter missing {needle}")
    if not NOTICE.is_file():
        errors.append("kho-bi-an missing NOTICE.md")
    return errors


def banner_for(labels: dict[str, str]) -> str:
    return "; ".join(f"{k}={labels[k]}" for k in LABELS)


def leftover_godot_count(export_job, project: Path) -> int:
    return int(export_job.leftover_godot_count(project))


def leftover_game_count(export_job) -> int:
    return int(export_job.leftover_game_count())


def kill_leftovers(export_job) -> tuple[int, int]:
    export_job.kill_godot_for_project(DOGFOOD)
    export_job.kill_leftover_game()
    leftover = leftover_godot_count(export_job, DOGFOOD)
    leftover_game = leftover_game_count(export_job)
    if leftover != 0:
        export_job.kill_godot_for_project(DOGFOOD)
        leftover = leftover_godot_count(export_job, DOGFOOD)
    if leftover_game != 0:
        export_job.kill_leftover_game()
        leftover_game = leftover_game_count(export_job)
    return leftover, leftover_game


def main() -> int:
    labels = {key: "unproven" for key in LABELS}
    labels["CLEAN_VM"] = "unproven"
    errors: list[str] = []
    job_cancel = "unproven"
    job_timeout = "unproven"
    smoke = "unproven"
    pck_n = 0
    wall = 0.0
    leftover = -1
    leftover_game = -1
    official_cmd = (
        f"python {rel(Path(__file__))}  "
        f"# sequential: godot --headless --path {rel(DOGFOOD)} --import --quit ; "
        f"godot --headless --path {rel(DOGFOOD)} --export-release \"Windows Desktop\" "
        f"{display_path(OUT_DIR / 'KhoBiAn.exe')}"
    )
    if not PLAN.is_file():
        emit("FAIL: R9-WP1 export clean build; missing plan")
        return 1
    plan_text = PLAN.read_text(encoding="utf-8")
    errors.extend(plan_errors(plan_text))
    errors.extend(src_scan_errors())
    errors.extend(product_errors())
    if not os.environ.get("LOCALAPPDATA"):
        errors.append("LOCALAPPDATA missing; official out_dir cannot be LocalAppData exports")
    if errors:
        emit(f"FAIL: R9-WP1 export clean build; {banner_for(labels)}")
        for item in errors:
            emit(f"  - {item}")
        return 1

    try:
        export_job = load_export_job()
    except (OSError, RuntimeError) as exc:
        emit(f"FAIL: R9-WP1 export clean build; {banner_for(labels)}")
        emit(f"  - load export_job: {exc}")
        return 1

    leftover, leftover_game = kill_leftovers(export_job)
    if leftover != 0 or leftover_game != 0:
        emit(f"FAIL: R9-WP1 export clean build; {banner_for(labels)}")
        emit(f"  - leftover Godot before start={leftover} leftover_KhoBiAn={leftover_game}")
        return 1

    try:
        _dest, template_version = export_job.ensure_windows_templates()
        labels["TEMPLATES"] = "proven"
    except RuntimeError as exc:
        errors.append(f"templates: {exc}")
        emit(f"FAIL: R9-WP1 export clean build; {banner_for(labels)}")
        for item in errors:
            emit(f"  - {item}")
        return 1

    try:
        export_job.validate_project(DOGFOOD, "Windows Desktop")
        labels["PRESET"] = "proven"
    except RuntimeError as exc:
        errors.append(f"preset/validate: {exc}")
        emit(f"FAIL: R9-WP1 export clean build; {banner_for(labels)}")
        for item in errors:
            emit(f"  - {item}")
        return 1

    try:
        cancel_pid = export_job.prove_cancel_kills_godot(DOGFOOD, JOB_ID + "CANCEL")
        leftover, leftover_game = kill_leftovers(export_job)
        if int(cancel_pid) > 0 and leftover == 0:
            job_cancel = "proven"
    except RuntimeError:
        leftover, leftover_game = kill_leftovers(export_job)

    try:
        timeout_pid = export_job.prove_timeout_kills_godot(DOGFOOD, JOB_ID + "TIMEOUT")
        leftover, leftover_game = kill_leftovers(export_job)
        if int(timeout_pid) > 0 and leftover == 0:
            job_timeout = "proven"
    except RuntimeError:
        leftover, leftover_game = kill_leftovers(export_job)

    t0 = time.perf_counter()
    try:
        rec = export_job.build_export(
            DOGFOOD,
            "Windows Desktop",
            OUT_DIR,
            JOB_ID,
            360.0,
            False,
        )
    except (OSError, RuntimeError) as exc:
        errors.append(f"export job: {exc}")
        leftover, leftover_game = kill_leftovers(export_job)
        emit(f"FAIL: R9-WP1 export clean build; {banner_for(labels)}")
        emit(f"  leftover_godot={leftover} leftover_KhoBiAn={leftover_game} official={official_cmd}")
        for item in errors:
            emit(f"  - {item}")
        return 1
    wall = time.perf_counter() - t0
    exe_out = Path(str(rec.get("exe", OUT_DIR / "KhoBiAn.exe")))
    if str(rec.get("state")) != "done" or not exe_out.is_file():
        errors.append("export job did not finish with an exe")
    else:
        labels["EXPORT"] = "proven"

    scan_hits: list[str] = []
    if exe_out.is_file():
        try:
            packed_paths, pck_hits = export_job.scan_packed_paths(exe_out)
            pck_n = len(packed_paths)
            scan_hits.extend(pck_hits)
            if pck_n < 1:
                errors.append("PCK path list was empty")
        except RuntimeError as exc:
            errors.append(f"PCK list: {exc}")
        scan_hits.extend(export_job.scan_artifact_bytes(exe_out))
        scan_hits.extend(export_job.scan_artifact_names(OUT_DIR))
    if scan_hits:
        errors.append(f"artifact PCK/path scan forbidden: {scan_hits}")
    elif pck_n > 0:
        labels["SCAN"] = "proven"

    if not (OUT_DIR / "build_manifest.json").is_file():
        errors.append("missing build_manifest.json")
    if not (OUT_DIR / "sbom.json").is_file():
        errors.append("missing sbom.json")
    if not (OUT_DIR / "NOTICE.md").is_file():
        errors.append("missing artifact NOTICE.md")
    if not (OUT_DIR / "hashes.txt").is_file():
        errors.append("missing hashes.txt")
    if not (OUT_DIR / "pck_paths.txt").is_file():
        errors.append("missing pck_paths.txt")

    if labels["EXPORT"] == "proven" and labels["SCAN"] == "proven":
        try:
            ship = export_job.smoke_dir(JOB_ID)
            dest_exe = export_job.populate_smoke(ship, exe_out)
            export_job.launch_smoke(dest_exe, ship)
            smoke = "proven"
            export_job.kill_leftover_game()
        except RuntimeError as exc:
            errors.append(f"smoke: {exc}")

    leftover, leftover_game = kill_leftovers(export_job)
    if leftover != 0:
        errors.append(f"leftover Godot after export={leftover}")
    if leftover_game != 0:
        errors.append(f"leftover KhoBiAn.exe after export={leftover_game}")

    if labels["CLEAN_VM"] == "proven":
        errors.append("must not stamp CLEAN_VM=proven on this Godot/Node machine")

    if errors or any(labels[key] != "proven" for key in REQUIRED_PROVEN) or labels["CLEAN_VM"] != "unproven":
        emit(f"FAIL: R9-WP1 export clean build; {banner_for(labels)}")
        emit(f"  godot_wall_s={wall:.1f} leftover_godot={leftover} leftover_KhoBiAn={leftover_game} not_g6=1")
        emit(f"  official={official_cmd}")
        for item in errors:
            emit(f"  - {item}")
        return 1

    leftover, leftover_game = kill_leftovers(export_job)
    if leftover != 0 or leftover_game != 0:
        emit(f"FAIL: R9-WP1 export clean build; {banner_for(labels)}")
        emit(f"  - leftover Godot={leftover} leftover_KhoBiAn={leftover_game}")
        return 1

    emit(f"PASS: R9-WP1 export clean build; {banner_for(labels)}")
    emit(f"  official={official_cmd}")
    emit(
        f"  pin={PINNED} godot={PINNED_VERSION} templates={template_version} "
        f"sidecar=none leftover_godot=0 leftover_KhoBiAn=0"
    )
    emit(
        f"  godot_wall_s={wall:.1f} exe={display_path(exe_out)} "
        f"pck_files={pck_n} scan=pck_paths not_g6=1 HUMAN=unproven"
    )
    emit(
        f"  smoke={smoke} job_cancel={job_cancel} job_timeout={job_timeout} "
        f"job_progress=unproven allowlist=LOCALAPPDATA/HHGodotAgent/exports+repo artifacts/"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
