"""Probe boundary regressions; inert engine facts are not native evidence."""
from copy import deepcopy
from dataclasses import asdict
import unittest
from unittest.mock import patch

from studio.tests.jobs import gt07_godot_authority as probe
from studio.tests.godot import test_publication_owner as fixture
from studio.protocol.core import Status


class GodotAuthorityProbeTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.PublicationOwnerTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.value = self.fixture.value

    def test_late_return_hook_uses_public_fifo_while_commit_phase_is_draining(self):
        request, grant, lease, before, validated, record, _ = self.fixture._inert_edit()
        value = self.value
        value.project_id = 'project.fixture'
        value.contract.CATALOG_DIGEST = 'sha256:' + '1' * 64
        value._leases = {}
        other = value.sessions.issue()
        options = {'authorization': 'Bearer ' + other.bearer,
                   'catalog_digest': value.contract.CATALOG_DIGEST}
        timing = {}
        original = value._journal.edit_committed
        # Timing is modeled only here; the native scenario waits on real clock.
        with patch.object(probe, 'wait_expiry') as expiry, \
                probe.delayed_commit(value, asdict(lease), options, timing):
            result = value._edit(request, grant, lease, before, validated, record)
        self.assertEqual(result.status, Status.COMMITTED)
        self.assertEqual(timing['contender_denial'], 'GODOT_LEASE_BUSY')
        expiry.assert_called_once_with(lease.expires_ms)
        self.assertIs(value._journal.edit_committed, original)
        value._editor.apply_edit.assert_called_once()
        self.assertFalse(value.sessions.status()['draining'])

    def test_revocation_hook_after_effect_blocks_commit_and_preserves_unknown(self):
        request, grant, lease, before, validated, record, credential = self.fixture._inert_edit()
        proof = {}
        original = self.value._editor.apply_edit
        with probe.revoked_edit(self.value, credential, proof):
            result = self.value._edit(request, grant, lease, before, validated, record)
        self.assertEqual(result.status, Status.UNKNOWN)
        self.assertFalse(result.postconditions['public_ack'])
        self.assertTrue(proof['revocation']['draining'])
        self.assertIs(self.value._editor.apply_edit, original)
        original.assert_called_once()
        self.value._journal.edit_committed.assert_not_called()
        with self.assertRaisesRegex(fixture.auth.SafetyViolation, 'AUTH_REQUIRED'):
            self.value.sessions.authenticate('Bearer ' + credential.bearer)

    def test_effect_chain_counts_real_calls_not_history_identity_increments(self):
        calls = [{'command_id': command, 'completed_ms': 1, 'observation': {
            'before_revision': prior, 'semantic_revision': after,
            'history_id_before': 42, 'history_id_after': 42}}
            for command, prior, after in [('m2.godot.late', 'a', 'b'),
                                          ('m2.godot.revoked', 'b', 'c')]]
        final = {'revision': 'c', 'history_id': 42}
        probe.verify_edits(calls, final)
        with self.assertRaisesRegex(RuntimeError, 'EFFECT_COUNT_UNPROVEN'):
            probe.verify_edits(calls + calls[-1:], final)
        changed = deepcopy(calls)
        changed[-1]['observation']['history_id_after'] += 1
        with self.assertRaisesRegex(RuntimeError, 'EFFECT_CHAIN_UNPROVEN'):
            probe.verify_edits(changed, dict(final, history_id=43))
        changed = deepcopy(calls)
        changed[-1]['observation']['before_revision'] = 'unrelated'
        with self.assertRaisesRegex(RuntimeError, 'EFFECT_CHAIN_UNPROVEN'):
            probe.verify_edits(changed, final)


if __name__ == '__main__':
    unittest.main()
