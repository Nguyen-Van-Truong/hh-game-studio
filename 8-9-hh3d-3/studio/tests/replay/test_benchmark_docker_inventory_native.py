"""Real owned Windows HTTP pipes; no Docker, engines or subprocesses.

Only the fixed endpoint is redirected to a newly owned local fixture pipe.
Native adoption, request write, response read, cancellation and close remain
real. These transport checks do not grant campaign or Docker acceptance.
"""
from __future__ import annotations

import ctypes as C
from ctypes import wintypes as W
import json
import os
from pathlib import Path
import sys
import threading
import time
import unittest
from unittest.mock import patch
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.tests.replay import benchmark_docker_inventory as inventory
from studio.host.core import pipe_io
from studio.host.core.private_store import _SecurityAttributes, _StoreApi

EXPECTED_REQUEST = (b'GET /containers/json?all=0 HTTP/1.1\r\nHost: docker\r\n'
                    b'Accept: application/json\r\nConnection: close\r\n\r\n')


def http_response(body):
    return (b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n'
            b'Content-Length: ' + str(len(body)).encode('ascii') + b'\r\n\r\n' + body)


@unittest.skipUnless(os.name == 'nt', 'Windows native owned pipe fixture required')
class NativeInventoryTests(unittest.TestCase):
    def setUp(self):
        self.before = set(pipe_io._OWNERS)
        self.servers = []
        self.assertEqual(inventory._RETAINED_PIPES, [])
        self.assertEqual(inventory._RETAINED_HANDLES, [])
        self.kernel = C.WinDLL('kernel32', use_last_error=True)
        self.kernel.CreateNamedPipeW.argtypes = [
            W.LPCWSTR, W.DWORD, W.DWORD, W.DWORD, W.DWORD, W.DWORD,
            W.DWORD, C.POINTER(_SecurityAttributes)]
        self.kernel.CreateNamedPipeW.restype = W.HANDLE
        self.kernel.GetHandleInformation.argtypes = [W.HANDLE, C.POINTER(W.DWORD)]
        self.kernel.GetHandleInformation.restype = W.BOOL
        self.kernel.CloseHandle.argtypes, self.kernel.CloseHandle.restype = [W.HANDLE], W.BOOL

    def tearDown(self):
        for server in reversed(self.servers):
            server.close()
        self.assertEqual(set(pipe_io._OWNERS), self.before)
        self.assertEqual(inventory._RETAINED_PIPES, [])
        self.assertEqual(inventory._RETAINED_HANDLES, [])

    def fixture(self):
        endpoint = r'\\.\pipe\hh-inventory-native-test-' + uuid.uuid4().hex
        security = _StoreApi()
        with security.descriptor() as descriptor:
            attributes = _SecurityAttributes(C.sizeof(_SecurityAttributes), descriptor, False)
            handle = self.kernel.CreateNamedPipeW(
                endpoint, 3 | 0x40000000 | 0x80000, 8, 1, 4096, 4096,
                1000, C.byref(attributes))
        if handle in (None, C.c_void_p(-1).value):
            raise C.WinError(C.get_last_error())
        try:
            server = pipe_io.OwnedPipe._adopt(handle)
        except BaseException:
            self.kernel.CloseHandle(handle)
            raise
        self.servers.append(server)
        return endpoint, server, handle

    def valid_handle(self, handle):
        return bool(self.kernel.GetHandleInformation(handle, C.byref(W.DWORD())))

    def serve(self, server, response):
        """Retain actual client ownership before allowing it to finish."""
        release = threading.Event()
        result, observed = [], {}

        def exchange():
            try:
                server.connect(timeout_ms=1000)
                observed['request'] = server._run(
                    lambda deadline: server._read_exact(len(EXPECTED_REQUEST), deadline), 1000)
                with pipe_io._OWNERS_LOCK:
                    clients = [owner for owner in pipe_io._OWNERS
                               if owner not in self.before and owner is not server]
                if len(clients) != 1:
                    raise AssertionError('Expected one actual inventory client owner')
                observed['client'] = client = clients[0]
                observed['client_handle'] = client._handle
                if response is None:
                    # Observe a real pending read and its native event before
                    # the inventory deadline requests CancelIoEx and drains it.
                    wait_until = time.monotonic() + 0.1
                    while time.monotonic() < wait_until:
                        operation = client._operation
                        if operation is not None and operation.kind == 'read':
                            observed['operation'] = operation
                            observed['event_handle'] = operation.overlapped.event
                            break
                        time.sleep(0.001)
                    if 'operation' not in observed:
                        raise AssertionError('No actual pending inventory read observed')
                    if not release.wait(2):
                        raise AssertionError('Stalled fixture release was not signaled')
                else:
                    # Fragment real writes across both HTTP headers and body.
                    def write(deadline):
                        for offset in range(0, len(response), 11):
                            part = response[offset:offset + 11]
                            server._io('write', len(part), deadline, part)
                    server._run(write, 1000)
                result.append(None)
            except BaseException as error:
                result.append(error)
            finally:
                try:
                    server.close()
                except BaseException as error:
                    result.append(error)

        worker = threading.Thread(target=exchange, daemon=True)
        worker.start()
        return worker, release, result, observed

    def assert_settled(self, server, server_handle, worker, release, result, observed):
        release.set()
        worker.join(2)
        self.assertFalse(worker.is_alive(), 'Owned local fixture thread must finish')
        self.assertEqual(len(result), 1, 'Fixture must finish once without close failure')
        if result[0] is not None:
            raise result[0]
        self.assertEqual(observed['request'], EXPECTED_REQUEST)
        client = observed['client']
        self.assertTrue(client.closed)
        self.assertIsNone(client._operation)
        self.assertFalse(self.valid_handle(observed['client_handle']))
        self.assertTrue(server.closed)
        self.assertIsNone(server._operation)
        self.assertFalse(self.valid_handle(server_handle))
        self.assertEqual(set(pipe_io._OWNERS), self.before)
        self.assertEqual(inventory._RETAINED_PIPES, [])
        self.assertEqual(inventory._RETAINED_HANDLES, [])

    def test_native_fragmented_http_names_and_actual_fixed_request(self):
        endpoint, server, server_handle = self.fixture()
        body = json.dumps([
            {'Id': 'b' * 64, 'Names': ['/other'], 'State': 'running'},
            {'Id': 'a' * 64, 'Names': ['/hh-arena', '/alias'], 'State': 'running'},
        ], separators=(',', ':')).encode('utf-8')
        worker, release, result, observed = self.serve(server, http_response(body))
        try:
            with patch.object(inventory, 'ENDPOINT', endpoint):
                names = inventory.query_containers(time.monotonic() + 1)
            self.assertEqual(names, ['alias', 'hh-arena', 'other'])
        finally:
            self.assert_settled(server, server_handle, worker, release, result, observed)

    def test_native_stalled_read_shares_150ms_deadline_cancels_and_drains(self):
        endpoint, server, server_handle = self.fixture()
        worker, release, result, observed = self.serve(server, None)
        started = time.monotonic()
        try:
            with patch.object(inventory, 'ENDPOINT', endpoint):
                with self.assertRaises(inventory.InventoryError) as caught:
                    inventory.query_containers(started + 0.15)
            elapsed = time.monotonic() - started
            self.assertEqual(caught.exception.reason, 'timeout')
            self.assertFalse(caught.exception.retryable)
            self.assertGreaterEqual(elapsed, 0.14)
            self.assertLess(elapsed, 0.5, 'Deadline plus native cancellation drain must stay bounded')
        finally:
            self.assert_settled(server, server_handle, worker, release, result, observed)
        operation = observed['operation']
        self.assertTrue(operation.complete, 'Cancellation must have native completion readback')
        self.assertEqual(operation.error, 995, 'Native read must complete as ERROR_OPERATION_ABORTED')
        self.assertFalse(self.valid_handle(observed['event_handle']))

    def test_native_malformed_json_response_closes_all_owners(self):
        endpoint, server, server_handle = self.fixture()
        worker, release, result, observed = self.serve(server, http_response(b'not-json'))
        try:
            with patch.object(inventory, 'ENDPOINT', endpoint):
                with self.assertRaises(inventory.InventoryError) as caught:
                    inventory.query_containers(time.monotonic() + 1)
            self.assertEqual(caught.exception.reason, 'bad_output')
            self.assertFalse(caught.exception.retryable)
        finally:
            self.assert_settled(server, server_handle, worker, release, result, observed)


if __name__ == '__main__':
    unittest.main(verbosity=2)
