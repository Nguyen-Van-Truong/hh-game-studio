"""Bounded authenticated GT03 map authoring for the consumer pilot.

This lane owns only the pilot workspace. Every map mutation is submitted to the
GT03 publication transport; the resulting saved editor observation is converted
to ``input/map.json``. It does not tick GT03/GT06 and never writes studio files.
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import importlib.util
import json
import re
import sys
import time
from pathlib import Path

STUDIO = Path(__file__).resolve().parents[1] / "studio"
REPO = STUDIO.parent.parent
sys.path.insert(0, str(STUDIO.parent))


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def close_editor_owner(owner):
    editor = owner._editor
    owner.close()
    cleanup = editor._cleanup
    if not isinstance(cleanup, dict):
        raise RuntimeError("post-close editor cleanup missing")
    return cleanup


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--binary", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", args.run_id):
        parser.error("invalid run id")
    output = args.output.resolve()
    if output.exists():
        raise RuntimeError("output already exists")
    output.mkdir(parents=True)

    inventory = load("pilot_gt03_inventory", STUDIO / "tests/godot/run_editor_probe.py")
    fixture = load("pilot_gt03_fixture", STUDIO / "godot-addon/fixture_profile.py")
    runner = load("pilot_gt03_runner", STUDIO / "build/bootstrap/run_fixture.py")
    before = inventory.inputs()
    closure = runner.source_closure_sha256(before)
    write(output / "source-closure.json", {"files": before, "source_closure_sha256": closure})
    if sha(args.binary) != json.loads((STUDIO / "toolchain.lock.json").read_text())["godot"]["gui_sha256"]:
        raise RuntimeError("GT03 GUI binary pin mismatch")

    owner = server = reopened = None
    events: list[dict[str, object]] = []
    try:
        initial = fixture.compose(fixture.DEFAULT_SCENE, fixture.DEFAULT_SCRIPT,
            scene_revision="sha256:" + hashlib.sha256(fixture.DEFAULT_SCENE).hexdigest(),
            engine_sha256=load("pilot_validation", STUDIO / "godot-addon/validation_owner.py").executor.BINARY_SHA256)
        workspace = output / "owned"
        workspace.mkdir()
        publication = load("pilot_publication_owner", STUDIO / "godot-addon/publication_owner.py")
        transport_mod = publication._load("publication_transport")
        from studio.protocol import core
        from studio.host.core import transport as transport_core
        owner = publication.GodotPublicationOwner.create(workspace, project_id="consumer.pilot",
            initial_bundle=initial, editor_binary=args.binary, source_closure_sha256=closure)
        credential = owner.sessions.issue()
        server = transport_mod.PublicationTransport(owner).start()

        def call(path: str, body: dict, *, control: bool = False):
            port = server.stop_port if path == "/v1/stop" else server.control_port if control else server.port
            conn = http.client.HTTPConnection("127.0.0.1", port,
                timeout=95 if body.get("operation") == "scene.save" else 35)
            try:
                raw_body = core.canonical_bytes(body)
                conn.request("POST", path, raw_body, {
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + credential.bearer,
                    "X-HH-Catalog": owner.contract.CATALOG_DIGEST,
                })
                response = conn.getresponse()
                raw = response.read()
                value = core.parse_json(raw)
                return response.status, value, raw
            finally:
                conn.close()

        status, discovery, _ = call("/v1/discovery", {"project_id": owner.project_id})
        if status != 200 or discovery.get("project_id") != owner.project_id:
            raise RuntimeError("GT03 authenticated discovery failed")
        status, lease, _ = call("/v1/lease", {"project_id": owner.project_id, "ttl_ms": 90_000})
        if status != 200:
            raise RuntimeError("GT03 writer lease failed")

        def request(command_id: str, operation: str, target: str, payload: dict, before_state: dict, horizon: int = 25):
            value = {"expected_generation": before_state["generation"],
                     "expected_project_revision": before_state["project_revision"], **payload}
            return core.Request(command_id=command_id, project_id=owner.project_id,
                operation=operation, lease_id=lease["lease_id"], fencing_epoch=lease["fencing_epoch"],
                expected_revision=before_state["revision"], target={"stable_id": target},
                payload=value, payload_hash="sha256:" + hashlib.sha256(core.canonical_bytes(value)).hexdigest(),
                deadline_ms=min(lease["expires_ms"], transport_core.epoch_ms() + horizon * 1000))

        def edit(index: int, stable_id: str, name: str, pos: list[float], size: list[float]):
            before_state = owner.inspect()
            command = request(f"pilot.map.create.{index}", "scene.node.create", "root", {
                "stable_id": stable_id, "node_type": "MeshInstance3D", "name": name,
                "position": pos, "rotation_degrees": [0, 0, 0], "scale": [1, 1, 1],
                "box_size": size}, before_state)
            status, result, wire = call("/v1/commands", command.as_dict())
            write(output / f"create-{index}-response.json", {"http_status": status,
                "request": command.as_dict(), "response": result,
                "wire_sha256": hashlib.sha256(wire).hexdigest()})
            if status != 200 or result.get("status") != "COMMITTED" or result.get("postconditions", {}).get("public_ack") is not True:
                raise RuntimeError(f"GT03 map mutation failed: {stable_id}")
            after = owner.inspect()
            events.append({"command_id": command.command_id, "operation": command.operation,
                           "wire_sha256": hashlib.sha256(wire).hexdigest(),
                           "revision": after["revision"], "stable_id": stable_id,
                           "postconditions": result.get("postconditions", {})})
            return after

        state = edit(1, "floor", "Floor", [0, -0.5, 0], [12, 1, 12])
        state = edit(2, "player", "Player", [0, 0.5, 0], [0.8, 1, 0.8])
        state = edit(3, "pickup", "Pickup", [2, 0.5, 0], [0.7, 0.7, 0.7])
        nodes = []
        for node in state["state"]["nodes"]:
            if node.get("stable_id") in {"floor", "player", "pickup"}:
                nodes.append({key: node[key] for key in ("stable_id", "name", "position", "rotation_degrees", "scale", "box_size")})
        if {n["stable_id"] for n in nodes} != {"floor", "player", "pickup"}:
            raise RuntimeError("GT03 readback did not contain required map nodes")

        state_before_save = owner.inspect()
        credential = owner.sessions.rotate(credential)
        status, lease, _ = call("/v1/lease", {"project_id": owner.project_id, "ttl_ms": 90_000})
        if status != 200:
            raise RuntimeError("GT03 save lease refresh failed")
        expected = {name: state_before_save["working_files"][name]["sha256"]
                    for name in (owner.contract.SCENE_PATH, owner.contract.SCRIPT_PATH)}
        save_request = request("pilot.map.save", "scene.save", "root", {"expected_files": expected}, state_before_save, horizon=89)
        status, saved, wire = call("/v1/commands", save_request.as_dict())
        write(output / "save-response.json", {"http_status": status, "response": saved,
            "wire_sha256": hashlib.sha256(wire).hexdigest(), "request": save_request.as_dict()})
        if status != 200 or saved.get("status") != "COMMITTED":
            raise RuntimeError("GT03 scene save failed")
        map_data = {"schema": 1, "source": {"run_id": args.run_id, "source_closure_sha256": closure,
            "editor_revision": state_before_save["revision"], "save_command_id": save_request.command_id}, "nodes": nodes}
        write(output / "map.json", map_data)
        status, stopped, _ = call("/v1/stop", {"project_id": owner.project_id, "command_id": "pilot.stop"}, control=True)
        if status != 200:
            raise RuntimeError("GT03 stop response failed")
        deadline = time.monotonic() + 20
        while stopped.get("stop_persistence") == "PENDING" and time.monotonic() < deadline:
            time.sleep(0.05)
            status, stopped, _ = call("/v1/stop", {"project_id": owner.project_id, "command_id": "pilot.stop"}, control=True)
        if stopped.get("stop_persistence") != "DURABLE":
            raise RuntimeError("GT03 stop barrier not durable")
        storage_id = owner.storage_id
        owner.sessions.halt()
        server.close(); server = None
        editor_cleanup = close_editor_owner(owner)
        owner = None
        write(output / "editor-close.json", editor_cleanup)
        after_files = {name: sha(STUDIO / name) for name in before}
        if after_files != before:
            raise RuntimeError("GT03 source changed during pilot")
        write(output / "author-result.json", {"schema": 1, "run_id": args.run_id,
            "command_ids": [event["command_id"] for event in events] + [save_request.command_id],
            "source_closure_sha256": closure, "map_sha256": sha(output / "map.json"),
            "actual_editor_cleanup": editor_cleanup, "stop": stopped, "events": events,
            "storage_id": storage_id, "authority": 0, "gt03_acceptance": False,
            "gt06_acceptance": False, "source_unchanged": True})
        print("HH_CONSUMER_GT03_AUTHOR_COMPLETE", flush=True)
        return 0
    except Exception as error:
        write(output / "author-failure.json", {"run_id": args.run_id, "authority": 0,
            "error_type": type(error).__name__, "error": str(error), "events": events})
        raise
    finally:
        cleanup_errors = []
        for resource in (server, owner, reopened):
            if resource is not None:
                try:
                    resource.close()
                except Exception as error:
                    cleanup_errors.append({"resource": type(resource).__name__, "error": str(error)})
        write(output / "author-finally.json", {"run_id": args.run_id, "cleanup_errors": cleanup_errors,
            "source_unchanged": all(sha(STUDIO / name) == digest for name, digest in before.items())})
        if cleanup_errors:
            raise RuntimeError("author cleanup failed; see author-finally.json")


if __name__ == "__main__":
    raise SystemExit(main())
