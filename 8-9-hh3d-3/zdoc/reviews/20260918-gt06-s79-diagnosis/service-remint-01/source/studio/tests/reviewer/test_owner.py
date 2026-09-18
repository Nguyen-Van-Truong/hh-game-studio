"""Prepared reviewer ownership tests with fakes; no Tk, sockets or native runs."""
from contextlib import ExitStack
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.reviewer import main as reviewer


class InjectedFailure(RuntimeError):
    pass


class FakeOwners:
    """Distinct owners expose acquisition, exact close order and retry behavior."""
    def __init__(self):
        self.events = []
        self.failures = {}
        self.backends, self.services, self.transports, self.clients = [], [], [], []
        self.prepare_error = None
        self.credential = object()
        rig = self

        class Backend:
            def __init__(self):
                self.closed = False
                rig.backends.append(self)

            @classmethod
            def prepare(cls, run_id):
                rig.event('backend.prepare')
                if rig.prepare_error is not None:
                    raise rig.prepare_error
                return cls()

            def start(self):
                rig.event('backend.start')
                raise AssertionError('Preparing a reviewer must not launch native Play')

            def close(self):
                rig.event('backend.close')
                self.closed = True

        class Sessions:
            def issue(self, *, ttl_ms):
                rig.event('credential.issue')
                if ttl_ms != 115_000:
                    raise AssertionError('unexpected credential lifetime')
                return rig.credential

        class Service:
            def __init__(self, backend):
                rig.event('service.create')
                self.backend = backend
                self.sessions = Sessions()
                self.project_id = 'fixture.owner-test'
                self.binding = {'owner': 'synthetic'}
                self.closed = False
                rig.services.append(self)

            def close(self):
                rig.event('service.close')
                self.backend.close()
                self.closed = True

        class Transport:
            def __init__(self, service):
                rig.event('transport.create')
                self.service = service
                self.port, self.control_port, self.stop_port = 10001, 10002, 10003
                self.started = self.closed = False
                rig.transports.append(self)

            def start(self):
                # Failure can follow partial startup; the caller already owns us.
                self.started = True
                rig.event('transport.start')

            def close(self):
                if not self.service.closed:
                    raise AssertionError('listener closed before its service drained')
                rig.event('transport.close')
                self.closed = True
                self.started = False

        class Client:
            def __init__(self, **values):
                rig.event('client.create')
                self.values = values
                rig.clients.append(self)

            def perform(self, action):
                rig.event('client.perform')
                raise AssertionError('Preparation must not invoke Play')

        self.Backend, self.Service, self.Transport, self.Client = Backend, Service, Transport, Client

    def event(self, name):
        self.events.append(name)
        failures = self.failures.get(name, [])
        if failures:
            raise failures.pop(0)

    def fail_once(self, name, error=None):
        error = error if error is not None else InjectedFailure(name)
        self.failures.setdefault(name, []).append(error)
        return error


class PreparedOwnerTests(unittest.TestCase):
    def setUp(self):
        self.rig = FakeOwners()
        self.held = []
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for name, replacement in (('PreparedPlay', self.rig.Backend),
            ('ReplayService', self.rig.Service), ('ReplayTransport', self.rig.Transport),
            ('ReplayClient', self.rig.Client), ('HELD_REVIEWERS', self.held)):
            self.stack.enter_context(patch.object(reviewer, name, replacement))

    def prepare(self):
        return reviewer.PreparedReviewer.prepare('gt06-review-owner-test')

    def closes(self):
        return [event for event in self.rig.events if event.endswith('.close')]

    def assert_no_launch_or_retry(self):
        self.assertEqual(self.rig.events.count('backend.prepare'), 1)
        self.assertNotIn('backend.start', self.rig.events)
        self.assertNotIn('client.perform', self.rig.events)

    def test_success_owns_exact_instances_and_closes_service_before_listener(self):
        owner = self.prepare()
        self.assertIs(owner.backend, self.rig.backends[0])
        self.assertIs(owner.service, self.rig.services[0])
        self.assertIs(owner.transport, self.rig.transports[0])
        self.assertIs(owner.client, self.rig.clients[0])
        self.assertIs(owner.service.backend, owner.backend)
        self.assertIs(owner.transport.service, owner.service)
        self.assertIs(owner.client.values['credential'], self.rig.credential)
        self.assertEqual(tuple(owner.client.values[name] for name in
            ('port', 'control_port', 'stop_port')), (10001, 10002, 10003))
        self.assertEqual(self.closes(), [])
        self.assertFalse(owner.closed)
        self.assertTrue(owner.close())
        self.assertEqual(self.closes(), ['service.close', 'backend.close', 'transport.close'])
        self.assertTrue(owner.closed)
        self.assertTrue(owner.backend.closed and owner.service.closed and owner.transport.closed)
        self.assertEqual(self.held, [])
        before = list(self.rig.events)
        self.assertTrue(owner.close())
        self.assertEqual(self.rig.events, before)
        self.assert_no_launch_or_retry()

    def test_backend_error_adopts_its_cleanup_owner_and_preserves_original_error(self):
        partial = self.rig.Backend()
        error = reviewer.BackendError('TEST_PREPARE_FAILED', cleanup_owner=partial)
        self.rig.prepare_error = error
        with self.assertRaises(reviewer.BackendError) as caught:
            self.prepare()
        self.assertIs(caught.exception, error)
        self.assertTrue(partial.closed)
        self.assertEqual(self.closes(), ['backend.close'])
        self.assertEqual(self.rig.services, [])
        self.assertEqual(self.rig.transports, [])
        self.assertEqual(self.held, [])
        self.assert_no_launch_or_retry()

    def test_failed_backend_cleanup_retains_exact_owner_and_blocks_reprepare(self):
        partial = self.rig.Backend()
        original = reviewer.BackendError('TEST_PREPARE_FAILED', cleanup_owner=partial)
        self.rig.prepare_error = original
        cleanup_error = self.rig.fail_once('backend.close')
        with self.assertRaises(InjectedFailure) as caught:
            self.prepare()
        self.assertIs(caught.exception, cleanup_error)
        self.assertIs(caught.exception.__context__, original)
        self.assertEqual(len(self.held), 1)
        owner = self.held[0]
        self.assertIs(owner.backend, partial)
        self.assertIsNone(owner.service)
        self.assertFalse(owner.closed)
        with self.assertRaisesRegex(RuntimeError, '^REVIEWER_CLEANUP_HELD$'):
            self.prepare()
        self.assert_no_launch_or_retry()
        self.assertTrue(owner.close())
        self.assertTrue(partial.closed and owner.closed)
        self.assertEqual(self.held, [])
        self.assertEqual(self.closes(), ['backend.close', 'backend.close'])

    def test_backend_error_without_cleanup_owner_does_not_create_new_owner(self):
        error = reviewer.BackendError('TEST_EARLY_FAILURE')
        self.rig.prepare_error = error
        with self.assertRaises(reviewer.BackendError) as caught:
            self.prepare()
        self.assertIs(caught.exception, error)
        self.assertEqual(self.rig.backends + self.rig.services + self.rig.transports, [])
        self.assertEqual(self.closes(), [])
        self.assertEqual(self.held, [])
        self.assert_no_launch_or_retry()

    def test_service_constructor_failure_closes_only_acquired_backend(self):
        error = self.rig.fail_once('service.create')
        with self.assertRaises(InjectedFailure) as caught:
            self.prepare()
        self.assertIs(caught.exception, error)
        self.assertEqual(self.closes(), ['backend.close'])
        self.assertTrue(self.rig.backends[0].closed)
        self.assertEqual(self.rig.services + self.rig.transports, [])
        self.assertEqual(self.held, [])
        self.assert_no_launch_or_retry()

    def test_credential_failure_closes_service_and_its_backend(self):
        error = self.rig.fail_once('credential.issue')
        with self.assertRaises(InjectedFailure) as caught:
            self.prepare()
        self.assertIs(caught.exception, error)
        self.assertEqual(self.closes(), ['service.close', 'backend.close'])
        self.assertTrue(self.rig.services[0].closed and self.rig.backends[0].closed)
        self.assertEqual(self.rig.transports, [])
        self.assertEqual(self.held, [])
        self.assert_no_launch_or_retry()

    def test_transport_constructor_failure_closes_exact_service_owner(self):
        error = self.rig.fail_once('transport.create')
        with self.assertRaises(InjectedFailure) as caught:
            self.prepare()
        self.assertIs(caught.exception, error)
        self.assertEqual(self.closes(), ['service.close', 'backend.close'])
        self.assertTrue(self.rig.services[0].closed and self.rig.backends[0].closed)
        self.assertEqual(self.rig.transports, [])
        self.assertEqual(self.held, [])
        self.assert_no_launch_or_retry()

    def test_partial_transport_start_failure_drains_before_closing_listener(self):
        error = self.rig.fail_once('transport.start')
        with self.assertRaises(InjectedFailure) as caught:
            self.prepare()
        self.assertIs(caught.exception, error)
        self.assertEqual(self.closes(), ['service.close', 'backend.close', 'transport.close'])
        self.assertTrue(self.rig.transports[0].closed)
        self.assertFalse(self.rig.transports[0].started)
        self.assertEqual(self.rig.clients, [])
        self.assertEqual(self.held, [])
        self.assert_no_launch_or_retry()

    def test_client_creation_failure_closes_all_owners_without_play(self):
        error = self.rig.fail_once('client.create')
        with self.assertRaises(InjectedFailure) as caught:
            self.prepare()
        self.assertIs(caught.exception, error)
        self.assertEqual(self.closes(), ['service.close', 'backend.close', 'transport.close'])
        self.assertTrue(self.rig.backends[0].closed and self.rig.services[0].closed
                        and self.rig.transports[0].closed)
        self.assertEqual(self.rig.clients, [])
        self.assertEqual(self.held, [])
        self.assert_no_launch_or_retry()

    def test_service_cleanup_failure_keeps_listener_and_unique_held_owner_for_retry(self):
        owner = self.prepare()
        self.rig.fail_once('service.close')
        self.rig.fail_once('service.close')
        for _ in range(2):
            with self.assertRaises(InjectedFailure):
                owner.close()
            self.assertEqual(self.held, [owner])
            self.assertFalse(owner.closed)
            self.assertFalse(owner.transport.closed)
            self.assertTrue(owner.transport.started)
            self.assertNotIn('transport.close', self.rig.events)
        self.assertTrue(owner.close())
        self.assertEqual(self.closes(), ['service.close', 'service.close',
            'service.close', 'backend.close', 'transport.close'])
        self.assertTrue(owner.closed)
        self.assertEqual(self.held, [])
        self.assert_no_launch_or_retry()

    def test_listener_cleanup_failure_retains_owner_until_retry_finishes(self):
        owner = self.prepare()
        self.rig.fail_once('transport.close')
        with self.assertRaises(InjectedFailure):
            owner.close()
        self.assertEqual(self.held, [owner])
        self.assertTrue(owner.service.closed and owner.backend.closed)
        self.assertFalse(owner.transport.closed or owner.closed)
        self.assertTrue(owner.close())
        self.assertEqual(self.closes(), ['service.close', 'backend.close', 'transport.close',
            'service.close', 'backend.close', 'transport.close'])
        self.assertTrue(owner.closed and owner.transport.closed)
        self.assertEqual(self.held, [])
        self.assert_no_launch_or_retry()

    def test_keyboard_interrupt_during_prepare_still_closes_acquired_owners(self):
        interrupt = self.rig.fail_once('transport.start', KeyboardInterrupt())
        with self.assertRaises(KeyboardInterrupt) as caught:
            self.prepare()
        self.assertIs(caught.exception, interrupt)
        self.assertEqual(self.closes(), ['service.close', 'backend.close', 'transport.close'])
        self.assertEqual(self.held, [])
        self.assert_no_launch_or_retry()

    def test_prepare_failure_with_service_cleanup_error_retains_listener_for_retry(self):
        original = self.rig.fail_once('client.create')
        cleanup = self.rig.fail_once('service.close')
        with self.assertRaises(InjectedFailure) as caught:
            self.prepare()
        self.assertIs(caught.exception, cleanup)
        self.assertIs(caught.exception.__context__, original)
        self.assertEqual(len(self.held), 1)
        owner = self.held[0]
        self.assertIs(owner.backend, self.rig.backends[0])
        self.assertIs(owner.service, self.rig.services[0])
        self.assertIs(owner.transport, self.rig.transports[0])
        self.assertTrue(owner.transport.started)
        self.assertNotIn('transport.close', self.rig.events)
        self.assertTrue(owner.close())
        self.assertEqual(self.held, [])
        self.assertTrue(owner.closed and owner.transport.closed)
        self.assert_no_launch_or_retry()


if __name__ == '__main__':
    unittest.main()
