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
    need(digest_file(Path("/tool") / request["binary_name"]) == request["binary_sha256"], "Linux Godot pin mismatch")
    upgrade = None
    if request.get("upgrade_artifact_sha256"):
        upgrade = verify_package(source / "upgrade.hhpkg", trusted_keys=keys, target="Linux-headless",
                                 expected_version="0.1.1")
        need(upgrade["archive_sha256"] == request["upgrade_artifact_sha256"]
             and upgrade["manifest_sha256"] == request["upgrade_manifest_sha256"]
             and upgrade["manifest"]["source_closure_sha256"] == package["manifest"]["source_closure_sha256"],
             "Linux upgrade pin mismatch")
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
    evidence = {}
    for path in output.rglob("*"):
        if path.is_file() and path.name != "linux.json":
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
