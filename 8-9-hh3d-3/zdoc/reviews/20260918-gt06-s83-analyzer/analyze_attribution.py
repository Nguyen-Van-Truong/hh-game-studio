"""Read-only S82 sparse attribution analysis; never launches/imports runtime code.

`baseline` reads named, published baseline artifacts only. `terminal` is permitted
only after an operator confirms all writers have stopped. JSON goes to stdout;
there is no file-writing code. Missing actual exits remain missing even when a
helper exited and a Job is empty. This is not an acceptance verifier.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import sys


SOURCE = "e010180a1bf85b7f565e9aa39734f8551caf170a85b36c50598be556b723ce7f"
PROFILE = "0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85"
RUN = "gt06-s82-attribution-01"
OUT = "project/benchmark/out/"
IN = "project/benchmark/input/"
COUNTERS = ("objects", "cached_resources", "tree_nodes", "orphan_nodes")


class Invalid(ValueError):
    pass


def require(value, message):
    if not value:
        raise Invalid(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def closure(files):
    return digest("".join(name + "\0" + files[name] + "\n" for name in sorted(files)).encode())


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key: " + key)
            result[key] = value
        return result

    def constant(value):
        raise Invalid("nonfinite JSON constant: " + value)

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def integer(value, name, minimum=0):
    require(type(value) in (int, float) and value == int(value) and value >= minimum,
            name + " must be an integer >= " + str(minimum))
    return int(value)


def instance_id(value):
    # GDScript exposes the uint64 ObjectID bit pattern through signed int64.
    # RefCounted identities in the actual S82 census include negative strings.
    return type(value) is str and re.fullmatch(r"-?[1-9][0-9]*", value) is not None \
        and -(2**63) <= int(value) <= 2**63 - 1


def ids(rows, label):
    require(type(rows) is list, label + " must be a list")
    result = {}
    for row in rows:
        require(type(row) is dict and instance_id(row.get("id"))
                and type(row.get("class")) is str, label + " row identity/class")
        require(row["id"] not in result, label + " duplicate id")
        result[row["id"]] = row
    return result


def counts(value, label):
    require(type(value) is dict, label + " must be a map")
    return {key: integer(number, label + ":" + key) for key, number in value.items()}


class Reader:
    def __init__(self, root):
        self.root = root.absolute()
        self.cache = {}

    def path(self, relative):
        p = PurePosixPath(relative)
        require(type(relative) is str and not p.is_absolute() and ".." not in p.parts
                and "\\" not in relative and ":" not in relative, "unsafe artifact path")
        target = self.root.joinpath(*p.parts)
        for component in (target, *target.parents):
            if component.exists():
                s = component.lstat()
                require(not stat.S_ISLNK(s.st_mode) and not getattr(s, "st_file_attributes", 0) & 0x400,
                        "linked/reparse artifact: " + str(component))
        return target

    def exists(self, relative):
        return self.path(relative).exists()

    def raw(self, relative):
        if relative not in self.cache:
            p = self.path(relative)
            a = p.stat()
            require(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and a.st_size <= 128 * 1024**2,
                    "artifact type/size/link count: " + relative)
            raw = p.read_bytes()
            b = p.stat()
            require((a.st_size, a.st_mtime_ns, a.st_ino) == (b.st_size, b.st_mtime_ns, b.st_ino)
                    and len(raw) == a.st_size, "artifact changed during read: " + relative)
            self.cache[relative] = raw
        return self.cache[relative]

    def json(self, relative):
        return decode(self.raw(relative))

    def optional(self, relative):
        return self.json(relative) if self.exists(relative) else None

    def ref(self, relative):
        raw = self.raw(relative)
        return {"file": relative, "sha256": digest(raw), "size_bytes": len(raw)}

    def check_ref(self, reference):
        require(type(reference) is dict and reference == self.ref(reference["file"]),
                "reference digest/size mismatch: " + str(reference))

    def names(self, directory, pattern):
        folder = self.path(directory)
        return sorted(p.relative_to(self.root).as_posix() for p in folder.glob(pattern))


def counter_check(point):
    before, after = point["counters_before"], point["counters_after"]
    for side in (before, after):
        for name in COUNTERS:
            integer(side[name], "counter " + name)
    require(before == after and point["counters_equal_across_collection"] is True,
            "snapshot counters changed across collection")
    return before


def point_check(point, run_id, pid, sequence):
    require(point["schema_id"] == "hh-studio.object-attribution-diagnostic"
            and point["schema_version"] == "1.0.0" and point["run_id"] == run_id
            and point["pid"] == pid and point["sequence"] == sequence,
            "snapshot schema/run/PID/sequence binding")
    require(point["formal_acceptance"] is False and point["full_benchmark"] is False
            and point["inventory_complete_objectdb"] is False
            and point["initial_inventory_ids_omitted"] is False,
            "snapshot diagnostic/partial-inventory scope")
    cs = counter_check(point)
    classes = counts(point["class_counts"], "class counts")
    owners = counts(point["owner_tree_item_counts"], "owner counts")
    n = integer(point["inventory_count"], "inventory count")
    require(n == sum(classes.values()) and point["unattributed_object_count"] == cs["objects"] - n
            and point["unattributed_object_count"] >= 0, "inventory/residual arithmetic")
    require(sum(owners.values()) == classes.get("TreeItem", 0), "per-owner TreeItem accounting")
    return cs, classes, owners


def binding(reader, point, baseline_count, full):
    batch = integer(point["batch"], "batch")
    name = OUT + f"attribution-{batch:02d}.json"
    receipt = reader.optional(name)
    result = {"snapshot": reader.ref(OUT + f"object-{point['sequence']:04d}.json"),
              "publication_receipt": reader.ref(name) if receipt is not None else None,
              "publication_stable": None, "joint_ack_verified": False,
              "snapshot_digest_embedded_in_receipt": False, "gaps": []}
    if receipt is None:
        result["gaps"].append("POST_PUBLICATION_RECEIPT_MISSING")
    else:
        require(receipt["run_id"] == point["run_id"] and receipt["batch"] == batch
                and receipt["baseline_objects"] == baseline_count
                and receipt["objects_before"] == point["counters_before"]["objects"]
                and receipt["formal_acceptance"] is False, "post-publication receipt binding")
        result["publication_stable"] = receipt["objects_after_publication"] == receipt["objects_before"]
        result["objects_after_publication"] = receipt["objects_after_publication"]
        if not result["publication_stable"]:
            result["gaps"].append("ATTRIBUTION_SELF_DRIFT_OBSERVED")
    if not full:
        return result
    joint_name = f"joint-{batch:02d}.json"
    joint = reader.optional(joint_name)
    if joint is None:
        result["gaps"].append("JOINT_ACK_MISSING_POSSIBLE_FAILURE_BEFORE_ACK")
        return result
    native_name, ack_name = OUT + f"batch-{batch:02d}.json", IN + f"ack-{batch:02d}.json"
    native, ack = reader.json(native_name), reader.json(ack_name)
    require(joint["run_id"] == native["run_id"] == ack["run_id"] == point["run_id"]
            and joint["index"] == native["index"] == ack["batch_index"] == batch
            and native["pid"] == point["pid"], "joint/native/ACK identity")
    require(joint["source_closure_sha256"] == ack["source_closure_sha256"] == SOURCE
            and joint["profile_sha256"] == ack["profile_sha256"] == PROFILE,
            "joint/ACK source and profile")
    require(joint["native_batch_sha256"] == ack["native_batch_sha256"]
            == digest(reader.raw(native_name)), "native batch digest")
    reader.check_ref(joint["ack_ref"])
    require(joint["ack_ref"]["file"] == ack_name, "joint ACK path")
    barrier = joint["barrier_receipt"]
    require(barrier["batch_index"] == batch and barrier["ack_sha256"] == digest(reader.raw(ack_name))
            and barrier["ack_size_bytes"] == len(reader.raw(ack_name))
            and barrier["native_batch_sha256"] == digest(reader.raw(native_name)), "barrier digest binding")
    require(joint["editor"]["native_observation"]["objects"] == barrier["objects"],
            "joint/barrier object count agreement")
    result["joint_ack_verified"] = True
    result["joint_ack_object_count"] = barrier["objects"]["value"]
    result["joint"] = reader.ref(joint_name)
    if receipt is not None and barrier["objects"]["value"] != receipt["objects_after_publication"]:
        result["gaps"].append("COUNTER_CHANGED_BETWEEN_PUBLICATION_AND_ACK")
    return result


def differences(before, after):
    return {key: after.get(key, 0) - before.get(key, 0)
            for key in sorted(before.keys() | after.keys()) if before.get(key, 0) != after.get(key, 0)}


def owner_rows(before, after, previous_descriptors, current_descriptors, added, removed, changed):
    adds = Counter(row.get("owner_tree_id") for row in added.values() if row["class"] == "TreeItem")
    rems = Counter(row.get("owner_tree_id") for row in removed.values() if row["class"] == "TreeItem")
    moves_in, moves_out, unknown = Counter(), Counter(), []
    for identity, row in changed.items():
        if row["class"] != "TreeItem":
            continue
        prior = previous_descriptors.get(identity)
        if prior is None:
            unknown.append(identity)
        elif prior.get("owner_tree_id") != row.get("owner_tree_id"):
            moves_out[prior.get("owner_tree_id")] += 1
            moves_in[row.get("owner_tree_id")] += 1
    rows = []
    owners = before.keys() | after.keys() | adds.keys() | rems.keys() | moves_in.keys() | moves_out.keys()
    for owner in sorted(owners, key=str):
        delta = after.get(owner, 0) - before.get(owner, 0)
        if not (delta or adds[owner] or rems[owner] or moves_in[owner] or moves_out[owner]):
            continue
        descriptor = current_descriptors.get(owner, previous_descriptors.get(owner, {}))
        explained = adds[owner] - rems[owner] + moves_in[owner] - moves_out[owner]
        rows.append({"owner_tree_id": owner, "path": descriptor.get("path"), "name": descriptor.get("name"),
                     "visible": descriptor.get("visible"), "before": before.get(owner, 0),
                     "after": after.get(owner, 0), "net": delta, "added": adds[owner], "removed": rems[owner],
                     "known_moves_in": moves_in[owner], "known_moves_out": moves_out[owner],
                     "residual_vs_known_rows": delta - explained})
    return {"rows": rows, "changed_treeitems_without_prior_descriptor": unknown,
            "note": "Count differences and reachable membership changes do not prove allocation ownership or a leak."}


def analyze_points(reader, full, run_id, pid):
    paths = reader.names(OUT, "object-*.json") if full else ([OUT + "object-0000.json"]
            if reader.exists(OUT + "object-0000.json") else [])
    if not paths:
        return {"baseline_available": False, "growth_observed": None, "points": []}
    membership, descriptors, previous, base, previous_owners = {}, {}, None, None, {}
    reports, integrity_gaps = [], []
    for sequence, path in enumerate(paths):
        require(path == OUT + f"object-{sequence:04d}.json", "missing/out-of-order snapshot sequence")
        point = reader.json(path)
        cs, class_counts, owners = point_check(point, run_id, pid, sequence)
        added, removed, changed = (ids(point[key], key) for key in ("added", "removed", "changed"))
        require(not (added.keys() & removed.keys() or added.keys() & changed.keys()
                     or removed.keys() & changed.keys()), "snapshot delta sets overlap")
        old_descriptors = dict(descriptors)
        if sequence == 0:
            require(point["label"] == "joint_baseline" and point["batch"] == 4
                    and not removed and not changed, "baseline position/deltas")
            membership = point["initial_id_classes"].copy()
            require(all(instance_id(k) and type(v) is str
                        for k, v in membership.items()), "baseline ID/class shape")
            require(all(membership.get(k) == row["class"] and row["class"] in ("Tree", "RichTextLabel")
                        for k, row in added.items()), "baseline selected descriptors")
            base = point
            descriptors.update(added)
            delta = None
        else:
            require(point["label"] == "joint_growth" and point["batch"] > previous["batch"]
                    and point["mono_us"] > previous["mono_us"] and not point["initial_id_classes"],
                    "growth snapshot order/baseline-map scope")
            require(cs["objects"] > base["counters_before"]["objects"], "growth label without positive ObjectDB delta")
            for identity, row in removed.items():
                require(membership.get(identity) == row["class"], "removed identity/class absent from prior census")
                prior = descriptors.get(identity)
                if prior is not None:
                    require({k: v for k, v in row.items() if k != "still_valid"} == prior,
                            "removed descriptor does not match prior known descriptor")
                membership.pop(identity)
                descriptors.pop(identity, None)
            for identity, row in added.items():
                require(identity not in membership, "added identity already in prior census")
                membership[identity] = row["class"]
                descriptors[identity] = row
            changes = []
            for identity, row in changed.items():
                require(membership.get(identity) == row["class"], "changed identity/class absent from prior census")
                prior = descriptors.get(identity)
                require(prior is None or prior != row, "unchanged known row listed as changed")
                changes.append({"id": identity, "class": row["class"], "before": prior, "after": row,
                    "changed_fields": sorted(k for k in (prior.keys() | row.keys()) if prior.get(k) != row.get(k))
                    if prior is not None else None, "prior_descriptor_available": prior is not None})
                descriptors[identity] = row
            inventory_delta = point["inventory_count"] - previous["inventory_count"]
            require(inventory_delta == len(added) - len(removed), "identity delta versus inventory delta")
            object_delta = cs["objects"] - previous["counters_before"]["objects"]
            delta = {"relative_to_previous_sequence": sequence - 1, "objectdb_net": object_delta,
                "reachable_inventory_net": inventory_delta, "unattributed_residual_net": object_delta - inventory_delta,
                "objectdb_since_baseline": cs["objects"] - base["counters_before"]["objects"],
                "reachable_since_baseline": point["inventory_count"] - base["inventory_count"],
                "unattributed_since_baseline": point["unattributed_object_count"] - base["unattributed_object_count"],
                "added_count": len(added), "removed_count": len(removed), "changed_count": len(changed),
                "added_classes": dict(Counter(r["class"] for r in added.values())),
                "removed_classes": dict(Counter(r["class"] for r in removed.values())),
                "changed_classes": dict(Counter(r["class"] for r in changed.values())),
                "class_net": differences(previous["class_counts"], class_counts),
                "removed_still_valid_count": sum(r.get("still_valid") is True for r in removed.values()),
                "added_rows": list(added.values()), "removed_rows": list(removed.values()), "changed_rows": changes,
                "owner_tree_diff": owner_rows(previous_owners, owners, old_descriptors, descriptors, added, removed, changed)}
        require(len(membership) == point["inventory_count"] and dict(Counter(membership.values())) == class_counts,
                "reconstructed ID/class census differs from published summary")
        require(all(owner in membership and membership[owner] != "TreeItem" for owner in owners),
                "TreeItem owner lacks a reachable non-TreeItem identity")
        bound = binding(reader, point, base["counters_before"]["objects"], full)
        integrity_gaps.extend({"sequence": sequence, "code": gap} for gap in bound["gaps"])
        reports.append({"sequence": sequence, "batch": point["batch"], "label": point["label"],
            "counters_before": cs, "counters_after": point["counters_after"],
            "inventory_count": point["inventory_count"], "unattributed_object_count": point["unattributed_object_count"],
            "inventory_duration_us": point["inventory_duration_us"], "class_counts": class_counts,
            "owner_tree_item_counts": owners, "binding": bound, "delta": delta})
        previous, previous_owners = point, owners
    return {"baseline_available": True, "initial_ids_are_not_growth": True,
            "baseline_id_count": base["inventory_count"], "baseline_selected_descriptor_count": len(base["added"]),
            "baseline_trees": [row for row in base["added"] if row["class"] == "Tree"],
            "growth_observed": len(reports) > 1, "points": reports, "integrity_gaps": integrity_gaps,
            "attribution_integrity_verified": not integrity_gaps}


def job_check(job):
    return type(job) is dict and all(job.get(k) is True for k in ("assigned", "closed", "zero_observed")) \
        and all(job.get(k) is False for k in ("tainted", "handle_retained", "create_uncertain", "close_uncertain")) \
        and job.get("active_count") == 0 and job.get("failed_operations") == [] and job.get("native_error") is None


def handle_check(handle):
    return type(handle) is dict and handle.get("closed") is True \
        and handle.get("handle_retained") is False and handle.get("close_uncertain") is False


def process_lane(reader, name):
    start, exited = (reader.optional(name + "/process-" + kind + ".json") for kind in ("start", "exit"))
    if start is not None:
        require(set(start) == {"pid"}, "process start shape")
        integer(start["pid"], "process PID", 1)
    if exited is not None:
        require(set(exited) == {"pid", "exit_code"} and type(exited["exit_code"]) is int
                and start is not None and exited["pid"] == start["pid"], "actual target exit identity/shape")
    capture = reader.optional(name + "/capture.json")
    cleanups = [reader.json(p) for p in reader.names(name, "cleanup-*.json")]
    if capture is not None:
        require(capture["actual_process_exit"] == exited, "capture target process receipt mismatch")
        if name != "import-host":
            require(capture["actual_process_start"] == start, "capture target start mismatch")
            require(capture["invocation_sha256"] == digest(reader.raw(name + "/invocation.json")),
                    "capture invocation digest")
        for artifact, expected in capture["artifacts"].items():
            require(digest(reader.raw(name + "/" + artifact)) == expected, "capture artifact digest")
    last = cleanups[-1] if cleanups else capture
    helper_exit = last.get("wrapper_exit_code") if last is not None else None
    require(helper_exit is None or type(helper_exit) is int, "helper exit is not an integer")
    if capture is not None and cleanups:
        require(capture["wrapper_exit_code"] == helper_exit, "helper exit receipts disagree")
    return {"actual_target_start": start, "actual_target_exit": exited, "actual_helper_exit_code": helper_exit,
            "target_exit_missing_reason": "TARGET_EXIT_NOT_RECORDED" if exited is None else None,
            "job_zero_closed": job_check(last.get("job")) if last else None,
            "wrapper_handle_released": handle_check(last.get("wrapper_process_handle")) if last else None,
            "job": last.get("job") if last else None,
            "cleanup_receipts": len(cleanups), "capture_present": capture is not None,
            "natural_exit_not_inferred": True}


def terminal_check(reader, context):
    terminal = reader.optional("child-terminal-cleanup.json")
    supervisor = reader.optional("supervisor-return.json")
    require(terminal is not None and supervisor is not None,
            "terminal analysis requires child-terminal-cleanup.json and supervisor-return.json")
    require(terminal["run_id"] == context["run_id"] and terminal["source_closure_sha256"] == SOURCE
            and terminal["profile_sha256"] == PROFILE and terminal["formal_acceptance"] is False,
            "terminal cleanup binding")
    reader.check_ref(terminal["context"])
    require(terminal["context"]["file"] == "context.json", "terminal context path")
    lanes = {role: process_lane(reader, role) for role in ("host-owner", "editor-host", "import-host")}
    obs = terminal["observations"]
    gaps = []
    for role in ("editor", "import"):
        claim = obs.get(role + "_target")
        actual = lanes[role + "-host"]["actual_target_exit"]
        require(claim is not None and claim["actual_target_exit"] == actual, "terminal target exit mismatch")
        for kind in ("start", "exit"):
            if claim.get(kind) is not None:
                reader.check_ref(claim[kind])
    for role, lane in lanes.items():
        if lane["actual_target_exit"] is None:
            gaps.append(role + ":ACTUAL_TARGET_EXIT_MISSING")
        if lane["actual_helper_exit_code"] is None:
            gaps.append(role + ":ACTUAL_HELPER_EXIT_MISSING")
        if lane["job_zero_closed"] is not True:
            gaps.append(role + ":JOB_ZERO_CLOSED_UNPROVEN")
        if role != "import-host" and lane["wrapper_handle_released"] is not True:
            gaps.append(role + ":WRAPPER_HANDLE_RELEASE_UNPROVEN")
    editor = obs.get("editor_owner", {})
    require(editor.get("helper_exit_code") == lanes["editor-host"]["actual_helper_exit_code"],
            "terminal editor helper exit mismatch")
    require(editor.get("job") == lanes["editor-host"]["job"], "terminal editor Job mismatch")
    if not (editor.get("present") is True and editor.get("closed") is True
            and not any(editor.get("drain_threads_alive", [True]))
            and handle_check(editor.get("wrapper_process_handle"))):
        gaps.append("EDITOR_OWNER_RELEASE_UNPROVEN")
    producer = obs.get("producer") or {}
    host, journal = producer.get("host") or {}, producer.get("journal") or {}
    if not (producer.get("closed") is True and host.get("stopped") is True and host.get("closing") is True
            and not any(host.get("threads_alive", [True])) and host.get("main_socket_closed") is True
            and host.get("control_socket_closed") is True and journal.get("cache_closed") is True
            and all(journal.get(k) is False for k in ("index_retained", "database_retained", "directory_retained"))):
        gaps.append("PRODUCER_THREADS_SOCKETS_JOURNAL_RELEASE_UNPROVEN")
    for name, probe in (("editor", obs.get("editor_probe")), ("producer", producer.get("observer_probe"))):
        if not (type(probe) is dict and probe.get("present") is True
                and probe.get("handle_retained") is False and probe.get("close_uncertain") is False):
            gaps.append(name + ":PROBE_RELEASE_UNPROVEN")
    if obs.get("heartbeat_alive") is not False or terminal.get("errors") != []:
        gaps.append("TERMINAL_HEARTBEAT_OR_CLEANUP_ERRORS")
    if "constructor_owner" in obs:
        gaps.append("EXCEPTION_CONSTRUCTOR_OWNER_REQUIRES_REVIEW")
    if supervisor.get("owner_closed") is not True or supervisor.get("owned_tree_zero") is not True:
        gaps.append("SUPERVISOR_CHILD_JOB_RELEASE_UNPROVEN")
    # The launched pythonw supervisor is not itself enclosed by these owner receipts.
    gaps.append("SUPERVISOR_ACTUAL_EXIT_NOT_CAPTURED_BY_THIS_RUNNER")
    return {"lanes": lanes, "cleanup_observations": obs, "cleanup_gaps": gaps,
            "child_completed_batches": terminal["completed_batches"], "child_primary_error": terminal["primary_error"],
            "supervisor_return": supervisor, "supervisor_actual_exit": None,
            "expected_failure_nonzero_exits_are_not_integrity_errors": True}


def provenance(reader, diagnostic, context):
    files = diagnostic["base_source_files"]
    require(len(files) == 51 and closure(files) == SOURCE and context["source_files"] == files
            and reader.json("source-files.json") == files, "51-file source closure")
    require(context["campaign_sha256"] == digest(reader.raw("diagnostic.json")), "context diagnostic digest")
    require(digest(reader.raw("benchmark-profile.json")) == PROFILE, "frozen profile exact digest")
    for name, expected in diagnostic["helper_files"].items():
        require(digest(reader.raw("source/" + name)) == expected, "frozen helper digest: " + name)
    overlay = reader.json("native-overlay.json")
    require(overlay["formal_acceptance"] is False and overlay["eligible_for_dataset"] is False
            and overlay["runtime_source_modified"] is False and overlay["thresholds_modified"] is False,
            "overlay scope")
    native = "project/addons/hh_benchmark/benchmark_native.gd"
    require(digest(reader.raw(native)) == overlay["effective_sha256"], "effective native overlay digest")
    require(overlay["base_sha256"] == files["tests/replay/benchmark_native.gd"], "overlay base digest")
    probe = next((v for k, v in diagnostic["helper_files"].items() if k.endswith("/object_probe.gd")), None)
    require(overlay["probe_sha256"] == probe, "overlay probe digest")
    host_invocation = reader.json("host-owner/invocation.json")
    expected_host = {**{"studio/" + k: v for k, v in files.items()}, **diagnostic["helper_files"]}
    require(host_invocation["source_files"] == expected_host, "host executed source/helper binding")
    editor_invocation = reader.json("editor-host/invocation.json")
    effective_sources = editor_invocation["source_files"]
    require(all(effective_sources.get(k) == v for k, v in files.items()), "editor base source binding")
    copied_native_key = ".local/reviews/" + context["run_id"] + "/" + native
    require(effective_sources.get(copied_native_key) == overlay["effective_sha256"],
            "editor invocation effective overlay binding")
    return {"runtime_manifest_entries_verified": 51, "runtime_source_bytes_reread": False,
            "frozen_helper_files_verified": len(diagnostic["helper_files"]),
            "source_closure": SOURCE, "profile_sha256": PROFILE, "overlay": overlay,
            "scope": "Runtime map closure and named helper/overlay bytes only; no runtime-source-byte reread, live-source claim, or recursive raw-tree hash."}


def full_completion(reader, context, process):
    result = reader.optional("child-result.json")
    if result is None:
        return {"verified": False, "joint_object_counts": []}
    require(result["run_id"] == context["run_id"] and result["source_closure_sha256"] == SOURCE
            and result["profile_sha256"] == PROFILE, "child-result binding")
    if result.get("completed") is not True or len(result.get("batches", [])) != 35:
        return {"verified": False, "joint_object_counts": []}
    object_counts = []
    for number, batch in enumerate(result["batches"]):
        require(batch["index"] == number, "completed batch index")
        # Only small joint counter receipts are needed for nonreproduction.
        # Do not rebuild campaign validation or reread all command/cycle files.
        reader.check_ref(batch["joint"])
        joint = reader.json(batch["joint"]["file"])
        require(joint["run_id"] == context["run_id"] and joint["index"] == number
                and joint["source_closure_sha256"] == SOURCE and joint["profile_sha256"] == PROFILE,
                "completed joint binding")
        object_counts.append(integer(joint["barrier_receipt"]["objects"]["value"], "joint objects", 1))
    reader.check_ref(result["native_index"])
    index = reader.json(result["native_index"]["file"])
    require(index["input"]["run_id"] == context["run_id"] and index["completed"] is True
            and index["benchmark_complete"] is True and len(index["batches"]) == 35
            and len(index["host_barriers"]) == 35, "native full diagnostic completion")
    exits_ok = all(lane["actual_target_exit"] is not None and lane["actual_target_exit"]["exit_code"] == 0
               and lane["actual_helper_exit_code"] == 0 and lane["job_zero_closed"] is True
               for lane in process["lanes"].values())
    return {"verified": exits_ok, "joint_object_counts": object_counts}


def analyze(root, mode, terminal_confirmed=False):
    require(mode != "terminal" or terminal_confirmed, "--terminal-confirmed is required; do not analyze a changing raw tree")
    reader = Reader(root)
    diagnostic, context = reader.json("diagnostic.json"), reader.json("context.json")
    run_id = diagnostic["run_id"]
    require(run_id == RUN == context["run_id"] and diagnostic["base_source_closure_sha256"] == SOURCE
            and context["source_closure_sha256"] == SOURCE and diagnostic["profile_sha256"] == PROFILE
            and context["profile_sha256"] == PROFILE and diagnostic["formal_acceptance"] is False
            and diagnostic["eligible_for_dataset"] is False, "diagnostic/context scope and fixed S82 binding")
    editor_start = reader.optional("editor-host/process-start.json")
    pid = editor_start["pid"] if editor_start is not None else None
    report = {"schema": "HH-GT06-S83-SPARSE-ATTRIBUTION-ANALYSIS-1", "authority": 0,
              "formal_acceptance": False, "eligible_for_dataset": False, "run_id": run_id, "mode": mode,
              "status": "observation_only" if mode == "baseline" else "terminal", "run_outcome": "not_evaluated",
              "liveness": "not_checked",
              "status_basis": "Caller selected baseline mode; live PID status is not probed or inferred."
              if mode == "baseline" else "Caller confirmed writers stopped; terminal receipts checked.",
              "limitations": ["Partial reachable census, not all ObjectDB allocations.",
                  "No-growth/nonreproduction does not prove no leak or a repair.",
                  "Instrumented run timing/RSS differ; never eligible for the campaign dataset.",
                  "Initial identity/class entries and selected descriptors are baseline, never growth.",
                  "A removed reachable ID can still be alive; unchanged count can hide identity churn.",
                  "Snapshot and publication receipt are exact-byte hashed by this analyzer; the producer receipt does not embed the snapshot digest or PID.",
                  "Supervisor return and helper exit are not substituted for missing actual target exits.",
                  "This tool does not probe current processes, verify every runtime postcondition, or confer GT-06 acceptance."]}
    if mode == "terminal":
        report["terminal"] = terminal_check(reader, context)
        report["provenance"] = provenance(reader, diagnostic, context)
    report["attribution"] = analyze_points(reader, mode == "terminal", run_id, pid)
    if mode == "terminal":
        failure = reader.optional("child-failure.json")
        native_failure = reader.optional(OUT + "failure.json")
        if failure is not None:
            require(failure["run_id"] == run_id, "child-failure run identity")
        if native_failure is not None:
            require(native_failure["input"]["run_id"] == run_id and native_failure["pid"] == pid,
                    "native-failure run identity")
        report["failure"] = {"child": failure, "native": native_failure}
        completion = full_completion(reader, context, report["terminal"])
        completed = completion["verified"]
        report["complete_35_batch_diagnostic"] = completion
        growth = report["attribution"]["growth_observed"]
        if completed:
            require(report["attribution"]["baseline_available"], "completed diagnostic missing attribution baseline")
            values = completion["joint_object_counts"]
            require(values[4] == report["attribution"]["points"][0]["counters_before"]["objects"],
                    "completion baseline counter mismatch")
            if any(value > values[4] for value in values[5:]):
                require(growth, "joint growth exists without sparse attribution growth snapshot")
        if growth:
            report["run_outcome"] = "positive_objectdb_growth_observed"
        elif completed and failure is None and native_failure is None:
            report["status"], report["run_outcome"] = "no_reproduction", "no_sampled_objectdb_growth_in_completed_diagnostic"
        elif failure is not None or native_failure is not None or report["terminal"]["child_primary_error"] is not None:
            report["status"], report["run_outcome"] = "error", "diagnostic_failed_without_attributed_growth"
        else:
            report["run_outcome"] = "terminal_incomplete_or_unproven"
        if report["attribution"].get("integrity_gaps"):
            report["status"] = "error"
    report["consumed_artifacts"] = [reader.ref(name) for name in sorted(reader.cache)]
    report["consumed_artifacts_closure_sha256"] = closure({r["file"]: r["sha256"] for r in report["consumed_artifacts"]})
    report["input_scope"] = "Exact bytes consumed once; no complete raw-tree inventory or changing log hash in baseline mode."
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--mode", choices=("baseline", "terminal"), default="baseline")
    parser.add_argument("--terminal-confirmed", action="store_true",
                        help="Operator verified writers stopped; never use while the diagnostic is active.")
    args = parser.parse_args()
    try:
        report = analyze(args.raw_root, args.mode, args.terminal_confirmed)
    except (Invalid, OSError, KeyError, TypeError, ValueError, StopIteration) as error:
        report = {"schema": "HH-GT06-S83-SPARSE-ATTRIBUTION-ANALYSIS-1", "authority": 0,
                  "formal_acceptance": False, "status": "error", "run_outcome": "not_concluded",
                  "error_type": type(error).__name__, "error": str(error)}
        code = 2
    else:
        # A recorded diagnostic failure can be successfully analyzed; exit0 is
        # analyzer success only, never an assertion that the run itself passed.
        code = 0
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
