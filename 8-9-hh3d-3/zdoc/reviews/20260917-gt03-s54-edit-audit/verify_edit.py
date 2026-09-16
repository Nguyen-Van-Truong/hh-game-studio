"""Read-only portable audit of the S54 edit03 component, never acceptance."""
from pathlib import Path
import argparse
import copy
import hashlib
import importlib.util
import json
import sys

HERE=Path(__file__).resolve().parent
RUN=HERE.parent/'20260917-gt03-s54-edit-publication-03'
EXPECTED='0fa75dac3afe05a7476ad12c852be221eb84c512f46f853d4c8ee1fab2042a32'
HELPER=HERE.parent/'20260917-gt03-s52-audit/verify_integration.py'
PIN='a4500bf057cd0e7d50201453b427e7124db2c04efb99cc114f8d73606ff31c66'
sha=lambda raw:hashlib.sha256(raw).hexdigest()
assert sha(HELPER.read_bytes())==PIN
spec=importlib.util.spec_from_file_location('s54_edit_raw_audit',HELPER)
base=importlib.util.module_from_spec(spec);sys.modules[spec.name]=base;spec.loader.exec_module(base)
need=base.need


class Evidence(base.Evidence):
    def __init__(self,overlay=None):super().__init__();self.overlay=overlay or {}
    def read(self,path):
        path=Path(path)
        self.add(path)
        return copy.deepcopy(self.overlay[path]) if path in self.overlay else json.loads(path.read_bytes())


def native_records(raw,canonical):
    rows=[];offset=0;previous='0'*64
    while offset<len(raw):
        need(len(rows)<512 and len(raw)-offset>=36,'native frame bound')
        size=int.from_bytes(raw[offset:offset+4],'little')
        need(0<size<=16384 and offset+36+size<=len(raw),'native frame size')
        body=raw[offset+4:offset+4+size];checksum=raw[offset+4+size:offset+36+size]
        need(hashlib.sha256(body).digest()==checksum,'native frame checksum')
        frame=json.loads(body)
        need(canonical(frame)==body and set(frame)=={'format','sequence','previous','event'}
            and frame['format']=='hh-private-events-1' and frame['sequence']==len(rows)+1
            and frame['previous']==previous,'native frame chain')
        offset+=size+36;previous=checksum.hex()
        rows.append({'head':{'sequence':len(rows)+1,'sha256':previous,'size':offset},'event':frame['event']})
    return rows


def verify(overlay=None):
    ev=Evidence(overlay)
    source,files,closure=base.source(ev,RUN);need(closure==EXPECTED,'component closure')
    sys.path.insert(0,str(source.parent))
    state=base.H.module('s54_edit_values',source/'godot-addon/publication_state_v5.py')
    validation=base.H.module('s54_edit_validation',source/'godot-addon/validation_owner.py')
    linux=base.H.module('s54_edit_linux',source/'tests/godot/run_linux_probe.py')
    canonical=validation.canonical_bytes
    capture=ev.read(RUN/'capture.json');report=ev.read(RUN/'publication.json')
    need(capture['passed'] is True and capture['snapshot_unchanged'] is True
        and capture['source_closure_sha256']==closure and capture['candidate_only'] is True
        and capture['gt03_acceptance'] is False,'candidate capture')
    stdout,stderr=base.checked_host(ev,RUN,capture['host'])
    need(not stderr.strip() and base.H.markers(stdout,'HH_EDIT_PUBLICATION_COMPLETE ')==[{'passed':True,'checks':61}],
         'actual complete host exit')
    checks=report['checks']
    need(report['passed'] is True and report['candidate_only'] is True and report['gt03_acceptance'] is False
        and report['source_closure_sha256']==closure and len(checks)==61
        and all(row['passed'] is True for row in checks) and len({r['label'] for r in checks})==61
        and checks==ev.read(RUN/'progress.json'),'native harness check inventory')
    events=ev.read(RUN/'journal-events.json');snapshot=ev.read(RUN/'journal-snapshot.json')
    replay=state.replay(events)
    need(replay.snapshot()==snapshot and snapshot['stopped'] is True,'typed stopped V5 fold')
    custody=ev.read(HERE/'native-custody.json')
    need(sha(canonical(custody['record']))==custody['sha256'],'custody checksum')
    native=ev.read(HERE/'native-capture.json')
    raw=ev.add(HERE/'native-events.bin').read_bytes();records=native_records(raw,canonical)
    need(len(records)==33 and [r['event'] for r in records[4:]]==events
        and records==native['native_records'],'native original event bytes')
    need(records[-1]['head']==custody['record']['events']['binding']['witnessed']==native['native_binding']['witnessed']
        and native['stream_sha256']==sha(raw) and native['stream_size_bytes']==len(raw),'native witnessed stream')
    need(native['registry_unchanged'] is True and native['stream_unchanged'] is True
        and native['native_resources_closed'] is True and native['cleanup_errors']==[],'read-only native audit')
    selected=snapshot['selected']
    need(selected==snapshot['last_good'] and ev.read(HERE/'native-selector.json')==selected['selector']
        and ev.read(HERE/'native-manifest.json')==selected['bundle_manifest']
        and native['selector_version']==selected['selector_version'],'actual selected release')
    base.check_selection({'selector':selected['selector'],'selector_version':selected['selector_version']},canonical)
    roots=list((RUN/'owned/editor').glob('editor-*'));need(len(roots)==1,'one live editor')
    root=roots[0];closed=ev.read(root/'close.json');exited=ev.read(root/'process-exit.json');started=ev.read(root/'process-start.json')
    need(closed==ev.read(RUN/'editor-close.json') and closed['actual_process_exit']==exited
        and exited['exit_code']==closed['wrapper_exit_code']==0 and exited['pid']==started['pid']
        and closed['closed'] is True and closed['held'] is False,'actual editor exit')
    base.checked_job(closed['job'])
    hello=ev.read(root/'hello.json')
    need(hello['pid']==started['pid'] and hello['main_thread'] is True and hello['editor_hint'] is True,'main-thread editor')
    for name in ('stdout.txt','stderr.txt'):need(not base.H.BAD_LOG.search(ev.text(root/name)),'editor diagnostics')
    before=ev.read(RUN/'before.json');after=ev.read(RUN/'after-save.json')
    names=['edit.create','edit.update','edit.undo','edit.redo','edit.remove','edit.restore']
    from studio.protocol.core import Request
    for name in names:
        request=Request.from_dict(ev.read(RUN/(name+'-request.json')))
        command=state.lookup(replay,name,request.digest)
        need(command['phase']=='COMMITTED' and command['edit_prepared']['operation']==request.operation,'edit command binding')
        response=ev.read(RUN/(name+'-response.json'))
        need(canonical(response)==state.lookup_response(replay,name,request.digest)
            ==ev.add(RUN/(name+'-wire.json')).read_bytes(),'exact historical edit response')
        p=response['postconditions']
        need(p['public_ack'] is True and p['effect_scope']=='editor_session'
            and p['files_saved'] is False and p['live_state_durable'] is False,'truthful edit scope')
        checkpoint=command['checkpoint'];prepared=command['edit_prepared']
        def blob(desc):
            content=ev.add(HERE/'blobs'/desc['object_id']).read_bytes()
            need(desc==native['edit_blobs'][desc['object_id']] and sha(content)==desc['sha256']
                and len(content)==desc['identity']['size'],'native edit blob identity')
            return content
        scene=blob(checkpoint['scene_blob']);capraw=blob(checkpoint['capture_blob']);cap=json.loads(capraw)
        observedraw=blob(command['observation_blob']);observed=json.loads(observedraw)
        need(canonical(cap)==capraw and canonical(observed)==observedraw,'canonical edit blob')
        need(state.capture_summary(cap,prepared,checkpoint['observed_ms'])==checkpoint['capture']
            and state.observation_summary(observed,command,snapshot['last_observed_ms'])==command['edit_observation'],
            'typed checkpoint and observation bindings')
        need(sha(scene)==cap['scene_sha256'] and len(scene)==cap['scene_size_bytes'],'checkpoint scene bytes')
        need(ev.read(root/(cap['observation_id']+'.json'))==cap
            and ev.read(root/(observed['observation_id']+'.json'))==observed,'raw actual editor observations')
        current=ev.read(RUN/(name+'-after.json'))
        need(current['state']==observed['semantic_state'] and current['working_files']==before['working_files']
            and current['generation']==before['generation'] and current['root_instance_id']==before['root_instance_id']
            and current['history_id']==before['history_id'],'unsaved state and native history')
    need(ev.read(RUN/'edit.undo-after.json')['state']==ev.read(RUN/'edit.create-after.json')['state']
        and ev.read(RUN/'edit.redo-after.json')['state']==ev.read(RUN/'edit.update-after.json')['state']
        and ev.read(RUN/'edit.restore-after.json')['state']==after['state'],'exact undo/redo/remove restore')
    need(not after['can_undo'] and not after['can_redo'] and after['project_revision']!=before['project_revision'],
         'save history boundary')
    save=state.lookup(replay,'edit.save');need(save['phase']=='COMMITTED'
        and state.lookup_response(replay,'edit.save',save['digest'])==canonical(ev.read(RUN/'save-response.json')),'durable save')
    runs=base.validators(ev,RUN,(validation,linux))
    candidates=[r for r in runs if canonical(r[3]['semantic']['state'])==canonical(after['state'])]
    need(len(candidates)==1,'exact Linux saved semantic state')
    for name,row in selected['bundle_manifest']['files'].items():
        payload=ev.add(root/'project'/name).read_bytes()
        need(sha(payload)==row['sha256'] and len(payload)==row['size_bytes'],'actual selected editor bytes')
        version=native['selected_files'][name];desc=selected['selector']['descriptor']['files'][name]
        need(version=={k:desc[k] for k in version},'native selected FileVersion')
    stopped=ev.read(RUN/'idle-stop-terminal.json');initial=ev.read(RUN/'idle-stop-initial.json')
    need(stopped['stopped'] is True and stopped['stop_persistence']=='DURABLE'
        and initial['response']['stopped'] is True and 0<=initial['response_ms']<500,'durable bounded idle Stop')
    for path in (Path(__file__),HERE/'capture_native.py',HELPER,base.HELPER):ev.add(path)
    return ev,{'passed':True,'source_closure_sha256':closure,'source_files':len(files),'harness_checks':61,
        'native_records':len(records),'native_edit_blobs':len(native['edit_blobs']),'linux_runs':len(runs),
        'portable_files':len(ev.files),'origin_source_unchanged':capture['origin_source_unchanged'],
        'scope':'frozen edit03 component only; HTTP rejection/retry/reopen actions remain harness assertions',
        'gt03_acceptance':False}


def main():
    p=argparse.ArgumentParser();p.add_argument('--write',action='store_true');p.add_argument('--negative',action='store_true');args=p.parse_args()
    ev,report=verify()
    if args.negative:
        cases=[]
        def bad(path,edit):
            value=json.loads(path.read_bytes());edit(value)
            try:verify({path:value})
            except (ValueError,KeyError,AssertionError):cases.append({'path':path.name,'rejected':True})
            else:raise AssertionError('corruption accepted: '+path.name)
        bad(RUN/'capture.json',lambda v:v.update(snapshot_unchanged=False))
        bad(RUN/'publication.json',lambda v:v['checks'][0].update(passed=False))
        bad(RUN/'journal-snapshot.json',lambda v:v.update(stopped=False))
        bad(HERE/'native-capture.json',lambda v:v.update(registry_unchanged=False))
        bad(HERE/'native-selector.json',lambda v:v.update(command_id='other'))
        bad(RUN/'edit.create-response.json',lambda v:v['postconditions'].update(files_saved=True))
        bad(RUN/'edit.undo-after.json',lambda v:v.update(state={'nodes':[]}))
        bad(RUN/'idle-stop-terminal.json',lambda v:v.update(stop_persistence='UNKNOWN'))
        report['corruption_rejections']=len(cases)
        if args.write:(HERE/'tamper-report.json').write_text(json.dumps(cases,indent=2)+'\n',encoding='utf-8')
    if args.write:
        (HERE/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        (HERE/'portable-manifest.json').write_text(json.dumps({'files':ev.files},indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))


if __name__=='__main__':main()
