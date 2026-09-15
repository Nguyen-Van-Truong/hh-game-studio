"""Read-only, selected GT02 socket regressions against the evolving worktree."""
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
project = Path(__file__).resolve().parents[3]
testroot = project / 'studio/tests/protocol'
sys.path.insert(0, str(testroot))
names = [
    'test_transport_recovery.TransportRecoveryTests.test_reload_fsync_failure_preserves_pending_and_requires_reconciliation',
    'test_transport_recovery.TransportRecoveryTests.test_terminal_fsync_failure_is_unknown_over_socket_until_recovery_barrier',
    'test_transport_recovery.TransportRecoveryTests.test_pending_ack_socket_cuts_preserve_lookup_and_one_effect',
    'test_transport_recovery.TransportRecoveryTests.test_committed_lookup_ack_socket_cuts_return_original_receipt',
    'test_transport_recovery.TransportRecoveryTests.test_cancel_ack_socket_cuts_do_not_duplicate_or_apply',
    'test_transport_recovery.TransportRecoveryTests.test_stop_ack_socket_cuts_preserve_stopped_state_on_reconnect',
    'test_journal_retention.JournalRetentionTests.test_terminal_fsync_failure_blocks_reopen_until_a_later_barrier',
]
def hashes():
    return {str(p.relative_to(project)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [project / 'studio/host/core/journal.py', project / 'studio/host/core/transport.py',
                      testroot / 'test_transport_recovery.py', testroot / 'test_journal_retention.py']}
before = hashes()
result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(names))
after = hashes()
print(json.dumps({'before': before, 'after': after, 'tests': result.testsRun,
                  'errors': len(result.errors), 'failures': len(result.failures),
                  'skips': len(result.skipped), 'completion': 'PREAUDIT_A_SOCKET_COMPLETE'}))
raise SystemExit(0 if result.wasSuccessful() and before == after else 1)
