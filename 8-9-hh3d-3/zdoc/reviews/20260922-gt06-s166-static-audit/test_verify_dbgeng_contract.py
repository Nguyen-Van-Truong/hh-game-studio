import importlib.util
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("verify_dbgeng_contract", HERE / "verify_dbgeng_contract.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


HEADER = """
DECLARE_INTERFACE_(IDebugClient, IUnknown)
{
STDMETHOD(QueryInterface)(THIS_ REFIID id, PVOID* out) PURE;
STDMETHOD_(ULONG, AddRef)(THIS) PURE;
STDMETHOD_(ULONG, Release)(THIS) PURE;
STDMETHOD(CreateProcess)(THIS) PURE;
};
DECLARE_INTERFACE_(IDebugControl, IUnknown)
{
STDMETHOD(QueryInterface)(THIS_ REFIID id, PVOID* out) PURE;
STDMETHOD_(ULONG, AddRef)(THIS) PURE;
STDMETHOD_(ULONG, Release)(THIS) PURE;
STDMETHODV(Output)(THIS_ ULONG mask, PCSTR format, ...) PURE;
STDMETHOD(WaitForEvent)(THIS) PURE;
};
DECLARE_INTERFACE_(IDebugSystemObjects, IUnknown)
{
STDMETHOD(QueryInterface)(THIS_ REFIID id, PVOID* out) PURE;
STDMETHOD_(ULONG, AddRef)(THIS) PURE;
STDMETHOD_(ULONG, Release)(THIS) PURE;
STDMETHOD(GetCurrentProcessSystemId)(THIS) PURE;
};
"""


class ContractTests(unittest.TestCase):
    def test_variadic_macro_and_slots_are_counted(self):
        parsed = {name: MODULE.interface_methods(HEADER, name) for name in MODULE.INTERFACES.values()}
        self.assertEqual(parsed["IDebugControl"], ["QueryInterface", "AddRef", "Release", "Output", "WaitForEvent"])

    def test_correct_literal_calls_pass(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "harness.cs"
            path.write_text(
                "M<CreateProcessDelegate>(client, 3); Method<WaitForEventDelegate>(control, 4); "
                "M<GetCurrentProcessSystemIdDelegate>(systems, 3);",
                encoding="utf-8",
            )
            header = Path(td) / "header.h"
            header.write_text(HEADER, encoding="utf-8")
            result = MODULE.verify(header, [path])
            self.assertTrue(result["pass"])
            self.assertEqual(result["calls_checked"], 3)
            self.assertEqual(result["source_sha256"][str(path.resolve())], MODULE.sha256(path))
            self.assertFalse(result["attribution_proven"])

    def test_tampered_slot_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "harness.cs"
            path.write_text("M<WaitForEventDelegate>(control, 3);", encoding="utf-8")
            methods = {name: MODULE.interface_methods(HEADER, name) for name in MODULE.INTERFACES.values()}
            calls = MODULE.source_calls(path, methods)
            self.assertFalse(calls[0]["valid"])
            self.assertEqual(calls[0]["error"], "slot_name_mismatch")

    def test_comments_and_strings_do_not_create_calls(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "harness.cs"
            path.write_text('// M<WaitForEventDelegate>(control, 99);\n'
                            'string s = "M<WaitForEventDelegate>(control, 98)";\n'
                            'M<WaitForEventDelegate>(control, 4);', encoding="utf-8")
            methods = {name: MODULE.interface_methods(HEADER, name) for name in MODULE.INTERFACES.values()}
            calls = MODULE.source_calls(path, methods)
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0]["line"], 3)
            self.assertTrue(calls[0]["valid"])

    def test_dynamic_slot_and_empty_source_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "harness.cs"
            methods = {name: MODULE.interface_methods(HEADER, name) for name in MODULE.INTERFACES.values()}
            for text in ("M<WaitForEventDelegate>(control, chosenIndex);", "// no calls"):
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError):
                    MODULE.source_calls(path, methods)

    def test_unknown_object_and_out_of_range_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "harness.cs"
            path.write_text("M<WaitForEventDelegate>(other, 4); M<WaitForEventDelegate>(control, 99);", encoding="utf-8")
            methods = {name: MODULE.interface_methods(HEADER, name) for name in MODULE.INTERFACES.values()}
            calls = MODULE.source_calls(path, methods)
            self.assertEqual([c["error"] for c in calls], ["unbound_object", "slot_out_of_range"])

    def test_unsupported_macro_is_not_silently_omitted(self):
        with self.assertRaisesRegex(ValueError, "unparsed"):
            MODULE.interface_methods(HEADER.replace("STDMETHODV(Output)", "UNKNOWN_MACRO(Output)"), "IDebugControl")

    def test_duplicate_or_missing_iunknown_rejected(self):
        for header in (HEADER.replace("WaitForEvent", "Output"), HEADER.replace("AddRef", "WrongRef")):
            with self.assertRaises(ValueError):
                MODULE.interface_methods(header, "IDebugControl")


if __name__ == "__main__":
    unittest.main()
