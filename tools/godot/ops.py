#!/usr/bin/env python3
"""R9-WP4 operations: backup/restore, logs, crash recover, token rotate, drill.

Does not tick the 20-8 plan. Does not start Superfighter.
Does not tick G6 or GX. Does not invent an API key or a signing cert.
--provider plan stays. Unsigned internal only; public sign/publish is E3.
Does not invent Hyper-V. Does not stamp CLEAN_VM as proven.
Does not stamp GATES as proven. Does not stamp DRILL as proven.
Does not stamp REVIEWER as proven. Does not stamp EVIDENCE as proven.
Does not create a folder named clean-vm. unsigned internal only.
Stdlib only. Isolated --home; does not copy a live owner session store.
backup must not ship raw tokens. rotate-token --live targets leftover
%LOCALAPPDATA%/HHGodotAgent/sessions. wipe-tokens after official.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import studio_bundle as studio

SCHEMA = "hh-godot-ops-drill/1"
CATALOG_SCHEMA = "hh-godot-release-gates/1"
PINNED = "4.7.1-stable"
PINNED_VERSION = "4.7.1.stable.official.a13da4feb"
V1 = "0.9.4-r9w4a"
V2 = "0.9.4-r9w4b"
GATES_FILE = HERE / "release_gates.json"
REPO_DEFAULT = HERE.parents[1]


class OpsError(RuntimeError):
    def __init__(self, message: str, *, do: str = "", code: str = "E_OPS") -> None:
        super().__init__(message)
        self.do = do
        self.code = code


def emit(text: str) -> None:
    stream = sys.stdout
    encoding = getattr(stream, "encoding", None) or "utf-8"
    stream.write(text.encode(encoding, errors="replace").decode(encoding, errors="replace"))
    stream.write("\n")


def refuse_e3(action: str) -> None:
    raise OpsError(
        f"{action} is E3",
        code="E_EXTERNAL",
        do="unsigned internal build is allowed; public sign/upload/channel needs a human — do not invent a cert",
    )


def refuse_proven_vm() -> None:
    raise OpsError(
        "CLEAN_VM stays unproven",
        code="E_POLICY",
        do="this Godot/Node/source machine is not a clean VM; do not invent Hyper-V; G6 owns the real VM",
    )


def default_home() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise OpsError("LOCALAPPDATA missing", do="run as the current Windows user")
    return Path(local) / "HHGodotAgent" / "release" / "r9-wp4"


def home_of(raw: str) -> Path:
    path = Path(raw).resolve() if raw else default_home()
    studio.refuse_admin_dest(path)
    blob = str(path).replace("\\", "/").lower()
    if "clean-vm" in blob or "clean_vm" in blob:
        raise OpsError(
            "refusing a clean-vm path",
            do="do not copy the exe into a folder named clean-vm; CLEAN_VM stays unproven",
        )
    return path


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def install_root_of(home: Path) -> Path:
    return home / "install"


def user_project_of(home: Path) -> Path:
    return home / "user-project"


def agent_home_of(home: Path) -> Path:
    return home / "agent-home"


def sessions_root_of(home: Path) -> Path:
    return agent_home_of(home) / "sessions"


def session_path_of(home: Path, project: Path) -> Path:
    return sessions_root_of(home) / studio.project_id_for(project) / "session.json"


def backup_root_of(home: Path) -> Path:
    return home / "backup"


def raw_logs_of(home: Path) -> Path:
    return home / "agent-home" / "logs" / "raw"


def collected_of(home: Path) -> Path:
    return home / "collected-logs"


def crash_path_of(home: Path) -> Path:
    return home / "crash" / "applying.json"


def plant_sk() -> str:
    return "sk-" + ("drillfixture" + "aaaaaaaaaa")


def plant_ghp() -> str:
    return "ghp_" + ("drillfixture" + "bbbbbbbbbb")


def redact_text(text: str, secrets: list[str]) -> str:
    out = text
    for secret in secrets:
        if secret and len(secret) >= 8 and secret in out:
            out = out.replace(secret, "[redacted]")
    home = os.environ.get("USERPROFILE") or ""
    local = os.environ.get("LOCALAPPDATA") or ""
    for path in (home, local):
        if path and len(path) >= 8:
            out = out.replace(path, "[redacted-home]")
            out = out.replace(path.replace("\\", "/"), "[redacted-home]")
    out = re.sub(r"\bsk-[A-Za-z0-9]{20,}", "[redacted]", out)
    out = re.sub(r"\bghp_[A-Za-z0-9]{20,}", "[redacted]", out)
    out = re.sub(r"\bHH_TOKEN=\S+", "HH_TOKEN=[redacted]", out)
    out = re.sub(r"\b[0-9a-f]{64}\b", "[redacted]", out)
    return out


def live_sessions_root() -> Path | None:
    return studio.sessions_root()


def hh_agent_root() -> Path | None:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None
    return Path(local) / "HHGodotAgent"


def session_files_under(*roots: Path | None) -> list[Path]:
    found: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        if root is None:
            continue
        try:
            exists = root.exists()
        except OSError:
            continue
        if not exists:
            continue
        paths: list[Path] = []
        if root.is_file() and root.name == "session.json":
            paths.append(root)
        elif root.is_dir():
            paths.extend(root.rglob("session.json"))
        for path in paths:
            key = str(path.resolve()).replace("\\", "/").lower()
            if key in seen:
                continue
            seen.add(key)
            found.append(path)
    return found


def session_token_of(path: Path) -> str:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(data, dict):
        return ""
    return str(data.get("token") or "")


def leftover_token_files(*roots: Path | None) -> list[Path]:
    return [path for path in session_files_under(*roots) if session_token_of(path)]


def write_session_path(path: Path, token: str, extra: dict[str, Any] | None = None) -> Path:
    payload: dict[str, Any] = {
        "schema": "hh-godot-session/1",
        "token": token,
        "bind": "127.0.0.1",
        "note": "session secret only; not an API key; --provider plan stays",
    }
    if extra:
        payload.update(extra)
        payload["token"] = token
    atomic_write_json(path, payload)
    return path


def write_session(home: Path, project: Path, token: str) -> Path:
    path = session_path_of(home, project)
    return write_session_path(
        path,
        token,
        {
            "project_id": studio.project_id_for(project),
            "project_root": studio.canonical_project_root(project),
            "note": "isolated drill session; not an API key; --provider plan stays",
        },
    )


def rotate_session_path(path: Path) -> bool:
    extra: dict[str, Any] = {}
    old = ""
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            loaded = {}
        if isinstance(loaded, dict):
            extra = {key: value for key, value in loaded.items() if key != "token"}
            old = str(loaded.get("token") or "")
    new = secrets.token_hex(32)
    extra["note"] = "session secret only; not an API key; --provider plan stays"
    write_session_path(path, new, extra)
    text = path.read_text(encoding="utf-8")
    if old and old in text:
        raise OpsError("previous token still in session.json", do="rewrite the session only")
    if new not in text:
        raise OpsError("new token missing", do="retry rotate-token")
    return bool(old)


def wipe_session_file(path: Path) -> bool:
    """Remove a plaintext token. Returns True if a token was present."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    old = str(data.get("token") or "")
    if not old:
        return False
    data["token"] = ""
    data["token_redacted"] = True
    data["note"] = "token wiped after official; not an API key; --provider plan stays"
    atomic_write_json(path, data)
    if old in path.read_text(encoding="utf-8"):
        raise OpsError("token still in session.json after wipe", do="delete the leftover session.json")
    return True


def read_session(home: Path, project: Path) -> dict[str, Any]:
    path = session_path_of(home, project)
    if not path.is_file():
        raise OpsError("session.json missing", do="run the drill or rotate-token after backup")
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def plant_raw_log(home: Path, token: str) -> Path:
    raw = raw_logs_of(home)
    raw.mkdir(parents=True, exist_ok=True)
    path = raw / "sidecar.log"
    local = os.environ.get("LOCALAPPDATA") or "LOCALAPPDATA"
    body = "\n".join(
        [
            "ops drill raw log — must be redacted before handoff",
            f"session token={token}",
            f"home={local}",
            f"planted {plant_sk()}",
            f"planted {plant_ghp()}",
            "HH_TOKEN=" + token,
            "--provider plan stays",
        ]
    )
    atomic_write_text(path, body + "\n")
    return path


def backup(home: Path) -> dict[str, Any]:
    dest = backup_root_of(home)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    install = install_root_of(home)
    current = install / "current"
    if not (current / "manifest.json").is_file():
        raise OpsError("studio current/ missing", do="run ops.py drill or install.py setup first")
    studio.verify_bundle(current)
    shutil.copytree(current, dest / "install" / "current")
    state = install / "state.json"
    if state.is_file():
        shutil.copy2(state, dest / "install" / "state.json")
    project = user_project_of(home)
    agent = project / ".hh-agent"
    if agent.is_dir():
        shutil.copytree(agent, dest / "user-project-hh-agent")
    secrets: list[str] = []
    live_session = session_path_of(home, project)
    if live_session.is_file():
        token = session_token_of(live_session)
        if token:
            secrets.append(token)
    sessions = sessions_root_of(home)
    if sessions.is_dir():
        shutil.copytree(sessions, dest / "sessions")
        for copied in (dest / "sessions").rglob("session.json"):
            wipe_session_file(copied)
    raw = raw_logs_of(home)
    if raw.is_dir():
        dest_logs = dest / "logs-raw"
        dest_logs.mkdir(parents=True, exist_ok=True)
        for src in raw.glob("*"):
            if not src.is_file():
                continue
            cleaned = redact_text(src.read_text(encoding="utf-8", errors="replace"), secrets)
            atomic_write_text(dest_logs / src.name, cleaned)
    sidecar = current / "sidecar" / "main.js"
    payload = {
        "schema": SCHEMA,
        "kind": "backup",
        "clean_vm": "unproven",
        "not_g6": 1,
        "signing": "unsigned",
        "version": studio.read_stamp(current),
        "sidecar_sha256": sha256_file(sidecar) if sidecar.is_file() else "",
        "project": str(project),
    }
    atomic_write_json(dest / "manifest.json", payload)
    return payload


def restore(home: Path) -> dict[str, Any]:
    src = backup_root_of(home)
    manifest_path = src / "manifest.json"
    if not manifest_path.is_file():
        raise OpsError("backup missing", do="python tools/godot/ops.py backup --home <home>")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    backup_current = src / "install" / "current"
    if not (backup_current / "manifest.json").is_file():
        raise OpsError("backup install/current missing", do="re-run backup")
    studio.verify_bundle(backup_current)
    install = install_root_of(home)
    current = install / "current"
    tmp = install / "restore-tmp"
    if tmp.exists():
        shutil.rmtree(tmp)
    shutil.copytree(backup_current, tmp)
    studio.verify_bundle(tmp)
    if current.exists():
        shutil.rmtree(current)
    tmp.replace(current)
    state_src = src / "install" / "state.json"
    if state_src.is_file():
        shutil.copy2(state_src, install / "state.json")
    project = user_project_of(home)
    agent_src = src / "user-project-hh-agent"
    if agent_src.is_dir():
        dest_agent = project / ".hh-agent"
        if dest_agent.exists():
            shutil.rmtree(dest_agent)
        shutil.copytree(agent_src, dest_agent)
    sessions_src = src / "sessions"
    if sessions_src.is_dir():
        dest_sessions = sessions_root_of(home)
        if dest_sessions.exists():
            shutil.rmtree(dest_sessions)
        shutil.copytree(sessions_src, dest_sessions)
    sidecar = current / "sidecar" / "main.js"
    expected = str(manifest.get("sidecar_sha256") or "")
    actual = sha256_file(sidecar) if sidecar.is_file() else ""
    if expected and actual != expected:
        raise OpsError(
            "restore hash mismatch",
            code="E_UNCERTAIN",
            do="do not report success; keep the backup and Pause",
        )
    studio.verify_bundle(current)
    return {
        "ok": True,
        "version": studio.read_stamp(current),
        "sidecar_sha256": actual,
        "clean_vm": "unproven",
    }


def recover(home: Path) -> dict[str, Any]:
    crash = crash_path_of(home)
    marker: dict[str, Any] = {}
    if crash.is_file():
        try:
            marker = json.loads(crash.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            marker = {"state": "uncertain"}
    try:
        restored = restore(home)
    except OpsError as exc:
        if exc.code == "E_UNCERTAIN":
            return {
                "ok": False,
                "code": "E_UNCERTAIN",
                "state": "uncertain",
                "clean_vm": "unproven",
                "message": str(exc),
            }
        raise
    if crash.is_file():
        crash.unlink()
    return {
        "ok": True,
        "code": "committed_durable",
        "state": "committed_durable",
        "before": marker.get("state") or "none",
        "version": restored.get("version"),
        "clean_vm": "unproven",
    }


def rotate_token(home: Path, *, live: bool = False) -> dict[str, Any]:
    if live:
        root = live_sessions_root()
        targets = leftover_token_files(root) or session_files_under(root)
        rotated = 0
        had_previous = False
        for path in targets:
            if rotate_session_path(path):
                had_previous = True
            rotated += 1
        rotation = {
            "schema": SCHEMA,
            "kind": "token-rotation-live",
            "rotated": rotated,
            "note": "live leftover path %LOCALAPPDATA%/HHGodotAgent/sessions; not an API key",
            "clean_vm": "unproven",
        }
        if home is not None:
            atomic_write_json(home / "agent-home" / "rotation-live.json", rotation)
        if rotated == 0:
            raise OpsError(
                "no live leftover session.json to rotate",
                do="python tools/godot/ops.py rotate-token --live after a leftover exists",
            )
        return {"ok": True, "rotated": rotated, "had_previous": had_previous, "live": True, "clean_vm": "unproven"}
    project = user_project_of(home)
    path = session_path_of(home, project)
    old = session_token_of(path) if path.is_file() else ""
    if path.is_file():
        rotate_session_path(path)
    else:
        write_session(home, project, secrets.token_hex(32))
    rotation = {
        "schema": SCHEMA,
        "kind": "token-rotation",
        "previous_token_sha256": sha256_text(old) if old else "",
        "note": "session secret only; not an API key; plaintext previous token discarded",
        "clean_vm": "unproven",
    }
    atomic_write_json(home / "agent-home" / "rotation.json", rotation)
    return {"ok": True, "rotated": True, "had_previous": bool(old), "live": False, "clean_vm": "unproven"}


def wipe_tokens(home: Path | None, *, live: bool = False) -> dict[str, Any]:
    roots: list[Path | None] = []
    if home is not None:
        roots.extend(
            [
                sessions_root_of(home),
                backup_root_of(home) / "sessions",
                home / "agent-home" / "sessions",
            ]
        )
    if live:
        roots.append(live_sessions_root())
        roots.append(hh_agent_root())
    wiped = 0
    unwritable = 0
    for path in session_files_under(*roots):
        try:
            if wipe_session_file(path):
                wiped += 1
        except (OSError, OpsError):
            unwritable += 1
    leftover = leftover_token_files(*roots)
    return {
        "ok": not leftover and unwritable == 0,
        "wiped": wiped,
        "leftover": len(leftover),
        "unwritable": unwritable,
        "clean_vm": "unproven",
    }


def collect_logs(home: Path) -> dict[str, Any]:
    secrets: list[str] = []
    project = user_project_of(home)
    path = session_path_of(home, project)
    if path.is_file():
        token = str(read_session(home, project).get("token") or "")
        if token:
            secrets.append(token)
    dest = collected_of(home)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    leaked = 0
    copied = 0
    for src in raw_logs_of(home).glob("*"):
        if not src.is_file():
            continue
        text = src.read_text(encoding="utf-8", errors="replace")
        cleaned = redact_text(text, secrets)
        atomic_write_text(dest / src.name, cleaned)
        copied += 1
        for secret in secrets:
            if secret and secret in cleaned:
                leaked += 1
        if plant_sk() in cleaned or plant_ghp() in cleaned:
            leaked += 1
        if re.search(r"\b[0-9a-f]{64}\b", cleaned):
            leaked += 1
    report = {
        "schema": SCHEMA,
        "kind": "collect-logs",
        "files": copied,
        "leaked": leaked,
        "clean_vm": "unproven",
        "not_g6": 1,
    }
    atomic_write_json(dest / "redaction-report.json", report)
    if leaked:
        raise OpsError("collected logs still contain secrets", do="do not hand off raw logs")
    return report


def load_gates() -> dict[str, Any]:
    data = json.loads(GATES_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != CATALOG_SCHEMA:
        raise OpsError("release_gates.json schema mismatch")
    if data.get("clean_vm") == "proven":
        raise OpsError("catalog must not stamp CLEAN_VM proven")
    return data


def catalog(repo: Path, home: Path | None = None) -> dict[str, Any]:
    spec = load_gates()
    plan = (repo / "zdocs" / "20-8-godot-agent-autopilot-plan.txt").read_text(encoding="utf-8")
    errors: list[str] = []
    resolved: list[str] = []
    for gate in spec.get("gates") or []:
        gid = str(gate.get("id") or "")
        status = str(gate.get("status") or "")
        if gid == "G6":
            if status != "unresolved":
                errors.append("G6 must stay unresolved until a real clean VM")
            if re.search(r"G6 RELEASE\s+\[x\]", plan, re.I):
                errors.append("plan G6 is ticked; official ops must not tick G6")
        elif gid == "GX":
            if status != "locked":
                errors.append("GX must stay locked")
            if re.search(r"GX FORK\s+\[x\]", plan, re.I):
                errors.append("plan GX is ticked; official ops must not touch GX")
        elif status != "resolved":
            errors.append(f"{gid} expected resolved, got {status}")
        for rel in gate.get("artifacts") or []:
            path = repo / str(rel)
            if not path.exists():
                errors.append(f"{gid} missing artifact {rel}")
            else:
                resolved.append(f"{gid}:{rel}")
        for rel in gate.get("optional_artifacts") or []:
            path = repo / str(rel)
            if path.exists():
                resolved.append(f"{gid}:{rel}:optional")
    for row in spec.get("acceptance") or []:
        aid = str(row.get("id") or "")
        status = str(row.get("status") or "")
        if aid == "AC-20" and status != "unproven":
            errors.append("AC-20 must stay unproven without a real clean VM")
        if aid == "AC-22" and status != "unproven":
            errors.append("AC-22 must stay unproven without a clean clone")
        if aid == "AC-21" and status not in {"partial", "unproven"}:
            errors.append("AC-21 must not claim clean-VM proven")
    report = {
        "schema": CATALOG_SCHEMA,
        "ok": not errors,
        "clean_vm": "unproven",
        "not_g6": 1,
        "signing": "unsigned",
        "gx": "locked",
        "resolved": resolved,
        "errors": errors,
        "g6": "unresolved",
    }
    if home is not None:
        atomic_write_json(home / "catalog-report.json", report)
    if errors:
        raise OpsError("catalog did not resolve honestly: " + "; ".join(errors))
    return report


def plant_crash(home: Path) -> None:
    current = install_root_of(home) / "current"
    sidecar = current / "sidecar" / "main.js"
    before = sha256_file(sidecar) if sidecar.is_file() else ""
    atomic_write_json(
        crash_path_of(home),
        {
            "schema": SCHEMA,
            "state": "applying",
            "command_id": "01R9WP4DRILL00000000000001",
            "before_sha256": before,
            "note": "crash in applying; recover must restore or E_UNCERTAIN — never skip-PASS",
        },
    )
    if sidecar.is_file():
        sidecar.write_bytes(sidecar.read_bytes() + b"\n//ops-crash-corrupt\n")


def drill(repo: Path, home: Path) -> dict[str, Any]:
    if home.exists():
        shutil.rmtree(home, ignore_errors=True)
    home.mkdir(parents=True, exist_ok=True)
    bundle_a = home / "bundle-a"
    bundle_b = home / "bundle-b"
    install = install_root_of(home)
    project = user_project_of(home)
    studio.build_package(repo, bundle_a, V1)
    studio.build_package(repo, bundle_b, V2)
    studio.setup(bundle_a, install, project)
    studio.install_bundle(bundle_b, install)
    token = secrets.token_hex(32)
    write_session(home, project, token)
    plant_raw_log(home, token)
    backup_info = backup(home)
    if leftover_token_files(backup_root_of(home) / "sessions"):
        raise OpsError("backup must not ship raw tokens", do="redact session.json before handoff")
    plant_crash(home)
    recovered = recover(home)
    if not recovered.get("ok"):
        raise OpsError(
            f"recover failed: {recovered.get('code')}",
            code=str(recovered.get("code") or "E_UNCERTAIN"),
            do="do not report success",
        )
    rotated = rotate_token(home)
    logs = collect_logs(home)
    rolled = studio.rollback_install(install)
    if studio.read_stamp(install / "current") != V1:
        raise OpsError(
            f"rollback version {studio.read_stamp(install / 'current')} != {V1}",
            do="keep one previous studio version",
        )
    gates = catalog(repo, home)
    if backup_info.get("clean_vm") == "proven" or gates.get("clean_vm") == "proven":
        refuse_proven_vm()
    report = {
        "schema": SCHEMA,
        "ok": True,
        "clean_vm": "unproven",
        "not_g6": 1,
        "signing": "unsigned",
        "e3": "human",
        "gx": "locked",
        "provider": "plan",
        "pin": PINNED,
        "godot": PINNED_VERSION,
        "backup": "ok",
        "restore": "ok",
        "recover": "ok",
        "rotate": "ok" if rotated.get("rotated") else "fail",
        "redact": "ok" if logs.get("leaked") == 0 else "fail",
        "rollback": "ok",
        "catalog": "ok" if gates.get("ok") else "fail",
        "version_after_rollback": studio.read_stamp(install / "current"),
        "home": str(home),
    }
    atomic_write_json(home / "drill-report.json", report)
    return report


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="HH Godot Agent operations handoff (R9-WP4).")
    p.add_argument(
        "command",
        choices=(
            "backup",
            "restore",
            "recover",
            "rotate-token",
            "wipe-tokens",
            "collect-logs",
            "catalog",
            "drill",
            "sign",
            "upload",
            "publish",
        ),
    )
    p.add_argument("--home", default="", help="isolated ops home (default LocalAppData release/r9-wp4)")
    p.add_argument("--repo", default="", help="repo root")
    p.add_argument("--sign", action="store_true", help="refused: signing is E3")
    p.add_argument("--upload", action="store_true", help="refused: publish is E3")
    p.add_argument("--clean-vm-proven", action="store_true", help="refused: CLEAN_VM stays unproven")
    p.add_argument("--hyperv", action="store_true", help="refused: do not invent Hyper-V")
    p.add_argument(
        "--live",
        action="store_true",
        help="rotate or wipe the live leftover %LOCALAPPDATA%/HHGodotAgent/sessions path",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.sign or args.command == "sign":
            refuse_e3("signing")
        if args.upload or args.command in {"upload", "publish"}:
            refuse_e3("upload/publish")
        if args.clean_vm_proven:
            refuse_proven_vm()
        if args.hyperv:
            raise OpsError("do not invent Hyper-V", do="G6 owns a real clean VM; this machine is not one")
        repo = studio.repo_root(Path(args.repo) if args.repo else REPO_DEFAULT)
        home = home_of(args.home)
        if args.command == "backup":
            payload = backup(home)
            emit(f"ops: PASS backup version={payload.get('version')} CLEAN_VM stays unproven")
            return 0
        if args.command == "restore":
            payload = restore(home)
            emit(f"ops: PASS restore version={payload.get('version')} CLEAN_VM stays unproven")
            return 0
        if args.command == "recover":
            payload = recover(home)
            if not payload.get("ok"):
                emit(f"ops: FAIL recover {payload.get('code')} CLEAN_VM stays unproven")
                return 1
            emit(f"ops: PASS recover state={payload.get('state')} CLEAN_VM stays unproven")
            return 0
        if args.command == "rotate-token":
            payload = rotate_token(home, live=bool(args.live))
            scope = "live leftover path" if payload.get("live") else "isolated home"
            emit(
                f"ops: PASS rotate-token ({scope}; session secret, not an API key) "
                "CLEAN_VM stays unproven"
            )
            return 0 if payload.get("ok") else 1
        if args.command == "wipe-tokens":
            payload = wipe_tokens(home, live=bool(args.live))
            emit(
                f"ops: PASS wipe-tokens wiped={payload.get('wiped')} "
                f"leftover={payload.get('leftover')} CLEAN_VM stays unproven"
            )
            return 0 if payload.get("ok") else 1
        if args.command == "collect-logs":
            payload = collect_logs(home)
            emit(f"ops: PASS collect-logs files={payload.get('files')} leaked=0 CLEAN_VM stays unproven")
            return 0
        if args.command == "catalog":
            payload = catalog(repo, home)
            emit(
                "ops: PASS catalog G0-G5 resolved G6=unresolved GX=locked "
                "GATES stays unproven CLEAN_VM stays unproven not_g6=1"
            )
            emit(json.dumps({"ok": payload.get("ok"), "g6": "unresolved", "clean_vm": "unproven"}, sort_keys=True))
            return 0
        if args.command == "drill":
            payload = drill(repo, home)
            emit(
                "ops: PASS disaster drill; "
                f"backup={payload.get('backup')} restore={payload.get('restore')} "
                f"recover={payload.get('recover')} rotate={payload.get('rotate')} "
                f"redact={payload.get('redact')} rollback={payload.get('rollback')}"
            )
            emit(
                f"ops: pin={PINNED} signing=unsigned e3=human "
                "CLEAN_VM stays unproven not_g6=1 HUMAN=unproven"
            )
            emit(json.dumps({k: payload[k] for k in ("ok", "clean_vm", "not_g6", "version_after_rollback")}, sort_keys=True))
            return 0
    except (OpsError, studio.BundleError) as exc:
        emit(f"ops: FAIL: {exc}")
        do = getattr(exc, "do", "")
        if do:
            emit(f"ops: do: {do}")
        return 2 if getattr(exc, "code", "") == "E_EXTERNAL" else 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
