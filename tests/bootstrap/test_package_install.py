#!/usr/bin/env python3
"""R9-WP2: package addon/sidecar + current-user install/doctor/rollback.

Does not tick the 20-8 plan. Does not change CURRENT_VALID_WP.
Keep R9-WP2 [ ]; CURRENT_VALID_WP=R9-WP2; progress stays 57/60.
Does not start R9-WP3. Does not start Superfighter.
Does not tick G6 or GX. Does not invent an API key. --provider plan stays.
Does not poke relic_reached. Does not regress kho-bi-an or R9-WP1 export honesty.
No snake demo. No r7w6 trial. No secret material. No skip-PASS.
Does not invent Hyper-V. Does not stamp CLEAN_VM=proven on this Godot/Node machine.

Official verify (plan R9-WP2 Verify, Godot §7.3 sequential):
  kill leftover Godot first
  package exact addon/sidecar/launcher/checksum/licenses
  current-user install (no admin)
  connect installed sidecar + plugin_noop against the pin Godot
  (Godot is not in the WP2 zip; pin+doctor is OK). Host is the
  bundled launcher, not the git tree.
  create a runnable microgame stub via the live editor (not two empty Node2Ds)
  uninstall keeps the user project and removes session.json tokens
  rollback one previous version
  tampered hash reject including sidecar/main.js and manifest.json
  CLEAN_VM stays unproven; this Godot/Node machine is not a clean VM.
  Do not map WP2 Verify to AC-20 (AC-20 is export, G6). not_g6=1

Labels: INSTALL, CONNECT, MICROGAME, UNINSTALL, ROLLBACK, TAMPER, CLEAN_VM
"""

from __future__ import annotations

import importlib.util
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
import test_scene_lifecycle as life
import test_session as sess

PLAN = REPO_ROOT / "zdocs" / "20-8-godot-agent-autopilot-plan.txt"
DOGFOOD = REPO_ROOT / "godot" / "dogfood" / "kho-bi-an"
PLUGIN_PROJECT = REPO_ROOT / "godot" / "plugin-project"
ADDON = PLUGIN_PROJECT / "addons" / "hh_agent"
TOOLS = REPO_ROOT / "tools" / "godot"
STUDIO = TOOLS / "studio_bundle.py"
PACKAGE_PY = TOOLS / "package.py"
INSTALL_PY = TOOLS / "install.py"
LAUNCH_PY = TOOLS / "launch.py"
EXPORT_TOOL = TOOLS / "export_job.py"
PINNED_VERSION = "4.7.1.stable.official.a13da4feb"
PINNED = "4.7.1-stable"
LABELS = ("INSTALL", "CONNECT", "MICROGAME", "UNINSTALL", "ROLLBACK", "TAMPER", "CLEAN_VM")
REQUIRED_PROVEN = ("INSTALL", "CONNECT", "MICROGAME", "UNINSTALL", "ROLLBACK", "TAMPER")
MICRO_SCENE = "res://scenes/micro.tscn"
MICRO_SCRIPT = "res://scripts/micro.gd"
MICRO_STUB = (
    "extends Node2D\n"
    "\n"
    "func _ready() -> void:\n"
    "	var hint: Label = get_node_or_null(\"Hint\") as Label\n"
    "	if hint != null:\n"
    "		hint.text = \"micro-stub\"\n"
    "\n"
    "func stub_ready() -> String:\n"
    "	return \"micro-stub\"\n"
)
VARIANT_SCHEMA = "hh-godot-variant/1"
V1 = "0.9.2"
V2 = "0.9.2-b"


def official_home() -> Path:
    local = os.environ.get("LOCALAPPDATA", "")
    if not local:
        raise RuntimeError("LOCALAPPDATA missing")
    return Path(local) / "HHGodotAgent" / "packages" / "r9-wp2"


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


def load_studio():
    spec = importlib.util.spec_from_file_location("studio_bundle", STUDIO)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load studio_bundle.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def plan_errors(text: str) -> list[str]:
    errors: list[str] = []
    current = ""
    wp2 = None
    g6 = None
    gx = None
    total = None
    r9_row = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R9-WP2\b", stripped):
            wp2 = stripped
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
    if current != "R9-WP2":
        errors.append(f"CURRENT_VALID_WP={current!r} (must stay R9-WP2)")
    if wp2 is None:
        errors.append("plan missing R9-WP2 heading")
    elif re.search(r"\[x\]", wp2, re.I):
        errors.append("R9-WP2 must stay unticked")
    if total and "57/60" not in total:
        errors.append(f"progress must stay 57/60 while R9-WP2 is unticked: {total}")
    if r9_row and not re.search(r"\[\s*\]\s*1/4", r9_row):
        errors.append(f"R9 row must stay 1/4 while WP2 is unticked: {r9_row}")
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
    if "CLEAN_VM stays unproven" not in self_text:
        errors.append("official test must keep CLEAN_VM=unproven")
    if "LOCALAPPDATA" not in self_text or "HHGodotAgent" not in self_text:
        errors.append("official test must use LocalAppData packages")
    if "4.7." + "2" in self_text:
        errors.append("official test must refuse Godot 4.7." + "2 pin")
    if ("relic_reached" + " =") in self_text:
        errors.append("official test must not assign relic_reached")
    if "kill leftover Godot first" not in self_text:
        errors.append("official test must kill leftover Godot first")
    if ("real clean VM is G6/" + "AC-20") in self_text or ("Real clean VM remains G6 / " + "AC-20") in self_text:
        errors.append("official test must not map WP2 Verify to AC-20")
    if "sidecar-bytes-flip" not in self_text:
        errors.append("official TAMPER must include a sidecar-bytes flip")
    if "leftover_session_tokens" not in self_text:
        errors.append("official test must check leftover session.json tokens")
    if "stub_ready" not in self_text or "ColorRect" not in self_text:
        errors.append("official MICROGAME must be more than two empty Node2Ds")
    install_md = REPO_ROOT / "docs" / "godot-agent" / "INSTALL.md"
    if install_md.is_file():
        install_text = install_md.read_text(encoding="utf-8")
        if ("Real clean VM remains G6 / " + "AC-20") in install_text or ("VM is " + "AC-20") in install_text:
            errors.append("INSTALL.md must not map WP2 VM to AC-20")
    for path in (STUDIO, PACKAGE_PY, INSTALL_PY, LAUNCH_PY):
        if not path.is_file():
            errors.append(f"missing {rel(path)}")
            continue
        text = path.read_text(encoding="utf-8")
        if "4.7." + "2" in text and "refuse" not in text.lower():
            errors.append(f"{rel(path)} must refuse Godot 4.7." + "2")
        if "CLEAN_VM=proven" in text:
            errors.append(f"{rel(path)} must not stamp CLEAN_VM=proven")
        if "PrivilegesRequired=admin" in text:
            errors.append(f"{rel(path)} must stay current-user")
        if "/releases/latest" in text and "refuse" not in text.lower() and "does not use" not in text.lower():
            errors.append(f"{rel(path)} must not bootstrap /releases/latest")
    studio_text = STUDIO.read_text(encoding="utf-8") if STUDIO.is_file() else ""
    for needle in (
        "current-user",
        "checksum reject",
        "Observe/Doctor only",
        "unsigned",
        "E3",
        "no online-latest",
        "rollback",
        "parse_checksums",
        "checksums.txt missing sidecar/main.js",
        "checksums.txt missing manifest.json",
        "purge_project_sessions",
        "host_sidecar_lookup_ok",
    ):
        if needle not in studio_text:
            errors.append(f"studio_bundle.py must mention {needle}")
    if not ADDON.is_dir():
        errors.append("missing canonical hh_agent addon")
    if (REPO_ROOT / "godot" / "superfighter").exists() or (REPO_ROOT / "godot" / "dogfood" / "superfighter").exists():
        errors.append("must not start a Superfighter folder")
    return errors


def banner_for(labels: dict[str, str]) -> str:
    return "; ".join(f"{k}={labels[k]}" for k in LABELS)


def leftover_count(export_job, project: Path) -> int:
    return int(export_job.leftover_godot_count(project))


def kill_project(export_job, project: Path) -> int:
    export_job.kill_godot_for_project(project)
    n = leftover_count(export_job, project)
    if n != 0:
        export_job.kill_godot_for_project(project)
        n = leftover_count(export_job, project)
    return n


def kill_known(export_job, extra: Path | None = None) -> int:
    leftover = 0
    leftover += kill_project(export_job, DOGFOOD)
    leftover += kill_project(export_job, PLUGIN_PROJECT)
    if extra is not None:
        leftover += kill_project(export_job, extra)
    export_job.kill_leftover_game()
    return leftover


def find_pinned_godot() -> tuple[Path | None, str]:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None, "LOCALAPPDATA missing"
    exe = (
        Path(local)
        / "HHGodotAgent"
        / "tooling"
        / "godot-4.7.1-stable"
        / "bin"
        / "Godot_v4.7.1-stable_win64_console.exe"
    )
    if not exe.is_file():
        return None, "pinned 4.7.1-stable console exe is not installed"
    return exe, PINNED_VERSION


def run_godot(exe: Path, args: list[str], cwd: Path, timeout: float) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("HH_AGENT_SELFTEST", None)
    env.pop("HH_AGENT_SELFTEST_OUT", None)
    env.pop("HH_AGENT_RELOAD_N", None)
    env.pop("HH_READ_OPEN_SCENE", None)
    return subprocess.run(
        [str(exe), *args],
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=env,
    )


def start_sidecar(main_js: Path, project: Path):
    proc = subprocess.Popen(
        [sess.node(), str(main_js), "--project", str(project)],
        cwd=str(main_js.parent),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
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
                    "clientInfo": {"name": "test-package-install", "version": "0"},
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


def start_godot(exe: Path, project: Path):
    env = os.environ.copy()
    env.pop("HH_AGENT_SELFTEST", None)
    env.pop("HH_AGENT_SELFTEST_OUT", None)
    env.pop("HH_AGENT_RELOAD_N", None)
    env.pop("HH_READ_OPEN_SCENE", None)
    godot = subprocess.Popen(
        [str(exe), "--headless", "--editor", "--path", str(project)],
        cwd=str(project),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    lines: list[str] = []

    def drain_out() -> None:
        if godot.stdout is None:
            return
        for line in godot.stdout:
            lines.append(line)

    threading.Thread(target=drain_out, daemon=True).start()
    threading.Thread(target=sess.drain_stderr, args=(godot, lines), daemon=True).start()
    return godot, lines


def wait_hello(proc: subprocess.Popen[str], godot: subprocess.Popen[str], req_id: int) -> tuple[int, bool, dict]:
    deadline = time.time() + 90.0
    last: dict = {}
    while time.time() < deadline:
        if godot.poll() is not None or proc.poll() is not None:
            break
        try:
            last = life.body_of(life.mcp_call(proc, req_id, "hh.plugin_noop", {}, timeout=8.0))
        except TimeoutError:
            time.sleep(0.25)
            continue
        req_id += 1
        if last.get("ok") is True and (last.get("postcondition") or {}).get("checks") == ["noop"]:
            return req_id, True, last
        time.sleep(0.25)
    return req_id, False, last


def stop_proc(proc: subprocess.Popen[str] | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()


def variant(typ: str, value: object) -> dict:
    return {"schema": VARIANT_SCHEMA, "type": typ, "value": value}


def tool_call(
    proc: subprocess.Popen[str],
    req_id: int,
    tool: str,
    action: str,
    params: dict,
    timeout: float = 40.0,
) -> tuple[int, dict]:
    cid = life.new_ulid()
    resp = life.mcp_call(proc, req_id, tool, {"action": action, "params": params, "command_id": cid}, timeout)
    return req_id + 1, life.body_of(resp)


def _copy_bundle(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)


def _flip_sidecar_bytes(root: Path) -> None:
    sidecar = root / "sidecar" / "main.js"
    sidecar.write_bytes(sidecar.read_bytes() + b"\n//sidecar-bytes-flip\n")


def _rewrite_manifest_version(root: Path) -> None:
    path = root / "manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = str(data.get("version") or "") + "-tamper"
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _plant_sidecar_and_manifest(studio, root: Path) -> None:
    sidecar = root / "sidecar" / "main.js"
    sidecar.write_bytes(sidecar.read_bytes() + b"\n//critic-tamper\n")
    size, sha256, sha512 = studio.hash_file(sidecar)
    path = root / "manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    files = data.get("files") if isinstance(data.get("files"), dict) else {}
    files["sidecar/main.js"] = {"bytes": size, "sha256": sha256, "sha512": sha512}
    data["files"] = files
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _assert_tamper_reject(studio, src: Path, dest: Path, mutate, label: str, errors: list[str]) -> bool:
    _copy_bundle(src, dest)
    mutate(dest)
    try:
        studio.verify_bundle(dest)
        errors.append(f"{label} must be checksum-rejected")
        return False
    except studio.BundleError as exc:
        blob = str(exc).lower()
        if "tampered" not in blob and "checksum" not in blob and "manifest" not in blob:
            errors.append(f"{label} raised unexpected: {exc}")
            return False
    try:
        studio.install_bundle(dest, dest.parent / (dest.name + "-install"))
        errors.append(f"{label} must not install")
        return False
    except studio.BundleError:
        return True


def main() -> int:
    labels = {key: "unproven" for key in LABELS}
    labels["CLEAN_VM"] = "unproven"
    errors: list[str] = []
    leftover = -1
    official_cmd = f"python {rel(Path(__file__))}"
    if not PLAN.is_file():
        emit("FAIL: R9-WP2 package install; missing plan")
        return 1
    plan_text = PLAN.read_text(encoding="utf-8")
    errors.extend(plan_errors(plan_text))
    errors.extend(src_scan_errors())
    if not os.environ.get("LOCALAPPDATA"):
        errors.append("LOCALAPPDATA missing; official home cannot be LocalAppData packages")
    if errors:
        emit(f"FAIL: R9-WP2 package install; {banner_for(labels)}")
        for item in errors:
            emit(f"  - {item}")
        return 1

    try:
        export_job = load_export_job()
        studio = load_studio()
    except (OSError, RuntimeError) as exc:
        emit(f"FAIL: R9-WP2 package install; {banner_for(labels)}")
        emit(f"  - load tools: {exc}")
        return 1

    home = official_home()
    bundle_a = home / "bundle-a"
    bundle_b = home / "bundle-b"
    install_root = home / "install"
    user_project = home / "user-project"
    leftover = kill_known(export_job, user_project if user_project.exists() else None)
    if leftover != 0:
        emit(f"FAIL: R9-WP2 package install; {banner_for(labels)}")
        emit(f"  - leftover Godot before start={leftover}")
        return 1

    if home.exists():
        shutil.rmtree(home, ignore_errors=True)
    home.mkdir(parents=True, exist_ok=True)
    studio.purge_project_sessions([user_project])

    try:
        studio.build_package(REPO_ROOT, bundle_a, V1)
        studio.build_package(REPO_ROOT, bundle_b, V2)
    except studio.BundleError as exc:
        emit(f"FAIL: R9-WP2 package install; {banner_for(labels)}")
        emit(f"  - package: {exc}")
        if exc.do:
            emit(f"  - do: {exc.do}")
        return 1

    sidecar_flip_ok = _assert_tamper_reject(
        studio,
        bundle_a,
        home / "bundle-tamper-sidecar",
        _flip_sidecar_bytes,
        "sidecar-bytes-flip",
        errors,
    )
    manifest_ok = _assert_tamper_reject(
        studio,
        bundle_a,
        home / "bundle-tamper-manifest",
        _rewrite_manifest_version,
        "manifest.json rewrite",
        errors,
    )
    planted_ok = _assert_tamper_reject(
        studio,
        bundle_a,
        home / "bundle-tamper-planted",
        lambda dest: _plant_sidecar_and_manifest(studio, dest),
        "sidecar+manifest plant leaving checksums.txt",
        errors,
    )
    stamp_ok = _assert_tamper_reject(
        studio,
        bundle_a,
        home / "bundle-tamper-stamp",
        lambda dest: (dest / "version-stamp.txt").write_bytes(
            (dest / "version-stamp.txt").read_bytes() + b"#tamper"
        ),
        "version-stamp.txt flip",
        errors,
    )
    if sidecar_flip_ok and manifest_ok and planted_ok and stamp_ok:
        labels["TAMPER"] = "proven"

    keep_marker = user_project / "USER_KEEP.txt"
    try:
        studio.setup(bundle_a, install_root, user_project)
        keep_marker.write_text("keep-me\n", encoding="utf-8")
        report = studio.doctor_report(install_root, user_project)
        if not report.get("ok"):
            errors.append(f"doctor after setup: {report.get('errors')}")
            for item in report.get("actions") or []:
                errors.append(f"doctor do: {item}")
        elif (install_root / "current" / "version-stamp.txt").read_text(encoding="utf-8").strip() != V1:
            errors.append("install current stamp is not v1")
        elif studio.is_admin_path(install_root):
            errors.append("install root must stay current-user")
        else:
            mcp_child = install_root / "current" / "launcher" / "mcp_child.js"
            bundled = (install_root / "current" / "sidecar" / "main.js").resolve()
            if not mcp_child.is_file():
                errors.append("installed launcher/mcp_child.js missing")
            elif not studio.host_sidecar_lookup_ok(mcp_child.read_text(encoding="utf-8", errors="replace")):
                errors.append("installed launcher must look up bundled sidecar/main.js, not repo bridge/dist")
            elif not bundled.is_file():
                errors.append("installed sidecar/main.js missing")
            else:
                labels["INSTALL"] = "proven"
    except studio.BundleError as exc:
        errors.append(f"setup: {exc}")
        emit(f"FAIL: R9-WP2 package install; {banner_for(labels)}")
        leftover = kill_known(export_job, user_project)
        for item in errors:
            emit(f"  - {item}")
        return 1

    exe, pin_err = find_pinned_godot()
    sidecar_proc = None
    godot_proc = None
    if exe is None:
        errors.append(pin_err)
    else:
        leftover = kill_known(export_job, user_project)
        if leftover != 0:
            errors.append(f"leftover Godot before import={leftover}")
        else:
            try:
                imported = run_godot(
                    exe,
                    ["--headless", "--editor", "--path", str(user_project), "--import", "--quit"],
                    user_project,
                    180.0,
                )
            except subprocess.TimeoutExpired:
                errors.append("godot import timed out")
                imported = None
            leftover = kill_known(export_job, user_project)
            if leftover != 0:
                errors.append(f"leftover Godot after import={leftover}")
            elif imported is not None:
                try:
                    sidecar_main = studio.sidecar_main(install_root)
                    current_sidecar = (install_root / "current" / "sidecar").resolve()
                    if not studio.is_under(sidecar_main, current_sidecar) and sidecar_main.parent.resolve() != current_sidecar:
                        errors.append("CONNECT must use bundled sidecar, not repo bridge/dist")
                    elif "bridge/dist/main.js" in sidecar_main.as_posix():
                        errors.append("CONNECT must not start repo bridge/dist/main.js")
                    else:
                        sidecar_proc, _desc, secret, err_lines = start_sidecar(sidecar_main, user_project)
                        godot_proc, godot_lines = start_godot(exe, user_project)
                        req_id, hello_ok, hello = wait_hello(sidecar_proc, godot_proc, 2)
                        if not hello_ok:
                            errors.append(f"connect hello failed: {sess.redact(json.dumps(hello), secret)}")
                            if err_lines:
                                errors.append("sidecar: " + sess.redact("".join(err_lines[-8:]), secret))
                            if godot_lines:
                                errors.append("godot: " + sess.redact("".join(godot_lines[-8:]), secret))
                        else:
                            labels["CONNECT"] = "proven"
                            _make_microgame(
                                sidecar_proc,
                                req_id,
                                user_project,
                                secret,
                                errors,
                                labels,
                            )
                except (OSError, RuntimeError, TimeoutError, ValueError) as exc:
                    errors.append(f"connect/microgame: {exc}")
                finally:
                    stop_proc(godot_proc)
                    stop_proc(sidecar_proc)
                    leftover = kill_known(export_job, user_project)
                    if leftover != 0:
                        errors.append(f"leftover Godot after connect={leftover}")

    try:
        studio.install_bundle(bundle_b, install_root)
        if (install_root / "current" / "version-stamp.txt").read_text(encoding="utf-8").strip() != V2:
            errors.append("update did not land v2")
        elif (install_root / "rollback" / "version-stamp.txt").read_text(encoding="utf-8").strip() != V1:
            errors.append("update must keep one previous version in rollback")
        else:
            studio.rollback_install(install_root)
            if (install_root / "current" / "version-stamp.txt").read_text(encoding="utf-8").strip() == V1:
                labels["ROLLBACK"] = "proven"
            else:
                errors.append("rollback did not restore v1")
    except studio.BundleError as exc:
        errors.append(f"update/rollback: {exc}")

    try:
        kept = studio.uninstall(install_root)
        leftover_tokens = studio.leftover_session_tokens([user_project])
        if leftover_tokens:
            errors.append(f"uninstall left session.json tokens: {leftover_tokens}")
        elif install_root.exists() and (
            (install_root / "current").exists() or (install_root / "state.json").is_file()
        ):
            errors.append("uninstall left studio files")
        elif not keep_marker.is_file() or keep_marker.read_text(encoding="utf-8").strip() != "keep-me":
            errors.append("uninstall must keep the user project marker")
        elif not (user_project / "project.godot").is_file():
            errors.append("uninstall must keep user project.godot")
        elif str(user_project.resolve()) not in [str(Path(p).resolve()) for p in kept] and not keep_marker.is_file():
            errors.append("uninstall did not report the kept user project")
        else:
            labels["UNINSTALL"] = "proven"
    except studio.BundleError as exc:
        errors.append(f"uninstall: {exc}")

    leftover = kill_known(export_job, user_project)
    studio.purge_project_sessions([user_project])
    if leftover != 0:
        errors.append(f"leftover Godot after verify={leftover}")
    if labels["CLEAN_VM"] == "proven":
        errors.append("must not stamp CLEAN_VM=proven on this Godot/Node machine")

    if errors or any(labels[key] != "proven" for key in REQUIRED_PROVEN) or labels["CLEAN_VM"] != "unproven":
        emit(f"FAIL: R9-WP2 package install; {banner_for(labels)}")
        emit(f"  leftover_godot={leftover} not_g6=1 official={official_cmd}")
        for item in errors:
            emit(f"  - {item}")
        leftover = kill_known(export_job, user_project)
        return 1

    leftover = kill_known(export_job, user_project)
    if leftover != 0:
        emit(f"FAIL: R9-WP2 package install; {banner_for(labels)}")
        emit(f"  - leftover Godot={leftover}")
        return 1

    emit(f"PASS: R9-WP2 package install; {banner_for(labels)}")
    emit(f"  official={official_cmd}")
    emit(
        f"  pin={PINNED} godot={PINNED_VERSION} sidecar=installed leftover_godot=0 "
        f"privileges=current-user signing=unsigned"
    )
    emit(
        f"  install_root={install_root} user_project={user_project} "
        f"smoke!=VM not_g6=1 HUMAN=unproven"
    )
    return 0


def _make_microgame(
    proc: subprocess.Popen[str],
    req_id: int,
    user_project: Path,
    secret: str,
    errors: list[str],
    labels: dict[str, str],
) -> None:
    req_id, _cid, created = life.scene_call(
        proc,
        req_id,
        "create",
        {"path": MICRO_SCENE, "root_class": "Node2D"},
    )
    micro_abs = user_project / "scenes" / "micro.tscn"
    script_abs = user_project / "scripts" / "micro.gd"
    if created.get("ok") is not True or not micro_abs.is_file():
        errors.append(f"microgame scene.create: {sess.redact(json.dumps(created), secret)}")
        return
    req_id, playfield = tool_call(
        proc,
        req_id,
        "godot.node",
        "add",
        {"scene": MICRO_SCENE, "parent": ".", "class_name": "ColorRect", "name": "Playfield"},
    )
    if playfield.get("ok") is not True:
        errors.append(f"microgame ColorRect add: {sess.redact(json.dumps(playfield), secret)}")
        return
    req_id, hint = tool_call(
        proc,
        req_id,
        "godot.node",
        "add",
        {"scene": MICRO_SCENE, "parent": ".", "class_name": "Label", "name": "Hint"},
    )
    if hint.get("ok") is not True:
        errors.append(f"microgame Label add: {sess.redact(json.dumps(hint), secret)}")
        return
    req_id, wrote = tool_call(
        proc,
        req_id,
        "godot.script",
        "write",
        {"path": MICRO_SCRIPT, "contents": MICRO_STUB},
    )
    if wrote.get("ok") is not True or not script_abs.is_file():
        errors.append(f"microgame script.write: {sess.redact(json.dumps(wrote), secret)}")
        return
    req_id, attached = tool_call(
        proc,
        req_id,
        "godot.script",
        "attach",
        {"scene": MICRO_SCENE, "node_path": ".", "path": MICRO_SCRIPT},
    )
    if attached.get("ok") is not True:
        errors.append(f"microgame script.attach: {sess.redact(json.dumps(attached), secret)}")
        return
    req_id, main_set = tool_call(
        proc,
        req_id,
        "godot.project",
        "settings",
        {"key": "application/run/main_scene", "op": "set", "value": variant("string", MICRO_SCENE)},
    )
    if main_set.get("ok") is not True:
        errors.append(f"microgame main_scene: {sess.redact(json.dumps(main_set), secret)}")
        return
    req_id, _sid, saved = life.scene_call(proc, req_id, "save", {"path": MICRO_SCENE})
    if saved.get("ok") is not True:
        errors.append(f"microgame save: {sess.redact(json.dumps(saved), secret)}")
        return
    tscn = micro_abs.read_text(encoding="utf-8")
    gd = script_abs.read_text(encoding="utf-8")
    project_text = (user_project / "project.godot").read_text(encoding="utf-8")
    empty_two_node = tscn.count("type=\"Node2D\"") >= 1 and "ColorRect" not in tscn and "Label" not in tscn
    if empty_two_node:
        errors.append("MICROGAME is two empty Node2Ds; need a runnable stub")
        return
    if "ColorRect" not in tscn or "Hint" not in tscn:
        errors.append("MICROGAME scene missing ColorRect/Label written by the live editor")
        return
    if "micro.gd" not in tscn and MICRO_SCRIPT not in tscn:
        errors.append("MICROGAME scene has no attached stub script")
        return
    if "stub_ready" not in gd:
        errors.append("plugin did not write the runnable stub script")
        return
    if MICRO_SCENE not in project_text:
        errors.append("MICROGAME main_scene was not set on the user project")
        return
    labels["MICROGAME"] = "proven"


if __name__ == "__main__":
    raise SystemExit(main())
