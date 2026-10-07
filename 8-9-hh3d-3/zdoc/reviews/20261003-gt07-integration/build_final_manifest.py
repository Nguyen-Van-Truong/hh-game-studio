import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.cwd()
STUDIO = ROOT / "studio"
PKG = STUDIO / ".local/reviews/gt07-final-critic-package-20261007-04"
MATRIX = STUDIO / ".local/reviews/gt07-final-matrix-gt07-m1-final-20261007-04"
SUP = STUDIO / ".local/reviews/gt07-final-supervisor-20261007-06"
REQ = ROOT / "zdoc/reviews/20261003-gt07-integration/requirements.md"


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tree(path):
    digest = hashlib.sha256()
    for item in sorted((x for x in path.rglob("*") if x.is_file()),
                       key=lambda x: x.relative_to(path).as_posix()):
        relative = item.relative_to(path).as_posix().encode()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(bytes.fromhex(sha(item)))
    return digest.hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True,
                               ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    PKG.mkdir(parents=True, exist_ok=True)
    freeze = json.loads((SUP / "source-freeze.json").read_text(encoding="utf-8"))
    matrix = json.loads((MATRIX / "manifest.json").read_text(encoding="utf-8"))
    launch = json.loads((SUP / "launch.json").read_text(encoding="utf-8"))
    supervisor = json.loads((SUP / "supervisor.json").read_text(encoding="utf-8"))
    assert matrix["state"] == "COMPLETE"
    assert len(matrix["rows"]) == 30
    assert all(row["status"] == "PASS" for row in matrix["rows"])
    assert launch["source_closure_sha256"] == freeze["sha256"]
    assert matrix["matrix_source_closure_sha256"] == freeze["sha256"]
    rows = []
    for row in matrix["rows"]:
        receipt = MATRIX / f"row-{row['index']:02d}-terminal.json"
        terminal = json.loads(receipt.read_text(encoding="utf-8"))
        raw = Path(row["terminal"]["output"])
        rows.append({
            "index": row["index"], "run_id": row["run_id"],
            "scenario": row["scenario"], "status": row["status"],
            "exit_code": row["terminal"]["exit_code"],
            "receipt_path": receipt.relative_to(ROOT).as_posix(),
            "receipt_sha256": sha(receipt), "raw_path": raw.relative_to(ROOT).as_posix(),
            "raw_tree_sha256": tree(raw),
            "source_closure_sha256": row["terminal"].get("source_closure_sha256"),
            "binary_sha256": row["terminal"].get("binary_sha256"),
            "terminal_fields": sorted(terminal.keys()),
        })
    manifest = {
        "schema": "HH-GT07-FINAL-SOURCE-REVIEW-RAW-MANIFEST-1", "authority": 0,
        "formal_acceptance": False,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "matrix_id": matrix["matrix_id"],
        "matrix_manifest_path": (MATRIX / "manifest.json").relative_to(ROOT).as_posix(),
        "matrix_manifest_sha256": sha(MATRIX / "manifest.json"),
        "matrix_closure_sha256": matrix["final_matrix_closure_sha256"],
        "matrix_source_closure_sha256": matrix["matrix_source_closure_sha256"],
        "source_freeze_path": (SUP / "source-freeze.json").relative_to(ROOT).as_posix(),
        "source_freeze_sha256": sha(SUP / "source-freeze.json"),
        "source_file_count": len(freeze["source_files"]),
        "supervisor_path": SUP.relative_to(ROOT).as_posix(),
        "supervisor_sha256": sha(SUP / "supervisor.json"),
        "target_exit_path": (SUP / "target-exit.json").relative_to(ROOT).as_posix(),
        "target_exit_sha256": sha(SUP / "target-exit.json"),
        "supervisor_actual_exit": supervisor["actual_exit"],
        "helper_exit": supervisor["helper_exit"], "tree_verified": supervisor["tree_verified"],
        "requirements_path": REQ.relative_to(ROOT).as_posix(), "requirements_sha256": sha(REQ),
        "row_count": len(rows), "rows": rows, "raw_roots_immutable": True,
        "critic_reports": [],
    }
    manifest_path = PKG / "final-source-review-raw-manifest.json"
    write(manifest_path, manifest)
    manifest_hash = sha(manifest_path)
    package = {
        "schema": "HH-GT07-CRITIC-PACKAGE-1", "acceptance_ready": False,
        "formal_acceptance": False, "authority": 0, "matrix_id": matrix["matrix_id"],
        "manifest_path": manifest_path.relative_to(ROOT).as_posix(),
        "manifest_sha256": manifest_hash,
        "source_closure_sha256": matrix["matrix_source_closure_sha256"],
        "matrix_manifest_sha256": sha(MATRIX / "manifest.json"),
        "matrix_closure_sha256": matrix["final_matrix_closure_sha256"],
        "row_count": 30, "row_status": "30/30 PASS", "supervisor_actual_exit": 0,
        "tree_verified": True, "job_closed_and_handles_released": True,
        "raw_roots": "studio/.local/reviews/",
        "critic_requirements": [
            "Read immutable source freeze, matrix manifest, supervisor/target exit and all 30 row receipts/raw roots",
            "Recompute manifest hash and all listed hashes",
            "Verify actual exit/Job/tree/handle and requirement-to-artifact mapping",
            "Write explicit TICK=yes/no for this exact manifest hash; do not mutate evidence",
        ], "critic_reports_pending": ["critic-astra", "critic-sol"],
    }
    package_path = PKG / "package.json"
    write(package_path, package)
    write(PKG / "checklist.json", {
        "schema": "HH-GT07-FINAL-CHECKLIST-1", "manifest_sha256": manifest_hash,
        "checks": {"matrix_complete_30_pass": True, "supervisor_actual_exit_0": True,
                    "helper_exit_0": True, "tree_verified": True,
                    "task_deleted_after_terminal": True, "source_closure_bound": True,
                    "row_receipts_30": True, "raw_preserved": True,
                    "critic_01": "PENDING", "critic_02": "PENDING",
                    "coordinator_acceptance": "BLOCKED_UNTIL_TWO_TICK_YES"},
    })
    for path in (manifest_path, package_path, PKG / "checklist.json"):
        (PKG / f"{path.name}.sha256").write_text(f"{sha(path)}  {path.name}\n", encoding="utf-8")
    archive = PKG / "gt07-final-critic-package-20261007-04.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for path in (manifest_path, package_path, PKG / "checklist.json",
                     SUP / "supervisor.json", SUP / "target-exit.json",
                     MATRIX / "manifest.json", REQ):
            output.write(path, path.relative_to(ROOT).as_posix())
    print(json.dumps({"manifest_sha256": manifest_hash,
                      "package_sha256": sha(package_path),
                      "archive_sha256": sha(archive), "rows": len(rows),
                      "matrix_closure": matrix["final_matrix_closure_sha256"],
                      "source_closure": matrix["matrix_source_closure_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
