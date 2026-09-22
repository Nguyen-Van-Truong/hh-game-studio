"""S160 diagnostic integration. AUTHORITY=0; never formal GT06 evidence.

Prepare/authenticate are inert. --run-existing is a real owned campaign launch;
it requires an externally retained exact freeze hash. No live run is authorized
by the presence of this implementation. The observer is a replaceable, pinned
helper: the initial S156 adapter is retained only to test runner integration.
Do not use a repeated PSS count capture as creator-attribution evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys


HERE = Path(__file__).absolute().parent
ROOT = HERE.parents[2]
SOURCE = 'fce149cd3a62e102aaba225794b9a5078cd84d7647cb359f6bbcacb8895ddcde'
PROFILE = '0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85'
CHILD = 'driver.py'
RUN_ID = re.compile(r'gt06-s160-diag-[a-z0-9-]{1,12}\Z')
FLAGS = {'authority': 0, 'formal_acceptance': False, 'eligible_for_dataset': False}
DEPENDENCIES = {
    'launcher_base.py': ('zdoc/reviews/20260922-gt06-s157-launcher/diagnostic_launcher_s157.py',
                         '103d0a24a7c39d01dbf6a5366456b8b7816fb9690fccd8f2a7c7dbd577b8a524'),
    'editor_handles.py': ('zdoc/reviews/20260922-gt06-s156-editor-handles/editor_handles.py',
                          '9e01eea7b3220da8e9299c9fc4afe5d5804be8aeb2e4f96dc9254f7cd32b5896'),
    'pss_adapter.py': ('zdoc/reviews/20260919-gt06-s105-handles/pss_adapter.py',
                       '797398a54cac5f7c772df7ec9c5ad988fe9e54c26c3c10e172a768e39dc25c76'),
}


class IntegrationError(RuntimeError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def need(condition, code):
    if not condition:
        raise IntegrationError(code)


def safe_relative(value):
    return (type(value) is str and bool(value) and '\x00' not in value
            and '\\' not in value and ':' not in value and not value.startswith('/')
            and all(p not in ('', '.', '..') and not p.endswith(('.', ' '))
                    for p in value.split('/')))


def checked_path(path, *, directory=False, missing=False):
    """Inspect lexical ancestors before resolve: links/junctions are forbidden."""
    path = Path(path)
    need(path.is_absolute(), 'S160_ABSOLUTE_PATH')
    need(all(p not in ('.', '..') for p in path.parts), 'S160_PATH_TRAVERSAL')
    for entry in list(reversed(path.parents)) + [path]:
        try:
            info = entry.lstat()
        except FileNotFoundError:
            need(missing, 'S160_PATH_MISSING')
            continue
        need(not stat.S_ISLNK(info.st_mode)
             and not getattr(info, 'st_file_attributes', 0) & 0x400,
             'S160_PATH_REPARSE')
    if not missing:
        need(path.is_dir() if directory else path.is_file(), 'S160_PATH_KIND')
    return path


def under(root, relative):
    need(safe_relative(relative), 'S160_PATH_TRAVERSAL')
    return checked_path(Path(root) / relative)


def digest(path):
    with checked_path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load_module(name, path, expected):
    need(digest(path) == expected, 'S160_IMPORTED_HELPER_DRIFT')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _base_module():
    relative, expected = DEPENDENCIES['launcher_base.py']
    path = HERE / 'launcher_base.py' if (HERE / 'launcher_base.py').exists() else ROOT / relative
    return load_module('s160_launcher_base', path, expected)


base = _base_module()
encoded = base.canonical_bytes
publish = base.publish_exclusive


def closure(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def read(path):
    checked_path(path)
    value = json.loads(Path(path).read_bytes())
    need(type(value) is dict, 'S160_DOCUMENT_SHAPE')
    return value


def flags(value):
    need(all(type(value.get(k)) is type(v) and value.get(k) == v for k, v in FLAGS.items()),
         'S160_DIAGNOSTIC_FLAGS')


def file_map(root, files):
    need(type(files) is dict and bool(files), 'S160_FILE_MAP')
    aliases = set()
    for name, expected in files.items():
        need(safe_relative(name) and base.valid_hash(expected), 'S160_FILE_MAP')
        alias = os.path.normcase(str(Path(root) / name))
        need(alias not in aliases, 'S160_FILE_ALIAS')
        aliases.add(alias)
        need(digest(under(root, name)) == expected, 'S160_FILE_DRIFT')


def helper_map(root):
    checked_path(root, directory=True)
    result = {}
    for folder, dirs, files in os.walk(root, followlinks=False):
        for name in dirs:
            checked_path(Path(folder) / name, directory=True)
        for name in files:
            path = checked_path(Path(folder) / name)
            result[path.relative_to(root).as_posix()] = digest(path)
    return result


def authenticate(run, services, *, freeze_sha256):
    """Bind exact helper/child/execution inventories, binaries and predecessor."""
    run = checked_path(run, directory=True)
    need(base.valid_hash(freeze_sha256) and digest(run / 'freeze.json') == freeze_sha256,
         'S160_FREEZE_PIN')
    frozen = read(run / 'freeze.json')
    need(frozen.get('schema') == 'HH-S160-freeze-1', 'S160_FREEZE_SCHEMA')
    flags(frozen)
    run_id = frozen.get('run_id')
    need(type(run_id) is str and RUN_ID.fullmatch(run_id)
         and len(run_id + '.r00.a01') <= 48, 'S160_RUN_ID')
    root = checked_path(frozen.get('original_root', ''), directory=True)
    need(run == root / 'studio/.local/reviews' / run_id, 'S160_RUN_PATH')
    helpers = checked_path(frozen.get('helper_root', ''), directory=True)
    need(helpers == run / 'helpers', 'S160_HELPER_ROOT')
    need(frozen.get('child_script') == CHILD and frozen.get('observer_strategy') == 's156-pinned-census',
         'S160_CHILD_SCRIPT')
    expected_helpers = frozen.get('helper_files')
    need(type(expected_helpers) is dict and set(expected_helpers) == {CHILD, *DEPENDENCIES},
         'S160_HELPER_SET')
    need(frozen.get('helper_closure_sha256') == closure(expected_helpers), 'S160_HELPER_CLOSURE')
    need(helper_map(helpers) == expected_helpers, 'S160_HELPER_DRIFT')
    for name, (_, expected) in DEPENDENCIES.items():
        need(expected_helpers[name] == expected, 'S160_HELPER_VERSION')
    # A coordinator-reviewed driver is copied byte for byte into this fresh run.
    need(frozen.get('driver_sha256') == expected_helpers[CHILD], 'S160_DRIVER_PIN')
    predecessor_path = checked_path(frozen.get('predecessor_freeze', ''))
    need(digest(predecessor_path) == frozen.get('predecessor_freeze_sha256'), 'S160_PREDECESSOR_PIN')
    predecessor = read(predecessor_path)
    base.validate_predecessor_document(predecessor)
    file_map(root, predecessor['files'])
    for path, expected in predecessor['binaries'].items():
        need(digest(path) == expected, 'S160_BINARY_DRIFT')
    executable = str(checked_path(services.python_executable()))
    need(executable == frozen.get('python_executable')
         and frozen.get('python_sha256') == predecessor['binaries'].get(executable)
         and services.python_sha256() == frozen['python_sha256'], 'S160_PYTHON_PIN')
    need(encoded(services.workstation()) == encoded(predecessor['workstation'])
         and frozen.get('workstation_sha256') == closure(predecessor['workstation']), 'S160_WORKSTATION_PIN')
    need(frozen.get('source_closure') == SOURCE and frozen.get('profile_sha256') == PROFILE,
         'S160_RUNTIME_PIN')
    source = frozen.get('source_files')
    file_map(root, source)
    observed = services.observed_source()
    need(observed == {'closure': SOURCE, 'count': len(source), 'profile_sha256': PROFILE,
                      'files': source}, 'S160_SOURCE_PIN')
    prefix = frozen.get('prefix_batches')
    need(type(prefix) is int and prefix in (1, 8), 'S160_PREFIX')
    need(type(frozen.get('outer_seconds')) is int
         and frozen['outer_seconds'] == (240 if prefix == 1 else 1500), 'S160_OUTER_LIMIT_PIN')
    campaign = read(run / 'campaign.json')
    context = read(run / 'attempt/context.json')
    campaign_sha = digest(run / 'campaign.json')
    need(frozen.get('campaign_sha256') == campaign_sha, 'S160_CAMPAIGN_PIN')
    expected_campaign = {'schema': 'HH-S160-diagnostic-campaign-1', 'campaign_id': run_id,
                         'source_files': source, 'source_closure_sha256': SOURCE,
                         'profile_sha256': PROFILE, 'prefix_batches': prefix, **FLAGS}
    need(encoded(campaign) == encoded(expected_campaign), 'S160_CAMPAIGN_BINDING')
    expected_context = {'run_id': run_id + '.r00.a01', 'index': 0, 'attempt': 1,
                        'source_files': source, 'source_closure_sha256': SOURCE,
                        'profile_sha256': PROFILE, 'campaign_sha256': campaign_sha,
                        'formal_acceptance': False, 'eligible_for_dataset': False}
    need(encoded(context) == encoded(expected_context), 'S160_CONTEXT_BINDING')
    execution = read(run / 'execution-source-files.json')
    # Exact union, not a caller-selected subset. All predecessor files are retained.
    expected_execution = dict(predecessor['files'])
    for name, expected in source.items():
        need(expected_execution.get(name) == expected, 'S160_SOURCE_OUTSIDE_PREDECESSOR')
    for name, expected in expected_helpers.items():
        expected_execution[(helpers / name).relative_to(root).as_posix()] = expected
    for path in (run / 'campaign.json', run / 'attempt/context.json', run / 'freeze.json', predecessor_path):
        expected_execution[path.relative_to(root).as_posix()] = digest(path)
    need(execution == expected_execution, 'S160_EXECUTION_EXACT_SET')
    file_map(root, execution)
    return {'freeze': frozen, 'freeze_sha256': freeze_sha256, 'context': context,
            'execution': execution, 'execution_closure_sha256': closure(execution)}


def prepare(root, run_id, prefix, services, *, predecessor_path=None):
    """Create fresh helper copies and immutable inputs. Does not spawn anything."""
    root = checked_path(root, directory=True)
    need(type(run_id) is str and RUN_ID.fullmatch(run_id), 'S160_RUN_ID')
    need(type(prefix) is int and prefix in (1, 8), 'S160_PREFIX')
    predecessor_path = predecessor_path or root / 'zdoc/reviews/20260922-gt06-s153-formal-campaign/freeze.json'
    predecessor = read(predecessor_path)
    base.validate_predecessor_document(predecessor)
    file_map(root, predecessor['files'])
    inputs = {CHILD: Path(__file__).absolute()}
    inputs.update({name: ROOT / relative for name, (relative, _) in DEPENDENCIES.items()})
    for name, path in inputs.items():
        compile(checked_path(path).read_bytes(), name, 'exec')
        if name in DEPENDENCIES:
            need(digest(path) == DEPENDENCIES[name][1], 'S160_HELPER_VERSION')
    run = checked_path(root / 'studio/.local/reviews' / run_id, missing=True)
    need(not os.path.lexists(run), 'S160_ID_REUSE')
    run.mkdir(parents=True)
    (run / 'attempt').mkdir()
    helpers = run / 'helpers'
    helpers.mkdir()
    for name, path in inputs.items():
        with (helpers / name).open('xb') as output:
            output.write(path.read_bytes())
            output.flush()
            os.fsync(output.fileno())
    sources = services.observed_source()['files']
    campaign = {'schema': 'HH-S160-diagnostic-campaign-1', 'campaign_id': run_id,
                'source_files': sources, 'source_closure_sha256': SOURCE,
                'profile_sha256': PROFILE, 'prefix_batches': prefix, **FLAGS}
    publish(run / 'campaign.json', campaign)
    context = {'run_id': run_id + '.r00.a01', 'index': 0, 'attempt': 1,
               'source_files': sources, 'source_closure_sha256': SOURCE,
               'profile_sha256': PROFILE, 'campaign_sha256': digest(run / 'campaign.json'),
               'formal_acceptance': False, 'eligible_for_dataset': False}
    publish(run / 'attempt/context.json', context)
    helpers_pins = helper_map(helpers)
    frozen = {'schema': 'HH-S160-freeze-1', 'run_id': run_id, 'original_root': str(root),
              'helper_root': str(helpers), 'helper_files': helpers_pins,
              'helper_closure_sha256': closure(helpers_pins), 'child_script': CHILD,
              'driver_sha256': helpers_pins[CHILD], 'observer_strategy': 's156-pinned-census',
              'source_files': sources, 'source_closure': SOURCE, 'profile_sha256': PROFILE,
              'campaign_sha256': context['campaign_sha256'], 'prefix_batches': prefix,
              'outer_seconds': 240 if prefix == 1 else 1500,
              'predecessor_freeze': str(predecessor_path),
              'predecessor_freeze_sha256': digest(predecessor_path),
              'python_executable': str(services.python_executable()),
              'python_sha256': services.python_sha256(),
              'workstation_sha256': closure(predecessor['workstation']), **FLAGS}
    publish(run / 'freeze.json', frozen)
    execution = dict(predecessor['files'])
    for name, expected in helpers_pins.items():
        execution[(helpers / name).relative_to(root).as_posix()] = expected
    for path in (run / 'campaign.json', run / 'attempt/context.json', run / 'freeze.json', predecessor_path):
        execution[path.relative_to(root).as_posix()] = digest(path)
    publish(run / 'execution-source-files.json', execution)
    freeze_sha = digest(run / 'freeze.json')
    authenticate(run, services, freeze_sha256=freeze_sha)
    return {'run': str(run), 'freeze_sha256': freeze_sha, 'launched': False, **FLAGS}


def reference(root, path):
    raw = checked_path(path).read_bytes()
    return {'file': path.relative_to(root).as_posix(), 'size_bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest()}


def verify_ref(root, ref, expected_name):
    need(type(ref) is dict and ref.get('file') == expected_name, 'S160_RAW_PATH_BINDING')
    path = under(root, expected_name)
    need(encoded(ref) == encoded(reference(root, path)), 'S160_RAW_HASH_BINDING')
    return read(path)


def bindings(auth):
    frozen = auth['freeze']
    return {'campaign_id': frozen['run_id'], 'run_id': auth['context']['run_id'],
            'freeze_sha256': auth['freeze_sha256'], 'source_closure_sha256': SOURCE,
            'profile_sha256': PROFILE, 'campaign_sha256': frozen['campaign_sha256'],
            'helper_closure_sha256': frozen['helper_closure_sha256'],
            'execution_closure_sha256': auth['execution_closure_sha256'],
            'prefix_batches': frozen['prefix_batches']}


def validate_boundary(run, auth, summary, child_target):
    flags(summary)
    need(summary.get('schema') == 'HH-S160-summary-1'
         and encoded(summary.get('bindings')) == encoded(bindings(auth)), 'S160_SUMMARY_BINDING')
    need(summary.get('status') == 'BOUNDARY_CAPTURED' and summary.get('primary_error') is None
         and summary.get('cleanup_errors') == [] and summary.get('reauthenticated') is True,
         'S160_NOT_BOUNDARY')
    prefix = auth['freeze']['prefix_batches']
    rows = summary.get('screened_batches')
    need(type(rows) is list and len(rows) == prefix, 'S160_EXACT_PREFIX')
    target = child_target.get('actual_target_exit') if type(child_target) is dict else None
    need(type(summary.get('pid')) is int and summary['pid'] > 0
         and type(target) is dict and type(target.get('pid')) is int
         and target['pid'] == summary['pid'], 'S160_TARGET_PID')
    root = run / 'attempt'
    editor_identity = None
    for index, row in enumerate(rows):
        need(type(row) is dict and type(row.get('index')) is int and row['index'] == index,
             'S160_CONTIGUOUS_PREFIX')
        gate = verify_ref(root, row.get('gate'), f's160-gates/gate-{index:02d}.json')
        flags(gate)
        need(gate.get('schema') == 'HH-S160-original-gate-1'
             and gate.get('run_id') == auth['context']['run_id']
             and type(gate.get('index')) is int and gate['index'] == index
             and type(gate.get('pid')) is int and gate['pid'] == summary['pid']
             and gate.get('result') == 'PASSED' and gate.get('error_code') is None,
             'S160_ORIGINAL_GATE_BINDING')
        need(verify_ref(root, gate.get('context'), 'context.json') == auth['context'], 'S160_GATE_CONTEXT')
        sample = verify_ref(root, gate.get('sample'), f'sample-preview-{index:02d}.json')
        joint = verify_ref(root, gate.get('joint'), f'joint-{index:02d}.json')
        for document in (sample, joint):
            need(type(document.get('index')) is int and document['index'] == index
                 and document.get('run_id') == auth['context']['run_id']
                 and document.get('source_closure_sha256') == SOURCE
                 and document.get('profile_sha256') == PROFILE, 'S160_RAW_IDENTITY')
        processes = sample.get('processes')
        need(type(processes) is dict and processes == joint.get('processes'), 'S160_RAW_PROCESS_BINDING')
        editor = processes.get('editor')
        need(type(editor) is dict and type(editor.get('pid')) is int and editor['pid'] > 0
             and editor.get('process_start') is not None, 'S160_EDITOR_PID')
        host = processes.get('host')
        need(type(host) is dict and type(host.get('pid')) is int and host['pid'] == summary['pid'],
             'S160_HOST_PID')
        if editor_identity is None:
            editor_identity = editor
        need(editor_identity == editor, 'S160_EDITOR_IDENTITY_CHANGED')
    editor_start = read(under(root, 'editor-host/process-start.json'))
    need(editor_start == {'pid': editor_identity['pid']}, 'S160_EDITOR_TARGET_PID')


def run_child(run, services, *, freeze_sha256, campaign=None, observer=None, adapter=None,
              script_path=None, pid=None):
    """Real child path: reuse S156 installed() around the unchanged campaign."""
    auth = authenticate(run, services, freeze_sha256=freeze_sha256)
    frozen, context = auth['freeze'], auth['context']
    script = Path(__file__).absolute() if script_path is None else Path(script_path)
    need(script == Path(frozen['helper_root']) / CHILD and digest(script) == frozen['driver_sha256'],
         'S160_COPIED_CHILD')
    claim = read(run / 'dispatch-claim.json')
    need(claim == {'schema': 'HH-S160-dispatch-claim-1', 'bindings': bindings(auth), **FLAGS},
         'S160_DISPATCH_BINDING')
    if campaign is None:
        campaign = campaign_module(Path(frozen['original_root']))
    helpers = Path(frozen['helper_root'])
    observer = observer or load_module('s160_editor_handles', helpers / 'editor_handles.py',
                                      frozen['helper_files']['editor_handles.py'])
    adapter = adapter or load_module('s160_pss_adapter', helpers / 'pss_adapter.py',
                                    frozen['helper_files']['pss_adapter.py'])
    pid = os.getpid() if pid is None else pid
    rows = []

    class BoundCensus(observer.EditorCensus):
        def observe(self, sample, baseline, primary):
            index = sample['index']
            need(type(index) is int and index == len(rows), 'S160_SCREEN_ORDER')
            gate = {'schema': 'HH-S160-original-gate-1', 'run_id': context['run_id'],
                    'pid': pid, 'index': index, 'result': 'FAILED' if primary else 'PASSED',
                    'error_code': None if primary is None else base.error_record(primary)['code'],
                    'context': reference(self.root, self.root / 'context.json'),
                    'sample': reference(self.root, self.root / f'sample-preview-{index:02d}.json'),
                    'joint': reference(self.root, self.root / f'joint-{index:02d}.json'), **FLAGS}
            path = self.root / f's160-gates/gate-{index:02d}.json'
            publish(path, gate)
            rows.append({'index': index, 'gate': reference(self.root, path)})
            # The original screen ran before installed() calls this observer.
            # Preserve its failure even if the supplementary census also fails.
            return super().observe(sample, baseline, primary)

    census = BoundCensus(run / 'attempt', context, frozen['prefix_batches'], adapter)
    status, primary, cleanup = 'INCOMPLETE', None, []
    reauthenticated = False
    try:
        with observer.installed(campaign, census):
            campaign.run_child(run / 'attempt')
        status = 'UNEXPECTED_FULL_COMPLETION'
    except observer.BoundaryStop as error:
        status = 'BOUNDARY_CAPTURED'
        cleanup = [base.error_record(e) for e in getattr(error, 'cleanup_errors', ())]
    except BaseException as error:
        status, primary = 'FAILURE', base.error_record(error)
        cleanup = [base.error_record(e) for e in getattr(error, 'cleanup_errors', ())]
    try:
        need(authenticate(run, services, freeze_sha256=freeze_sha256) == auth, 'S160_POST_RUN_DRIFT')
        reauthenticated = True
    except BaseException as error:
        cleanup.append(base.error_record(error))
    if cleanup or not reauthenticated:
        status = 'FAILURE'
    summary = {'schema': 'HH-S160-summary-1', 'bindings': bindings(auth), 'pid': pid,
               'status': status, 'primary_error': primary, 'cleanup_errors': cleanup,
               'screened_batches': rows, 'reauthenticated': reauthenticated,
               'ended_utc': services.utc(), **FLAGS}
    publish(run / 'diagnostic-summary.json', summary)
    return 1 if status == 'BOUNDARY_CAPTURED' else 2


def launch_existing(run, services, *, freeze_sha256, publisher=publish):
    """Owned launch with post-close reauthentication and independently read exits."""
    run = Path(run)
    auth, owner, helper_exit, helper_pid = None, None, None, None
    summary, child_target, editor_target, cleanup = None, None, None, None
    errors, stop_before, stop_during = [], False, False
    post_auth = False
    started = services.monotonic()

    def stopped():
        context = auth['context']
        return services.stop_requested(run / 'attempt', run_id=context['run_id'],
                                       source_closure_sha256=SOURCE,
                                       campaign_sha256=context['campaign_sha256'])

    def observe(getter):
        try:
            return getter()
        except BaseException as error:
            errors.append(base.error_record(error))
            return None

    try:
        auth = authenticate(run, services, freeze_sha256=freeze_sha256)
        if stopped():
            stop_before = True
            raise IntegrationError('S160_STOPPED')
        need(not os.path.lexists(run / 'dispatch-claim.json')
             and not os.path.lexists(run / 'result.json'), 'S160_ID_REUSE')
        # Stale terminal/raw output cannot be smuggled into a fresh dispatch.
        need(not os.path.lexists(run / 'diagnostic-summary.json')
             and not os.path.lexists(run / 'owned')
             and {p.name for p in (run / 'attempt').iterdir()} <= {'context.json', 'stop-request.json'},
             'S160_PREEXISTING_OUTPUT')
        claim = {'schema': 'HH-S160-dispatch-claim-1',
                 'bindings': bindings(auth), **FLAGS}
        publisher(run / 'dispatch-claim.json', claim)
        need(read(run / 'dispatch-claim.json') == claim, 'S160_DISPATCH_READBACK')
        if stopped():
            stop_before = True
            raise IntegrationError('S160_STOPPED')
        need(authenticate(run, services, freeze_sha256=freeze_sha256) == auth, 'S160_PRESPAWN_DRIFT')
        frozen = auth['freeze']
        argv = [services.python_executable(), '-B', str(Path(frozen['helper_root']) / CHILD),
                '--child', str(run), '--freeze-sha256', freeze_sha256]
        owner = services.spawn(argv, cwd=run, output=run / 'owned',
                               source_root=Path(frozen['original_root']), source_files=auth['execution'],
                               binary_sha256=frozen['python_sha256'], campaign_host=True)
        helper_pid = owner.process.pid
        need(type(helper_pid) is int and helper_pid > 0, 'S160_HELPER_PID')
        while True:
            if stopped():
                stop_before = True
                raise IntegrationError('S160_STOPPED')
            helper_exit = owner.tick(stop=False)
            if helper_exit is not None:
                need(type(helper_exit) is int, 'S160_HELPER_EXIT_TYPE')
                if stopped():
                    stop_before = True
                break
            need(services.monotonic() - started < frozen['outer_seconds'], 'S160_OUTER_LIMIT')
            services.sleep(0.2)
    except BaseException as error:
        if owner is None:
            owner = getattr(error, 'cleanup_owner', None)
        errors.append(base.error_record(error))
    finally:
        if owner is not None:
            observe(owner.close)
        if auth is not None:
            if observe(stopped) and not stop_before:
                stop_during = True
            after = observe(lambda: authenticate(run, services, freeze_sha256=freeze_sha256))
            post_auth = after == auth
            if not post_auth and not errors:
                errors.append(base.error_record(IntegrationError('S160_POST_RUN_DRIFT')))
        summary = observe(lambda: read(run / 'diagnostic-summary.json')
                          if os.path.lexists(run / 'diagnostic-summary.json') else None)
        cleanup = observe(lambda: services.editor_cleanup(owner))
        child_target = observe(lambda: base.seal_target(services.target_exit(run, 'owned'), helper_exit))
        editor_target = observe(lambda: base.seal_target(services.target_exit(run / 'attempt', 'editor-host'), helper_exit))
        # Re-read receipt references, including paths, rather than trusting services metadata.
        for role, root, target in (('owned', run, child_target), ('editor-host', run / 'attempt', editor_target)):
            if target:
                for kind in ('start', 'exit'):
                    ref = target.get(kind)
                    if ref is not None:
                        observe(lambda r=root, v=ref, p=f'{role}/process-{kind}.json': verify_ref(r, v, p))
        if auth is not None and summary is not None and not errors and not (stop_before or stop_during):
            observe(lambda: validate_boundary(run, auth, summary, child_target))
            if not errors:
                code = base._boundary_code({'source_unchanged': post_auth, 'primary_error': None,
                                            'cleanup_errors': []}, helper_exit, cleanup, child_target)
                if code:
                    errors.append(base.error_record(IntegrationError(code)))
                if (type(cleanup) is not dict or type(cleanup.get('helper_pid')) is not int
                        or cleanup['helper_pid'] != helper_pid
                        or type(cleanup.get('helper_exit_code')) is not int
                        or cleanup['helper_exit_code'] != helper_exit):
                    errors.append(base.error_record(IntegrationError('S160_HELPER_IDENTITY')))
        elif not (stop_before or stop_during) and not errors:
            errors.append(base.error_record(IntegrationError('S160_SUMMARY_MISSING')))
    status = 'STOPPED' if stop_before else 'STOPPED_DURING_CLEANUP' if stop_during else 'FAILURE' if errors else 'BOUNDARY_CAPTURED'
    record = {'schema': 'HH-S160-owner-result-1', 'status': status,
              'launcher_exit': 2 if stop_before or stop_during else 1 if errors else 0,
              'boundary_permitted': status == 'BOUNDARY_CAPTURED',
              'bindings': None if auth is None else bindings(auth), 'reauthenticated': post_auth,
              'helper_pid': helper_pid, 'helper_exit_before_close': helper_exit,
              'cleanup': cleanup, 'child_target': child_target, 'editor_target': editor_target,
              'editor_exit_status': 'RECORDED' if editor_target and editor_target['actual_target_exit'] is not None else 'UNKNOWN',
              'stop': {'before_terminal': stop_before, 'during_cleanup': stop_during},
              'primary_error': summary.get('primary_error') if summary else None,
              'errors': errors, 'formal_eligibility': False, 'not_formal_pass': True,
              'elapsed_seconds': services.monotonic() - started, 'ended_utc': services.utc(), **FLAGS}
    try:
        # Publication failure is a failure even if a Stop status is preserved.
        publisher(run / 'result.json', record)
        record['result_published'] = True
    except BaseException as error:
        record.update(result_published=False, boundary_permitted=False, launcher_exit=1,
                      publish_error=base.error_record(error))
        if not (stop_before or stop_during):
            record['status'] = 'FAILURE'
    return record


def campaign_module(root):
    sys.path.insert(0, str(root))
    from studio.tests.replay import run_benchmark_campaign
    run_benchmark_campaign.load_fixture()
    return run_benchmark_campaign


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--prepare', action='store_true')
    modes.add_argument('--authenticate', type=Path)
    modes.add_argument('--run-existing', type=Path)
    modes.add_argument('--child', type=Path)
    parser.add_argument('--run-id')
    parser.add_argument('--prefix', type=int, choices=(1, 8), default=1)
    parser.add_argument('--freeze-sha256')
    args = parser.parse_args(argv)
    run = args.authenticate or args.run_existing or args.child
    root = ROOT
    if run:
        run = checked_path(run.absolute(), directory=True)
        need(base.valid_hash(args.freeze_sha256) and digest(run / 'freeze.json') == args.freeze_sha256,
             'S160_FREEZE_PIN')
        root = Path(read(run / 'freeze.json')['original_root'])
        # Check all importable runtime bytes before importing the campaign module.
        frozen = read(run / 'freeze.json')
        predecessor = read(checked_path(frozen['predecessor_freeze']))
        need(digest(frozen['predecessor_freeze']) == frozen['predecessor_freeze_sha256'], 'S160_PREDECESSOR_PIN')
        file_map(root, predecessor['files'])
    campaign = campaign_module(root)
    services = base.services_from_campaign(campaign, python_executable=sys.executable)
    if args.prepare:
        result = prepare(root, args.run_id, args.prefix, services)
    elif args.authenticate:
        auth = authenticate(run, services, freeze_sha256=args.freeze_sha256)
        result = {'authenticated': True, 'bindings': bindings(auth), 'launched': False, **FLAGS}
    elif args.child:
        return run_child(run, services, freeze_sha256=args.freeze_sha256, campaign=campaign)
    else:
        result = launch_existing(run, services, freeze_sha256=args.freeze_sha256)
    print(json.dumps(result, sort_keys=True), flush=True)
    return result.get('launcher_exit', 0)


if __name__ == '__main__':
    raise SystemExit(main())
