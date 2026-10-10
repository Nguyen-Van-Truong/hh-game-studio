"""Offline archive contract: external trust, bounded verify-before-extract.

Signing is injected by a publisher outside the artifact. Runtime verification
contains only public-key code. Consumer transactions are in consumer_install.
No native acceptance or public distribution is implied by archive verification.
"""
from __future__ import annotations
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Callable, Mapping
import uuid
import zipfile

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
try:
    from build.bootstrap.install_toolchain import safe_path, sync_directory
except ModuleNotFoundError:
    from studio.build.bootstrap.install_toolchain import safe_path, sync_directory

SCHEMA = "hh-studio-package-0.1"
DOMAIN = b"HH-STUDIO-OFFLINE-RELEASE-2\x00"
TARGETS = ("Windows", "Linux", "Linux-headless")
MAX_MEMBER, MAX_TOTAL, MAX_ARCHIVE = 64 * 1024**2, 512 * 1024**2, 128 * 1024**2
MAX_FILES, MAX_MANIFEST = 8192, 4 * 1024**2
HEX = re.compile(r"[0-9a-f]{64}\Z")
VERSION = re.compile(r"0\.1\.(0|[1-9][0-9]{0,5})\Z")
SEGMENT = re.compile(r"[A-Za-z0-9_.-]{1,120}\Z")
DEVICES = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1,10)), *(f"LPT{i}" for i in range(1,10))}
SOURCE_DOMAINS = ("host", "protocol", "contracts", "godot-addon", "blender-addon",
                  "pipeline", "build", "fixtures", "package", "tests", "reviewer")
EXCLUDED_DIRS = {".local", ".godot", ".git", "__pycache__", ".pytest_cache", ".mypy_cache"}
EXCLUDED_FILES = {"tests/conformance/gt10pc_signing.py"}


class PackageError(ValueError):
    pass


def need(condition: Any, message: str) -> None:
    if not condition:
        raise PackageError(message)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_file(path: Path) -> str:
    with safe_path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def strict_json(data: bytes) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    try:
        return json.loads(data, object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(PackageError("nonfinite JSON")))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise PackageError("invalid JSON") from exc


def _safe_member(name: str) -> None:
    need(isinstance(name, str) and 0 < len(name) <= 240, "invalid member length")
    parts = name.split("/")
    for part in parts:
        need(SEGMENT.fullmatch(part) and part not in (".", "..")
             and not part.endswith(".") and part.split(".")[0].upper() not in DEVICES,
             "nonportable package member")
    need(not any(p.casefold() in EXCLUDED_DIRS for p in parts)
         and not name.casefold().startswith(("zdoc/", "evidence/", "payload/studio/evidence/")),
         "generated evidence/cache cannot ship")


def check_names(names: list[str]) -> None:
    folded = set()
    for name in names:
        _safe_member(name)
        key = name.casefold()
        need(key not in folded, "duplicate/case-colliding package member")
        folded.add(key)
    for key in folded:
        parts = key.split("/")
        need(not any("/".join(parts[:i]) in folded for i in range(1, len(parts))), "file/directory collision")


def file_ledger(files: Mapping[str, bytes]) -> dict[str, dict]:
    return {name: {"sha256": digest_bytes(data), "size": len(data)} for name, data in sorted(files.items())}


def _payload_digest(files: Mapping[str, bytes]) -> str:
    return digest_bytes(canonical(file_ledger(files)))


def _source_files(source_root: Path) -> dict[str, bytes]:
    """Explicit source domains; tests are a separate verification component.

    Accepted runtime bindings include some test helpers. Preserve their pinned
    bytes, not historical evidence, generated caches or the publisher signer.
    """
    root = safe_path(source_root)
    files = {}
    for domain in SOURCE_DOMAINS:
        base = safe_path(root / domain)
        need(base.is_dir(), "missing source domain: " + domain)
        for directory, dirs, names in os.walk(base, followlinks=False):
            dirs[:] = sorted(d for d in dirs if d not in EXCLUDED_DIRS)
            for name in dirs:
                safe_path(Path(directory) / name)
            for name in sorted(names):
                path = safe_path(Path(directory) / name)
                rel = path.relative_to(root).as_posix()
                if rel in EXCLUDED_FILES or path.suffix in {".pyc", ".pyo"}:
                    continue
                need(path.stat().st_size <= MAX_MEMBER, "source file too large")
                files["payload/studio/" + rel] = path.read_bytes()
    files["payload/studio/toolchain.lock.json"] = safe_path(root / "toolchain.lock.json").read_bytes()
    check_names(list(files))
    binding = strict_json(files["payload/studio/host/replay/execution-source.json"])
    for name, expected in binding["source_files"].items():
        need("payload/studio/" + name in files, "execution dependency absent: " + name)
        need(digest_bytes(files["payload/studio/" + name]) == expected, "execution dependency changed: " + name)
    selector = strict_json(files["payload/studio/host/replay/execution-current.json"])
    need(selector.get("binding_sha256") == digest_bytes(files["payload/studio/host/replay/execution-source.json"]),
         "execution selector is stale")
    from studio.host.replay.execution_installed import _required_sources
    need(_required_sources(root) <= set(binding["source_files"]), "execution binding misses runtime dependencies")
    return files


def _component_digest(files: Mapping[str, bytes], prefixes: tuple[str, ...]) -> str:
    subset = {name: data for name, data in files.items() if name.startswith(prefixes)}
    need(subset, "required component absent")
    return _payload_digest(subset)


def build_package(source_root: Path, output: Path, *, signer: Callable[[bytes], bytes],
                  key_id: str, version: str = "0.1.0", target: str = "Windows") -> dict:
    need(VERSION.fullmatch(version) and target in TARGETS, "unsupported version/target")
    need(isinstance(key_id, str) and SEGMENT.fullmatch(key_id), "invalid trust key id")
    files = _source_files(source_root)
    closure = _payload_digest(files)
    identity = {"version": version, "target": target, "source_closure_sha256": closure}
    package_id = "hh-studio-" + digest_bytes(canonical(identity))
    for name in ("NOTICE.txt", "runbook.md", "known-limits.md", "requirements.txt"):
        files["docs/" + name] = files["payload/studio/package/" + name]
    files["docs/SBOM.json"] = canonical({"schema": "hh-file-sbom-1", "package_id": package_id,
        "components": {"runtime": [d for d in SOURCE_DOMAINS if d not in ("tests", "reviewer")],
                       "verification": ["tests", "reviewer"]}, "files": file_ledger(files),
        "external_dependencies": {"cryptography": "46.0.5", "tools": "payload/studio/toolchain.lock.json"}})
    manifest = {"schema": SCHEMA, "package_id": package_id, **identity,
        "supported_targets": list(TARGETS), "android": "DEFERRED_NO_DEVICE",
        "content_sha256": _payload_digest(files),
        "protocol_schema_digest": _component_digest(files, ("payload/studio/protocol/", "payload/studio/contracts/")),
        "toolchain_lock_sha256": digest_bytes(files["payload/studio/toolchain.lock.json"]),
        "trust_key_id": key_id, "security_floor": "local-test-floor-1",
        "rollback_compatibility": {"schema": SCHEMA, "version_series": "0.1"},
        "monetization": "OFF", "failpoint": "DISABLED", "files": file_ledger(files)}
    signature = signer(DOMAIN + canonical(manifest))
    need(isinstance(signature, bytes) and len(signature) == 64, "publisher signature invalid")
    manifest["signature"] = signature.hex()
    check_names(["manifest.json", *files])
    need(len(files) < MAX_FILES and sum(len(v) for v in files.values()) < MAX_TOTAL, "package limit")
    output = safe_path(output)
    need(not output.exists(), "artifact already exists; use a fresh output")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = safe_path(output.with_name(output.name + "." + uuid.uuid4().hex + ".tmp"))
    with temporary.open("xb") as stream:
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for name, data in [("manifest.json", canonical(manifest)), *sorted(files.items())]:
                info = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                archive.writestr(info, data)
        stream.flush(); os.fsync(stream.fileno())
    os.rename(temporary, output)
    sync_directory(output.parent)
    return {"manifest": manifest, "manifest_sha256": digest_bytes(canonical(manifest)),
            "artifact_path": str(output), "archive_sha256": digest_file(output)}


def verify_manifest(manifest: Any, *, trusted_keys: Mapping[str, bytes], target: str,
                    expected_version: str | None = None) -> None:
    need(isinstance(manifest, dict), "manifest is not an object")
    body = dict(manifest)
    signature = body.pop("signature", None)
    need(set(body) == {"schema", "package_id", "version", "target", "source_closure_sha256",
         "supported_targets", "android", "content_sha256", "protocol_schema_digest", "toolchain_lock_sha256",
         "trust_key_id", "security_floor", "rollback_compatibility", "monetization", "failpoint", "files"},
         "unknown/missing manifest fields")
    key = trusted_keys.get(body.get("trust_key_id")) if isinstance(body.get("trust_key_id"), str) else None
    need(key is not None, "untrusted signing key")
    try:
        Ed25519PublicKey.from_public_bytes(key).verify(bytes.fromhex(signature), DOMAIN + canonical(body))
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise PackageError("package signature invalid") from exc
    need(body.get("schema") == SCHEMA, "unsupported package schema")
    version = body.get("version")
    need(isinstance(version, str) and VERSION.fullmatch(version), "incompatible package version")
    need(expected_version is None or version == expected_version, "package version rejected")
    need(target in TARGETS and body.get("target") == target and body.get("supported_targets") == list(TARGETS), "package target rejected")
    need(body.get("android") == "DEFERRED_NO_DEVICE" and body.get("monetization") == "OFF"
         and body.get("failpoint") == "DISABLED", "unsafe release flags")
    need(body.get("security_floor") == "local-test-floor-1" and body.get("rollback_compatibility") ==
         {"schema": SCHEMA, "version_series": "0.1"}, "incompatible rollback/security policy")
    for field in ("source_closure_sha256", "content_sha256", "protocol_schema_digest", "toolchain_lock_sha256"):
        need(isinstance(body.get(field), str) and HEX.fullmatch(body[field]), "invalid manifest digest")
    identity = {key: body[key] for key in ("version", "target", "source_closure_sha256")}
    need(body.get("package_id") == "hh-studio-" + digest_bytes(canonical(identity)), "invalid package identity")
    rows = body.get("files")
    need(isinstance(rows, dict) and 0 < len(rows) < MAX_FILES and "manifest.json" not in rows, "invalid file ledger")
    check_names(list(rows))
    for name, row in rows.items():
        need(name.startswith(("payload/studio/", "docs/")) and isinstance(row, dict)
             and set(row) == {"sha256", "size"} and isinstance(row["sha256"], str)
             and HEX.fullmatch(row["sha256"]) and type(row["size"]) is int
             and 0 <= row["size"] <= MAX_MEMBER, "invalid ledger row")


def verify_contents(manifest: dict, members: Mapping[str, bytes]) -> None:
    need(file_ledger(members) == manifest["files"], "package closure hash mismatch")
    need(_payload_digest(members) == manifest["content_sha256"], "package content mismatch")
    source = {k: v for k, v in members.items() if k.startswith("payload/studio/")}
    need(_payload_digest(source) == manifest["source_closure_sha256"], "source closure mismatch")
    need(_component_digest(members, ("payload/studio/protocol/", "payload/studio/contracts/")) == manifest["protocol_schema_digest"], "protocol/schema mismatch")
    need(digest_bytes(members.get("payload/studio/toolchain.lock.json", b"")) == manifest["toolchain_lock_sha256"], "toolchain lock mismatch")


def verify_package(path: Path, *, trusted_keys: Mapping[str, bytes], target: str = "Windows",
                   expected_version: str | None = None) -> dict:
    """Seal bounded input bytes once; extract only the returned verified bytes."""
    try:
        with safe_path(path).open("rb") as stream:
            raw = stream.read(MAX_ARCHIVE + 1)
        need(len(raw) <= MAX_ARCHIVE, "archive too large")
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            infos = archive.infolist()
            need(0 < len(infos) <= MAX_FILES, "archive file count exceeded")
            names = [i.filename for i in infos]
            check_names(names)
            total = 0
            for info in infos:
                need(info.orig_filename == info.filename and not info.is_dir(), "invalid ZIP name")
                mode = stat.S_IFMT(info.external_attr >> 16)
                need(mode in (0, stat.S_IFREG) and not info.external_attr & 0x410
                     and not info.flag_bits & 1 and info.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED), "unsupported ZIP entry")
                total += info.file_size
                need(0 <= info.file_size <= MAX_MEMBER and total <= MAX_TOTAL, "ZIP expansion limit")
            need("manifest.json" in names and archive.getinfo("manifest.json").file_size <= MAX_MANIFEST, "manifest missing/oversized")
            manifest = strict_json(archive.read("manifest.json"))
            verify_manifest(manifest, trusted_keys=trusted_keys, target=target, expected_version=expected_version)
            need(set(names) == set(manifest["files"]) | {"manifest.json"}, "undeclared/missing ZIP member")
            members = {}
            for name, row in manifest["files"].items():
                need(archive.getinfo(name).file_size == row["size"], "ZIP length disagrees with ledger")
                with archive.open(name) as stream:
                    data = stream.read(row["size"] + 1)
                need(len(data) == row["size"], "ZIP expanded length mismatch")
                members[name] = data
            verify_contents(manifest, members)
            return {"manifest": manifest, "manifest_sha256": digest_bytes(canonical(manifest)),
                    "archive_sha256": digest_bytes(raw), "members": members}
    except (zipfile.BadZipFile, EOFError, OSError, RuntimeError) as exc:
        raise PackageError("package unreadable") from exc


def __getattr__(name: str):
    if name == "ConsumerInstall":
        from .consumer_install import ConsumerInstall
        return ConsumerInstall
    raise AttributeError(name)
