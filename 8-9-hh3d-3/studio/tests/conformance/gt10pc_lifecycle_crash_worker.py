"""Host crash worker for the combined selector/addon lifecycle.

The parent owns the process handle and records the real non-zero exit.  This
worker deliberately terminates at one durable phase; it is never used as
acceptance evidence by itself.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
import os
from pathlib import Path
import sys
import time
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from package.consumer_install import ConsumerInstall
from package import addon_transaction as addon
from package import lifecycle_transaction as lifecycle


@contextmanager
def instrument(installer, command_id, callback):
    """Diagnostic instrumentation stays wholly outside the shipped API."""
    prepare = addon.prepare
    publish = installer._publish
    stage = installer._stage
    rename = os.rename
    replace = os.replace

    def prepared(*args, **kwargs):
        result = prepare(*args, **kwargs)
        callback("staged")
        callback("before-selector")
        return result

    def published(state, expected):
        result = publish(state, expected)
        if command_id not in state["commands"]:
            callback("selector-before-addon-intent")
        else:
            callback("journal-published")
        return result

    def staged(verified):
        result = stage(verified)
        callback("release-renamed")
        return result

    def renamed(source, destination):
        result = rename(source, destination)
        name = Path(destination).name
        if name == "backup": callback("old-addon-moved")
        if name == "hh_studio": callback("new-addon-moved")
        return result

    def replaced(source, destination):
        result = replace(source, destination)
        if Path(destination).name == ".addon-pending.json": callback("addon-intent")
        return result

    with mock.patch.object(addon, "prepare", prepared), mock.patch.object(installer, "_publish", published), \
         mock.patch.object(installer, "_stage", staged), mock.patch.object(os, "rename", renamed), \
         mock.patch.object(os, "replace", replaced):
        yield


def main() -> int:
    request = json.loads(Path(sys.argv[1]).read_bytes())
    installer = ConsumerInstall(Path(request["install"]),
                                trusted_keys={request["key_id"]: bytes.fromhex(request["public_key"])})
    phase = request["phase"]

    def cut(reached: str) -> None:
        if reached == phase:
            marker = Path(request["marker"])
            marker.write_text(json.dumps({"phase": reached, "pid": os.getpid()}), encoding="utf-8")
            while True:
                time.sleep(1)  # The parent must kill the actual worker process.

    with instrument(installer, request["command_id"], cut):
        installer.install_lifecycle(Path(request["project"]), Path(request["package"]),
                                    command_id=request["command_id"],
                                    expected_state_sha256=request["state"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
