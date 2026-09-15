"""Bounded selected regression replay in private temporary fixtures."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

OUT = Path(__file__).resolve().parent
PRODUCT = OUT.parents[2]
tests = [
    'studio.tests.protocol.test_journal_durability',
    'studio.tests.protocol.test_transport_recovery.TransportRecoveryTests.test_unreadable_history_never_rejects_an_already_applied_command',
    'studio.tests.protocol.test_transport_recovery.TransportRecoveryTests.test_pending_ack_socket_cuts_preserve_lookup_and_one_effect',
    'studio.tests.protocol.test_transport_recovery.TransportRecoveryTests.test_committed_lookup_ack_socket_cuts_return_original_receipt',
    'studio.tests.protocol.test_transport_recovery.TransportRecoveryTests.test_cancel_ack_socket_cuts_do_not_duplicate_or_apply',
    'studio.tests.protocol.test_transport_recovery.TransportRecoveryTests.test_stop_ack_socket_cuts_preserve_stopped_state_on_reconnect',
]
started = datetime.now(timezone.utc).isoformat()
result = subprocess.run([sys.executable, '-B', '-m', 'unittest', '-v', *tests],
    cwd=PRODUCT, capture_output=True, timeout=45,
    env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8'))
(OUT / 'focused-stdout.txt').write_bytes(result.stdout)
(OUT / 'focused-stderr.txt').write_bytes(result.stderr)
report = {'started_utc': started, 'completed_utc': datetime.now(timezone.utc).isoformat(),
    'process_exit': result.returncode, 'engine_run': False, 'full_suite_run': False, 'tests': tests,
    'stdout': 'focused-stdout.txt', 'stderr': 'focused-stderr.txt'}
(OUT / 'focused-host.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(result.stderr.decode('utf-8'))
print(json.dumps(report, indent=2))
raise SystemExit(result.returncode)
