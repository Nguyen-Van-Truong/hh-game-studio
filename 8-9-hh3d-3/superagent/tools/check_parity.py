#!/usr/bin/env python3
"""Parity gates over the SA-01 reference ledger.

``--inventory`` is the SA5 observation gate: every row must have a tier and the
first six numeric groups must have measured samples; behavioral/random rows can
remain open for the WP that uses them.
``--classic`` is the release gate: functional rows must be MATCHED or proven
NOT_IN_CURRENT.  Presentation-only owner exemptions are explicitly marked in
notes and never exempt a functional row.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

try:
    from check_ledger import (
        Row,
        _is_nonfunctional_exemption,
        _owner_approval_reference,
        load_ledger,
        validate_ledger,
    )
except ImportError:  # package invocation from repository root
    from tools.check_ledger import (
        Row,
        _is_nonfunctional_exemption,
        _owner_approval_reference,
        load_ledger,
        validate_ledger,
    )

try:
    from measurement_gate import errors as measurement_errors
except ImportError:  # package invocation from repository root
    from tools.measurement_gate import errors as measurement_errors

try:
    from measurement_gate import ROW_TARGETS
except ImportError:  # package invocation from repository root
    from tools.measurement_gate import ROW_TARGETS


REQUIRED_FIRST_MEASUREMENTS = [f"A{i:02d}" for i in range(1, 7)]
DEFAULT_MEASUREMENTS = Path(__file__).resolve().parents[1] / "docs" / "measurements" / "core-measurements.json"


def _functional(row: Row) -> bool:
    """Rows are functional by default; only an explicit owner scope exempts."""
    return not _is_nonfunctional_exemption(row)


def _measurement_file(measurement_path: str | Path | None) -> Path:
    return Path(measurement_path) if measurement_path is not None else DEFAULT_MEASUREMENTS


def _numeric_groups(rows: list[Row]) -> list[str]:
    """Map tier-A ledger rows to the numeric groups they claim."""
    groups: set[str] = set()
    for row in rows:
        # A numeric comparison proves a product claim.  NOT_IN_CURRENT and
        # unresolved rows have no product value to compare.
        if row.tier == "A" and row.status == "MATCHED":
            groups.update(ROW_TARGETS.get(row.id, ()))
    return sorted(groups)


def inventory_errors(rows: list[Row], measurement_path: str | Path | None = None) -> list[str]:
    errors: list[str] = []
    errors.extend(measurement_errors(_measurement_file(measurement_path), REQUIRED_FIRST_MEASUREMENTS))
    # SA5 inventory deliberately leaves unmeasurable behavioral and random
    # rows open; their tier is recorded and the WP that uses them owns the
    # follow-up. A01-A06 remain the numeric prerequisite for SA-03.
    return errors


def classic_errors(
    rows: list[Row], measurement_path: str | Path | None = None
) -> list[str]:
    errors: list[str] = []
    numeric_groups = _numeric_groups(rows)
    if numeric_groups:
        errors.extend(
            measurement_errors(_measurement_file(measurement_path), numeric_groups, compare=True)
        )
    for row in rows:
        state = row.status
        if state == "EXEMPT_BY_OWNER" and _functional(row):
            errors.append(
                f"line {row.line}: functional row {row.id} cannot use EXEMPT_BY_OWNER"
            )
            continue
        if _functional(row):
            if state == "APPROX" and row.tier == "C":
                if not _owner_approval_reference(row.values.get("notes", "")):
                    errors.append(
                        f"line {row.line}: tier C APPROX requires notes owner_ok=<record>"
                    )
            elif state not in {"MATCHED", "NOT_IN_CURRENT"}:
                errors.append(
                    f"line {row.line}: classic functional row {row.id} must be "
                    f"MATCHED or NOT_IN_CURRENT (got {state})"
                )
        elif state not in {"MATCHED", "NOT_IN_CURRENT", "EXEMPT_BY_OWNER"}:
            errors.append(
                f"line {row.line}: nonfunctional row {row.id} has unsupported "
                f"classic state {state}"
            )
    return errors


def run(
    path: str | Path,
    mode: str,
    measurement_path: str | Path | None = None,
) -> list[str]:
    structural = validate_ledger(path)
    if structural:
        return structural
    rows, _ = load_ledger(path)
    if mode == "inventory":
        return inventory_errors(rows, measurement_path)
    return classic_errors(rows, measurement_path)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--inventory", action="store_true", help="observation inventory gate")
    group.add_argument("--classic", action="store_true", help="Classic parity/release gate")
    parser.add_argument("--measurements", default="docs/measurements/core-measurements.json", help="SA5 numeric measurement JSON")
    parser.add_argument("ledger", nargs="?", default="docs/reference-ledger.tsv")
    args = parser.parse_args(list(argv) if argv is not None else None)
    mode = "classic" if args.classic else "inventory"
    errors = run(args.ledger, mode, args.measurements)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    rows, _ = load_ledger(args.ledger)
    print(f"parity {mode} OK: {len(rows)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
