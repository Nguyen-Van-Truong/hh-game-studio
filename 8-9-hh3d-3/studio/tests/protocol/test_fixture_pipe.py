"""RPC adapter tests with explicit frame-boundary substitution, not OS auth proof.

Real session/journal/queue/HTTP lookup are exercised. Native AppContainer
integration must additionally exercise these bytes through an unpatched endpoint.
"""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent))
from studio.host.core.fixture_pipe import FixturePipeServer, fixture_frame
from studio.host.core.pipe_endpoint import AppContainerEndpoint
from studio.host.core.journal import Journal, JournalError
from studio.host.core.pipe_io import PipeIOError
from studio.host.core.transport import FixtureClient, LoopbackFixtureHost
from studio.protocol.core import Status, canonical_bytes


@unittest.skipUnless(os.name == 'nt', 'Windows endpoint constructor required')
class FixturePipeTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        folder = self.stack.enter_context(tempfile.TemporaryDirectory(prefix='gt02-pipe-rpc-'))
        self.root = Path(folder)
        self.host = self.stack.enter_context(LoopbackFixtureHost('project.fixture', self.root, Journal(self.root/'journal.jsonl')))
        self.credential = self.host.sessions.issue(scopes=frozenset({'fixture.read','fixture.write','control.stop','control.cancel'}))
        self.client = FixtureClient(self.host.port, self.host.control_port, self.credential)
        self.endpoint = AppContainerEndpoint.create('S-1-15-2-1-2-3-4-5-6-7', role='work')
        self.stack.callback(self.endpoint.close)
        self.server = FixturePipeServer(self.endpoint, self.host, self.credential)

    def rpc(self, route, body, *, credential=None, raw=None):
        wire = raw if raw is not None else fixture_frame(credential or self.credential, route, body)
        with mock.patch.object(self.endpoint, 'read_frame', return_value=wire), \
                mock.patch.object(self.endpoint, 'write_frame') as send:
            self.server.serve_one()
            self.assertEqual(send.call_count, 1)
            response = send.call_args.args[0]
            self.assertNotIn(self.credential.bearer.encode(), response)
            return json.loads(response)

    def terminal(self, command):
        end = time.monotonic() + 2
        while time.monotonic() < end:
            result = self.client.lookup(command)
            if result.status is not Status.ACCEPTED_PENDING:
                return result
            time.sleep(.005)
        self.fail('Bounded fixture lookup expired')

    def test_real_dispatch_journal_and_http_lookup_share_one_command(self):
        request = self.client.request('pipe.command', value=83, lease=self.client.lease())
        self.assertEqual(self.rpc('/v1/commands', request.as_dict())['status'], 'ACCEPTED_PENDING')
        terminal = self.terminal(request.command_id)
        self.assertIs(terminal.status, Status.COMMITTED)
        self.assertEqual(self.rpc('/v1/commands', request.as_dict()), terminal.as_dict())
        self.assertEqual(self.host.fixture.effect_count, 1)

    def test_auth_precedes_json_and_another_session_cannot_take_binding(self):
        other = self.host.sessions.issue()
        for header, code in (('Bearer '+'x'*43, 'AUTH_REQUIRED'),
                             ('Bearer '+other.bearer, 'SESSION_BINDING_MISMATCH')):
            with self.subTest(code=code), mock.patch('studio.host.core.fixture_pipe.parse_json_utf8') as parser:
                reply = self.rpc('', {}, raw=(header+'\n/v1/commands\n{broken').encode())
                self.assertEqual(reply['code'], code)
                parser.assert_not_called()
        self.assertEqual(self.host.fixture.effect_count, 0)

    def test_revoked_session_has_no_effect(self):
        request = self.client.request('pipe.revoked', value=89, lease=self.client.lease())
        self.host.sessions.revoke(self.credential)
        reply = self.rpc('/v1/commands', request.as_dict())
        self.assertEqual(reply['status'], 'REJECTED')
        self.assertEqual(self.host.fixture.effect_count, 0)

    def test_role_blocks_work_route_on_control_and_stop_on_work(self):
        body = {'project_id':'project.fixture','command_id':'pipe.stop'}
        self.assertEqual(self.rpc('/v1/stop', body)['code'], 'UNSUPPORTED_ROUTE')
        control = AppContainerEndpoint.create('S-1-15-2-1-2-3-4-5-6-7', role='control')
        self.stack.callback(control.close)
        self.endpoint = control
        self.server = FixturePipeServer(control, self.host, self.credential)
        self.assertEqual(self.rpc('/v1/lease', {'project_id':'project.fixture','ttl_ms':1000})['code'], 'UNSUPPORTED_ROUTE')
        self.assertEqual(self.rpc('/v1/stop', body)['status'], 'ACCEPTED_PENDING')
        self.assertTrue(self.host._stopped.is_set())
        self.assertIs(self.terminal('pipe.stop').status, Status.COMMITTED)

    def test_reply_loss_keeps_durable_admission_and_lookup_without_reapply(self):
        request = self.client.request('pipe.reply.loss', value=97, lease=self.client.lease())
        wire = fixture_frame(self.credential, '/v1/commands', request.as_dict())
        with mock.patch.object(self.endpoint, 'read_frame', return_value=wire), \
                mock.patch.object(self.endpoint, 'write_frame', side_effect=PipeIOError('PIPE_IO_FAILED', delivery_unknown=True)):
            with self.assertRaisesRegex(PipeIOError, 'PIPE_IO_FAILED'):
                self.server.serve_one()
        terminal = self.terminal(request.command_id)
        self.assertIs(terminal.status, Status.COMMITTED)
        self.assertEqual(self.rpc('/v1/commands', request.as_dict()), terminal.as_dict())
        self.assertEqual(self.host.fixture.effect_count, 1)

    def test_uncertain_journal_error_matches_http_unknown_and_closes_admission(self):
        error = JournalError('JOURNAL_LOCKED')
        error.outcome_unknown = True
        with mock.patch.object(self.host, '_dispatch', side_effect=error):
            reply = self.rpc('/v1/commands', {'project_id':'project.fixture','command_id':'pipe.journal'})
        self.assertEqual(reply['status'], 'UNKNOWN')
        self.assertEqual(reply['command_id'], 'pipe.journal')
        self.assertNotIn('no_effect', reply['postconditions'])
        self.assertTrue(self.host._stopped.is_set())

    def test_malformed_headers_and_body_never_echo_credentials(self):
        for wire in (b'no delimiters', b'a'*129+b'\n/v1/commands\n{}',
                     ('Bearer '+self.credential.bearer+'\n/v1/commands\n{broken').encode()):
            with self.subTest(length=len(wire)):
                reply = self.rpc('', {}, raw=wire)
                self.assertEqual(reply['status'], 'REJECTED')
        self.assertEqual(self.host.fixture.effect_count, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
