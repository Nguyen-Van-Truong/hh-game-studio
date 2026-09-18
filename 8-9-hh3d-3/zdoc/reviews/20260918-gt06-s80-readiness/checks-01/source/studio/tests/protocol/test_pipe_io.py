"""Owned real Windows pipes; failure injection retains live native operations.

No mock completion is allowed to free storage still in use by the kernel.
These are transport/lifetime tests, not worker authentication or sandbox proof.
"""
from __future__ import annotations

import ctypes as C
from ctypes import wintypes as W
import gc
import os
from pathlib import Path
import struct
import sys
import threading
import time
import unittest
from unittest import mock
import uuid
import weakref

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from host.core import pipe_io
from host.core.pipe_io import MAX_FRAME_BYTES, OwnedPipe, PipeIOError, pending_cleanup
from host.core.private_store import _StoreApi, _SecurityAttributes


@unittest.skipUnless(os.name == "nt", "Windows overlapped pipe fixture required")
class PipeIOTests(unittest.TestCase):
    def setUp(self):
        self.before = set(pipe_io._OWNERS)
        self.owners = []
        self.k = C.WinDLL("kernel32", use_last_error=True)
        self.k.CreateNamedPipeW.argtypes = [W.LPCWSTR, W.DWORD, W.DWORD, W.DWORD,
            W.DWORD, W.DWORD, W.DWORD, C.POINTER(_SecurityAttributes)]
        self.k.CreateNamedPipeW.restype = W.HANDLE
        self.k.CreateFileW.argtypes = [W.LPCWSTR, W.DWORD, W.DWORD, C.c_void_p,
                                      W.DWORD, W.DWORD, W.HANDLE]
        self.k.CreateFileW.restype = W.HANDLE
        self.k.GetHandleInformation.argtypes = [W.HANDLE, C.POINTER(W.DWORD)]
        self.k.GetHandleInformation.restype = W.BOOL
        self.k.CloseHandle.argtypes, self.k.CloseHandle.restype = [W.HANDLE], W.BOOL

    def tearDown(self):
        for owner in reversed(self.owners):
            owner.close()
        self.assertEqual(set(pipe_io._OWNERS), self.before)

    def retain(self, handle):
        try:
            owner = OwnedPipe._adopt(handle, cancel_grace_ms=30)
        except BaseException:
            self.k.CloseHandle(handle)
            raise
        self.owners.append(owner)
        return owner

    def server(self):
        name = "\\\\.\\pipe\\hh-gt02-io-test-" + uuid.uuid4().hex
        security = _StoreApi()
        with security.descriptor() as descriptor:
            attributes = _SecurityAttributes(C.sizeof(_SecurityAttributes), descriptor, False)
            handle = self.k.CreateNamedPipeW(name, 3 | 0x40000000 | 0x80000,
                                            8, 1, 4096, 4096, 1000, C.byref(attributes))
        if handle == C.c_void_p(-1).value:
            raise C.WinError(C.get_last_error())
        return self.retain(handle), name

    def pair(self):
        server, name = self.server()
        handle = self.k.CreateFileW(name, 0xC0000000, 0, None, 3, 0x40000000, None)
        if handle == C.c_void_p(-1).value:
            raise C.WinError(C.get_last_error())
        client = self.retain(handle)
        server.connect(timeout_ms=250)  # Deliberate ERROR_PIPE_CONNECTED path.
        return server, client

    def valid(self, handle):
        return bool(self.k.GetHandleInformation(handle, C.byref(W.DWORD())))

    @staticmethod
    def raw_write(owner, data):
        owner._run(lambda end: owner._io("write", len(data), end, data), 500)

    def threaded(self, action):
        outcome = []
        def run():
            try:
                outcome.append(action())
            except BaseException as exc:
                outcome.append(exc)
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return thread, outcome

    def joined(self, thread, outcome):
        thread.join(2)
        self.assertFalse(thread.is_alive(), "Owned fixture thread must drain")
        self.assertEqual(len(outcome), 1)
        if isinstance(outcome[0], BaseException):
            raise outcome[0]
        return outcome[0]

    def test_round_trip_binary_and_max_frame_without_inheritance(self):
        server, client = self.pair()
        for owner in (server, client):
            flags = W.DWORD()
            self.assertTrue(self.k.GetHandleInformation(owner._handle, C.byref(flags)))
            self.assertEqual(flags.value & 1, 0)
        for data in (b"{}", b"\x00\xff\r\n\xe1\xbb\x87", b"a" * MAX_FRAME_BYTES):
            thread, outcome = self.threaded(lambda: client.write_frame(data, timeout_ms=1000))
            self.assertEqual(server.read_frame(timeout_ms=1000), data)
            self.joined(thread, outcome)
            server.write_frame(b"reply")
            self.assertEqual(client.read_frame(), b"reply")

    def test_connect_pending_is_canceled_and_reaped(self):
        server, _ = self.server()
        start = time.monotonic()
        with self.assertRaisesRegex(PipeIOError, "PIPE_TIMEOUT") as raised:
            server.connect(timeout_ms=20)
        self.assertLess(time.monotonic() - start, 1)
        self.assertFalse(raised.exception.delivery_unknown)
        self.assertIsNone(server._operation)
        self.assertIn(server, pending_cleanup())
        server.close()
        self.assertTrue(server.closed)

    def test_read_timeout_cancels_only_owned_operation(self):
        server, client = self.pair()
        with self.assertRaisesRegex(PipeIOError, "PIPE_TIMEOUT"):
            server.read_frame(timeout_ms=20)
        self.assertIsNone(server._operation)
        self.assertTrue(self.valid(client._handle))
        with self.assertRaisesRegex(PipeIOError, "PIPE_CLOSED_OR_POISONED"):
            server.read_frame()

    def test_stop_prevents_start_and_interrupts_pending_read(self):
        server, _ = self.pair()
        thread, outcome = self.threaded(lambda: (time.sleep(.03), server.request_stop()))
        start = time.monotonic()
        with self.assertRaisesRegex(PipeIOError, "PIPE_STOPPED"):
            server.read_frame(timeout_ms=30_000)
        self.assertLess(time.monotonic() - start, 1)
        self.joined(thread, outcome)
        self.assertIsNone(server._operation)
        other, _ = self.pair()
        other.request_stop()
        with mock.patch.object(other._api, "start", wraps=other._api.start) as start_io:
            with self.assertRaisesRegex(PipeIOError, "PIPE_STOPPED"):
                other.write_frame(b"do not send")
            start_io.assert_not_called()

    def test_no_cancel_completion_keeps_buffer_event_pipe_and_owner_alive(self):
        server, _ = self.pair()
        retained = weakref.ref(server)
        with mock.patch.object(server._api, "cancel", return_value=1168):
            with self.assertRaisesRegex(PipeIOError, "PIPE_DRAIN_PENDING") as raised:
                server.read_frame(timeout_ms=10)
            op = server._operation
            self.assertIs(raised.exception.cleanup_owner, server)
            self.assertFalse(op.complete)
            self.assertTrue(self.valid(op.overlapped.event))
            self.assertTrue(self.valid(server._handle))
            self.owners.remove(server)
            del raised, server
            gc.collect()
            self.assertIsNotNone(retained())
            server = retained()
            self.owners.append(server)
            with self.assertRaisesRegex(PipeIOError, "PIPE_DRAIN_PENDING"):
                server.close()
            self.assertIs(server._operation, op)
        # Resume cleanup of that exact native operation, not a replacement read.
        handles = server._handle, op.overlapped.event
        server.close()
        self.assertTrue(server.closed)
        self.assertTrue(all(not self.valid(handle) for handle in handles))

    def test_result_query_error_does_not_release_pending_storage(self):
        server, _ = self.pair()
        with mock.patch.object(server._api, "result", return_value=6):
            with self.assertRaisesRegex(PipeIOError, "PIPE_DRAIN_PENDING"):
                server.read_frame(timeout_ms=20)
            op = server._operation
            self.assertFalse(op.complete)
            self.assertTrue(self.valid(op.overlapped.event))
        server.close()
        self.assertTrue(server.closed)

    def test_cancel_success_or_failure_without_completion_never_frees_storage(self):
        for error in (0, 5):
            with self.subTest(cancel_return=error):
                server, _ = self.pair()
                with mock.patch.object(server._api, "cancel", return_value=error):
                    with self.assertRaisesRegex(PipeIOError, "PIPE_DRAIN_PENDING"):
                        server.read_frame(timeout_ms=10)
                    self.assertFalse(server._operation.complete)
                    self.assertTrue(self.valid(server._operation.overlapped.event))
                server.close()
                self.assertTrue(server.closed)

    def test_exception_after_native_issue_drains_the_original_operation(self):
        server, _ = self.pair()
        start = server._api.start
        observed = []
        def fail_after_issue(pipe, op):
            observed.append(start(pipe, op))
            raise RuntimeError("local injected boundary failure")
        with mock.patch.object(server._api, "start", side_effect=fail_after_issue):
            with self.assertRaisesRegex(PipeIOError, "PIPE_IO_UNCERTAIN"):
                server.read_frame(timeout_ms=20)
        self.assertEqual(observed, [997])
        self.assertIsNone(server._operation)
        self.assertTrue(server._poisoned)

    def test_event_creation_failure_starts_no_native_io(self):
        server, _ = self.pair()
        with mock.patch.object(server._api, "event", side_effect=PipeIOError("PIPE_EVENT_CREATE_FAILED")), \
                mock.patch.object(server._api, "start", wraps=server._api.start) as start_io:
            with self.assertRaisesRegex(PipeIOError, "PIPE_EVENT_CREATE_FAILED"):
                server.read_frame(timeout_ms=20)
            start_io.assert_not_called()
        self.assertIsNone(server._operation)
        server.close()

    def test_wait_failure_still_observes_real_cancel_completion(self):
        server, _ = self.pair()
        with mock.patch.object(server._api, "wait", return_value=0xffffffff):
            with self.assertRaisesRegex(PipeIOError, "PIPE_WAIT_FAILED|PIPE_DRAIN_PENDING"):
                server.read_frame(timeout_ms=20)
        server.close()
        self.assertTrue(server.closed)

    def test_event_close_failure_retains_completed_operation_for_retry(self):
        server, client = self.pair()
        client.write_frame(b"ready")
        close = server._api.close
        def fail_event(handle):
            if handle != server._handle:
                raise PipeIOError("PIPE_CLOSE_FAILED")
            close(handle)
        with mock.patch.object(server._api, "close", side_effect=fail_event):
            with self.assertRaisesRegex(PipeIOError, "PIPE_CLEANUP_PENDING"):
                server.read_frame()
            op = server._operation
            self.assertTrue(op.complete)
            self.assertTrue(self.valid(op.overlapped.event))
            with self.assertRaisesRegex(PipeIOError, "PIPE_CLEANUP_PENDING"):
                server.close()
        event = op.overlapped.event
        server.close()
        self.assertFalse(self.valid(event))

    def test_pipe_close_failure_retains_handle_until_checked_close(self):
        server, _ = self.pair()
        handle = server._handle
        with mock.patch.object(server._api, "close", side_effect=PipeIOError("PIPE_CLOSE_FAILED")):
            with self.assertRaisesRegex(PipeIOError, "PIPE_CLEANUP_PENDING"):
                server.close()
            self.assertTrue(self.valid(handle))
            self.assertIn(server, pending_cleanup())
        server.close()
        server.close()
        self.assertFalse(self.valid(handle))

    def test_malformed_size_poisoned_without_reading_unbounded_body(self):
        for size in (0, MAX_FRAME_BYTES + 1, 0xffffffff):
            with self.subTest(size=size):
                server, client = self.pair()
                self.raw_write(client, struct.pack("<I", size))
                with mock.patch.object(server._api, "start", wraps=server._api.start) as start_io:
                    with self.assertRaisesRegex(PipeIOError, "PIPE_FRAME_LIMIT"):
                        server.read_frame()
                    self.assertEqual(start_io.call_count, 1)
                self.assertTrue(server._poisoned)

    def test_partial_header_disconnect_does_not_return_a_frame(self):
        server, client = self.pair()
        self.raw_write(client, b"\x04\x00")
        client.close()
        with self.assertRaisesRegex(PipeIOError, "PIPE_IO_FAILED|PIPE_EOF"):
            server.read_frame(timeout_ms=100)
        self.assertTrue(server._poisoned)

    def test_deadline_is_shared_by_header_and_body(self):
        server, client = self.pair()
        def peer():
            time.sleep(.20)
            self.raw_write(client, struct.pack("<I", 5))
        thread, outcome = self.threaded(peer)
        start = time.monotonic()
        with self.assertRaisesRegex(PipeIOError, "PIPE_TIMEOUT"):
            server.read_frame(timeout_ms=300)
        elapsed = time.monotonic() - start
        self.joined(thread, outcome)
        self.assertLess(elapsed, .45, "Header must not reset the body deadline")
        self.assertGreaterEqual(elapsed, .29)

    def test_write_timeout_is_delivery_unknown_and_never_retried(self):
        server, _ = self.pair()
        with mock.patch.object(server._api, "start", wraps=server._api.start) as start_io:
            with self.assertRaisesRegex(PipeIOError, "PIPE_TIMEOUT") as raised:
                server.write_frame(b"a" * MAX_FRAME_BYTES, timeout_ms=20)
            self.assertTrue(raised.exception.delivery_unknown)
            self.assertEqual(start_io.call_count, 1)
        self.assertTrue(server._poisoned)

    def test_successful_short_native_write_is_not_retried(self):
        server, client = self.pair()
        start = server._api.start
        def short(pipe, op):
            size, op.size = op.size, 3
            try:
                return start(pipe, op)
            finally:
                op.size = size
        with mock.patch.object(server._api, "start", side_effect=short) as start_io:
            with self.assertRaisesRegex(PipeIOError, "PIPE_SHORT_OR_INVALID_TRANSFER") as raised:
                server.write_frame(b"payload")
            self.assertTrue(raised.exception.delivery_unknown)
            self.assertEqual(start_io.call_count, 1)
        self.assertEqual(client._run(lambda end: client._read_exact(3, end), 100), b"\x07\x00\x00")

    def test_invalid_local_limits_and_duplicate_handle_do_not_transfer_ownership(self):
        server, _ = self.pair()
        for data in (b"", b"x" * (MAX_FRAME_BYTES + 1), "text", bytearray(b"x")):
            with self.assertRaisesRegex(PipeIOError, "PIPE_FRAME_LIMIT"):
                server.write_frame(data)
        for limit in (0, -1, True, 30_001, float("inf")):
            with self.assertRaisesRegex(PipeIOError, "INVALID_PIPE_LIMIT"):
                server.read_frame(timeout_ms=limit)
        with self.assertRaisesRegex(PipeIOError, "PIPE_ALREADY_OWNED"):
            OwnedPipe._adopt(server._handle)
        self.assertFalse(server._poisoned)
        self.assertTrue(self.valid(server._handle))
        with mock.patch.object(pipe_io, "MAX_OWNED_PIPES", len(pipe_io._OWNERS)):
            with self.assertRaisesRegex(PipeIOError, "PIPE_OWNER_LIMIT"):
                OwnedPipe._adopt(server._handle)

    def test_concurrent_close_requests_stop_without_closing_an_active_handle(self):
        server, _ = self.pair()
        issued = threading.Event()
        start = server._api.start
        def observe(pipe, op):
            result = start(pipe, op)
            issued.set()
            return result
        with mock.patch.object(server._api, "start", side_effect=observe):
            thread, outcome = self.threaded(lambda: server.read_frame(timeout_ms=2000))
            self.assertTrue(issued.wait(1))
            with self.assertRaisesRegex(PipeIOError, "PIPE_BUSY"):
                server.close()
            self.assertTrue(self.valid(server._handle))
            thread.join(1)
            self.assertFalse(thread.is_alive())
        self.assertEqual(len(outcome), 1)
        self.assertIsInstance(outcome[0], PipeIOError)
        self.assertEqual(outcome[0].code, "PIPE_STOPPED")
        server.close()
        self.assertTrue(server.closed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
