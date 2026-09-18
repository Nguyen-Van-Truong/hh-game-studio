"""Preserve/recheck four finished diagnostic cost arms, never runtime acceptance.

Modes: collect (exclusive), verify (read-only), seal (exclusive).
Imports only stdlib and the local metadata-only inventory helper.
"""
from pathlib import Path
import datetime, hashlib, json, os, re, sys
from inventory import ARMS, OUT, ROOT, inventory, plain

SOURCE='e010180a1bf85b7f565e9aa39734f8551caf170a85b36c50598be556b723ce7f'
PROFILE='0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85'
SEAL={'package-manifest.json','package-manifest.sha256'}

def sha(path):
    plain(path);before=path.stat();value=hashlib.sha256(path.read_bytes()).hexdigest();after=path.stat()
    assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
    return value

def load(path):
    plain(path);return json.loads(path.read_bytes())

def write(name,value):
    path=OUT/name;assert path.resolve().is_relative_to(OUT)
    path.parent.mkdir(parents=True,exist_ok=True);plain(path.parent)
    data=value if isinstance(value,bytes) else (json.dumps(value,indent=2,ensure_ascii=False)+'\n').encode()
    with path.open('xb') as f:f.write(data)

def closure(mapping):
    return hashlib.sha256(''.join(k+'\0'+mapping[k]+'\n' for k in sorted(mapping)).encode()).hexdigest()

def selected(row):
    return row['sha256'] is not None and not row['path'].startswith('source/studio/')

def screen(data,name):
    assert not re.search(rb'(?i)(?:Bearer\s+[a-z0-9_\-.]{12,}|-----BEGIN[^\r\n]*PRIVATE KEY-----|sk-[a-zA-Z0-9]{20,})',data),name
    if name.startswith('source/'):return
    def walk(v):
        if isinstance(v,dict):
            for k,item in v.items():
                assert not re.search(r'(?:^|_)(?:token|secret|password|credential|authorization|api_key)(?:$|_)',k,re.I),(name,k)
                walk(item)
        elif isinstance(v,list):
            for item in v:walk(item)
    if name.endswith('.json'):walk(json.loads(data))

def derive():
    saved=load(OUT/'raw-inventory.json');results=[]
    for arm in ARMS:
        raw=Path(saved['roots'][arm+'/raw']);outer=Path(saved['roots'][arm+'/outer'])
        inv=load(raw/'invocation.json');source=inv['source_files'];runtime=load(raw/'runtime-source-files.json')
        assert len(source)==51 and closure(source)==inv['binding']['source_closure_sha256']==SOURCE
        assert inv['binding']['profile_sha256']==PROFILE and inv['arm']==arm and inv['formal_acceptance'] is False
        source_rows=[]
        for name,expected in source.items():
            actual=sha(raw/'source/studio'/name);assert actual==expected
            source_rows.append(dict(path=name,expected_sha256=expected,frozen_sha256=actual))
        helper_rows=[]
        for name,expected in inv['helper_files'].items():
            actual=sha(raw/'source'/name);assert actual==expected
            helper_rows.append(dict(path=name,executed_sha256=expected,frozen_sha256=actual))
        outer_inv=load(outer/'invocation.json')
        assert outer_inv['helper_sha256']==inv['helper_files']['zdoc/reviews/20260918-gt06-s84-probe-cost/measure_cost.py']
        project_rows=[]
        for name,expected in inv['initial_project_files'].items():
            value=sha(raw/'project'/name)
            project_rows.append(dict(path=name,initial_sha256=expected,actual_sha256=value,matches=value==expected))
        for name,expected in runtime.items():
            path=raw/'source/studio'/name if name in source else ROOT/'studio'/name
            assert sha(path)==expected,name
        captures={}
        for lane in ['import-host','editor-host']:
            cap=load(raw/lane/'capture.json');start=load(raw/lane/'process-start.json');end=load(raw/lane/'process-exit.json')
            call=load(raw/lane/'invocation.json')
            assert cap['actual_process_exit']==end and start['pid']==end['pid'] and end['exit_code']==0
            assert cap['completed'] is True and cap['natural_tree_exit'] is True and cap['wrapper_exit_code']==0
            assert call['source_files']==(source if lane=='import-host' else runtime)
            if 'invocation_sha256' in cap:assert cap['invocation_sha256']==sha(raw/lane/'invocation.json')
            for name,expected in cap['artifacts'].items():assert sha(raw/lane/name)==expected
            job=cap['job']
            assert job['closed'] and job['zero_observed'] and job['active_count']==0
            assert not job['close_uncertain'] and not job['create_uncertain'] and not job['handle_retained'] and not job['failed_operations']
            assert not (raw/lane/'stderr.txt').read_bytes().strip()
            captures[lane]=dict(actual_process_start=start,actual_process_exit=end,wrapper_exit_code=cap['wrapper_exit_code'],
                wrapper_pid=cap.get('helper_pid'),wrapper_pid_recorded=('helper_pid' in cap),natural_tree_exit=cap['natural_tree_exit'],
                wrapper_process_handle=cap.get('wrapper_process_handle'),job=job,
                gap='Native/helper exit0 is recorded separately; helper PID is not captured in this receipt' if 'helper_pid' not in cap else None)
        native_index=load(raw/'project/benchmark/out/index.json')
        assert native_index['completed'] is True and native_index['benchmark_complete'] is False
        assert native_index['batches_completed']==1 and native_index['cycles_per_batch']==1
        batch=load(raw/'project/benchmark/out/batch-00.json')
        assert len(batch['cycles'])==1
        observations=[]
        points=sorted(raw.glob('observation-*.json'))
        assert len(points)==(4 if arm=='compact-growth' else 3)
        for i,path in enumerate(points):
            row=load(path);native=row['native'];receipt=raw/f'project/benchmark/out/cost-{i:02d}.json'
            assert native==load(receipt) and row['native_sha256']==sha(receipt)
            assert native['phase']==i and native['pid']==captures['editor-host']['actual_process_exit']['pid']
            assert (raw/f'project/benchmark/input/cost-{i:02d}.ack').read_bytes()==native['run_id'].encode()
            observations.append(dict(phase=i,label=native['label'],objects=native['objects'],resources=native['resources'],
                static_memory_bytes=native['static_memory_bytes'],rss_bytes=row['os']['rss_bytes']['value'],
                held_handles=row['os']['held_handles']['value'],native_mono_us=native['mono_us'],host_mono_us=row['os']['host_mono_us'],
                receipt_sha256=row['native_sha256'],observation_sha256=sha(path)))
        baseline=observations[0]
        for row in observations:
            row['rss_delta_bytes']=row['rss_bytes']-baseline['rss_bytes']
            row['static_delta_bytes']=row['static_memory_bytes']-baseline['static_memory_bytes']
            row['objects_delta']=row['objects']-baseline['objects']
        census=[]
        for path in sorted((raw/'project/benchmark/out').glob('object-*.json')):
            obj=load(path)
            assert obj['inventory_complete_objectdb'] is False and obj['formal_acceptance'] is False
            assert obj['counters_equal_across_collection'] is True and obj['counters_before']==obj['counters_after']
            census.append(dict(file=path.relative_to(raw).as_posix(),bytes=path.stat().st_size,sha256=sha(path),
                **{k:obj.get(k) for k in ['label','inventory_count','unattributed_object_count','inventory_duration_us','counters_before','counters_after',
                'inventory_complete_objectdb','collector_variant','retained_identity_count','retained_ordinary_descriptors','retained_summary_count',
                'ordinary_baseline_content_changes_observed','prior_metadata_for_ordinary_removals','content_change_coverage','per_tree_count_coverage']},
                added_count=len(obj['added']),removed_count=len(obj['removed']),changed_count=len(obj['changed'])))
        assert len(census)=={'original':1,'sham':0,'compact':1,'compact-growth':3}[arm]
        outer_cap=load(outer/'capture.json')
        assert outer_cap['exit_code']==(1 if arm=='original' else 0)
        assert outer_cap['wrapper_exit_code']==0 and outer_cap['tree_verified'] and not outer_cap['timed_out']
        cleanup=load(raw/'cleanup.json')
        assert cleanup==dict(errors=[],formal_acceptance=False,owner_closed=True,probe_handle_retained=False)
        if arm=='original':
            assert load(raw/'failure.json')==dict(detail='',type='AssertionError') and not os.path.lexists(raw/'result.json')
            old=(raw/'source/zdoc/reviews/20260918-gt06-s84-probe-cost/measure_cost.py').read_text()
            assert "assert all(p['native']['objects'] == observations[0]['native']['objects'] for p in observations)" in old
            assert b'AssertionError' in (outer/'cost-stderr.txt').read_bytes()
        else:
            result=load(raw/'result.json')
            assert result['completed_cost_diagnostic'] is True and result['actual_process_exit']==captures['editor-host']['actual_process_exit']
        results.append(dict(arm=arm,formal_acceptance=False,eligible_for_dataset=False,
            outcome='NATIVE_ALLOCATION_EXPERIMENT_COMPLETED_WITH_COLLECTOR_FAILURE' if arm=='original' else 'COST_DIAGNOSTIC_COMPLETED',
            source_closure_sha256=SOURCE,source_files=source_rows,helper_files=helper_rows,
            effective_native_sha256=sha(raw/'project/addons/hh_benchmark/benchmark_native.gd'),
            project_files=project_rows,native_index_completed=True,full_benchmark=False,semantic_cycles=1,
            outer_collector_capture=outer_cap,outer_invocation=outer_inv,captures=captures,cleanup=cleanup,
            observations=observations,census=census,operator_stop_lexists=os.path.lexists(raw/'stop-request.json'),
            collector_failure=(load(raw/'failure.json') if arm=='original' else None),
            original_result_missing=(not os.path.lexists(raw/'result.json'))))
    return dict(authority=0,formal_acceptance=False,source_closure_sha256=SOURCE,arms=results,
        limitations=['Single serial trial per arm; short native diagnostic, no HTTP/native full sequence or campaign acceptance.',
        'RSS is host sampled; Godot static allocator bytes are supplemental, not replacements for RSS.',
        'Object counts drift between two-second phase observations even in sham; no count-stability or no-leak conclusion.',
        'Native census unchanged counters apply only across each synchronous collection, not across phase waits.',
        'Censuses are partial reachable inventories, not full ObjectDB.',
        'Native/editor/import wrapper exit0 is recorded, but their helper PIDs are not in the capture receipts. Import wrapper-handle receipt is absent.',
        'No independent critic, source fix, engine launch or acceptance verdict is supplied by this preservation.'])

def collect():
    assert not (OUT/'copy-map.json').exists()
    initial=load(OUT/'raw-inventory.json')
    assert initial['files']=={k:inventory(Path(v)) for k,v in initial['roots'].items()}
    facts=derive()
    choices=[(key,row) for key,rows in initial['files'].items() for row in rows if selected(row)]
    for key,row in choices:screen((Path(initial['roots'][key])/row['path']).read_bytes(),row['path'])
    copies=[]
    for key,row in choices:
        data=(Path(initial['roots'][key])/row['path']).read_bytes()
        assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']
        destination='raw/'+key+'/'+row['path'];write(destination,data)
        assert sha(OUT/destination)==row['sha256']
        copies.append(dict(path=destination,raw_root=key,raw_path=row['path'],bytes=row['bytes'],sha256=row['sha256']))
    current=[]
    paths=sorted({r['path'] for arm in facts['arms'] for r in arm['helper_files']}|{'studio/build/bootstrap/run_fixture.py'})
    for name in paths:
        data=(ROOT/name).read_bytes();destination='current-context/'+name;write(destination,data)
        value=hashlib.sha256(data).hexdigest()
        current.append(dict(path=name,packet_path=destination,sha256=value,scope='Current file snapshot only; never substituted for per-arm executed source'))
    assert initial['files']=={k:inventory(Path(v)) for k,v in initial['roots'].items()}
    write('copy-map.json',dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),files=copies,
        frozen_source_hash_only=[dict(root=k,**r) for k,rows in initial['files'].items() for r in rows if r['sha256'] and not selected(r)],
        policy='Exact selected bytes; caches/settings/sensitive filename classes not copied; all 51 frozen runtime source files per arm remain hash-addressed in original.',
        limited_secret_screen='Selected evidence sensitive JSON keys and bearer/private-key/API-key byte patterns; controlled helper source is byte-pattern screened only'))
    write('current-helper-comparison.json',dict(current_files=current,
        comparisons=[dict(arm=arm['arm'],path=helper['path'],executed_sha256=helper['executed_sha256'],current_sha256=next(r['sha256'] for r in current if r['path']==helper['path']),
            matches=helper['executed_sha256']==next(r['sha256'] for r in current if r['path']==helper['path'])) for arm in facts['arms'] for helper in arm['helper_files']]))
    write('derived-facts.json',facts)
    write('collection.json',dict(authority=0,formal_acceptance=False,raw_before_after_equal=True,raw_hashed_files=420,metadata_only_exclusions=156,
        exact_copies=len(copies),copied_bytes=sum(r['bytes'] for r in copies),current_context_files=len(current),outcome='FOUR_DIAGNOSTIC_ARMS_PRESERVED'))
    print(json.dumps(load(OUT/'collection.json')))

def verify():
    initial=load(OUT/'raw-inventory.json')
    assert initial['files']=={k:inventory(Path(v)) for k,v in initial['roots'].items()}
    copies=load(OUT/'copy-map.json')['files']
    assert {(r['raw_root'],r['raw_path']) for r in copies}=={(k,r['path']) for k,rows in initial['files'].items() for r in rows if selected(r)}
    assert {r['path'] for r in copies}=={p.relative_to(OUT).as_posix() for p in (OUT/'raw').rglob('*') if p.is_file()}
    for row in copies:assert (OUT/row['path']).stat().st_size==row['bytes'] and sha(OUT/row['path'])==row['sha256']
    assert derive()==load(OUT/'derived-facts.json')
    for row in load(OUT/'current-helper-comparison.json')['current_files']:assert sha(OUT/row['packet_path'])==row['sha256']
    if (OUT/'package-manifest.json').exists():
        assert sha(OUT/'package-manifest.json')==(OUT/'package-manifest.sha256').read_text().strip()
        manifest=load(OUT/'package-manifest.json')
        assert {r['path'] for r in manifest['files']}|SEAL=={p.relative_to(OUT).as_posix() for p in OUT.rglob('*') if p.is_file()}
        for row in manifest['files']:assert sha(OUT/row['path'])==row['sha256'] and (OUT/row['path']).stat().st_size==row['bytes']
    print(json.dumps(dict(status='PRESERVATION_BYTE_STATIC_RECHECK_VERIFIED',formal_acceptance=False,arms=4,exact_copies=len(copies),original_collector_exit=1,editor_import_actual_exits_zero=8)))

def seal():
    assert all(not (OUT/p).exists() for p in SEAL);verify()
    rows=[dict(path=p.relative_to(OUT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(OUT.rglob('*')) if p.is_file()]
    write('package-manifest.json',dict(schema='S84_COST_EVIDENCE_PACKET_1',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),authority=0,formal_acceptance=False,
        hash_domain='SHA256 exact bytes; every packet file except manifest and digest sidecar',files=rows))
    value=sha(OUT/'package-manifest.json');write('package-manifest.sha256',(value+'\n').encode());verify()
    print(json.dumps(dict(packet_sha256=value,sealed_files=len(rows),total_files=len(rows)+2,formal_acceptance=False)))

if __name__=='__main__':
    assert sys.argv[1:] in [['collect'],['verify'],['seal']]
    {'collect':collect,'verify':verify,'seal':seal}[sys.argv[1]]()
