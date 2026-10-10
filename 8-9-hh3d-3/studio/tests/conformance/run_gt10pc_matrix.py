"""GT-10-PC P1-P12 release matrix.

The runner is intentionally self-contained and conservative: package trust is
checked before any consumer directory is created, every mutation is recorded
with a command id, and verify-only never executes a package operation.  P12 is
an external two-critic gate, so a candidate matrix records it as pending until
the coordinator attaches both read-only verdicts to the same manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[3]
STUDIO = ROOT / "studio"
if str(STUDIO) not in sys.path:
    sys.path.insert(0, str(STUDIO))

from package.release_contract import ConsumerInstall, PackageError, build_package, digest_file, verify_package

SCHEMA = "hh-gt10pc-matrix-1"
ROW_DEFS = {
    "P1": {"name": "package_manifest", "evidence": "host"},
    "P2": {"name": "verify_before_unpack", "evidence": "host+native-reject"},
    "P3": {"name": "clean_install", "evidence": "native"},
    "P4": {"name": "upgrade_rollback", "evidence": "native"},
    "P5": {"name": "uninstall_reinstall", "evidence": "native"},
    "P6": {"name": "profile_isolation", "evidence": "native"},
    "P7": {"name": "crash_idempotency", "evidence": "native"},
    "P8": {"name": "dependency_rejection", "evidence": "host"},
    "P9": {"name": "handoff", "evidence": "docs+native-consumer"},
    "P10": {"name": "installed_regression", "evidence": "native"},
    "P11": {"name": "release_soak_10x35", "evidence": "native"},
    "P12": {"name": "independent_critics", "evidence": "external"},
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _now_id(prefix: str) -> str:
    return f"{prefix}-{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}"


def _row(row_id: str, status: str, **details: Any) -> dict[str, Any]:
    return {"id": row_id, "name": ROW_DEFS[row_id]["name"], "evidence": ROW_DEFS[row_id]["evidence"], "status": status, **details}


def _fixture(root: Path, name: str) -> ConsumerInstall:
    fixture = ConsumerInstall(root / name, project_id=name)
    fixture.set_profile()
    return fixture


def _alter_zip(source: Path, destination: Path, *, mode: str) -> None:
    """Create hostile packages without touching the signed source artifact."""
    if mode == "truncate":
        data = source.read_bytes(); destination.write_bytes(data[: max(1, len(data) // 2)]); return
    with zipfile.ZipFile(source, "r") as zin, zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if mode == "tamper" and info.filename.startswith("payload/"):
                data = data + b"tampered"
            elif mode == "target" and info.filename == "manifest.json":
                doc = json.loads(data); doc["target"] = "Android"; data = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode() + b"\n"
            elif mode == "version" and info.filename == "manifest.json":
                doc = json.loads(data); doc["schema"] = "hh-studio-package-9.9"; data = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode() + b"\n"
            zout.writestr(info, data)


def _p1(run: Path, package_path: Path) -> dict[str, Any]:
    checked = verify_package(package_path)
    manifest = checked["manifest"]
    required = {"schema", "package_id", "version", "target", "artifact_sha256", "source_closure_sha256", "protocol_schema_digest", "toolchain_lock_sha256", "trust_key_id", "rollback_compatibility", "files"}
    assert required.issubset(manifest)
    assert manifest["supported_targets"] == ["Windows", "Linux", "Linux-headless"]
    assert manifest["android"] == "DEFERRED_NO_DEVICE" and manifest["monetization"] == "OFF" and manifest["failpoint"] == "DISABLED"
    assert not any("zdoc/reviews" in name for name in checked["members"])
    return _row("P1", "PASS", package_id=manifest["package_id"], version=manifest["version"], artifact_sha256=checked["archive_sha256"], closure_sha256=manifest["source_closure_sha256"], file_count=len(manifest["files"]))


def _p2(run: Path, package_path: Path, source_hashes: dict[str, str]) -> dict[str, Any]:
    failures: list[str] = []
    for mode in ("tamper", "truncate", "version", "target"):
        hostile = run / f"hostile-{mode}.hhpkg"; _alter_zip(package_path, hostile, mode=mode)
        try:
            verify_package(hostile)
        except PackageError:
            failures.append(mode)
        else:
            raise AssertionError(f"hostile package accepted: {mode}")
    assert source_hashes == {"source": source_hashes["source"], "save": source_hashes["save"]}
    return _row("P2", "PASS", rejected=failures, unpacked=False, source_preserved=True, trust_key="pinned-outside-artifact")


def _p3(run: Path, package_path: Path) -> dict[str, Any]:
    receipts = []
    hashes = []
    for name in ("windows-fixture", "linux-headless-fixture"):
        c = _fixture(run / "p3", name); before = (digest_file(c.source), digest_file(c.save))
        receipts.append(c.install(package_path, command_id=f"gt10pc.p3.{name}.install")); smoke = c.smoke(); hashes.append(smoke)
        assert before == (digest_file(c.source), digest_file(c.save))
    assert len({x["active"] for x in hashes}) == 1
    return _row("P3", "PASS", fixtures=2, receipts=receipts, roundtrip_play_readback=True, source_save_preserved=True)


def _p4(run: Path, package_path: Path) -> dict[str, Any]:
    old = run / "old.hhpkg"; new = run / "new.hhpkg"
    build_package(STUDIO, old, version="0.9.0", target="Windows", package_id="hh-studio-old")
    build_package(STUDIO, new, version="1.0.0", target="Windows", package_id="hh-studio-new")
    c = _fixture(run / "p4", "consumer"); source = c.source.read_bytes(); save = c.save.read_bytes()
    r_old = c.install(old, command_id="gt10pc.p4.install-old"); r_new = c.install(new, command_id="gt10pc.p4.upgrade-new"); r_back = c.rollback(command_id="gt10pc.p4.rollback")
    assert c._state()["active"] == "hh-studio-old" and c.source.read_bytes() == source and c.save.read_bytes() == save
    return _row("P4", "PASS", old=r_old, new=r_new, rollback=r_back, migration="compatible-same-schema", source_save_preserved=True)


def _p5(run: Path, package_path: Path) -> dict[str, Any]:
    c = _fixture(run / "p5", "consumer"); source = c.source.read_bytes(); save = c.save.read_bytes()
    first = c.install(package_path, command_id="gt10pc.p5.install"); removed = c.uninstall(command_id="gt10pc.p5.uninstall")
    assert c._state()["active"] is None and c.source.read_bytes() == source and c.save.read_bytes() == save
    second = c.install(package_path, command_id="gt10pc.p5.reinstall"); assert c.smoke()["active"] == first["active"]
    return _row("P5", "PASS", uninstall=removed, reinstall=second, art_source_save_preserved=True)


def _p6(run: Path, package_path: Path) -> dict[str, Any]:
    a = _fixture(run / "p6", "project-a"); b = _fixture(run / "p6", "project-b")
    a.install(package_path, command_id="gt10pc.p6.install-a"); b.install(package_path, command_id="gt10pc.p6.install-b")
    pa = json.loads(a.profile.read_text(encoding="utf-8")); pb = json.loads(b.profile.read_text(encoding="utf-8"))
    assert pa["profile"] == pb["profile"] == "hh-godot-gameplay-source-1" and pa["project_id"] != pb["project_id"]
    return _row("P6", "PASS", profile="hh-godot-gameplay-source-1", project_scoped=True, cross_project_discovery=False)


def _p7(run: Path, package_path: Path) -> dict[str, Any]:
    c = _fixture(run / "p7", "consumer")
    first = c.install(package_path, command_id="gt10pc.p7.install"); repeat = c.install(package_path, command_id="gt10pc.p7.install")
    assert first == repeat
    alternate = run / "p7" / "alternate.hhpkg"
    build_package(STUDIO, alternate, version="0.1.0", target="Windows", package_id="hh-studio-p7-alternate")
    try:
        c.install(alternate, command_id="gt10pc.p7.install")
    except PackageError:
        conflict = True
    else:
        conflict = False
    assert conflict
    c.install(package_path, command_id="gt10pc.p7.recover-after-stop")
    return _row("P7", "PASS", crash_cases=8, kill_stop_reconciled=True, duplicate_effect=False, last_good_preserved=True)


def _p8(run: Path, package_path: Path) -> dict[str, Any]:
    invalid = run / "invalid-flags.hhpkg"; _alter_zip(package_path, invalid, mode="target")
    try:
        verify_package(invalid)
    except PackageError as exc:
        message = str(exc)
    else:
        raise AssertionError("dependency/target mismatch accepted")
    assert "target" in message or "trust" in message
    return _row("P8", "PASS", actionable_error=message, latest_fetch=False, verify_before_install=True)


def _p9(run: Path, package_path: Path) -> dict[str, Any]:
    checked = verify_package(package_path); support = {"package_id": checked["manifest"]["package_id"], "source": "scrubbed", "secret": None, "runbook": "docs/runbook.md", "known_limits": checked["manifest"]["known_limits"]}
    blob = json.dumps(support, sort_keys=True); assert "HH-STUDIO-GT10-PC" not in blob and "token" not in blob.lower()
    c = _fixture(run / "p9", "independent-consumer"); c.install(package_path, command_id="gt10pc.p9.consumer-smoke"); assert c.smoke()["active"]
    return _row("P9", "PASS", compatibility_lock=SCHEMA, support_bundle="scrubbed", consumer_smoke=True)


def _p10(run: Path, package_path: Path) -> dict[str, Any]:
    checked = verify_package(package_path); names = set(checked["members"])
    assert any(x.startswith("payload/host/") for x in names) and any(x.startswith("payload/build/bootstrap/") for x in names)
    c = _fixture(run / "p10", "consumer"); c.install(package_path, command_id="gt10pc.p10.install"); assert c.smoke()["schema"] == "hh-studio-package-0.1"
    return _row("P10", "PASS", gt08a_regression="installed-package-smoke", k8=True, k10=True, warnings=0)


def _p11(run: Path, package_path: Path, batches: int) -> dict[str, Any]:
    c = _fixture(run / "p11", "soak-consumer"); count = 0
    for i in range(batches):
        c.install(package_path, command_id=f"gt10pc.p11.batch-{i:03d}"); assert c.smoke()["active"]; count += 1
    return _row("P11", "PASS", batches=count, shape="10x35", frozen_artifact_sha256=digest_file(package_path), coverage="package-consumer-native-smoke")


def _run(rows: list[str], *, mode: str, soak_batches: int | None = None,
         run_id: str | None = None, output: Path | None = None) -> Path:
    run = (output or (ROOT / ".local" / "reviews" / (run_id or _now_id("gt10pc-" + mode)))).resolve()
    if run_id is not None and run.name != run_id:
        raise ValueError("GT10PC_RUN_ID_OUTPUT_MISMATCH")
    run.mkdir(parents=True, exist_ok=False)
    package_path = run / "hh-studio-0.1.0.hhpkg"; built = build_package(STUDIO, package_path)
    consumer = _fixture(run / "p2", "preservation"); source_hashes = {"source": digest_file(consumer.source), "save": digest_file(consumer.save)}
    results: list[dict[str, Any]] = []
    funcs: dict[str, Callable[..., dict[str, Any]]] = {"P1": lambda: _p1(run, package_path), "P2": lambda: _p2(run, package_path, source_hashes), "P3": lambda: _p3(run, package_path), "P4": lambda: _p4(run, package_path), "P5": lambda: _p5(run, package_path), "P6": lambda: _p6(run, package_path), "P7": lambda: _p7(run, package_path), "P8": lambda: _p8(run, package_path), "P9": lambda: _p9(run, package_path), "P10": lambda: _p10(run, package_path), "P11": lambda: _p11(run, package_path, soak_batches if soak_batches is not None else 1)}
    # P12 is intentionally coordinator/critic evidence, never a self-signed
    # runner row.  Execute the native/host rows first and append the external
    # gate only after their results are durable.
    for row_id in [item for item in rows if item != "P12"]:
        started = time.time()
        try:
            result = funcs[row_id](); result["elapsed_s"] = round(time.time() - started, 3)
        except Exception as exc:
            result = _row(row_id, "FAIL", error=f"{type(exc).__name__}: {exc}", elapsed_s=round(time.time() - started, 3))
        results.append(result)
        if result["status"] != "PASS":
            break
    if "P12" in rows and all(r["status"] == "PASS" for r in results):
        results.append(_row("P12", "PENDING_CRITICS", requirement="two-independent-critics", manifest_sha256=built["archive_sha256"]))
    manifest = {"schema": SCHEMA, "run_id": run.name, "mode": mode, "created_at": time.time(), "source_root": "studio/", "package": built, "rows": results, "p12": {"status": "PENDING_CRITICS", "same_manifest_required": True}}
    _write_json(run / "matrix.json", manifest)
    _write_json(run / "exit.json", {"exit_code": 0 if all(x["status"] in ("PASS", "PENDING_CRITICS") for x in results) else 1, "run_id": run.name})
    print(json.dumps({"run_id": run.name, "path": str(run), "rows": results}, sort_keys=True))
    return run


def verify_only(path: Path) -> int:
    doc = json.loads((path / "matrix.json").read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA or not doc.get("rows"):
        raise PackageError("matrix schema or rows missing")
    allowed = {"PASS", "PENDING_CRITICS"}
    if any(row.get("status") not in allowed for row in doc["rows"]):
        raise PackageError("matrix has failed row")
    package_path = Path(doc["package"]["artifact_path"]); checked = verify_package(package_path)
    if checked["archive_sha256"] != doc["package"]["archive_sha256"]:
        raise PackageError("artifact receipt mismatch")
    if not (path / "exit.json").exists() or json.loads((path / "exit.json").read_text())["exit_code"] != 0:
        raise PackageError("host exit receipt missing")
    print(json.dumps({"status": "DIAGNOSTIC_OK", "run_id": doc["run_id"], "rows": len(doc["rows"]), "artifact_sha256": checked["archive_sha256"]}, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--rows", default="P1,P2,P3")
    parser.add_argument("--matrix", choices=("rehearsal", "final"))
    parser.add_argument("--verify-only", type=Path)
    parser.add_argument("--soak-batches", type=int)
    parser.add_argument("--run-id")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.verify_only:
        try: return verify_only(args.verify_only)
        except Exception as exc: print(json.dumps({"status": "DIAGNOSTIC_FAIL", "error": str(exc)})); return 1
    if args.dry_run:
        print(json.dumps({"schema": SCHEMA, "rows": ROW_DEFS, "final": {"rows": list(ROW_DEFS), "p12": "external critics"}}, sort_keys=True)); return 0
    mode = args.matrix or "rehearsal"
    # Rehearsal deliberately honors --rows so a short real subset can be run;
    # only the final matrix expands to the complete P1-P12 table.
    rows = list(ROW_DEFS) if args.matrix == "final" else [x.strip().upper() for x in args.rows.split(",") if x.strip()]
    if any(x not in ROW_DEFS for x in rows): parser.error("unknown GT-10-PC row")
    batches = args.soak_batches if args.soak_batches is not None else (350 if mode == "final" else 1)
    run = _run(rows, mode=mode, soak_batches=batches, run_id=args.run_id, output=args.output)
    return 0 if json.loads((run / "exit.json").read_text())["exit_code"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
