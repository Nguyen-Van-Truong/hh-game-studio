"""Pure log-policy negatives; no native engine, Docker, or child claims."""
import hashlib
import importlib.util
from pathlib import Path
import unittest

STUDIO = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('gameplay_log_policy_tests',
    STUDIO / 'godot-addon/gameplay_log_policy.py')
policy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(policy)


class GameplayLogPolicyTests(unittest.TestCase):
    def setUp(self):
        self.scripts = ['scripts/fixture_actor.gd']
        self.stdout = ('\n'.join(policy.GAMEPLAY_PHASE_EVENTS) + '\n').encode()
        self.stderr = policy.GAMEPLAY_STARTUP_ERRORS.encode()

    def classify(self, *, stdout=None, stderr=None, scripts=None):
        return policy.classify(self.stdout if stdout is None else stdout,
            self.stderr if stderr is None else stderr,
            self.scripts if scripts is None else scripts)

    def test_exact_single_script_transcript_is_explained_only(self):
        verdict = self.classify()
        self.assertEqual(verdict, {'policy': 'hh-gameplay-startup-log-1', 'accepted': True,
            'stdout_sha256': hashlib.sha256(self.stdout).hexdigest(),
            'stderr_sha256': hashlib.sha256(self.stderr).hexdigest()})
        # The classifier never promotes gameplay's own success/authority marker.
        self.assertIs(self.classify(stdout=self.stdout +
            b'HH_ENGINE_VALIDATED {"public_ack":true}\n')['accepted'], True)
        self.assertEqual(set(verdict), {'policy', 'accepted', 'stdout_sha256', 'stderr_sha256'})

    def test_secondary_modules_require_direct_parse_in_inventory_order(self):
        self.scripts += ['scripts/base.gd', 'scripts/shared_motion.gd']
        modules = ('HH_GAMEPLAY_MODULE_BEGIN scripts/base.gd\n' + policy.GUARD_MARKER + '\n'
                   'HH_GAMEPLAY_MODULE_END scripts/base.gd 0\n'
                   'HH_GAMEPLAY_MODULE_BEGIN scripts/shared_motion.gd\n' + policy.GUARD_MARKER + '\n'
                   'HH_GAMEPLAY_MODULE_END scripts/shared_motion.gd 0\n')
        self.stdout = self.stdout.replace(b'HH_GAMEPLAY_PHASE_END parse 0\n',
            modules.encode() + b'HH_GAMEPLAY_PHASE_END parse 0\n')
        self.stderr = policy.GUARDED_STARTUP_ERROR.encode() * 2 + self.stderr
        self.assertIs(self.classify()['accepted'], True)
        for script_list in ([self.scripts[0], self.scripts[2], self.scripts[1]], self.scripts[:2]):
            self.assertIs(self.classify(scripts=script_list)['accepted'], False)
        self.assertIs(self.classify(stdout=self.stdout.replace(
            b'HH_GAMEPLAY_MODULE_END scripts/base.gd 0',
            b'HH_GAMEPLAY_MODULE_END scripts/base.gd 1'))['accepted'], False)
        self.assertIs(self.classify(stderr=self.stderr[len(policy.GUARDED_STARTUP_ERROR):])['accepted'], False)

    def test_missing_duplicate_reordered_or_nonzero_phase_rejects(self):
        for output in (self.stdout.replace(b'HH_GAMEPLAY_PHASE_BEGIN import\n', b''),
                       self.stdout + b'HH_GAMEPLAY_PHASE_BEGIN parse\n',
                       self.stdout.replace(b'HH_GAMEPLAY_PHASE_BEGIN import', b'HH_GAMEPLAY_PHASE_BEGIN play'),
                       self.stdout.replace(b'HH_GAMEPLAY_PHASE_END import 0', b'HH_GAMEPLAY_PHASE_END import 1'),
                       self.stdout.replace((policy.GUARD_MARKER + '\n').encode(), b'', 1),
                       self.stdout + (policy.GUARD_MARKER + '\n').encode(),
                       self.stdout + b'HH_GAMEPLAY_MODULE_BEGIN scripts/extra.gd\n'):
            with self.subTest(output=output):
                self.assertIs(self.classify(stdout=output)['accepted'], False)

    def test_exact_stderr_count_order_and_stack_locations_are_required(self):
        for error in (b'', self.stderr + b'\n', self.stderr + policy.GUARDED_STARTUP_ERROR.encode(),
                      self.stderr[len(policy.GUARDED_STARTUP_ERROR):],
                      self.stderr.replace(b'os_unix.cpp:899', b'os_unix.cpp:900'),
                      (policy.GAMEPLAY_STARTUP_ERRORS.replace(
                          policy.GUARDED_SOCKET_ERROR + policy.GUARDED_LISTEN_ERROR,
                          policy.GUARDED_LISTEN_ERROR + policy.GUARDED_SOCKET_ERROR, 1)).encode()):
            with self.subTest(stderr=error):
                self.assertIs(self.classify(stderr=error)['accepted'], False)

    def test_unknown_diagnostics_in_either_stream_reject(self):
        for error in (b'ERROR: unexpected\n', b'SCRIPT ERROR: bad script\n',
                      b'WARNING: unsafe call\n', b'ObjectDB instances leaked\n', b'warning: unsafe call\n'):
            self.assertIs(self.classify(stdout=self.stdout + error)['accepted'], False)
            self.assertIs(self.classify(stderr=self.stderr + error)['accepted'], False)

    def test_invalid_utf8_or_nul_reject_without_replacing_raw_bytes(self):
        for suffix in (b'\xff', b'\x00'):
            self.assertIs(self.classify(stdout=self.stdout + suffix)['accepted'], False)
            self.assertIs(self.classify(stderr=self.stderr + suffix)['accepted'], False)
        bad = self.stdout + b'\xff'
        self.assertEqual(self.classify(stdout=bad)['stdout_sha256'], hashlib.sha256(bad).hexdigest())

    def test_line_ending_normalization_does_not_change_evidence_hashes(self):
        out, err = self.stdout.replace(b'\n', b'\r\n'), self.stderr.replace(b'\n', b'\r\n')
        verdict = self.classify(stdout=out, stderr=err)
        self.assertIs(verdict['accepted'], True)
        self.assertEqual(verdict['stdout_sha256'], hashlib.sha256(out).hexdigest())
        self.assertEqual(verdict['stderr_sha256'], hashlib.sha256(err).hexdigest())
        self.assertNotEqual(verdict['stderr_sha256'], self.classify()['stderr_sha256'])

    def test_script_inventory_must_be_bounded_unique_and_canonical(self):
        for scripts in ([], (), [None], ['scripts/other.gd'], self.scripts * 2,
                        ['scripts/fixture_actor.gd', 'scripts/Fixture_Actor.gd'],
                        self.scripts + ['scripts/../other.gd'], self.scripts + ['scripts//other.gd'],
                        self.scripts + ['scripts/other.tscn'], self.scripts + ['scripts/other\n.gd'],
                        self.scripts + ['scripts/other\\bad.gd'], self.scripts + ['scripts/x:bad.gd'],
                        self.scripts + ['scripts/x.gd'] * 64):
            with self.subTest(scripts=scripts):
                self.assertIs(policy.classify(self.stdout, self.stderr, scripts)['accepted'], False)

    def test_nonbytes_and_oversized_streams_reject(self):
        for out, err in ((self.stdout.decode(), self.stderr), (self.stdout, bytearray(self.stderr)),
                         (self.stdout + b'x' * policy.MAX_LOG_BYTES, self.stderr)):
            self.assertIs(policy.classify(out, err, self.scripts)['accepted'], False)


if __name__ == '__main__':
    unittest.main()
