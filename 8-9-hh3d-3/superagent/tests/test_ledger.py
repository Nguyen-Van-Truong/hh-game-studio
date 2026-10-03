#!/usr/bin/env python3
"""Unit tests for SA-01's fail-closed ledger/parity rules.

All positive fixtures are synthetic process fixtures. They do not claim that
Superagent matches Y8 and do not read a game or a capture.
"""
from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from tools import check_ledger, check_parity  # noqa: E402

HEADERS = check_ledger.HEADERS


def write_rows(rows):
    handle = tempfile.NamedTemporaryFile("w", suffix=".tsv", encoding="utf-8", delete=False, newline="")
    with handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return Path(handle.name)


def row(group, status="OBSERVED", **overrides):
    values = {h: "" for h in HEADERS}
    values.update(
        id=f"{group}-SYNTH",
        group=group,
        item="synthetic observation fixture",
        source="synthetic transcript S-01",
        observation="measured synthetic event; not a Y8 claim",
        samples="3",
        error="0",
        tolerance="±5%",
        implementation="fixture implementation" if status in {"IMPLEMENTED", "MATCHED"} else "",
        test="fixture test" if status in {"IMPLEMENTED", "MATCHED"} else "",
        status=status,
        notes="synthetic only",
    )
    values.update(overrides)
    return values


class LedgerTests(unittest.TestCase):
    def test_seed_ledger_has_all_groups_but_is_not_an_inventory_pass(self):
        path = HERE / "docs" / "reference-ledger.tsv"
        self.assertEqual(check_ledger.validate_ledger(path), [])
        self.assertTrue(check_parity.run(path, "inventory"))

    def test_duplicate_and_missing_group_fail_closed(self):
        rows = [row(f"R{i:02d}") for i in range(1, 16)]
        rows[-1]["id"] = rows[0]["id"]
        rows.pop(1)  # R02 is missing
        path = write_rows(rows)
        try:
            errors = check_ledger.validate_ledger(path)
            self.assertTrue(any("duplicate id" in e for e in errors))
            self.assertTrue(any("R02" in e for e in errors))
        finally:
            path.unlink(missing_ok=True)

    def test_forged_observed_row_requires_source_observation_samples(self):
        rows = [row(f"R{i:02d}") for i in range(1, 16)]
        rows[0].update(source="", observation="", samples="")
        path = write_rows(rows)
        try:
            errors = check_ledger.validate_ledger(path)
            self.assertTrue(any("OBSERVED requires proof" in e for e in errors))
        finally:
            path.unlink(missing_ok=True)

    def test_functional_owner_exemption_is_rejected(self):
        rows = [row(f"R{i:02d}") for i in range(1, 16)]
        rows[0].update(status="EXEMPT_BY_OWNER", notes="owner approved functional shortcut")
        path = write_rows(rows)
        try:
            errors = check_ledger.validate_ledger(path)
            self.assertTrue(any("EXEMPT_BY_OWNER" in e for e in errors))
        finally:
            path.unlink(missing_ok=True)

    def test_sourced_synthetic_inventory_rows_pass(self):
        rows = [row(f"R{i:02d}") for i in range(1, 16)]
        path = write_rows(rows)
        try:
            self.assertEqual(check_ledger.validate_ledger(path), [])
            self.assertEqual(check_parity.run(path, "inventory"), [])
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
