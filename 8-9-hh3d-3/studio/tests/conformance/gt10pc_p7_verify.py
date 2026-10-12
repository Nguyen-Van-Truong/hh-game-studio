"""Read-only P7 recovery proof; labels and equal empty ledgers are not proof."""
from pathlib import Path

from studio.package.release_contract import (
    digest_file, digest_bytes, need, strict_json, verify_package, _safe_member,
)
from studio.package.trust import load_trust


def _without_godot(ledger: dict) -> dict:
    need(isinstance(ledger, dict) and ledger, "P7_VERIFY_PROJECT_LEDGER")
    return {key: value for key, value in ledger.items() if ".godot" not in Path(key).parts}


def _addon_on_disk(case: Path) -> dict:
    root = case / "project" / "addons" / "hh_studio"
    need(root.is_dir(), "P7_VERIFY_ADDON_DIR")
    found = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        need(".godot" not in Path(relative).parts, "P7_VERIFY_ADDON_PATH")
        found[relative] = {"sha256": digest_file(path), "size": path.stat().st_size}
    return found


def _release_intact(root: Path, identity: str, package: dict) -> None:
    """A last-good release tree must still equal its signed manifest, byte for byte."""
    need((root / "manifest.json").is_file() and digest_file(root / "manifest.json") == identity,
         "P7_VERIFY_LAST_GOOD_MANIFEST")
    files = package["manifest"]["files"]
    found = sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file())
    need(found == sorted([*files, "manifest.json"]), "P7_VERIFY_LAST_GOOD_TREE")
    for name, entry in files.items():
        need(digest_file(root / name) == entry["sha256"], "P7_VERIFY_LAST_GOOD_FILE")


def verify_p7(root: Path, *, trust: Path, trust_sha256: str, group: str,
              release: dict, group_host: dict | None = None) -> dict:
    from studio.tests.conformance.run_gt10pc_matrix import _read, _process, _lifecycle, verify_profile
    from studio.tests.conformance.run_gt10pc_p7 import CASES, state_digest
    doc = _read(root / "p7.json")
    need(doc.get("schema") == "hh-gt10pc-p7-native-recovery-2"
         and doc.get("authority") == 0 and doc.get("acceptance") is False
         and doc.get("native_required") is True and doc.get("case_group") == group,
         "P7_VERIFY_SCHEMA")
    keys = load_trust(trust, expected_sha256=trust_sha256)
    packages = {}
    for tag, version in (("old", "0.1.0"), ("new", "0.1.1")):
        package = verify_package(root / "artifacts" / (tag + ".hhpkg"), trusted_keys=keys,
                                 target="Windows", expected_version=version)
        need(doc.get(tag + "_artifact_sha256") == package["archive_sha256"]
             and doc.get(tag + "_manifest_sha256") == package["manifest_sha256"], "P7_VERIFY_PACKAGE")
        # Only the explicit crash-fixture marker and its two execution pins may
        # differ from the selected matrix release. Never accept arbitrary code.
        source = release["members"]
        variant = package["members"]
        prefix = "payload/studio/"
        changed = {prefix + name for name in ("godot-addon/addons/hh_studio/plugin.gd",
                   "host/replay/execution-source.json", "host/replay/execution-current.json")}
        need({k: v for k, v in variant.items() if k.startswith(prefix) and k not in changed}
             == {k: v for k, v in source.items() if k.startswith(prefix) and k not in changed},
             "P7_VERIFY_RELEASE_SOURCE")
        plugin = prefix + "godot-addon/addons/hh_studio/plugin.gd"
        need(variant[plugin] == source[plugin] + ("\n# GT10PC_P7_VARIANT=" + tag + "\n").encode(),
             "P7_VERIFY_VARIANT")
        packages[package["manifest_sha256"]] = package
    expected = {"first": CASES[:3], "second": CASES[3:6], "third": CASES[6:]}[group]
    cases = doc.get("cases")
    need(isinstance(cases, list) and [r.get("name") for r in cases] == [r[0] for r in expected],
         "P7_VERIFY_CASES")
    evidence = doc.get("evidence")
    need(isinstance(evidence, dict) and evidence, "P7_VERIFY_EVIDENCE")
    for name, digest in evidence.items():
        _safe_member(name)
        need(digest_file(root / name) == digest, "P7_VERIFY_EVIDENCE_HASH:" + name)
    for row, (name, action, phase, disposition) in zip(cases, expected):
        case = root / "cases" / name
        required = {"request.json", "cut.json", "worker-host.json", "worker-stdout.txt",
                    "worker-stderr.txt", "retry-proof.json", "project-before.json", "project-final.json",
                    "install-before-reopen.json", "applicability.json",
                    "native/receipt.json", "native-driver/driver-host.json"}
        for label in ("parse", "godot"):
            required.update("native/" + label + suffix for suffix in ("-host.json", "-stdout.txt", "-stderr.txt"))
        required.update("native-driver/driver" + suffix for suffix in ("-stdout.txt", "-stderr.txt"))
        missing = sorted("cases/" + name + "/" + rel for rel in required if "cases/" + name + "/" + rel not in evidence)
        need(not missing, "P7_VERIFY_EVIDENCE_SET:" + ",".join(missing))
        need((row.get("action"), row.get("phase"), row.get("disposition")) == (action, phase, disposition),
             "P7_VERIFY_CASE_BINDING")
        worker, cut = _read(case / "worker-host.json"), _read(case / "cut.json")
        victim = worker.get("victim_pid")
        exit_code = worker.get("exit_code")
        process_tree = worker.get("process_tree")
        killer = worker.get("killer_pid")
        epoch_name = "kill_epoch" if disposition == "kill" else "stop_epoch"
        other_epoch = "stop_epoch" if disposition == "kill" else "kill_epoch"
        need(worker.get("schema") == "hh-gt10pc-p7-worker-host-2"
             and worker.get("disposition") == disposition
             and type(victim) is int and victim > 0 and victim == cut.get("pid")
             and type(exit_code) is int and ((exit_code != 0) == (disposition == "kill"))
             and isinstance(process_tree, list) and victim in process_tree
             and all(type(pid) is int and pid > 0 for pid in process_tree)
             and type(killer) is int and killer > 0
             and type(worker.get(epoch_name)) in (int, float) and worker.get(other_epoch) is None
             and digest_file(case / "worker-host.json") == row["worker"].get("host_sha256")
             and cut == row["worker"].get("cut") and cut.get("phase") == phase,
             "P7_VERIFY_WORKER")
        if group_host is not None:
            need(isinstance(group_host, dict) and type(group_host.get("target_pid")) is int
                 and killer == group_host["target_pid"], "P7_VERIFY_KILLER_HOST")
        applicability = _read(case / "applicability.json")
        for key in ("network_loss", "token_rotation"):
            item = applicability.get(key) if isinstance(applicability, dict) else None
            need(isinstance(item, dict) and item.get("status") == "NOT_APPLICABLE"
                 and isinstance(item.get("reason"), str) and item["reason"].strip(),
                 "P7_VERIFY_NOT_APPLICABLE:" + key)
        reopen_sha = digest_file(case / "install-before-reopen.json")
        need(isinstance(row.get("install_before_reopen_sha256"), str)
             and reopen_sha == row["install_before_reopen_sha256"], "P7_VERIFY_BEFORE_REOPEN")
        # The selector on disk right after the cut is the last-good; recovery must keep it
        # and its release trees must still match their signed manifests.
        snapshot = strict_json((case / "install-before-reopen.json").read_bytes())
        recovered = row["after_recovery"]
        need(isinstance(snapshot, dict) and snapshot.get("schema") == "hh-studio-install-4"
             and snapshot.get("target") == "Windows"
             and (snapshot.get("active"), snapshot.get("previous"))
             == (recovered.get("active"), recovered.get("previous")), "P7_VERIFY_LAST_GOOD_SELECTOR")
        for identity in (snapshot.get("active"), snapshot.get("previous")):
            if identity is not None:
                need(identity in packages, "P7_VERIFY_LAST_GOOD_RELEASE")
                _release_intact(case / "install" / "releases" / identity, identity, packages[identity])
        for stream in ("stdout", "stderr"):
            need(digest_file(case / ("worker-" + stream + ".txt")) == worker.get(stream + "_sha256"),
                 "P7_VERIFY_WORKER_LOG")
        need(not (case / "worker-stderr.txt").read_bytes(), "P7_VERIFY_WORKER_STDERR")
        proof = _read(case / "retry-proof.json")
        project_view = _without_godot(proof.get("project_after"))
        need(proof.get("first") == proof.get("second") == row.get("lookup") == row.get("retry")
             and isinstance(proof.get("first"), dict)
             and proof.get("state") == proof.get("state_after_second_retry")
             and proof.get("install_before") == proof.get("install_after")
             and _without_godot(proof.get("project_before")) == project_view
             and bool(proof.get("install_before")), "P7_VERIFY_DEDUP")
        early = disposition == "kill" and phase in {"staged", "before-selector", "release-renamed"}
        need((proof.get("lookup_before_retry") is None) == early
             and proof["state"]["revision"] == row["after_recovery"]["revision"] + int(early),
             "P7_VERIFY_REVISION")
        for state in (row["before"], row["after_recovery"], proof["state"], row["final"]):
            need(state_digest(state) == state.get("state_sha256"), "P7_VERIFY_STATE_HASH")
        disk_state = digest_file(case / "install" / ".install.json")
        need(disk_state == row["final"].get("state_sha256")
             == proof["state_after_second_retry"].get("state_sha256"), "P7_VERIFY_FINAL_DISK")
        install_doc = strict_json((case / "install" / ".install.json").read_bytes())
        commands = install_doc.get("commands") if isinstance(install_doc, dict) else None
        command_id = "p7." + name
        matched = []
        if isinstance(commands, dict):
            for key, item in commands.items():
                receipt = item.get("receipt") if isinstance(item, dict) else None
                if key == command_id or (isinstance(receipt, dict) and receipt.get("command_id") == command_id):
                    matched.append(key)
        need(matched == [command_id], "P7_VERIFY_COMMAND_ROW")
        selected = packages.get(row["final"].get("active"))
        need(selected is not None, "P7_VERIFY_ACTIVE")
        baseline, final = _read(case / "project-before.json"), _read(case / "project-final.json")
        fixture = "payload/studio/fixtures/gt09-arena/"
        core = {k[len(fixture):]: v for k, v in release["manifest"]["files"].items() if k.startswith(fixture)}
        core["owner-save.dat"] = {"sha256": digest_bytes(b"p7-owner-save\n"), "size": 14}
        need({k: v for k, v in baseline.items()
              if not k.startswith("addons/hh_studio/") and ".godot" not in Path(k).parts} == core,
             "P7_VERIFY_BASELINE")
        addon_prefix = "payload/studio/godot-addon/addons/hh_studio/"
        addon = {"addons/hh_studio/" + k[len(addon_prefix):]: v for k, v in selected["manifest"]["files"].items()
                 if k.startswith(addon_prefix)}
        protocol = selected["manifest"]["files"]["payload/studio/protocol/jcs_godot.gd"]
        addon["addons/hh_studio/jcs_godot.gd"] = protocol
        manual = b"p7 manual survives\n"
        addon["addons/hh_studio/owner-manual-note.txt"] = {"sha256": digest_bytes(manual), "size": len(manual)}
        need(final == {**core, **addon} == project_view, "P7_VERIFY_ADDON_BYTES")
        on_disk = _addon_on_disk(case)
        disk_manual = on_disk.pop("owner-manual-note.txt", None)
        expected_disk = {key.removeprefix("addons/hh_studio/"): value for key, value in addon.items()
                         if key != "addons/hh_studio/owner-manual-note.txt"}
        need(disk_manual == addon["addons/hh_studio/owner-manual-note.txt"]
             and on_disk == expected_disk
             and on_disk.get("jcs_godot.gd") == protocol, "P7_VERIFY_ADDON_DISK")
        native = _read(case / "native/receipt.json")
        need(native == row["native"].get("receipt")
             and native.get("active_release") == selected["manifest_sha256"]
             and native.get("version") == selected["manifest"]["version"]
             and native.get("probe_sha256") == selected["manifest"]["files"]["payload/studio/package/installed_probe.py"]["sha256"],
             "P7_VERIFY_NATIVE_BINDING")
        verify_profile(native, selected["manifest"], "gt09-arena", selected["members"])
        _process(case / "native-driver", "driver", row["native"]["driver"])
        _process(case / "native", "parse", native.get("parse"))
        _lifecycle(_process(case / "native", "godot", native.get("process")))
    return {"cases": len(cases), "status": "P7_RAW_VERIFIED", "authority": 0}
