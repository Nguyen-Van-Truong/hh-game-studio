"""Frozen actual Linux parse/import/fresh-instance observations for closed data.

This is an implementation candidate, not authenticated publication or GT03
acceptance. Never pass arbitrary generated code to a Windows live editor.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

STUDIO = Path(__file__).resolve().parents[2]


def load(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path,value):
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')


def evaluate(executor_result, stdout, stderr, bundle, comparator):
    """Recompute from raw logs and actual owned lifecycle, not a saved verdict."""
    phases=[line for line in stdout.splitlines() if line.startswith('HH_PROFILE_PHASE_')]
    expected=[item for phase in ('parse','import','readback')
              for item in ('HH_PROFILE_PHASE_BEGIN '+phase,'HH_PROFILE_PHASE_END '+phase+' 0')]
    markers=[line.removeprefix('HH_PROFILE_READBACK ') for line in stdout.splitlines()
             if line.startswith('HH_PROFILE_READBACK ')]
    order=[line if line.startswith('HH_PROFILE_PHASE_') else 'HH_PROFILE_READBACK'
           for line in stdout.splitlines()
           if line.startswith(('HH_PROFILE_PHASE_','HH_PROFILE_READBACK '))]
    expected_order=expected[:-1]+['HH_PROFILE_READBACK',expected[-1]]
    result={'passed':False,'public_ack':False,'sandbox_acceptance':False,
            'phases_match':phases==expected,'marker_count':len(markers)}
    native=executor_result.get('container_state') or {}
    host=executor_result.get('command_host') or {}
    job=host.get('job_owner') or {}
    eof=host.get('stream_reader_eof')
    def integer(value, expected):
        return type(value) is int and value == expected
    lifecycle=(executor_result.get('schema')=='hh-gt03-linux-diagnostic-1'
        and executor_result.get('mode')=='profile-validate'
        and executor_result.get('diagnostic_process_clean') is True
        and executor_result.get('profile_eligible') is True
        and executor_result.get('profile_harness_unchanged') is True
        and executor_result.get('profile_harness_sha256') == sha(STUDIO/'godot-addon/validation_bootstrap.gd')
        and executor_result.get('admission',{}).get('acquired') is True
        and integer(executor_result.get('admission',{}).get('maximum_active'),1)
        and executor_result.get('owner_record_retained') is False
        and executor_result.get('errors')==[]
        and all(executor_result.get(key) is True for key in
                ('owned_removed','input_unchanged','snapshot_unchanged','binary_unchanged','log_clean'))
        and integer(native.get('ExitCode'),0) and native.get('Running') is False and integer(native.get('Pid'),0)
        and native.get('OOMKilled') is False and integer(executor_result.get('docker_wait_exit'),0)
        and integer(host.get('exit_code'),0) and integer(host.get('job_active_count'),0)
        and host.get('readers_stopped') is True
        and type(eof) is list and len(eof)==2 and all(value is True for value in eof)
        and host.get('stream_reader_errors')==[None,None]
        and host.get('timed_out') is False and host.get('stream_cap_exceeded') is False
        and host.get('host_error') is None and host.get('evidence_write_error') is None
        and all(job.get(k) is True for k in ('configured','assigned','closed','zero_observed'))
        and all(job.get(k) is False for k in ('tainted','handle_retained'))
        and integer(job.get('active_count'),0) and job.get('failed_operations')==[]
        and job.get('native_error') is None)
    expected_hashes={k:hashlib.sha256(v).hexdigest() for k,v in bundle.files.items()}
    lifecycle=lifecycle and all(executor_result.get(k)==expected_hashes for k in
        ('input_hashes_before','input_hashes_after','snapshot_hashes_after'))
    result['owned_lifecycle_verified']=bool(lifecycle)
    clean=re.search(r'(?m)^(?:SCRIPT ERROR|ERROR|WARNING):|ObjectDB instances leaked',stdout+'\n'+stderr) is None
    if lifecycle and clean and phases==expected and len(markers)==1 and order==expected_order:
        try:
            # The shared parser rejects duplicate keys, invalid Unicode and NaN.
            from studio.protocol.core import parse_json
            observation=parse_json(markers[0].encode('utf-8'))
            result['comparison']=comparator.compare_observation(bundle,observation)
            result['observation']=observation
            result['passed']=True
        except (ValueError,TypeError) as error:
            result['comparison_error']=getattr(error,'code',type(error).__name__)
    return result


def cases(factory):
    script=(b'extends Node3D\n@export var fixture_value: int = 9\n'
            b'@export var move_speed: float = 2.25\n@export var turn_speed: float = 90.0\n'
            b'@export var enabled: bool = false\n')
    baseline=factory.DEFAULT_SCENE
    boxed=baseline.replace(b'load_steps=2',b'load_steps=3').replace(b'[node name="Fixture"',
        b'[sub_resource type="BoxMesh" id="BoxMesh_one"]\nsize = Vector3(3, 2, 1)\n\n[node name="Fixture"')
    boxed+=(b'\n[node name="BoxOne" type="MeshInstance3D" parent="."]\n'
        b'transform = Transform3D(0, -3, 0, 2, 0, 0, 0, 0, 4, 4, 5, 6)\n'
        b'mesh = SubResource("BoxMesh_one")\nmetadata/hh_studio_id = "box-one"\n')
    scalar=boxed.replace(b'fixture_value = 23',b'fixture_value = -23\nmove_speed = 7\nenabled = true')
    nested=boxed+(b'\n[node name="Nested" type="Node3D" parent="BoxOne"]\n'
        b'transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 1, 2, 3)\n'
        b'metadata/hh_studio_id = "nested-one"\n')
    return [('defaults_override',baseline,script),('transformed_box',boxed,script),
            ('typed_scene_override',scalar,script.replace(b'int = 9',b'int = 17')),
            ('tiny_export',baseline,script.replace(b'float = 2.25',b'float = 0.0000000000001')),
            ('nested_node',nested,script)]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--run-id',required=True);args=parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',args.run_id):parser.error('run ID')
    output=args.output.resolve();output.relative_to(STUDIO.parent/'zdoc/reviews')
    output.mkdir(parents=True,exist_ok=False)
    common=load('profile_freeze_input',Path(__file__).with_name('run_editor_probe.py'))
    before=common.inputs();source=output/'source/studio'
    for name,digest in before.items():
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((STUDIO/name).read_bytes())
        if sha(target)!=digest:raise ValueError('changed freeze input')
    runner=load('profile_owned_runner',source/'build/bootstrap/run_fixture.py')
    closure=runner.source_closure_sha256(before)
    save(output/'source-closure.json',{'files':before,'source_closure_sha256':closure})
    # The child interpreter imports exclusively from this complete frozen copy.
    code=('import importlib.util,sys; from pathlib import Path; '
          'p=Path("tests/godot/run_profile_probe.py").resolve(); '
          's=importlib.util.spec_from_file_location("frozen_profile",p); '
          'm=importlib.util.module_from_spec(s);s.loader.exec_module(m); '
          'sys.exit(m.frozen_cases(Path(sys.argv[1])))')
    env=dict(os.environ)
    env['HH_STUDIO_LINUX_GODOT']=str(STUDIO/'.local/tooling/godot-4.7.2-stable-linux/Godot_v4.7.2-stable_linux.x86_64')
    host=runner.run_process([sys.executable,'-B','-c',code,str(output)],cwd=source,
        output=output,timeout=240,label='profile',env=env)
    capture={'run_id':args.run_id,'source_closure_sha256':closure,'host':host,
        'source_unchanged':before==common.inputs(),
        'snapshot_unchanged':all(sha(source/name)==digest for name,digest in before.items()),
        'public_ack':False,'sandbox_acceptance':False,'production_save_verified':False}
    result_path=output/'profile-cases.json'
    capture['cases']=json.loads(result_path.read_bytes()) if result_path.exists() else None
    capture['passed']=bool(capture['cases'] and capture['cases']['passed'] and
        host['exit_code']==host['wrapper_exit_code']==0 and host['tree_verified'] and not host['timed_out']
        and capture['source_unchanged'] and capture['snapshot_unchanged'])
    save(output/'capture.json',capture)
    print(json.dumps({'passed':capture['passed'],'closure':closure,'cases':capture['cases'], 'host':host}))
    return 0 if capture['passed'] else 1


def frozen_cases(output):
    sys.path.insert(0,str(STUDIO.parent))
    comparator=load('frozen_profile_readback',STUDIO/'godot-addon/profile_readback.py')
    executor=load('frozen_profile_executor',STUDIO/'godot-addon/linux_executor.py')
    rows=[]
    for name,scene,script in cases(comparator.factory):
        case=output/name;case.mkdir()
        bundle=comparator.factory.compose(scene,script,scene_revision='sha256:'+hashlib.sha256(scene).hexdigest(),
                                           engine_sha256=executor.BINARY_SHA256)
        comparator.factory.qualify(bundle)
        (case/'manifest.json').write_bytes(bundle.manifest_bytes)
        project=case/'input'
        for relative,raw in bundle.files.items():
            path=project/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
        result=executor.run(project,mode='profile-validate',output=case/'executor',timeout_seconds=20)
        stdout=(case/'executor'/result['stdout']).read_text(encoding='utf-8',errors='strict')
        stderr=(case/'executor'/result['stderr']).read_text(encoding='utf-8',errors='strict')
        verdict=evaluate(result,stdout,stderr,bundle,comparator)
        save(case/'comparison.json',verdict)
        rows.append({'case':name,'passed':verdict['passed'],'project_revision':bundle.project_revision})
        print('HH_PROFILE_CASE '+json.dumps(rows[-1]),flush=True)
    result={'passed':len(rows)==len(cases(comparator.factory)) and all(row['passed'] for row in rows),'cases':rows,
            'public_ack':False,'sandbox_acceptance':False}
    save(output/'profile-cases.json',result)
    return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
