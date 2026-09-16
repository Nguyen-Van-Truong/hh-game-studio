"""In-memory artifact tampering only; never opens an engine or journal owner."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('client_component_audit', HERE / 'verify_evidence.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
PACKAGE = HERE.parent / audit.DEFAULT_PACKAGE


class EvidenceTests(unittest.TestCase):
    def relative(self, path):
        return path.relative_to(audit.ROOT).as_posix()

    def changes(self, name, change):
        path = PACKAGE / name
        value = json.loads(path.read_bytes())
        change(value)
        return {self.relative(path): json.dumps(value).encode()}

    def client_changes(self, change):
        path = PACKAGE / 'client.json'
        value = json.loads(path.read_bytes())
        change(value)
        return {self.relative(path): json.dumps(value).encode(),
            self.relative(PACKAGE / 'client-stdout.txt'):
                ('GT04_HTTP_CLIENT_COMPLETE ' + json.dumps(value) + '\n').encode()}

    def reject(self, overrides, label):
        with self.assertRaisesRegex(ValueError, label):
            audit.verify(overrides=overrides)

    def test_complete_component_bindings(self):
        result = audit.verify()
        self.assertTrue(result['passed'])
        self.assertFalse(result['formal_acceptance'])
        self.assertEqual(result['http_calls'], 15)

    def test_incomplete_capture_rejected(self):
        self.reject(self.changes('capture.json', lambda x: x.update(native_completion=False)),
                    'completed candidate')

    def test_failed01_cannot_be_promoted(self):
        self.failed_package('01')

    def test_failed02_cannot_be_promoted(self):
        self.failed_package('02')

    def test_failed03_child_success_cannot_promote_parent(self):
        self.failed_package('03')

    def failed_package(self, number):
        name = '20260917-gt04-client-' + number
        source = json.loads((HERE.parent / name / 'source-closure.json').read_bytes())
        with self.assertRaisesRegex(ValueError, 'completed candidate'):
            audit.verify(name, expected_closure=source['source_closure_sha256'])

    def test_changed_closure_rejected(self):
        self.reject(self.changes('source-closure.json', lambda x: x.update(source_closure_sha256='0'*64)),
                    'closure digest')

    def test_changed_frozen_file_rejected_before_import(self):
        path = PACKAGE / 'source/studio/host/blender/client_owner.py'
        self.reject({self.relative(path): path.read_bytes() + b'\n# changed\n'}, 'frozen source inventory')

    def test_raw_actual_exit_rejected(self):
        self.reject(self.changes('native-host.json', lambda x: x.update(exit_code=1)), 'actual native exit')

    def test_wrapper_exit_rejected(self):
        self.reject(self.changes('capture.json', lambda x: x['host'].update(wrapper_exit_code=1)), 'actual native exit')

    def test_unverified_tree_rejected(self):
        self.reject(self.changes('capture.json', lambda x: x['unit'].update(tree_verified=False)), 'actual unit exit')

    def test_missing_unit_inventory_marker_rejected(self):
        path = PACKAGE / 'unit-stdout.txt'
        data = b'\n'.join(line for line in path.read_bytes().splitlines() if not line.startswith(b'GT04_UNIT_INVENTORY '))
        self.reject({self.relative(path): data}, 'unit markers')

    def test_raw_unit_result_tamper_rejected(self):
        path = PACKAGE / 'unit-stderr.txt'
        self.reject({self.relative(path): path.read_bytes().replace(b'... ok', b'... FAIL', 1)}, 'raw unit inventory')

    def test_client_exit_rejected(self):
        self.reject(self.changes('client-exit.json', lambda x: x.update(exit_code=9)), 'independent client')

    def test_scanner_check_missing_rejected(self):
        self.reject(self.changes('native.json', lambda x: x['checks'].pop(0)), 'required native check inventory')

    def test_native_cleanup_job_active_rejected(self):
        gui = next(PACKAGE.glob('blender-*'))
        closed = json.loads((gui / 'close.json').read_bytes())
        closed['job']['active_count'] = 1
        changes = self.changes('native.json', lambda x: x.update(cleanup=closed))
        changes[self.relative(gui / 'close.json')] = json.dumps(closed).encode()
        self.reject(changes, 'native Job cleanup')

    def test_discovery_catalog_changed_rejected(self):
        def change(client):
            wire = json.loads(client['calls'][0]['response_wire'])
            wire['schema_digest'] = 'sha256:' + '0'*64
            protocol = audit.pure_protocol(PACKAGE / 'source/studio')
            client['calls'][0]['response_wire'] = protocol.canonical_bytes(wire).decode()
            client['artifacts']['discovery'] = wire
        self.reject(self.client_changes(change), 'exact Discovery')

    def test_duplicate_wire_changed_rejected(self):
        def change(client):
            wire = json.loads(client['calls'][6]['response_wire'])
            wire['code'] = 'WRONG_CACHED_RESULT'
            protocol = audit.pure_protocol(PACKAGE / 'source/studio')
            client['calls'][6]['response_wire'] = protocol.canonical_bytes(wire).decode()
        self.reject(self.client_changes(change), 'exact duplicate and lookup wires')

    def test_result_hash_changed_rejected(self):
        def change(client):
            wire = copy.deepcopy(client['artifacts']['response'])
            wire['result_hash'] = 'sha256:' + '0'*64
            protocol = audit.pure_protocol(PACKAGE / 'source/studio')
            text = protocol.canonical_bytes(wire).decode()
            client['calls'][5]['response_wire'] = text
            client['artifacts'].update(response=wire, response_wire=text)
        self.reject(self.client_changes(change), 'read response/hash')

    def test_wrong_lookup_caller_rejected(self):
        self.reject(self.client_changes(lambda x: x['calls'][8].update(client_role='primary')), 'HTTP route/caller')

    def test_stop_sent_to_work_listener_rejected(self):
        self.reject(self.client_changes(lambda x: x['calls'][12].update(listener='work')), 'HTTP listener isolation')

    def test_wrong_lookup_command_rejected(self):
        self.reject(self.client_changes(lambda x: x['calls'][14]['request'].update(command_id='other')), 'lookup command binding')

    def test_bearer_header_in_retained_evidence_rejected(self):
        self.reject(self.client_changes(lambda x: x.update(injected_note='Bearer ' + 'A'*43)), 'bearer header in evidence')


if __name__ == '__main__':
    unittest.main()
