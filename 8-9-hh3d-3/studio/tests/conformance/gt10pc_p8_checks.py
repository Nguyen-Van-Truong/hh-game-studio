"""P8 offline producer and raw re-verifier. Never launches a native process."""
from __future__ import annotations

from contextlib import contextmanager
import io
import os
from pathlib import Path
import socket
import tempfile
from unittest.mock import patch
import zipfile

from studio.package.consumer_support import install_checked
from studio.package.release_contract import (
    PackageError, canonical, digest_bytes, digest_file, file_ledger,
    need, safe_path, strict_json, verify_package,
)
from studio.package.trust import load_trust

CASES = ("missing-dependency", "missing-template", "addon-version", "archive", "closure")
MARKERS = {
    "missing-dependency": "missing dependency godot; provide the exact local",
    "missing-template": "missing dependency export_templates; provide the exact local",
    "addon-version": "addon version mismatch (expected ",
    "archive": "package unreadable",
    "closure": "package closure hash mismatch",
}
BAD_ADDON = b'[plugin]\nversion="99.0.0"\n'


@contextmanager
def offline_guard():
    """Block network attempts in this sequential host-only lane, record calls."""
    calls = []
    def denied(*_args, **_kwargs):
        calls.append("blocked")
        raise RuntimeError("P8 network attempt forbidden")
    with patch.object(socket.socket, "connect", denied), \
         patch.object(socket.socket, "connect_ex", denied), \
         patch.object(socket.socket, "sendto", denied), \
         patch.object(socket, "getaddrinfo", denied), \
         patch.object(socket, "create_connection", denied):
        yield calls


def damaged(source: bytes, case: str) -> bytes:
    if case == "archive":
        return source[:-19]
    if case != "closure":
        return source
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(source)) as original, zipfile.ZipFile(output, "w") as archive:
        for info in original.infolist():
            value = original.read(info.filename)
            if info.filename == "docs/NOTICE.txt":
                need(value, "P8 NOTICE payload required")
                value = bytes((value[0] ^ 1,)) + value[1:]
            archive.writestr(info, value)
    return output.getvalue()


def exercise(artifact: Path, case: str, root: Path, *, keys: dict, target: str) -> dict:
    """Route failures through the intake/install API, asserting zero effects."""
    need(case in CASES and not root.exists(), "P8 fresh case required")
    root.mkdir()
    candidate = root / "input.hhpkg"
    candidate.write_bytes(damaged(artifact.read_bytes(), case))
    addon = None
    if case == "addon-version":
        addon = root / "existing-addon"
        addon.mkdir()
        (addon / "plugin.cfg").write_bytes(BAD_ADDON)
    required = (("export_templates",) if case == "missing-template" else
                () if case == "addon-version" else ("godot",))
    output = root / "install"
    reason = None
    with offline_guard() as network:
        try:
            install_checked(candidate, output, trusted_keys=keys, target=target,
                            command_id="p8." + case, expected_state_sha256="ABSENT",
                            required=required, paths={}, addon=addon)
        except PackageError as exc:
            reason = str(exc)
    need(reason is not None and MARKERS[case] in reason, "P8 wrong or absent rejection:" + case)
    if case in CASES[:3]:
        need("latest/network auto-fetch is disabled" in reason, "P8 missing repair/no-fetch guidance")
    need(not network and not output.exists(), "P8 network or install effect")
    need(addon is None or (addon / "plugin.cfg").read_bytes() == BAD_ADDON, "P8 addon changed")
    need(candidate.read_bytes() == damaged(artifact.read_bytes(), case), "P8 artifact changed")
    result = {"case": case, "reason": reason, "input_sha256": digest_file(candidate),
              "install_absent": True, "network_attempts": len(network),
              "required": list(required), "addon_unchanged": addon is not None}
    (root / "observation.json").write_bytes(canonical(result) + b"\n")
    return result


def run_p8(output: Path, *, artifact: Path, trust: Path, trust_sha256: str,
           target: str = "Windows") -> dict:
    keys = load_trust(trust, expected_sha256=trust_sha256)
    package = verify_package(artifact, trusted_keys=keys, target=target)
    output = safe_path(output)
    need(not output.exists(), "P8 output exists")
    output.mkdir(parents=True)
    rows = [exercise(artifact, case, output / case, keys=keys, target=target) for case in CASES]
    evidence = {p.relative_to(output).as_posix(): digest_file(p)
                for p in output.rglob("*") if p.is_file()}
    report = {"schema": "hh-gt10pc-p8-1", "authority": 0, "acceptance": False,
              "target": target, "artifact_sha256": package["archive_sha256"],
              "manifest_sha256": package["manifest_sha256"],
              "source_closure_sha256": package["manifest"]["source_closure_sha256"],
              "trust_sha256": trust_sha256, "rows": rows, "evidence": evidence}
    (output / "p8.json").write_bytes(canonical(report) + b"\n")
    return verify_p8(output, artifact=artifact, trust=trust, trust_sha256=trust_sha256, target=target)


def verify_p8(output: Path, *, artifact: Path, trust: Path, trust_sha256: str,
              target: str = "Windows") -> dict:
    keys = load_trust(trust, expected_sha256=trust_sha256)
    package = verify_package(artifact, trusted_keys=keys, target=target)
    output = safe_path(output)
    report = strict_json((output / "p8.json").read_bytes())
    need(report.get("schema") == "hh-gt10pc-p8-1" and report.get("authority") == 0
         and report.get("acceptance") is False and report.get("target") == target, "P8 schema")
    need(report.get("artifact_sha256") == package["archive_sha256"]
         and report.get("manifest_sha256") == package["manifest_sha256"]
         and report.get("source_closure_sha256") == package["manifest"]["source_closure_sha256"]
         and report.get("trust_sha256") == trust_sha256, "P8 artifact/trust binding")
    expected_names = {case + "/" + name for case in CASES for name in ("input.hhpkg", "observation.json")}
    expected_names.add("addon-version/existing-addon/plugin.cfg")
    need(set(report.get("evidence", {})) == expected_names, "P8 evidence set")
    for name in expected_names:
        need(digest_file(output / name) == report["evidence"][name], "P8 evidence changed:" + name)
    need(isinstance(report.get("rows"), list) and len(report["rows"]) == len(CASES), "P8 row count")
    # Reproduce each exact fail-before-install path. Equal caller-written flags
    # alone cannot establish ordering, repair text, or rejection semantics.
    with tempfile.TemporaryDirectory(prefix="hh-p8-verify-") as temporary:
        for case, row in zip(CASES, report["rows"]):
            replay = exercise(artifact, case, Path(temporary) / case, keys=keys, target=target)
            observed = strict_json((output / case / "observation.json").read_bytes())
            need(row == observed == replay and not (output / case / "install").exists(),
                 "P8 observation differs:" + case)
            need((output / case / "input.hhpkg").read_bytes() == damaged(artifact.read_bytes(), case),
                 "P8 attack bytes differ")
    return {"status": "P8_HOST_VERIFIED", "authority": 0, "acceptance": False,
            "cases": list(CASES), "artifact_sha256": package["archive_sha256"],
            "source_closure_sha256": package["manifest"]["source_closure_sha256"]}
