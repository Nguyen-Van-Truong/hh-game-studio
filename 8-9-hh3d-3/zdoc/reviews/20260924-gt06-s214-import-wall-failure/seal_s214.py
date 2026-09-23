from pathlib import Path
import hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[3]
raw=ROOT/'studio/.local/reviews/gt06-s213-formal-01'
sup=ROOT/'studio/.local/reviews/gt06-s213-formal-01-supervisor'
archive=ROOT/'studio/.local/archives/gt06-s213-formal-01-s214-terminal.zip'
packet=ROOT/'zdoc/reviews/20260924-gt06-s214-import-wall-failure'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def rels(base,prefix):
    return [{'path':prefix+'/'+p.relative_to(base).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(base.rglob('*')) if p.is_file() and p.name!='raw-manifest.json']
entries=rels(raw,'raw')+rels(sup,'supervisor')
manifest={
 'schema_id':'hh-studio.gt06-s214-raw-manifest','schema_version':'1.0.0',
 'run_id':'gt06-s213-formal-01','authority':0,'formal_acceptance':False,
 'terminal':'import_stage_wall_limit','files':entries,
 'source_closure_sha256':'6f6c96d4014f4bf1509052c50013dcadd1a27e3671728b80de19f2e3c5bf8127',
 'profile_sha256':'0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85',
 'archive':'studio/.local/archives/gt06-s213-formal-01-s214-terminal.zip'
}
manifest_path=raw/'raw-manifest.json'; manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
manifest_sha=sha(manifest_path)
archive.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    z.write(manifest_path,'raw-manifest.json')
    for e in entries:
        source=(raw/e['path'][4:]) if e['path'].startswith('raw/') else (sup/e['path'][11:])
        z.write(source,e['path'])
archive_sha=sha(archive)
analysis={
 'schema_id':'hh-studio.gt06-s214-import-wall-failure','schema_version':'1.0.0',
 'run_id':'gt06-s213-formal-01','authority':0,'formal_acceptance':False,
 'failure_code':'BENCHMARK_WRAPPER_EXIT','child_failure_code':'StageFailed',
 'phase':{'batch':-1,'phase':'import'},'stage_failure':'STAGE_WALL_LIMIT',
 'effective_wall_seconds':20,'elapsed_seconds':20.29700000002049,
 'completed_batches':0,'partial_merge':False,
 'observed_import':{'sample_count':185,'target_exit':None,'thread_alive':False,'probe_handles_released':True,'handle_close_uncertain':False},
 'cleanup':{'host_wrapper_exit':1,'import_actual_exit':None,'editor_target_exit':None,'owned_tree_zero':True,'owner_closed':True,'jobs_zero_closed':True,'handles_released':True,'cleanup_error':None,'natural_exit_inferred':False},
 'interpretation':'Godot import did not produce an independently recorded target exit before the existing 20-second stage wall limit. This is a bounded environment/stage failure only; it is not a GT06 run, leak, ownership, or root-cause claim.',
 'next_action':'Review import-stage timing/provenance and repair only a proven boundary; do not change wall limit/profile/gate or merge partial data; use a fresh campaign ID.'
}
analysis_sha=sha(packet/'analysis.json') if (packet/'analysis.json').exists() else None
(packet/'analysis.json').write_text(json.dumps(analysis,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8'); analysis_sha=sha(packet/'analysis.json')
seal={
 'schema_id':'hh-studio.gt06-s214-terminal-seal','schema_version':'1.0.0','run_id':'gt06-s213-formal-01','authority':0,'formal_acceptance':False,
 'terminal':'import_stage_wall_limit','raw_root':'studio/.local/reviews/gt06-s213-formal-01 + studio/.local/reviews/gt06-s213-formal-01-supervisor','raw_manifest':'studio/.local/reviews/gt06-s213-formal-01/raw-manifest.json','raw_manifest_sha256':manifest_sha,'archive':'studio/.local/archives/gt06-s213-formal-01-s214-terminal.zip','archive_sha256':archive_sha,'verified_files':len(entries)+1,'completed_batches':0,'host_wrapper_exit':1,'import_actual_exit':None,'editor_target_exit':None,'owned_tree_zero':True,'owner_closed':True,'jobs_zero_closed':True,'handles_released':True,'formal_gate_unchanged':True,'decision':'retain Authority0 failure; no partial merge; no ID reuse; review import-stage boundary before any fresh formal'}
(packet/'terminal-seal.json').write_text(json.dumps(seal,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8'); seal_sha=sha(packet/'terminal-seal.json')
readme='''# S214 — S213 import-stage wall-limit terminal\n\nS213 (`gt06-s213-formal-01`) terminated before batch 0 because the Godot import stage hit the existing 20-second bounded wall limit (`STAGE_WALL_LIMIT`, elapsed 20.297 s). Raw and supervisor evidence are sealed by the manifest and archive. The import observer recorded 185 samples, no target exit receipt, released its probe handle, and no cleanup error; scheduler state is not treated as an exit proof.\n\nThis is Authority 0 diagnostic evidence only. It does not prove a leak, ownership, root cause, or GT06 acceptance. No partial batch is merged. The timeout, baseline, profile, counter/RSS gates, and formal 10×35 contract remain unchanged. A future repair must be tied to a proven import boundary and use a fresh campaign ID.\n'''
(packet/'README.md').write_text(readme,encoding='utf-8'); readme_sha=sha(packet/'README.md')
package={'schema_id':'hh-studio.gt06-s214-package-manifest','schema_version':'1.0.0','run_id':'gt06-s213-formal-01','authority':0,'formal_acceptance':False,'packet':'zdoc/reviews/20260924-gt06-s214-import-wall-failure','files':{'README.md':readme_sha,'analysis.json':analysis_sha,'terminal-seal.json':seal_sha,'raw_manifest_sha256':manifest_sha,'archive_sha256':archive_sha},'source_closure_sha256':'6f6c96d4014f4bf1509052c50013dcadd1a27e3671728b80de19f2e3c5bf8127','profile_sha256':'0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85','gate_policy':'10 fresh pairs x 35 batches; unchanged','decision':'retain import-stage wall-limit failure; review proven boundary before fresh formal'}
(packet/'package-manifest.json').write_text(json.dumps(package,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'manifest_sha256':manifest_sha,'archive_sha256':archive_sha,'verified_files':len(entries)+1,'entries':len(entries)},indent=2))
