"""Read-only Linux raw verifier; summaries never substitute for process evidence."""
from pathlib import Path, PurePosixPath

from studio.package.release_contract import (
    HEX, _safe_member, canonical, digest_bytes, digest_file, need, strict_json, verify_package,
)
from studio.package.trust import load_trust
from studio.tests.conformance.run_gt10pc_matrix import (
    FIXTURES, _lifecycle, _process, _read, verify_profile,
)


def _ledger(root, ledger, required):
    need(isinstance(ledger, dict) and set(required) <= set(ledger), "GT10PC_LINUX_EVIDENCE_MISSING")
    for name, expected in ledger.items():
        _safe_member(name)
        need(isinstance(expected, str) and HEX.fullmatch(expected)
             and digest_file(root / name) == expected, "GT10PC_LINUX_EVIDENCE_CHANGED:" + name)


def verify_linux(root: Path, *, artifact: Path, upgrade_artifact: Path,
                 trust: Path, trust_sha256: str) -> dict:
    keys = load_trust(trust, expected_sha256=trust_sha256)
    package = verify_package(artifact, trusted_keys=keys, target="Linux-headless", expected_version="0.1.0")
    upgrade = verify_package(upgrade_artifact, trusted_keys=keys, target="Linux-headless", expected_version="0.1.1")
    manifest = package["manifest"]
    need(upgrade["manifest"]["source_closure_sha256"] == manifest["source_closure_sha256"],
         "GT10PC_LINUX_UPGRADE_CLOSURE")
    doc = _read(root / "producer.json")
    need(doc.get("schema") == "hh-gt10pc-linux-producer-1" and doc.get("authority") == 0
         and doc.get("acceptance") is False and doc.get("mode") == "DIAGNOSTIC"
         and doc.get("target") == "Linux-headless" and doc.get("status") == "DIAGNOSTIC_PASS"
         and doc.get("error") is None, "GT10PC_LINUX_PRODUCER")
    for key, expected in {
        "artifact_sha256": package["archive_sha256"], "manifest_sha256": package["manifest_sha256"],
        "upgrade_artifact_sha256": upgrade["archive_sha256"], "upgrade_manifest_sha256": upgrade["manifest_sha256"],
        "source_closure_sha256": manifest["source_closure_sha256"], "trust_sha256": trust_sha256,
    }.items():
        need(doc.get(key) == expected, "GT10PC_LINUX_ARTIFACT_BINDING:" + key)
    labels = ("image", "create", "inspect-created", "run", "inspect-exited", "inspect-closeout", "remove", "leftover")
    required = {"native/linux.json", "input/request.json", "input/bootstrap.py", "input/wheels/wheel-lock.json"}
    required.update("host/" + label + suffix for label in labels
                    for suffix in ("-receipt.json", "-host.json", "-stdout.txt", "-stderr.txt"))
    _ledger(root, doc.get("evidence"), required)
    host = root / "host"
    stdout = {}
    need(set(doc.get("processes", {})) == set(labels), "GT10PC_LINUX_PROCESS_SET")
    for label in labels:
        process = _read(host / (label + "-receipt.json"))
        need(process == doc["processes"][label], "GT10PC_LINUX_PROCESS_RECEIPT")
        stdout[label] = _process(host, label, process)
    lock = strict_json(package["members"]["payload/studio/godot-addon/validator-toolchain.lock.json"])
    image = strict_json(stdout["image"].encode())
    need(len(image) == 1 and image[0].get("Id") == lock["image_id"]
         and image[0].get("Os") == "linux" and image[0].get("Architecture") == "amd64",
         "GT10PC_LINUX_IMAGE")
    identity = stdout["create"].strip()
    need(HEX.fullmatch(identity) and identity == doc.get("container_id")
         and doc.get("image_id") == lock["image_id"] and doc.get("context") == lock["docker_context"],
         "GT10PC_LINUX_CONTAINER_BINDING")
    for label in ("inspect-created", "inspect-exited", "inspect-closeout"):
        inspected = strict_json(stdout[label].encode())
        need(len(inspected) == 1, "GT10PC_LINUX_INSPECTION")
        observed = inspected[0]
        need(observed == doc.get("inspections", {}).get(label)
             and observed.get("Id") == identity and observed.get("Image") == lock["image_id"]
             and observed.get("Name") == "/" + doc["run_id"]
             and observed.get("Config", {}).get("Labels", {}).get("hh.gt10pc.owner") == doc["run_id"],
             "GT10PC_LINUX_INSPECTION_BINDING")
        config = observed["HostConfig"]
        need(config.get("NetworkMode") == "none" and config.get("ReadonlyRootfs") is True
             and config.get("Privileged") is False and config.get("CapDrop") == ["ALL"]
             and config.get("NanoCpus") == 12000000000 and config.get("PidsLimit") == 64
             and config.get("Memory") == config.get("MemorySwap") == 1073741824
             and set(config.get("SecurityOpt", [])) == {"no-new-privileges=true", "seccomp=builtin"}
             and observed["Config"].get("User") == "65532:65532"
             and observed["Config"].get("Entrypoint") == ["/usr/local/bin/python3"]
             and observed["Config"].get("Cmd") == ["-B", "/input/bootstrap.py"],
             "GT10PC_LINUX_CONFINEMENT")
        mounts = observed.get("Mounts", [])
        need(len(mounts) == 2 and {m.get("Destination"): m.get("RW") for m in mounts}
             == {"/input": False, "/evidence": True}
             and set(config.get("Tmpfs", {})) == {"/tmp", "/output"}, "GT10PC_LINUX_MOUNTS")
        state = observed["State"]
        if label != "inspect-created":
            need(state.get("ExitCode") == 0 and state.get("Running") is False
                 and state.get("Pid") == 0 and state.get("OOMKilled") is False
                 and state.get("Status") == "exited" and not state.get("Error"), "GT10PC_LINUX_EXIT")
    need(stdout["remove"].strip() == identity and not stdout["leftover"].strip()
         and doc.get("owned_removed") is True, "GT10PC_LINUX_LEFTOVER")
    request = _read(root / "input/request.json")
    for field in ("artifact_sha256", "manifest_sha256", "upgrade_artifact_sha256", "upgrade_manifest_sha256",
                  "trust_sha256", "source_closure_sha256", "wheel_lock_sha256"):
        need(request.get(field) == doc.get(field), "GT10PC_LINUX_REQUEST_BINDING")
    need(request.get("binary_name") == lock["binary_name"] and request.get("binary_sha256") == lock["binary_sha256"]
         and request.get("worker_sha256") == manifest["files"]["payload/studio/tests/conformance/gt10pc_linux_worker.py"]["sha256"]
         and request["wheel_lock_sha256"] == digest_file(root / "input/wheels/wheel-lock.json"),
         "GT10PC_LINUX_BOOTSTRAP_BINDING")
    native_root = root / "native"
    native = _read(native_root / "linux.json")
    need(native.get("schema") == "hh-gt10pc-linux-native-2" and native.get("system") == "Linux"
         and native.get("target") == "Linux-headless" and native.get("authority") == 0
         and native.get("acceptance") is False and native.get("python", "").startswith("3.12."),
         "GT10PC_LINUX_NATIVE_SCHEMA")
    for field in ("artifact_sha256", "manifest_sha256", "upgrade_artifact_sha256", "upgrade_manifest_sha256", "source_closure_sha256"):
        need(native.get(field) == doc[field], "GT10PC_LINUX_NATIVE_ARTIFACT")
    records = native.get("records")
    need(isinstance(records, list) and [r.get("fixture") for r in records] == list(FIXTURES), "GT10PC_LINUX_FIXTURES")
    phases = ("install", "upgrade", "rollback", "reinstall")
    ledgers = ("project-before.json", "project-before-play.json", "project-after-play.json",
               "project-after-uninstall.json", "project-after-reinstall.json")
    required_native = set()
    for fixture in FIXTURES:
        prefix = "consumer/" + fixture + "/"
        required_native.update(prefix + n for n in (*ledgers, "native-phases.json", "install-state.json"))
        for phase in phases:
            for domain, labels in (("drivers", ("driver",)), ("native", ("parse", "godot"))):
                phase_path = prefix + domain + "/" + phase + "/"
                required_native.add(phase_path + "receipt.json")
                required_native.update(phase_path + label + suffix for label in labels
                                       for suffix in ("-host.json", "-stdout.txt", "-stderr.txt"))
    _ledger(native_root, native.get("evidence"), required_native)
    need({"native/" + n for n in required_native} <= set(doc["evidence"]), "GT10PC_LINUX_OUTER_EVIDENCE")
    addon_prefix = "payload/studio/godot-addon/addons/hh_studio/"
    addon = {"addons/hh_studio/" + k[len(addon_prefix):]: v for k, v in manifest["files"].items() if k.startswith(addon_prefix)}
    addon["addons/hh_studio/jcs_godot.gd"] = manifest["files"]["payload/studio/protocol/jcs_godot.gd"]
    checked = []
    for record in records:
        fixture = record["fixture"]
        base = native_root / "consumer" / fixture
        prefix = "payload/studio/fixtures/" + fixture + "/"
        baseline = {k[len(prefix):]: v for k, v in manifest["files"].items() if k.startswith(prefix)}
        save, manual = b"consumer-save-before-install\n", b"owner edit must survive uninstall\n"
        baseline["owner-save.dat"] = {"sha256": digest_bytes(save), "size": len(save)}
        retained = {**baseline, "addons/hh_studio/owner-manual-note.txt": {"sha256": digest_bytes(manual), "size": len(manual)}}
        ready = {**retained, **addon}
        for name in ledgers:
            expected = baseline if name == ledgers[0] else retained if name == "project-after-uninstall.json" else ready
            need(_read(base / name) == expected, "GT10PC_LINUX_LEDGER:" + name)
        recorded_phases = _read(base / "native-phases.json").get("phases")
        need(recorded_phases == record.get("phases") and [p.get("phase") for p in recorded_phases] == list(phases),
             "GT10PC_LINUX_PHASE_SET")
        state = _read(base / "install-state.json")
        need(state.get("active") == package["manifest_sha256"] and state.get("previous") is None
             and state.get("target") == "Linux-headless", "GT10PC_LINUX_FINAL_STATE")
        state_body = {k: v for k, v in state.items() if k != "state_sha256"}
        need(state.get("state_sha256") == digest_bytes(canonical(state_body) + b"\n"), "GT10PC_LINUX_STATE_HASH")
        for key, action, selected in (("install_receipt", "install", package), ("upgrade_receipt", "install", upgrade),
                                      ("rollback_receipt", "rollback", package), ("uninstall_receipt", "uninstall-addon", package),
                                      ("reinstall_receipt", "install-addon", package)):
            receipt = record.get(key, {})
            need(receipt.get("status") == "COMMITTED" and receipt.get("action") == action
                 and receipt.get("active") == selected["manifest_sha256"]
                 and state.get("commands", {}).get(receipt.get("command_id"), {}).get("receipt") == receipt,
                 "GT10PC_LINUX_COMMAND_JOURNAL")
        prior_profile = None
        for phase in recorded_phases:
            name = phase["phase"]
            selected = upgrade if name == "upgrade" else package
            need(phase.get("active") == selected["manifest_sha256"] and phase.get("project_ledger") == ready,
                 "GT10PC_LINUX_PHASE_BINDING")
            driver_base, native_base = base / "drivers" / name, base / "native" / name
            _process(driver_base, "driver", _read(driver_base / "receipt.json"), ownership="process_group")
            receipt = _read(native_base / "receipt.json")
            expected_studio = PurePosixPath("/output/consumer") / fixture / "install/releases" / selected["manifest_sha256"] / "payload/studio"
            need(receipt.get("schema") == "hh-installed-native-probe-2" and receipt.get("studio") == str(expected_studio)
                 and receipt.get("active_release") == selected["manifest_sha256"]
                 and receipt.get("version") == selected["manifest"]["version"]
                 and receipt.get("package_schema") == manifest["schema"] and receipt.get("target") == "Linux-headless"
                 and receipt.get("os_name") == "posix" and receipt.get("godot_sha256") == lock["binary_sha256"]
                 and receipt.get("probe_sha256") == manifest["files"]["payload/studio/package/installed_probe.py"]["sha256"]
                 and receipt.get("launcher_sha256") == manifest["files"]["payload/studio/build/bootstrap/run_fixture.py"]["sha256"],
                 "GT10PC_LINUX_INSTALLED_BINDING")
            profile = verify_profile(receipt, selected["manifest"], fixture, selected["members"])
            need(prior_profile is None or profile == prior_profile, "GT10PC_LINUX_PROFILE_PHASES")
            prior_profile = profile
            _process(native_base, "parse", receipt.get("parse"), ownership="process_group")
            lifecycle = _lifecycle(_process(native_base, "godot", receipt.get("process"), ownership="process_group"))
            checked.append({"fixture": fixture, "phase": name, "lifecycle": lifecycle, "exit": 0})
    return {"status": "DIAGNOSTIC_LINUX_VERIFIED", "authority": 0, "acceptance": False,
            "fixtures": checked, "evidence_files": len(doc["evidence"]), "artifact_sha256": package["archive_sha256"]}
