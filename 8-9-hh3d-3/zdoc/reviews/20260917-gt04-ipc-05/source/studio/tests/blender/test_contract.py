import copy
import importlib.util
import json
from pathlib import Path
import threading
import unittest

ADDON = Path(__file__).resolve().parents[2] / "blender-addon"
spec = importlib.util.spec_from_file_location("gt04_test_adapter", ADDON / "adapter.py")
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)
c = adapter.contract


def command(operation="mesh.create_box"):
    return {"schema": c.SCHEMA, "command_id": "create-1", "operation": operation,
            "expected_revision": "sha256:" + "1" * 64,
            "expected_context": {"mode": "OBJECT", "active_id": None, "selected_ids": []},
            "payload": {"object_id": "box-1", "size": [1, 2, 3]}}


class ContractTests(unittest.TestCase):
    def test_create_roundtrip_detached(self):
        value = command()
        checked = c.parse(c.canonical(value))
        checked["payload"]["size"][0] = 9
        self.assertEqual(value["payload"]["size"][0], 1)

    def test_inspect(self):
        value = command("scene.inspect")
        value.update(expected_revision=None, expected_context=None, payload={})
        self.assertEqual(c.validate(value), value)

    def test_transform(self):
        value = command("object.transform.set")
        value["payload"] = {"object_id": "box", "location": [1, 2, 3], "rotation": [0, 0.5, 0], "scale": [1, 2, 1]}
        self.assertEqual(c.validate(value), value)

    def test_exact_fields_all_levels(self):
        for target in ("top", "payload", "expected_context"):
            value = command()
            (value if target == "top" else value[target])["script"] = "no"
            with self.subTest(target=target), self.assertRaises(c.Rejected):
                c.validate(value)

    def test_missing_fields(self):
        for key in command():
            value = command()
            del value[key]
            with self.subTest(key=key), self.assertRaises(c.Rejected):
                c.validate(value)

    def test_unsupported_operation(self):
        for op in ("python.exec", "save", "file.open", None, True, []):
            value = command()
            value["operation"] = op
            with self.subTest(op=op), self.assertRaises(c.Rejected):
                c.validate(value)

    def test_ids_are_not_paths(self):
        for identifier in ("../box", "C:\\box", "\\\\host\\box", "box/child", "é", "a" * 49, 1, ""):
            value = command()
            value["payload"]["object_id"] = identifier
            with self.subTest(identifier=identifier), self.assertRaises(c.Rejected):
                c.validate(value)

    def test_numbers(self):
        for number in (True, None, "1", float("nan"), float("inf"), 0, -1, 1001, 10 ** 1000):
            value = command()
            value["payload"]["size"][0] = number
            with self.subTest(number=str(number)[:20]), self.assertRaises(c.Rejected):
                c.validate(value)

    def test_wrong_vector_shape(self):
        for vector in ([1, 2], [1, 2, 3, 4], {"x": 1}, (1, 2, 3)):
            value = command()
            value["payload"]["size"] = vector
            with self.subTest(vector=vector), self.assertRaises(c.Rejected):
                c.validate(value)

    def test_revision_required(self):
        for revision in (None, "", "sha256:" + "A" * 64, True):
            value = command()
            value["expected_revision"] = revision
            with self.subTest(revision=revision), self.assertRaises(c.Rejected):
                c.validate(value)

    def test_selection_and_mode(self):
        for context in ({"mode": "SCULPT", "active_id": None, "selected_ids": []},
                        {"mode": "EDIT_MESH", "active_id": "a", "selected_ids": []},
                        {"mode": "OBJECT", "active_id": "a", "selected_ids": ["a", "a"]},
                        {"mode": "OBJECT", "active_id": None, "selected_ids": ["b", "a"]}):
            value = command()
            value["expected_context"] = context
            with self.subTest(context=context), self.assertRaises(c.Rejected):
                c.validate(value)

    def test_duplicate_json_and_nonfinite(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'\xff', b'[]', b'null'):
            with self.subTest(raw=raw), self.assertRaises(c.Rejected):
                c.parse(raw)

    def test_size_and_depth_limits(self):
        for raw in (b" " * 4097, b"[" * 2000 + b"]" * 2000, "{}"):
            with self.assertRaises(c.Rejected):
                c.parse(raw)

    def test_main_thread_guard_before_bpy_import(self):
        outcomes = []
        def worker():
            try:
                adapter.FixtureAdapter()
            except c.Rejected as exc:
                outcomes.append(str(exc))
        thread = threading.Thread(target=worker)
        thread.start()
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(outcomes, ["MAIN_THREAD_REQUIRED"])


if __name__ == "__main__":
    unittest.main()
