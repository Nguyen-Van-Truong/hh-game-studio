"""Inside the pinned offline Linux executor; exercise signed installed bytes."""
from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import re
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.package.consumer_install import ConsumerInstall
from studio.package.release_contract import digest_file, need, strict_json, verify_package
from studio.package.trust import load_trust
from studio.tests.conformance.run_gt10pc_native_probe import project_ledger, write_json
from studio.build.bootstrap.run_fixture import run_process

FIXTURES = ("gt09-arena", "gt09-room")
LEDGERS = ("project-before.json", "project-before-play.json", "project-after-play.json",
           "project-after-uninstall.json", "project-after-reinstall.json")


def native_phase(consumer: Path, fixture: str, phase: str, installer: ConsumerInstall,
                 project: Path, request: dict, selected: dict) -> dict:
    driver_out = consumer / "drivers" / phase
    driver_out.mkdir(parents=True)
    native_out = consumer / "native" / phase
    native_out.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(installer.active_path().parent) + ":/tmp/deps"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    command = [sys.executable, "-B", "-m", "studio.package.installed_probe", "--target", "Linux-headless",
        "--install-root", str(installer.root), "--project", str(project), "--fixture", fixture,
        "--godot", "/tool/" + request["binary_name"], "--output", str(native_out),
        "--trust", "/input/trust.json", "--trust-sha256", request["trust_sha256"]]
    driver = run_process(command, cwd=installer.active_path().parent, output=driver_out,
                         timeout=100, label="driver", env=env)
    write_json(driver_out / "receipt.json", driver)
    need(driver["exit_code"] == 0 and driver["wrapper_exit_code"] == 0
         and driver["tree_verified"] and not driver["timed_out"], "Linux installed driver failed")
    receipt = strict_json((native_out / "receipt.json").read_bytes())
    need(receipt.get("target") == "Linux-headless" and receipt.get("os_name") == "posix"
         and receipt.get("active_release") == selected["manifest_sha256"]
         and receipt.get("godot_sha256") == request["binary_sha256"]
         and receipt.get("probe_sha256") == selected["manifest"]["files"][
             "payload/studio/package/installed_probe.py"]["sha256"], "Linux installed source mismatch")
    for base, label, process in ((driver_out, "driver", driver),
            (native_out, "parse", receipt.get("parse")), (native_out, "godot", receipt.get("process"))):
        need(isinstance(process, dict) and process.get("exit_code") == 0
             and process.get("wrapper_exit_code") == 0 and process.get("tree_verified") is True
             and process.get("timed_out") is False and process.get("ownership") == "process_group",
             "Linux process group was not clean")
        host = strict_json((base / (label + "-host.json")).read_bytes())
        need(type(host.get("target_pid")) is int and host["target_pid"] > 0
             and host["target_pid"] == process.get("target_pid") and host.get("exit_code") == 0,
             "Linux host exit differs")
        stdout = (base / (label + "-stdout.txt")).read_text(encoding="utf-8")
        need(not (base / (label + "-stderr.txt")).read_bytes()
             and not re.search(r"(?im)\b(error|warning|orphan)\b", stdout), "Linux native log is not clean")
    return {"phase": phase, "active": selected["manifest_sha256"],
            "project_ledger": project_ledger(project),
            "driver": "drivers/" + phase + "/receipt.json",
            "native": "native/" + phase + "/receipt.json"}


L02_DELTA = ("Accepted GT-08A L02 used the Windows editor to export Linux/X11. "
             "This row uses the Linux editor with the same template bytes.")
P10_FIXTURE_NAME = "fixture Ñé with spaces"


def _load_gt08a(studio: Path):
    import importlib.util
    path = studio / "build/ci/gt08a_matrix.py"
    spec = importlib.util.spec_from_file_location("gt10pc_p10_installed_gt08a", path)
    need(spec is not None and spec.loader is not None, "installed GT-08A module missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _capture(command: list[str], cwd: Path, output: Path, timeout: int, label: str,
             env: dict[str, str]) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    row = run_process(command, cwd=cwd, output=output, timeout=timeout, label=label, env=env)
    row["stdout_sha256"] = digest_file(output / row["stdout"])
    row["stderr_sha256"] = digest_file(output / row["stderr"])
    write_json(output / (label + "-receipt.json"), row)
    host = strict_json((output / (label + "-host.json")).read_bytes())
    need(row["exit_code"] == 0 and row["wrapper_exit_code"] == 0 and row["tree_verified"]
         and not row["timed_out"], label + " process failed")
    need(not (output / row["stderr"]).read_bytes(), label + " stderr is not empty")
    need(type(host.get("target_pid")) is int and host["target_pid"] > 0
         and host["target_pid"] == row.get("target_pid") and host.get("exit_code") == 0,
         label + " host receipt mismatch")
    return row


def run_p10_rows(source: Path, output: Path, request: dict, package: dict, tool: Path,
                 keys: dict) -> None:
    """L01/L02 and per-fixture K10 smoke inside the existing pinned container."""
    installer = ConsumerInstall(Path("/tmp/p10-install"), trusted_keys=keys, target="Linux-headless")
    installed = installer.install(source / "release.hhpkg", command_id="p10.install",
                                  expected_state_sha256="ABSENT")
    gt08a = _load_gt08a(installer.active_path())
    fixture_src = installer.active_path() / "fixtures" / "sample-game"
    source_tree = gt08a.checked_tree(fixture_src)
    source_hash = gt08a.closure_hash(source_tree)
    need(not any("zdoc" in path for path in source_tree), "sample-game closure contains zdoc")
    write_json(output / "gt08a" / "closure.json", {
        "schema": "hh-gt10pc-p10-fixture-closure-1", "authority": 0, "acceptance": False,
        "source_closure": source_hash, "files": source_tree})
    work = Path("/tmp/gt08a")
    project = work / P10_FIXTURE_NAME
    shutil.copytree(fixture_src, project)
    gt08a.write_presets(project)
    need(P10_FIXTURE_NAME in str(project), "unicode fixture path missing")
    template_dest = Path("/tmp/xdg/godot/export_templates/4.7.2.stable")
    template_dest.mkdir(parents=True)
    for filename in ("version.txt", "linux_release.x86_64", "linux_debug.x86_64"):
        shutil.copyfile(source / "export-templates" / filename, template_dest / filename)
    env = os.environ.copy()
    env.update({"HOME": "/tmp", "XDG_CACHE_HOME": "/tmp/cache", "XDG_DATA_HOME": "/tmp/xdg"})
    godot = str(tool)
    l01 = _capture([godot, "--headless", "--path", str(project), "--quit-after", "1"],
                   work, output / "gt08a" / "L01", 120, "l01", env)
    export_path = Path("/tmp/gt08a/L02/fixture.x86_64")
    export_path.parent.mkdir(parents=True)
    l02 = _capture([godot, "--headless", "--path", str(project), "--export-release", "Linux/X11",
                    str(export_path)], work, output / "gt08a" / "L02", 180, "l02", env)
    need(export_path.is_file() and export_path.stat().st_size > 0, "L02 export artifact missing")
    evidence_artifact = Path("/evidence/gt08a/L02/fixture.x86_64")
    evidence_artifact.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(export_path, evidence_artifact)
    rows = [
        {"id": "L01", "status": "PASS", "source_closure": source_hash, "process": l01},
        {"id": "L02", "status": "PASS", "editor_os": "linux", "delta": L02_DELTA,
         "source_closure": source_hash, "artifact_sha256": digest_file(evidence_artifact),
         "artifact_bytes": evidence_artifact.stat().st_size, "process": l02},
    ]
    for fixture in FIXTURES:
        consumer_project = Path("/tmp/k10") / fixture
        shutil.copytree(installer.active_path() / "fixtures" / fixture, consumer_project)
        installer.install_addon(consumer_project, release=installed["active"],
                                command_id="p10.addon." + fixture,
                                expected_state_sha256=installer.snapshot()["state_sha256"])
        _capture([godot, "--headless", "--path", str(consumer_project), "--scene", "scenes/fixture.tscn",
                  "--max-fps", "60", "--", "--fixture-lifecycle-smoke"],
                 consumer_project, output / "k10" / fixture, 90, "godot", env)
    write_json(output / "linux.json", {
        "schema": "hh-gt10pc-linux-p10-1", "authority": 0, "acceptance": False,
        "purpose": "p10", "rows": rows, "k10_fixtures": list(FIXTURES),
        "artifact_sha256": request["artifact_sha256"], "manifest_sha256": package["manifest_sha256"],
        "source_closure_sha256": package["manifest"]["source_closure_sha256"]})
    print("GT10PC_LINUX_P10_COMPLETE", flush=True)


def bind_negative_inputs(source: Path, request: dict) -> dict[str, dict[str, str]]:
    """Check host-built P4 artifacts before any install uses them."""
    root = source / "negative"
    archive = root / "incompatible-schema.hhpkg"
    release_root = root / "untrusted-release"
    need(archive.is_file() and release_root.is_dir(), "Linux negative inputs missing")
    children = sorted(path for path in release_root.iterdir() if path.is_dir())
    need(len(children) == 1, "Linux negative manifest set")
    manifest = children[0] / "manifest.json"
    need(manifest.is_file(), "Linux negative manifest missing")
    archive_sha = digest_file(archive)
    manifest_sha = digest_file(manifest)
    need(archive_sha == request.get("negative_incompatible_sha256"), "Linux negative archive pin")
    need(manifest_sha == request.get("negative_manifest_sha256") == children[0].name,
         "Linux negative manifest pin")
    return {"incompatible-schema.hhpkg": {"path": str(archive), "sha256": archive_sha},
            "untrusted-manifest": {"path": str(manifest), "sha256": manifest_sha}}


def stage_negative_evidence(source: Path, output: Path, request: dict, keys: dict) -> None:
    """Side install of 0.1.0 then 0.1.1, then the two refusals. No Play."""
    from studio.tests.conformance.gt10pc_p4_negative import run_negative
    pinned = bind_negative_inputs(source, request)
    out = output / "negative"
    out.mkdir()
    archive = out / "incompatible-schema.hhpkg"
    shutil.copyfile(pinned["incompatible-schema.hhpkg"]["path"], archive)
    manifest_src = Path(pinned["untrusted-manifest"]["path"])
    manifest_dest = out / "untrusted-release" / manifest_src.parent.name / "manifest.json"
    manifest_dest.parent.mkdir(parents=True)
    shutil.copyfile(manifest_src, manifest_dest)
    need(digest_file(archive) == pinned["incompatible-schema.hhpkg"]["sha256"],
         "Linux negative archive copy")
    need(digest_file(manifest_dest) == pinned["untrusted-manifest"]["sha256"],
         "Linux negative manifest copy")
    side = Path("/tmp/p4-negative")
    installer = ConsumerInstall(side, trusted_keys=keys, target="Linux-headless")
    installer.install(source / "release.hhpkg", command_id="negative.install",
                      expected_state_sha256=installer.snapshot()["state_sha256"])
    installer.install(source / "upgrade.hhpkg", command_id="negative.upgrade",
                      expected_state_sha256=installer.snapshot()["state_sha256"])
    copied = {"incompatible-schema.hhpkg": {"path": str(archive), "sha256": digest_file(archive)},
              "untrusted-manifest": {"path": str(manifest_dest), "sha256": digest_file(manifest_dest)}}

    def open_consumer() -> ConsumerInstall:
        return ConsumerInstall(side, trusted_keys=keys, target="Linux-headless")

    run_negative(side, open_consumer, copied, out)


def main() -> None:
    need(platform.system() == "Linux", "Linux native OS required")
    source, output = Path("/input"), Path("/output")
    request = strict_json((source / "request.json").read_bytes())
    keys = load_trust(source / "trust.json", expected_sha256=request["trust_sha256"])
    package = verify_package(source / "release.hhpkg", trusted_keys=keys, target="Linux-headless")
    need(package["archive_sha256"] == request["artifact_sha256"]
         and package["manifest_sha256"] == request["manifest_sha256"], "Linux artifact pin mismatch")
    need(digest_file(Path(__file__)) == package["manifest"]["files"][
         "payload/studio/tests/conformance/gt10pc_linux_worker.py"]["sha256"], "Linux bootstrap worker mismatch")
    tool_binary = Path("/tool") / request["binary_name"]
    need(digest_file(tool_binary) == request["binary_sha256"], "Linux Godot pin mismatch")
    need(os.access(tool_binary, os.X_OK), "Linux image Godot is not executable")
    if request.get("purpose") == "p10":
        need(not request.get("upgrade_artifact_sha256"), "p10 container does not take an upgrade")
        run_p10_rows(source, output, request, package, tool_binary, keys)
        return
    upgrade = None
    if request.get("upgrade_artifact_sha256"):
        upgrade = verify_package(source / "upgrade.hhpkg", trusted_keys=keys, target="Linux-headless",
                                 expected_version="0.1.1")
        need(upgrade["archive_sha256"] == request["upgrade_artifact_sha256"]
             and upgrade["manifest_sha256"] == request["upgrade_manifest_sha256"]
             and upgrade["manifest"]["source_closure_sha256"] == package["manifest"]["source_closure_sha256"],
             "Linux upgrade pin mismatch")
        bind_negative_inputs(source, request)
    records = []
    for fixture in FIXTURES:
        consumer = output / "consumer" / fixture
        installer = ConsumerInstall(consumer / "install", trusted_keys=keys, target="Linux-headless")
        installed = installer.install(source / "release.hhpkg", command_id="install." + fixture,
                                      expected_state_sha256="ABSENT")
        project = consumer / "project"
        shutil.copytree(installer.active_path() / "fixtures" / fixture, project)
        (project / "owner-save.dat").write_bytes(b"consumer-save-before-install\n")
        before = project_ledger(project)
        write_json(consumer / "project-before.json", before)
        addon = installer.install_addon(project, release=installed["active"], command_id="addon." + fixture,
                    expected_state_sha256=installer.snapshot()["state_sha256"])
        manual = project / "addons/hh_studio/owner-manual-note.txt"
        manual.write_bytes(b"owner edit must survive uninstall\n")
        manual_before = project_ledger(project)["addons/hh_studio/owner-manual-note.txt"]
        ready = project_ledger(project)
        write_json(consumer / "project-before-play.json", ready)
        phases = [native_phase(consumer, fixture, "install", installer, project, request, package)]
        need(project_ledger(project) == ready, "Linux native Play changed consumer files")
        write_json(consumer / "project-after-play.json", project_ledger(project))
        upgraded = rolled_back = upgrade_addon = rollback_addon = None
        if upgrade is not None:
            upgraded = installer.install(source / "upgrade.hhpkg", command_id="upgrade." + fixture,
                                         expected_state_sha256=installer.snapshot()["state_sha256"])
            upgrade_addon = installer.install_addon(project, release=upgraded["active"], repair=True,
                command_id="upgrade-addon." + fixture, expected_state_sha256=installer.snapshot()["state_sha256"])
            phases.append(native_phase(consumer, fixture, "upgrade", installer, project, request, upgrade))
            rolled_back = installer.rollback(command_id="rollback." + fixture, destination=installed["active"],
                                             expected_state_sha256=installer.snapshot()["state_sha256"])
            rollback_addon = installer.install_addon(project, release=rolled_back["active"], repair=True,
                command_id="rollback-addon." + fixture, expected_state_sha256=installer.snapshot()["state_sha256"])
            phases.append(native_phase(consumer, fixture, "rollback", installer, project, request, package))
        uninstall = installer.uninstall_addon(project, command_id="uninstall." + fixture,
                    expected_state_sha256=installer.snapshot()["state_sha256"])
        after_uninstall = project_ledger(project)
        need(set(after_uninstall) == set(before) | {"addons/hh_studio/owner-manual-note.txt"},
             "Linux uninstall changed consumer files")
        need(after_uninstall["addons/hh_studio/owner-manual-note.txt"] == manual_before,
             "Linux uninstall changed manual edit")
        write_json(consumer / "project-after-uninstall.json", after_uninstall)
        reinstall = installer.install_addon(project, release=installed["active"], command_id="reinstall." + fixture,
                    expected_state_sha256=installer.snapshot()["state_sha256"])
        after_reinstall = project_ledger(project)
        need(after_reinstall.get("addons/hh_studio/owner-manual-note.txt") == after_uninstall[
            "addons/hh_studio/owner-manual-note.txt"], "Linux reinstall lost manual edit")
        write_json(consumer / "project-after-reinstall.json", after_reinstall)
        phases.append(native_phase(consumer, fixture, "reinstall", installer, project, request, package))
        need(all(phase["project_ledger"] == after_reinstall for phase in phases), "Linux phase changed consumer files")
        write_json(consumer / "native-phases.json", {"phases": phases})
        write_json(consumer / "install-state.json", installer.snapshot())
        records.append({"fixture": fixture, "install_receipt": installed, "addon_receipt": addon,
            "upgrade_receipt": upgraded, "rollback_receipt": rolled_back,
            "upgrade_addon_receipt": upgrade_addon, "rollback_addon_receipt": rollback_addon,
            "uninstall_receipt": uninstall, "reinstall_receipt": reinstall,
            "phases": phases})
    if upgrade is not None:
        stage_negative_evidence(source, output, request, keys)
    evidence = {}
    for fixture in FIXTURES:
        consumer = output / "consumer" / fixture
        for name in (*LEDGERS, "native-phases.json", "install-state.json"):
            path = consumer / name
            evidence[path.relative_to(output).as_posix()] = digest_file(path)
        for phase in records[FIXTURES.index(fixture)]["phases"]:
            for domain in ("drivers", "native"):
                for path in (consumer / domain / phase["phase"]).iterdir():
                    if path.is_file():
                        evidence[path.relative_to(output).as_posix()] = digest_file(path)
    negative_root = output / "negative"
    if negative_root.is_dir():
        for path in sorted(negative_root.rglob("*")):
            if path.is_file():
                evidence[path.relative_to(output).as_posix()] = digest_file(path)
    write_json(output / "linux.json", {"schema": "hh-gt10pc-linux-native-2", "authority": 0, "acceptance": False,
        "mode": "DIAGNOSTIC", "system": platform.system(), "python": platform.python_version(),
        "target": "Linux-headless", "records": records, "evidence": evidence,
        "artifact_sha256": request["artifact_sha256"], "manifest_sha256": package["manifest_sha256"],
        "upgrade_artifact_sha256": request.get("upgrade_artifact_sha256"),
        "upgrade_manifest_sha256": request.get("upgrade_manifest_sha256"),
        "source_closure_sha256": package["manifest"]["source_closure_sha256"]})
    print("GT10PC_LINUX_NATIVE_COMPLETE", flush=True)


if __name__ == "__main__":
    main()
