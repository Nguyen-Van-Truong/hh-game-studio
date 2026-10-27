#!/usr/bin/env python3
"""Fail-closed validator for the Superagent Y8 reference ledger.

The ledger deliberately separates source/observation evidence from product
implementation.  A state is a claim only when the corresponding evidence
fields are complete; an UNVERIFIED row is allowed in the seed inventory but
never passes parity.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

REQUIRED_GROUPS = {f"R{i:02d}" for i in range(1, 16)}
STATUSES = {
    "UNVERIFIED",
    "OBSERVED",
    "IMPLEMENTED",
    "MATCHED",
    "GAP",
    "EXEMPT_BY_OWNER",
    "NOT_IN_CURRENT",
    "APPROX",
}
TIERS = {"A", "B", "C"}
HEADERS = [
    "id", "group", "item", "tier", "source", "observation", "samples", "error",
    "tolerance", "implementation", "test", "status", "notes",
]


@dataclass(frozen=True)
class Row:
    values: dict[str, str]
    line: int

    @property
    def id(self) -> str:
        return self.values["id"]

    @property
    def group(self) -> str:
        return self.values["group"]

    @property
    def status(self) -> str:
        return self.values["status"]

    @property
    def item(self) -> str:
        return self.values["item"]

    @property
    def tier(self) -> str:
        return self.values["tier"]


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _proof(row: Row) -> list[str]:
    """Return missing evidence fields required by the row's state."""
    v = row.values
    missing: list[str] = []
    # A citation and a dated/traceable observation are intentionally separate.
    for field in ("source", "observation"):
        if not _clean(v.get(field)):
            missing.append(field)
    if not _clean(v.get("samples")):
        missing.append("samples")
    return missing


def _positive_samples(value: str) -> bool:
    text = value.strip().lower()
    if not text:
        return False
    # Accept a count (`3`, `n=30`) or a documented qualitative sample count;
    # reject placeholders which otherwise make a forged claim look complete.
    if text in {"none", "n/a", "na", "unknown", "tbd", "unverified", "-"}:
        return False
    digits = "".join(ch for ch in text if ch.isdigit())
    return bool(digits and int(digits) > 0)


def _is_nonfunctional_exemption(row: Row) -> bool:
    notes = row.values.get("notes", "").lower()
    return "scope=nonfunctional" in notes or "nonfunctional" in notes


_OWNER_APPROVAL_RE = re.compile(
    r"(?:^|[\s;,])owner_ok\s*[:=]\s*([^\s;,]+)", re.IGNORECASE
)


def _owner_approval_reference(notes: str) -> str | None:
    """Return an explicit owner record token, rejecting negative/empty claims."""
    match = _OWNER_APPROVAL_RE.search(notes or "")
    if not match:
        return None
    reference = match.group(1).strip()
    if reference.lower() in {"", "no", "none", "false", "0", "pending", "tbd"}:
        return None
    return reference


def load_ledger(path: str | Path) -> tuple[list[Row], list[str]]:
    """Read and structurally validate a TSV; returns rows and diagnostics."""
    path = Path(path)
    errors: list[str] = []
    if not path.is_file():
        return [], [f"ledger not found: {path}"]
    try:
        with path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            if reader.fieldnames != HEADERS:
                errors.append(
                    "header must be exactly: " + "\t".join(HEADERS)
                )
                return [], errors
            rows: list[Row] = []
            for line, raw in enumerate(reader, start=2):
                if None in raw:
                    errors.append(f"line {line}: too many TSV fields")
                    continue
                values = {h: _clean(raw.get(h)) for h in HEADERS}
                if not any(values.values()):
                    continue
                rows.append(Row(values, line))
    except (OSError, UnicodeError, csv.Error) as exc:
        return [], [f"cannot read ledger: {exc}"]

    ids: set[str] = set()
    groups: set[str] = set()
    for row in rows:
        if not row.id:
            errors.append(f"line {row.line}: empty id")
        if row.id in ids:
            errors.append(f"line {row.line}: duplicate id {row.id}")
        ids.add(row.id)
        if row.group not in REQUIRED_GROUPS:
            errors.append(f"line {row.line}: unsupported group {row.group!r}")
        else:
            groups.add(row.group)
        if row.status not in STATUSES:
            errors.append(f"line {row.line}: unsupported status {row.status!r}")
        if not row.item:
            errors.append(f"line {row.line}: empty item")
        if row.tier not in TIERS:
            errors.append(f"line {row.line}: tier must be A, B or C")
        # Claims are evidence gated.  UNVERIFIED is intentionally the only
        # state allowed to carry no proof in the seed ledger.
        if row.status in {"OBSERVED", "NOT_IN_CURRENT"}:
            missing = _proof(row)
            if missing:
                errors.append(
                    f"line {row.line}: {row.status} requires proof fields: "
                    + ", ".join(missing)
                )
            elif not _positive_samples(row.values["samples"]):
                errors.append(f"line {row.line}: samples must contain a positive count")
        elif row.status == "IMPLEMENTED":
            # Implementation proof is intentionally independent of reference
            # evidence; a later MATCHED row binds both sides.
            for field in ("implementation", "test"):
                if not row.values[field]:
                    errors.append(f"line {row.line}: {row.status} requires {field}")
        elif row.status == "MATCHED":
            if row.tier == "C":
                errors.append(f"line {row.line}: tier C cannot be MATCHED; use APPROX")
            missing = _proof(row)
            if missing:
                errors.append(
                    f"line {row.line}: MATCHED requires proof fields: "
                    + ", ".join(missing)
                )
            elif not _positive_samples(row.values["samples"]):
                errors.append(f"line {row.line}: samples must contain a positive count")
            for field in ("implementation", "test"):
                if not row.values[field]:
                    errors.append(f"line {row.line}: MATCHED requires {field}")
            if row.tier == "B" and not _owner_approval_reference(row.values["notes"]):
                errors.append(
                    f"line {row.line}: tier B MATCHED requires notes owner_ok=<record>"
                )
        elif row.status == "GAP":
            if not row.values["notes"]:
                errors.append(f"line {row.line}: GAP requires a reason in notes")
        elif row.status == "EXEMPT_BY_OWNER":
            if not _is_nonfunctional_exemption(row):
                errors.append(
                    f"line {row.line}: EXEMPT_BY_OWNER is only for explicit "
                    "nonfunctional scope=nonfunctional rows"
                )
            if not row.values["notes"]:
                errors.append(f"line {row.line}: EXEMPT_BY_OWNER requires notes")
        elif row.status == "APPROX":
            if row.tier != "C":
                errors.append(f"line {row.line}: APPROX is only valid for tier C")
            missing = _proof(row)
            if missing:
                errors.append(
                    f"line {row.line}: APPROX requires proof fields: "
                    + ", ".join(missing)
                )
            elif not _positive_samples(row.values["samples"]):
                errors.append(f"line {row.line}: samples must contain a positive count")
            for field in ("implementation", "test"):
                if not row.values[field]:
                    errors.append(f"line {row.line}: APPROX requires {field}")
            if not _owner_approval_reference(row.values["notes"]):
                errors.append(
                    f"line {row.line}: tier C APPROX requires notes owner_ok=<record>"
                )
    missing_groups = REQUIRED_GROUPS - groups
    if missing_groups:
        errors.append("missing required groups: " + ", ".join(sorted(missing_groups)))
    return rows, errors


def validate_ledger(path: str | Path) -> list[str]:
    """Return all diagnostics; an empty list means structural validity."""
    _, errors = load_ledger(path)
    return errors


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", nargs="?", default="docs/reference-ledger.tsv")
    args = parser.parse_args(list(argv) if argv is not None else None)
    errors = validate_ledger(args.ledger)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    rows, _ = load_ledger(args.ledger)
    print(f"ledger OK: {len(rows)} rows; groups R01-R15 present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
