"""Windows installed-release diagnostic; no P-row or rehearsal acceptance.

Consumer projects are copied before installation and never become installer
property. Both fixtures complete the existing lifecycle smoke trace. The real
installed package runs the native launcher in a separate Python process.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent))
from studio.package.consumer_install import ConsumerInstall
from studio.package.release_contract import (
    build_package, digest_file, _source_files, _payload_digest, need, safe_path,
)
from studio.package.trust import load_trust
from studio.build.bootstrap.run_fixture import run_process

GODOT_WINDOWS = ROOT / ".local/tooling/godot-4.7.2-stable/Godot_v4.7.2-stable_win64_console.exe"
SCHEMA = "HH-GT10PC-NATIVE-PRODUCER-4"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def project_ledger(root: Path) -> dict:
    result = {}
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if d != ".godot"]
        for name in dirs:
            safe_path(Path(directory) / name)
        for name in files:
            path = safe_path(Path(directory) / name)
            # `safe_path` has already validated this exact path.  Hash the
            # opened file directly so every ledger walk does not repeat the
            # full ancestor/reparse validation performed by `digest_file`.
            # The streaming digest preserves the ledger's memory and content
            # semantics while keeping the native producer within its bound.
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            result[path.relative_to(root).as_posix()] = {"sha256": digest, "size": path.stat().st_size}
    return result


def project_state(project: Path) -> dict:
    return {"source": digest_file(project / "project.godot"),
            "save": digest_file(project / "owner-save.dat")}


def native_phase(output: Path, fixture: str, phase: str, install: ConsumerInstall,
                 project: Path, args, *, godot: Path, target: str) -> dict:
    label = fixture if phase == "install" else fixture + "-" + phase
    driver_output = output / "drivers" / label
    driver_output.mkdir(parents=True)
    native_output = output / "godot" / label
    command = [sys.executable, "-B", "-m", "studio.package.installed_probe",
               "--install-root", str(install.root), "--project", str(project),
               "--godot", str(godot), "--output", str(native_output),
               "--fixture", fixture,
               "--target", target,
               "--trust", str(safe_path(args.trust)), "--trust-sha256", args.trust_sha256]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(install.active_path().parent)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    # The installed payload is bound through PYTHONPATH.  Keep the process cwd
    # on the consumer project so a lifecycle selector/recovery cannot make the
    # launch directory transient while the native child is starting.
    driver = run_process(command, cwd=project, output=driver_output,
                         timeout=90, label="driver", env=env)
    write_json(driver_output / "receipt.json", driver)
    need(driver["exit_code"] == 0 and driver["wrapper_exit_code"] == 0
         and driver["tree_verified"] and not driver["timed_out"], "installed native driver failed")
    return {"phase": phase, "label": label, "active": install.snapshot()["active"],
            "project_ledger": project_ledger(project)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trust", type=Path, required=True)
    parser.add_argument("--trust-sha256", required=True)
    parser.add_argument("--private-key", type=Path, required=True)
    parser.add_argument("--target", choices=("Windows", "Linux-headless"), default="Windows")
    parser.add_argument("--godot", type=Path)
    args = parser.parse_args(argv)
    output = safe_path(args.output)
    need(not output.exists(), "GT10PC_PROBE_OUTPUT_EXISTS")
    godot = safe_path(args.godot or GODOT_WINDOWS)
    need((args.target == "Windows") == (os.name == "nt"), "GT10PC_NATIVE_TARGET_OS_MISMATCH")
    need(godot.is_file(), "GT10PC_GODOT_PIN_REQUIRED")
    keys = load_trust(args.trust, expected_sha256=args.trust_sha256)
    key_id, public = next(iter(keys.items()))
    from studio.tests.conformance.gt10pc_signing import load_signer
    signer = load_signer(safe_path(args.private_key), public)
    before_closure = _payload_digest(_source_files(ROOT))
    output.mkdir(parents=True)
    artifact = output / "release.hhpkg"
    package = build_package(ROOT, artifact, signer=signer, key_id=key_id, target=args.target)
    need(package["manifest"]["source_closure_sha256"] == before_closure, "build source drift")
    upgrade_artifact = output / "upgrade.hhpkg"
    upgrade_package = build_package(ROOT, upgrade_artifact, signer=signer, key_id=key_id,
                                    version="0.1.1", target=args.target)
    records = []
    for fixture in ("gt09-arena", "gt09-room"):
        consumer_root = output / "consumer" / fixture
        project = consumer_root / "project"
        shutil.copytree(ROOT / "fixtures" / fixture, project,
                        ignore=shutil.ignore_patterns(".godot", "__pycache__"))
        (project / "owner-save.dat").write_bytes(b"consumer-save-before-install\n")
        before_ledger = project_ledger(project)
        before = project_state(project)
        write_json(consumer_root / "project-before.json", before_ledger)
        install = ConsumerInstall(consumer_root / "install", trusted_keys=keys, target=args.target)
        installed = install.install(artifact, command_id="install." + fixture,
                                    expected_state_sha256=install.snapshot()["state_sha256"])
        addon_installed = install.install_addon(project, release=installed["active"], command_id="install-addon." + fixture,
                                                expected_state_sha256=install.snapshot()["state_sha256"])
        manual = project / "addons" / "hh_studio" / "owner-manual-note.txt"
        manual.write_text("owner edit must survive uninstall\n", encoding="utf-8")
        before_play_ledger = project_ledger(project)
        write_json(consumer_root / "project-before-play.json", before_play_ledger)
        phases = [native_phase(output, fixture, "install", install, project, args,
                               godot=godot, target=args.target)]
        after_play = project_state(project)
        after_play_ledger = project_ledger(project)
        need(before_play_ledger == after_play_ledger, "consumer project ledger changed during Play")
        write_json(consumer_root / "project-after-play.json", after_play_ledger)
        need(before == after_play, "consumer source/save changed during Play")
        upgraded = install.install(upgrade_artifact, command_id="upgrade." + fixture,
                                    expected_state_sha256=install.snapshot()["state_sha256"])
        upgrade_addon = install.install_addon(project, release=upgraded["active"], repair=True,
                         command_id="upgrade-addon." + fixture, expected_state_sha256=install.snapshot()["state_sha256"])
        phases.append(native_phase(output, fixture, "upgrade", install, project, args,
                                   godot=godot, target=args.target))
        rolled_back = install.rollback(command_id="rollback." + fixture, destination=installed["active"],
                                       expected_state_sha256=install.snapshot()["state_sha256"])
        rollback_addon = install.install_addon(project, release=rolled_back["active"], repair=True,
                         command_id="rollback-addon." + fixture, expected_state_sha256=install.snapshot()["state_sha256"])
        phases.append(native_phase(output, fixture, "rollback", install, project, args,
                                   godot=godot, target=args.target))
        for phase in phases:
            need(phase["project_ledger"] == before_play_ledger, "upgrade/rollback mutated consumer project")
        write_json(consumer_root / "native-phases.json", {"phases": phases})
        addon_removed = install.uninstall_addon(project, command_id="uninstall-addon." + fixture,
                                                expected_state_sha256=install.snapshot()["state_sha256"])
        after_uninstall = project_state(project)
        after_uninstall_ledger = project_ledger(project)
        manual_rel = manual.relative_to(project).as_posix()
        expected_after_uninstall = dict(before_ledger)
        expected_after_uninstall[manual_rel] = {"sha256": digest_file(manual), "size": manual.stat().st_size}
        need(after_uninstall_ledger == expected_after_uninstall,
             "uninstall changed consumer files outside package ownership")
        write_json(consumer_root / "project-after-uninstall.json", after_uninstall_ledger)
        need(before == after_uninstall and manual.is_file(), "consumer source/save/manual changed on addon uninstall")
        # Reinstall demonstrates that manual content survives and missing
        # package-owned files are restored into the same project.
        reinstall_addon = install.install_addon(project, release=installed["active"], command_id="reinstall-addon." + fixture,
                                                 expected_state_sha256=install.snapshot()["state_sha256"])
        need(manual.is_file(), "manual addon edit lost during reinstall")
        after_reinstall = project_state(project)
        need(after_reinstall == before, "consumer source/save changed on reinstall")
        after_reinstall_ledger = project_ledger(project)
        expected_after_reinstall = dict(before_ledger)
        from studio.package.release_contract import digest_bytes
        for name, data in install.addon_files(installed["active"]).items():
            expected_after_reinstall["addons/hh_studio/" + name] = {"sha256": digest_bytes(data), "size": len(data)}
        expected_after_reinstall[manual_rel] = {"sha256": digest_file(manual), "size": manual.stat().st_size}
        need(after_reinstall_ledger == expected_after_reinstall,
             "reinstall did not restore package-owned addon closure")
        write_json(consumer_root / "project-after-reinstall.json", after_reinstall_ledger)
        deactivated = install.deactivate(command_id="deactivate." + fixture,
                                          expected_state_sha256=install.snapshot()["state_sha256"])
        after_deactivate = project_state(project)
        need(after_deactivate == before, "consumer source/save changed on deactivate")
        after_deactivate_ledger = project_ledger(project)
        need(after_deactivate_ledger == after_reinstall_ledger, "deactivate changed consumer project ledger")
        write_json(consumer_root / "project-after-deactivate.json", after_deactivate_ledger)
        reinstalled = install.install(artifact, command_id="reinstall." + fixture,
                                      expected_state_sha256=install.snapshot()["state_sha256"])
        need(reinstalled["active"] == installed["active"], "immutable reinstall identity changed")
        records.append({"fixture": fixture, "before": before, "after_play": after_play,
                        "ledger_sha256": {
                            name: digest_file(consumer_root / name) for name in
                            ("project-before.json", "project-before-play.json", "project-after-play.json", "project-after-uninstall.json",
                             "project-after-reinstall.json", "project-after-deactivate.json")},
                        "after_uninstall": after_uninstall, "install_receipt": installed,
                        "upgrade_receipt": upgraded, "rollback_receipt": rolled_back,
                        "upgrade_addon_receipt": upgrade_addon, "rollback_addon_receipt": rollback_addon,
                        "addon_install_receipt": addon_installed, "addon_uninstall_receipt": addon_removed,
                        "addon_reinstall_receipt": reinstall_addon, "deactivate_receipt": deactivated,
                        "reinstall_receipt": reinstalled})
    after_closure = _payload_digest(_source_files(ROOT))
    need(after_closure == before_closure, "source changed during diagnostic")
    # Side root only: incompatible schema and untrusted rollback, no Play.
    from studio.tests.conformance.gt10pc_p4_negative import (
        build_bad_artifacts, run_negative, verify_negative,
    )
    side_root = output / "consumer" / "negative"
    side = ConsumerInstall(side_root, trusted_keys=keys, target=args.target)
    side.install(artifact, command_id="negative.install",
                 expected_state_sha256=side.snapshot()["state_sha256"])
    side.install(upgrade_artifact, command_id="negative.upgrade",
                 expected_state_sha256=side.snapshot()["state_sha256"])
    negative_dir = output / "negative"
    bad = build_bad_artifacts(artifact, signer, negative_dir)

    def open_side() -> ConsumerInstall:
        return ConsumerInstall(side_root, trusted_keys=keys, target=args.target)

    run_negative(side_root, open_side, bad, negative_dir)
    negative_report = verify_negative(negative_dir, keys)
    evidence = {}
    for base in (output / "drivers", output / "godot"):
        for path in sorted(base.rglob("*")):
            if path.is_file() and "godot-user" not in path.parts:
                evidence[path.relative_to(output).as_posix()] = digest_file(path)
    for row in records:
        path = output / "consumer" / row["fixture"] / "native-phases.json"
        evidence[path.relative_to(output).as_posix()] = digest_file(path)
        for name in ("project-before.json", "project-before-play.json", "project-after-play.json", "project-after-uninstall.json",
                     "project-after-reinstall.json", "project-after-deactivate.json"):
            path = output / "consumer" / row["fixture"] / name
            evidence[path.relative_to(output).as_posix()] = digest_file(path)
    for path in sorted(negative_dir.rglob("*")):
        if path.is_file():
            evidence[path.relative_to(output).as_posix()] = digest_file(path)
    manifest = {"schema": SCHEMA, "mode": "DIAGNOSTIC", "authority": 0, "acceptance": False,
                "artifact_sha256": digest_file(artifact), "manifest_sha256": package["manifest_sha256"],
                "upgrade_artifact_sha256": digest_file(upgrade_artifact),
                "upgrade_manifest_sha256": upgrade_package["manifest_sha256"],
                "source_closure_sha256": before_closure, "trust_sha256": args.trust_sha256,
                "target": args.target, "godot_sha256": digest_file(godot),
                "fixtures": records, "negative": negative_report, "evidence": evidence,
                "remaining": ["Linux", "AUTH07", "crash/Stop", "GT08A/K8/K10",
                              "formal25 soak", "final critics"]}
    write_json(output / "producer.json", manifest)
    write_json(output / "matrix.json", {"schema": "hh-gt10pc-matrix-2", "authority": 0,
               "acceptance": False, "mode": "DIAGNOSTIC", "producer": "producer.json",
               "producer_sha256": digest_file(output / "producer.json")})
    print(json.dumps({"status": "DIAGNOSTIC_COMPLETE", "authority": 0,
                      "artifact_sha256": manifest["artifact_sha256"], "output": str(output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
