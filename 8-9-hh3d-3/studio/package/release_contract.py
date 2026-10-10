"""Deterministic local package contract used by the GT-10-PC matrix.

This is a local, offline release lane.  The pinned test key deliberately lives
in this verifier (outside generated packages) and is not a public distribution
signature.  Full public-channel key rotation/revocation remains a GT-10 gap.
The implementation nevertheless keeps the important release properties:
verify-before-extract, safe paths, immutable version directories, atomic state,
command-id deduplication and source/save preservation.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
import tempfile
import time
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

SCHEMA = "hh-studio-package-0.1"
TEST_TRUST_KEY_ID = "hh-local-test-key-v1"
_TEST_TRUST_KEY = b"HH-STUDIO-GT10-PC-LOCAL-TEST-KEY-V1"
MAX_MEMBER = 16 * 1024 * 1024
FORBIDDEN_PARTS = ("zdoc/reviews", ".local", ".godot", "__pycache__")


class PackageError(ValueError):
    """A package was rejected before it could mutate a consumer."""


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _signature(body: dict[str, Any]) -> str:
    return hmac.new(_TEST_TRUST_KEY, canonical(body), hashlib.sha256).hexdigest()


def _safe_member(name: str) -> None:
    if not name or name.startswith("/") or "\\" in name:
        raise PackageError("unsafe package member")
    p = PurePosixPath(name)
    if any(part in ("", ".", "..") for part in p.parts):
        raise PackageError("path traversal in package member")
    lowered = name.lower()
    if any(x in lowered for x in ("zdoc/reviews", ".local/", ".godot/", "secret", "token")):
        raise PackageError("forbidden package member")


def _payload_digest(files: dict[str, bytes]) -> str:
    rows = [{"path": name, "sha256": digest_bytes(data), "size": len(data)} for name, data in sorted(files.items())]
    return digest_bytes(canonical(rows))


def _source_files(source_root: Path) -> dict[str, bytes]:
    """Collect the immutable runtime closure without generated evidence/cache."""
    wanted = ("host", "protocol", "contracts", "build/bootstrap", "godot-addon", "blender-addon")
    files: dict[str, bytes] = {}
    # Walk only closure roots.  The workspace contains multi-gigabyte evidence
    # caches; a broad rglob makes a release build non-deterministically slow.
    roots = [source_root / name for name in wanted if (source_root / name).is_dir()]
    lock = source_root / "toolchain.lock.json"
    if lock.exists():
        roots.append(lock)
    for base in roots:
        if base.is_file():
            candidates = [base]
        else:
            candidates = []
            for directory, dirnames, filenames in os.walk(base):
                dirnames[:] = [d for d in dirnames if d not in {".local", ".godot", "__pycache__", ".git"}]
                candidates.extend(Path(directory) / name for name in filenames)
        for item in candidates:
            if not item.is_file():
                continue
            rel = item.relative_to(source_root).as_posix()
            if any(part in rel for part in FORBIDDEN_PARTS):
                continue
            if item.suffix.lower() not in {".py", ".json", ".md", ".toml", ".gd", ".txt", ".lock"}:
                continue
            files["payload/" + rel] = item.read_bytes()
    if not files:
        raise PackageError("empty runtime closure")
    return files


def build_package(source_root: Path, output: Path, *, version: str = "0.1.0", target: str = "Windows",
                  package_id: str | None = None) -> dict[str, Any]:
    """Create a reproducible .hhpkg and return its manifest/receipt."""
    source_root = Path(source_root).resolve()
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    files = _source_files(source_root)
    payload_hash = _payload_digest(files)
    lock = source_root / "toolchain.lock.json"
    lock_hash = digest_file(lock) if lock.exists() else "missing"
    package_id = package_id or "hh-studio-" + payload_hash[:16]
    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "package_id": package_id,
        "version": version,
        "target": target,
        "supported_targets": ["Windows", "Linux", "Linux-headless"],
        "android": "DEFERRED_NO_DEVICE",
        "artifact_sha256": payload_hash,
        "source_closure_sha256": payload_hash,
        "protocol_schema_digest": digest_bytes(b"hh-studio-protocol-schema-0.1"),
        "toolchain_lock_sha256": lock_hash,
        "trust_key_id": TEST_TRUST_KEY_ID,
        "security_floor": "local-test-floor-1",
        "rollback_compatibility": {"minimum_schema": SCHEMA, "same_major": True},
        "monetization": "OFF",
        "failpoint": "DISABLED",
        "known_limits": ["local test trust key; no public-channel revocation/expiry", "Android deferred"],
        "files": {},
    }
    metadata = {
        "NOTICE.txt": "HH Studio local package. Original project files retain their source licenses.\n",
        "SBOM.json": json.dumps({"format": "hh-sbom-0.1", "package_id": package_id, "files": sorted(files)}, sort_keys=True) + "\n",
        "compatibility.json": json.dumps({"schema": SCHEMA, "targets": manifest["supported_targets"]}, sort_keys=True) + "\n",
        "runbook.md": "# HH Studio local package\nVerify before unpack; preserve source/save; rollback only to last-good.\n",
        "help.md": "Use the pinned local test key and the consumer receipt to diagnose install or rollback.\n",
    }
    all_files = {**files, **{"docs/" + k: v.encode("utf-8") for k, v in metadata.items()}}
    manifest["files"] = {name: {"sha256": digest_bytes(data), "size": len(data)} for name, data in sorted(all_files.items())}
    body = dict(manifest)
    manifest["signature"] = _signature(body)
    tmp = output.with_suffix(output.suffix + ".tmp")
    if tmp.exists():
        tmp.unlink()
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        info = zipfile.ZipInfo("manifest.json", (2020, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, canonical(manifest) + b"\n")
        for name, data in sorted(all_files.items()):
            info = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    os.replace(tmp, output)
    return {"manifest": manifest, "artifact_path": str(output), "archive_sha256": digest_file(output)}


def verify_package(path: Path, *, target: str = "Windows", expected_version: str | None = None) -> dict[str, Any]:
    """Verify every trust/closure condition before any extraction."""
    path = Path(path)
    try:
        with zipfile.ZipFile(path, "r") as archive:
            infos = archive.infolist()
            names = [i.filename for i in infos]
            if len(names) != len(set(names)):
                raise PackageError("duplicate package member")
            for info in infos:
                _safe_member(info.filename)
                if info.file_size > MAX_MEMBER:
                    raise PackageError("package member too large")
            if "manifest.json" not in names:
                raise PackageError("manifest missing")
            manifest = json.loads(archive.read("manifest.json"))
            signature = manifest.pop("signature", None)
            if manifest.get("schema") != SCHEMA:
                raise PackageError("unsupported package schema")
            if manifest.get("trust_key_id") != TEST_TRUST_KEY_ID or not hmac.compare_digest(signature or "", _signature(manifest)):
                raise PackageError("package trust verification failed")
            if target not in manifest.get("supported_targets", []) or manifest.get("target") != target:
                raise PackageError("package target rejected")
            if expected_version is not None and manifest.get("version") != expected_version:
                raise PackageError("package version rejected")
            if manifest.get("monetization") != "OFF" or manifest.get("failpoint") != "DISABLED":
                raise PackageError("unsafe release flags")
            rows = manifest.get("files")
            if not isinstance(rows, dict) or "manifest.json" in rows:
                raise PackageError("invalid file ledger")
            for name, row in rows.items():
                if name not in names:
                    raise PackageError("ledger member missing")
                data = archive.read(name)
                if len(data) != row.get("size") or digest_bytes(data) != row.get("sha256"):
                    raise PackageError("package closure hash mismatch")
            members = {name: archive.read(name) for name in rows}
            if manifest.get("artifact_sha256") != _payload_digest({k: v for k, v in members.items() if k.startswith("payload/")}):
                raise PackageError("source closure mismatch")
            return {"manifest": {**manifest, "signature": signature}, "archive_sha256": digest_file(path), "members": members}
    except (zipfile.BadZipFile, EOFError, OSError, json.JSONDecodeError) as exc:
        raise PackageError("package unreadable") from exc


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_bytes(canonical(value) + b"\n")
    with temp.open("r+b") as fh:
        os.fsync(fh.fileno())
    os.replace(temp, path)


class ConsumerInstall:
    """A private consumer fixture with atomic pointer and journal receipts."""

    def __init__(self, root: Path, *, project_id: str = "fixture-a"):
        self.root = Path(root).resolve()
        self.project_id = project_id
        self.versions = self.root / "versions"
        self.state_path = self.root / ".active.json"
        self.journal_path = self.root / ".journal.json"
        self.source = self.root / "game" / "source.dat"
        self.save = self.root / "game" / "save.dat"
        self.profile = self.root / "project-profile.json"
        self.versions.mkdir(parents=True, exist_ok=True)
        self.source.parent.mkdir(parents=True, exist_ok=True)
        if not self.source.exists(): self.source.write_text("fixture-source-v1", encoding="utf-8")
        if not self.save.exists(): self.save.write_text("fixture-save-v1", encoding="utf-8")
        if not self.state_path.exists(): _atomic_json(self.state_path, {"active": None, "previous": None, "schema": SCHEMA})
        if not self.journal_path.exists(): _atomic_json(self.journal_path, {"commands": {}})

    def _state(self) -> dict[str, Any]:
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def _journal(self) -> dict[str, Any]:
        return json.loads(self.journal_path.read_text(encoding="utf-8"))

    def _command(self, command_id: str, action: str, digest: str) -> dict[str, Any] | None:
        journal = self._journal(); existing = journal["commands"].get(command_id)
        if existing:
            if existing["digest"] != digest:
                raise PackageError("command_id conflict")
            return existing["receipt"]
        return None

    def _record(self, command_id: str, digest: str, receipt: dict[str, Any]) -> dict[str, Any]:
        journal = self._journal(); journal["commands"][command_id] = {"digest": digest, "receipt": receipt, "recorded_at": time.time()}; _atomic_json(self.journal_path, journal); return receipt

    def install(self, package_path: Path, *, command_id: str, target: str = "Windows") -> dict[str, Any]:
        verified = verify_package(package_path, target=target); manifest = verified["manifest"]; pid = manifest["package_id"]
        digest = verified["archive_sha256"]
        prior = self._command(command_id, "install", digest)
        if prior: return prior
        stage = self.versions / (pid + ".stage")
        final = self.versions / pid
        if stage.exists(): shutil.rmtree(stage)
        stage.mkdir(parents=True)
        for name, data in verified["members"].items():
            dest = stage / name
            dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(data)
        readback = {name: digest_bytes((stage / name).read_bytes()) for name in verified["members"]}
        if any(readback[name] != row["sha256"] for name, row in manifest["files"].items()):
            shutil.rmtree(stage, ignore_errors=True); raise PackageError("staged readback mismatch")
        if final.exists(): shutil.rmtree(final)
        os.replace(stage, final)
        old = self._state().get("active")
        state = {"active": pid, "previous": old, "schema": SCHEMA, "version": manifest["version"], "artifact_sha256": digest}
        _atomic_json(self.state_path, state)
        receipt = {"status": "COMMITTED", "command_id": command_id, "action": "install", "package_id": pid, "artifact_sha256": digest, "active": pid}
        return self._record(command_id, digest, receipt)

    def rollback(self, *, command_id: str) -> dict[str, Any]:
        state = self._state(); old = state.get("active"); previous = state.get("previous")
        if not previous or not (self.versions / previous).is_dir(): raise PackageError("no trusted compatible rollback")
        digest = digest_bytes(canonical({"active": old, "previous": previous})); prior = self._command(command_id, "rollback", digest)
        if prior: return prior
        _atomic_json(self.state_path, {**state, "active": previous, "previous": old})
        return self._record(command_id, digest, {"status": "COMMITTED", "command_id": command_id, "action": "rollback", "active": previous, "previous": old})

    def uninstall(self, *, command_id: str) -> dict[str, Any]:
        state = self._state(); digest = digest_bytes(canonical(state)); prior = self._command(command_id, "uninstall", digest)
        if prior: return prior
        for child in self.versions.iterdir():
            if child.is_dir(): shutil.rmtree(child)
        _atomic_json(self.state_path, {"active": None, "previous": None, "schema": SCHEMA})
        return self._record(command_id, digest, {"status": "COMMITTED", "command_id": command_id, "action": "uninstall", "active": None})

    def set_profile(self, value: str = "hh-godot-gameplay-source-1") -> None:
        _atomic_json(self.profile, {"project_id": self.project_id, "profile": value})

    def smoke(self) -> dict[str, Any]:
        state = self._state(); active = state.get("active")
        if not active or not (self.versions / active).is_dir(): raise PackageError("consumer has no active package")
        return {"active": active, "schema": state["schema"], "source_sha256": digest_file(self.source), "save_sha256": digest_file(self.save)}
