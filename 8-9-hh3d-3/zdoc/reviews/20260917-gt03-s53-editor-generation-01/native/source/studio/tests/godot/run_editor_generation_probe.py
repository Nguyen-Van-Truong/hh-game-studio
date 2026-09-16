"""Actual Windows old-close/new-generation proof; no selector/Linux/auth claim."""
import argparse
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

STUDIO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(STUDIO.parent))
spec=importlib.util.spec_from_file_location('s53_editor_generation',STUDIO/'godot-addon/editor_owner.py')
owner=importlib.util.module_from_spec(spec);sys.modules[spec.name]=owner;spec.loader.exec_module(owner)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    output=args.output.absolute();output.mkdir(parents=True,exist_ok=False)
    source=owner._release()
    for name in ('run_editor_generation_probe.py','test_editor_owner.py'):
        source['tests/godot/'+name]=hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
    for name,digest in source.items():
        target=output/'source/studio'/name;target.parent.mkdir(parents=True,exist_ok=True)
        raw=(STUDIO/name).read_bytes();assert hashlib.sha256(raw).hexdigest()==digest;target.write_bytes(raw)
    report={'ok':False,'public_ack':False,'acceptance':False,'source_files':source,'checks':[],
        'scope':'actual Windows editor lifecycle and readback; pure expected-state fixture, no Linux validation/selector/auth'}
    old=new=None
    def check(label,value):
        report['checks'].append({'label':label,'passed':value is True})
        if value is not True:raise AssertionError(label)
    def denied(label,action):
        try:action()
        except owner.EditorOwnerError:check(label,True)
        else:check(label,False)
    try:
        local=json.loads((STUDIO/'.local/toolchain.local.json').read_bytes())
        binary=Path(local['godot_console']).with_name('Godot_v4.7.2-stable_win64.exe')
        initial=owner.factory.compose(owner.factory.DEFAULT_SCENE,owner.factory.DEFAULT_SCRIPT,
            scene_revision='sha256:'+'0'*64,engine_sha256='8d106cbe6144c2dc7e881d61d2429c1a8a76e6b22ef48bd5e48dcf934953f71e')
        old=owner.EditorOwner(output,initial,editor_binary=binary)
        before=old.inspect();initial_script=old.script_observation()
        check('default_generation_seed_one',before['generation']==1)
        check('initial_script_default_separate_from_scene_override',
            initial_script['script']['defaults']['fixture_value']['value']==7
            and before['state']['nodes'][0]['stored']['fixture_value']==23)
        projection={'operation':'scene.node.update','command_id':'local.dirty',
            'expected_revision':before['revision'],'expected_generation':before['generation'],
            'target_stable_id':'root','payload':{'expected_generation':before['generation'],
                'changes':{'position':[2,3,4]}}}
        old.apply_projection(projection);dirty=old.inspect()
        check('actual_dirty_scene_changed',dirty['revision']!=before['revision'])
        intent=old.prepare_effect('replace.script','sha256:'+'1'*64,'capture',
            expected_generation=dirty['generation'],expected_revision=dirty['revision'],
            deadline_ms=int(time.time()*1000)+10000)
        captured=old.capture(intent);scene=old.capture_bytes(captured)
        new_script=owner.factory.DEFAULT_SCRIPT.replace(b'int = 7',b'int = 9')
        # Closed fixture oracle: the scene override masks the changed default.
        # Only script source SHA changes in the already observed full scene state.
        # This is not presented as a registered Linux validation observation.
        expected=owner.parse_json(old.captured_semantic(captured))
        expected['nodes'][0]['stored']['script']['source_sha256']=hashlib.sha256(new_script).hexdigest()
        expected_bytes=owner.canonical_bytes(expected)
        candidate=owner.factory.compose(scene,new_script,scene_revision='sha256:'+hashlib.sha256(expected_bytes).hexdigest(),
            engine_sha256=initial.engine_sha256)
        owner.factory.qualify(candidate)
        (output/'expected-semantic.json').write_bytes(expected_bytes)
        (output/'candidate-manifest.json').write_bytes(candidate.manifest_bytes)
        report['old_identity']=old.identity
        retired=old.retire_for_replacement('replace.script','sha256:'+'1'*64,
            retirement_intent_id='retire.native',expected_snapshot=dirty,deadline_ms=int(time.time()*1000)+10000)
        retirement=old.retirement_observation(retired);report['retirement']=retirement
        check('old_actual_exit_before_successor',retirement['cleanup']['actual_process_exit']['exit_code']==0
            and retirement['cleanup']['job']['closed'] is True and retirement['cleanup']['job']['zero_observed'] is True)
        denied('copied_retirement_rejected',lambda:old.retirement_observation(replace(retired)))
        selection={'generation':1,'identity':'sha256:'+'2'*64}
        new,receipt=owner.EditorOwner.open_selected_generation(old,retired,output,candidate,editor_binary=binary,
            selection=selection,semantic_bytes=expected_bytes)
        facts=new.observation(receipt,candidate);report['adoption']=facts
        check('new_process_identity_bound',facts['old_editor']==report['old_identity']
            and facts['new_editor']['session_id']!=facts['old_editor']['session_id']
            and int(facts['new_editor']['creation_filetime'])>int(facts['old_editor']['creation_filetime']))
        check('successor_generation_strictly_advances',facts['generation_after']==dirty['generation']+1)
        check('close_completed_before_new_launch_phase',retirement['close_completed_ms']<=facts['effect_started_ms'])
        check('full_scene_semantics_match',owner.canonical_bytes(facts['semantic_state'])==expected_bytes)
        check('changed_default_observed_despite_override',facts['script']['defaults']['fixture_value']['value']==9
            and facts['semantic_state']['nodes'][0]['stored']['fixture_value']==23)
        check('both_script_source_and_disk_hash',facts['script']['source_sha256']==facts['script']['disk_sha256']
            ==hashlib.sha256(new_script).hexdigest())
        check('complete_eleven_input_bytes',facts['working_files']==owner._metadata(candidate.files))
        check('new_history_boundary',facts['history_boundary'] is True
            and new.inspect()['can_undo'] is False and new.inspect()['can_redo'] is False)
        # Use CURRENT revision with OLD generation to isolate the generation guard.
        stale={**projection,'command_id':'stale.epoch','expected_revision':facts['semantic_revision']}
        denied('old_generation_rejected_with_current_revision',lambda:new.apply_projection(stale))
        denied('copied_adoption_receipt_rejected',lambda:new.observation(replace(receipt),candidate))
        report['new_close']=new.close()
        check('new_actual_clean_exit',report['new_close']['actual_process_exit']['exit_code']==0
            and report['new_close']['job']['zero_observed'] is True and report['new_close']['job']['closed'] is True)
        check('source_unchanged',all(hashlib.sha256((STUDIO/name).read_bytes()).hexdigest()==digest for name,digest in source.items()))
        report['ok']=True
    except BaseException as error:
        report['failure']=type(error).__name__+': '+str(error)
        report['cause']=str(error.__cause__) if error.__cause__ else None
    finally:
        errors=[]
        for name,value in (('new',new),('old',old)):
            if value is not None:
                try:report[name+'_close']=value.close()
                except BaseException as error:errors.append({'owner':name,'failure':str(error)})
        if errors:report['cleanup_failures']=errors;report['ok']=False
        report['artifacts']={path.relative_to(output).as_posix():hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(output.rglob('*')) if path.is_file() and not any(part in
            ('.godot','__pycache__','appdata','localappdata','temp','tmp') for part in path.relative_to(output).parts)}
        (output/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report.get(k) for k in ('ok','failure','cause','cleanup_failures')}))
    return 0 if report['ok'] else 2

if __name__=='__main__':raise SystemExit(main())
