"""O6 phase-aware benchmark transport retries and uncertainty tests."""
import errno
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.host.core.transport import SessionCredential
from studio.protocol.core import Status
from studio.tests.replay.benchmark_transport import BenchmarkFixtureClient


class _Reply:
    status = 200

    def read(self, *_args, **_kwargs):
        return b'{"ok":true}'


class _Connection:
    def __init__(self, *, connect_error=None, response_error=None):
        self.connect_error = connect_error
        self.response_error = response_error
        self.auto_open = 1
        self.calls = []

    def connect(self):
        self.calls.append('connect')
        if self.connect_error is not None:
            raise self.connect_error

    def request(self, *args):
        self.calls.append(('request', args))

    def getresponse(self):
        self.calls.append('getresponse')
        if self.response_error is not None:
            raise self.response_error
        return _Reply()

    def close(self):
        self.calls.append('close')


class _Client(BenchmarkFixtureClient):
    def __init__(self, connections):
        credential = SessionCredential('session', 'project', 9_999_999_999,
                                       frozenset({'fixture.read'}), 'bearer')
        super().__init__(1234, 1235, credential, timeout=2.0)
        self.connections = list(connections)

    def _connection(self, _port):
        return self.connections.pop(0)


class BenchmarkTransportTests(unittest.TestCase):
    def test_pre_send_connect_retry_records_recovery_and_reuses_payload(self):
        first = _Connection(connect_error=ConnectionRefusedError(errno.ECONNREFUSED, 'refused'))
        second = _Connection()
        client = _Client([first, second])
        with patch('studio.tests.replay.benchmark_transport.time.sleep') as sleep:
            result = client._call('/v1/lookup', {'command_id': 'same-id'}, control=True)
        self.assertEqual(result, {'ok': True})
        self.assertEqual([call[0] if isinstance(call, tuple) else call for call in second.calls],
                         ['connect', 'request', 'getresponse', 'close'])
        sleep.assert_called_once_with(.025)
        events = client.transport_events_since(0)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['stage'], 'connect')
        self.assertTrue(events[0]['recovered'])
        self.assertFalse(events[0]['bytes_sent'])
        self.assertEqual(events[0]['attempts'], 2)
        self.assertEqual(events[0]['attempt_details'][0]['errno'], errno.ECONNREFUSED)
        self.assertIsNone(client.last_transport_failure)

    def test_exhausted_pre_send_connect_failures_return_unknown_with_bound(self):
        failures = [_Connection(connect_error=ConnectionRefusedError(errno.ECONNREFUSED, 'refused'))
                    for _ in range(4)]
        client = _Client(failures)
        with patch('studio.tests.replay.benchmark_transport.time.sleep') as sleep:
            result = client._call('/v1/commands', {'command_id': 'same-id'})
        self.assertEqual(result['status'], Status.UNKNOWN.value)
        self.assertEqual(result['code'], 'CONNECTION_LOST_LOOKUP')
        event = client.transport_events_since(0)[0]
        self.assertEqual((event['attempts'], len(event['attempt_details'])), (4, 4))
        self.assertFalse(event['recovered'])
        self.assertFalse(event['bytes_sent'])
        self.assertEqual(sleep.call_count, 3)

    def test_post_send_failure_is_unknown_without_reconnect(self):
        connection = _Connection(response_error=ConnectionResetError('reset'))
        client = _Client([connection])
        result = client._call('/v1/lookup', {'command_id': 'same-id'}, control=True)
        self.assertEqual(result['status'], Status.UNKNOWN.value)
        self.assertEqual(len(client.connections), 0)
        event = client.transport_events_since(0)[0]
        self.assertEqual(event['stage'], 'getresponse')
        self.assertTrue(event['bytes_sent'])
        self.assertFalse(event['recovered'])
        self.assertIsNotNone(client.last_transport_failure)


if __name__ == '__main__':
    unittest.main()
