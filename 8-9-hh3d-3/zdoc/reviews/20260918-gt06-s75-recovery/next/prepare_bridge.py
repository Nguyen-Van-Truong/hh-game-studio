"""Preparation only: read declared source maps and author drafts in this folder.

Does not run an engine, test, campaign validator, scheduler or acceptance gate.
Run from the repository root with python -B and preserve the printed real exit.
"""
from __future__ import annotations
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

OUT = Path(__file__).resolve().parent
PRODUCT = OUT.parents[3]
STUDIO = PRODUCT / 'studio'
PRIOR = PRODUCT / 'zdoc/reviews/20260918-gt06-s73-next/seal'
REL = OUT.relative_to(PRODUCT).as_posix()
CAMPAIGN = 'gt06-s75-campaign-01'
sys.path.insert(0, str(PRODUCT))
from studio.tests.replay import run_benchmark_campaign as campaign


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(relative):
    return (PRODUCT / relative).read_bytes()


def parsed(relative):
    return json.loads(read(relative))


def write(name, value):
    raw = value.encode('utf-8') if isinstance(value, str) else (json.dumps(
        value, indent=2, ensure_ascii=True, allow_nan=False) + '\n').encode('utf-8')
    with (OUT / name).open('xb') as stream:
        stream.write(raw)


def ref(relative):
    raw = read(relative)
    return {'file': relative, 'sha256': sha(raw), 'size_bytes': len(raw)}


campaign.load_fixture()
current = campaign.source_files()
digest = campaign.closure(current)
frozen_path = 'studio/.local/reviews/gt06-s73-campaign-01/campaign.json'
frozen = parsed(frozen_path)
old = frozen['source_files']
changed = {key: {'s73_sha256': old[key], 'candidate_sha256': current[key]}
           for key in sorted(old.keys() & current.keys()) if old[key] != current[key]}
assert len(current) == 49 and current.keys() == old.keys()
assert set(changed) == {'tests/replay/benchmark_native.gd',
                        'tests/replay/run_native_benchmark.py',
                        'tests/replay/benchmark_assembly.py'}, changed
assert campaign.closure(old) == frozen['source_closure_sha256']
assert campaign.profile.PROFILE_SHA256 == frozen['profile_sha256']
assert sha((STUDIO / 'toolchain.lock.json').read_bytes()) == frozen['toolchain_sha256']

service_ids = ['gt06-s73-' + mode + '-01' for mode in
               ('http-complete', 'http-stop', 'saturated-stop', 'revoked-result', 'stale-capture')]
gui_ids = ['gt06-s68-reviewer-complete-02', 'gt06-s68-reviewer-stop-02']
historic_service_ids = ['gt06-s69-' + mode + '-01' for mode in
                        ('saturated-stop', 'revoked-result', 'stale-capture')]
map_paths = [('review_runner', 'zdoc/reviews/20260918-gt06-s73-recovery/service-remint/source-files.json')]
map_paths += [('service_current_runtime', f'studio/.local/reviews/{rid}/source-files.json') for rid in service_ids]
map_paths += [('gui_historical_runtime', f'studio/.local/reviews/{rid}/source-files.json') for rid in gui_ids]
map_paths += [('service_historical_runtime', f'studio/.local/reviews/{rid}/source-files.json') for rid in historic_service_ids]
map_paths += [('managed_replay_runtime', 'studio/.local/reviews/gt06-s69-managed-replay-01/source-files.json')]
map_paths += [('reviewer_ui', f'studio/.local/reviews/{rid}/reviewer-probe/source.json') for rid in gui_ids]
comparisons = []
for domain, relative in map_paths:
    original = parsed(relative)
    projection = {}
    for name in original:
        path = (STUDIO / name).resolve()
        assert path.is_relative_to(STUDIO) and path.is_file(), name
        projection[name] = sha(path.read_bytes())
    differences = {name: {'recorded_sha256': original[name], 'current_sha256': projection[name]}
                   for name in sorted(original) if original[name] != projection[name]}
    if domain in ('service_current_runtime', 'managed_replay_runtime', 'reviewer_ui'):
        assert not differences, (relative, differences)
    if domain in ('gui_historical_runtime', 'service_historical_runtime'):
        assert set(differences) == {'host/replay/verified_journal.py'}
    comparisons.append({'domain': domain, **ref(relative), 'declared_count': len(original),
        'declared_map_closure_sha256': campaign.closure(original),
        'current_projection_closure_sha256': campaign.closure(projection),
        'compared_count': len(projection), 'missing_paths': [], 'changed': differences,
        's75_changed_runtime_overlap': sorted(set(original) & set(changed)),
        'exact_current_declared_projection': not differences,
        'scope': 'Every declared path compared to current bytes; does not independently prove original map completeness or raw execution.'})

service_manifest = 'zdoc/reviews/20260918-gt06-s73-recovery/service-remint/verification.json'
assert sha(read(service_manifest)) == 'f29b942a9dd84fe9c73e6e537650f57fab2fd40470ac3dce870f7e7fa86de1d5'
repair_root = 'studio/.local/reviews/gt06-s65-repair-02/'
replay = parsed('studio/.local/reviews/gt06-s69-managed-replay-01/repair-replay.json')
repair = parsed(repair_root + 'repair.json')
response = parsed(repair_root + 'response.json')
request = parsed(repair_root + 'request.json')
assert replay['binding']['fault_capture_sha256'] == sha(read('studio/.local/reviews/gt06-s65-native-04/capture.json'))
assert replay['binding']['repair_capture_sha256'] == sha(read(repair_root + 'capture.json'))
assert replay['native_capture_sha256'] == sha(read('studio/.local/reviews/gt06-s69-managed-replay-01/capture.json'))
assert replay['binding']['selected_config_sha256'] == sha(read(repair_root + 'selected-config.gd')) == repair['selected_config_sha256']
assert repair['response_sha256'] == sha(read(repair_root + 'response-wire.json'))
assert parsed(repair_root + 'response-wire.json') == response
assert request['command_id'] == response['command_id'] == 'gt06.repair.move-speed'
assert response['postconditions']['request_digest'] == request['digest']
causal_files = [f'studio/.local/reviews/{rid}/{name}' for rid, names in [
    ('gt06-s65-native-04', ('capture.json', 'source-files.json', 'runtime-snapshot.json')),
    ('gt06-s65-repair-02', ('capture.json', 'source-files.json', 'repair.json', 'request.json',
                           'response.json', 'response-wire.json', 'lookup-response.json', 'retry-response.json', 'selected-config.gd')),
    ('gt06-s65-native-05', ('capture.json', 'source-files.json', 'repair-replay.json')),
    ('gt06-s69-managed-replay-01', ('capture.json', 'source-files.json', 'repair-replay.json')),
] for name in names]
old_bridge = json.loads((PRIOR / 'affected-dependency-bridge.json').read_bytes())
bridge = {'schema': 'HH-GT06-S75-AFFECTED-DEPENDENCY-BRIDGE-DRAFT-1',
    'status': 'SOURCE_PROJECTIONS_CHECKED_CAMPAIGN_NOT_RUN_BY_PREPARER',
    'prepared_utc': datetime.now(timezone.utc).isoformat(), 'formal_acceptance': False,
    'critic_verdict': None, 'candidate_campaign_id': CAMPAIGN,
    'observed_git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=PRODUCT).decode().strip(),
    'candidate_source_revision': None, 'named_commit_byte_verification': 'PENDING_COORDINATOR_CHECKPOINT',
    'source_count': len(current), 'candidate_source_closure_sha256': digest,
    'candidate_source_map': REL + '/source-files.json', 'source_domain': 'studio-relative runtime49',
    'frozen_s73_campaign': ref(frozen_path), 'frozen_s73_source_closure_sha256': campaign.closure(old),
    'added_runtime_paths': [], 'removed_runtime_paths': [], 'changed_runtime_paths': changed,
    'profile_sha256': campaign.profile.PROFILE_SHA256, 'profile_unchanged': True,
    'toolchain_sha256': frozen['toolchain_sha256'], 'toolchain_unchanged': True,
    'comparisons': comparisons, 'historical_s73_bridge': ref('zdoc/reviews/20260918-gt06-s73-next/seal/affected-dependency-bridge.json'),
    'service_manifest': ref(service_manifest), 'service_lane_recorded_results': parsed(service_manifest)['lanes'],
    'original_causal_chain': old_bridge['original_causal_chain'],
    'causal_named_artifact_byte_refs': [ref(name) for name in causal_files],
    'causal_join_checks': {'checked_named_hash_links_only': True, 'command_id': request['command_id'],
        'durable_receipt_sha256_recorded': response['postconditions']['durable_receipt_sha256'],
        'repair_response_hash_domain': 'Original response-wire.json bytes; response.json adds LF and has a distinct exact-byte hash.',
        'receipt_semantics_revalidated': False, 'replayed': False},
    'remint_required': ['new S75 benchmark campaign: all ten complete fresh process pairs and 35 batches each',
        'affected benchmark fixture/assembly validation on final source: positive native marker, exact-byte negative marker and assembly missing/coherently-altered marker rejection',
        'new source checkpoint proof, selected-run verification, final source/review/raw manifest and two independent same-hash critics'],
    'reuse_scopes': ['S73 five service runtime173 projections: exact-current; retain original run IDs, owners, logs, exits and raw hashes',
        'S69 managed replay159: exact-current declared projection, preserve original S65 fault/repair02 receipt and S69 generation',
        'S68 reviewer UI5: exact-current; runtime173 historical verified_journal edge remains bridged by S73 five service remints',
        'S69 adversary173: historical only for changed journal edge; S73 remints supply current service behavior',
        'S73 broad review-runner148: historical map, not exact-current; benchmark-only changed paths do not invalidate unaffected service execution',
        'GT03-05 accepted packages: preserve scoped original acceptance; no reopening or signature transfer'],
    'full_raw_audit_performed': False, 'engines_launched': False, 'tests_executed': False,
    'validators_executed': False, 'automations_modified': False, 'plan_modified': False}
write('source-files.json', current)
write('affected-dependency-bridge.json', bridge)

recipe = json.loads((PRIOR / 'collection-recipe.json').read_bytes())
recipe['schema'] = 'HH-GT06-S75-SEAL-RECIPE-DRAFT-1'
recipe['status'] = 'PREPARATION_ONLY_UNCOMMITTED_SOURCE_CANDIDATE'
recipe['campaign'].update(id=CAMPAIGN, raw_root='studio/.local/reviews/' + CAMPAIGN,
    source_revision=None, source_closure_sha256=digest, checkpoint_map=REL + '/source-files.json',
    checkpoint_revision_caveat='Working source snapshot only. Coordinator must freeze and record an actual named commit byte proof; no future commit is claimed.')
recipe['terminal_preconditions'] = json.loads(json.dumps(recipe['terminal_preconditions']).replace('gt06-s73-campaign-01', CAMPAIGN))
for row in recipe['validator_reuse']:
    if row['id'] == 'V_SOURCE_GIT':
        row['argv'][3] = '{actual_source_checkpoint_revision}'
        row['then_require'] = 'Actual named revision proof; exact_git_bytes=true; exact49 path/hash map equals S75 frozen campaign; closure=' + digest + '; unchanged profile; verifier actual exit0.'
    if row['id'] == 'DRAFT_ADAPTER':
        row['path'] = REL + '/verify_campaign_readonly.py.draft'
        row['argv'][2] = row['path']
        row['source_revision_binding'] = 'Uncommitted candidate; no revision asserted. V_SOURCE_GIT must bind the actual coordinator checkpoint separately.'
recipe['source_policy']['functional_reuse'] = 'Use the S75 affected-dependency-bridge full declared map comparisons. S75 changes benchmark fixture/assembly only. S73 service173 and S69 managed replay159 remain exact-current projections. S68 UI5 remains exact-current; older service173 retains its S73 journal bridge. Broad review-runner148 is not exact-current.'
recipe['source_policy']['s75_runtime_diff'] = {'from': campaign.closure(old), 'to': digest, 'changed': changed, 'added': [], 'removed': []}
recipe['source_policy']['affected_dependency_bridge'] = REL + '/affected-dependency-bridge.json'
recipe['source_policy']['historical_causal_exception'] += ' Preserve these observations under their original generations when packaging S75.'
recipe['selected_campaign_collection']['historical_campaigns'] = 'Retain all S68-S71 failures and both FAILED S73 launches under original source/IDs. No partial batch or failed source generation enters the S75 selected dataset.'
for row in recipe['inherited_evidence']:
    if row['id'] in ('E68GUI', 'E69A', 'E69R', 'E73_SERVICE'):
        row['s75_projection_check'] = REL + '/affected-dependency-bridge.json'
recipe['inherited_evidence'].append({'id': 'E75_FAILED_S73',
    'review_roots': ['zdoc/reviews/20260918-gt06-s74-recovery/failure', 'zdoc/reviews/20260918-gt06-s75-recovery/failure'],
    'scope': 'S73 launch1 RSS/status-gap failure and launch2 retained-counter failure; forensic only, never S75 samples.'})
recipe['s75_pending_affected_validation'] = {'status': 'COORDINATOR_OWNED_RESULTS_NOT_CLAIMED_BY_PREPARER',
    'required': bridge['remint_required'][1], 'bound_artifact_manifest': None}
recipe['hash_domains']['s75_projection'] = 'Each historical declared source map retains its own exact-byte hash/closure; current hashes over that same path set form a separate named projection. This is not a new original execution source map.'
recipe['final_manifest_design']['required_sections'].append('S75 fixture marker/assembly affected validation, dependency projections and supplemental telemetry observer disclosure when collected')
recipe['final_manifest_design']['current_disposition'] = 'Preparation only for S75 working source. No launch, final validator, candidate seal or acceptance performed. Exact frozen commit, terminal full campaign, final manifest and two independent critics remain pending.'
recipe['derived_from'] = {'directory': PRIOR.relative_to(PRODUCT).as_posix(),
    'copy_policy': 'Historical S73 draft unchanged; active campaign bindings adapted here, historic evidence kept under original identities.',
    'historical_reviews_transfer': False}
write('collection-recipe.json', recipe)
draft = (PRIOR / 'verify_campaign_readonly.py.draft').read_text(encoding='utf-8')
draft = draft.replace("CAMPAIGN = 'gt06-s73-campaign-01'", "CAMPAIGN = '" + CAMPAIGN + "'")
draft = draft.replace("SOURCE_REVISION_EXPECTED = 'cb4d1f6f'", 'SOURCE_REVISION_EXPECTED = None  # Actual coordinator checkpoint proof pending.')
draft = draft.replace("SOURCE = '" + campaign.closure(old) + "'", "SOURCE = '" + digest + "'")
draft = draft.replace('HH-GT06-S73-CAMPAIGN-READONLY-DRAFT-1', 'HH-GT06-S75-CAMPAIGN-READONLY-DRAFT-1')
draft = draft.replace('separate named-commit Git byte verification for cb4d1f6f', 'separate named-commit Git byte verification for the actual S75 source checkpoint')
draft = draft.replace("'S73 focused-validation and five service-remint dependency bridge',", "'S73 focused-validation and five service-remint dependency bridge',\n            'S75 exact-marker and assembly validation plus unchanged service/functional projections',")
ast.parse(draft)
write('verify_campaign_readonly.py.draft', draft)
assert campaign.source_files() == current, 'SOURCE_CHANGED_DURING_PREPARATION'
write('preparation-check.json', {'schema': 'HH-GT06-S75-PREPARATION-CHECK-1',
    'source_stable_during_preparation': True, 'source_count': 49, 'source_closure_sha256': digest,
    'declared_maps_compared': len(comparisons), 'validator_ast_parse': 'PASS_SYNTAX_ONLY',
    'validator_executed': False, 'tests_executed': False, 'engines_launched': False,
    'raw_byte_hash_domains_preserved': True, 'full_raw_evidence_audit': False,
    'formal_acceptance': False, 'critic_verdict': None,
    'output_refs': [ref(REL + '/' + name) for name in ('source-files.json', 'affected-dependency-bridge.json', 'collection-recipe.json', 'verify_campaign_readonly.py.draft')]})
print(json.dumps({'source_count': 49, 'source_closure_sha256': digest, 'changed_runtime': sorted(changed),
    'compared_maps': len(comparisons), 'formal_acceptance': False, 'validators_executed': False}))
