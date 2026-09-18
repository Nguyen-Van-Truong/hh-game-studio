"""Endpoint denial/ownership tests; native AppContainer positives are separate."""
import ctypes as C
from ctypes import wintypes as W
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent))
from studio.host.core import pipe_endpoint as ep
from studio.host.core.pipe_endpoint import AppContainerEndpoint, EndpointError, _EndpointApi
from studio.host.core.private_store import PrivateStoreError

PACKAGE = 'S-1-15-2-1-2-3-4-5-6-7'


@unittest.skipUnless(os.name == 'nt', 'Windows AppContainer endpoint required')
class PipeEndpointTests(unittest.TestCase):
    def setUp(self):
        self.before = set(ep._ENDPOINTS)
        self.items = []

    def tearDown(self):
        for item in self.items:
            item.close()
        self.assertEqual(set(ep._ENDPOINTS), self.before)

    def endpoint(self, role='work'):
        item = AppContainerEndpoint.create(PACKAGE, role=role)
        self.items.append(item)
        return item

    def test_real_pipe_security_role_and_noninheritable_handle(self):
        for role in ('work', 'control'):
            item = self.endpoint(role)
            item._api.check_security(item._pipe._handle)
            self.assertEqual(item.role, role)
            self.assertTrue(item.address.startswith('\\\\.\\pipe\\' + PACKAGE + '\\hh-studio-'))
            dll = item._api.dll
            dll.GetHandleInformation.argtypes = [W.HANDLE, C.POINTER(W.DWORD)]
            dll.GetHandleInformation.restype = W.BOOL
            flags = W.DWORD()
            self.assertTrue(dll.GetHandleInformation(item._pipe._handle, C.byref(flags)))
            self.assertEqual(flags.value & 1, 0)
            self.assertIn('(A;;RC;;;OW)', item._api.expected_security)
            self.assertIn('(A;;0x12019b;;;' + PACKAGE + ')', item._api.expected_security)

    def test_current_process_is_not_authorized_as_appcontainer(self):
        item = self.endpoint()
        with self.assertRaisesRegex(EndpointError, 'PEER_NOT_APPCONTAINER'):
            item.bind_worker(item._api.dll.GetCurrentProcess())
        self.assertTrue(item._poisoned)
        self.assertEqual(item._api.dll.WaitForSingleObject(item._process, 0), 258)
        self.assertIn(item, ep.pending_endpoint_cleanup())
        item.close()
        self.assertFalse(item._api._owned_handles)

    def test_dead_process_handle_cannot_be_bound(self):
        item = self.endpoint()
        with subprocess.Popen([sys.executable, '-c', 'pass']) as child:
            self.assertEqual(child.wait(timeout=5), 0)
            with self.assertRaisesRegex(EndpointError, 'PEER_PROCESS_NOT_LIVE'):
                item.bind_worker(int(child._handle))

    def test_unbound_endpoint_cannot_read_connect_or_send(self):
        for method, args in (('connect', ()), ('read_frame', ()), ('write_frame', (b'{}',))):
            with self.subTest(method=method):
                item = self.endpoint()
                with self.assertRaisesRegex(EndpointError, 'PEER_NOT_BOUND'):
                    getattr(item, method)(*args)
                self.assertTrue(item._poisoned)

    def test_invalid_package_role_or_capacity_creates_nothing(self):
        before = set(ep._ENDPOINTS)
        for package in ('S-1-1-0', PACKAGE + ';D:NO_ACCESS_CONTROL', PACKAGE + '\n', None):
            with self.assertRaisesRegex(EndpointError, 'INVALID_PACKAGE_SID'):
                AppContainerEndpoint.create(package, role='work')
        with self.assertRaisesRegex(EndpointError, 'INVALID_ENDPOINT_ROLE'):
            AppContainerEndpoint.create(PACKAGE, role='arbitrary')
        with mock.patch.object(ep, 'MAX_ENDPOINTS', len(before)):
            with self.assertRaisesRegex(EndpointError, 'ENDPOINT_LIMIT'):
                AppContainerEndpoint.create(PACKAGE, role='work')
        self.assertEqual(set(ep._ENDPOINTS), before)

    def test_create_failure_retains_real_handle_when_close_also_fails(self):
        with mock.patch.object(_EndpointApi, 'check_security', side_effect=EndpointError('PIPE_ACL_UNVERIFIED')), \
                mock.patch.object(_EndpointApi, 'close_owned', side_effect=PrivateStoreError('PRIVATE_CLOSE_UNCERTAIN')):
            with self.assertRaisesRegex(EndpointError, 'ENDPOINT_CLEANUP_PENDING') as raised:
                AppContainerEndpoint.create(PACKAGE, role='work')
            item = raised.exception.cleanup_owner
            self.items.append(item)
            self.assertEqual(len(item._api._owned_handles), 1)
            self.assertIn(item, ep.pending_endpoint_cleanup())
        item.close()
        self.assertFalse(item._api._owned_handles)

    def test_token_close_failure_keeps_duplicate_and_token_for_retry(self):
        item = self.endpoint()
        close = item._api.close
        def refuse_token(handle):
            if handle != item._process:
                raise PrivateStoreError('PRIVATE_CLOSE_FAILED')
            close(handle)
        with mock.patch.object(item._api, 'close', side_effect=refuse_token):
            with self.assertRaisesRegex(EndpointError, 'PRIVATE_CLOSE_FAILED'):
                item.bind_worker(item._api.dll.GetCurrentProcess())
            self.assertEqual(len(item._api._owned_handles), 2)
            with self.assertRaisesRegex(EndpointError, 'ENDPOINT_CLEANUP_PENDING'):
                item.close()
        item.close()
        self.assertFalse(item._api._owned_handles)

    def test_real_dacl_change_is_rejected_before_frame_io(self):
        create = _EndpointApi.create_pipe
        def with_test_write_dac(api, address, package):
            native = api.dll.CreateNamedPipeW
            def create_with_dac(address, flags, *args):
                return native(address, flags | 0x40000, *args)
            with mock.patch.object(api.dll, 'CreateNamedPipeW', side_effect=create_with_dac):
                return create(api, address, package)
        # Only this fixture's server handle gets WRITE_DAC. A client handle
        # cannot alter server security (the initial diagnostic returned 5).
        with mock.patch.object(_EndpointApi, 'create_pipe', with_test_write_dac):
            item = self.endpoint()
        api = item._api
        handle = item._pipe._handle
        # Empty DACL on this wholly owned test pipe, not any product endpoint.
        descriptor = C.c_void_p()
        self.assertTrue(api.adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            'D:P', 1, C.byref(descriptor), None))
        api.adv.GetSecurityDescriptorDacl.argtypes = [C.c_void_p, C.POINTER(W.BOOL), C.POINTER(C.c_void_p), C.POINTER(W.BOOL)]
        api.adv.GetSecurityDescriptorDacl.restype = W.BOOL
        api.adv.SetSecurityInfo.argtypes = [W.HANDLE, C.c_int, W.DWORD, C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p]
        api.adv.SetSecurityInfo.restype = W.DWORD
        acl, present, defaulted = C.c_void_p(), W.BOOL(), W.BOOL()
        try:
            self.assertTrue(api.adv.GetSecurityDescriptorDacl(descriptor, C.byref(present), C.byref(acl), C.byref(defaulted)))
            self.assertEqual(api.adv.SetSecurityInfo(handle, 1, 4 | 0x80000000, None, None, acl, None), 0)
            with self.assertRaisesRegex(EndpointError, 'PIPE_ACL_CHANGED'):
                item.read_frame()
        finally:
            api.dll.LocalFree(descriptor)

    def test_token_sid_decoder_rejects_out_of_buffer_pointers(self):
        for pointer_delta in (-1, 0, 63, 1024):
            raw = C.create_string_buffer(64)
            C.cast(raw, C.POINTER(C.c_void_p)).contents.value = C.addressof(raw) + pointer_delta
            with self.assertRaisesRegex(EndpointError, 'PEER_TOKEN_UNVERIFIED'):
                _EndpointApi._sid(raw)


if __name__ == '__main__':
    unittest.main(verbosity=2)
