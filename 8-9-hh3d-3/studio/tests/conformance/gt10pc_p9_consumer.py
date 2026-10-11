"""Independent archive-only consumer smoke and read-only native verification."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from studio.package.consumer_install import ConsumerInstall
from studio.package.consumer_support import _consumer_fixture_files, support_bundle
from studio.package.release_contract import (
    digest_bytes, digest_file, need, safe_path, strict_json, verify_package,
)
from studio.package.trust import load_trust
from studio.tests.conformance.run_gt10pc_native_probe import (
    GODOT_WINDOWS, native_phase, project_ledger, write_json,
)

FIXTURE = "gt09-arena"
SAVE = b"p9-independent-consumer-save\n"
LEDGERS = ("project-before.json", "project-installed.json", "project-after.json")


def prepare_consumer(package: dict, root: Path) -> Path:
    """Use every fixture byte from the verified package, never the live repo."""
    root = safe_path(root)
    need(not root.exists(), "P9_CONSUMER_OUTPUT_EXISTS")
    project = root / "project"
    project.mkdir(parents=True)
    for name, data in _consumer_fixture_files(package, FIXTURE).items():
        path = safe_path(project / name)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)
    with (project / "consumer-save.dat").open("xb") as stream:
        stream.write(SAVE)
    return project


def run_consumer(output: Path, artifact: Path, *, trust: Path, trust_sha256: str) -> dict:
    keys = load_trust(trust, expected_sha256=trust_sha256)
    package = verify_package(artifact, trusted_keys=keys, target="Windows")
    project = prepare_consumer(package, output)
    write_json(output / LEDGERS[0], project_ledger(project))
    installer = ConsumerInstall(output / "install", trusted_keys=keys)
    receipt = installer.install_lifecycle(project, artifact,
        command_id="p9.independent-consumer.install", expected_state_sha256="ABSENT")
    write_json(output / "install-receipt.json", receipt)
    installed = project_ledger(project)
    write_json(output / LEDGERS[1], installed)
    state = installer.snapshot()
    write_json(output / "state-before-play.json", state)
    native_phase(output, FIXTURE, "install", installer, project,
                 SimpleNamespace(trust=trust, trust_sha256=trust_sha256),
                 godot=GODOT_WINDOWS, target="Windows")
    after = project_ledger(project)
    write_json(output / LEDGERS[2], after)
    after_state = installer.snapshot()
    write_json(output / "state-after-play.json", after_state)
    need(installed == after and state == after_state, "P9_PLAY_MUTATED_CONSUMER")
    support_bundle(artifact, output / "support.json", trusted_keys=keys,
                   target="Windows", install=installer)
    report = {"schema": "hh-gt10pc-p9-consumer-1", "authority": 0, "acceptance": False,
              "artifact_sha256": package["archive_sha256"],
              "manifest_sha256": package["manifest_sha256"],
              "source_closure_sha256": package["manifest"]["source_closure_sha256"],
              "trust_sha256": trust_sha256, "fixture": FIXTURE}
    evidence = list(LEDGERS) + ["install-receipt.json", "state-before-play.json",
                               "state-after-play.json", "support.json"]
    for domain, labels in (("drivers", ("driver",)), ("godot", ("parse", "godot"))):
        prefix = domain + "/" + FIXTURE + "/"
        evidence.append(prefix + "receipt.json")
        evidence.extend(prefix + label + suffix for label in labels
                        for suffix in ("-host.json", "-stdout.txt", "-stderr.txt"))
    report["evidence"] = {name: digest_file(output / name) for name in evidence}
    write_json(output / "p9.json", report)
    return verify_consumer(output, artifact, trust=trust, trust_sha256=trust_sha256)


def verify_consumer(output: Path, artifact: Path, *, trust: Path, trust_sha256: str) -> dict:
    # Import lazily: the matrix also invokes this producer.
    from studio.tests.conformance.run_gt10pc_matrix import _read, _process, _lifecycle, verify_profile
    from studio.package.release_contract import _safe_member, HEX
    keys = load_trust(trust, expected_sha256=trust_sha256)
    package = verify_package(artifact, trusted_keys=keys, target="Windows")
    manifest = package["manifest"]
    doc = _read(output / "p9.json")
    need(doc.get("schema") == "hh-gt10pc-p9-consumer-1" and doc.get("authority") == 0
         and doc.get("acceptance") is False and doc.get("fixture") == FIXTURE
         and doc.get("trust_sha256") == trust_sha256
         and doc.get("artifact_sha256") == package["archive_sha256"]
         and doc.get("manifest_sha256") == package["manifest_sha256"]
         and doc.get("source_closure_sha256") == manifest["source_closure_sha256"],
         "P9_ARTIFACT_BINDING")
    expected_files = set(LEDGERS) | {"install-receipt.json", "state-before-play.json",
                                    "state-after-play.json", "support.json"}
    for domain, labels in (("drivers", ("driver",)), ("godot", ("parse", "godot"))):
        prefix = domain + "/" + FIXTURE + "/"
        expected_files.add(prefix + "receipt.json")
        expected_files.update(prefix + label + suffix for label in labels
                              for suffix in ("-host.json", "-stdout.txt", "-stderr.txt"))
    need(isinstance(doc.get("evidence"), dict) and set(doc["evidence"]) == expected_files,
         "P9_EVIDENCE_SET")
    for name, digest in doc["evidence"].items():
        _safe_member(name)
        need(isinstance(digest, str) and HEX.fullmatch(digest)
             and digest_file(output / name) == digest, "P9_EVIDENCE_HASH:" + name)
    prefix = "payload/studio/fixtures/" + FIXTURE + "/"
    baseline = {name[len(prefix):]: row for name, row in manifest["files"].items()
                if name.startswith(prefix)}
    baseline["consumer-save.dat"] = {"sha256": digest_bytes(SAVE), "size": len(SAVE)}
    addon_prefix = "payload/studio/godot-addon/addons/hh_studio/"
    installed = {**baseline, **{"addons/hh_studio/" + name[len(addon_prefix):]: row
                 for name, row in manifest["files"].items() if name.startswith(addon_prefix)}}
    installed["addons/hh_studio/jcs_godot.gd"] = manifest["files"]["payload/studio/protocol/jcs_godot.gd"]
    need(_read(output / LEDGERS[0]) == baseline and _read(output / LEDGERS[1]) == installed
         and _read(output / LEDGERS[2]) == installed
         and project_ledger(output / "project") == installed, "P9_CONSUMER_LEDGER")
    state = _read(output / "state-before-play.json")
    need(state == _read(output / "state-after-play.json")
         and state.get("active") == package["manifest_sha256"], "P9_CONSUMER_STATE")
    receipt = _read(output / "install-receipt.json")
    need(receipt.get("status") == "COMMITTED" and receipt.get("active") == state["active"]
         and state.get("commands", {}).get(receipt.get("command_id"), {}).get("receipt") == receipt,
         "P9_INSTALL_RECEIPT")
    driver, native = output / "drivers" / FIXTURE, output / "godot" / FIXTURE
    _process(driver, "driver", _read(driver / "receipt.json"))
    observed = _read(native / "receipt.json")
    expected_studio = output / "install/releases" / state["active"] / "payload/studio"
    lock = strict_json(package["members"]["payload/studio/toolchain.lock.json"])
    need(observed.get("schema") == "hh-installed-native-probe-2"
         and observed.get("active_release") == state["active"]
         and observed.get("version") == manifest["version"]
         and observed.get("package_schema") == manifest["schema"]
         and observed.get("target") == "Windows" and observed.get("os_name") == "nt"
         and safe_path(Path(observed.get("studio", ""))) == safe_path(expected_studio)
         and observed.get("godot_sha256") == lock["godot"]["console_sha256"]
         and observed.get("probe_sha256") == manifest["files"]["payload/studio/package/installed_probe.py"]["sha256"]
         and observed.get("launcher_sha256") == manifest["files"]["payload/studio/build/bootstrap/run_fixture.py"]["sha256"],
         "P9_INSTALLED_SOURCE_BINDING")
    verify_profile(observed, manifest, FIXTURE, package["members"])
    _process(native, "parse", observed.get("parse"))
    _lifecycle(_process(native, "godot", observed.get("process")))
    bundle = _read(output / "support.json")
    need(set(bundle) == {"schema", "authority", "acceptance", "scrub_policy", "package",
                        "artifact_sha256", "manifest_sha256", "network_used", "install"}
         and bundle.get("artifact_sha256") == package["archive_sha256"]
         and bundle.get("manifest_sha256") == package["manifest_sha256"]
         and bundle.get("scrub_policy") == "allowlist-no-raw-values-v1"
         and bundle.get("package") == {k: manifest[k] for k in
             ("package_id", "version", "target", "schema", "source_closure_sha256")}
         and bundle.get("install") == {"state_sha256": state["state_sha256"],
             "revision": state["revision"], "active": state["active"], "previous": state["previous"],
             "command_count": len(state["commands"]),
             "command_id_sha256": sorted(digest_bytes(key.encode()) for key in state["commands"])},
         "P9_SUPPORT_ALLOWLIST")
    for name in ("docs/NOTICE.txt", "docs/runbook.md", "docs/known-limits.md", "docs/compatibility-lock.json"):
        need(bool(package["members"].get(name)), "P9_PACKAGE_DOCUMENTS_MISSING")
    return {"status": "REHEARSAL_PASS", "authority": 0, "acceptance": False,
            "evidence_kind": "docs+native", "artifact_sha256": package["archive_sha256"],
            "report_sha256": digest_file(output / "p9.json")}
