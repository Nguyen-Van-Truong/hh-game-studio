import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio.tests.replay import run_o9_quiet_chain as chain


class QuietChainTests(unittest.TestCase):
    def test_dry_run_binds_one_formal_closure_without_starting_work(self):
        with tempfile.TemporaryDirectory(dir=chain.REVIEWS, prefix='o9-test-') as temp:
            value = chain.dry_run('gt06-o9-chain-test', 'gt06-o4-formal-22',
                                  Path(temp) / 'gt06-o9-chain-test')
        self.assertFalse(value['commands_started'])
        self.assertEqual(value['formal_acceptance'], False)
        self.assertEqual(value['source_closure_sha256'], chain.campaign.closure(value['source_files']))
        self.assertIn('tests/replay/run_o9_quiet_chain.py', value['source_files'])

    def test_ids_and_mode_fail_closed(self):
        with self.assertRaisesRegex(RuntimeError, 'FORMAL_ID'):
            chain.validate_ids('gt06-o9-chain-test', 'formal22')
        with self.assertRaisesRegex(RuntimeError, 'CHAIN_MODE'):
            chain.require(False, 'CHAIN_MODE')
        with self.assertRaisesRegex(RuntimeError, 'CHAIN_OUTPUT_PATH'):
            chain.validate_output(Path(tempfile.gettempdir()) / 'gt06-o9-chain-test',
                                  'gt06-o9-chain-test')

    def test_cpu_minute_uses_exclusive_stage_receipts(self):
        binding = {'chain_id': 'gt06-o9-chain-test',
                   'source_closure_sha256': 'a' * 64,
                   'source_files': {}}
        with tempfile.TemporaryDirectory() as temp, \
                patch.object(chain.campaign, 'environment_preflight', return_value={'ok': True}), \
                patch.object(chain.campaign, 'require_environment_preflight'), \
            patch.object(chain.campaign, 'observe_pair_launch') as observe:
            root = Path(temp) / 'out'
            root.mkdir()
            chain._run_cpu_minute(root, binding, 'o4.1-cpu-minute-before')
            chain._run_cpu_minute(root, binding, 'o4.1-cpu-minute-final')
            self.assertTrue((root / 'o4.1-cpu-minute-before').is_dir())
            self.assertTrue((root / 'o4.1-cpu-minute-final').is_dir())
            self.assertEqual(observe.call_count, 2)


if __name__ == '__main__':
    unittest.main()
