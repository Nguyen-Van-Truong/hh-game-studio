"""Mutation checks for the S17 documentation freeze; never runtime acceptance."""
from pathlib import Path
import hashlib
import json
import sys
import unittest

import validate_plans as validator


def manifest_for(inputs):
    rows = [{'path': n, 'sha256': hashlib.sha256(b).hexdigest(), 'bytes': len(b)}
            for n, b in inputs.items()]
    digest = hashlib.sha256('\n'.join(sorted(f"{r['path']} {r['sha256']}" for r in rows)).encode()).hexdigest()
    return {'revision': 'S19', 'files': rows, 'manifest_sha256': digest}


class S19Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = {n: (validator.Z / n).read_bytes() for n in validator.NAMES}

    def check_mutation(self, index, old, new, expected, *, recompute=True):
        inputs = self.inputs.copy()
        name = validator.NAMES[index]
        original = inputs[name].decode('utf-8')
        self.assertTrue(old in original, 'Mutation must target a real clause: ' + old)
        inputs[name] = original.replace(old, new).encode('utf-8')
        # Rehash by default: a check must catch the content defect, not just staleness.
        result = validator.validate(manifest_for(inputs if recompute else self.inputs), inputs, validator.Z)
        self.assertEqual(result['result'], 'FAIL')
        self.assertTrue(any(expected in e for e in result['errors']), result['errors'])

    # Retained S16 mutations.
    def test_signature_self_reference(self):
        self.check_mutation(1, 'decision_signature.signed_payload_sha256', 'self_hash_unexcluded', 'acyclic signed payload')

    def test_diagnostic_not_acceptance(self):
        self.check_mutation(0, 'GT01_EVIDENCE_STATUS=PARTIAL_RUNTIME_UNREVIEWED', 'GT01_EVIDENCE_STATUS=ACCEPTED', 'partial status')

    def test_baseline(self):
        result = validator.validate(manifest_for(self.inputs), self.inputs, validator.Z)
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['warnings'], [])
        self.assertEqual([p['wp_rows'] for p in result['plans']], [10, 32])

    def test_stale_bytes(self):
        self.check_mutation(0, 'fixture kỹ thuật', 'fixture sửa', 'source hash', recompute=False)

    def test_aggregate_digest(self):
        manifest = manifest_for(self.inputs)
        manifest['manifest_sha256'] = '0' * 64
        self.assertIn('aggregate manifest digest', validator.validate(manifest, self.inputs, validator.Z)['errors'])

    def test_missing_source_manifest_entry(self):
        manifest = manifest_for(self.inputs)
        manifest['files'].pop()
        self.assertIn('manifest file set', validator.validate(manifest, self.inputs, validator.Z)['errors'])

    def test_premature_acceptance(self):
        self.check_mutation(0, 'OWNER_START | IN_PROGRESS', 'OWNER_START | ACCEPTED', 'table status')

    def test_stale_authorization(self):
        self.check_mutation(0, 'EXECUTION_AUTHORIZATION=OWNER_APPROVED_GATED', 'EXECUTION_AUTHORIZATION=PLAN_ONLY', 'EXECUTION_AUTHORIZATION')

    def test_premature_game_dispatch(self):
        self.check_mutation(1, 'DISPATCHABLE=NO_UNTIL_GT10_ACCEPTED', 'DISPATCHABLE=YES', 'game waits GT10')

    def test_terminal_sentinel(self):
        self.check_mutation(1, 'END_OF_GAME_PLAN', 'END_BROKEN', 'terminal sentinel')

    def test_encoding_and_newlines(self):
        self.check_mutation(0, 'CURRENT_VALID_WP=GT-01\n', 'CURRENT_VALID_WP=GT-01\r\n', 'LF/control/BOM')

    def test_wrong_worker_model(self):
        self.check_mutation(0, 'MODEL=grok-4.6;', 'MODEL=auto;', 'exact official Grok policy')

    def test_wrong_worker_effort(self):
        self.check_mutation(1, 'REASONING_EFFORT=xhigh;', 'REASONING_EFFORT=medium;', 'exact official Grok policy')

    def test_dependency_table_economy(self):
        lines = self.inputs[validator.NAMES[1]].decode().splitlines()
        row = next(line for line in lines if line.startswith('16 | H2-P4-02 |'))
        self.assertIn('H2-P3-04', row)
        self.check_mutation(1, row, row.replace('H2-P3-04', 'H2-P2-04'), 'dependency table agrees')

    def test_dependency_cycle(self):
        self.check_mutation(0, '| GT-01 | PLANNED', '| GT-03 | PLANNED', 'DAG cycle')

    def test_release_profile_schema(self):
        self.check_mutation(1, 'BLOCKED_RELEASE_PROFILE_SCHEMA', 'PROFILE_ERROR_REMOVED', 'release profile is closed-schema')

    def test_load_profile_samples(self):
        self.check_mutation(1, '1.000', '10', 'load profile freezes')

    def test_deployment_profile(self):
        self.check_mutation(1, 'BLOCKED_DEPLOYMENT_PROFILE', 'DEPLOY_ANYWAY', 'deployment profile binds')

    def test_safe_open(self):
        self.check_mutation(0, 'UNSUPPORTED_SAFE_OPEN_WINDOWS', 'OPEN_UNCHECKED', 'linked inputs and safe-open')

    # S17 mutations: each new clause must be load-bearing.
    def test_design_critics_header_cannot_claim_accept(self):
        self.check_mutation(0, 'PLAN_DESIGN_CRITICS=NO_ACCEPTED_VERDICT_S6_TO_S16', 'PLAN_DESIGN_CRITICS=ACCEPTED', 'PLAN_DESIGN_CRITICS')

    def test_design_critics_header_required_in_game_plan(self):
        self.check_mutation(1, 'PLAN_DESIGN_CRITICS=NO_ACCEPTED_VERDICT_S6_TO_S16\n', '', 'PLAN_DESIGN_CRITICS')

    def test_pin_cannot_drift_to_observed_471(self):
        self.check_mutation(0, 'GT01_PIN_DECISION=GODOT_4.7.2_STABLE_OFFICIAL', 'GT01_PIN_DECISION=GODOT_4.7.1_OBSERVED', 'pin decision')

    def test_diagnostic_binary_cannot_enter_candidate(self):
        self.check_mutation(0, 'không được đưa vào package candidate GT-01', 'được đưa vào package candidate GT-01', 'pin decision')

    def test_lock_must_stay_portable(self):
        self.check_mutation(0, 'studio/.local/toolchain.local.json (ignored)', 'studio/toolchain.lock.json', 'lock is portable')

    def test_runner_exit_zero_is_not_pass(self):
        self.check_mutation(0, 'Exit 0 đơn lẻ không là PASS', 'Exit 0 là PASS', 'runner acceptance')

    def test_runner_requires_trace_line(self):
        self.check_mutation(0, 'stdout có đúng một dòng JSON GT01_TRACE', 'stdout có banner', 'runner acceptance')

    def test_process_tree_mechanism_named(self):
        self.check_mutation(0, 'KILL_ON_JOB_CLOSE', 'best-effort', 'owned-process-tree mechanism')

    def test_worker_output_machine_checks(self):
        self.check_mutation(0, 'py_compile', 'read by eye', 'machine checks')

    def test_escalation_after_two_rejects(self):
        self.check_mutation(0, 'hai batch liên tiếp bị REJECT', 'mọi batch bị REJECT', 'machine checks')

    def test_evidence_paths_redacted(self):
        self.check_mutation(0, 'đường dẫn tuyệt đối host/username phải redact', 'đường dẫn tuyệt đối host/username được giữ', 'path-redacted')

    def test_s6_s8_closures_still_enforced(self):
        # A regression to pre-S7 shop wording must still fail under the S17 validator.
        self.check_mutation(1, 'Chủ quầy không nhận currency/điểm/hoa hồng', 'Chủ quầy nhận hoa hồng', 'stall owner receives no commission')


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    report = {'result': 'PASS' if result.wasSuccessful() else 'FAIL', 'tests_run': result.testsRun,
              'failures': len(result.failures), 'errors': len(result.errors),
              'manifest_sha256': manifest_for(S19Tests.inputs)['manifest_sha256'],
              'limits': 'Static and rehashed mutation checks only; no runtime/critic/legal acceptance.'}
    (validator.OUT / 'selfcheck-s18.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    raise SystemExit(0 if result.wasSuccessful() else 1)

