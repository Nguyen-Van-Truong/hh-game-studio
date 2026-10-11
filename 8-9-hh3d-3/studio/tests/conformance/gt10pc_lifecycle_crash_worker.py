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

    published_count = 0

    def published(state, expected):
        nonlocal published_count
        result = publish(state, expected)
        published_count += 1
        if published_count == 1:
            callback("selector-before-addon-intent")
        elif published_count == 2:
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
    action = request.get("action", "install")
    stop_mode = request.get("disposition", "kill") == "stop"
    unpark = Path(request.get("unpark", str(Path(request["marker"]).with_suffix(".unpark"))))

    def cut(reached: str) -> None:
        if reached == phase:
            marker = Path(request["marker"])
            marker.parent.mkdir(parents=True, exist_ok=True)
            temporary = marker.with_name(marker.name + ".tmp")
            with temporary.open("w", encoding="utf-8") as stream:
                json.dump({"phase": reached, "pid": os.getpid(), "action": action,
                           "disposition": "stop" if stop_mode else "kill"}, stream,
                          sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, marker)
            if stop_mode:
                # The parent owns the external Stop command.  Parking here
                # keeps the cut between two real filesystem phases and lets
                # the parent record the stop receipt independently before
                # releasing this worker.
                deadline = time.monotonic() + float(request.get("park_seconds", 60))
                while not unpark.exists() and time.monotonic() < deadline:
                    time.sleep(0.05)
                if not unpark.exists():
                    raise TimeoutError("P7 stop unpark deadline")
                return
            deadline = time.monotonic() + float(request.get("park_seconds", 60))
            while time.monotonic() < deadline:
                time.sleep(0.1)  # Parent must kill the actual worker process.
            raise TimeoutError("P7 kill deadline")

    with instrument(installer, request["command_id"], cut):
        if action == "install":
            installer.install_lifecycle(Path(request["project"]), Path(request["package"]),
                                        command_id=request["command_id"],
                                        expected_state_sha256=request["state"])
        elif action == "rollback":
            installer.rollback_lifecycle(Path(request["project"]), destination=request["destination"],
                                         command_id=request["command_id"],
                                         expected_state_sha256=request["state"])
        else:
            raise ValueError("unsupported lifecycle action")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
