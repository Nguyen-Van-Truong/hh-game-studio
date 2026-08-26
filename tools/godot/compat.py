#!/usr/bin/env python3
"""R9-WP3: compatibility/update matrix — pin, probe, migrate, rollback.

Supports the exact Godot pin. Probe of a newer stable is non-blocking and
never applied until a later approved WP. Capability-lock migration is a
project migration copy first. Downgrade restores the old lock. Version
mismatch is Observe/Doctor only. Does not auto-bump mid-session.

Does not tick the plan. Does not start R9-WP4 or G6. Does not start Superfighter.
Does not tick GX. Does not invent an API key. --provider plan stays.
Does not stamp CLEAN_VM as proven. CLEAN_VM stays unproven.
Broken API uses a minimal editor project (addon only). do not copytree plugin-project.
strip .hh-agent from fixture copies. --import the editor project.
One sidecar / one --path. Kill leftover Godot first.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
PIN_PATH = HERE / "pin.json"
MATRIX_PATH = HERE / "compatibility_matrix.json"
PROBE_FIXTURE = HERE / "probe_latest.fixture.json"
REPO_LOCK = REPO_ROOT / ".hh-agent" / "capability-lock.json"
STAGING = REPO_ROOT / "third_party" / "mcp-staging"
PINNED = "4.7.1-stable"
PINNED_VERSION = "4.7.1.stable.official.a13da4feb"
PROTOCOL = "hh-godot-agent/1"
REGISTRY = "hh-godot-actions/1"
LOCK_SCHEMA = "hh-godot-capability-lock/1"
BROKEN_PROTOCOL = "hh-godot-agent/broken"
BROKEN_SCHEMA = "hh-godot-actions/broken"
COPY_IGNORE = shutil.ignore_patterns(
    ".godot",
    "__pycache__",
    ".git",
    "node_modules",
    "dist",
    ".hh-agent",
)
ADDON_REL = Path("godot") / "plugin-project" / "addons" / "hh_agent"
BROKEN_PROJECT_GODOT = """config_version=5

[application]

config/name="HH Broken API Fixture"
config/features=PackedStringArray("4.7", "Forward Plus")

[debug]

gdscript/warnings/untyped_declaration=1
gdscript/warnings/inferred_declaration=1

[editor_plugins]

enabled=PackedStringArray("res://addons/hh_agent/plugin.cfg")
"""


class CompatError(RuntimeError):
    def __init__(self, message: str, *, do: str = "") -> None:
        super().__init__(message)
        self.do = do or "Observe/Doctor only; keep the official pin"


def emit(text: str) -> None:
    stream = sys.stdout
    encoding = getattr(stream, "encoding", None) or "utf-8"
    stream.write(text.encode(encoding, errors="replace").decode(encoding, errors="replace"))
    stream.write("\n")


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise CompatError(f"missing {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise CompatError(f"{path} must be a JSON object")
    return data


def dump_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def load_pin() -> dict[str, Any]:
    return load_json(PIN_PATH)


def load_matrix() -> dict[str, Any]:
    return load_json(MATRIX_PATH)


def refuse_needles(pin: dict[str, Any] | None = None) -> list[str]:
    data = pin or load_pin()
    godot = data.get("godot") if isinstance(data.get("godot"), dict) else {}
    prefixes = godot.get("refuse_version_prefixes")
    if isinstance(prefixes, list):
        return [str(item) for item in prefixes]
    return []


def lock_godot(lock: dict[str, Any]) -> dict[str, Any]:
    godot = lock.get("godot")
    return godot if isinstance(godot, dict) else {}


def pin_ok(lock: dict[str, Any], pin: dict[str, Any] | None = None) -> list[str]:
    errors: list[str] = []
    pin_data = pin or load_pin()
    engine = pin_data.get("godot") if isinstance(pin_data.get("godot"), dict) else {}
    godot = lock_godot(lock)
    if godot.get("tag") != PINNED or engine.get("tag") != PINNED:
        errors.append("lock/pin tag must stay " + PINNED)
    if godot.get("version_id") != PINNED_VERSION:
        errors.append(f"lock version_id {godot.get('version_id')!r} != {PINNED_VERSION}")
    if godot.get("commit_full") != engine.get("commit_full"):
        errors.append("lock commit_full != tools/godot/pin.json")
    if lock.get("mcp_vendor") != "none":
        errors.append("mcp_vendor must stay none")
    if lock.get("patch_queue") != "do-not-patch-vendor":
        errors.append("patch_queue must stay do-not-patch-vendor")
    blob = json.dumps(godot)
    for needle in refuse_needles(pin_data):
        if needle and needle in blob:
            errors.append(f"lock must refuse Godot channel {needle}")
    return errors


def lock_revision(lock: dict[str, Any]) -> int:
    raw = lock.get("lock_revision")
    if isinstance(raw, int) and raw > 0:
        return raw
    return 1


def candidate_lock(old: dict[str, Any]) -> dict[str, Any]:
    new = json.loads(json.dumps(old))
    new["lock_revision"] = lock_revision(old) + 1
    new["compat_note"] = (
        "candidate lock only; Godot pin unchanged; not applied to the repo lock"
    )
    return new


def assess_lock(
    project_root: Path,
    *,
    pin: dict[str, Any] | None = None,
    repo_lock: dict[str, Any] | None = None,
) -> dict[str, Any]:
    reasons: list[str] = []
    planted_protocol = (project_root / ".hh-agent" / "protocol").read_text(
        encoding="utf-8"
    ).strip() if (project_root / ".hh-agent" / "protocol").is_file() else ""
    planted_schema = (project_root / ".hh-agent" / "schema-version").read_text(
        encoding="utf-8"
    ).strip() if (project_root / ".hh-agent" / "schema-version").is_file() else ""
    project_lock_path = project_root / ".hh-agent" / "capability-lock.json"
    project_lock: dict[str, Any] | None = None
    if project_lock_path.is_file():
        project_lock = load_json(project_lock_path)
    if planted_protocol and planted_protocol != PROTOCOL:
        reasons.append(f"protocol {planted_protocol} != {PROTOCOL}")
    if planted_schema and planted_schema != REGISTRY:
        reasons.append(f"schema {planted_schema} != {REGISTRY}")
    if project_lock is not None:
        godot = lock_godot(project_lock)
        version_id = str(godot.get("version_id") or "")
        if version_id and version_id != PINNED_VERSION:
            reasons.append(f"capability-lock {version_id} != pin {PINNED_VERSION}")
        reasons.extend(pin_ok(project_lock, pin))
    mismatch = len(reasons) > 0
    return {
        "mismatch": mismatch,
        "mode": "Observe/Doctor only" if mismatch else "mutate-allowed",
        "reason": (
            "; ".join(reasons) + "; Observe/Doctor only"
            if mismatch
            else "lock matches pin"
        ),
        "protocol": planted_protocol or PROTOCOL,
        "schema": planted_schema or REGISTRY,
        "has_project_lock": project_lock is not None,
        "repo_lock_revision": lock_revision(repo_lock or {}),
    }


def probe_latest(*, fixture: Path | None = None, apply: bool = False) -> dict[str, Any]:
    path = fixture or PROBE_FIXTURE
    data = load_json(path)
    report = {
        "ok": True,
        "blocking": False,
        "approved": False,
        "applied": False,
        "source": str(data.get("source") or "fixture"),
        "pin_tag": PINNED,
        "pin_version_id": PINNED_VERSION,
        "latest_tag": str(data.get("latest_tag") or ""),
        "latest_version_id": str(data.get("latest_version_id") or ""),
        "note": str(data.get("note") or "probe only"),
        "do": "keep the official pin; probe is non-blocking until approved",
    }
    if apply:
        report["ok"] = False
        report["do"] = "refused apply; probe stays non-blocking until an approved WP"
        raise CompatError("probe --apply is refused; latest stable stays unapproved")
    if report["latest_version_id"] == PINNED_VERSION:
        report["note"] = "fixture latest equals pin; still do not auto-bump"
    return report


def required_suites(matrix: dict[str, Any] | None = None) -> list[dict[str, str]]:
    data = matrix or load_matrix()
    raw = data.get("required_suites_before_patch_or_minor")
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    for item in raw:
        if isinstance(item, dict) and item.get("id"):
            out.append({"id": str(item["id"]), "command": str(item.get("command") or "")})
    return out


def suite_gate(suites_path: Path | None) -> dict[str, Any]:
    required = required_suites()
    evidence: dict[str, Any] = {}
    if suites_path is not None and suites_path.is_file():
        loaded = load_json(suites_path)
        raw = loaded.get("suites")
        if isinstance(raw, dict):
            evidence = raw
    missing = [
        item["id"]
        for item in required
        if not (isinstance(evidence.get(item["id"]), dict) and evidence[item["id"]].get("ok") is True)
    ]
    return {
        "required": [item["id"] for item in required],
        "missing": missing,
        "ok": not missing,
        "do": (
            "run contract/E2E/visible/headless/export before any patch/minor apply"
            if missing
            else "suites recorded"
        ),
    }


def mcp_sync_review(repo: Path | None = None) -> dict[str, Any]:
    root = repo or REPO_ROOT
    lock = load_json(root / ".hh-agent" / "capability-lock.json")
    refs = lock.get("reference_shas") if isinstance(lock.get("reference_shas"), dict) else {}
    status = lock.get("g1_status") if isinstance(lock.get("g1_status"), dict) else {}
    pins = {
        "A": root / "third_party" / "mcp-staging" / "satelliteoflove-godot-mcp" / "PIN.json",
        "B": root / "third_party" / "mcp-staging" / "keeveeg-godot-mcp" / "PIN.json",
        "C": root / "third_party" / "mcp-staging" / "beckett-godot-mcp-lite" / "PIN.json",
        "D": root / "third_party" / "mcp-staging" / "sods2-godot-mcp" / "PIN.json",
    }
    diffs: list[str] = []
    licenses_ok = True
    for cid, pin_path in pins.items():
        if not pin_path.is_file():
            diffs.append(f"missing {pin_path.name} for {cid}")
            continue
        staged = load_json(pin_path)
        if str(staged.get("commit") or "") != str(refs.get(cid) or ""):
            diffs.append(f"{cid} SHA drift")
        if staged.get("spdx") != "MIT":
            diffs.append(f"{cid} license not MIT")
        if staged.get("g1") != "never-enable":
            diffs.append(f"{cid} must stay never-enable")
        if staged.get("vendored_source_tree") is not False:
            diffs.append(f"{cid} vendor source must stay false")
        license_path = pin_path.parent / "LICENSE"
        if not license_path.is_file():
            licenses_ok = False
            diffs.append(f"{cid} LICENSE missing")
        if status.get(cid) != "never-enable":
            diffs.append(f"lock g1_status.{cid} must stay never-enable")
    queue = str(lock.get("patch_queue") or "")
    reapplied: list[str] = []
    if queue != "do-not-patch-vendor":
        diffs.append("patch_queue is not do-not-patch-vendor; refuse auto reapply")
    return {
        "ok": not diffs and lock.get("mcp_vendor") == "none" and licenses_ok,
        "mcp_vendor": lock.get("mcp_vendor"),
        "patch_queue": queue,
        "reapplied": reapplied,
        "license_ok": licenses_ok,
        "schema_ownership": lock.get("schema_ownership"),
        "security": "never-enable A/B/C/D; do not vendor",
        "diff": diffs or ["reference SHAs match PIN.json"],
        "do": "review only; reapply minimal patch queue is a no-op while vendor is none",
    }


def session_live(project: Path) -> bool:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return False
    root = Path(local) / "HHGodotAgent" / "sessions"
    if not root.is_dir():
        return False
    want = str(project.resolve())
    for desc in root.glob("*/session.json"):
        try:
            data = json.loads(desc.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        root_s = str(data.get("project_root") or "")
        if root_s and Path(root_s).resolve() == Path(want):
            return True
    return False


def migrate_copy(src: Path, dest: Path, new_lock: dict[str, Any]) -> dict[str, Any]:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest, ignore=COPY_IGNORE)
    dest_lock = dest / ".hh-agent" / "capability-lock.json"
    dump_json(dest_lock, new_lock)
    src_lock = src / ".hh-agent" / "capability-lock.json"
    src_hash = sha256_file(src_lock) if src_lock.is_file() else ""
    dest_hash = sha256_file(dest_lock)
    if src_lock.is_file() and src_hash == dest_hash:
        raise CompatError("migration copy wrote the old lock; new lock missing")
    if src_lock.is_file() and sha256_file(src_lock) != src_hash:
        raise CompatError("migration must not mutate the source lock")
    return {
        "ok": True,
        "src": str(src),
        "dest": str(dest),
        "src_lock_hash": src_hash,
        "dest_lock_hash": dest_hash,
        "lock_revision": lock_revision(new_lock),
        "source_untouched": True,
    }


def downgrade_lock(project: Path, old_lock: dict[str, Any]) -> dict[str, Any]:
    dest_lock = project / ".hh-agent" / "capability-lock.json"
    dump_json(dest_lock, old_lock)
    restored = load_json(dest_lock)
    if lock_revision(restored) != lock_revision(old_lock):
        raise CompatError("downgrade did not restore the old lock revision")
    if lock_godot(restored).get("version_id") != PINNED_VERSION:
        raise CompatError("downgrade must keep the official Godot pin")
    return {
        "ok": True,
        "project": str(project),
        "lock_revision": lock_revision(restored),
        "version_id": lock_godot(restored).get("version_id"),
        "do": "old lock restored on the migration copy only",
    }


def stage_broken_editor(dest: Path, addon: Path) -> dict[str, Any]:
    """Minimal editor project: addon only, no plugin-project copytree, strip .hh-agent."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "project.godot").write_text(BROKEN_PROJECT_GODOT, encoding="utf-8")
    addon_dest = dest / "addons" / "hh_agent"
    addon_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(addon, addon_dest, ignore=COPY_IGNORE)
    planted = plant_broken_api(dest)
    agent_files = [p for p in (dest / ".hh-agent").rglob("*") if p.is_file()]
    if len(agent_files) > 8:
        raise CompatError("broken fixture .hh-agent must stay minimal")
    extras = [
        p
        for p in dest.rglob("*")
        if p.is_file()
        and ".hh-agent" in p.parts
        and p.name
        not in {"protocol", "schema-version", "capability-lock.json", "broken-api.json"}
    ]
    if extras:
        raise CompatError("broken fixture must strip leftover .hh-agent files")
    return {
        **planted,
        "minimal": True,
        "addon_only": True,
        "hh_agent_files": len(agent_files),
    }


def plant_broken_api(project: Path) -> dict[str, Any]:
    agent = project / ".hh-agent"
    agent.mkdir(parents=True, exist_ok=True)
    (agent / "protocol").write_text(BROKEN_PROTOCOL + "\n", encoding="utf-8")
    (agent / "schema-version").write_text(BROKEN_SCHEMA + "\n", encoding="utf-8")
    broken_lock = candidate_lock(load_json(REPO_LOCK))
    broken_lock["godot"] = dict(lock_godot(broken_lock))
    broken_lock["godot"]["version_id"] = "broken.stable.official.deadbeef0"
    broken_lock["godot"]["tag"] = "broken-stable"
    dump_json(agent / "capability-lock.json", broken_lock)
    (agent / "broken-api.json").write_text(
        json.dumps(
            {
                "schema": "hh-godot-broken-api/1",
                "method": "godot.broken",
                "action": "explode",
                "note": "intentionally missing from the registry; Observe/Doctor only",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    assessed = assess_lock(project)
    if not assessed["mismatch"]:
        raise CompatError("broken API fixture must mismatch the pin")
    return {
        "ok": True,
        "project": str(project),
        "protocol": BROKEN_PROTOCOL,
        "schema": BROKEN_SCHEMA,
        "mode": assessed["mode"],
        "reason": assessed["reason"],
    }


def refuse_apply(
    *,
    lock_path: Path,
    suites_path: Path | None,
    project: Path | None,
    approved: bool,
) -> dict[str, Any]:
    reasons: list[str] = []
    if lock_path.resolve() == REPO_LOCK.resolve():
        reasons.append("refuse writing the live repo capability-lock")
    if not approved:
        reasons.append("latest/candidate is not approved")
    gate = suite_gate(suites_path)
    if not gate["ok"]:
        reasons.append("missing suites: " + ",".join(gate["missing"]))
    if project is not None and session_live(project):
        reasons.append("mid-session apply refused")
    if not reasons:
        reasons.append("auto-apply is disabled")
    raise CompatError(
        "apply refused: " + "; ".join(reasons),
        do="Observe/Doctor only; do not bump Godot/dependency mid-session",
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="HH Godot compatibility/update matrix (R9-WP3).")
    p.add_argument(
        "command",
        choices=(
            "pin",
            "probe",
            "suites",
            "mcp-sync",
            "assess",
            "candidate",
            "migrate",
            "downgrade",
            "plant-broken",
            "stage-broken",
            "apply",
        ),
    )
    p.add_argument("--repo", default="", help="repo root")
    p.add_argument("--project", default="", help="Godot project (copy, never the live lock)")
    p.add_argument("--dest", default="", help="migration copy destination")
    p.add_argument("--lock", default="", help="lock JSON path")
    p.add_argument("--old-lock", default="", help="old lock JSON path")
    p.add_argument("--new-lock", default="", help="new/candidate lock JSON path")
    p.add_argument("--fixture", default="", help="probe fixture JSON")
    p.add_argument("--suites", default="", help="suite evidence JSON")
    p.add_argument("--apply", action="store_true", help="refused unless approved+suites; still never auto")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    repo = Path(args.repo).resolve() if args.repo else REPO_ROOT
    try:
        if args.command == "pin":
            lock = load_json(repo / ".hh-agent" / "capability-lock.json")
            errors = pin_ok(lock)
            report = {
                "ok": not errors,
                "pin": PINNED,
                "version_id": PINNED_VERSION,
                "lock_revision": lock_revision(lock),
                "errors": errors,
                "CLEAN_VM": "unproven",
                "provider": "plan",
            }
            emit(json.dumps(report, indent=2))
            return 0 if report["ok"] else 2
        if args.command == "probe":
            fixture = Path(args.fixture) if args.fixture else PROBE_FIXTURE
            report = probe_latest(fixture=fixture, apply=args.apply)
            emit(json.dumps(report, indent=2))
            return 0
        if args.command == "suites":
            report = suite_gate(Path(args.suites) if args.suites else None)
            emit(json.dumps(report, indent=2))
            return 0 if report["ok"] else 2
        if args.command == "mcp-sync":
            report = mcp_sync_review(repo)
            emit(json.dumps(report, indent=2))
            return 0 if report["ok"] else 2
        if args.command == "assess":
            project = Path(args.project).resolve() if args.project else repo
            report = assess_lock(project)
            emit(json.dumps(report, indent=2))
            return 0 if not report["mismatch"] else 2
        if args.command == "candidate":
            old = load_json(Path(args.old_lock) if args.old_lock else repo / ".hh-agent" / "capability-lock.json")
            new = candidate_lock(old)
            dest = Path(args.new_lock) if args.new_lock else Path(args.dest)
            if not dest:
                raise CompatError("--new-lock or --dest required for candidate")
            if dest.suffix.lower() != ".json":
                dest = dest / "new-lock.json"
            dump_json(dest, new)
            emit(json.dumps({"ok": True, "path": str(dest), "lock_revision": lock_revision(new)}, indent=2))
            return 0
        if args.command == "migrate":
            if not args.project or not args.dest:
                raise CompatError("migrate requires --project and --dest")
            src = Path(args.project).resolve()
            dest = Path(args.dest).resolve()
            if dest.resolve() == src.resolve():
                raise CompatError("migrate must be a project copy, not in-place")
            old = load_json(Path(args.old_lock) if args.old_lock else REPO_LOCK)
            new = load_json(Path(args.new_lock)) if args.new_lock else candidate_lock(old)
            report = migrate_copy(src, dest, new)
            emit(json.dumps(report, indent=2))
            return 0
        if args.command == "downgrade":
            if not args.project or not args.old_lock:
                raise CompatError("downgrade requires --project and --old-lock")
            old = load_json(Path(args.old_lock))
            report = downgrade_lock(Path(args.project).resolve(), old)
            emit(json.dumps(report, indent=2))
            return 0
        if args.command == "plant-broken":
            if not args.project:
                raise CompatError("plant-broken requires --project")
            report = plant_broken_api(Path(args.project).resolve())
            emit(json.dumps(report, indent=2))
            return 0
        if args.command == "stage-broken":
            if not args.project:
                raise CompatError("stage-broken requires --project")
            addon = repo / ADDON_REL
            if not addon.is_dir():
                raise CompatError(f"missing addon {addon}")
            report = stage_broken_editor(Path(args.project).resolve(), addon)
            emit(json.dumps(report, indent=2))
            return 0
        if args.command == "apply":
            lock_path = Path(args.lock).resolve() if args.lock else REPO_LOCK
            suites = Path(args.suites) if args.suites else None
            project = Path(args.project).resolve() if args.project else None
            refuse_apply(
                lock_path=lock_path,
                suites_path=suites,
                project=project,
                approved=False,
            )
        raise CompatError(f"unknown command {args.command}")
    except CompatError as exc:
        emit(json.dumps({"ok": False, "error": str(exc), "do": exc.do}, indent=2))
        print(f"compat: FAIL: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
