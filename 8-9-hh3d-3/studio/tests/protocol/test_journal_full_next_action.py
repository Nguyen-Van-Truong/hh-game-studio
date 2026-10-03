"""Capacity recovery guidance over real authenticated fixture HTTP routes."""
from dataclasses import replace
import http.client
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))

from studio.host.core.journal import Journal, JournalError
from studio.host.core.transport import FixtureClient, LoopbackFixtureHost, epoch_ms
from studio.protocol.core import Response, Status, canonical_bytes


class JournalFullNextActionTests(unittest.TestCase):
    def submit_http(self, host, request, credential=None):
        connection = http.client.HTTPConnection('127.0.0.1', host.port, timeout=2)
        headers = {'Content-Type': 'application/json'}
        if credential is not None:
            headers['Authorization'] = 'Bearer ' + credential.bearer
        try:
            connection.request('POST', '/v1/commands', canonical_bytes(request.as_dict()), headers)
            reply = connection.getresponse()
            return reply.status, Response.from_dict(json.loads(reply.read()))
        finally:
            connection.close()

    def terminal(self, client, command_id):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            result = client.lookup(command_id)
            if result.status is not Status.ACCEPTED_PENDING:
                return result
            time.sleep(.01)
        self.fail('fixture command did not complete')

    def test_real_capacity_refusals_guide_recovery_without_effect_or_dedupe_change(self):
        for capacity, code in (('bytes', 'JOURNAL_FULL'), ('records', 'JOURNAL_RECORD_LIMIT')):
            with self.subTest(capacity=capacity), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                journal = Journal(root / 'journal.jsonl')
                with LoopbackFixtureHost('project.capacity', root, journal) as host:
                    credential = host.sessions.issue(scopes=frozenset({'fixture.read', 'fixture.write'}))
                    client = FixtureClient(host.port, host.control_port, credential)
                    saved = client.request('capacity.saved', value=11, lease=client.lease())
                    self.assertIs(client.submit(saved).status, Status.ACCEPTED_PENDING)
                    committed = self.terminal(client, saved.command_id)
                    self.assertIs(committed.status, Status.COMMITTED)
                    lease = client.lease()
                    # Remove obsolete versions so refusal itself need not compact.
                    journal.compact(now_ms=epoch_ms())
                    journal.limits = replace(journal.limits, **(
                        {'max_bytes': journal.path.stat().st_size + 1000} if capacity == 'bytes'
                        else {'max_records': len(journal._records) + 1}))
                    request = client.request('capacity.refused', value=37, lease=lease)
                    before = journal.path.read_bytes(), host.fixture.snapshot()

                    http_status, denied = self.submit_http(host, request)
                    self.assertEqual(http_status, 400)
                    self.assertEqual(denied.code, 'AUTH_REQUIRED')
                    self.assertNotIn('next_action', denied.postconditions)

                    http_status, refused = self.submit_http(host, request, credential)
                    self.assertEqual(http_status, 400)
                    self.assertIs(refused.status, Status.REJECTED)
                    self.assertEqual(refused.code, code)
                    self.assertEqual(refused.command_id, request.command_id)
                    self.assertEqual(refused.postconditions['next_action'],
                                     'pause_new_work_and_request_host_capacity_recovery')
                    self.assertEqual(client.submit(request), refused)
                    self.assertEqual(client.lookup(request.command_id).code, 'COMMAND_NOT_FOUND')
                    self.assertEqual(client.submit(saved), committed)
                    self.assertEqual(client.lookup(saved.command_id), committed)
                    self.assertEqual((journal.path.read_bytes(), host.fixture.snapshot()), before)
                    self.assertFalse(host._stopped.is_set())
                    self.assertEqual(len(host._jobs), 0)
                    self.assertEqual(len(host._queue), 0)

    def test_uncertain_capacity_and_write_failures_keep_unknown_reconciliation(self):
        for code, outcome_unknown in (('JOURNAL_FULL', True), ('JOURNAL_WRITE_FAILED', False)):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                journal = Journal(root / 'journal.jsonl')
                with LoopbackFixtureHost('project.uncertain', root, journal) as host:
                    credential = host.sessions.issue()
                    client = FixtureClient(host.port, host.control_port, credential)
                    request = client.request('capacity.unknown')
                    failure = JournalError(code)
                    failure.outcome_unknown = outcome_unknown
                    with mock.patch.object(journal, 'append_command', side_effect=failure):
                        http_status, result = self.submit_http(host, request, credential)
                    self.assertEqual(http_status, 503)
                    self.assertIs(result.status, Status.UNKNOWN)
                    self.assertEqual(result.code, code)
                    self.assertEqual(result.command_id, request.command_id)
                    self.assertEqual(result.postconditions,
                                     {'accepting_work': False, 'next_action': 'lookup.reconcile'})
                    self.assertTrue(host._stopped.is_set())
                    self.assertFalse(journal.path.exists())
                    self.assertEqual(host.fixture.effect_count, 0)


if __name__ == '__main__':
    unittest.main()
