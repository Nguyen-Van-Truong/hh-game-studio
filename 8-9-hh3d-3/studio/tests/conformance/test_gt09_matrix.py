import json
from pathlib import Path
import unittest

from tests.conformance import run_gt09_matrix as matrix


class GT09MatrixTests(unittest.TestCase):
    def test_row_table_is_complete_and_runners_exist(self):
        report = matrix.dry_run()
        self.assertEqual(report["schema"], matrix.SCHEMA)
        self.assertEqual(report["row_count"], 15)
        self.assertFalse(report["engine_launched"])
        self.assertEqual([row["id"] for row in report["rows"]], list(matrix.ROW_IDS))
        self.assertTrue(all(row["runner_exists"] for row in report["rows"]))

    def test_single_row_dry_run_is_bounded(self):
        report = matrix.dry_run("K13")
        self.assertEqual(report["row_count"], 1)
        self.assertEqual(report["rows"][0]["id"], "K13")
        self.assertFalse(report["engine_launched"])

    def test_final_rejects_open_rows_and_missing_closure(self):
        with self.assertRaisesRegex(matrix.MatrixError, "final_requires_row_evidence"):
            matrix.final_matrix(None, None, "gt09-matrix-test")


if __name__ == "__main__":
    unittest.main()
