"""Frozen external-HTTP proof for the unsaved Blender writer integration candidate.

Credentials enter the separately owned CLI through gated stdin only. This probe
does not connect save/export, claim durable scene state, or accept GT04.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import http.client
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

sys.dont_write_bytecode = True
STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from run_blender_ipc_probe import load, sources
from run_client_ledger_probe import cleanup_passed, host_artifact_passed, safe_failure, write_json
from run_absolute_deadline_probe import (
    evidence_inventory, sha, utc_now, valid_run_id,
    unit_program as base_unit_program, unit_completion as base_unit_completion,
    UNIT_INVENTORY as BASE_INVENTORY, UNIT_COMPLETE as BASE_COMPLETE,
)

CLIENT_COMPLETE = "GT04_WRITER_HTTP_COMPLETE "
NATIVE_COMPLETE = "GT04_WRITER_NATIVE_COMPLETE "
UNIT_INVENTORY = "GT04_WRITER_UNIT_INVENTORY "
UNIT_COMPLETE = "GT04_WRITER_UNIT_COMPLETE "
MAX_CLIENT_BYTES = 262144
CLIENT_CHECKS = frozenset({
    "writer_discovery_exact", "reader_discovery_readonly", "readonly_write_lease_rejected",
    "registered_writer_lease", "registered_read_lease", "initial_inspect_committed",
    "initial_empty_owned_scene", "create_committed", "create_one_exact_box",
    "duplicate_same_wire", "changed_payload_conflict", "own_lookup_same_wire",
    "foreign_lookup_denied", "foreign_writer_known_id_rejected", "readonly_write_denied", "expired_fresh_rejected",
    "transform_committed", "transform_exact", "material_committed", "material_exact",
    "undo_committed", "undo_restores_transform_scene", "redo_committed",
    "redo_restores_material_scene", "final_inspect_committed", "read_matches_latest_revision",
    "stop_port_is_separate", "stop_only_listener_rejects_lookup", "native_stop_observed",
    "stopped_discovery_empty", "historical_receipt_survives_stop",
})
NATIVE_CHECKS = frozenset({
    "separate_cli_exit_zero_and_owned_tree_empty", "client_complete_and_scoped",
    "seven_native_data_commands_only", "final_owner_observation_matches_client",
    "transport_drained_before_gui_release", "native_gui_exit_zero_and_owned_tree_empty",
    "credentials_absent_from_captured_evidence",
})


def parser():
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--client", action="store_true", help=argparse.SUPPRESS)
    value.add_argument("--frozen", action="store_true", help=argparse.SUPPRESS)
    value.add_argument("--output", type=Path)
    value.add_argument("--run-id", type=valid_run_id)
    value.add_argument("--binary", type=Path)
    value.add_argument("--unit-suite", choices=("focused", "all"), default="focused")
    return value


def checks_complete(rows, required):
    if type(rows) is not list or len(rows) != len(required):
        return False
    if any(type(row) is not dict or set(row) != {"label", "passed"} for row in rows):
        return False
    labels = [row["label"] for row in rows]
    return all(type(label) is str for label in labels) and set(labels) == required \
        and all(row["passed"] is True for row in rows)


def client_report(stdout):
    if type(stdout) is not bytes or not 0 < len(stdout) <= MAX_CLIENT_BYTES:
        raise ValueError("bounded writer client output required")
    lines = stdout.decode("utf-8", "strict").splitlines()
    if len(lines) != 1 or not lines[0].startswith(CLIENT_COMPLETE):
        raise ValueError("unique writer client completion required")
    report = json.loads(lines[0][len(CLIENT_COMPLETE):])
    if type(report) is not dict or report.get("passed") is not True \
            or not checks_complete(report.get("checks"), CLIENT_CHECKS) \
            or type(report.get("pid")) is not int or report["pid"] <= 0 \
            or report.get("public_ack") is not False or report.get("scene_state_durable") is not False \
            or report.get("formal_acceptance") is not False:
        raise ValueError("complete scoped writer client proof required")
    return report


def client():
    from studio.host.core.transport import epoch_ms
    from studio.host.blender import client_write_catalog as catalog
    from studio.protocol.core import Discovery, Request, Response, canonical_bytes, parse_json

    rows = []
    calls = []
    observed = {}
    failure = None
    config = {}

    def check(label, condition):
        rows.append({"label": label, "passed": condition is True})
        if condition is not True:
            raise AssertionError(label)

    try:
        raw_config = sys.stdin.buffer.read(65537)
        if not 0 < len(raw_config) <= 65536:
            raise ValueError("bounded client configuration required")
        config = parse_json(raw_config)
        end = time.monotonic() + 35

        def call(path, body, *, role="writer", port=None):
            selected = config["stop_port"] if path == "/v1/stop" else (
                config["control_port"] if path == "/v1/lookup" else config["port"])
            selected = port if port is not None else selected
            remaining = end - time.monotonic()
            if remaining <= 0 or len(calls) >= 32:
                raise TimeoutError("bounded writer HTTP client exhausted")
            encoded = canonical_bytes(body)
            connection = http.client.HTTPConnection("127.0.0.1", selected, timeout=min(5, remaining))
            try:
                connection.request("POST", path, encoded, {
                    "Content-Type": "application/json", "Authorization": "Bearer " + config[role],
                    "X-HH-Catalog": catalog.CATALOG_DIGEST,
                })
                received = connection.getresponse()
                raw = received.read(catalog.MAX_WIRE + 1)
                if len(raw) > catalog.MAX_WIRE:
                    raise ValueError("writer response byte cap")
                decoded = parse_json(raw)
                calls.append({
                    "route": path, "request": parse_json(encoded), "request_sha256": sha(encoded),
                    "role": role, "listener": {
                        config["port"]: "work", config["control_port"]: "control", config["stop_port"]: "stop",
                    }[selected], "http_status": received.status,
                    "response_wire": raw.decode("utf-8"), "response_sha256": sha(raw),
                })
                return received.status, decoded, raw
            finally:
                connection.close()

        project = {"project_id": config["project_id"]}
        status, value, _ = call("/v1/discovery", project)
        discovery = Discovery.from_dict(value)
        check("writer_discovery_exact", status == 200 and discovery.project_id == config["project_id"]
              and discovery.schema_digest == catalog.CATALOG_DIGEST and discovery.build == config["source_sha256"]
              and {cap.operation for cap in discovery.capabilities} == catalog.EDIT_OPERATIONS | {catalog.READ}
              and all(cap.write_scopes == (() if cap.operation == catalog.READ else ("blender.scene.write",))
                      for cap in discovery.capabilities))
        status, value, _ = call("/v1/discovery", project, role="reader")
        reader = Discovery.from_dict(value)
        check("reader_discovery_readonly", status == 200
              and [cap.operation for cap in reader.capabilities] == [catalog.READ]
              and reader.capabilities[0].write_scopes == ())
        status, denied, _ = call("/v1/lease", {**project, "access": "write", "ttl_ms": 30000}, role="reader")
        check("readonly_write_lease_rejected", status == 400 and denied["code"] == "BLENDER_WRITER_GRANT_REQUIRED")
        status, writer_lease, _ = call("/v1/lease", {**project, "access": "write", "ttl_ms": 30000})
        check("registered_writer_lease", status == 200 and writer_lease["access"] == "write"
              and type(writer_lease["fencing_epoch"]) is int and writer_lease["fencing_epoch"] > 0
              and writer_lease["target"] == {"stable_id": catalog.TARGET}
              and writer_lease["revision"] == config["expected"]["revision"]
              and writer_lease["catalog_digest"] == catalog.CATALOG_DIGEST)
        status, read_lease, _ = call("/v1/lease", {**project, "access": "read", "ttl_ms": 30000})
        check("registered_read_lease", status == 200 and read_lease["fencing_epoch"] == 0
              and read_lease["access"] == "read" and read_lease["target"] == writer_lease["target"])

        def request(key, operation, state, arguments=None, *, expired=False):
            write = operation != catalog.READ
            lease = writer_lease if write else read_lease
            payload = {"expected_context": state["context"], "arguments": arguments or {}} if write else {}
            maximum = catalog.MAX_UI_MS if write else catalog.MAX_READ_MS
            deadline = epoch_ms() - 1 if expired else min(lease["expires_ms"], epoch_ms() + maximum)
            return Request(key, config["project_id"], operation, lease["lease_id"], lease["fencing_epoch"],
                           state["revision"], lease["target"], payload, sha(canonical_bytes(payload)), deadline)

        def submit(label, value):
            status, reply, raw = call("/v1/commands", value.as_dict())
            response = Response.from_dict(reply)
            post = response.postconditions
            observation = post.get("observation", {})
            scene = observation.get("scene", {})
            check(label + "_committed", status == 200 and response.status.value == "COMMITTED"
                  and response.code == "BLENDER_CLIENT_READBACK" and response.command_id == value.command_id
                  and response.result_revision == scene.get("revision") == observation.get("native_revision")
                  and response.result_hash == sha(canonical_bytes(observation))
                  and post.get("hash_domain") == "jcs-observation-v1"
                  and post.get("public_ack") is False and post.get("scene_state_durable") is False
                  and post.get("durable_publication") is False and post.get("ledger_receipt_only") is True
                  and post.get("read_only") is (value.operation == catalog.READ)
                  and post.get("live_edits_unsaved") is (value.operation != catalog.READ)
                  and observation.get("source_sha256") == config["source_sha256"]
                  and observation.get("pid") == config["native_pid"]
                  and observation.get("generation") == config["generation"])
            observed[label] = scene
            return scene, raw

        initial, _ = submit("initial_inspect", request("Writer.Initial", catalog.READ, config["expected"]))
        check("initial_empty_owned_scene", initial == config["expected"] and initial["snapshot"]["objects"] == [])
        create = request("Writer.Box/Create", "mesh.create_box", initial, {"object_id": "probe_box", "size": [1, 2, 3]})
        created, create_wire = submit("create", create)
        objects = created["snapshot"]["objects"]
        exact_box = len(objects) == 1 and objects[0]["object_id"] == "probe_box"
        if exact_box:
            vertices = objects[0]["vertices"]
            exact_box = len(vertices) == 8 and len(objects[0]["faces"]) == 6
            exact_box = exact_box and [max(v[axis] for v in vertices) - min(v[axis] for v in vertices)
                                      for axis in range(3)] == [1, 2, 3]
        check("create_one_exact_box", exact_box and created["context"] == initial["context"])
        status, _, retried = call("/v1/commands", create.as_dict())
        check("duplicate_same_wire", status == 200 and retried == create_wire)
        changed_payload = {"expected_context": initial["context"], "arguments": {"object_id": "probe_box", "size": [2, 2, 3]}}
        conflicting = replace(create, payload=changed_payload, payload_hash=sha(canonical_bytes(changed_payload)))
        status, denied, _ = call("/v1/commands", conflicting.as_dict())
        check("changed_payload_conflict", status == 200 and denied["status"] == "REJECTED"
              and denied["code"] == "BLENDER_LEDGER_COMMAND_CONFLICT")
        query = {**project, "command_id": create.command_id}
        status, _, looked_up = call("/v1/lookup", query)
        check("own_lookup_same_wire", status == 200 and looked_up == create_wire)
        status, denied, _ = call("/v1/lookup", query, role="reader")
        check("foreign_lookup_denied", status == 200 and denied["status"] == "REJECTED"
              and denied["code"] == "BLENDER_LEDGER_COMMAND_NOT_FOUND")
        status, denied, _ = call("/v1/commands", create.as_dict(), role="foreign")
        check("foreign_writer_known_id_rejected", status == 200 and denied["status"] == "REJECTED"
              and denied["code"] == "BLENDER_LEDGER_COMMAND_OWNER"
              and denied.get("result_revision") is None and denied.get("result_hash") is None
              and "observation" not in denied.get("postconditions", {}))
        readonly = request("Reader.WriteDenied", "mesh.create_box", created, {"object_id": "unauthorized_box", "size": [1, 1, 1]})
        status, denied, _ = call("/v1/commands", readonly.as_dict(), role="reader")
        check("readonly_write_denied", status == 200 and denied["status"] == "REJECTED"
              and denied["code"] == "BLENDER_OPERATION_FORBIDDEN")
        expired = request("Writer.Expired", "mesh.create_box", created, {"object_id": "expired_box", "size": [1, 1, 1]}, expired=True)
        status, denied, _ = call("/v1/commands", expired.as_dict())
        check("expired_fresh_rejected", status == 200 and denied["status"] == "REJECTED"
              and denied["code"] == "BLENDER_DEADLINE_EXPIRED")

        transform = {"object_id": "probe_box", "location": [2, -3, 4], "rotation": [0.25, 0, -0.5], "scale": [1, 2, 0.5]}
        transformed, _ = submit("transform", request("Writer.Transform", "object.transform.set", created, transform))
        item = transformed["snapshot"]["objects"][0]
        check("transform_exact", len(transformed["snapshot"]["objects"]) == 1
              and all(item[key] == transform[key] for key in ("location", "rotation", "scale")))
        material = {"object_id": "probe_box", "material_id": "probe_copper", "base_color": [0.25, 0.5, 0.75],
                    "metallic": 0.5, "roughness": 0.25}
        painted, _ = submit("material", request("Writer.Material", "material.set_principled", transformed, material))
        actual_material = painted["snapshot"]["objects"][0]["material"]
        check("material_exact", actual_material["material_id"] == material["material_id"]
              and actual_material["base_color"] == material["base_color"] + [1]
              and actual_material["metallic"] == material["metallic"]
              and actual_material["roughness"] == material["roughness"])
        undone, _ = submit("undo", request("Writer.Undo", "history.undo", painted))
        check("undo_restores_transform_scene", undone == transformed)
        redone, _ = submit("redo", request("Writer.Redo", "history.redo", undone))
        check("redo_restores_material_scene", redone == painted)
        final, _ = submit("final_inspect", request("Writer.Final", catalog.READ, redone))
        check("read_matches_latest_revision", final == redone and len(final["snapshot"]["objects"]) == 1)
        check("stop_port_is_separate", len({config["port"], config["control_port"], config["stop_port"]}) == 3)
        status, denied, _ = call("/v1/lookup", query, port=config["stop_port"])
        check("stop_only_listener_rejects_lookup", status == 400 and denied["code"] == "UNSUPPORTED_ROUTE")
        began = time.monotonic()
        status, stopped, _ = call("/v1/stop", {**project, "command_id": "Writer.Stop"})
        check("native_stop_observed", status == 200 and stopped["status"] == "COMMITTED"
              and stopped["code"] == "BLENDER_STOP_OBSERVED" and time.monotonic() - began < 3)
        status, stopped_discovery, _ = call("/v1/discovery", project)
        check("stopped_discovery_empty", status == 200 and stopped_discovery["capabilities"] == [])
        status, _, historical = call("/v1/lookup", query)
        check("historical_receipt_survives_stop", status == 200 and historical == create_wire)
    except BaseException as error:
        failure = safe_failure(error)
    report = {"passed": failure is None and checks_complete(rows, CLIENT_CHECKS), "failure": failure,
              "pid": os.getpid(), "checks": rows, "calls": calls, "observed": observed,
              "public_ack": False, "scene_state_durable": False, "formal_acceptance": False}
    from studio.protocol.core import canonical_bytes
    raw = canonical_bytes(report)
    if len(raw) > MAX_CLIENT_BYTES or any(type(config.get(role)) is str and config[role].encode() in raw
                                        for role in ("writer", "reader", "foreign")):
        raw = canonical_bytes({"passed": False, "failure": {"type": "EvidenceRejected", "code": None}})
        report["passed"] = False
    print(CLIENT_COMPLETE + raw.decode("utf-8"), flush=True)
    return int(not report["passed"])


def cli_cleanup_passed(value):
    if type(value) is not dict or type(value.get("pid")) is not int or value["pid"] <= 0 \
            or type(value.get("exit_code")) is not int or value["exit_code"] != 0 or value.get("timed_out") is not False:
        return False
    job = value.get("job")
    return type(job) is dict and job.get("zero_observed") is True and type(job.get("active_count")) is int \
        and job["active_count"] == 0 and job.get("closed") is True and job.get("handle_retained") is False


def frozen(output, binary, run_id, closure):
    from studio.host.blender.ui_host import BlenderUIHost, cli_job
    from studio.host.blender.durable_session import DurableBlenderSession
    from studio.host.blender.client_writer_owner import BlenderWriterClientOwner
    from studio.host.blender.client_transport import BlenderClientTransport
    from studio.host.blender import client_write_catalog as catalog
    from studio.protocol.core import canonical_bytes, parse_json

    gui = server = process = client_job = owner = None
    cleanup = child_cleanup = child = None
    rows = []
    secrets = []
    failure = None
    cleanup_errors = []
    stdout = stderr = b""
    drained = False
    timed_out = False

    def record(label, condition):
        rows.append({"label": label, "passed": condition is True})
        print("GT04_WRITER_CHECK " + json.dumps(rows[-1]), flush=True)
        return condition is True

    def check(label, condition):
        if not record(label, condition):
            raise AssertionError(label)

    try:
        try:
            gui = BlenderUIHost(output, binary=binary, session_seconds=90)
        except BaseException as error:
            retained = getattr(error, "cleanup_owner", None)
            if type(retained) is BlenderUIHost:
                gui = retained
            raise
        secrets.extend(channel.key.hex().encode("ascii") for channel in gui.channels.values())
        durable = DurableBlenderSession(gui.directory / "journal", host=gui)
        owner = BlenderWriterClientOwner.from_session(durable)
        operations = catalog.EDIT_OPERATIONS | {catalog.READ, "control.lookup", "control.stop"}
        writer = owner.sessions.issue(operations=operations)
        reader = owner.sessions.issue(operations=frozenset({catalog.READ, "control.lookup", "control.stop"}))
        foreign = owner.sessions.issue(operations=frozenset({catalog.READ, "mesh.create_box", "control.lookup"}))
        secrets.extend(value.bearer.encode("ascii") for value in (writer, reader, foreign))
        server = BlenderClientTransport(owner)
        server.start()
        before = gui.channels["data"].sent
        config = {"project_id": owner.project_id, "port": server.port, "control_port": server.control_port,
                  "stop_port": server.stop_port, "writer": writer.bearer, "reader": reader.bearer,
                  "foreign": foreign.bearer,
                  "expected": parse_json(owner._read_owner._baseline), "native_pid": gui.pid,
                  "generation": gui._session, "source_sha256": owner._source_sha256}
        encoded = canonical_bytes(config)
        if len(encoded) > 65536:
            raise ValueError("bounded client configuration required")
        process = subprocess.Popen([sys.executable, "-B", str(Path(__file__).resolve()), "--client"],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        # The child cannot authenticate or launch work until its stdin closes.
        # Retain a failed Job constructor before allowing any child input.
        try:
            client_job = cli_job.create(process)
        except BaseException as error:
            client_job = getattr(error, "cleanup_owner", None) or cli_job.owner_for_process(process)
            raise
        try:
            stdout, stderr = process.communicate(encoded, timeout=40)
        except subprocess.TimeoutExpired:
            timed_out = True
            raise
        finally:
            encoded = b""
            config.clear()
        client_job.close()
        child_cleanup = {"pid": process.pid, "exit_code": process.returncode, "timed_out": timed_out,
                         "job": client_job.snapshot()}
        write_json(output, "client-exit.json", child_cleanup)
        if any(secret in stdout + stderr for secret in secrets) or len(stdout) > MAX_CLIENT_BYTES or len(stderr) > MAX_CLIENT_BYTES:
            raise ValueError("client log evidence rejected")
        for name, raw in (("client-stdout.txt", stdout), ("client-stderr.txt", stderr)):
            with (output / name).open("xb") as stream:
                stream.write(raw)
        check("separate_cli_exit_zero_and_owned_tree_empty", process.pid != os.getpid()
              and cli_cleanup_passed(child_cleanup) and not stderr)
        child = client_report(stdout)
        check("client_complete_and_scoped", child["pid"] == process.pid)
        write_json(output, "client.json", child)
        check("seven_native_data_commands_only", gui.channels["data"].sent == before + 7)
        check("final_owner_observation_matches_client", parse_json(owner._read_owner._baseline) == child["observed"]["final_inspect"])
    except BaseException as error:
        failure = safe_failure(error)
    finally:
        if process is not None:
            if process.poll() is None:
                try:
                    if client_job is not None:
                        client_job.terminate()
                    else:
                        process.kill()
                    stdout, stderr = process.communicate(timeout=5)
                except Exception as error:
                    cleanup_errors.append(safe_failure(error))
            if client_job is not None:
                try:
                    client_job.close()
                except Exception as error:
                    cleanup_errors.append(safe_failure(error))
            for pipe in (process.stdin, process.stdout, process.stderr):
                if pipe is not None and not pipe.closed:
                    pipe.close()
            if child_cleanup is None:
                child_cleanup = {"pid": process.pid, "exit_code": process.returncode,
                                 "timed_out": timed_out, "job": client_job.snapshot() if client_job else None}
                try:
                    write_json(output, "client-exit.json", child_cleanup)
                except Exception as error:
                    cleanup_errors.append(safe_failure(error))
        if server is not None:
            for attempt in range(2):
                try:
                    if owner is not None and not owner.sessions._stopped.is_set():
                        owner._durable.stop()
                    server.close()
                    drained = True
                    break
                except Exception as error:
                    cleanup_errors.append(safe_failure(error))
                    if gui is not None:
                        try:
                            gui.stop()
                        except Exception as stop_error:
                            cleanup_errors.append(safe_failure(stop_error))
        record("transport_drained_before_gui_release", drained)
        if gui is not None and (server is None or drained):
            for attempt in range(2):
                try:
                    cleanup = gui.close()
                    break
                except Exception as error:
                    cleanup_errors.append(safe_failure(error))
        record("native_gui_exit_zero_and_owned_tree_empty", cleanup_passed(cleanup, getattr(gui, "pid", None)))

    # Preserve bounded failure diagnostics too, after the same secret check.
    # Failed evidence never overrides a prior artifact or becomes a PASS.
    if process is not None:
        for name, raw in (("client-stdout.txt", stdout), ("client-stderr.txt", stderr)):
            if not (output / name).exists() and len(raw) <= MAX_CLIENT_BYTES and all(secret not in raw for secret in secrets):
                try:
                    with (output / name).open("xb") as stream:
                        stream.write(raw)
                except Exception as error:
                    cleanup_errors.append(safe_failure(error))
    clean = bool(secrets)
    try:
        for path in output.rglob("*"):
            if path.is_file() and path.relative_to(output).parts[0] != "source":
                raw = path.read_bytes()
                clean = clean and all(secret and secret not in raw for secret in secrets)
    except Exception as error:
        clean = False
        cleanup_errors.append(safe_failure(error))
    record("credentials_absent_from_captured_evidence", clean)
    report = {"run_id": run_id, "source_closure_sha256": closure, "finished_at": utc_now(),
              "passed": failure is None and checks_complete(rows, NATIVE_CHECKS), "failure": failure,
              "checks": rows, "cleanup_errors": cleanup_errors, "cleanup": cleanup,
              "client_cleanup": child_cleanup, "client_checks": len(child["checks"]) if child else 0,
              "probe_pid": os.getpid(), "native_pid": getattr(gui, "pid", None),
              "gui_directory": gui.directory.name if gui is not None and hasattr(gui, "directory") else None,
              "public_ack": False, "scene_state_durable": False, "formal_acceptance": False}
    write_json(output, "writer-native.json", report)
    print(NATIVE_COMPLETE + json.dumps({"passed": report["passed"], "checks": len(rows),
                                      "client_checks": report["client_checks"]}), flush=True)
    return int(not report["passed"])


def native_completion(output, host):
    try:
        if not host_artifact_passed(output, host):
            return False
        report = json.loads((output / "writer-native.json").read_bytes())
        manifest = json.loads((output / "source-closure.json").read_bytes())
        if type(report.get("run_id")) is not str or not report["run_id"] \
                or type(report.get("source_closure_sha256")) is not str or not report["source_closure_sha256"] \
                or report.get("run_id") != manifest.get("run_id") \
                or report.get("source_closure_sha256") != manifest.get("source_closure_sha256") \
                or not checks_complete(report.get("checks"), NATIVE_CHECKS):
            return False
        directory = report.get("gui_directory")
        if type(directory) is not str or len(directory) != 40 or not directory.startswith("blender-") \
                or any(char not in "0123456789abcdef" for char in directory[8:]):
            return False
        raw_exit = json.loads((output / directory / "process-exit.json").read_bytes())
        raw_close = json.loads((output / directory / "close.json").read_bytes())
        cli_exit = json.loads((output / "client-exit.json").read_bytes())
        child = client_report((output / "client-stdout.txt").read_bytes())
        saved_child = json.loads((output / "client.json").read_bytes())
        lines = (output / "native-stdout.txt").read_text(encoding="utf-8").splitlines()
        markers = [json.loads(line[len(NATIVE_COMPLETE):]) for line in lines if line.startswith(NATIVE_COMPLETE)]
        return report.get("passed") is True and type(report.get("probe_pid")) is int \
            and report["probe_pid"] == host["target_pid"] and report.get("public_ack") is False \
            and report.get("scene_state_durable") is False and report.get("formal_acceptance") is False \
            and cleanup_passed(report.get("cleanup"), report.get("native_pid")) \
            and cleanup_passed(raw_close, report.get("native_pid")) and raw_close == report["cleanup"] \
            and type(raw_exit.get("exit_code")) is int and type(raw_exit.get("pid")) is int \
            and raw_exit == raw_close["actual_process_exit"] \
            and cli_cleanup_passed(cli_exit) and cli_exit == report.get("client_cleanup") \
            and type(report.get("client_checks")) is int and report["client_checks"] == len(CLIENT_CHECKS) \
            and child == saved_child and child["pid"] == cli_exit["pid"] \
            and cli_exit["pid"] not in (report["probe_pid"], report["native_pid"]) \
            and not (output / "client-stderr.txt").read_bytes() \
            and len(markers) == 1 and type(markers[0].get("checks")) is int \
            and type(markers[0].get("client_checks")) is int \
            and markers == [{"passed": True, "checks": len(NATIVE_CHECKS), "client_checks": len(CLIENT_CHECKS)}]
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, AttributeError):
        return False


def unit_patterns(snapshot, suite):
    if suite == "all":
        return ["test_*.py"]
    patterns = ["test_writer_client_probe.py", "test_client_write_catalog.py", "test_client_writer_session.py",
                "test_client_writer_owner.py", "test_client_ledger.py", "test_client_transport.py"]
    if any(not (snapshot / "tests/blender" / name).is_file() for name in patterns):
        raise ValueError("required writer component test source missing")
    return patterns


def unit_program(patterns):
    return base_unit_program(patterns).replace(BASE_INVENTORY, UNIT_INVENTORY).replace(BASE_COMPLETE, UNIT_COMPLETE)


def unit_completion(stdout):
    return base_unit_completion(stdout.replace(UNIT_INVENTORY, BASE_INVENTORY).replace(UNIT_COMPLETE, BASE_COMPLETE))


def main(argv=None):
    arguments = parser()
    args = arguments.parse_args(argv)
    if args.client:
        return client()
    if args.output is None or args.run_id is None:
        arguments.error("--output and --run-id required")
    runner = load(STUDIO / "build/bootstrap/run_fixture.py")
    runner._reject_reparse_ancestors(args.output)
    output = args.output.resolve()
    if args.frozen:
        manifest = json.loads((output / "source-closure.json").read_bytes())
        if STUDIO != output / "source/studio" or sources(STUDIO) != manifest["files"] \
                or runner.source_closure_sha256(manifest["files"]) != manifest["source_closure_sha256"] \
                or manifest["run_id"] != args.run_id:
            raise ValueError("writer probe requires exact frozen source")
        return frozen(output, args.binary, args.run_id, manifest["source_closure_sha256"])
    output.mkdir(exist_ok=False)
    original = sources(STUDIO)
    snapshot = output / "source/studio"
    for name in original:
        target = snapshot / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(STUDIO / name, target)
    if sources(snapshot) != original:
        raise ValueError("writer source snapshot mismatch")
    closure = runner.source_closure_sha256(original)
    write_json(output, "source-closure.json", {"run_id": args.run_id, "recorded_at": utc_now(),
               "files": original, "source_closure_sha256": closure})
    patterns = unit_patterns(snapshot, args.unit_suite)
    unit = runner.run_process([sys.executable, "-B", "-c", unit_program(patterns)],
                             cwd=snapshot, output=output, timeout=120, label="unit")
    unit_ok, counts = unit_completion((output / "unit-stdout.txt").read_text(encoding="utf-8"))
    host = None
    if host_artifact_passed(output, unit) and unit_ok:
        binary = args.binary or STUDIO / ".local/tooling/blender-5.2.1-windows-x64/blender.exe"
        host = runner.run_process([
            sys.executable, "-B", str(snapshot / "tests/blender/run_writer_client_probe.py"),
            "--frozen", "--output", str(output), "--run-id", args.run_id, "--binary", str(binary.resolve()),
        ], cwd=snapshot, output=output, timeout=100, label="native")
    native_ok = native_completion(output, host)
    clean_logs = False
    if native_ok:
        report = json.loads((output / "writer-native.json").read_bytes())
        clean_logs = runner._streams_clean(output, [{"stdout": "native-stdout.txt", "stderr": "native-stderr.txt"},
                                                   {"stdout": "client-stdout.txt", "stderr": "client-stderr.txt"}])
        clean_logs = clean_logs and runner._streams_clean(output / report["gui_directory"], [
            {"stdout": "stdout.txt", "stderr": "stderr.txt"}])
    result = {"run_id": args.run_id, "source_closure_sha256": closure, "finished_at": utc_now(),
              "unit": unit, "unit_patterns": patterns, "unit_counts": counts, "unit_completion": unit_ok,
              "host": host, "native_completion": native_ok, "logs_clean": clean_logs,
              "source_unchanged": sources(STUDIO) == original, "snapshot_unchanged": sources(snapshot) == original,
              "public_ack": False, "scene_state_durable": False, "formal_acceptance": False}
    result["passed"] = host_artifact_passed(output, unit) and unit_ok and native_ok and clean_logs \
        and result["source_unchanged"] and result["snapshot_unchanged"]
    write_json(output, "capture.json", result)
    write_json(output, "evidence-inventory.json", evidence_inventory(output))
    print(json.dumps(result), flush=True)
    return int(not result["passed"])


if __name__ == "__main__":
    raise SystemExit(main())
