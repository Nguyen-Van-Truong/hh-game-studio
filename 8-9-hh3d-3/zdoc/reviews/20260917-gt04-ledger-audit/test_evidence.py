"""In-memory corruption checks; no native engine, lock or storage access."""
import json
import unittest
import verify_evidence as audit


class CorruptionTests(unittest.TestCase):
    def reject_json(self, name, change):
        path = audit.PACKAGE / name
        value = json.loads(path.read_bytes())
        change(value)
        with self.assertRaises((ValueError, RuntimeError, AssertionError)):
            audit.verify({path.relative_to(audit.ROOT).as_posix(): json.dumps(value).encode()})

    def test_nonzero_actual_target_exit(self):
        self.reject_json('native-host.json', lambda value: value.update(exit_code=1))

    def test_false_is_not_integer_exit_zero(self):
        self.reject_json('unit-host.json', lambda value: value.update(exit_code=False))

    def test_native_result_hash_changed(self):
        def change(value):
            wire = json.loads(value['artifacts']['terminal_wire'])
            wire['result_hash'] = 'sha256:' + '0' * 64
            value['artifacts']['terminal_wire'] = json.dumps(wire)
        self.reject_json('ledger-native.json', change)

    def test_foreign_owner_pin(self):
        self.reject_json('ledger-native.json', lambda value:
            value['artifacts']['ledger_binding'].update(owner_pin_sha256='sha256:' + '0' * 64))

    def test_unresolved_promoted_to_commit(self):
        def change(value):
            wire = json.loads(value['artifacts']['unresolved_wire'])
            wire['status'] = 'COMMITTED'
            value['artifacts']['unresolved_wire'] = json.dumps(wire)
        self.reject_json('ledger-native.json', change)

    def test_redispatch_count_changed(self):
        self.reject_json('ledger-native.json', lambda value:
            value['artifacts'].update(native_submissions_after=99))

    def test_false_public_write_claim(self):
        self.reject_json('capture.json', lambda value: value.update(public_write_facade=True))

    def test_source_byte_changed(self):
        path = audit.SOURCE / 'host/blender/client_ledger.py'
        with self.assertRaisesRegex(ValueError, 'snapshot inventory'):
            audit.verify({path.relative_to(audit.ROOT).as_posix(): path.read_bytes() + b'\n'})

    def test_truncated_journal_snapshot(self):
        path = audit.PACKAGE / 'intent-before-native.jsonl'
        with self.assertRaisesRegex(ValueError, 'artifact hash'):
            audit.verify({path.relative_to(audit.ROOT).as_posix(): path.read_bytes()[:-1]})


if __name__ == '__main__':
    unittest.main()
