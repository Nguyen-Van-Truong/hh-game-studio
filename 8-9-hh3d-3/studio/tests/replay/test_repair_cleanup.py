"""Managed repair failure teardown; inert owners, no Godot or Docker launch."""
from pathlib import Path
import json
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.host.replay import repair


class CleanupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='hh-repair-cleanup-')
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name)
        self.events = []

    def resource(self, name, error=None):
        def close():
            self.events.append(name)
            if error:
                raise error
        return SimpleNamespace(close=Mock(side_effect=close))

    def run_cleanup(self, owner, server, *, editors=(), primary=None):
        return repair._cleanup(self.output, owner, server, editors, lambda *_: None, primary)

    def test_success_halts_owner_before_transport(self):
        result = self.run_cleanup(self.resource('owner'), self.resource('transport'))
        self.assertEqual(self.events, ['owner', 'transport'])
        self.assertTrue(result['cleanup_clean'])

    def test_timeout_remains_primary_with_original_cause(self):
        cause = OSError('private cause text')
        primary = TimeoutError('private timeout text')
        server = self.resource('transport', RuntimeError('private close text'))
        try:
            try:
                raise primary from cause
            finally:
                self.run_cleanup(self.resource('owner'), server, primary=sys.exc_info()[1])
        except TimeoutError as caught:
            self.assertIs(caught, primary)
            self.assertIs(caught.__cause__, cause)
        raw = (self.output / 'repair-terminal-cleanup.json').read_text()
        self.assertNotIn('private', raw)
        self.assertEqual(json.loads(raw)['cleanup_errors'], 1)

    def test_no_direct_editor_close_while_owner_or_handler_is_active(self):
        editor = self.resource('editor')
        result = self.run_cleanup(self.resource('owner', RuntimeError('work active')),
            self.resource('transport', RuntimeError('handler active')),
            editors=[(editor, {'pid': 1})], primary=TimeoutError())
        editor.close.assert_not_called()
        self.assertTrue(result['editor_receipts_deferred'])
        self.assertFalse(result['owner_closed'])
        self.assertEqual(self.events, ['owner', 'transport'])

    def test_drained_transport_allows_one_owner_retry_but_retains_failure(self):
        owner = self.resource('owner')
        owner.close.side_effect = [RuntimeError('initial work'), None]
        result = self.run_cleanup(owner, self.resource('transport'), primary=TimeoutError())
        self.assertEqual(owner.close.call_count, 2)
        self.assertTrue(result['owner_closed'])
        self.assertFalse(result['cleanup_clean'])
        self.assertEqual([r['role'] for r in result['attempts']],
                         ['owner', 'transport', 'owner_after_transport_drain'])

    def test_cleanup_failure_alone_is_not_success(self):
        failure = RuntimeError('cleanup')
        with self.assertRaises(RuntimeError) as caught:
            self.run_cleanup(self.resource('owner'), self.resource('transport', failure))
        self.assertIs(caught.exception, failure)
        self.assertFalse(json.loads((self.output / 'repair-terminal-cleanup.json').read_bytes())['cleanup_clean'])

    def test_late_successor_receipt_is_collected_without_inventing_exit(self):
        owner = self.resource('owner')
        owner._editor_parent = self.output / 'editors'
        folder = owner._editor_parent / ('editor-' + 'a' * 32)
        folder.mkdir(parents=True)
        cleanup = {'actual_process_exit': None, 'closed': True, 'wrapper_exit_code': 2}
        (folder / 'close.json').write_text(json.dumps(cleanup))
        result = self.run_cleanup(owner, self.resource('transport'), primary=TimeoutError())
        self.assertEqual(result['owner_editor_receipts'][0]['cleanup'], cleanup)
        self.assertIsNone(result['owner_editor_receipts'][0]['cleanup']['actual_process_exit'])

    def test_missing_successor_close_remains_missing(self):
        owner = self.resource('owner')
        owner._editor_parent = self.output / 'editors'
        (owner._editor_parent / ('editor-' + 'b' * 32)).mkdir(parents=True)
        result = self.run_cleanup(owner, None, primary=TimeoutError())
        self.assertIsNone(result['owner_editor_receipts'][0]['cleanup'])
        self.assertFalse(result['cleanup_clean'])

    def test_terminal_write_failure_does_not_mask_primary(self):
        (self.output / 'repair-terminal-cleanup.json').write_text('existing')
        primary = KeyboardInterrupt()
        try:
            try:
                raise primary
            finally:
                self.run_cleanup(None, None, primary=sys.exc_info()[1])
        except KeyboardInterrupt as caught:
            self.assertIs(caught, primary)


if __name__ == '__main__':
    unittest.main(verbosity=2)
