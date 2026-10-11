"""One real consumer-process P2 rejection run.

The worker creates a trusted last-good install, sends malformed and
wrong-target/version packages through ``ConsumerInstall.install`` in this
separate process, and then launches the installed Godot probe.  Rejections
are only accepted when the installer root and consumer source/save ledger are
byte-identical before and after each attempt.  This is rehearsal evidence;
it never asserts GT-10 acceptance.
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
from studio.build.bootstrap.run_fixture import run_process
from studio.package.consumer_install import ConsumerInstall
from studio.package.release_contract import (
    build_package, digest_file, digest_bytes, need, safe_path, verify_package,
)
from studio.package.trust import load_trust
from studio.tests.conformance.gt10pc_signing import load_signer
from studio.tests.conformance.run_gt10pc_native_probe import project_ledger

GODOT_WINDOWS = ROOT / ".local/tooling/godot-4.7.2-stable/Godot_v4.7.2-stable_win64_console.exe"
ATTACKS = ("tamper", "truncate", "wrong-target", "wrong-version")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def tree_ledger(root: Path) -> dict:
    result = {}
    if not root.exists():
        return result
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(dirs)
        for name in sorted(files):
            path = safe_path(Path(directory) / name)
            # ``safe_path`` already performed the complete reparse/device/
            # hard-link check for this file.  Calling ``digest_file`` here
            # would repeat that check (including an lstat walk for every
            # ancestor) and made the native worker miss its 180 s bound on a
            # cold Windows filesystem.  Hash the checked path directly while
            # retaining the same size/readback fields used by the ledger.
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            result[path.relative_to(root).as_posix()] = {
                "sha256": digest, "size": path.stat().st_size
            }
    return result


def mutate(source: bytes, attack: str) -> bytes:
    if attack == "truncate":
        return source[:-19]
    if attack == "tamper":
        index = len(source) // 2
        return source[:index] + bytes([source[index] ^ 1]) + source[index + 1:]
    return source


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trust", type=Path, required=True)
    parser.add_argument("--trust-sha256", required=True)
    parser.add_argument("--private-key", type=Path, required=True)
    parser.add_argument("--target", choices=("Windows", "Linux-headless"), default="Windows")
    parser.add_argument("--godot", type=Path)
    parser.add_argument("--artifact", type=Path)
    args = parser.parse_args(argv)
    output = safe_path(args.output)
    need(not output.exists(), "GT10PC_P2_OUTPUT_EXISTS")
    need((args.target == "Windows") == (os.name == "nt"), "GT10PC_P2_TARGET_OS_MISMATCH")
    if args.target != "Windows":
        raise ValueError("GT10PC_P2_NATIVE_WINDOWS_FIXTURE_REQUIRED")
    godot = safe_path(args.godot or GODOT_WINDOWS)
    need(godot.is_file(), "GT10PC_P2_GODOT_PIN_REQUIRED")
    keys = load_trust(args.trust, expected_sha256=args.trust_sha256)
    key_id, public = next(iter(keys.items()))
    signer = load_signer(safe_path(args.private_key), public)
    output.mkdir(parents=True)
    artifact = safe_path(args.artifact) if args.artifact else output / "release.hhpkg"
    package = (verify_package(artifact, trusted_keys=keys, target=args.target)
               if args.artifact else
               build_package(ROOT, artifact, signer=signer, key_id=key_id, target=args.target))
    wrong_target = output / "wrong-target.hhpkg"
    build_package(ROOT, wrong_target, signer=signer, key_id=key_id,
                  target="Linux-headless")

    consumer = output / "consumer"
    project = consumer / "project"
    shutil.copytree(ROOT / "fixtures" / "gt09-arena", project,
                    ignore=shutil.ignore_patterns(".godot", "__pycache__"))
    (project / "owner-save.dat").write_bytes(b"p2-owner-save\n")
    install = ConsumerInstall(consumer / "install", trusted_keys=keys, target=args.target)
    installed = install.install(artifact, command_id="p2.last-good",
                                expected_state_sha256=install.snapshot()["state_sha256"])
    install.install_addon(project, release=installed["active"],
                          command_id="p2.last-good-addon",
                          expected_state_sha256=install.snapshot()["state_sha256"])
    baseline_root = tree_ledger(install.root)
    baseline_project = project_ledger(project)
    baseline_state = install.snapshot()
    attacks = []
    original = artifact.read_bytes()
    for attack in ATTACKS:
        if attack == "wrong-target":
            attack_path = wrong_target
        else:
            attack_path = output / (attack + ".hhpkg")
            attack_path.write_bytes(mutate(original, attack))
        rejected = False
        reason = None
        try:
            install.install(attack_path, command_id="p2.reject." + attack,
                            expected_state_sha256=baseline_state["state_sha256"],
                            expected_version="0.1.1" if attack == "wrong-version" else None)
        except (ValueError, OSError) as exc:
            rejected, reason = True, type(exc).__name__ + ": " + str(exc)
        need(rejected, "GT10PC_P2_ATTACK_ACCEPTED:" + attack)
        need(tree_ledger(install.root) == baseline_root,
             "GT10PC_P2_INSTALL_ROOT_CHANGED:" + attack)
        need(project_ledger(project) == baseline_project,
             "GT10PC_P2_PROJECT_SOURCE_SAVE_CHANGED:" + attack)
        need(install.snapshot() == baseline_state,
             "GT10PC_P2_SELECTOR_CHANGED:" + attack)
        attacks.append({"attack": attack, "rejected": True, "reason": reason,
                        "artifact_sha256": digest_file(attack_path)})

    write_json(output / "install-before.json", baseline_root)
    write_json(output / "install-after.json", tree_ledger(install.root))
    write_json(output / "project-before.json", baseline_project)
    write_json(output / "project-after.json", project_ledger(project))
    write_json(output / "state-before.json", baseline_state)
    write_json(output / "state-after.json", install.snapshot())

    # Run the real installed adapter/Godot path after all rejections.  The
    # wrapper writes independent host and target receipts for both processes.
    native = output / "native"
    driver = output / "driver"
    command = [sys.executable, "-B", "-m", "studio.package.installed_probe",
               "--install-root", str(install.root), "--project", str(project),
               "--godot", str(godot), "--output", str(native), "--fixture", "gt09-arena",
               "--target", args.target, "--trust", str(safe_path(args.trust)),
               "--trust-sha256", args.trust_sha256]
    driver.mkdir(parents=True)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(install.active_path().parent)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    process = run_process(command, cwd=install.active_path().parent, output=driver,
                          timeout=100, label="driver", env=env)
    need(process["exit_code"] == 0 and process["wrapper_exit_code"] == 0
         and process["tree_verified"] is True and process["timed_out"] is False,
         "GT10PC_P2_NATIVE_DRIVER_EXIT")
    receipt = json.loads((native / "receipt.json").read_bytes())
    need(receipt["process"]["exit_code"] == 0
         and receipt["process"]["wrapper_exit_code"] == 0
         and receipt["process"]["tree_verified"] is True
         and receipt["process"]["timed_out"] is False,
         "GT10PC_P2_NATIVE_GODOT_EXIT")
    need(project_ledger(project) == baseline_project,
         "GT10PC_P2_NATIVE_MUTATED_PROJECT")
    evidence = {}
    for name in ("install-before.json", "install-after.json", "project-before.json",
                 "project-after.json", "state-before.json", "state-after.json",
                 "native/receipt.json"):
        evidence[name] = digest_file(output / name)
    for base in (driver, native):
        for path in base.iterdir():
            if path.is_file():
                evidence[path.relative_to(output).as_posix()] = digest_file(path)
    write_json(output / "p2.json", {
        "schema": "hh-gt10pc-p2-native-rejection-1", "authority": 0,
        "acceptance": False, "target": args.target, "attacks": attacks,
        "install_root_before_sha256": digest_bytes(json.dumps(baseline_root, sort_keys=True).encode()),
        "project_before_sha256": digest_bytes(json.dumps(baseline_project, sort_keys=True).encode()),
        "last_good_active": installed["active"], "driver": process,
        "native_receipt": "native/receipt.json", "godot_exit": receipt["process"],
        "evidence": evidence, "artifact_sha256": digest_file(artifact),
        "source_closure_sha256": package["manifest"]["source_closure_sha256"],
    })
    print(json.dumps({"status": "P2_NATIVE_REJECTION_PASS", "authority": 0,
                      "acceptance": False, "attacks": len(attacks), "output": str(output)},
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
