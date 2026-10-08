"""Codec/lifecycle tests only; no claim of native driver protection."""
import hashlib
import hmac
import importlib.util
import io
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('gameplay_attribution_tested',
    Path(__file__).resolve().parents[2] / 'godot-addon/gameplay_attribution.py')
codec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(codec)
CONTEXT = {'run_id': 'hh-gt03-test', 'source_closure_sha256': 'a' * 64,
           'input_manifest_sha256': 'b' * 64}
SCRIPTS = ['scripts/fixture_actor.gd']
GUARDS = {**codec.GUARD_FACTS, 'parent_mem_errno': 13, 'parent_fd_errno': 13,
          'project_write_errno': 30, 'root_write_errno': 30, 'guard_cloexec': 1}


def transcript(codes=(0, 0, 0), payload=b'candidate says HH_GAMEPLAY_PHASE_END play 0\n'):
    stream = io.BytesIO()
    writer = codec.Recorder(stream, CONTEXT)
    for index, (phase, script) in enumerate((('parse', SCRIPTS[0]), ('import', None), ('play', None))):
        pid = 10 + index
        writer.begin_child(phase, script, pid)
        writer.guard(pid, dict(GUARDS))
        writer.output(pid, 'stdout', payload)
        writer.end_child(pid, codes[index], reaped=True, pipe_eof=[True, True, True])
        if codes[index]:
            break
    writer.finish(45 if any(codes) else 0)
    return stream.getvalue()


def verify(wire):
    return codec.verify(wire, context=CONTEXT, scripts=SCRIPTS)


def reencode(rows, *, resign=False):
    if resign:
        key = bytes.fromhex(rows[-1]['reveal'])
        for row in rows[1:-1]:
            body = {'seq': row['seq'], 'event': row['event']}
            row['mac'] = hmac.new(key, codec.DOMAIN + codec.canonical(body), hashlib.sha256).hexdigest()
    return b''.join(codec.canonical(row) + b'\n' for row in rows)


class GameplayAttributionTests(unittest.TestCase):
    def test_two_observations_must_precede_candidate_execution(self):
        def wire(phases):
            stream = io.BytesIO()
            writer = codec.Recorder(stream, CONTEXT)
            for index, (phase, script) in enumerate(phases):
                pid = index + 10
                writer.begin_child(phase, script, pid)
                writer.guard(pid, dict(GUARDS))
                writer.output(pid, 'stdout', b'observer' if phase.startswith('dependencies') else b'candidate')
                writer.end_child(pid, 0, reaped=True, pipe_eof=[True] * 3)
            writer.finish(0)
            return stream.getvalue()
        candidate = [('parse', SCRIPTS[0]), ('import', None), ('play', None)]
        safe = [('dependencies', None), ('dependencies_reopen', None)] + candidate
        result = verify(wire(safe))
        self.assertEqual([r['phase'] for r in result['dependency_observations']],
                         ['dependencies', 'dependencies_reopen'])
        for unsafe in ([safe[0]] + candidate[:2] + [safe[1], candidate[2]],
                       [safe[0], candidate[0], safe[1]] + candidate[1:]):
            with self.subTest(unsafe=unsafe), self.assertRaisesRegex(codec.AttributionError,
                                                                     'ATTRIBUTION_PHASE_ORDER'):
                verify(wire(unsafe))

    def test_roundtrip_does_not_promote_child_markers(self):
        result = verify(transcript())
        self.assertEqual([r['phase'] for r in result['phase_results']], ['parse', 'import', 'play'])
        self.assertEqual([r['returncode'] for r in result['phase_results']], [0, 0, 0])
        self.assertIn(b'HH_GAMEPLAY_PHASE_END', result['child_stdout'])
        self.assertFalse(result['child_claims_authenticated'])
        self.assertFalse(result['dependency_closure_verified'])

    def test_actual_failure_stops_later_phases(self):
        result = verify(transcript((0, -9, 0)))
        self.assertEqual([r['returncode'] for r in result['phase_results']], [0, -9])
        self.assertEqual(result['driver_returncode'], 45)

    def test_boundary_facts_require_actual_denials_not_false_zero_or_missing(self):
        self.assertTrue(codec.valid_guard(dict(GUARDS)))
        for key in GUARDS:
            for value in (0, False, None):
                facts = {**GUARDS, key: value}
                with self.subTest(key=key, value=value):
                    self.assertFalse(codec.valid_guard(facts))
            facts = dict(GUARDS)
            del facts[key]
            self.assertFalse(codec.valid_guard(facts))

    def test_never_reveals_with_live_child_or_uncertain_pipe(self):
        stream = io.BytesIO()
        writer = codec.Recorder(stream, CONTEXT)
        writer.begin_child('parse', SCRIPTS[0], 8)
        with self.assertRaises(codec.AttributionError):
            writer.finish(0)
        for reaped, eof in ((False, [True]*3), (True, [True, True, False]), (True, [1]*3)):
            with self.subTest(reaped=reaped, eof=eof), self.assertRaises(codec.AttributionError):
                writer.end_child(8, 0, reaped=reaped, pipe_eof=eof)
        self.assertNotIn(b'"reveal"', stream.getvalue())
        with self.assertRaises(codec.AttributionError):
            verify(stream.getvalue())

    def test_forged_outer_markers_and_partial_or_extra_wire_fail(self):
        wire = transcript()
        lines = wire.splitlines(keepends=True)
        bad = [b'HH_GAMEPLAY_PHASE_END play 0\n' + wire,
               wire + b'HH_GAMEPLAY_PHASE_END play 0\n', b''.join(lines[:-1]), wire[:-1],
               b''.join([lines[0], lines[-1], *lines[1:]]), wire + lines[-1],
               b''.join(lines[:2] + [lines[1]] + lines[2:]),
               b''.join(lines[:2] + lines[3:]),
               b''.join(lines[:2] + [lines[3], lines[2]] + lines[4:])]
        for index, altered in enumerate(bad):
            with self.subTest(index=index), self.assertRaises(codec.AttributionError):
                verify(altered)

    def test_mac_commitment_and_run_binding(self):
        original = [json.loads(line) for line in transcript().splitlines()]
        for path in ('mac', 'commitment', 'exit', 'context'):
            rows = json.loads(json.dumps(original))
            if path == 'mac': rows[1]['mac'] = '0' * 64
            elif path == 'commitment': rows[0]['key_commitment'] = '0' * 64
            elif path == 'context': rows[0]['context']['run_id'] = 'other'
            else: rows[4]['event']['returncode'] = 1
            with self.subTest(path=path), self.assertRaises(codec.AttributionError):
                verify(reencode(rows))

    def test_signed_invalid_facts_are_not_accepted(self):
        for mutation in ('early_terminal', 'bool_exit', 'guard_bool', 'guard_missing',
                         'channel_list', 'base64', 'cap', 'wrong_phase'):
            rows = [json.loads(line) for line in transcript().splitlines()]
            if mutation == 'early_terminal': rows[4]['event'] = {'kind':'terminal','returncode':0,'children':1}
            elif mutation == 'bool_exit': rows[4]['event']['returncode'] = False
            elif mutation == 'guard_bool': rows[2]['event']['facts']['fork_errno'] = True
            elif mutation == 'guard_missing': rows[2]['event']['facts'] = {}
            elif mutation == 'channel_list': rows[3]['event']['channel'] = []
            elif mutation == 'base64': rows[3]['event']['base64'] = '!'
            elif mutation == 'cap': rows[3]['event']['base64'] = 'A' * (codec.MAX_CHUNK_BYTES * 2)
            elif mutation == 'wrong_phase': rows[1]['event']['phase'] = 'play'
            with self.subTest(mutation=mutation), self.assertRaises(codec.AttributionError):
                verify(reencode(rows, resign=True))


if __name__ == '__main__':
    unittest.main()
