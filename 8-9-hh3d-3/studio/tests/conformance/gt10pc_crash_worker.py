"""Test-only process cut harness; no failpoint is exposed by the installer API."""
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.package.consumer_install import ConsumerInstall
from studio.package import addon_transaction


def main() -> int:
    request = json.loads(Path(sys.argv[1]).read_bytes())
    install = ConsumerInstall(Path(request["install"]), trusted_keys={"test": bytes.fromhex(request["public_key"])})
    marker = Path(request["marker"])

    def park(phase):
        if request["phase"] != phase:
            return
        with marker.open("x") as stream:
            json.dump({"phase": phase, "pid": os.getpid()}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        while True:
            time.sleep(1)  # Parent must kill this process, not raise an exception.

    real_rename = addon_transaction.os.rename
    def rename(source, destination):
        result = real_rename(source, destination)
        destination = Path(destination)
        if destination.name == ".addon-pending.json": park("intent")
        if destination.name == "backup": park("old-moved")
        if destination.name == "hh_studio": park("new-moved")
        return result
    addon_transaction.os.rename = rename
    real_publish = install._publish
    def publish(state, expected):
        result = real_publish(state, expected)
        park("state-published")
        return result
    install._publish = publish
    install.install_addon(Path(request["project"]), release=request["release"],
                          command_id="crashed-addon", expected_state_sha256=request["state"])
    raise RuntimeError("cut point was not reached")


if __name__ == "__main__":
    raise SystemExit(main())
