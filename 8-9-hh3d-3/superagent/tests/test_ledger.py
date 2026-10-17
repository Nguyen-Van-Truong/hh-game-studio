#!/usr/bin/env python3
"""Unit tests for SA-01's fail-closed ledger/parity rules.

All positive fixtures are synthetic process fixtures. They do not claim that
Superagent matches Y8 and do not read a game or a capture.
"""
from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from tools import check_ledger, check_parity, measurement_gate  # noqa: E402

HEADERS = check_ledger.HEADERS


def write_rows(rows):
    handle = tempfile.NamedTemporaryFile("w", suffix=".tsv", encoding="utf-8", delete=False, newline="")
    with handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return Path(handle.name)


def write_measurements(groups, *, mismatch=False):
    """Create complete synthetic samples for the requested numeric groups."""
    data = measurement_gate.template()
    for group in groups:
        for metric, unit in measurement_gate.TARGETS[group].items():
            sample = [1, 1, 1] if unit == "count" else [1.0, 1.0, 1.0]
            product = list(sample)
            if mismatch and group == "A01" and metric == "walk_speed":
                product = [2, 2, 2]
            common = {"samples": sample, "source": "synthetic measurement S-01", "uncertainty": 0}
            product_common = {"samples": product, "source": "synthetic product S-01", "uncertainty": 0}
            data["groups"][group][metric]["reference"] = common
            data["groups"][group][metric]["product"] = product_common
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False)
    with handle:
        json.dump(data, handle)
    return Path(handle.name)


def row(group, status="OBSERVED", **overrides):
    values = {h: "" for h in HEADERS}
    values.update(
        id=f"{group}-SYNTH",
        group=group,
        item="synthetic observation fixture",
        tier="B",
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
        # An empty A01-A06 template is work, so the default inventory gate
        # must not silently bypass it.
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

    def test_c_matched_and_b_matched_without_owner_record_fail_closed(self):
        rows = [row(f"R{i:02d}") for i in range(1, 16)]
        rows[0].update(status="MATCHED", tier="C", notes="owner_ok=OWNER-SYNTH-01")
        rows[1].update(status="MATCHED", tier="B", notes="parallel play pending")
        path = write_rows(rows)
        try:
            errors = check_ledger.validate_ledger(path)
            self.assertTrue(any("tier C cannot be MATCHED" in e for e in errors))
            self.assertTrue(any("tier B MATCHED requires" in e for e in errors))
        finally:
            path.unlink(missing_ok=True)

    def test_approx_requires_real_owner_record_source_and_test(self):
        rows = [row(f"R{i:02d}") for i in range(1, 16)]
        rows[0].update(
            status="APPROX",
            tier="C",
            source="",
            observation="",
            samples="",
            implementation="",
            test="",
            notes="no owner_ok recorded",
        )
        path = write_rows(rows)
        try:
            errors = check_ledger.validate_ledger(path)
            self.assertTrue(any("APPROX requires proof fields" in e for e in errors))
            self.assertTrue(any("APPROX requires implementation" in e for e in errors))
            self.assertTrue(any("owner_ok=<record>" in e for e in errors))
        finally:
            path.unlink(missing_ok=True)

    def test_sourced_synthetic_inventory_rows_pass(self):
        rows = [row(f"R{i:02d}") for i in range(1, 16)]
        path = write_rows(rows)
        measurement = write_measurements([f"A{i:02d}" for i in range(1, 7)])
        try:
            self.assertEqual(check_ledger.validate_ledger(path), [])
            self.assertEqual(check_parity.run(path, "inventory", measurement), [])
        finally:
            path.unlink(missing_ok=True)
            measurement.unlink(missing_ok=True)

    def test_classic_compares_numeric_rows_and_accepts_matching_fixture(self):
        rows = [row(f"R{i:02d}", status="NOT_IN_CURRENT") for i in range(1, 16)]
        rows[1].update(
            id="R02-01",
            group="R02",
            status="MATCHED",
            tier="A",
            implementation="synthetic implementation",
            test="synthetic parity test",
        )
        path = write_rows(rows)
        measurement = write_measurements(["A01"])
        try:
            self.assertEqual(check_parity.run(path, "classic", measurement), [])
            mismatch = write_measurements(["A01"], mismatch=True)
            try:
                errors = check_parity.run(path, "classic", mismatch)
                self.assertTrue(any("product does not match" in e for e in errors))
            finally:
                mismatch.unlink(missing_ok=True)
        finally:
            path.unlink(missing_ok=True)
            measurement.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
