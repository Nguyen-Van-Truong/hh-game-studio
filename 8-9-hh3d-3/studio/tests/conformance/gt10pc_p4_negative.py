"""P4 reject-only schema and untrusted-rollback proof. No installer changes.

The same module is imported by the Windows probe now and by the Linux worker
later. It uses the stdlib plus the package modules that worker already imports.
Signing material is a caller-supplied signer; this file never loads a key.
"""
from __future__ import annotations

import os
import stat
import zipfile
from collections.abc import Callable
from pathlib import Path

from studio.package.consumer_install import ConsumerInstall
from studio.package.release_contract import (
    DOMAIN, SCHEMA, canonical, digest_bytes, digest_file, PackageError, strict_json,
    verify_manifest, verify_package,
)

SCHEMA_COMMAND_ID = "p4.negative.incompatible-schema"
ROLLBACK_COMMAND_ID = "p4.negative.untrusted-rollback"
BAD_SCHEMA = "hh-studio-package-incompatible"
ABSENT_KEY_ID = "hh-untrusted-absent"
SCHEMA_ERROR = "unsupported package schema"
ROLLBACK_ERROR = "untrusted signing key"


def _fail(code: str) -> None:
    raise ValueError("P4_NEG_" + code)


def _write_new(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _resign(manifest: dict, signer: Callable[[bytes], bytes], **overrides: object) -> bytes:
    body = dict(manifest)
    body.pop("signature", None)
    body.update(overrides)
    signature = signer(DOMAIN + canonical(body))
    if not isinstance(signature, bytes) or len(signature) != 64:
        _fail("SIGNATURE")
    body["signature"] = signature.hex()
    return canonical(body)


def _repack(source: Path, dest: Path, manifest_bytes: bytes) -> None:
    with zipfile.ZipFile(source) as original, dest.open("xb") as stream:
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            names = ["manifest.json", *sorted(name for name in original.namelist() if name != "manifest.json")]
            for name in names:
                data = manifest_bytes if name == "manifest.json" else original.read(name)
                info = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                archive.writestr(info, data)
        stream.flush()
        os.fsync(stream.fileno())


def build_bad_artifacts(good_package_path: Path, signer: Callable[[bytes], bytes],
                        out_dir: Path) -> dict[str, dict[str, str]]:
    """Re-sign one schema override and one absent trust id. No new keys."""
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(good_package_path) as archive:
        manifest = strict_json(archive.read("manifest.json"))
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
        _fail("GOOD_PACKAGE")
    incompatible = out_dir / "incompatible-schema.hhpkg"
    if incompatible.exists():
        _fail("OUTPUT_EXISTS")
    schema_bytes = _resign(manifest, signer, schema=BAD_SCHEMA)
    _repack(good_package_path, incompatible, schema_bytes)
    untrusted_bytes = _resign(manifest, signer, trust_key_id=ABSENT_KEY_ID)
    digest = digest_bytes(untrusted_bytes)
    manifest_path = out_dir / "untrusted-release" / digest / "manifest.json"
    _write_new(manifest_path, untrusted_bytes)
    return {
        "incompatible-schema.hhpkg": {"path": str(incompatible), "sha256": digest_file(incompatible)},
        "untrusted-manifest": {"path": str(manifest_path), "sha256": digest},
    }


def _refuse(install_root: Path, case_dir: Path, command_id: str, expected: str,
            kind: str, call: Callable[[], object]) -> None:
    state_path = install_root / ".install.json"
    before = state_path.read_bytes()
    _write_new(case_dir / "state-before.install.json", before)
    _write_new(case_dir / "command-id.txt", command_id.encode("ascii"))
    try:
        call()
    except ValueError as exc:
        # package.* and studio.package.* are the same tree loaded twice under
        # the unit-test path. Match the class name so either copy is the refusal.
        if type(exc).__name__ != "PackageError":
            raise
        observed = str(exc)
    else:
        _fail(kind + "_ACCEPTED")
    after = state_path.read_bytes()
    _write_new(case_dir / "state-after.install.json", after)
    _write_new(case_dir / "exception.txt", observed.encode("ascii"))
    if observed != expected:
        _fail(kind + "_EXCEPTION")
    if before != after:
        _fail("STATE_BYTES")


def _arm_untrusted_previous(install_root: Path, manifest_bytes: bytes, digest: str) -> str:
    release = install_root / "releases" / digest
    if release.exists():
        _fail("RELEASE_EXISTS")
    _write_new(release / "manifest.json", manifest_bytes)
    state_path = install_root / ".install.json"
    state = strict_json(state_path.read_bytes())
    if not isinstance(state, dict):
        _fail("STATE")
    state["previous"] = digest
    raw = canonical(state) + b"\n"
    temporary = state_path.with_name(".install.json.p4neg-tmp")
    _write_new(temporary, raw)
    os.replace(temporary, state_path)
    return digest_bytes(raw)


def run_negative(install_root: Path, open_consumer: Callable[[], ConsumerInstall],
                 artifacts: dict[str, dict[str, str]], out_dir: Path) -> dict[str, str]:
    """Refuse one incompatible install and one untrusted rollback. No Play."""
    package = Path(artifacts["incompatible-schema.hhpkg"]["path"])
    manifest_path = Path(artifacts["untrusted-manifest"]["path"])
    manifest_bytes = manifest_path.read_bytes()
    if digest_bytes(manifest_bytes) != artifacts["untrusted-manifest"]["sha256"]:
        _fail("MANIFEST_HASH")

    def reject_schema() -> None:
        consumer = open_consumer()
        consumer.install(package, command_id=SCHEMA_COMMAND_ID,
                         expected_state_sha256=consumer.snapshot()["state_sha256"])

    _refuse(install_root, out_dir / "incompatible-schema", SCHEMA_COMMAND_ID,
            SCHEMA_ERROR, "SCHEMA", reject_schema)
    state_sha256 = _arm_untrusted_previous(install_root, manifest_bytes, digest_bytes(manifest_bytes))
    _write_new(out_dir / "untrusted-rollback" / "setup.json", canonical({
        "previous": digest_bytes(manifest_bytes), "state_sha256": state_sha256}) + b"\n")

    def reject_rollback() -> None:
        consumer = open_consumer()
        consumer.rollback(command_id=ROLLBACK_COMMAND_ID, destination=digest_bytes(manifest_bytes),
                          expected_state_sha256=consumer.snapshot()["state_sha256"])

    _refuse(install_root, out_dir / "untrusted-rollback", ROLLBACK_COMMAND_ID,
            ROLLBACK_ERROR, "ROLLBACK", reject_rollback)
    return {"incompatible-schema": SCHEMA_ERROR, "untrusted-rollback": ROLLBACK_ERROR}


def _read_exact(path: Path, code: str) -> bytes:
    if not path.is_file():
        _fail(code)
    return path.read_bytes()


def _json_object(raw: bytes, code: str) -> dict:
    try:
        value = strict_json(raw)
    except PackageError:
        _fail(code)
    if not isinstance(value, dict):
        _fail(code)
    return value


def _case_state(case_dir: Path, command_id: str) -> tuple[dict, dict, str]:
    before_raw = _read_exact(case_dir / "state-before.install.json", "CASE_MISSING")
    after_raw = _read_exact(case_dir / "state-after.install.json", "CASE_MISSING")
    if before_raw != after_raw:
        _fail("STATE_BYTES")
    if _read_exact(case_dir / "command-id.txt", "COMMAND_ID") != command_id.encode("ascii"):
        _fail("COMMAND_ID")
    before = _json_object(before_raw, "STATE")
    after = _json_object(after_raw, "STATE")
    if before.get("active") != after.get("active") or before.get("previous") != after.get("previous"):
        _fail("SELECTOR")
    commands = after.get("commands")
    if not isinstance(commands, dict) or command_id in commands:
        _fail("COMMAND_PRESENT")
    if not isinstance(after.get("active"), str) or not isinstance(after.get("previous"), str):
        _fail("SELECTOR")
    return before, after, digest_bytes(before_raw)


def _exception_text(case_dir: Path, expected: str) -> None:
    if _read_exact(case_dir / "exception.txt", "EXCEPTION") != expected.encode("ascii"):
        _fail("EXCEPTION")


def verify_negative(out_dir: Path, trust: dict[str, bytes]) -> dict:
    """Recompute both refusals from raw files. Ignore any producer rejected flag."""
    if not isinstance(trust, dict) or not trust:
        _fail("TRUST")
    schema_before, _schema_after, schema_state = _case_state(
        out_dir / "incompatible-schema", SCHEMA_COMMAND_ID)
    _exception_text(out_dir / "incompatible-schema", SCHEMA_ERROR)
    target = schema_before.get("target")
    if not isinstance(target, str):
        _fail("TARGET")
    package_path = out_dir / "incompatible-schema.hhpkg"
    try:
        with zipfile.ZipFile(package_path) as archive:
            packaged = _json_object(archive.read("manifest.json"), "SCHEMA_VALUE")
    except (zipfile.BadZipFile, OSError):
        _fail("SCHEMA_VALUE")
    if packaged.get("schema") == SCHEMA or packaged.get("schema") != BAD_SCHEMA:
        _fail("SCHEMA_VALUE")
    if packaged.get("trust_key_id") not in trust:
        _fail("SCHEMA_KEY")
    try:
        verify_package(package_path, trusted_keys=trust, target=target)
    except PackageError as exc:
        if str(exc) != SCHEMA_ERROR:
            _fail("SCHEMA_TEXT")
    else:
        _fail("SCHEMA_ACCEPTED")
    rollback_before, rollback_after, rollback_state = _case_state(
        out_dir / "untrusted-rollback", ROLLBACK_COMMAND_ID)
    _exception_text(out_dir / "untrusted-rollback", ROLLBACK_ERROR)
    release_root = out_dir / "untrusted-release"
    children = [path for path in release_root.iterdir() if path.is_dir()] if release_root.is_dir() else []
    if len(children) != 1:
        _fail("MANIFEST_NAME")
    manifest_path = children[0] / "manifest.json"
    raw = _read_exact(manifest_path, "MANIFEST_NAME")
    digest = digest_bytes(raw)
    if digest != children[0].name:
        _fail("MANIFEST_NAME")
    if rollback_before.get("previous") != digest or rollback_after.get("previous") != digest:
        _fail("PREVIOUS")
    setup = _json_object(_read_exact(out_dir / "untrusted-rollback" / "setup.json", "SETUP"), "SETUP")
    if setup.get("previous") != digest or setup.get("state_sha256") != rollback_state:
        _fail("SETUP")
    manifest = _json_object(raw, "MANIFEST_NAME")
    if manifest.get("trust_key_id") in trust or manifest.get("trust_key_id") != ABSENT_KEY_ID:
        _fail("ROLLBACK_KEY")
    try:
        verify_manifest(manifest, trusted_keys=trust, target=target)
    except PackageError as exc:
        if str(exc) != ROLLBACK_ERROR:
            _fail("ROLLBACK_TEXT")
    else:
        _fail("ROLLBACK_ACCEPTED")
    if schema_before.get("active") != rollback_after.get("active"):
        _fail("SELECTOR")
    return {
        "status": "P4_NEG_VERIFIED", "authority": 0, "acceptance": False,
        "cases": {
            "incompatible-schema": {
                "command_id": SCHEMA_COMMAND_ID, "error": SCHEMA_ERROR,
                "state_sha256": schema_state, "active": schema_before["active"],
                "previous": schema_before["previous"],
            },
            "untrusted-rollback": {
                "command_id": ROLLBACK_COMMAND_ID, "error": ROLLBACK_ERROR,
                "state_sha256": rollback_state, "active": rollback_after["active"],
                "previous": rollback_after["previous"], "manifest_sha256": digest,
            },
        },
    }
