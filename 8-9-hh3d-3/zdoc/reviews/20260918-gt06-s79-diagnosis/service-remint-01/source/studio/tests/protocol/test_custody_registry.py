"""Native disposable-key tests, not a claim of worker isolation or public CAS."""
from __future__ import annotations

import ctypes as C
from ctypes import wintypes as W
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from host.core.custody_registry import (
    RegistryCustody, CustodyError, MAX_STATE_BYTES, BASE_PATH, _RegistryApi,
    _FORMAT, _HKCU, _ACCESS, _SecurityAttributes, pending_custody_cleanup,
)

if os.name == "nt":
    import winreg


@unittest.skipUnless(os.name == "nt", "Windows registry custody required")
class RegistryCustodyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        created = RegistryCustody.provision_base()
        print("HH_CUSTODY_BASE_PROVISION " + json.dumps({"created_components": [p.rsplit('\\', 1)[-1] for p in created]}), flush=True)

    def setUp(self):
        self.owned = []
        self.objects = []
        self.addCleanup(self.cleanup)

    def leaf(self):
        identifier = uuid.uuid4().hex
        with self.assertRaises(FileNotFoundError):
            winreg.OpenKey(winreg.HKEY_CURRENT_USER, BASE_PATH + "\\" + identifier,
                           0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
        # Exact randomly minted absent leaf only. No parent cleanup is allowed.
        self.owned.append(identifier)
        return identifier

    def create(self):
        value = RegistryCustody.create(self.leaf())
        self.objects.append(value)
        return value

    def reopen(self, identifier):
        value = RegistryCustody.reopen(identifier)
        self.objects.append(value)
        return value

    def cleanup(self):
        for value in reversed(self.objects):
            value.close()
        for value in pending_custody_cleanup():
            if isinstance(value, RegistryCustody) and value.local_id in self.owned:
                value.close()
            elif isinstance(value, _RegistryApi):
                value.close_owned()
        api = _RegistryApi()
        try:
            # NtDeleteKey deletes exactly the no-follow key handle checked below;
            # unlike recursive cleanup it cannot walk a link into its target.
            api.nt.NtDeleteKey.argtypes = [W.HANDLE]
            api.nt.NtDeleteKey.restype = W.LONG
            for identifier in reversed(self.owned):
                self.assertRegex(identifier, r"^[0-9a-f]{32}$")
                handle = W.HANDLE()
                code = api.adv.RegOpenKeyExW(_HKCU, BASE_PATH + "\\" + identifier, 8,
                    _ACCESS | 0x10000, C.byref(handle))
                if code == 2:
                    continue
                self.assertEqual(code, 0)
                api.keys.add(handle.value)
                expected = "\\REGISTRY\\USER\\" + api.owner + "\\" + BASE_PATH + "\\" + identifier
                self.assertEqual(api.native_name(handle.value).casefold(), expected.casefold())
                self.assertEqual(api.nt.NtDeleteKey(handle), 0)
                api.close_key(handle.value)
                with self.assertRaises(FileNotFoundError):
                    winreg.OpenKey(winreg.HKEY_CURRENT_USER, BASE_PATH + "\\" + identifier,
                                   0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
        finally:
            api.close_owned()

    def raw(self, identifier, name="State"):
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, BASE_PATH + "\\" + identifier,
                            0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            return winreg.QueryValueEx(key, name)

    def mutate(self, identifier, name, value, kind):
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, BASE_PATH + "\\" + identifier,
                            0, winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY) as key:
            if value is None:
                winreg.DeleteValue(key, name)
            else:
                winreg.SetValueEx(key, name, 0, kind, value)

    def test_create_store_and_fresh_process_reopen_exact_bytes(self):
        value = self.create()
        self.assertEqual(value.local_id, self.owned[-1])
        self.assertIsNone(value.read())
        self.assertEqual(self.raw(value.local_id, "Format"), (_FORMAT + value.local_id.encode(), winreg.REG_BINARY))
        value.store(b"a\0b\xff", None)
        self.assertEqual(value.read(), b"a\0b\xff")
        identifier = value.local_id
        value.close()
        code = "from host.core.custody_registry import RegistryCustody; import sys; c=RegistryCustody.reopen(sys.argv[1]); assert c.read()==b'a\\0b\\xff'; c.close(); print('CUSTODY_REOPEN_VERIFIED')"
        result = subprocess.run([sys.executable, "-B", "-c", code, identifier], cwd=ROOT,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "CUSTODY_REOPEN_VERIFIED")

    def test_binary_empty_and_maximum_are_distinct_from_absence(self):
        value = self.create()
        value.store(b"", None)
        self.assertEqual(value.read(), b"")
        value.store(b"x" * MAX_STATE_BYTES, b"")
        identifier = value.local_id
        value.close()
        self.assertEqual(self.reopen(identifier).read(), b"x" * MAX_STATE_BYTES)

    def test_invalid_ids_are_rejected_before_native_api(self):
        for identifier in (None, "", "A" * 32, "0" * 31, "0" * 33, "../outside", "0" * 32 + "\0", 123):
            with self.subTest(identifier=identifier), mock.patch("host.core.custody_registry._RegistryApi", side_effect=AssertionError("no native API")):
                with self.assertRaisesRegex(CustodyError, "LOCAL_ID_INVALID"):
                    RegistryCustody.create(identifier)

    def test_invalid_payloads_and_expected_values_have_no_write(self):
        value = self.create()
        for data in (None, "text", bytearray(b"a"), b"x" * (MAX_STATE_BYTES + 1)):
            with self.subTest(kind=type(data).__name__), self.assertRaises(CustodyError):
                value.store(data, None)
        for expected in (1, "text", bytearray(), b"x" * (MAX_STATE_BYTES + 1)):
            with self.assertRaises(CustodyError):
                value.store(b"ok", expected)
        self.assertIsNone(value.read())

    def test_conflict_does_not_set_or_poison(self):
        value = self.create()
        value.store(b"before", None)
        with mock.patch.object(value._api, "set", side_effect=AssertionError("no write")):
            for expected in (None, b"wrong"):
                with self.assertRaisesRegex(CustodyError, "STATE_CONFLICT") as error:
                    value.store(b"after", expected)
                self.assertFalse(error.exception.outcome_unknown)
        self.assertEqual(value.read(), b"before")
        value.store(b"after", b"before")

    def test_duplicate_local_owner_and_existing_create_are_refused(self):
        value = self.create()
        value.store(b"keep", None)
        with self.assertRaisesRegex(CustodyError, "LOCAL_OWNER_EXISTS"):
            RegistryCustody.reopen(value.local_id)
        value.close()
        with self.assertRaisesRegex(CustodyError, "KEY_EXISTS"):
            RegistryCustody.create(value.local_id)
        self.assertEqual(self.raw(value.local_id)[0], b"keep")

    def test_reopen_missing_is_open_only(self):
        identifier = self.leaf()
        with mock.patch.object(_RegistryApi, "create", side_effect=AssertionError("no create")):
            with self.assertRaisesRegex(CustodyError, "KEY_MISSING"):
                RegistryCustody.reopen(identifier)
        with self.assertRaises(FileNotFoundError):
            self.raw(identifier)

    def test_created_empty_key_after_exit_is_incomplete_not_a_new_store(self):
        value = self.create()
        identifier = value.local_id
        value.close()
        with self.assertRaisesRegex(CustodyError, "INCOMPLETE_PROVISIONING"):
            RegistryCustody.reopen(identifier)
        with self.assertRaisesRegex(CustodyError, "KEY_EXISTS"):
            RegistryCustody.create(identifier)

    def test_state_removed_after_provision_never_resets_to_empty(self):
        value = self.create()
        value.store(b"state", None)
        self.mutate(value.local_id, "State", None, None)
        with self.assertRaisesRegex(CustodyError, "INCOMPLETE_PROVISIONING"):
            value.read()
        value.close()
        with self.assertRaisesRegex(CustodyError, "INCOMPLETE_PROVISIONING"):
            RegistryCustody.reopen(value.local_id)

    def test_wrong_marker_wrong_type_oversize_remain_preserved(self):
        for name, data, kind, code in (("Format", b"wrong", winreg.REG_BINARY, "FORMAT_INVALID"),
                ("State", "wrong", winreg.REG_SZ, "STATE_TYPE_INVALID"),
                ("State", b"a" * (MAX_STATE_BYTES + 1), winreg.REG_BINARY, "STATE_LIMIT")):
            with self.subTest(code=code):
                value = self.create()
                value.store(b"before", None)
                value.close()
                self.mutate(value.local_id, name, data, kind)
                with self.assertRaisesRegex(CustodyError, code):
                    RegistryCustody.reopen(value.local_id)
                self.assertEqual(self.raw(value.local_id, name), (data, kind))

    def test_flush_failure_after_set_is_unknown_then_reopen_requires_barrier(self):
        value = self.create()
        value.store(b"before", None)
        original = value._api.flush
        calls = 0
        def fail_after_set(handle):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise CustodyError("INJECTED_FLUSH")
            return original(handle)
        with mock.patch.object(value._api, "flush", side_effect=fail_after_set):
            with self.assertRaisesRegex(CustodyError, "STORE_UNCERTAIN") as error:
                value.store(b"after", b"before")
        self.assertTrue(error.exception.outcome_unknown)
        self.assertEqual(self.raw(value.local_id)[0], b"after")
        with self.assertRaisesRegex(CustodyError, "RECONCILIATION_REQUIRED"):
            value.store(b"must-not-retry", b"after")
        value.close()
        with mock.patch.object(_RegistryApi, "flush", side_effect=CustodyError("INJECTED_FRESH_BARRIER")):
            with self.assertRaisesRegex(CustodyError, "FRESH_BARRIER"):
                RegistryCustody.reopen(value.local_id)
        self.assertEqual(self.reopen(value.local_id).read(), b"after")

    def test_set_failure_and_lying_set_both_poison(self):
        for failure in (CustodyError("INJECTED_SET"), None):
            value = self.create()
            value.store(b"before", None)
            with mock.patch.object(value._api, "set", side_effect=failure):
                with self.assertRaisesRegex(CustodyError, "STORE_UNCERTAIN") as error:
                    value.store(b"after", b"before")
                self.assertTrue(error.exception.outcome_unknown)
            self.assertEqual(self.raw(value.local_id)[0], b"before")
            value.close()

    def test_key_close_failure_retains_exact_handle_and_local_owner(self):
        value = self.create()
        handle, close = value._handle, value._api.close_key
        def fail_leaf(item):
            if item == handle:
                raise CustodyError("REAL_HANDLE_STILL_OPEN")
            close(item)
        with mock.patch.object(value._api, "close_key", side_effect=fail_leaf):
            with self.assertRaisesRegex(CustodyError, "CLOSE_UNCERTAIN"):
                value.close()
        self.assertEqual(value._api.keys, {handle})
        self.assertEqual(value._api.query(handle, "Format")[1], _FORMAT + value.local_id.encode())
        with self.assertRaisesRegex(CustodyError, "LOCAL_OWNER_EXISTS"):
            RegistryCustody.reopen(value.local_id)
        value.close()
        self.assertFalse(value._api.keys)

    def test_api_constructor_token_close_failure_keeps_cleanup_owner(self):
        identifier = self.leaf()
        with mock.patch.object(_RegistryApi, "close_token", side_effect=CustodyError("REAL_TOKEN_STILL_OPEN")):
            with self.assertRaisesRegex(CustodyError, "INIT_CLEANUP_UNCERTAIN") as error:
                RegistryCustody.create(identifier)
        owner = error.exception.cleanup_owner
        self.assertIsNotNone(owner)
        self.objects.append(owner)
        self.assertTrue(owner._api.tokens)
        owner.close()
        self.assertFalse(owner._api.tokens)

    def test_api_constructor_localfree_failure_keeps_allocations(self):
        identifier = self.leaf()
        with mock.patch.object(_RegistryApi, "free", side_effect=CustodyError("REAL_ALLOCATION_STILL_OWNED")):
            with self.assertRaisesRegex(CustodyError, "INIT_CLEANUP_UNCERTAIN") as error:
                RegistryCustody.create(identifier)
        owner = error.exception.cleanup_owner
        self.objects.append(owner)
        self.assertTrue(owner._api.allocations)
        owner.close()
        self.assertFalse(owner._api.allocations)

    def test_security_change_is_detected_from_actual_handle(self):
        value = self.create()
        value.store(b"before", None)
        api = value._api
        api.adv.SetSecurityInfo.argtypes = [W.HANDLE, C.c_int, W.DWORD, C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p]
        api.adv.SetSecurityInfo.restype = W.DWORD
        api.adv.GetSecurityDescriptorDacl.argtypes = [C.c_void_p, C.POINTER(W.BOOL), C.POINTER(C.c_void_p), C.POINTER(W.BOOL)]
        api.adv.GetSecurityDescriptorDacl.restype = W.BOOL
        # Separate test-owned handle has WRITE_DAC; product handles do not.
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, BASE_PATH + "\\" + value.local_id,
                            0, 0x40000 | winreg.KEY_WOW64_64KEY) as writable:
            original = api.sddl
            def apply(sddl):
                api.sddl = sddl
                try:
                    with api.descriptor() as descriptor:
                        present, defaulted, dacl = W.BOOL(), W.BOOL(), C.c_void_p()
                        self.assertTrue(api.adv.GetSecurityDescriptorDacl(descriptor, C.byref(present), C.byref(dacl), C.byref(defaulted)))
                        self.assertEqual(api.adv.SetSecurityInfo(int(writable), 4, 4 | 0x80000000, None, None, dacl, None), 0)
                finally:
                    api.sddl = original
            apply(original + "(A;;KR;;;WD)")
            try:
                with self.assertRaisesRegex(CustodyError, "SECURITY_CHANGED"):
                    value.read()
                self.assertEqual(self.raw(value.local_id)[0], b"before")
            finally:
                apply(original)

    def test_owner_comparison_and_impersonation_guard_fail_before_write(self):
        value = self.create()
        value.store(b"before", None)
        with mock.patch.object(value._api, "render_security", return_value="O:wrongD:P"), \
             mock.patch.object(value._api, "set", side_effect=AssertionError("no write")):
            with self.assertRaisesRegex(CustodyError, "SECURITY_CHANGED"):
                value.store(b"after", b"before")
        value.close()
        value = self.reopen(value.local_id)
        with mock.patch.object(value._api, "no_impersonation", side_effect=CustodyError("CUSTODY_IMPERSONATION_UNSUPPORTED")), \
             mock.patch.object(value._api, "set", side_effect=AssertionError("no write")):
            with self.assertRaisesRegex(CustodyError, "IMPERSONATION_UNSUPPORTED"):
                value.store(b"after", b"before")

    def test_native_registry_symbolic_link_is_rejected_without_target_write(self):
        target = self.create()
        target.store(b"untouched", None)
        identifier = self.leaf()
        api = target._api
        base, _, _ = api.base()
        handle, disposition = W.HANDLE(), W.DWORD()
        with api.descriptor() as descriptor:
            attributes = _SecurityAttributes(C.sizeof(_SecurityAttributes), descriptor, False)
            result = api.adv.RegCreateKeyExW(base, identifier, 0, None, 2, _ACCESS,
                                           C.byref(attributes), C.byref(handle), C.byref(disposition))
        self.assertEqual(result, 0)
        api.keys.add(handle.value)
        self.assertEqual(disposition.value, 1)
        path = target._path.encode("utf-16-le")
        buffer = C.create_string_buffer(path)
        self.assertEqual(api.adv.RegSetValueExW(handle, "SymbolicLinkValue", 0, 6, buffer, len(path)), 0)
        api.close_key(handle.value)
        with self.assertRaises(CustodyError):
            RegistryCustody.reopen(identifier)
        self.assertEqual(target.read(), b"untouched")

    def test_reprovision_existing_base_does_not_set_security_or_values(self):
        with mock.patch.object(_RegistryApi, "create", side_effect=AssertionError("no create")), \
             mock.patch.object(_RegistryApi, "set", side_effect=AssertionError("no write")):
            self.assertEqual(RegistryCustody.provision_base(), ())

    def test_actual_process_cuts_leave_incomplete_or_flush_reconcilable_state(self):
        code = r'''import os,sys
from host.core.custody_registry import RegistryCustody
c=RegistryCustody.create(sys.argv[1])
phase=sys.argv[2]
if phase=='empty':
 print('CUSTODY_CUT_ARMED empty',flush=True); os._exit(81)
original=c._api.flush
count=0
def cut(handle):
 global count
 count+=1
 if count==2:
  if phase=='after_barrier': original(handle)
  print('CUSTODY_CUT_ARMED '+phase,flush=True); os._exit(81)
 original(handle)
c._api.flush=cut
c.store(b'complete-state',None)
raise AssertionError('cut not reached')
'''
        for phase in ("empty", "before_barrier", "after_barrier"):
            identifier = self.leaf()
            result = subprocess.run([sys.executable, "-B", "-c", code, identifier, phase],
                                    cwd=ROOT, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 81, result.stderr)
            self.assertEqual(result.stdout.strip(), "CUSTODY_CUT_ARMED " + phase)
            if phase == "empty":
                with self.assertRaisesRegex(CustodyError, "INCOMPLETE_PROVISIONING"):
                    RegistryCustody.reopen(identifier)
            else:
                self.assertEqual(self.reopen(identifier).read(), b"complete-state")
            print("HH_CUSTODY_ACTUAL_CUT " + json.dumps({"phase":phase,"actual_exit":result.returncode}), flush=True)

    def test_unfinished_native_link_object_cannot_become_custody(self):
        identifier = self.leaf()
        api = _RegistryApi()
        try:
            base, _, _ = api.base()
            handle, disposition = W.HANDLE(), W.DWORD()
            with api.descriptor() as descriptor:
                attributes = _SecurityAttributes(C.sizeof(_SecurityAttributes), descriptor, False)
                self.assertEqual(api.adv.RegCreateKeyExW(base, identifier, 0, None, 2, _ACCESS,
                    C.byref(attributes), C.byref(handle), C.byref(disposition)), 0)
            api.keys.add(handle.value)
            self.assertEqual(disposition.value, 1)
            with self.assertRaises(CustodyError):
                RegistryCustody.reopen(identifier)
        finally:
            api.close_owned()


if __name__ == "__main__":
    unittest.main(verbosity=2)
