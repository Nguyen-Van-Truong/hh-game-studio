#!/usr/bin/env python3
"""Parity gates over the SA-01 reference ledger.

``--inventory`` is the observation gate: every required row must have a real
state/evidence record, so an all-UNVERIFIED seed cannot silently pass.
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
        load_ledger,
        validate_ledger,
    )
except ImportError:  # package invocation from repository root
    from tools.check_ledger import (
        Row,
        _is_nonfunctional_exemption,
        load_ledger,
        validate_ledger,
    )


def _functional(row: Row) -> bool:
    """Rows are functional by default; only an explicit owner scope exempts."""
    return not _is_nonfunctional_exemption(row)


def inventory_errors(rows: list[Row]) -> list[str]:
    errors: list[str] = []
    for row in rows:
        if row.status == "UNVERIFIED":
            errors.append(
                f"line {row.line}: inventory row {row.id} is UNVERIFIED; "
                "observe it or prove NOT_IN_CURRENT before the inventory gate"
            )
    return errors


def classic_errors(rows: list[Row]) -> list[str]:
    errors: list[str] = []
    for row in rows:
        state = row.status
        if state == "EXEMPT_BY_OWNER" and _functional(row):
            errors.append(
                f"line {row.line}: functional row {row.id} cannot use EXEMPT_BY_OWNER"
            )
            continue
        if _functional(row):
            if state not in {"MATCHED", "NOT_IN_CURRENT"}:
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


def run(path: str | Path, mode: str) -> list[str]:
    structural = validate_ledger(path)
    if structural:
        return structural
    rows, _ = load_ledger(path)
    return inventory_errors(rows) if mode == "inventory" else classic_errors(rows)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--inventory", action="store_true", help="observation inventory gate")
    group.add_argument("--classic", action="store_true", help="Classic parity/release gate")
    parser.add_argument("ledger", nargs="?", default="docs/reference-ledger.tsv")
    args = parser.parse_args(list(argv) if argv is not None else None)
    mode = "classic" if args.classic else "inventory"
    errors = run(args.ledger, mode)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    rows, _ = load_ledger(args.ledger)
    print(f"parity {mode} OK: {len(rows)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
