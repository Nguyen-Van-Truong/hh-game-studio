"""Short native consumer diagnostic, executed from an installed release."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .consumer_install import ConsumerInstall
from .release_contract import digest_file, need
from .trust import load_trust
from ..build.bootstrap.run_fixture import run_process, _isolated_user_env

STUDIO = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    for name in ("install-root", "project", "godot", "output", "trust"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--trust-sha256", required=True)
    args = parser.parse_args()
    keys = load_trust(args.trust, expected_sha256=args.trust_sha256)
    install = ConsumerInstall(args.install_root, trusted_keys=keys)
    need(install.active_path() == STUDIO, "probe did not import installed source")
    lock = json.loads((STUDIO / "toolchain.lock.json").read_bytes())
    need(digest_file(args.godot) == lock["godot"]["console_sha256"], "Godot pin mismatch")
    args.output.mkdir(parents=True, exist_ok=False)
    invocation = [str(args.godot), "--headless", "--path", str(args.project),
                  "--scene", "scenes/fixture.tscn", "--max-fps", "60",
                  "--", "--fixture-lifecycle-smoke"]
    result = run_process(invocation, cwd=args.project, output=args.output,
                         timeout=60, label="godot", env=_isolated_user_env(args.output))
    receipt = {"schema": "hh-installed-native-probe-1", "studio": str(STUDIO),
               "probe_sha256": digest_file(Path(__file__)),
               "launcher_sha256": digest_file(STUDIO / "build/bootstrap/run_fixture.py"),
               "godot_sha256": digest_file(args.godot), "process": result}
    with (args.output / "receipt.json").open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, sort_keys=True)
    print(json.dumps({"output": str(args.output), "exit": result["exit_code"]}))
    return 0 if result["exit_code"] == 0 and result["wrapper_exit_code"] == 0 and result["tree_verified"] and not result["timed_out"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
