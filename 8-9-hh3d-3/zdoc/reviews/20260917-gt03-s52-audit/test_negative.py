"""Focused corruption tests; read saved evidence only, never run engines."""
from __future__ import annotations
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('s52_integration_negative_auditor', HERE / 'verify_integration.py')
A = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = A
exec(compile(spec.loader.get_data(str(HERE / 'verify_integration.py')), str(HERE / 'verify_integration.py'), 'exec'), A.__dict__)
HAPPY = A.REVIEWS / '20260917-gt03-s52-publication-05'
STOP = A.REVIEWS / '20260917-gt03-s52-stop-01'


class OverlayEvidence(A.Evidence):
    """Only parsed copies change; original bytes and inventories stay intact."""
    def __init__(self, path, change):
        super().__init__()
        self.path, self.change = path.resolve(), change

    def read(self, path):
        value = super().read(path)
        if Path(path).resolve() == self.path:
            value = copy.deepcopy(value)
            self.change(value)
        return value


class CorruptionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = [A.source(A.Evidence(), package) for package in (HAPPY, STOP)]
        root = cls.sources[0][0]
        sys.path.insert(0, str(root.parent))
        cls.modules = tuple(A.H.module('s52_negative_' + name, root / relative) for name, relative in (
            ('validation', 'godot-addon/validation_owner.py'),
            ('linux', 'tests/godot/run_linux_probe.py'),
            ('state', 'godot-addon/publication_state_v3.py'),
            ('editor', 'godot-addon/editor_owner.py')))

    def test_runtime_file_map_substitution_rejected(self):
        maps = [copy.deepcopy(item[1]) for item in self.sources]
        A.same_runtime(maps)  # The real runner-only difference is allowed.
        name = next(iter(A.runtime_map(maps[1])))
        maps[1][name] = '0' * 64 if maps[1][name] != '0' * 64 else '1' * 64
        with self.assertRaisesRegex(ValueError, 'runtime per-file maps differ'):
            A.same_runtime(maps)

    def test_completed_response_and_event_substitution_rejected(self):
        def change_response(value):
            value['postconditions']['durable_receipt_sha256'] = '0' * 64
        evidence = OverlayEvidence(HAPPY / 'response.json', change_response)
        with self.assertRaisesRegex(ValueError, 'durable response/reopen receipt binding'):
            A.verify_happy(evidence, HAPPY, self.sources[0][0], self.sources[0][2], self.modules)
        events = A.H.read(HAPPY / 'events.json')
        event = copy.deepcopy(next(row['adoption'] for row in events if row['kind'] == 'READBACK'))
        observation = A.H.read(next((HAPPY / 'owned/editor').glob('editor-*/adoption-*.json')))
        A.bind_editor_event(event, observation, adoption=True)
        event['effect_completed_ms'] += 1
        with self.assertRaisesRegex(ValueError, 'event observation differs: effect_completed_ms'):
            A.bind_editor_event(event, observation, adoption=True)

    def test_stop_response_after_actual_native_exit_rejected(self):
        timing = A.H.read(STOP / 'timing.json')
        native = A.H.read(STOP / timing['native_result_relative'])
        finished = A.milliseconds(native['container_state']['FinishedAt'])
        def change_timing(value):
            value['stop_completed_ms'] = finished + 1
            value['validation_returned_ms'] = max(value['validation_returned_ms'], finished + 2)
        evidence = OverlayEvidence(STOP / 'timing.json', change_timing)
        with self.assertRaisesRegex(ValueError, 'Stop time not inside actual native run'):
            A.verify_stop(evidence, STOP, self.sources[1][0], self.sources[1][2], self.modules)

    def test_bool_host_exit_and_unclean_tree_rejected(self):
        host = A.H.read(HAPPY / 'capture.json')['host']
        raw_path = (HAPPY / host['host']).resolve()
        original_read = A.H.read
        def bool_exit(path):
            value = original_read(path)
            if Path(path).resolve() == raw_path:
                value = copy.deepcopy(value)
                value['exit_code'] = False  # Python equality alone treats False as zero.
            return value
        with patch.object(A.H, 'read', side_effect=bool_exit):
            with self.assertRaisesRegex(ValueError, 'actual host exit mismatch'):
                A.H.host(HAPPY, host)
        unclean = copy.deepcopy(host)
        unclean['tree_verified'] = False
        with self.assertRaisesRegex(ValueError, 'unclean Windows process ownership'):
            A.H.host(HAPPY, unclean)


def main():
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CorruptionTests)
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    value = {'passed': result.wasSuccessful(), 'run': result.testsRun,
        'failures': len(result.failures), 'errors': len(result.errors), 'skips': len(result.skipped),
        'read_only_evidence': True, 'native_processes_launched': False,
        'formal_acceptance': False, 'audit_sha256': A.sha(HERE / 'verify_integration.py'),
        'test_sha256': A.sha(Path(__file__)), 'output': stream.getvalue()}
    (HERE / 'negative-results.json').write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    print(stream.getvalue(), end='')
    print(json.dumps({key: item for key, item in value.items() if key != 'output'}, sort_keys=True))
    return int(not result.wasSuccessful())


if __name__ == '__main__':
    raise SystemExit(main())
