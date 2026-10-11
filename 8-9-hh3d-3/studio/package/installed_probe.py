"""Short native consumer diagnostic, executed from an installed release."""
from __future__ import annotations
import argparse
import json
import os
import importlib.util
from pathlib import Path
import sys
from .consumer_install import ConsumerInstall
from .release_contract import digest_file, need
from .trust import load_trust
from ..build.bootstrap.run_fixture import run_process, _isolated_user_env

STUDIO = Path(__file__).resolve().parents[1]


def profile_discovery(output: Path, project: Path, fixture: str) -> dict:
    """Exercise the actual source-bound adapter; no mock owner or credentials."""
    path = STUDIO / "godot-addon/gameplay_source_adapter.py"
    spec = importlib.util.spec_from_file_location("hh_installed_gameplay_adapter", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    # This source-bound module rejects stale bytecode. Match its import path.
    exec(compile(path.read_bytes(), str(path), "exec", dont_inherit=True), module.__dict__)
    owner_module = module._owner_module()
    files, closure = owner_module.runtime_source_closure()
    project_id = "project.registered." + fixture.removeprefix("gt09-")
    # Godot has already exercised this exact fixture. Only the actual source
    # bundle, not installed addon or consumer saves, belongs to source owner.
    baseline = {name.relative_to(STUDIO / "fixtures" / fixture).as_posix(): name.read_bytes()
                for name in (STUDIO / "fixtures" / fixture).rglob("*")
                if name.is_file() and name.name != "project.godot"}
    parent = output / "profile-owner"
    parent.mkdir()
    owner = owner_module.GameplaySourcePublicationOwner.create(parent.absolute(), project_id=project_id,
                source_files=baseline, entrypoint=owner_module.ENTRYPOINT, source_closure_sha256=closure)
    try:
        profile = module.load_fixture_host_profile(project_id)
        adapter = module.GameplaySourceAdapter(owner, host_profile=profile)
        default = module.GameplaySourceAdapter(owner)
        own = adapter.profile_discovery()
        other = adapter.profile_discovery(project_id="project.consumer.other")
        hidden = default.profile_discovery()
        need(own["fixture_enabled"] and len(own["profiles"]) == 1
             and other["profiles"] == [] and hidden["profiles"] == []
             and module.load_fixture_host_profile("project.consumer.other") is None,
             "installed profile isolation failed")
        return {"own": own, "other": other, "default": hidden,
                "runtime_source_closure_sha256": closure, "runtime_files": files}
    finally:
        owner.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    for name in ("install-root", "project", "godot", "output", "trust"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--trust-sha256", required=True)
    parser.add_argument("--fixture", required=True, choices=("gt09-arena", "gt09-room"))
    parser.add_argument("--target", choices=("Windows", "Linux-headless"), default="Windows")
    args = parser.parse_args()
    keys = load_trust(args.trust, expected_sha256=args.trust_sha256)
    need((args.target == "Windows") == (os.name == "nt"), "native target/OS mismatch")
    install = ConsumerInstall(args.install_root, trusted_keys=keys, target=args.target)
    need(install.active_path() == STUDIO, "probe did not import installed source")
    lock = json.loads((STUDIO / "toolchain.lock.json").read_bytes())
    godot_hash = (lock["godot"]["console_sha256"] if args.target == "Windows" else
                  json.loads((STUDIO / "godot-addon/validator-toolchain.lock.json").read_bytes())["binary_sha256"])
    need(digest_file(args.godot) == godot_hash, "Godot pin mismatch")
    args.output.mkdir(parents=True, exist_ok=False)
    parse = run_process([str(args.godot), "--headless", "--path", str(args.project),
                         "--check-only", "--script", "res://addons/hh_studio/plugin.gd"],
                        cwd=args.project, output=args.output, timeout=30, label="parse",
                        env=_isolated_user_env(args.output))
    need(parse["exit_code"] == 0 and parse["wrapper_exit_code"] == 0
         and parse["tree_verified"] and not parse["timed_out"], "installed addon failed Godot parse")
    invocation = [str(args.godot), "--headless", "--path", str(args.project),
                  "--scene", "scenes/fixture.tscn", "--max-fps", "60",
                  "--", "--fixture-lifecycle-smoke"]
    result = run_process(invocation, cwd=args.project, output=args.output,
                         timeout=60, label="godot", env=_isolated_user_env(args.output))
    profile = profile_discovery(args.output, args.project, args.fixture)
    state = install.snapshot()
    release = install._read_release(state["active"])
    receipt = {"schema": "hh-installed-native-probe-2", "studio": str(STUDIO),
               "active_release": state["active"], "parse": parse,
               "version": release["version"], "package_schema": release["schema"],
               "target": args.target, "os_name": os.name, "profile": profile,
               "probe_sha256": digest_file(Path(__file__)),
               "launcher_sha256": digest_file(STUDIO / "build/bootstrap/run_fixture.py"),
               "godot_sha256": digest_file(args.godot), "process": result}
    with (args.output / "receipt.json").open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, sort_keys=True)
    print(json.dumps({"output": str(args.output), "exit": result["exit_code"]}))
    return 0 if result["exit_code"] == 0 and result["wrapper_exit_code"] == 0 and result["tree_verified"] and not result["timed_out"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
