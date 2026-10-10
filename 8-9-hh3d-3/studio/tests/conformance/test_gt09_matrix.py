import json
from pathlib import Path
import unittest
import tempfile
import hashlib

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

    def test_final_rejects_caller_supplied_pass_without_raw_receipts(self):
        with tempfile.TemporaryDirectory(prefix='gt09-matrix-') as temp:
            root = Path(temp)
            rows = [{"id": ident, "status": "PASS", "actual_exit": 0,
                     "source_closure_sha256": "0" * 64}
                    for ident in matrix.ROW_IDS]
            manifest = {"schema": matrix.SCHEMA, "rows": rows}
            path = root / 'manifest.json'
            path.write_text(json.dumps(manifest), encoding='utf-8')
            self.assertEqual(matrix.final_matrix(path, None, 'gt09-matrix-forged'), 2)

    def test_final_rejects_rows_without_strict_owned_receipts(self):
        with tempfile.TemporaryDirectory(prefix='gt09-matrix-') as temp:
            root = Path(temp)
            closure = 'sha256:' + 'a' * 64
            rows = []
            for ident in matrix.ROW_IDS:
                evidence = root / f'{ident}-result.json'
                exit_receipt = root / f'{ident}-exit.json'
                evidence.write_text(json.dumps({"schema": "hh-gt09-row-result-1",
                    "row_id": ident, "status": "PASS",
                    "source_closure_sha256": closure}), encoding='utf-8')
                exit_receipt.write_text(json.dumps({"schema": "hh-process-exit-1",
                    "row_id": ident, "actual_exit": 0, "timed_out": False,
                    "owned_tree_zero": True}), encoding='utf-8')
                rows.append({"id": ident, "evidence_path": evidence.name,
                    "exit_evidence_path": exit_receipt.name,
                    "evidence_sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
                    "exit_evidence_sha256": hashlib.sha256(exit_receipt.read_bytes()).hexdigest()})
            manifest_path = root / 'manifest.json'
            manifest_path.write_text(json.dumps({"schema": matrix.SCHEMA, "rows": rows}), encoding='utf-8')
            output = root / 'final.json'
            self.assertEqual(matrix.final_matrix(manifest_path, output, 'gt09-matrix-good'), 2)
            self.assertEqual(json.loads(output.read_text())['status'], 'INCOMPLETE')

    def test_rehearsal_requires_wired_dependencies_and_is_not_final(self):
        with tempfile.TemporaryDirectory(prefix='gt09-rehearsal-') as temp:
            with self.assertRaisesRegex(matrix.MatrixError, "rehearsal_dependencies_not_wired:K4"):
                matrix.rehearsal_rows(output=Path(temp) / 'unsupported',
                                      run_id='gt09-rehearsal-test', selected=('K4',))
            root = Path(temp) / 'rehearsal'
            root.mkdir()
            (root / 'manifest.json').write_text(json.dumps({
                'schema': matrix.SCHEMA, 'mode': 'REHEARSAL',
                'source_closure_sha256': 'sha256:' + 'a' * 64,
                'rows': [], 'status': 'PASS'}), encoding='utf-8')
            self.assertEqual(matrix.verify_only(root), 2)


if __name__ == "__main__":
    unittest.main()
