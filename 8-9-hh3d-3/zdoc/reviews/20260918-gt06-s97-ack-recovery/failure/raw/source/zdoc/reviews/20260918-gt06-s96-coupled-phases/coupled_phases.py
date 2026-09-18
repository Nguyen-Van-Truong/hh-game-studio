"""One fixed S96 coupled diagnostic, composed from retained owned runners.

Import installs nothing. --describe only reads pins. Other modes require the
registered request. No accepted runtime/profile file is edited; copied native
instrumentation and in-process HTTP wrappers are ineligible for acceptance.
"""
from contextlib import ExitStack
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import traceback
from types import SimpleNamespace
from unittest.mock import patch

BASE = Path(__file__).resolve().parent
ENTRY = Path(__file__).resolve()
ROOT = BASE.parents[2]
STUDIO = ROOT / 'studio'
REVIEWS = ROOT / 'zdoc/reviews'
S93 = REVIEWS / '20260918-gt06-s93-sparse-attribution'
S95 = REVIEWS / '20260918-gt06-s95-native-isolation'
RECORDER = REVIEWS / '20260918-gt06-s95-result-prep/http-phases/phase_observer.py'
SOURCE_MAP = REVIEWS / '20260918-gt06-s95-status-recovery/source-current.json'
RUN_ID = 'gt06-s96-coupled-phases-01'
PREFLIGHT_ID = 'gt06-s96-coupled-phases-preflight-01'
SOURCE_SHA256 = '564e5b7877f49d33a1af84eaf3b3a7ddf4ea2f846c4161eb694c5c40514fc752'
PROFILE_SHA256 = '0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85'
OUTPUT = STUDIO / '.local/reviews' / RUN_ID
LAUNCH = BASE / 'launch-01'
HELPERS = (ENTRY, BASE / 'register_task.ps1', BASE / 'test_coupled_phases.py', S93 / 'diagnose_sequence_s91.py',
           S93 / 'launch_observer.py', S93 / 'patch_native_s91.py',
           S95 / 'object_probe_s95.gd', RECORDER, SOURCE_MAP)
FLAGS = {'formal_acceptance': False, 'eligible_for_dataset': False, 'full_benchmark': False}
KNOWN_CODES = frozenset({'S96_REPARSE', 'S96_NOT_FILE', 'S96_SOURCE_MAP',
    'S96_SOURCE_MISMATCH', 'S96_PROFILE', 'S96_REQUEST', 'S96_GODOT_PIN',
    'S96_PATCH_ANCHOR', 'S96_PROBE_GUARD', 'S96_PATCH_ROUNDTRIP',
    'S96_OVERLAY_READBACK', 'S96_FIXED_MODE', 'S96_HELPER_DRIFT'})


def need(value, code):
    if not value:
        raise RuntimeError(code)


def plain(path):
    path = Path(path).absolute()
    for item in (path, *path.parents):
        if item.exists():
            info = item.lstat()
            need(not item.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400,
                 'S96_REPARSE')
    return path


def sha(path):
    path = plain(path)
    need(path.is_file(), 'S96_NOT_FILE')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def map_digest(files):
    return hashlib.sha256(''.join(name + '\0' + files[name] + '\n'
                                for name in sorted(files)).encode()).hexdigest()


def helper_files():
    return {path.relative_to(ROOT).as_posix(): sha(path) for path in HELPERS}


def source_difference(expected, actual):
    # Paths come from the pinned local source collector; never include contents.
    return {kind: sorted(names)[:64] for kind, names in {
        'added': actual.keys() - expected.keys(), 'missing': expected.keys() - actual.keys(),
        'changed': {name for name in actual.keys() & expected.keys()
                    if actual[name] != expected[name]}}.items()}


def campaign():
    sys.path.insert(0, str(ROOT))
    from studio.tests.replay import run_benchmark_campaign as c
    c.load_fixture()
    files = c.source_files()
    expected = json.loads(plain(SOURCE_MAP).read_bytes())
    need(expected['source_closure_sha256'] == SOURCE_SHA256
         and len(expected['source_files']) == 51
         and map_digest(expected['source_files']) == SOURCE_SHA256, 'S96_SOURCE_MAP')
    if files != expected['source_files']:
        error = RuntimeError('S96_SOURCE_MISMATCH')
        error.source_difference = source_difference(expected['source_files'], files)
        raise error
    need(c.profile.PROFILE_SHA256 == PROFILE_SHA256, 'S96_PROFILE')
    return c, files


def request_value(console, windowed):
    c, files = campaign()
    helpers = helper_files()
    lock = json.loads(c.read_regular(STUDIO / 'toolchain.lock.json'))['godot']
    godot = STUDIO / '.local/tooling/godot-4.7.2-stable' / lock['gui_executable']
    need(sha(godot) == lock['gui_sha256'], 'S96_GODOT_PIN')
    return {'schema': 'HH-GT06-S96-COUPLED-REQUEST-1', 'run_id': RUN_ID,
        'preflight_id': PREFLIGHT_ID, 'source_files': files, 'source_sha256': SOURCE_SHA256,
        'profile_sha256': PROFILE_SHA256, 'helper_files': helpers,
        'helper_sha256': map_digest(helpers), 'python': str(console), 'pythonw': str(windowed),
        'python_sha256': sha(console), 'pythonw_sha256': sha(windowed),
        'godot_sha256': lock['gui_sha256'], 'working_directory': str(STUDIO),
        'wall_seconds': 7530, 'outer_process_limit': 7, **FLAGS}, godot


def check_request():
    console = Path(sys.executable).absolute().with_name('python.exe')
    expected, _ = request_value(console, console.with_name('pythonw.exe'))
    need(json.loads(plain(LAUNCH / 'request.json').read_bytes()) == expected, 'S96_REQUEST')
    return expected


def load_helper(name, path):
    # Launch modes validate the full request before executing any external helper.
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sanitized_error(error):
    kind = type(error).__name__
    result = {'exception_class': kind if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,79}', kind) else 'Exception',
              'frames': []}
    for frame in traceback.extract_tb(error.__traceback__)[-16:]:
        name = Path(frame.filename).name
        result['frames'].append({'file': name if re.fullmatch(r'[A-Za-z0-9_.-]{1,96}', name)
                                else 'nonstandard_filename', 'line': frame.lineno})
    if len(error.args) == 1 and type(error.args[0]) is str and error.args[0] in KNOWN_CODES:
        result['known_code'] = error.args[0]
        if error.args[0] == 'S96_SOURCE_MISMATCH':
            result['source_difference'] = error.source_difference
    return result


def error_text():
    error = sys.exc_info()[1]
    return json.dumps(sanitized_error(error)) if error is not None else 'NO_ACTIVE_EXCEPTION'


def patch_native(raw, probe):
    """S95 primitive census at validated ACK, with exact base-byte reversal."""
    text, body = raw.decode('utf-8'), probe.decode('utf-8-sig')
    marker = '# S95_SPARSE_HELPER_BOUNDARY\n'
    old_guard = 'if _mode != "diagnostic" or _s95_snapshot_count'
    need(body.startswith(marker) and body.count(marker) == 1 and body.count(old_guard) == 1,
         'S96_PROBE_GUARD')
    body = body.split(marker, 1)[1]
    replacements = {
        old_guard: 'if _mode != "full" or _s95_snapshot_count',
        'func _s95_before_batch() -> void:': 'func _s96_before_ack(ack_file_sha256: String) -> void:',
        'hh-studio.gt06.s95-sparse-attribution': 'hh-studio.gt06.s96-ack-sparse-attribution',
        'hh-studio.gt06.s95-sparse-post': 'hh-studio.gt06.s96-ack-sparse-post',
        'before_batch_counter_readback': 'before_ack_counter_readback',
        'baseline_batch4': 'baseline_ack_batch4',
        'first_prepublication_object_growth': 'first_ack_object_growth',
    }
    for old, new in replacements.items():
        need(body.count(old) == 1, 'S96_PROBE_GUARD')
        body = body.replace(old, new, 1)
    identity = '"run_id": _input.run_id,'
    need(body.count(identity) == 2, 'S96_PROBE_GUARD')
    body = body.replace(identity, identity + ' "ack_file_sha256": ack_file_sha256,')
    begin = text.index('func _wait_host_ack() -> void:\n')
    end = text.index('\n\nfunc _advance_batch() -> void:\n', begin)
    section = text[begin:end]
    anchor = '    var objects: float = Performance.get_monitor(Performance.OBJECT_COUNT)\n'
    inserted = '    _s96_before_ack(digest)\n    if _failed:\n        return\n'
    need(section.count(anchor) == 1
         and section.index('_fail("BENCHMARK_HOST_ACK_POSTCONDITION")')
         < section.index('_fail("BENCHMARK_HOST_ACK_CHANGED")') < section.index(anchor)
         < section.index('    var observed: int = Time.get_ticks_usec()\n')
         < section.index('    _heartbeat(true)\n'),
         'S96_PATCH_ANCHOR')
    section = section.replace(anchor, inserted + anchor, 1)
    changed = text[:begin] + section + text[end:]
    restored = changed.replace(inserted, '', 1)
    need(restored.encode() == raw, 'S96_PATCH_ROUNDTRIP')
    return (changed + '\n' + body).encode()


def install_prepare(c, output):
    original = c.prepare

    def prepared(project, factory, trusted, binding):
        original(project, factory, trusted, binding)
        native = project / 'addons/hh_benchmark/benchmark_native.gd'
        before, probe = native.read_bytes(), (S95 / 'object_probe_s95.gd').read_bytes()
        after = patch_native(before, probe)
        native.write_bytes(after)
        need(native.read_bytes() == after, 'S96_OVERLAY_READBACK')
        c.write(output / 'native-overlay.json', {**FLAGS,
            'base_sha256': c.sha(before), 'effective_sha256': c.sha(after), 'probe_sha256': c.sha(probe),
            'original_probe': (S95 / 'object_probe_s95.gd').relative_to(ROOT).as_posix(),
            'probe_adaptation': 'full_guard_ACK_phase_schema_trigger_labels_and_validated_ACK_digest_only',
            'phase': 'before_ack_counter_readback_after_validated_ACK_inspection_and_file_hash',
            'runtime_source_modified': False, 'thresholds_modified': False,
            'dimensions_or_barriers_modified': False, 'write_batch_bytes_modified': False,
            'ack_observed_deadline_check_heartbeat_modified': False,
            'binding_required': 'sparse ACK digest/counters/frame/time to original native ACK receipt'})
        c.write(output / 'effective-benchmark-native.gd', after)
        return c.project_files(project)

    c.prepare = prepared


def diagnostic_module():
    # Keep the archived import and its original file in helper_files. Rebinding
    # __file__ below selects the new child entry; it does not relabel old bytes.
    sys.path.insert(0, str(S93))
    sys.modules['patch_native_s91'] = load_helper('patch_native_s91', S93 / 'patch_native_s91.py')
    d = load_helper('_s96_retained_diagnostic', S93 / 'diagnose_sequence_s91.py')
    d.__file__, d.BASE, d.ROOT, d.STUDIO = str(ENTRY), BASE, ROOT, STUDIO
    d.RUN_ID, d.PREFLIGHT_ID = RUN_ID, PREFLIGHT_ID
    d.EXPECTED_SOURCE, d.EXPECTED_PROFILE = SOURCE_SHA256, PROFILE_SHA256
    d.modules, d.helpers, d.install_prepare = campaign, helper_files, install_prepare
    d.traceback = SimpleNamespace(print_exc=lambda: print(error_text(), file=sys.stderr, flush=True))
    original_inputs = d.write_inputs

    def inputs(c, files, output, run_id):
        meta = original_inputs(c, files, output, run_id)
        c.write(output / 's96-composition.json', {**FLAGS, 'run_id': run_id,
            'entry': ENTRY.relative_to(ROOT).as_posix(),
            'original_supervisor': (S93 / 'diagnose_sequence_s91.py').relative_to(ROOT).as_posix(),
            'original_observer': (S93 / 'launch_observer.py').relative_to(ROOT).as_posix(),
            'helper_closure_sha256': map_digest(meta['helper_files']),
            'source_files_are_unmodified_formal_base': True,
            'effective_native_copy_is_instrumented': True,
            'http_phases': 'bounded memory ring; terminal-only JSON after original child cleanup',
            'hard_kill_may_leave_phase_snapshot_missing': True,
            'instrumentation_overhead_not_subtracted': True})
        return meta

    d.write_inputs = inputs
    return d


def observed_child(d):
    c, _ = campaign()
    frozen_helpers = json.loads(c.read_regular(OUTPUT / 'diagnostic.json'))['helper_files']
    from studio.tests.replay import benchmark_commands as commands
    phases = load_helper('_s96_phase_observer', RECORDER)
    recorder = phases.PhaseRecorder(event_capacity=512, active_capacity=64)
    original_connection = http.client.HTTPConnection
    with ExitStack() as installed:
        for name, factory in (('Journal', phases.observed_journal_type),
                              ('LoopbackFixtureHost', phases.observed_host_type),
                              ('FixtureClient', phases.observed_client_type)):
            installed.enter_context(patch.object(commands, name, factory(getattr(commands, name), recorder)))
        installed.enter_context(patch.object(http.client, 'HTTPConnection',
            phases.observed_connection_type(original_connection, recorder)))
        try:
            return d.child()
        finally:
            # Original run_child's finally owns all cleanup. No disk writes in
            # operation wrappers and no invented response/progress timestamps.
            c.write(OUTPUT / 'http-phases-final.json', {**FLAGS, 'run_id': RUN_ID,
                'source_closure_sha256': SOURCE_SHA256, 'profile_sha256': PROFILE_SHA256,
                'helper_closure_sha256': map_digest(frozen_helpers),
                'helper_files_unchanged': helper_files() == frozen_helpers, 'observation': recorder.snapshot(),
                'scope': 'instrumented bounded phases; nested spans overlap; no root cause claim',
                'cleanup_proof': 'separate child-terminal-cleanup and external actual-exit receipts'})


def observer_module():
    o = load_helper('_s96_retained_observer', S93 / 'launch_observer.py')
    o.__file__, o.BASE, o.ROOT, o.STUDIO = str(ENTRY), BASE, ROOT, STUDIO
    o.RUN_ID, o.HELPER, o.LAUNCH, o.OUTPUT = RUN_ID, ENTRY, LAUNCH, OUTPUT
    o.pins = request_value
    o.traceback = SimpleNamespace(format_exc=error_text)
    original_write = o.write

    def sanitized_write(path, value):
        # Retained observer errors may contain arbitrary exception text. Keep
        # stable classes/frames separately; do not retain text or args.
        if isinstance(value, dict) and 'errors' in value:
            value = dict(value)
            value['errors'] = [{key: item for key, item in row.items() if key != 'message'}
                               for row in value['errors']]
        original_write(path, value)

    o.write = sanitized_write
    return o


def main():
    modes = ('--describe', '--preflight', '--observer', '--owned-supervisor', '--supervisor', '--owned-child')
    need(len(sys.argv) == 2 and sys.argv[1] in modes, 'S96_FIXED_MODE')
    mode = sys.argv[1]
    if mode == '--describe':
        console = Path(sys.executable).absolute().with_name('python.exe')
        value, _ = request_value(console, console.with_name('pythonw.exe'))
        print(json.dumps({'request': value, 'launch_performed': False, **FLAGS}, sort_keys=True))
        return 0
    request = check_request()
    if mode in ('--observer', '--owned-supervisor'):
        o = observer_module()
        return o.observer() if mode == '--observer' else o.gated_child()
    sys.executable = str(Path(sys.executable).with_name('python.exe'))
    d = diagnostic_module()
    need(helper_files() == request['helper_files'], 'S96_HELPER_DRIFT')
    return d.preflight() if mode == '--preflight' else d.parent() if mode == '--supervisor' else observed_child(d)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        message = json.dumps(sanitized_error(error)) + '\n'
        if sys.stderr is not None and not sys.stderr.closed:
            sys.stderr.write(message)
            sys.stderr.flush()
        else:
            target = plain(LAUNCH / 'entry-startup-failure.json')
            with target.open('x', encoding='utf-8') as stream:
                stream.write(message)
        raise SystemExit(1)
