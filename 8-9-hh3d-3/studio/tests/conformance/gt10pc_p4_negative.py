"""P4 reject-only schema and untrusted-rollback proof. No installer changes.

The same module is imported by the Windows probe now and by the Linux worker
later. It uses the stdlib plus the package modules that worker already imports.
Signing material is a caller-supplied signer; this file never loads a key.

Each refusal case runs in its own child interpreter. The parent writes
receipts/<case>.json from that child's pid, exit, and stdout.
"""
from __future__ import annotations

import os
import stat
import subprocess
import sys
import zipfile
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from studio.package.consumer_install import ConsumerInstall
from studio.package.release_contract import (
    DOMAIN, SCHEMA, canonical, digest_bytes, digest_file, PackageError, safe_path, strict_json,
    verify_manifest, verify_package,
)

SCHEMA_COMMAND_ID = "p4.negative.incompatible-schema"
ROLLBACK_COMMAND_ID = "p4.negative.untrusted-rollback"
BAD_SCHEMA = "hh-studio-package-incompatible"
ABSENT_KEY_ID = "hh-untrusted-absent"
SCHEMA_ERROR = "unsupported package schema"
ROLLBACK_ERROR = "untrusted signing key"
RECEIPT_SCHEMA = "hh-gt10pc-p4-negative-receipt-1"
CASE_EXIT_CODE = {"incompatible-schema": 0, "untrusted-rollback": 0}
CASE_ERROR = {"incompatible-schema": SCHEMA_ERROR, "untrusted-rollback": ROLLBACK_ERROR}
CASE_TIMEOUT_SECONDS = 120
RECEIPT_KEYS = {
    "schema", "case", "pid", "exit_code", "started_at", "ended_at",
    "stdout_sha256", "stdout_file", "refused", "error_code",
}


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


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _child_base(install_root: Path, open_consumer: Callable[[], ConsumerInstall],
                out_dir: Path) -> dict[str, object]:
    consumer = open_consumer()
    if safe_path(install_root) != consumer.root:
        _fail("ROOT")
    if not isinstance(consumer.target, str) or not consumer.trusted_keys:
        _fail("TRUST")
    keys = {}
    for key_id, value in consumer.trusted_keys.items():
        if not isinstance(key_id, str) or not isinstance(value, bytes) or len(value) != 32:
            _fail("TRUST")
        keys[key_id] = value.hex()
    return {"install_root": str(consumer.root), "target": consumer.target,
            "trusted_keys": keys, "out_dir": str(safe_path(out_dir))}


def _trusted_keys(request: dict) -> dict[str, bytes]:
    raw = request.get("trusted_keys")
    if not isinstance(raw, dict) or not raw:
        _fail("TRUST")
    keys = {}
    for key_id, hex_key in raw.items():
        if not isinstance(key_id, str) or not isinstance(hex_key, str) or len(hex_key) != 64:
            _fail("TRUST")
        try:
            value = bytes.fromhex(hex_key)
        except ValueError:
            _fail("TRUST")
        if len(value) != 32:
            _fail("TRUST")
        keys[key_id] = value
    return keys


def _request_path(request: dict, name: str) -> Path:
    value = request.get(name)
    if not isinstance(value, str) or not value:
        _fail("PATH")
    return Path(value)


def _execute_case(request: dict) -> str:
    """Run one refusal inside the child. Return the observed error text."""
    case = request.get("case")
    if case not in CASE_EXIT_CODE or not isinstance(request, dict):
        _fail("CASE")
    install_root = _request_path(request, "install_root")
    out_dir = _request_path(request, "out_dir")
    target = request.get("target")
    if not isinstance(target, str):
        _fail("TARGET")
    keys = _trusted_keys(request)

    def open_consumer() -> ConsumerInstall:
        return ConsumerInstall(install_root, trusted_keys=keys, target=target)

    if case == "incompatible-schema":
        package = _request_path(request, "package")

        def reject_schema() -> None:
            consumer = open_consumer()
            consumer.install(package, command_id=SCHEMA_COMMAND_ID,
                             expected_state_sha256=consumer.snapshot()["state_sha256"])

        _refuse(install_root, out_dir / "incompatible-schema", SCHEMA_COMMAND_ID,
                SCHEMA_ERROR, "SCHEMA", reject_schema)
        return SCHEMA_ERROR
    destination = request.get("destination")
    if not isinstance(destination, str) or not destination:
        _fail("DESTINATION")

    def reject_rollback() -> None:
        consumer = open_consumer()
        consumer.rollback(command_id=ROLLBACK_COMMAND_ID, destination=destination,
                          expected_state_sha256=consumer.snapshot()["state_sha256"])

    _refuse(install_root, out_dir / "untrusted-rollback", ROLLBACK_COMMAND_ID,
            ROLLBACK_ERROR, "ROLLBACK", reject_rollback)
    return ROLLBACK_ERROR


def _spawn_case(case: str, request: dict, out_dir: Path) -> None:
    """Run one refusal child and write receipts/<case>.json from the parent."""
    if case not in CASE_EXIT_CODE:
        _fail("CASE")
    receipt_dir = out_dir / "receipts"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = receipt_dir / (case + ".stdout")
    stderr_path = receipt_dir / (case + ".stderr")
    receipt_path = receipt_dir / (case + ".json")
    if stdout_path.exists() or stderr_path.exists() or receipt_path.exists():
        _fail("RECEIPT")
    env = os.environ.copy()
    repo = str(_repo_root())
    prior = env.get("PYTHONPATH")
    env["PYTHONPATH"] = repo if not prior else repo + os.pathsep + prior
    command = [sys.executable, "-B", "-m", "studio.tests.conformance.gt10pc_p4_negative"]
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    started_at = datetime.now(timezone.utc).isoformat()
    timed_out = False
    try:
        with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
            proc = subprocess.Popen(command, cwd=repo, env=env, stdin=subprocess.PIPE,
                                    stdout=stdout, stderr=stderr, creationflags=flags)
            try:
                proc.communicate(canonical(request), timeout=CASE_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                timed_out = True
                proc.kill()
                proc.wait(timeout=30)
    except OSError:
        _fail("CASE_CHILD")
    ended_at = datetime.now(timezone.utc).isoformat()
    stdout_bytes = stdout_path.read_bytes()
    expected_stdout = (CASE_ERROR[case] + "\n").encode("ascii")
    code = proc.returncode if type(proc.returncode) is int else -1
    pid = proc.pid if type(proc.pid) is int else 0
    matched = stdout_bytes == expected_stdout
    refused = (not timed_out) and code == CASE_EXIT_CODE[case] and matched and pid > 0
    receipt = {"schema": RECEIPT_SCHEMA, "case": case, "pid": pid, "exit_code": code,
               "started_at": started_at, "ended_at": ended_at,
               "stdout_sha256": digest_file(stdout_path), "stdout_file": "receipts/" + stdout_path.name,
               "refused": refused, "error_code": CASE_ERROR[case] if matched else ""}
    _write_new(receipt_path, canonical(receipt) + b"\n")
    if timed_out or not refused:
        tail = stderr_path.read_bytes()[-1000:] if stderr_path.is_file() else b""
        text = "P4_NEG_" + ("CASE_TIMEOUT" if timed_out else "CASE_CHILD")
        text += " exit=" + str(code)
        if tail:
            text += "\n" + tail.decode("utf-8", errors="replace")
        raise ValueError(text)


def run_negative(install_root: Path, open_consumer: Callable[[], ConsumerInstall],
                 artifacts: dict[str, dict[str, str]], out_dir: Path) -> dict[str, str]:
    """Refuse one incompatible install and one untrusted rollback. No Play.

    Each refusal runs in its own child Python process. A completed refusal
    child exits with that case's contract code (0). The parent writes one
    receipt per case under receipts/.
    """
    package = Path(artifacts["incompatible-schema.hhpkg"]["path"])
    manifest_path = Path(artifacts["untrusted-manifest"]["path"])
    manifest_bytes = manifest_path.read_bytes()
    if digest_bytes(manifest_bytes) != artifacts["untrusted-manifest"]["sha256"]:
        _fail("MANIFEST_HASH")
    base = _child_base(install_root, open_consumer, out_dir)
    _spawn_case("incompatible-schema", {**base, "case": "incompatible-schema",
                                       "package": str(safe_path(package))}, out_dir)
    state_sha256 = _arm_untrusted_previous(install_root, manifest_bytes, digest_bytes(manifest_bytes))
    _write_new(out_dir / "untrusted-rollback" / "setup.json", canonical({
        "previous": digest_bytes(manifest_bytes), "state_sha256": state_sha256}) + b"\n")
    _spawn_case("untrusted-rollback", {**base, "case": "untrusted-rollback",
                                       "destination": digest_bytes(manifest_bytes)}, out_dir)
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


def _relative_stdout(out_dir: Path, relative: object) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        _fail("RECEIPT")
    parts = Path(relative).parts
    if not parts or any(part in ("", ".", "..") for part in parts):
        _fail("RECEIPT")
    try:
        return safe_path(out_dir.joinpath(*parts))
    except ValueError:
        _fail("RECEIPT")


def _bind_receipt(out_dir: Path, case: str, refusal: str) -> None:
    try:
        path = safe_path(out_dir / "receipts" / (case + ".json"))
    except ValueError:
        _fail("RECEIPT")
    receipt = _json_object(_read_exact(path, "RECEIPT"), "RECEIPT")
    if (set(receipt) != RECEIPT_KEYS or receipt.get("schema") != RECEIPT_SCHEMA
            or receipt.get("case") != case or receipt.get("refused") is not True):
        _fail("RECEIPT")
    pid, exit_code = receipt.get("pid"), receipt.get("exit_code")
    if type(pid) is not int or pid <= 0 or type(exit_code) is not int or exit_code != CASE_EXIT_CODE[case]:
        _fail("RECEIPT")
    if receipt.get("error_code") != refusal:
        _fail("RECEIPT")
    started, ended = receipt.get("started_at"), receipt.get("ended_at")
    if not isinstance(started, str) or not started or not isinstance(ended, str) or ended < started:
        _fail("RECEIPT")
    stdout_path = _relative_stdout(out_dir, receipt.get("stdout_file"))
    if not stdout_path.is_file():
        _fail("RECEIPT")
    try:
        if (stdout_path.read_bytes() != (refusal + "\n").encode("ascii")
                or digest_file(stdout_path) != receipt.get("stdout_sha256")):
            _fail("RECEIPT")
    except (OSError, ValueError):
        _fail("RECEIPT")


def _require_receipts(out_dir: Path, refusals: dict[str, str], *,
                      legacy_ok_without_receipts: bool) -> None:
    """Require one receipt per case. Skip only when historical raw has no directory."""
    receipt_dir = out_dir / "receipts"
    if not receipt_dir.exists():
        if legacy_ok_without_receipts is True:
            return
        # Raw produced before per-case receipts (for example c3h); a new packaging run writes them.
        _fail("RECEIPTS_ABSENT")
    if not receipt_dir.is_dir() or set(refusals) != set(CASE_EXIT_CODE):
        _fail("RECEIPT")
    names = sorted(path.name for path in receipt_dir.iterdir() if path.is_file() and path.suffix == ".json")
    if names != sorted(case + ".json" for case in CASE_EXIT_CODE):
        _fail("RECEIPT")
    for case, refusal in refusals.items():
        _bind_receipt(out_dir, case, refusal)


def verify_negative(out_dir: Path, trust: dict[str, bytes], *,
                    legacy_ok_without_receipts: bool = False) -> dict:
    """Recompute both refusals from raw files. Ignore any producer rejected flag.

    New runs require exactly one host receipt per case at receipts/<case>.json
    (pid > 0, the case contract exit code, stdout_sha256 matching the saved
    stdout file, and error_code equal to the refusal recomputed here). Pass
    legacy_ok_without_receipts=True only to verify historical raw that has no
    receipts directory. No caller passes that keyword by default. When the
    directory is absent and the keyword is true, receipt binding is skipped.
    A receipts directory that exists is always bound, including when the
    keyword is true.
    """
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
    _require_receipts(out_dir, {
        "incompatible-schema": SCHEMA_ERROR,
        "untrusted-rollback": ROLLBACK_ERROR,
    }, legacy_ok_without_receipts=legacy_ok_without_receipts)
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


def main() -> int:
    """Child entry: one refusal request on stdin, the refusal text on stdout."""
    raw = sys.stdin.buffer.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        return 2
    try:
        request = strict_json(raw)
    except PackageError:
        return 2
    if not isinstance(request, dict):
        return 2
    try:
        observed = _execute_case(request)
    except ValueError as exc:
        sys.stderr.write(str(exc) + "\n")
        return 1
    sys.stdout.buffer.write(observed.encode("ascii") + b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
