"""Offline reader controls, including missing/ambiguous lifecycle rejection."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
RUN = Path(__file__).parents[3] / 'studio/.local/reviews/gt06-s119-lookup-boundary-01'
spec = importlib.util.spec_from_file_location('v2', HERE / 'read_terminal_v2.py')
v2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(v2)


class ReaderV2Controls(unittest.TestCase):
    def correlation_inputs(self):
        final = json.loads((RUN/'attempt/http-phases-final.json').read_bytes())['observation']
        timings = json.loads((RUN/'timing-summary.json').read_bytes())['timings']
        return final['first_failure'], final, timings

    def test_real_boundary_is_bounded(self):
        report = v2.summarize(RUN)
        self.assertEqual('OBSERVED_BOUNDARY', report['correlation']['status'])
        self.assertTrue(report['correlation']['lookup_started_after_client_timeout'])
        self.assertEqual(4, len(report['correlation']['matched_timings']))

    def test_preceding_reload_cannot_be_labeled_append(self):
        report = v2.summarize(RUN)
        self.assertEqual('journal.reload', report['correlation']['matched_timings'][0]['phase'])
        self.assertNotEqual('journal.append', report['correlation']['matched_timings'][0]['phase'])

    def test_missing_http_returns_unknown_without_shortcutting_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ('result.json', 'freeze.json', 'attempt/context.json',
                         'owned/process-exit.json', 'timing-summary.json'):
                source = RUN / name
                target = root / name; target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
            report = v2.summarize(root)
            self.assertEqual('UNKNOWN', report['correlation']['status'])
            self.assertEqual('MISSING_HTTP_OR_TIMING', report['correlation']['reason'])

    def test_wrong_pid_rejected_even_without_http(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root/'attempt').mkdir(); (root/'owned').mkdir()
            for name in ('result.json','freeze.json','attempt/context.json',
                         'owned/process-exit.json','timing-summary.json'):
                source = RUN / name; target=root/name; target.write_bytes(source.read_bytes())
            exit_path=root/'owned/process-exit.json'; value=json.loads(exit_path.read_bytes()); value['pid'] += 1
            exit_path.write_text(json.dumps(value), encoding='utf8')
            with self.assertRaisesRegex(ValueError, 'TARGET_EXIT_BINDING'):
                v2.summarize(root)

    def test_conflicting_duplicate_event_rejected(self):
        source = json.loads((RUN/'attempt/http-phases-final.json').read_bytes())
        first = source['observation']['first_failure']; final = source['observation']
        altered = copy.deepcopy(final['events'][0]); altered['phase'] = 'tampered'
        with self.assertRaisesRegex(ValueError, 'EVENT_CONFLICT'):
            v2.merged_events(first, {'events': final['events'] + [altered],
                                     'spans_dropped': False, 'identity_missing': False})

    def test_missing_target_lifecycle_stays_unknown(self):
        first, final, timings = self.correlation_inputs()
        for window in (first, final):
            window['events'] = [e for e in window['events']
                if not (e['span_id'] == 253729 and e['kind'] == 'enter')]
        self.assertEqual('UNKNOWN', v2.correlate(first, final, timings)['status'])

    def test_unrelated_historical_evictions_do_not_invent_a_gap(self):
        first, final, timings = self.correlation_inputs()
        self.assertGreater(first['events_evicted'], 0)
        self.assertEqual('OBSERVED_BOUNDARY', v2.correlate(first, final, timings)['status'])

    def test_actual_dropped_identity_stays_unknown(self):
        first, final, timings = self.correlation_inputs()
        first['identity_missing'] = 1
        self.assertEqual('UNKNOWN', v2.correlate(first, final, timings)['status'])

    def test_wrong_port_pair_stays_unknown(self):
        first, final, timings = self.correlation_inputs()
        for window in (first, final):
            for event in window['events']:
                if event['span_id'] == 253728:
                    event['client_port'] = 60000
        self.assertEqual('UNKNOWN', v2.correlate(first, final, timings)['status'])

    def test_wrong_timing_thread_not_joined(self):
        first, final, timings = self.correlation_inputs()
        for aggregate in timings.values():
            for row in aggregate['slowest']:
                row['thread_id'] = -1
        result = v2.correlate(first, final, timings)
        self.assertEqual('UNKNOWN', result['status'])
        self.assertEqual([], result['matched_timings'])

    def test_same_thread_overlap_outside_parent_is_not_containment(self):
        first, final, timings = self.correlation_inputs()
        reload = copy.deepcopy(timings['coupled.reload']['slowest'][1])
        reload.update(start_ns=724222657945800, end_ns=724223802863300,
                      enclosing_scope='append', thread_id=41852)
        timings['coupled.sqlite_commit']['slowest'] = [reload]
        result = v2.correlate(first, final, timings)
        self.assertFalse(any(r['label'] == 'coupled.sqlite_commit' for r in result['matched_timings']))

    def test_wrong_source_or_profile_rejected_before_missing_http_return(self):
        for field in ('source_closure_sha256', 'profile_sha256', 'run_id'):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                for name in ('result.json','freeze.json','attempt/context.json',
                             'owned/process-exit.json','timing-summary.json'):
                    target=root/name; target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes((RUN/name).read_bytes())
                context=root/'attempt/context.json'; value=json.loads(context.read_bytes())
                value[field] = 'changed'
                context.write_text(json.dumps(value), encoding='utf8')
                with self.assertRaisesRegex(ValueError, 'RUN_SOURCE_PROFILE_BINDING'):
                    v2.summarize(root)


if __name__ == '__main__':
    unittest.main()
