"""Offline intake diagnostics and a small allowlisted support bundle.

No dependency is downloaded and no raw environment/log/project data is copied.
The bundle is a support aid, not native or release acceptance evidence.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Mapping

from .release_contract import (
    PackageError, canonical, digest_bytes, digest_file, need, safe_path,
    strict_json, verify_package,
)


def _consumer_fixture_files(package: dict, fixture: str) -> dict[str, bytes]:
    prefix = "payload/studio/fixtures/" + fixture + "/"
    files = {name[len(prefix):]: data for name, data in package["members"].items()
             if name.startswith(prefix)}
    need("project.godot" in files and "scenes/fixture.tscn" in files,
         "consumer fixture is incomplete; restore the signed fixture closure")
    return files


def verify_local_dependencies(package: dict, paths: Mapping[str, Path], *,
                              required: tuple[str, ...]) -> dict:
    """Check explicit local tool inputs against the verified archive lock.

    Export templates are required only for export, not addon installation.
    Callers name their operation's required subset; unknown names fail closed.
    """
    lock = strict_json(package["members"]["payload/studio/toolchain.lock.json"])
    definitions = {
        "godot": (lock["godot"]["version"], lock["godot"]["console_sha256"]),
        "export_templates": (lock["export_templates"]["version"], lock["export_templates"]["sha256"]),
        "blender": (lock["blender"]["version"], lock["blender"]["executable_sha256"]),
    }
    need(isinstance(required, tuple) and len(required) == len(set(required))
         and set(required) <= set(definitions), "unknown or duplicate dependency requirement")
    need(set(paths) <= set(definitions), "unknown local dependency override")
    observed = {}
    for name in required:
        version, expected = definitions[name]
        action = ("provide the exact local " + name + " " + version +
                  " from toolchain.lock.json; latest/network auto-fetch is disabled")
        if name not in paths:
            raise PackageError("missing dependency " + name + "; " + action)
        try:
            path = safe_path(paths[name])
            need(path.is_file(), "missing dependency " + name + "; " + action)
            actual = digest_file(path)
        except OSError as exc:
            raise PackageError("unreadable dependency " + name + "; " + action) from exc
        need(actual == expected, "dependency version/hash mismatch for " + name + "; " + action)
        observed[name] = {"version": version, "sha256": actual}
    return {"schema": "hh-studio-dependency-check-1", "network_used": False,
            "latest_autofetch": False, "dependencies": observed}


def verify_addon_version(package: dict, addon: Path | None) -> None:
    """Reject an existing incompatible consumer addon before changing it."""
    if addon is None:
        return
    config = safe_path(addon / "plugin.cfg")
    expected = strict_json(package["members"]["docs/compatibility-lock.json"])["addon"]["version"]
    action = ("preserve the existing addon and select a matching pinned package, or explicitly "
              "repair the owned addon; latest/network auto-fetch is disabled")
    need(config.is_file(), "addon version missing; " + action)
    need(config.stat().st_size <= 65536, "addon config oversized; " + action)
    try:
        match = re.search(r'(?m)^version="([^"]+)"\s*$', config.read_text(encoding="utf-8"))
    except UnicodeError as exc:
        raise PackageError("addon version unreadable; " + action) from exc
    need(match is not None and match.group(1) == expected,
         "addon version mismatch (expected " + expected + "); " + action)


def preflight(artifact: Path, *, trusted_keys: Mapping[str, bytes], target: str,
              expected_version: str | None = None, paths: Mapping[str, Path] | None = None,
              required: tuple[str, ...] = (), addon: Path | None = None) -> dict:
    """Verify artifact and closure before examining external tools or installing."""
    package = verify_package(artifact, trusted_keys=trusted_keys, target=target,
                             expected_version=expected_version)
    dependencies = verify_local_dependencies(package, paths or {}, required=required)
    verify_addon_version(package, addon)
    return {"schema": "hh-studio-consumer-preflight-1", "authority": 0,
            "acceptance": False, "artifact_sha256": package["archive_sha256"],
            "manifest_sha256": package["manifest_sha256"],
            "source_closure_sha256": package["manifest"]["source_closure_sha256"],
            "dependencies": dependencies["dependencies"], "network_used": False,
            "latest_autofetch": False}


def install_checked(artifact: Path, root: Path, *, trusted_keys: Mapping[str, bytes],
                    target: str, command_id: str, expected_state_sha256: str,
                    paths: Mapping[str, Path] | None = None,
                    required: tuple[str, ...] = (), addon: Path | None = None) -> dict:
    """Perform intake before constructing or mutating an installer root."""
    from .consumer_install import ConsumerInstall
    preflight(artifact, trusted_keys=trusted_keys, target=target, paths=paths,
              required=required, addon=addon)
    install = ConsumerInstall(root, trusted_keys=trusted_keys, target=target)
    return install.install(artifact, command_id=command_id,
                           expected_state_sha256=expected_state_sha256)


def support_bundle(artifact: Path, output: Path, *, trusted_keys: Mapping[str, bytes],
                   target: str, install=None) -> dict:
    """Write only verified identities, counters and hashes, never raw state.

    Hash command ids because even caller-chosen IDs may contain secrets. Paths,
    command requests, receipts, project ownership, logs and environments are not
    admitted into the bundle at all; regex redaction cannot protect unknown keys.
    """
    package = verify_package(artifact, trusted_keys=trusted_keys, target=target)
    manifest = package["manifest"]
    bundle = {"schema": "hh-studio-support-bundle-1", "authority": 0,
              "acceptance": False, "scrub_policy": "allowlist-no-raw-values-v1",
              "package": {k: manifest[k] for k in
                          ("package_id", "version", "target", "schema", "source_closure_sha256")},
              "artifact_sha256": package["archive_sha256"],
              "manifest_sha256": package["manifest_sha256"],
              "network_used": False, "install": None}
    if install is not None:
        state = install.snapshot()
        bundle["install"] = {"state_sha256": state["state_sha256"],
                             "revision": state["revision"], "active": state["active"],
                             "previous": state["previous"],
                             "command_count": len(state["commands"]),
                             "command_id_sha256": sorted(digest_bytes(key.encode("utf-8"))
                                                         for key in state["commands"])}
    data = canonical(bundle) + b"\n"
    output = safe_path(output)
    need(not output.exists(), "support bundle output already exists; choose a fresh path")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    need(output.read_bytes() == data, "support bundle readback failed")
    return {"schema": bundle["schema"], "sha256": digest_bytes(data),
            "bytes": len(data), "scrub_policy": bundle["scrub_policy"]}


def consumer_fixture_smoke(artifact: Path, root: Path, *,
                           trusted_keys: Mapping[str, bytes], target: str = "Windows",
                           fixture: str = "gt09-arena") -> dict:
    """Install the verified artifact into a fresh fixture and read it back.

    This intentionally consumes the archive as a consumer would; it does not
    import producer receipts or trust a caller-supplied PASS field.
    """
    from .consumer_install import ConsumerInstall

    package = verify_package(artifact, trusted_keys=trusted_keys, target=target)
    fixture_files = _consumer_fixture_files(package, fixture)
    root = safe_path(root)
    need(not root.exists(), "consumer smoke root already exists; use a fresh root")
    project = safe_path(root / "project")
    project.mkdir(parents=True)
    (project / "project.godot").write_bytes(fixture_files["project.godot"])
    sentinel = project / "consumer-save.dat"
    sentinel.write_bytes(b"consumer-owned-save\n")
    installer = ConsumerInstall(root / "install", trusted_keys=trusted_keys, target=target)
    token = installer.snapshot()["state_sha256"]
    receipt = installer.install(artifact, command_id="consumer-smoke-install",
                                expected_state_sha256=token)
    token = installer.snapshot()["state_sha256"]
    addon = installer.install_addon(project, release=receipt["active"],
                                    command_id="consumer-smoke-addon",
                                    expected_state_sha256=token)
    need(addon["status"] == "COMMITTED" and addon["active"] == receipt["active"],
         "consumer smoke install receipt mismatch")
    for relative, expected in installer.addon_files(receipt["active"]).items():
        actual = safe_path(project / "addons/hh_studio" / relative).read_bytes()
        need(actual == expected, "consumer smoke addon readback mismatch: " + relative)
    token = installer.snapshot()["state_sha256"]
    uninstall = installer.uninstall_addon(project, command_id="consumer-smoke-uninstall",
                                          expected_state_sha256=token)
    need(uninstall["status"] == "COMMITTED" and sentinel.read_bytes() == b"consumer-owned-save\n",
         "consumer smoke removed consumer save")
    return {"schema": "hh-studio-consumer-smoke-1", "authority": 0,
            "acceptance": False, "fixture": fixture, "target": target,
            "artifact_sha256": package["archive_sha256"],
            "source_closure_sha256": package["manifest"]["source_closure_sha256"],
            "addon_files_readback": len(installer.addon_files(receipt["active"])),
            "consumer_save_preserved": True, "network_used": False}
