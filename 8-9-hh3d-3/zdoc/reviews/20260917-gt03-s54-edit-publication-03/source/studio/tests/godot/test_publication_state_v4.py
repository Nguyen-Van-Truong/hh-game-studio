"""Synthetic v4 event histories: no native effects or engine/auth evidence."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import sys
import unittest

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.protocol.core import canonical_bytes, parse_json, ValidationError


def load(name, filename):
    path = STUDIO / 'godot-addon' / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


journal = load('gt03_v4_pure_journal', 'publication_journal_v4.py')
state, codec = journal.state_model, journal.bundle_codec


def sha(text): return hashlib.sha256(text.encode()).hexdigest()
def rev(text): return 'sha256:' + sha(text)


def bundle(scene='initial-scene', *, script='initial-script', revision='captured-state'):
    files = {path: (b'uid://abc123\n' if path.endswith('.uid') else ('synthetic ' + path + '\n').encode())
             for path in codec.PATHS}
    files[codec.SCENE_PATH] = scene.encode(); files[codec.SCRIPT_PATH] = script.encode()
    return codec.create_bundle(files, scene_revision=rev(revision), engine_sha256=sha('validator'))


def native_descriptor(value, prefix):
    m = parse_json(value.manifest_bytes)
    root = {'volume': '12', 'file_id': 'a' * 32}
    result = {'root_identity': root, 'project_revision': value.project_revision, 'files': {}}
    for path in (*codec.PATHS, '@manifest'):
        metadata = {'sha256': hashlib.sha256(value.manifest_bytes).hexdigest(), 'size_bytes': len(value.manifest_bytes)} if path == '@manifest' else m['files'][path]
        row = {'name': 'obj-' + sha(prefix + path)[:32], 'volume': root['volume'],
               'file_id': sha('file-' + prefix + path)[:32], **{k:metadata[k] for k in ('sha256','size_bytes')}}
        if path == '@manifest': result['manifest'] = row
        else: result['files'][path] = row
    return result


def selection(desc, selected, parent, command):
    return {'schema': 'hh-godot-active-selection-1', 'command_id': command,
            'parent_selection': parent, 'selection': selected, 'descriptor_sha256': state.digest(desc), 'descriptor': desc}


def native_version(selector, prefix):
    return {'volume': '12', 'file_id': sha(prefix)[:32], 'size_bytes': len(canonical_bytes(selector)), 'sha256': state.digest(selector)}


def configuration():
    initial = bundle(); desc = native_descriptor(initial, 'initial')
    selected = selection(desc, {'generation': 0, 'identity': rev('initial')}, None, 'bootstrap.initial')
    return {'schema': state.SCHEMA, 'kind': 'CONFIG', 'sequence': 1, 'project_id': 'v4-journal-test',
        'observed_ms': 100, 'validator_engine_sha256': sha('validator'), 'editor_engine_sha256': sha('editor'),
        'source_closure_sha256': sha('source'), 'validation_source_release_sha256': sha('validation-source'),
        'content_root_identity': desc['root_identity'], 'initial': {'bundle_manifest': parse_json(initial.manifest_bytes),
            'selector': selected, 'selector_version': native_version(selected, 'initial-selector')}}


def event(folded, kind, *, at=None, **fields):
    snapshot = folded.snapshot()
    return {'schema': state.SCHEMA, 'kind': kind, 'sequence': folded.event_count + 1,
            'project_id': snapshot['project_id'], 'observed_ms': snapshot['last_observed_ms'] + 1 if at is None else at, **fields}


def prepared(current, operation='scene.save', *, at=None):
    s = current.snapshot(); old = s['selected']; t = s['last_observed_ms'] + 1 if at is None else at
    script = parse_json(bundle(script='replacement-script').manifest_bytes)['files'][codec.SCRIPT_PATH]
    return event(current, 'CAPTURE_PREPARED', at=t, command_id='command.one', digest=rev('command.one'),
        operation=operation, candidate_id='candidate-' + '1' * 32,
        script_change=None if operation == 'scene.save' else {'path': codec.SCRIPT_PATH,
            'expected_sha256': old['bundle_manifest']['files'][codec.SCRIPT_PATH]['sha256'], **{k:script[k] for k in ('sha256','size_bytes')}},
        before_project_revision=old['bundle_manifest']['project_revision'], before_scene_revision=rev('captured-state'),
        expected_files=old['bundle_manifest']['files'], parent_selection=old['selector']['selection'],
        checkpoint_descriptor=old['selector']['descriptor'], previous_selector_version=old['selector_version'],
        previous_selector_sha256=state.digest(old['selector']), editor={'session_id': 'synthetic-editor', 'pid': 1234,
            'creation_filetime': '123456789', 'root_identity': {'volume': '12', 'file_id': 'b' * 32},
            'engine_sha256': sha('editor'), 'installed_source_sha256': sha('installed')}, editor_generation=1,
        root_instance_id=1, admission={'session_id': 'synthetic-auth', 'catalog_digest': rev('catalog'),
            'lease_id': 'lease-one', 'fencing_epoch': 1, 'admitted_ms': t, 'deadline_ms': t + 90000,
            'lease_expires_ms': t + 90000}, scratch_name='capture-' + '2' * 32 + '.tscn')


def capture_facts(command, at):
    p = command['capture_prepared']; files = parse_json(bundle('captured-scene').manifest_bytes)['files']
    return {'capture_id': 'capture-observation', 'scratch_name': p['scratch_name'], 'editor': p['editor'],
        'generation_before': 1, 'generation_after': 1, 'root_instance_id': 1, 'effect_started_ms': at,
        'effect_completed_ms': at, 'semantic_revision': rev('captured-state'), 'semantic_sha256': sha('captured-state'),
        'files': files, 'scene_sha256': files[codec.SCENE_PATH]['sha256'], 'scene_size_bytes': files[codec.SCENE_PATH]['size_bytes']}


def validation_facts(command, at):
    m = command['bundle_manifest']
    return {'command_id': command['command_id'], 'project_revision': m['project_revision'],
        'scene_revision': m['caller_observations']['scene_revision'], 'manifest_sha256': state.digest(m),
        'input_files_sha256': state.digest(m['files']), 'source_release_sha256': sha('validation-source'),
        'validator_engine_sha256': sha('validator'), 'observation_sha256': sha('validation-observation'),
        'evidence_sha256': sha('evidence'), 'run_id': 'hh-gt03-' + '3' * 32, 'validation_started_ms': at,
        'validation_completed_ms': at, 'context_kind': 'isolated_candidate', 'public_ack': False,
        'selected_state_verified': False, 'live_editor_adoption_verified': False}


def retirement_facts(command, at):
    p, r = command['capture_prepared'], command['retire_prepared']
    return {'observation_id': 'retirement-observation', 'observation_sha256': sha('retirement-observation'),
        'command_id': command['command_id'], 'request_digest': command['digest'],
        'retirement_intent_id': r['retirement_intent_id'], 'editor': p['editor'], 'before_generation': 1,
        'before_root_instance_id': 1, 'before_revision': p['before_scene_revision'], 'before_snapshot_sha256': sha('before'),
        'effect_started_ms': at, 'effect_completed_ms': at, 'close_completed_ms': at, 'next_generation': 2,
        'actual_exit_code': 0, 'wrapper_exit_code': 0, 'job_active_count': 0, 'job_zero_observed': True,
        'job_closed': True, 'job_tainted': False, 'handles_retained': False, 'public_ack': False}


def adoption_facts(command, at):
    p, m = command['capture_prepared'], command['bundle_manifest']
    common = {'generation_before': 1, 'generation_after': 2, 'effect_started_ms': at,
        'semantic_revision': m['caller_observations']['scene_revision'],
        'semantic_sha256': m['caller_observations']['scene_revision'][7:], 'project_revision': m['project_revision'],
        'manifest_sha256': state.digest(m), 'files': m['files'], 'selection': command['selector']['selection'],
        'selector_version': command['selector_version'], 'history_boundary': True}
    if p['operation'] == 'scene.save':
        return {**common, 'mode': 'same_editor', 'adoption_id': 'adoption-observation', 'context_kind': 'live_editor',
            'editor': p['editor'], 'root_instance_id_before': 1, 'root_instance_id_after': 2,
            'effect_completed_ms': at, 'scene_path': 'res://scenes/fixture.tscn'}
    old = p['editor']; new = {**old, 'session_id': 'successor-editor', 'creation_filetime': '123456790',
                            'root_identity': {'volume': '12', 'file_id': 'c' * 32}}
    return {**common, 'mode': 'fresh_editor', 'observation_id': 'adoption-observation',
        'command_id': command['command_id'], 'request_digest': command['digest'], 'old_editor': old, 'new_editor': new,
        'root_before': 1, 'root_after': 1, 'retirement_observation_id': command['retirement']['observation_id'],
        'retirement_sha256': command['retirement']['observation_sha256'], 'observed_ms': at, 'public_ack': False}


def next_event(current):
    s = current.snapshot(); c = s['commands'][-1]; p = c['capture_prepared']; t = s['last_observed_ms'] + 1
    common = {'command_id': c['command_id'], 'digest': c['digest']}
    phase = c['phase']
    if phase == 'CAPTURE_PREPARED': return event(current, 'CAPTURED', **common, capture=capture_facts(c, t))
    if phase == 'CAPTURED':
        value = bundle('captured-scene', script='replacement-script' if p['operation']=='script_text.replace' else 'initial-script',
                       revision='replacement-state' if p['operation']=='script_text.replace' else 'captured-state')
        desc = native_descriptor(value, 'candidate')
        return event(current, 'PREPARED', **common, planned_names={**{k:v['name'] for k,v in desc['files'].items()},
            '@manifest': desc['manifest']['name']}, bundle_manifest=parse_json(value.manifest_bytes))
    if phase == 'PREPARED':
        value = codec.decode_bundle(canonical_bytes(c['bundle_manifest']), bundle('captured-scene',
            script='replacement-script' if p['operation']=='script_text.replace' else 'initial-script',
            revision='replacement-state' if p['operation']=='script_text.replace' else 'captured-state').files)
        return event(current, 'STAGED', **common, descriptor=native_descriptor(value, 'candidate'))
    if phase == 'STAGED': return event(current, 'VALIDATED', **common, validation=validation_facts(c, t))
    if phase == 'VALIDATED' and p['operation'] == 'script_text.replace':
        return event(current, 'RETIRE_PREPARED', **common, current=state.activation_current(p),
                     retirement_intent_id='retire-intent', deadline_ms=t+10000)
    if phase == 'RETIRE_PREPARED': return event(current, 'RETIRED', **common, retirement=retirement_facts(c,t))
    if phase in ('VALIDATED', 'RETIRED'):
        selected = {'generation': 1, 'identity': state.selection_identity(s['project_id'], c['command_id'], c['digest'],
            p['parent_selection'], c['descriptor'], c['bundle_manifest'])}
        return event(current, 'ACTIVATING', **common, current=state.activation_current(p),
            selector=selection(c['descriptor'],selected,p['parent_selection'],c['command_id']),
            expected_selector_version=s['selected']['selector_version'])
    if phase == 'ACTIVATING':
        return event(current, 'SELECTED', **common, activation_event_sha256=c['activation_event_sha256'],
            selector_sha256=state.digest(c['selector']), selector_version=native_version(c['selector'],'candidate-selector'))
    if phase == 'SELECTED': return event(current, 'READBACK', **common, adoption=adoption_facts(c,t))
    if phase == 'READBACK':
        return event(current, 'COMMITTED', **common, readback_event_sha256=c['readback_event_sha256'],
                     response=state.terminal_plan(s,c)['response'])
    raise AssertionError(phase)


def history(operation='scene.save', until='COMMITTED'):
    rows = [configuration()]; current = state.replay(rows)
    rows.append(prepared(current, operation)); current = state.reduce_event(current, rows[-1])
    while state.lookup(current,'command.one')['phase'] != until:
        rows.append(next_event(current)); current = state.reduce_event(current, rows[-1])
    return rows


class PublicationStateV4Tests(unittest.TestCase):
    def test_both_operations_commit_exact_original_response_and_no_hash_cycle(self):
        for operation in ('scene.save','script_text.replace'):
            rows = history(operation); current = state.replay(rows); c = state.lookup(current,'command.one')
            response = state.lookup_response(current,'command.one',rev('command.one'))
            self.assertEqual(response,canonical_bytes(rows[-1]['response']))
            self.assertEqual(state.digest(c['receipt']),c['response']['postconditions']['durable_receipt_sha256'])
            self.assertNotIn('response',c['receipt']); self.assertIs(c['public_ack'],False)
            self.assertIs(c['engine_effects_verified'],False)
            self.assertEqual(c['response']['code'],'GODOT_MANAGED_SCENE_SAVED' if operation=='scene.save' else 'GODOT_MANAGED_SCRIPT_REPLACED')

    def test_every_cut_replays_inertly_and_unfinished_has_no_original_response(self):
        for operation in ('scene.save','script_text.replace'):
            rows=history(operation)
            for count in range(1,len(rows)+1):
                current=state.replay(rows[:count]); self.assertEqual(state.replay(current.events).snapshot(),current.snapshot())
                if count<len(rows):
                    with self.assertRaises(ValidationError):state.lookup_response(current,'command.one',rev('command.one'))

    def test_final_delta_rejects_caller_substitution_before_staging(self):
        rows=history('script_text.replace','CAPTURED'); current=state.replay(rows); good=next_event(current)
        for name in codec.PATHS:
            bad=copy.deepcopy(good); old=bad['bundle_manifest']; metadata=copy.deepcopy(old['files'])
            metadata[name]['sha256']=sha('wrong')
            bad['bundle_manifest']=state.values.bundle_manifest(metadata,old['caller_observations']['scene_revision'],sha('validator'))
            with self.subTest(path=name),self.assertRaises(ValidationError):state.reduce_event(current,bad)

    def test_capture_keeps_original_script_and_new_script_only_enters_candidate(self):
        rows=history('script_text.replace','CAPTURE_PREPARED'); current=state.replay(rows); bad=next_event(current)
        bad['capture']['files'][codec.SCRIPT_PATH]['sha256']=sha('replacement-script')
        with self.assertRaises(ValidationError):state.reduce_event(current,bad)

    def test_retirement_failure_or_boolean_native_fields_cannot_enable_selection(self):
        current=state.replay(history('script_text.replace','RETIRE_PREPARED')); good=next_event(current)
        for key,value in [('actual_exit_code',True),('wrapper_exit_code',False),('job_active_count',True),
            ('job_zero_observed',1),('job_closed',False),('job_tainted',True),('handles_retained',True),('next_generation',True),
            ('retirement_intent_id','wrong'),('before_revision',rev('wrong'))]:
            bad=copy.deepcopy(good); bad['retirement'][key]=value
            with self.subTest(key=key),self.assertRaises(ValidationError):state.reduce_event(current,bad)

    def test_script_cannot_skip_retirement_and_save_cannot_start_it(self):
        current=state.replay(history('script_text.replace','VALIDATED')); bad=next_event(current)
        save=state.replay(history('scene.save','VALIDATED')); activation=next_event(save)
        activation['selector']['descriptor']=state.lookup(current,'command.one')['descriptor']
        with self.assertRaises(ValidationError):state.reduce_event(current,activation)
        with self.assertRaises(ValidationError):state.reduce_event(save,bad)

    def test_fresh_identity_requires_new_process_creation_and_session_but_root_id_may_repeat(self):
        current=state.replay(history('script_text.replace','SELECTED')); good=next_event(current)
        self.assertEqual(state.reduce_event(current,good).snapshot()['commands'][0]['phase'],'READBACK')
        mutations=[('new_editor',good['adoption']['old_editor']),('generation_after',True),('root_after',True),
            ('history_boundary',1),('public_ack',0),('retirement_sha256',sha('wrong')),('effect_started_ms',0)]
        for key,value in mutations:
            bad=copy.deepcopy(good);bad['adoption'][key]=value
            with self.subTest(key=key),self.assertRaises(ValidationError):state.reduce_event(current,bad)

    def test_response_tampering_or_changed_digest_is_rejected(self):
        current=state.replay(history('script_text.replace','READBACK')); good=next_event(current)
        for key,value in [('status','UNKNOWN'),('command_id','wrong'),('code','wrong')]:
            bad=copy.deepcopy(good);bad['response'][key]=value
            with self.subTest(key=key),self.assertRaises(ValidationError):state.reduce_event(current,bad)
        committed=state.reduce_event(current,good)
        with self.assertRaises(ValidationError):state.lookup_response(committed,'command.one',rev('other'))

    def test_stop_before_retirement_is_rejected_after_intent_unknown_and_no_ack(self):
        for phase,status in [('VALIDATED','FAILED'),('RETIRE_PREPARED','UNKNOWN'),('RETIRED','UNKNOWN'),('SELECTED','UNKNOWN')]:
            current=state.replay(history('script_text.replace',phase))
            stopped=state.reduce_event(current,event(current,'STOP',reason='user-stop'))
            found=state.lookup(stopped,'command.one');self.assertEqual(found['phase'],status)
            self.assertIs(found['response']['postconditions']['public_ack'],False)
            self.assertEqual(parse_json(state.lookup_response(stopped,'command.one',rev('command.one'))),found['response'])

    def test_unknown_then_stop_preserves_original_response_and_uncertain_phase(self):
        current=state.replay(history('script_text.replace','RETIRED')); command=state.lookup(current,'command.one')
        response=state.terminal_plan(current.snapshot(),command,'UNKNOWN','lost-result')['response']
        current=state.reduce_event(current,event(current,'UNKNOWN',command_id='command.one',digest=rev('command.one'),reason='lost-result',response=response))
        before=state.lookup_response(current,'command.one',rev('command.one'))
        stopped=state.reduce_event(current,event(current,'STOP',reason='user-stop'))
        self.assertEqual(state.lookup_response(stopped,'command.one',rev('command.one')),before)
        self.assertEqual(state.lookup(stopped,'command.one')['uncertain_phase'],'RETIRED')

    def test_version_replay_is_explicit_and_no_v3_relabel(self):
        rows=history(); rows[0]['schema']=state.v3.SCHEMA
        with self.assertRaises(ValidationError):state.replay(rows)
        with self.assertRaises(ValidationError):state.v3.replay(history())

    def test_deadline_and_generation_overflow_reject_before_retire_intent(self):
        current=state.replay(history('script_text.replace','VALIDATED')); good=next_event(current)
        bad=copy.deepcopy(good);bad['deadline_ms']+=1
        with self.assertRaises(ValidationError):state.reduce_event(current,bad)
        cfg=state.replay([configuration()]); bad=prepared(cfg);bad['admission']['deadline_ms']+=1;bad['admission']['lease_expires_ms']+=1
        with self.assertRaises(ValidationError):state.reduce_event(cfg,bad)
        rows=history('script_text.replace','VALIDATED')
        rows[1]['editor_generation']=2147483647; rows[2]['capture']['generation_before']=2147483647; rows[2]['capture']['generation_after']=2147483647
        current=state.replay(rows); bad=next_event(current)
        with self.assertRaises(ValidationError):state.reduce_event(current,bad)


if __name__=='__main__':unittest.main(verbosity=2)
