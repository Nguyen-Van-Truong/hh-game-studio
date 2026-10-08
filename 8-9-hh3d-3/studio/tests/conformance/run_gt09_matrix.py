"""Single fail-closed GT-09 K1-K15 matrix coordinator.

The dry-run freezes the row table and validates that every referenced runner is
present without starting Godot, Blender, Docker, MCP, or a long playtest.
``--matrix final`` only assembles rows that already have explicit PASS evidence
on one source closure; it never turns a diagnostic banner into a PASS.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

STUDIO = Path(__file__).resolve().parents[2]
PLAN = STUDIO.parent / "zdoc" / "8-9-godot-blender-agent-studio-plan.txt"
SCHEMA = "hh-gt09-matrix-1"
ROW_IDS = tuple(f"K{i}" for i in range(1, 16))

# Evidence is deliberately explicit.  A row may be reused only after its
# producer has emitted status=PASS on the same final closure.
ROWS: dict[str, dict[str, Any]] = {
    "K1": {"gate": "registered catalog discovery and fixture-only admission", "runner": "tests/godot/run_registered_authoring_probe.py", "status": "OPEN"},
    "K2": {"gate": "registered allowlist validation and idempotent conflict", "runner": "tests/godot/test_registered_authoring_owner.py", "status": "OPEN"},
    "K3": {"gate": "registered AUTH-01 authored behavior and replay", "runner": "tests/godot/run_registered_authoring_probe.py", "status": "OPEN"},
    "K4": {"gate": "AUTH-02 dependency graph, UID/import and rejects", "runner": "tests/godot/run_registered_authoring_probe.py", "status": "OPEN"},
    "K5": {"gate": "AUTH-03 failure preserves last good", "runner": "tests/godot/run_gameplay_failure_probe.py", "status": "OPEN"},
    "K6": {"gate": "AUTH-04 durable publish retry/reopen and owner edit", "runner": "tests/godot/run_gameplay_publication_probe.py", "status": "OPEN"},
    "K7": {"gate": "AUTH-05 executor isolation and hostile cases", "runner": "tests/godot/run_linux_probe.py", "status": "OPEN"},
    "K8": {"gate": "two fixtures authored through catalog commands", "runner": "tests/godot/run_registered_authoring_probe.py", "status": "OPEN"},
    "K9": {"gate": "seeded defect repair through catalog batch and replay", "runner": "tests/godot/run_registered_authoring_probe.py", "status": "OPEN"},
    "K10": {"gate": "input/pause/save/reload/perf on final catalog fixtures", "runner": "tests/godot/run_delegated_playtest.py", "status": "OPEN"},
    "K11": {"gate": "reconnect/retry/context reset/owner edit/parallel source jobs", "runner": "tests/godot/run_gameplay_adapter_probe.py", "status": "OPEN"},
    "K12": {"gate": "prompt injection and out-of-scope command rejection", "runner": "tests/godot/test_gameplay_attribution.py", "status": "OPEN"},
    "K13": {"gate": "pinned MCP/client/model/host operation matrix", "runner": "tests/conformance/run_gt09_mcp_spike.py", "status": "OPEN"},
    "K14": {"gate": "GT-08A/TX15/focused regression on final closure", "runner": "build/ci/gt08a_matrix.py", "status": "OPEN"},
    "K15": {"gate": "delegated 2 x 15 minute final-closure playtest", "runner": "tests/godot/run_delegated_playtest.py", "status": "OPEN"},
}


class MatrixError(ValueError):
    pass


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise MatrixError(message)


def _row_payload(row_id: str | None = None) -> list[dict[str, Any]]:
    if row_id is not None:
        _need(row_id in ROWS, f"unknown_row:{row_id}")
        ids = [row_id]
    else:
        ids = list(ROW_IDS)
    result = []
    for ident in ids:
        row = dict(ROWS[ident])
        runner = STUDIO / row["runner"]
        row.update({"id": ident, "runner_exists": runner.is_file(),
                    "runner_sha256": _sha(runner) if runner.is_file() else None})
        _need(row["runner_exists"], f"runner_missing:{ident}:{row['runner']}")
        result.append(row)
    return result


def dry_run(row_id: str | None = None) -> dict[str, Any]:
    _need(PLAN.is_file(), "plan_missing")
    rows = _row_payload(row_id)
    return {"schema": SCHEMA, "mode": "DRY_RUN", "authority": 0,
            "acceptance": False, "engine_launched": False, "network_used": False,
            "plan_sha256": _sha(PLAN), "row_count": len(rows), "rows": rows,
            "required_rows": list(ROW_IDS)}


def load_rows(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise MatrixError("evidence_manifest_invalid") from exc
    _need(type(value) is dict and value.get("schema") == SCHEMA, "evidence_manifest_schema")
    return value


def _safe_review_path(path: Path, *, root: Path) -> Path:
    """Resolve a receipt only inside this matrix's review directory."""
    value = path if path.is_absolute() else root / path
    value = value.resolve()
    _need(value.is_relative_to(root.resolve()), "evidence_path_outside_review")
    _need(value.is_file(), f"evidence_missing:{value.name}")
    return value


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise MatrixError(f"evidence_json_invalid:{path.name}") from exc
    _need(type(value) is dict, f"evidence_json_shape:{path.name}")
    return value


def _verify_row(row: dict[str, Any], *, matrix_root: Path, closure: str | None) -> str:
    """Verify raw child receipts; caller fields cannot manufacture a PASS."""
    ident = row.get("id")
    _need(ident in ROWS, f"unknown_row:{ident}")
    raw_path = _safe_review_path(Path(str(row.get("evidence_path", ""))), root=matrix_root)
    raw = _load_json(raw_path)
    _need(raw.get("schema") in ("hh-gt09-row-result-1", "hh-gt09-evidence-1"),
          f"{ident}:evidence_schema")
    _need(raw.get("row_id") == ident, f"{ident}:evidence_row_id")
    _need(raw.get("status") == "PASS", f"{ident}:evidence_status")
    child_closure = raw.get("source_closure_sha256")
    _need(type(child_closure) is str and child_closure.startswith("sha256:")
          and len(child_closure) == 71, f"{ident}:evidence_closure")
    if closure is not None:
        _need(child_closure == closure, f"{ident}:source_closure_mismatch")
    exit_path = _safe_review_path(Path(str(row.get("exit_evidence_path", ""))), root=matrix_root)
    receipt = _load_json(exit_path)
    _need(receipt.get("schema") == "hh-process-exit-1", f"{ident}:exit_schema")
    _need(receipt.get("row_id") == ident and receipt.get("actual_exit") == 0
          and receipt.get("timed_out") is False and receipt.get("owned_tree_zero") is True,
          f"{ident}:actual_exit")
    _need(row.get("evidence_sha256") == _sha(raw_path)
          and row.get("exit_evidence_sha256") == _sha(exit_path),
          f"{ident}:receipt_hash")
    return child_closure


def final_matrix(row_evidence: Path | None, output: Path | None, run_id: str) -> int:
    _need(row_evidence is not None, "final_requires_row_evidence")
    manifest = load_rows(row_evidence)
    rows = manifest.get("rows")
    _need(type(rows) is list and {r.get("id") for r in rows if isinstance(r, dict)} == set(ROW_IDS),
          "final_requires_all_rows")
    errors: list[str] = []
    closures: set[str] = set()
    matrix_root = row_evidence.parent.resolve()
    for row in rows:
        try:
            closures.add(_verify_row(row, matrix_root=matrix_root,
                                     closure=next(iter(closures), None)))
        except MatrixError as exc:
            errors.append(str(exc))
    if len(closures) != 1:
        errors.append("source_closure_mismatch")
    result = {"schema": SCHEMA, "run_id": run_id, "authority": 0,
              "acceptance": False, "status": "PASS" if not errors else "INCOMPLETE",
              "source_closure_sha256": next(iter(closures)) if len(closures) == 1 else None,
              "rows": rows, "errors": errors, "engine_launched": False}
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(_canonical(result))
    print(json.dumps({"schema": SCHEMA, "run_id": run_id, "status": result["status"],
                      "errors": errors, "authority": 0}, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--row", choices=ROW_IDS)
    parser.add_argument("--matrix", choices=("final",))
    parser.add_argument("--row-evidence", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--run-id", default="gt09-matrix-local")
    args = parser.parse_args(argv)
    if args.dry_run and args.matrix:
        parser.error("choose --dry-run or --matrix final")
    try:
        if args.dry_run:
            print(json.dumps(dry_run(args.row), sort_keys=True, separators=(",", ":")))
            return 0
        if args.matrix == "final":
            return final_matrix(args.row_evidence, args.output, args.run_id)
        parser.error("choose --dry-run or --matrix final")
    except MatrixError as exc:
        print(f"GT09_MATRIX_FAIL: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
